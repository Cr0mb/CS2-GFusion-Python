from __future__ import annotations
"""Standalone CS2 box ESP.

- Attaches to `cs2.exe`
- Resolves offsets from a2x/cs2-dumper (online)
- Draws simple team-coloured boxes using a transparent PyQt5 overlay

Requirements (install with pip):
    pip install PyQt5

Run this file with Python 3 on Windows while CS2 is running.
"""

import os
import sys
import time
import json
import ctypes
import struct
import threading
import urllib.request
from ctypes import wintypes, byref
from types import SimpleNamespace
from typing import Dict, Any, List, Tuple, Optional
def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin():
    params = " ".join(f'"{arg}"' for arg in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        params,
        None,
        1,
    )
    sys.exit(0)

# ---------------------------------------------------------------------------
# Basic Win32 / process helpers
# ---------------------------------------------------------------------------

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_PERMISSIONS = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


class Vec3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]


# ---------------------------------------------------------------------------
# Neac kernel driver + unified memory interface
# ---------------------------------------------------------------------------

class MemoryReader:
    """User-mode RPM reader fallback."""

    def __init__(self, pid: int):
        # Use same permissions as the rest of this script
        self.handle = kernel32.OpenProcess(PROCESS_PERMISSIONS, False, pid)
        if not self.handle:
            raise RuntimeError(f"OpenProcess failed for pid={pid}, err={ctypes.get_last_error()}")

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def read(self, address: int, size: int):
        if not address or size <= 0:
            return None
        buf = (ctypes.c_ubyte * size)()
        read_size = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf, size, ctypes.byref(read_size))
        if not ok or read_size.value == 0:
            return None
        return bytes(buf[:read_size.value])


import threading as _threading
_kernel_driver = None
_kernel_driver_lock = _threading.Lock()
_kernel_driver_init_attempted = False


def _init_neac_driver():
    """Lazy-load and connect to NeacController driver once per process."""
    global _kernel_driver, _kernel_driver_init_attempted
    with _kernel_driver_lock:
        if _kernel_driver is not None:
            return _kernel_driver
        if _kernel_driver_init_attempted:
            return None
        _kernel_driver_init_attempted = True
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            controller_path = os.path.join(base_dir, "NeacController-main", "NeacController")
            if os.path.isdir(controller_path) and controller_path not in sys.path:
                sys.path.insert(0, controller_path)
            import neac_controller  # type: ignore

            mgr = neac_controller.NeacDriverManager()
            if not mgr.start_driver():
                return None
            if not mgr.connect():
                try:
                    mgr.stop_driver()
                except Exception:
                    pass
                return None
            _kernel_driver = mgr
            print("[Kernel] NeacController driver started and connected.")
            return _kernel_driver
        except Exception as e:
            print(f"[Kernel] Failed to initialize NeacController driver: {e}")
            return None


class KernelMemoryReader:
    """Thin wrapper over NeacController for CS2 reads."""

    def __init__(self, pid: int):
        self.pid = pid
        self.driver = _init_neac_driver()

    def is_valid(self) -> bool:
        return self.driver is not None

    def read(self, address: int, size: int):
        if not self.driver or not address or size <= 0:
            return None
        try:
            data = self.driver.read_process_memory(self.pid, int(address), int(size))
            if not data:
                return None
            return bytes(data)
        except Exception:
            return None

    def read_u64(self, address: int) -> int:
        data = self.read(address, 8)
        if not data or len(data) < 8:
            return 0
        return int.from_bytes(data[:8], "little", signed=False)

    def read_u32(self, address: int) -> int:
        data = self.read(address, 4)
        if not data or len(data) < 4:
            return 0
        return int.from_bytes(data[:4], "little", signed=False)

    def read_u16(self, address: int) -> int:
        data = self.read(address, 2)
        if not data or len(data) < 2:
            return 0
        return int.from_bytes(data[:2], "little", signed=False)

    def read_f32(self, address: int) -> float:
        data = self.read(address, 4)
        if not data or len(data) < 4:
            return 0.0
        return struct.unpack("<f", data[:4])[0]

    def read_vec3(self, address: int) -> Tuple[float, float, float]:
        data = self.read(address, 12)
        if not data or len(data) < 12:
            return (0.0, 0.0, 0.0)
        return struct.unpack("<fff", data[:12])


class MemoryInterface:
    """Unified memory facade that prefers kernel-mode but can fall back."""

    def __init__(self, pid: int, kernel_enabled: bool = True, fallback_to_usermode: bool = True):
        self.pid = pid
        self.kernel_enabled = kernel_enabled
        self.fallback_to_usermode = fallback_to_usermode

        self.usermode: MemoryReader | None = None
        self.kernel: KernelMemoryReader | None = None
        self._current = None
        self._kernel_active = False

        self._init_readers()

    def _init_readers(self) -> None:
        if self.kernel_enabled:
            self.kernel = KernelMemoryReader(self.pid)
            if self.kernel.is_valid():
                self._current = self.kernel
                self._kernel_active = True
                print("[Mem] Using kernel-mode reader.")
        if self._current is None and self.fallback_to_usermode:
            try:
                self.usermode = MemoryReader(self.pid)
                self._current = self.usermode
                self._kernel_active = False
                print("[Mem] Using user-mode RPM fallback.")
            except Exception as e:
                print(f"[Mem] User-mode MemoryReader init failed: {e}")
        if self._current is None:
            raise RuntimeError("Failed to initialize any memory reader (kernel + user-mode).")

    def close(self) -> None:
        if self.usermode:
            self.usermode.close()
            self.usermode = None

    def is_kernel_mode_active(self) -> bool:
        return self._kernel_active

    # Low-level read ------------------------------------------------------
    def _reader(self):
        return self._current

    def read(self, address: int, size: int):
        r = self._reader()
        if not r:
            return None
        # KernelMemoryReader and MemoryReader both expose .read
        return r.read(address, size)

    # Typed helpers -------------------------------------------------------
    def read_u64(self, address: int) -> int:
        r = self._reader()
        if not r:
            return 0
        if hasattr(r, "read_u64"):
            return r.read_u64(address)  # type: ignore[no-any-return]
        data = self.read(address, 8)
        if not data or len(data) < 8:
            return 0
        return int.from_bytes(data[:8], "little", signed=False)

    def read_u32(self, address: int) -> int:
        r = self._reader()
        if not r:
            return 0
        if hasattr(r, "read_u32"):
            return r.read_u32(address)  # type: ignore[no-any-return]
        data = self.read(address, 4)
        if not data or len(data) < 4:
            return 0
        return int.from_bytes(data[:4], "little", signed=False)

    def read_f32(self, address: int) -> float:
        r = self._reader()
        if not r:
            return 0.0
        if hasattr(r, "read_f32"):
            return r.read_f32(address)  # type: ignore[no-any-return]
        data = self.read(address, 4)
        if not data or len(data) < 4:
            return 0.0
        return struct.unpack("<f", data[:4])[0]

    def read_vec3(self, address: int) -> Tuple[float, float, float]:
        r = self._reader()
        if not r:
            return (0.0, 0.0, 0.0)
        if hasattr(r, "read_vec3"):
            return r.read_vec3(address)  # type: ignore[no-any-return]
        data = self.read(address, 12)
        if not data or len(data) < 12:
            return (0.0, 0.0, 0.0)
        return struct.unpack("<fff", data[:12])

    def read_matrix4x4(self, address: int) -> Tuple[float, ...]:
        data = self.read(address, 64)
        if not data or len(data) < 64:
            return (0.0,) * 16
        return struct.unpack("f" * 16, data[:64])


# Global memory interface used by helper functions below
MEM: MemoryInterface | None = None


def init_memory_interface(pid: int) -> None:
    global MEM
    try:
        MEM = MemoryInterface(pid, kernel_enabled=True, fallback_to_usermode=True)
    except Exception as e:
        print(f"[Mem] Failed to initialize MemoryInterface: {e}")
        MEM = None


# ---------------------------------------------------------------------------
# Helper functions rewritten to use MemoryInterface instead of raw RPM
# ---------------------------------------------------------------------------

def read_bytes(_handle_unused: int, addr: int, size: int) -> bytes:
    global MEM
    if MEM is None or not addr or size <= 0:
        return b""
    data = MEM.read(addr, size)
    if not data:
        return b""
    if isinstance(data, bytes):
        return data
    try:
        return bytes(data)
    except Exception:
        return b""


def read_int(handle: int, addr: int) -> int:
    data = read_bytes(handle, addr, 4)
    return struct.unpack("i", data)[0] if data and len(data) >= 4 else 0


def read_u64(handle: int, addr: int) -> int:
    global MEM
    if MEM is None:
        return 0
    return MEM.read_u64(addr)


def safe_read_u64(handle: int, addr: int) -> int:
    if not addr or addr > 0x7FFF_FFFF_FFFF:
        return 0
    try:
        return read_u64(handle, addr)
    except Exception:
        return 0


def read_vec3(handle: int, addr: int) -> Vec3:
    data = read_bytes(handle, addr, 12)
    if not data or len(data) < 12:
        return Vec3(0.0, 0.0, 0.0)
    try:
        return Vec3.from_buffer_copy(data[:12])
    except Exception:
        return Vec3(0.0, 0.0, 0.0)


def read_matrix(handle: int, addr: int) -> Tuple[float, ...]:
    global MEM
    if MEM is None:
        return (0.0,) * 16
    return MEM.read_matrix4x4(addr)


def w2s(m: Tuple[float, ...], p: Vec3, w: int, h: int) -> Dict[str, float]:
    x = m[0] * p.x + m[1] * p.y + m[2] * p.z + m[3]
    y = m[4] * p.x + m[5] * p.y + m[6] * p.z + m[7]
    z = m[12] * p.x + m[13] * p.y + m[14] * p.z + m[15]
    if z < 0.1:
        raise RuntimeError("behind camera")
    inv = 1.0 / z
    return {
        "x": w / 2.0 + x * inv * w / 2.0,
        "y": h / 2.0 - y * inv * h / 2.0,
    }


# ---------------------------------------------------------------------------
# Offset loader (a2x/cs2-dumper)
# ---------------------------------------------------------------------------

OFFSETS_URL = "https://raw.githubusercontent.com/a2x/cs2-dumper/refs/heads/main/output/offsets.json"
CLIENT_DLL_URL = "https://raw.githubusercontent.com/a2x/cs2-dumper/refs/heads/main/output/client_dll.json"
HTTP_TIMEOUT_SECONDS = 15


def _fetch_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CS2-Box-ESP/offset_manager",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as r:
        data = r.read()
    return json.loads(data.decode("utf-8", errors="replace"))


_offsets_cache: SimpleNamespace | None = None


def get_offsets(force_update: bool = False) -> SimpleNamespace:
    global _offsets_cache
    if _offsets_cache is not None and not force_update:
        return _offsets_cache

    offsets_json = _fetch_json(OFFSETS_URL)
    client_json = _fetch_json(CLIENT_DLL_URL)

    flat: Dict[str, int] = {}

    # Base offsets (dwEntityList, dwViewMatrix, etc.)
    for module in offsets_json.values():
        if isinstance(module, dict):
            for k, v in module.items():
                if isinstance(v, int):
                    flat[k] = v

    # Make sure controller offset exists
    if "dwLocalPlayerController" not in flat:
        if "dwLocalPlayerPawn" in flat:
            flat["dwLocalPlayerController"] = flat["dwLocalPlayerPawn"]
        else:
            flat["dwLocalPlayerController"] = 0

    # Flatten client_dll class fields (m_iHealth, m_iTeamNum, etc.)
    for module in client_json.values():
        classes = module.get("classes", {}) or {}
        for class_name, class_data in classes.items():
            fields = (class_data or {}).get("fields", {}) or {}
            if not fields:
                continue
            for field, value in fields.items():
                # Special-case CSkeletonInstance::m_modelState -> m_pBoneArray
                if field == "m_modelState" and class_name == "CSkeletonInstance":
                    field = "m_pBoneArray"
                    value = int(value) + 128
                if isinstance(value, int):
                    flat[field] = value

    _offsets_cache = SimpleNamespace(**flat)
    return _offsets_cache


Offsets = get_offsets(force_update=False)

# We only need a head index for boxes; reuse the same index as GScript.
BONE_POSITIONS = {"head": 6}


# ---------------------------------------------------------------------------
# CS2 process + entity cache
# ---------------------------------------------------------------------------


class CS2Process:
    def __init__(self, proc_name: str | None = None, mod_name: str | None = None, timeout: int = 30):
        self.process_name = (proc_name or "cs2.exe").encode()
        self.module_name = (mod_name or "client.dll").encode()
        self.wait_timeout = timeout
        self.process_handle: int | None = None
        self.process_id: int | None = None
        self.module_base: int | None = None

    def _get_pid(self) -> int | None:
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == INVALID_HANDLE_VALUE:
            return None
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not kernel32.Process32First(snap, byref(entry)):
            kernel32.CloseHandle(snap)
            return None
        while True:
            if entry.szExeFile == self.process_name:
                pid = entry.th32ProcessID
                kernel32.CloseHandle(snap)
                return pid
            if not kernel32.Process32Next(snap, byref(entry)):
                break
        kernel32.CloseHandle(snap)
        return None

    def _get_module_base(self) -> int | None:
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, self.process_id)
        if snap == INVALID_HANDLE_VALUE:
            return None
        mod = MODULEENTRY32()
        mod.dwSize = ctypes.sizeof(MODULEENTRY32)
        if not kernel32.Module32First(snap, byref(mod)):
            kernel32.CloseHandle(snap)
            return None
        while True:
            if mod.szModule == self.module_name:
                base = ctypes.cast(mod.modBaseAddr, ctypes.c_void_p).value
                kernel32.CloseHandle(snap)
                return base
            if not kernel32.Module32Next(snap, byref(mod)):
                break
        kernel32.CloseHandle(snap)
        return None

    def initialize(self) -> None:
        start = time.time()
        while time.time() - start < self.wait_timeout:
            self.process_id = self._get_pid()
            if self.process_id:
                self.process_handle = kernel32.OpenProcess(
                    PROCESS_PERMISSIONS, False, self.process_id
                )
                if self.process_handle:
                    self.module_base = self._get_module_base()
                    if self.module_base:
                        return
            time.sleep(0.5)
        raise TimeoutError("CS2 process or client.dll not found")


class Entity:
    """Lightweight view of a CS2 player entity with cached bones."""

    _BONE_STRIDE = 32
    _BONEBUF_TTL = 0.02

    def __init__(self, controller: int, pawn: int, handle: int):
        self.handle = handle
        self.controller = controller
        self.pawn = pawn

        self.hp = 0
        self.team = 0
        self.pos = Vec3(0.0, 0.0, 0.0)
        self.head: Vec3 | None = None

        now = time.perf_counter()
        self.last_seen_frame = -1
        self.cached_frame = -1
        self._next_team_refresh = now

        self.bone_base: int | None = None
        self._bone_buf: bytes | None = None
        self._bone_buf_min = 0
        self._bone_buf_max = -1
        self._bone_buf_expiry = 0.0

    def touch(self, frame_id: int) -> None:
        self.last_seen_frame = frame_id

    def update_refs(self, controller: int, pawn: int, handle: int) -> None:
        self.handle = handle
        self.controller = controller
        self.pawn = pawn

    def _refresh_bone_base(self) -> int | None:
        scene_node = safe_read_u64(self.handle, self.pawn + Offsets.m_pGameSceneNode)
        if not scene_node:
            self.bone_base = None
            return None
        self.bone_base = safe_read_u64(self.handle, scene_node + Offsets.m_pBoneArray)
        return self.bone_base

    def read_data(self, frame_id: int, now: float | None = None) -> None:
        if self.cached_frame == frame_id:
            return
        self.cached_frame = frame_id
        if now is None:
            now = time.perf_counter()

        # Health
        try:
            self.hp = read_int(self.handle, self.pawn + Offsets.m_iHealth)
        except Exception:
            self.hp = 0
        if self.hp <= 0:
            return

        # Position
        try:
            self.pos = read_vec3(self.handle, self.pawn + Offsets.m_vOldOrigin)
        except Exception:
            self.pos = Vec3(0.0, 0.0, 0.0)

        # Team (cheap, but still avoid spamming a bit)
        if now >= self._next_team_refresh:
            try:
                self.team = read_int(self.handle, self.pawn + Offsets.m_iTeamNum)
            except Exception:
                self.team = 0
            self._next_team_refresh = now + 1.0

        # Head bone (for box size)
        bone_base = self._refresh_bone_base()
        if bone_base:
            bones = self.get_bone_positions({BONE_POSITIONS["head"]}, now=now)
            self.head = bones.get(BONE_POSITIONS["head"])
        else:
            self.head = None

    def get_bone_positions(self, indices, now: float | None = None) -> Dict[int, Vec3 | None]:
        if now is None:
            now = time.perf_counter()
        out: Dict[int, Vec3 | None] = {int(i): None for i in indices}
        if not out:
            return out
        if not self.bone_base and not self._refresh_bone_base():
            return out

        idxs = [int(i) for i in out.keys() if int(i) >= 0]
        if not idxs:
            return out
        bmin = min(idxs)
        bmax = max(idxs)

        need_new = (
            self._bone_buf is None
            or now >= self._bone_buf_expiry
            or bmin < self._bone_buf_min
            or bmax > self._bone_buf_max
        )
        if need_new:
            size = (bmax - bmin + 1) * self._BONE_STRIDE
            base_addr = self.bone_base + bmin * self._BONE_STRIDE
            buf = read_bytes(self.handle, base_addr, size)
            if not buf or len(buf) != size:
                return out
            self._bone_buf = buf
            self._bone_buf_min = bmin
            self._bone_buf_max = bmax
            self._bone_buf_expiry = now + self._BONEBUF_TTL

        buf = self._bone_buf
        stride = self._BONE_STRIDE
        base_min = self._bone_buf_min
        for i in out.keys():
            if i < base_min or i > self._bone_buf_max:
                continue
            off = (i - base_min) * stride
            try:
                x, y, z = struct.unpack_from("fff", buf, off)
                out[i] = Vec3(float(x), float(y), float(z))
            except Exception:
                out[i] = None
        return out


_ENTITY_CACHE: Dict[int, Entity] = {}
_ENTITY_FRAME = 0


def get_entities(handle: int, base: int) -> List[Entity]:
    global _ENTITY_CACHE, _ENTITY_FRAME

    _ENTITY_FRAME += 1
    frame_id = _ENTITY_FRAME
    now = time.perf_counter()

    try:
        local_controller = safe_read_u64(handle, base + Offsets.dwLocalPlayerController)
        entity_list = safe_read_u64(handle, base + Offsets.dwEntityList)
    except Exception:
        return []

    result: List[Entity] = []

    for i in range(1, 65):  # standard 64-player budget
        try:
            list_entry = safe_read_u64(
                handle, entity_list + (8 * ((i & 0x7FFF) >> 9) + 16)
            )
            if not list_entry:
                continue

            controller = safe_read_u64(handle, list_entry + 112 * (i & 0x1FF))
            if not controller or controller == local_controller:
                continue

            pawn_handle = safe_read_u64(handle, controller + Offsets.m_hPlayerPawn)
            if not pawn_handle:
                continue

            pawn_entry = safe_read_u64(
                handle, entity_list + (8 * ((pawn_handle & 0x7FFF) >> 9) + 16)
            )
            if not pawn_entry:
                continue

            pawn = safe_read_u64(handle, pawn_entry + 112 * (pawn_handle & 0x1FF))
            if not pawn:
                continue

            ent = _ENTITY_CACHE.get(pawn)
            if ent is None:
                ent = Entity(controller, pawn, handle)
                _ENTITY_CACHE[pawn] = ent
            else:
                ent.update_refs(controller, pawn, handle)

            ent.touch(frame_id)
            ent.read_data(frame_id, now=now)
            if ent.hp <= 0:
                continue
            result.append(ent)
        except Exception:
            continue

    # Periodic cleanup of stale entities
    if frame_id % 60 == 0:
        stale_before = frame_id - 300
        for pawn_addr, ent in list(_ENTITY_CACHE.items()):
            if getattr(ent, "last_seen_frame", -1) < stale_before:
                _ENTITY_CACHE.pop(pawn_addr, None)

    return result


# ---------------------------------------------------------------------------
# Minimal PyQt5 overlay (based on GScript QtOverlay)
# ---------------------------------------------------------------------------

try:
    from PyQt5.QtCore import Qt, QRect
    from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QGuiApplication
    from PyQt5.QtWidgets import QApplication, QWidget
except Exception as e:  # pragma: no cover - import-time failure
    QApplication = None  # type: ignore
    QGuiApplication = None  # type: ignore
    QWidget = object  # type: ignore
    _overlay_import_error = e
else:
    _overlay_import_error = None

_global_qapp: QApplication | None = None
_global_qapp_lock = threading.Lock()


def ensure_qapp() -> QApplication:
    global _global_qapp
    with _global_qapp_lock:
        if _global_qapp is not None:
            return _global_qapp
        if QApplication is None:
            raise RuntimeError(
                "PyQt5 is required for the overlay but is not installed: %r"
                % (_overlay_import_error,)
            )
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv or ["cs2_box_overlay"])
        _global_qapp = app  # type: ignore[assignment]
        return app  # type: ignore[return-value]


class _OverlayWidget(QWidget):
    def __init__(self, owner: "QtOverlay", title: str):
        super().__init__()
        self._owner = owner
        self.setWindowTitle(title or "CS2 Box ESP")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        try:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        try:
            self.setWindowFlag(Qt.WindowTransparentForInput, True)
        except Exception:
            pass

        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.geometry()
            self._owner.width = geo.width()
            self._owner.height = geo.height()
            self.setGeometry(geo)
        else:
            self._owner.width = 1920
            self._owner.height = 1080
            self.setGeometry(0, 0, self._owner.width, self._owner.height)

        self.show()
        self._pen_cache: Dict[tuple, QPen] = {}
        self._brush_cache: Dict[tuple, QBrush] = {}

    def paintEvent(self, event):  # type: ignore[override]
        primitives = self._owner._snapshot_primitives()
        if not primitives:
            return
        painter = QPainter(self)
        if getattr(self._owner, "use_antialiasing", False):
            painter.setRenderHint(QPainter.Antialiasing, True)
        else:
            painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        for prim in primitives:
            kind = prim[0]
            if kind == "rect":
                _, x, y, w, h, color, filled = prim
                r, g, b, a = color
                if filled:
                    painter.setPen(Qt.NoPen)
                    brush_key = (r, g, b, a)
                    brush = self._brush_cache.get(brush_key)
                    if brush is None:
                        brush = QBrush(QColor(r, g, b, a))
                        self._brush_cache[brush_key] = brush
                    painter.setBrush(brush)
                else:
                    pen_key = (r, g, b, a, 1)
                    pen = self._pen_cache.get(pen_key)
                    if pen is None:
                        pen = QPen(QColor(r, g, b, a))
                        pen.setWidth(1)
                        self._pen_cache[pen_key] = pen
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)
                painter.drawRect(QRect(int(x), int(y), int(w), int(h)))

        painter.end()


class QtOverlay:
    def __init__(self):
        self.width: int = 1920
        self.height: int = 1080
        self.fps: int = 144
        self.use_antialiasing: bool = False

        self._title = "CS2 Box ESP"
        self._widget: _OverlayWidget | None = None
        self._last_frame = 0.0
        self._primitives: List[tuple] = []
        self._lock = threading.Lock()
        self._hwnd: int | None = None

    @property
    def hwnd(self) -> int | None:
        if self._hwnd is not None:
            return self._hwnd
        w = self._widget
        if w is None:
            return None
        try:
            self._hwnd = int(w.winId())
        except Exception:
            self._hwnd = None
        return self._hwnd

    def init(self, title: str = "CS2 Box ESP") -> None:
        self._title = title
        app = ensure_qapp()
        del app
        if self._widget is None:
            self._widget = _OverlayWidget(self, title)

    def _color_to_rgba(self, color) -> Tuple[int, int, int, int]:
        try:
            r, g, b = color
        except Exception:
            r = g = b = 255
        return int(r) & 255, int(g) & 255, int(b) & 255, 255

    def _push_prim(self, prim: tuple) -> None:
        with self._lock:
            self._primitives.append(prim)

    def _snapshot_primitives(self) -> List[tuple]:
        with self._lock:
            prims = list(self._primitives)
            self._primitives.clear()
            return prims

    def begin_scene(self) -> bool:
        if self.fps:
            now = time.perf_counter()
            min_dt = 1.0 / float(self.fps)
            dt = now - self._last_frame
            if dt < min_dt:
                time.sleep(min_dt - dt)
            self._last_frame = time.perf_counter()

        if self._widget is None:
            try:
                self.init(self._title)
            except Exception:
                return False

        return True

    def end_scene(self) -> None:
        if self._widget is None:
            return
        try:
            self._widget.update()
            app = ensure_qapp()
            app.processEvents()
        except Exception:
            pass

    # Drawing primitives -------------------------------------------------
    def draw_box(self, x: float, y: float, w: float, h: float, color) -> None:
        rgba = self._color_to_rgba(color)
        self._push_prim(("rect", float(x), float(y), float(w), float(h), rgba, False))

    def draw_filled_rect(self, x: float, y: float, w: float, h: float, color) -> None:
        rgba = self._color_to_rgba(color)
        self._push_prim(("rect", float(x), float(y), float(w), float(h), rgba, True))


# ---------------------------------------------------------------------------
# Box ESP main loop
# ---------------------------------------------------------------------------


def main() -> None:
    cs2 = CS2Process()
    cs2.initialize()
    handle = cs2.process_handle
    base = cs2.module_base
    pid = cs2.process_id
    if not pid or not base:
        return

    # Initialise unified memory interface (kernel + fallback)
    init_memory_interface(pid)
    if MEM is None:
        return

    overlay = QtOverlay()
    overlay.init("CS2 Box ESP")

    # Simple toggles
    show_t = True
    show_ct = True

    # Colors
    COLOR_T = (255, 64, 64)
    COLOR_CT = (64, 160, 255)
    COLOR_OTHER = (255, 255, 255)

    while overlay.begin_scene():
        try:
            matrix = read_matrix(handle, base + Offsets.dwViewMatrix)
            w, h = overlay.width, overlay.height
            entities = get_entities(handle, base)

            for ent in entities:
                if ent.hp <= 0 or ent.pos is None:
                    continue

                if ent.team == 2 and not show_t:
                    continue
                if ent.team == 3 and not show_ct:
                    continue

                head = ent.head
                if head is None:
                    # fall back to origin-based box if we don't have bones yet
                    head = Vec3(ent.pos.x, ent.pos.y, ent.pos.z + 64.0)

                try:
                    feet2d = w2s(matrix, ent.pos, w, h)
                    head2d = w2s(matrix, head, w, h)
                except Exception:
                    continue

                box_h = (feet2d["y"] - head2d["y"]) * 1.08
                if box_h <= 1:
                    continue
                box_w = box_h / 2.0
                x = head2d["x"] - box_w / 2.0
                y = head2d["y"] - box_h * 0.08

                if ent.team == 2:
                    col = COLOR_T
                elif ent.team == 3:
                    col = COLOR_CT
                else:
                    col = COLOR_OTHER

                overlay.draw_box(x, y, box_w, box_h, col)

        except KeyboardInterrupt:
            break
        except Exception:
            # Never let a single bad frame kill the overlay
            pass

        overlay.end_scene()


if __name__ == "__main__":
    if not is_admin():
        print("[!] Administrator privileges required. Requesting elevation...")
        relaunch_as_admin()    
    try:
        main()
    except Exception as e:
        time.sleep(3.0)
