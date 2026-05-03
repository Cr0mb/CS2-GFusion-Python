"""GFusion offset manager.

Ported from GScript-CS2-Python-Closet-Cheat-main/Process/offset_manager.py.

Loading priority:
  1) Local JSON files (cs2-dumper-main/output/*.json or GFusion/offsets/*.json)
  2) Runtime signature scanning of cs2.exe modules
  3) The static Process.offsets.Offsets class (last-resort frozen snapshot)

Returns ``(offsets_ns, class_offsets_ns)`` where both are SimpleNamespace.
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import struct
import sys
from ctypes import wintypes
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(wintypes.BYTE)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


class ModuleInfo:
    def __init__(self, name: str, base: int, size: int):
        self.name = name
        self.base = base
        self.size = size


class ProcessReader:
    """Minimal RPM-based reader for sig-scanning."""

    def __init__(self, process_name: str = "cs2.exe"):
        self.process_name = process_name
        self.handle = None
        self.process_id: Optional[int] = None
        self.modules: Dict[str, ModuleInfo] = {}
        self.kernel32 = ctypes.windll.kernel32

    def open(self) -> bool:
        self.process_id = self._find_process(self.process_name)
        if not self.process_id:
            return False
        self.handle = self.kernel32.OpenProcess(
            PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, self.process_id
        )
        return bool(self.handle)

    def close(self):
        if self.handle:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None

    def _find_process(self, name: str) -> Optional[int]:
        snap = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == -1:
            return None
        try:
            entry = PROCESSENTRY32()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
            if self.kernel32.Process32First(snap, ctypes.byref(entry)):
                while True:
                    if entry.szExeFile.decode("utf-8", errors="ignore").lower() == name.lower():
                        return entry.th32ProcessID
                    if not self.kernel32.Process32Next(snap, ctypes.byref(entry)):
                        break
        finally:
            self.kernel32.CloseHandle(snap)
        return None

    def enumerate_modules(self) -> Dict[str, ModuleInfo]:
        if not self.handle:
            return {}
        snap = self.kernel32.CreateToolhelp32Snapshot(
            TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, self.process_id
        )
        if snap == -1:
            return {}
        try:
            entry = MODULEENTRY32()
            entry.dwSize = ctypes.sizeof(MODULEENTRY32)
            if self.kernel32.Module32First(snap, ctypes.byref(entry)):
                while True:
                    name = entry.szModule.decode("utf-8", errors="ignore")
                    base = ctypes.addressof(entry.modBaseAddr.contents) if entry.modBaseAddr else 0
                    self.modules[name] = ModuleInfo(name=name, base=base, size=entry.modBaseSize)
                    if not self.kernel32.Module32Next(snap, ctypes.byref(entry)):
                        break
        finally:
            self.kernel32.CloseHandle(snap)
        return self.modules

    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        if not self.handle:
            return None
        buf = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t(0)
        ok = self.kernel32.ReadProcessMemory(
            self.handle, ctypes.c_void_p(address), buf, size, ctypes.byref(read)
        )
        if ok and read.value == size:
            return bytes(buf.raw)
        return None

    def read_i32(self, address: int) -> Optional[int]:
        d = self.read_memory(address, 4)
        return struct.unpack("<i", d)[0] if d else None

    def read_u64(self, address: int) -> Optional[int]:
        d = self.read_memory(address, 8)
        return struct.unpack("<Q", d)[0] if d else None

    read_ptr = read_u64

    def read_string(self, address: int, max_length: int = 256) -> Optional[str]:
        d = self.read_memory(address, max_length)
        if not d:
            return None
        try:
            null = d.index(0)
            return d[:null].decode("utf-8", errors="ignore")
        except ValueError:
            return d.decode("utf-8", errors="ignore")


class SignatureScanner:
    """Pattern-driven offset extraction. Patterns mirror cs2-dumper-main."""

    OFFSET_PATTERNS = {
        "client.dll": {
            "dwCSGOInput": "488905${'} 0f57c0 0f1105",
            "dwEntityList": "48890d${'} e9${} cc",
            "dwGameEntitySystem": "488b1d${'} 48891d[4] 4c63b3",
            "dwGameEntitySystem_highestEntityIndex": "ff81u4 4885d2",
            "dwGameRules": "f6c1010f85${} 4c8b05${'} 4d85",
            "dwGlobalVars": "488915${'} 488942",
            "dwGlowManager": "488b05${'} c3 cccccccccccccccc 8b41",
            "dwLocalPlayerController": "488b05${'} 4189be",
            "dwPlantedC4": "488b15${'} 41ffc0 488d4c24? 448905[4]",
            "dwPrediction": "488d05${'} c3 cccccccccccccccc 405356 4154",
            "dwSensitivity": "488d0d${[8]'} 660f6ecd",
            "dwSensitivity_sensitivity": "488d7eu1 480fbae0? 72? 85d2 490f4fff",
            "dwViewMatrix": "488d0d${'} 48c1e006",
            "dwViewRender": "488905${'} 488bc8 4885c0",
            "dwWeaponC4": "488b15${'} 488b5c24? ffc0 8905${} 488bc6 488934ea 80be",
        },
        "engine2.dll": {
            "dwBuildNumber": "8905${'} 488d0d${} ff15${} 488b0d",
            "dwNetworkGameClient": "48893d${'} ff87",
            "dwNetworkGameClient_clientTickCount": "8b81u4 c3 cccccccccccccccccc 8b81${} c3 cccccccccccccccccc 83b9",
            "dwNetworkGameClient_deltaTick": "4c8db7u4 4c897c24",
            "dwNetworkGameClient_isBackgroundMap": "0fb681u4 c3 cccccccccccccccc 0fb681${} c3 cccccccccccccccc 4053",
            "dwNetworkGameClient_localPlayer": "428b94d3u4 5b 49ffe3 32c0 5b c3 cccccccccccccccc 4053",
            "dwNetworkGameClient_maxClients": "8b81u4 c3????????? 8b81[4] c3????????? 8b81",
            "dwNetworkGameClient_serverTickCount": "8b81u4 c3 cccccccccccccccccc 83b9",
            "dwNetworkGameClient_signOnState": "448b81u4 488d0d",
            "dwWindowHeight": "8b05${'} 8903",
            "dwWindowWidth": "8b05${'} 8907",
        },
        "inputsystem.dll": {"dwInputSystem": "488905${'} 33c0"},
        "matchmaking.dll": {"dwGameTypes": "488d0d${'} ff90"},
        "soundsystem.dll": {
            "dwSoundSystem": "488d05${'} c3 cccccccccccccccc 488915",
            "dwSoundSystem_engineViewData": "0f1147u1 0f104e? 0f118f",
        },
    }

    @staticmethod
    def parse_pattern(pattern: str) -> List[Optional[int]]:
        pattern = pattern.replace(" ", "")
        pattern = re.sub(r"\$\{[^\}]*\}", "????", pattern)
        pattern = re.sub(r"\[[0-9]+\]", lambda m: "?" * int(m.group()[1:-1]), pattern)
        pattern = re.sub(r"u[0-9]+", lambda m: "?" * int(m.group()[1:]), pattern)
        out: List[Optional[int]] = []
        i = 0
        while i < len(pattern):
            ch = pattern[i]
            if ch == "?":
                out.append(None)
                i += 1
            elif i + 1 < len(pattern) and all(c in "0123456789ABCDEFabcdef" for c in pattern[i : i + 2]):
                out.append(int(pattern[i : i + 2], 16))
                i += 2
            else:
                i += 1
        return out

    @staticmethod
    def find_pattern(data: bytes, pattern_bytes: List[Optional[int]]) -> List[int]:
        results: List[int] = []
        plen = len(pattern_bytes)
        if plen == 0 or plen > len(data):
            return results
        anchors = [(i, b) for i, b in enumerate(pattern_bytes) if b is not None]
        if not anchors:
            return results
        last_pos, last_b = anchors[-1]
        pos = 0
        while pos <= len(data) - plen:
            try:
                found = data.index(bytes([last_b]), pos + last_pos, len(data) - plen + 1)
            except ValueError:
                break
            pos = found - last_pos
            ok = True
            for i, pb in enumerate(pattern_bytes):
                if pb is not None and data[pos + i] != pb:
                    ok = False
                    break
            if ok:
                results.append(pos)
                return results[:1]
            pos += 1
        return results

    @staticmethod
    def extract_rip_offset(data: bytes, match_offset: int, base: int) -> Optional[int]:
        pos = match_offset
        if pos + 7 >= len(data):
            return None
        opcodes_3byte = [
            b"\x48\x89\x05", b"\x48\x8B\x05", b"\x48\x8D\x05",
            b"\x48\x8B\x1D", b"\x48\x89\x1D", b"\x48\x89\x15",
            b"\x48\x8D\x0D", b"\x48\x8B\x15", b"\x48\x8B\x0D",
            b"\x48\x89\x0D", b"\x48\x89\x3D", b"\x48\x8B\x3D",
        ]
        for op in opcodes_3byte:
            if data[pos : pos + 3] == op:
                rel = struct.unpack("<i", data[pos + 3 : pos + 7])[0]
                return (base + pos + 7 + rel) - base
        opcodes_2byte = [
            b"\x89\x05", b"\x8B\x05", b"\x8D\x05",
            b"\x8D\x15", b"\x8B\x15", b"\x8B\x1D",
            b"\x89\x15", b"\x89\x0D", b"\x8D\x0D",
        ]
        for op in opcodes_2byte:
            if data[pos : pos + 2] == op:
                rel = struct.unpack("<i", data[pos + 2 : pos + 6])[0]
                return (base + pos + 6 + rel) - base
        if data[pos : pos + 3] == b"\x48\x8D\x7E":
            return data[pos + 3]
        if len(data) > pos + 4 and data[pos : pos + 2] == b"\xff\x81":
            return struct.unpack("<I", data[pos + 2 : pos + 6])[0]
        if len(data) > pos + 4 and data[pos : pos + 3] == b"\x4c\x8d\xb7":
            return struct.unpack("<I", data[pos + 3 : pos + 7])[0]
        if len(data) > pos + 4 and data[pos : pos + 3] == b"\x0f\xb6\x81":
            return struct.unpack("<I", data[pos + 3 : pos + 7])[0]
        if len(data) > pos + 4 and data[pos : pos + 3] == b"\x42\x8b\x94":
            return struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        if len(data) > pos + 4 and data[pos : pos + 2] == b"\x8b\x81":
            return struct.unpack("<I", data[pos + 2 : pos + 6])[0]
        if len(data) > pos + 4 and data[pos : pos + 3] == b"\x44\x8b\x81":
            return struct.unpack("<I", data[pos + 3 : pos + 7])[0]
        return None


class SchemaScanner:
    """Walk schemasystem.dll's UtlTsHash to recover class field offsets."""

    def __init__(self, process: ProcessReader):
        self.process = process

    def scan_schemas(self) -> Dict[str, Dict[str, int]]:
        if "schemasystem.dll" not in self.process.modules:
            return {}
        module = self.process.modules["schemasystem.dll"]
        data = self.process.read_memory(module.base, min(module.size, 20 * 1024 * 1024))
        if not data:
            return {}
        schema_addr: Optional[int] = None
        for m in re.finditer(b"\x4c\x8d\x35", data):
            off = m.start()
            if off + 10 >= len(data):
                continue
            if data[off + 7 : off + 10] == b"\x0f\x28\x45":
                rel = struct.unpack("<i", data[off + 3 : off + 7])[0]
                schema_addr = module.base + off + 7 + rel
                break
        if not schema_addr:
            return {}
        return self._read_all_classes(schema_addr)

    def _read_all_classes(self, schema_addr: int) -> Dict[str, Dict[str, int]]:
        classes: Dict[str, Dict[str, int]] = {}
        type_scopes_ptr = self.process.read_ptr(schema_addr + 0x190 + 8)
        type_scopes_count = self.process.read_i32(schema_addr + 0x190)
        if not type_scopes_ptr or not type_scopes_count:
            return classes
        for i in range(min(type_scopes_count, 100)):
            scope_ptr = self.process.read_ptr(type_scopes_ptr + (i * 8))
            if not scope_ptr:
                continue
            classes.update(self._read_type_scope(scope_ptr))
        return classes

    def _read_type_scope(self, scope_ptr: int) -> Dict[str, Dict[str, int]]:
        classes: Dict[str, Dict[str, int]] = {}
        hash_base = scope_ptr + 0x560
        buckets_base = hash_base + 0x60
        visited: set = set()
        for bucket_idx in range(256):
            bucket_addr = buckets_base + (bucket_idx * 24)
            bucket_first = self.process.read_ptr(bucket_addr + 8)
            if not bucket_first:
                continue
            current = bucket_first
            it = 0
            while current and it < 5000:
                if current in visited:
                    break
                visited.add(current)
                data_ptr = self.process.read_ptr(current + 16)
                next_ptr = self.process.read_ptr(current + 8)
                if data_ptr:
                    info = self._read_class_info(data_ptr)
                    if info:
                        name, fields = info
                        classes[name] = fields
                current = next_ptr
                it += 1
        return classes

    def _read_class_info(self, class_ptr: int) -> Optional[Tuple[str, Dict[str, int]]]:
        name_ptr = self.process.read_ptr(class_ptr + 8)
        # AG2 layout: fieldCount @ +0x24, fieldsPtr @ +0x30
        fc_data = self.process.read_memory(class_ptr + 36, 2)
        fc = struct.unpack("<H", fc_data)[0] if fc_data else 0
        fields_ptr = self.process.read_ptr(class_ptr + 48)
        if not name_ptr:
            return None
        name = self.process.read_string(name_ptr, 128)
        if not name:
            return None
        fields: Dict[str, int] = {}
        if fields_ptr and fc > 0:
            for i in range(min(fc, 200)):
                field_addr = fields_ptr + (i * 32)
                fn_ptr = self.process.read_ptr(field_addr)
                off_data = self.process.read_memory(field_addr + 16, 4)
                off = struct.unpack("<i", off_data)[0] if off_data else 0
                if fn_ptr:
                    fn = self.process.read_string(fn_ptr, 128)
                    if fn:
                        if fn == "m_modelState" and name == "CSkeletonInstance":
                            fields["m_pBoneArray"] = off + 128
                        else:
                            fields[fn] = off
        return (name, fields)


# Canonical schema-class -> field assignments. JSON flatten order is
# nondeterministic, so we re-apply these *after* the flat dict is built so
# common names like ``m_iHealth`` resolve to the right class.
CANONICAL_OWNERS: Dict[str, Tuple[str, ...]] = {
    "C_BaseEntity": ("m_fFlags", "m_iHealth", "m_iTeamNum", "m_lifeState",
                     "m_vecVelocity", "m_pGameSceneNode"),
    "C_BasePlayerPawn": ("m_vOldOrigin", "m_pWeaponServices", "m_pObserverServices"),
    "C_CSPlayerPawnBase": ("m_flFlashDuration",),
    "C_CSPlayerPawn": ("m_bIsScoped", "m_angEyeAngles", "m_iShotsFired", "m_iIDEntIndex"),
    "CBasePlayerController": ("m_hPawn", "m_iszPlayerName"),
    "CCSPlayerController": ("m_hPlayerPawn", "m_pInGameMoneyServices"),
    "C_EconEntity": ("m_AttributeManager",),
    "C_EconItemView": ("m_iItemDefinitionIndex",),
    "C_AttributeContainer": ("m_Item",),
    "CSkeletonInstance": ("m_modelState",),
    "CGameSceneNode": ("m_bDormant", "m_vecAbsOrigin"),
    "CPlayer_WeaponServices": ("m_hActiveWeapon",),
    "CPlayer_ObserverServices": ("m_hObserverTarget",),
    "CCSPlayerController_InGameMoneyServices": ("m_iAccount",),
}


def _candidate_dump_dirs() -> List[str]:
    """Return JSON-dump directories to try, in priority order."""
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)  # CS2-GFusion-Python-main/
    parent = os.path.dirname(project_root)  # GFusion/
    return [
        os.path.join(project_root, "offsets"),
        os.path.join(parent, "cs2-dumper-main", "output"),
        os.path.join(project_root, "cs2-dumper-main", "output"),
    ]


def _load_from_json() -> Optional[Tuple[SimpleNamespace, SimpleNamespace]]:
    for d in _candidate_dump_dirs():
        offsets_file = os.path.join(d, "offsets.json")
        client_file = os.path.join(d, "client_dll.json")
        if not (os.path.exists(offsets_file) and os.path.exists(client_file)):
            continue
        try:
            with open(offsets_file, "r", encoding="utf-8") as f:
                off_data = json.load(f)
            with open(client_file, "r", encoding="utf-8") as f:
                client_data = json.load(f)
        except Exception as e:
            logger.error(f"[OffsetManager] Failed to read JSON in {d}: {e}")
            continue

        flat: Dict[str, int] = {}
        for _mod, mod_offs in off_data.items():
            if isinstance(mod_offs, dict):
                for name, val in mod_offs.items():
                    flat[name] = val

        class_ns: Dict[str, SimpleNamespace] = {}
        if "client.dll" in client_data:
            classes = client_data["client.dll"].get("classes", {})
            for cls_name, cls_info in classes.items():
                fields = cls_info.get("fields", {})
                class_ns[cls_name] = SimpleNamespace(**fields)
                for f_name, f_off in fields.items():
                    if f_name not in flat:
                        flat[f_name] = f_off

        for cls_name, field_names in CANONICAL_OWNERS.items():
            cls = class_ns.get(cls_name)
            if not cls:
                continue
            for f_name in field_names:
                if hasattr(cls, f_name):
                    flat[f_name] = getattr(cls, f_name)

        # m_pBoneArray = m_modelState + 0x80
        if "CSkeletonInstance" in class_ns and hasattr(class_ns["CSkeletonInstance"], "m_modelState"):
            flat["m_pBoneArray"] = class_ns["CSkeletonInstance"].m_modelState + 0x80

        if "dwViewAngles" not in flat and "dwCSGOInput" in flat:
            flat["dwViewAngles"] = flat["dwCSGOInput"] + 0x688
        if "dwLocalPlayerPawn" not in flat and "dwPrediction" in flat:
            flat["dwLocalPlayerPawn"] = flat["dwPrediction"] + 0xF0

        flat.setdefault("m_aimPunchAngle", 0)
        flat.setdefault("m_pClippingWeapon", 0)

        logger.info(f"[OffsetManager] Loaded offsets from JSON dir: {d}")
        return SimpleNamespace(**flat), SimpleNamespace(**class_ns)
    return None


def _load_from_signature_scan() -> Optional[Tuple[SimpleNamespace, SimpleNamespace]]:
    process = ProcessReader("cs2.exe")
    if not process.open():
        return None
    try:
        process.enumerate_modules()
        flat: Dict[str, int] = {}
        for mod_name, patterns in SignatureScanner.OFFSET_PATTERNS.items():
            if mod_name not in process.modules:
                continue
            module = process.modules[mod_name]
            data = process.read_memory(module.base, min(module.size, 100 * 1024 * 1024))
            if not data:
                continue
            for off_name, pattern in patterns.items():
                pb = SignatureScanner.parse_pattern(pattern)
                matches = SignatureScanner.find_pattern(data, pb)
                if matches:
                    rva = SignatureScanner.extract_rip_offset(data, matches[0], module.base)
                    if rva is not None:
                        flat[off_name] = rva

        if "client.dll" in process.modules:
            module = process.modules["client.dll"]
            client_data = process.read_memory(module.base, min(module.size, 120 * 1024 * 1024))
            if client_data:
                if "dwCSGOInput" in flat:
                    p = SignatureScanner.parse_pattern("f2420f108428????")
                    m = SignatureScanner.find_pattern(client_data, p)
                    if m:
                        pos = m[0] + 6
                        if pos + 4 <= len(client_data):
                            flat["dwViewAngles"] = flat["dwCSGOInput"] + struct.unpack(
                                "<I", client_data[pos : pos + 4]
                            )[0]
                if "dwPrediction" in flat:
                    p = SignatureScanner.parse_pattern("4c39b6???? 74? 4488be")
                    m = SignatureScanner.find_pattern(client_data, p)
                    if m:
                        pos = m[0] + 3
                        if pos + 4 <= len(client_data):
                            flat["dwLocalPlayerPawn"] = flat["dwPrediction"] + struct.unpack(
                                "<I", client_data[pos : pos + 4]
                            )[0]

        if "dwLocalPlayerController" not in flat and "dwLocalPlayerPawn" in flat:
            flat["dwLocalPlayerController"] = flat["dwLocalPlayerPawn"]
        if "dwLocalPlayerPawn" not in flat and "dwLocalPlayerController" in flat:
            flat["dwLocalPlayerPawn"] = flat["dwLocalPlayerController"]

        schema = SchemaScanner(process).scan_schemas()
        class_ns: Dict[str, SimpleNamespace] = {}
        for cls_name, fields in schema.items():
            class_ns[cls_name] = SimpleNamespace(**fields)
            for fn, off in fields.items():
                flat[fn] = off

        flat.setdefault("m_aimPunchAngle", 0)
        flat.setdefault("m_pClippingWeapon", 0)
        logger.info("[OffsetManager] Loaded offsets via runtime signature scan")
        return SimpleNamespace(**flat), SimpleNamespace(**class_ns)
    finally:
        process.close()


def _load_from_static_class() -> Tuple[SimpleNamespace, SimpleNamespace]:
    """Last-ditch fallback: use the frozen Process.offsets.Offsets snapshot."""
    try:
        from . import offsets as _o  # type: ignore
    except Exception:
        from Process import offsets as _o  # type: ignore
    flat: Dict[str, Any] = {}
    for k in dir(_o.Offsets):
        if k.startswith("_"):
            continue
        v = getattr(_o.Offsets, k)
        if isinstance(v, int):
            flat[k] = v
    flat.setdefault("m_aimPunchAngle", 0)
    flat.setdefault("m_pClippingWeapon", 0)
    logger.warning("[OffsetManager] Using STATIC offsets snapshot (Process.offsets.Offsets)")
    return SimpleNamespace(**flat), SimpleNamespace()


_offsets_cache: Optional[SimpleNamespace] = None
_class_offsets_cache: Optional[SimpleNamespace] = None


def get_offsets(force_update: bool = False) -> Tuple[SimpleNamespace, SimpleNamespace]:
    """Return ``(offsets_ns, class_offsets_ns)``.

    Tries local JSON first, then live signature scanning, finally the
    frozen ``Process.offsets.Offsets`` snapshot. The first non-empty source
    wins and is cached for the rest of the session.
    """
    global _offsets_cache, _class_offsets_cache
    if _offsets_cache and _class_offsets_cache and not force_update:
        return _offsets_cache, _class_offsets_cache

    result = _load_from_json()
    if result is None:
        try:
            result = _load_from_signature_scan()
        except Exception as e:
            logger.error(f"[OffsetManager] Signature scan failed: {e}")
            result = None
    if result is None:
        result = _load_from_static_class()

    _offsets_cache, _class_offsets_cache = result
    return _offsets_cache, _class_offsets_cache


def set_global_offsets(offsets_ns: SimpleNamespace, class_offsets_ns: Optional[SimpleNamespace] = None) -> None:
    """Cache offsets globally so other modules can call ``get_offsets`` without rescanning."""
    global _offsets_cache, _class_offsets_cache
    _offsets_cache = offsets_ns
    _class_offsets_cache = class_offsets_ns or SimpleNamespace()
