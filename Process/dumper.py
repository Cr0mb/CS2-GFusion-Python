"""Runtime CS2 offset dumper — Python port of GHax_Free_v2/Core/Dumper.cpp.

Three-phase pipeline:
  1. Pattern-scan client.dll / inputsystem.dll / matchmaking.dll for module-RVA
     offsets (dwEntityList, dwViewMatrix, dwLocalPlayerPawn, dwViewAngles, ...).
  2. Walk client.dll's button linked list to recover key-button state RVAs.
  3. Walk schemasystem.dll's TypeScopes -> UtlTsHash buckets -> class bindings
     -> field arrays to recover live schema field offsets (m_iHealth,
     m_pGameSceneNode, m_hPlayerPawn, ...).

The output mirrors the C++ Dumper exactly, so when CS2 ships a new build the
Python features get fresh offsets the next time the user launches GFusion
without waiting for a2x/cs2-dumper to publish a new offsets.json.
"""

from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from typing import Optional, List, Tuple


# ---------------------------------------------------------------------------
# Toolhelp module enumeration
# ---------------------------------------------------------------------------

TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


def find_module(pid: int, module_name: str) -> Tuple[int, int]:
    """Return (base, size) for the named module in the target process, or (0, 0)."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if not snap or snap == INVALID_HANDLE_VALUE:
        return 0, 0
    try:
        me = MODULEENTRY32W()
        me.dwSize = ctypes.sizeof(me)
        if not k32.Module32FirstW(snap, ctypes.byref(me)):
            return 0, 0
        target = module_name.lower()
        while True:
            if me.szModule.lower() == target:
                return int(me.modBaseAddr or 0), int(me.modBaseSize)
            if not k32.Module32NextW(snap, ctypes.byref(me)):
                break
        return 0, 0
    finally:
        k32.CloseHandle(snap)


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def parse_pattern(pattern: str) -> List[Tuple[int, bool]]:
    """'48 8D 0D ?? ?? ?? ?? E9' -> [(0x48, False), ..., (0, True), ..., (0xE9, False)]"""
    out: List[Tuple[int, bool]] = []
    for tok in pattern.split():
        if tok == "??" or tok == "?":
            out.append((0, True))
        else:
            out.append((int(tok, 16), False))
    return out


def find_pattern(data: bytes, pat: List[Tuple[int, bool]], start: int = 0) -> int:
    """Anchored search using bytes.find for the longest non-wildcard run.

    A naive byte-by-byte Python loop over the 30MB client.dll image takes
    multiple seconds per pattern. By anchoring on the longest concrete run
    we hand the inner search to libc-speed memchr/SSE inside CPython.
    """
    if not pat or len(data) < len(pat):
        return -1
    plen = len(pat)

    # Pick the longest run of concrete bytes as the anchor.
    best_run_start = 0
    best_run = b""
    run_start = -1
    run_bytes = bytearray()
    for i, (val, wild) in enumerate(pat):
        if wild:
            if run_start >= 0 and len(run_bytes) > len(best_run):
                best_run = bytes(run_bytes)
                best_run_start = run_start
            run_start = -1
            run_bytes = bytearray()
        else:
            if run_start < 0:
                run_start = i
                run_bytes = bytearray()
            run_bytes.append(val)
    if run_start >= 0 and len(run_bytes) > len(best_run):
        best_run = bytes(run_bytes)
        best_run_start = run_start

    if not best_run:
        # Entirely wildcards -> first index in range is a "match".
        return start if start + plen <= len(data) else -1

    end_limit = len(data) - plen
    pos = start
    while pos <= end_limit:
        # bytes.find drops to memmem/SSE -> orders of magnitude faster.
        anchor = data.find(best_run, pos + best_run_start)
        if anchor < 0:
            return -1
        candidate = anchor - best_run_start
        if candidate < pos:
            pos = anchor + 1
            continue
        if candidate > end_limit:
            return -1
        ok = True
        for j, (val, wild) in enumerate(pat):
            if not wild and data[candidate + j] != val:
                ok = False
                break
        if ok:
            return candidate
        pos = candidate + 1
    return -1


def resolve_rip(data: bytes, match_off: int, rip_off: int, instr_len: int) -> int:
    """Read int32 disp at match_off+rip_off, return RVA = match_off + instr_len + disp."""
    if match_off + rip_off + 4 > len(data):
        return 0
    disp = struct.unpack_from("<i", data, match_off + rip_off)[0]
    return (match_off + instr_len + disp) & 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Memory reader adapter
# ---------------------------------------------------------------------------

class _MemReader:
    """Thin adapter over a process handle. Used by the dumper for the
    schema-walk phase (lots of tiny ReadProcessMemory calls)."""

    def __init__(self, process_handle: int, memory_interface=None):
        self._handle = process_handle
        self._mi = memory_interface
        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def read_bytes(self, addr: int, size: int) -> bytes:
        if not addr or addr >= 0x7FFFFFFFFFFF or size <= 0 or size > 0x10000:
            return b""
        if self._mi is not None:
            try:
                d = self._mi.read_bytes(addr, size)
                if d and len(d) == size:
                    return d
            except Exception:
                pass
        buf = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t(0)
        ok = self._k32.ReadProcessMemory(
            wintypes.HANDLE(self._handle),
            ctypes.c_void_p(addr),
            buf, size, ctypes.byref(read))
        if not ok or read.value != size:
            return b""
        return buf.raw

    def read_u8(self, addr: int) -> int:
        d = self.read_bytes(addr, 1)
        return d[0] if d else 0

    def read_u32(self, addr: int) -> int:
        d = self.read_bytes(addr, 4)
        return struct.unpack("<I", d)[0] if len(d) == 4 else 0

    def read_i32(self, addr: int) -> int:
        d = self.read_bytes(addr, 4)
        return struct.unpack("<i", d)[0] if len(d) == 4 else 0

    def read_i16(self, addr: int) -> int:
        d = self.read_bytes(addr, 2)
        return struct.unpack("<h", d)[0] if len(d) == 2 else 0

    def read_u64(self, addr: int) -> int:
        d = self.read_bytes(addr, 8)
        return struct.unpack("<Q", d)[0] if len(d) == 8 else 0

    def read_cstr(self, addr: int, max_len: int = 128) -> str:
        d = self.read_bytes(addr, max_len)
        if not d:
            return ""
        i = d.find(b"\x00")
        if i >= 0:
            d = d[:i]
        try:
            return d.decode("utf-8", errors="replace")
        except Exception:
            return ""

    def read_module(self, base: int, size: int) -> bytes:
        """Read a whole module into a single bytes blob.

        Uses 1MB chunks for usermode RPM (each ReadProcessMemory has ~10us of
        ring-transition overhead, so fewer huge reads >> many small ones).
        On the rare unreadable page (PAGE_NOACCESS / pageguard) the whole
        chunk fails -> we retry that chunk at a smaller stride so a single
        bad page doesn't black-hole 1MB of code.
        """
        if not base or not size:
            return b""
        out = bytearray(size)
        big = 0x100000   # 1 MiB
        small = 0x1000   # 4 KiB fallback per-page
        off = 0
        while off < size:
            n = min(big, size - off)
            d = self.read_bytes(base + off, n)
            if d and any(d):
                out[off:off + len(d)] = d
                off += n
                continue
            # Big read failed/blank -> fall back to per-page reads.
            page_end = off + n
            while off < page_end:
                pn = min(small, page_end - off)
                pd = self.read_bytes(base + off, pn)
                if pd:
                    out[off:off + len(pd)] = pd
                off += pn
        return bytes(out)


# ---------------------------------------------------------------------------
# The dumper
# ---------------------------------------------------------------------------

# Classes we care about — mirrors g_neededClasses[] in Dumper.cpp.
NEEDED_CLASSES = {
    "CCSPlayerController",
    "CBasePlayerController",
    "C_CSPlayerPawn",
    "C_BasePlayerPawn",
    "C_BaseEntity",
    "CSkeletonInstance",
    "CCSPlayerBase_CameraServices",
    "CCSPlayer_BulletServices",
    "C_CSPlayerPawnBase",
    "EntitySpottedState_t",
    "CPlayer_ObserverServices",
    "C_EconEntity",
    "C_BasePlayerWeapon",
    "CCSWeaponBaseVData",
    "CBasePlayerWeaponVData",
    "C_AttributeContainer",
    "C_EconItemView",
    "CPlayer_WeaponServices",
    "C_PlantedC4",
    "CCSPlayer_AimPunchServices",
    "CCSPlayer_ItemServices",
    "CPlayer_ItemServices",
    "C_CSPlayerPawnBase",
    "CBasePlayerPawn",
    "CCSPlayer_MovementServices",
    "CPlayer_MovementServices",
    "CCSGameRulesProxy",
    "CCSGameRules",
    "C_C4",
    "C_BaseCSGrenadeProjectile",
    "C_EnvironmentProbeVolume",
    "CBaseAnimGraph",
}


class CS2Dumper:
    def __init__(self, pid: int, process_handle: int, memory_interface=None,
                 log=print):
        self.pid = pid
        self.mem = _MemReader(process_handle, memory_interface)
        self.log = log

        # Results — kept structurally compatible with the C++ Dumper output.
        self.offsets: dict = {}        # module -> { name -> rva }
        self.buttons: dict = {}        # name -> rva
        self.schema_fields: dict = {}  # className -> { fieldName -> offset }

    # --------- public entry points -----------------------------------------
    def run(self) -> bool:
        self.log("[Dumper] Phase 1: pattern scanning offsets...")
        if not self._scan_offsets():
            self.log("[Dumper] ERROR: Pattern scan failed")
            return False

        self.log("[Dumper] Phase 2: scanning buttons...")
        client_base, client_data = self._cached_modules.get("client.dll", (0, b""))
        if client_data:
            self._scan_buttons(client_base, client_data)

        self.log("[Dumper] Phase 3: schema system traversal...")
        if not self._scan_schemas():
            self.log("[Dumper] WARNING: schema scan had issues")
        return True

    def rescan_matchmaking(self) -> bool:
        base, size = find_module(self.pid, "matchmaking.dll")
        if not base:
            return False
        data = self.mem.read_module(base, size)
        if not data:
            return False
        self._cached_modules["matchmaking.dll"] = (base, data)
        return self._scan_matchmaking(data)

    # --------- internals ----------------------------------------------------
    _cached_modules: dict  # populated by _scan_offsets

    def _load_module(self, name: str) -> bytes:
        base, size = find_module(self.pid, name)
        if not base:
            self.log(f"[Dumper] ERROR: module not found: {name}")
            return b""
        self.log(f"[Dumper] Loading {name}: base=0x{base:X} size=0x{size:X}")
        data = self.mem.read_module(base, size)
        if not data:
            self.log(f"[Dumper] ERROR: failed to read {name}")
            return b""
        self._cached_modules[name] = (base, data)
        return data

    # ---- Phase 1 ----------------------------------------------------------
    def _scan_offsets(self) -> bool:
        self._cached_modules = {}

        client = self._load_module("client.dll")
        if not client:
            return False
        inputsystem = self._load_module("inputsystem.dll")
        if not inputsystem:
            return False

        self._scan_client(client)
        self._scan_inputsystem(inputsystem)

        matchmaking = self._load_module("matchmaking.dll")
        if matchmaking:
            self._scan_matchmaking(matchmaking)
        else:
            self.log("[Dumper] matchmaking.dll not loaded yet -- dwGameTypes deferred")
        return True

    def _scan_client(self, data: bytes):
        client_map = self.offsets.setdefault("client.dll", {})

        def scan_rip(name: str, pattern: str, rip_off: int, instr_len: int) -> int:
            pat = parse_pattern(pattern)
            m = find_pattern(data, pat)
            if m < 0:
                self.log(f"[Dumper] MISS: {name}")
                return 0
            rva = resolve_rip(data, m, rip_off, instr_len)
            client_map[name] = rva
            self.log(f"[Dumper] {name} = 0x{rva:X}")
            return rva

        # Patterns and offsets mirror Dumper.cpp::ScanClientOffsets.
        csgo_input = scan_rip(
            "dwCSGOInput", "48 89 05 ?? ?? ?? ?? 0F 57 C0 0F 11 05", 3, 7)

        # dwViewAngles = dwCSGOInput + sub-offset (read from a different pattern)
        p = parse_pattern("F2 42 0F 10 84 28 ?? ?? ?? ??")
        m = find_pattern(data, p)
        if m >= 0 and csgo_input:
            sub = struct.unpack_from("<I", data, m + 6)[0]
            client_map["dwViewAngles"] = (csgo_input + sub) & 0xFFFFFFFF
            self.log(f"[Dumper] dwViewAngles = 0x{client_map['dwViewAngles']:X} (CSGOInput + 0x{sub:X})")
        else:
            self.log("[Dumper] MISS: dwViewAngles")

        scan_rip("dwEntityList",            "48 89 0D ?? ?? ?? ?? E9 ?? ?? ?? ?? CC", 3, 7)
        scan_rip("dwGlobalVars",            "48 89 15 ?? ?? ?? ?? 48 89 42", 3, 7)
        scan_rip("dwLocalPlayerController", "48 8B 05 ?? ?? ?? ?? 41 89 BE", 3, 7)
        scan_rip("dwViewMatrix",            "48 8D 0D ?? ?? ?? ?? 48 C1 E0 06", 3, 7)
        scan_rip("dwPlantedC4",
                 "48 8B 15 ?? ?? ?? ?? 41 FF C0 48 8D 4C 24 ?? 44 89 05", 3, 7)

        # dwPrediction — try a few pattern lengths
        prediction = 0
        for pat in (
            "48 8D 05 ?? ?? ?? ?? C3 CC CC CC CC CC CC CC CC CC 40 53 56 41 54",
            "48 8D 05 ?? ?? ?? ?? C3 CC CC CC CC CC CC CC CC 40 53 56 41 54",
            "48 8D 05 ?? ?? ?? ?? C3 CC CC CC CC CC CC CC CC CC 40 53",
        ):
            m = find_pattern(data, parse_pattern(pat))
            if m >= 0:
                prediction = resolve_rip(data, m, 3, 7)
                break
        if prediction:
            client_map["dwPrediction"] = prediction
            self.log(f"[Dumper] dwPrediction = 0x{prediction:X}")
        else:
            self.log("[Dumper] MISS: dwPrediction")

        # dwLocalPlayerPawn = dwPrediction + sub-offset
        p = parse_pattern("4C 39 B6 ?? ?? ?? ?? 74 ?? 44 88 BE")
        m = find_pattern(data, p)
        if m >= 0 and prediction:
            sub = struct.unpack_from("<I", data, m + 3)[0]
            client_map["dwLocalPlayerPawn"] = (prediction + sub) & 0xFFFFFFFF
            self.log(f"[Dumper] dwLocalPlayerPawn = 0x{client_map['dwLocalPlayerPawn']:X} "
                     f"(Prediction + 0x{sub:X})")
        else:
            self.log("[Dumper] MISS: dwLocalPlayerPawn")

        # dwSensitivity
        sens_pats = (
            "48 8D 0D ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 66 0F 6E CD",
            "48 8D 0D ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 66 0F 6E",
        )
        for pat in sens_pats:
            m = find_pattern(data, parse_pattern(pat))
            if m >= 0:
                rva = resolve_rip(data, m, 3, 7)
                client_map["dwSensitivity"] = rva
                self.log(f"[Dumper] dwSensitivity = 0x{rva:X}")
                break
        else:
            self.log("[Dumper] MISS: dwSensitivity")

        # dwSensitivity_sensitivity — single-byte literal
        p = parse_pattern("48 8D 7E ?? 48 0F BA E0 ?? 72 ?? 85 D2 49 0F 4F FF")
        m = find_pattern(data, p)
        if m >= 0:
            val = data[m + 3]
            client_map["dwSensitivity_sensitivity"] = val
            self.log(f"[Dumper] dwSensitivity_sensitivity = 0x{val:X}")
        else:
            self.log("[Dumper] MISS: dwSensitivity_sensitivity")

    def _scan_inputsystem(self, data: bytes):
        is_map = self.offsets.setdefault("inputsystem.dll", {})
        p = parse_pattern("48 89 05 ?? ?? ?? ?? 33 C0")
        m = find_pattern(data, p)
        if m >= 0:
            rva = resolve_rip(data, m, 3, 7)
            is_map["dwInputSystem"] = rva
            self.log(f"[Dumper] dwInputSystem = 0x{rva:X}")
        else:
            self.log("[Dumper] MISS: dwInputSystem")

    def _scan_matchmaking(self, data: bytes) -> bool:
        mm_map = self.offsets.setdefault("matchmaking.dll", {})
        p = parse_pattern("48 8D 0D ?? ?? ?? ?? FF 90")
        m = find_pattern(data, p)
        if m < 0:
            self.log("[Dumper] MISS: dwGameTypes")
            return False
        rva = resolve_rip(data, m, 3, 7)
        mm_map["dwGameTypes"] = rva
        self.log(f"[Dumper] dwGameTypes = 0x{rva:X}")
        return True

    # ---- Phase 2 ----------------------------------------------------------
    def _scan_buttons(self, client_base: int, client_data: bytes):
        pat = parse_pattern("48 8B 15 ?? ?? ?? ?? 48 85 D2 74 ?? 48 8B 02 48 85 C0")
        m = find_pattern(client_data, pat)
        if m < 0:
            self.log("[Dumper] MISS: button list head")
            return
        list_head_rva = resolve_rip(client_data, m, 3, 7)
        self.log(f"[Dumper] Button list head RVA = 0x{list_head_rva:X}")

        list_head_ptr = self.mem.read_u64(client_base + list_head_rva)
        if not list_head_ptr:
            self.log("[Dumper] button list head is null")
            return

        current = list_head_ptr
        count = 0
        while current and count < 200:
            name_ptr = self.mem.read_u64(current + 0x08)
            if name_ptr:
                name = self.mem.read_cstr(name_ptr, 64)
                if name:
                    state_rva = (current + 0x30) - client_base
                    if 0 <= state_rva < 0x10000000:
                        self.buttons[name] = state_rva & 0xFFFFFFFF
            nxt = self.mem.read_u64(current + 0x88)
            current = nxt
            count += 1
        self.log(f"[Dumper] Found {len(self.buttons)} buttons")

    # ---- Phase 3 ----------------------------------------------------------
    def _scan_schemas(self) -> bool:
        ss = self._load_module("schemasystem.dll")
        if not ss:
            return False
        base, _size = self._cached_modules["schemasystem.dll"]

        pat = parse_pattern("4C 8D 35 ?? ?? ?? ?? 0F 28 45")
        m = find_pattern(ss, pat)
        if m < 0:
            self.log("[Dumper] MISS: SchemaSystem pattern")
            return False
        schema_rva = resolve_rip(ss, m, 3, 7)
        schema_addr = base + schema_rva
        self.log(f"[Dumper] SchemaSystem at 0x{schema_addr:X} (RVA 0x{schema_rva:X})")

        reg_count = self.mem.read_i32(schema_addr + 0x0280)
        self.log(f"[Dumper] Schema registration count: {reg_count}")
        if reg_count <= 0:
            return False

        scope_count = self.mem.read_i32(schema_addr + 0x0190)
        scope_data_ptr = self.mem.read_u64(schema_addr + 0x0198)
        self.log(f"[Dumper] TypeScope count: {scope_count}, data ptr: 0x{scope_data_ptr:X}")
        if scope_count <= 0 or not scope_data_ptr:
            return False

        for i in range(min(scope_count, 32)):
            type_scope = self.mem.read_u64(scope_data_ptr + i * 8)
            if not type_scope:
                continue

            scope_name = self.mem.read_cstr(type_scope + 0x08, 255)
            self.log(f"[Dumper] TypeScope[{i}]: '{scope_name}'")

            hash_base = type_scope + 0x0560
            blocks_alloc = self.mem.read_i32(hash_base + 0x0C)
            peak_alloc = self.mem.read_i32(hash_base + 0x10)
            self.log(f"[Dumper]   blocks_allocated={blocks_alloc}, peak_allocated={peak_alloc}")

            class_ptrs: List[int] = []

            # Walk first_uncommitted chains across 256 buckets.
            for b in range(256):
                bucket_base = hash_base + 0x60 + b * 0x18
                node = self.mem.read_u64(bucket_base + 0x10)
                safety = 0
                while node and safety < 512:
                    data_ptr = self.mem.read_u64(node + 0x10)
                    if data_ptr:
                        class_ptrs.append(data_ptr)
                    node = self.mem.read_u64(node + 0x08)
                    safety += 1
                    if len(class_ptrs) >= blocks_alloc:
                        break
                if len(class_ptrs) >= blocks_alloc:
                    break

            # Walk free-blocks list (UtlTsHashAllocatedBlob chain).
            free_ptr = self.mem.read_u64(hash_base + 0x20)
            safety = 0
            limit = blocks_alloc + peak_alloc
            while free_ptr and safety < 4096:
                blob = self.mem.read_u64(free_ptr + 0x10)
                if blob:
                    class_ptrs.append(blob)
                free_ptr = self.mem.read_u64(free_ptr + 0x00)
                safety += 1
                if len(class_ptrs) >= limit:
                    break

            self.log(f"[Dumper]   Found {len(class_ptrs)} class binding pointers")

            # First pass: pull the class header (name ptr + field count +
            # fields ptr live in the first 0x40 bytes) in one read per class
            # and prune to NEEDED_CLASSES before we touch any field memory.
            needed_classes: List[tuple[str, int, int]] = []  # (name, fc, fields_ptr)
            for class_ptr in class_ptrs:
                hdr = self.mem.read_bytes(class_ptr, 0x40)
                if not hdr or len(hdr) < 0x40:
                    continue
                name_ptr = struct.unpack_from("<Q", hdr, 0x08)[0]
                if not name_ptr:
                    continue
                class_name = self.mem.read_cstr(name_ptr, 127)
                if not class_name or class_name not in NEEDED_CLASSES:
                    continue
                field_count = struct.unpack_from("<h", hdr, 0x24)[0]
                fields_ptr = struct.unpack_from("<Q", hdr, 0x30)[0]
                if field_count <= 0 or not fields_ptr:
                    continue
                needed_classes.append((class_name, field_count, fields_ptr))

            # Second pass: for each needed class, bulk-read the entire field
            # array (stride 0x20) in one RPC, then iterate the buffer in-proc.
            for class_name, field_count, fields_ptr in needed_classes:
                fc = min(field_count, 512)
                arr = self.mem.read_bytes(fields_ptr, fc * 0x20)
                if not arr:
                    continue
                field_map = self.schema_fields.setdefault(class_name, {})
                for f in range(fc):
                    base = f * 0x20
                    if base + 0x14 > len(arr):
                        break
                    fn_ptr = struct.unpack_from("<Q", arr, base + 0x00)[0]
                    foff = struct.unpack_from("<i", arr, base + 0x10)[0] & 0xFFFFFFFF
                    if not fn_ptr:
                        continue
                    fname = self.mem.read_cstr(fn_ptr, 127)
                    if not fname:
                        continue
                    field_map[fname] = foff
                self.log(f"[Dumper]   Class '{class_name}' ({len(field_map)} fields)")

        # Sanity: did we recover the core fields ESP/Aimbot need?
        sanity_classes = (
            "C_BaseEntity", "CCSPlayerController", "C_BasePlayerPawn",
            "CSkeletonInstance", "C_CSPlayerPawn")
        for cn in sanity_classes:
            if cn not in self.schema_fields:
                self.log(f"[Dumper] WARNING: missing class '{cn}' from schema")
        return True


# ---------------------------------------------------------------------------
# Helper used by GFusion.py at startup
# ---------------------------------------------------------------------------

def run_dumper(pid: int, process_handle: int, memory_interface=None,
               log=print) -> Optional[CS2Dumper]:
    """Convenience wrapper. Returns the populated CS2Dumper on success."""
    d = CS2Dumper(pid, process_handle, memory_interface, log=log)
    if not d.run():
        return None
    return d
