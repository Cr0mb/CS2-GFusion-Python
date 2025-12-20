from __future__ import annotations

import ctypes
import math
import threading
import time
from ctypes import wintypes as wt
from dataclasses import dataclass
from typing import List, Optional, Tuple


# ============================================================
# Offsets import (project-friendly)
# ============================================================
try:
    from Process.offsets import Offsets  # type: ignore
except Exception:
    from offsets import Offsets  # type: ignore

# ============================================================
# Config import (shared with GFusion)
# ============================================================
try:
    from Process.config import Config  # type: ignore
except Exception:
    try:
        from config import Config  # type: ignore
    except Exception:
        class Config:  # minimal fallback
            pass


# ============================================================
# Win32 / GDI declarations (ctypes)
# ============================================================
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
# Text / background modes belong to gdi32 (NOT user32)
gdi32.SetTextColor.argtypes = [wt.HDC, wt.COLORREF]
gdi32.SetTextColor.restype = wt.COLORREF

gdi32.SetBkMode.argtypes = [wt.HDC, ctypes.c_int]
gdi32.SetBkMode.restype = ctypes.c_int
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

# --- user32 ---
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT

user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
user32.RegisterClassExW.restype = wt.ATOM

user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID
]
user32.CreateWindowExW.restype = wt.HWND

user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindow.restype = wt.BOOL

user32.UpdateWindow.argtypes = [wt.HWND]
user32.UpdateWindow.restype = wt.BOOL

user32.GetMessageW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = ctypes.c_int

user32.PeekMessageW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, wt.UINT, wt.UINT]
user32.PeekMessageW.restype = wt.BOOL

user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.TranslateMessage.restype = wt.BOOL

user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.restype = LRESULT

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC

user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.ReleaseDC.restype = ctypes.c_int

user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.SetWindowPos.restype = wt.BOOL

user32.SetLayeredWindowAttributes.argtypes = [wt.HWND, wt.COLORREF, wt.BYTE, wt.DWORD]
user32.SetLayeredWindowAttributes.restype = wt.BOOL

user32.GetCursorPos.argtypes = [ctypes.c_void_p]
user32.GetCursorPos.restype = wt.BOOL

user32.ScreenToClient.argtypes = [wt.HWND, ctypes.c_void_p]
user32.ScreenToClient.restype = wt.BOOL

user32.ClientToScreen.argtypes = [wt.HWND, ctypes.c_void_p]
user32.ClientToScreen.restype = wt.BOOL

user32.GetWindowRect.argtypes = [wt.HWND, ctypes.c_void_p]
user32.GetWindowRect.restype = wt.BOOL

user32.SetCapture.argtypes = [wt.HWND]
user32.SetCapture.restype = wt.HWND

user32.ReleaseCapture.argtypes = []
user32.ReleaseCapture.restype = wt.BOOL

user32.FillRect.argtypes = [wt.HDC, ctypes.c_void_p, wt.HBRUSH]
user32.FillRect.restype = ctypes.c_int

user32.DrawTextW.argtypes = [wt.HDC, wt.LPCWSTR, ctypes.c_int, ctypes.c_void_p, wt.UINT]
user32.DrawTextW.restype = ctypes.c_int




# OBS-proofing (hide overlay from capture when enabled)
user32.SetWindowDisplayAffinity.argtypes = [wt.HWND, wt.DWORD]
user32.SetWindowDisplayAffinity.restype = wt.BOOL
# --- gdi32 ---
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC

gdi32.DeleteDC.argtypes = [wt.HDC]
gdi32.DeleteDC.restype = wt.BOOL

gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP

gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ

gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteObject.restype = wt.BOOL

gdi32.BitBlt.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD]
gdi32.BitBlt.restype = wt.BOOL

gdi32.CreateSolidBrush.argtypes = [wt.COLORREF]
gdi32.CreateSolidBrush.restype = wt.HBRUSH

gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wt.COLORREF]
gdi32.CreatePen.restype = wt.HPEN

gdi32.Rectangle.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
gdi32.Rectangle.restype = wt.BOOL

gdi32.Ellipse.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
gdi32.Ellipse.restype = wt.BOOL

gdi32.MoveToEx.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
gdi32.MoveToEx.restype = wt.BOOL

gdi32.LineTo.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.LineTo.restype = wt.BOOL

gdi32.SetDCBrushColor.argtypes = [wt.HDC, wt.COLORREF]
gdi32.SetDCBrushColor.restype = wt.COLORREF

gdi32.SetDCPenColor.argtypes = [wt.HDC, wt.COLORREF]
gdi32.SetDCPenColor.restype = wt.COLORREF

gdi32.GetStockObject.argtypes = [ctypes.c_int]
gdi32.GetStockObject.restype = wt.HGDIOBJ

gdi32.SetBkColor.argtypes = [wt.HDC, wt.COLORREF]
gdi32.SetBkColor.restype = wt.COLORREF

gdi32.SetTextAlign.argtypes = [wt.HDC, wt.UINT]
gdi32.SetTextAlign.restype = wt.UINT

gdi32.SetMapMode.argtypes = [wt.HDC, ctypes.c_int]
gdi32.SetMapMode.restype = ctypes.c_int

gdi32.SetStretchBltMode.argtypes = [wt.HDC, ctypes.c_int]
gdi32.SetStretchBltMode.restype = ctypes.c_int

# --- kernel32 process / module snapshots ---
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

SW_SHOW = 5

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000

WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000

LWA_ALPHA = 0x00000002


# Window display affinity (OBS / screen-capture protection)
WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011
HWND_TOPMOST = wt.HWND(-1)
HWND_NOTOPMOST = wt.HWND(-2)

# SetWindowPos flags
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

# Messages
WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEMOVE = 0x0200

PM_REMOVE = 0x0001

# GDI constants
SRCCOPY = 0x00CC0020
TRANSPARENT = 1
DT_LEFT = 0x0000
DT_TOP = 0x0000
DT_SINGLELINE = 0x0020
DT_VCENTER = 0x0004
DT_NOPREFIX = 0x0800

# Stock objects
DC_BRUSH = 18
DC_PEN = 19
NULL_BRUSH = 5

# ============================================================
# Helpers
# ============================================================
def _rgb(r: int, g: int, b: int) -> int:
    # COLORREF is 0x00bbggrr
    return (b << 16) | (g << 8) | r

def _lo_word(dword: int) -> int:
    return dword & 0xFFFF

def _hi_word(dword: int) -> int:
    return (dword >> 16) & 0xFFFF

def _sign16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


# ============================================================
# Snapshot structs
# ============================================================
MAX_PATH = 260

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * MAX_PATH),
    ]

class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("th32ModuleID", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("GlblcntUsage", wt.DWORD),
        ("ProccntUsage", wt.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wt.DWORD),
        ("hModule", wt.HMODULE),
        ("szModule", wt.WCHAR * 256),
        ("szExePath", wt.WCHAR * MAX_PATH),
    ]

kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE

kernel32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32FirstW.restype = wt.BOOL
kernel32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32NextW.restype = wt.BOOL

kernel32.Module32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]
kernel32.Module32FirstW.restype = wt.BOOL
kernel32.Module32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]
kernel32.Module32NextW.restype = wt.BOOL

kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL

kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE

kernel32.ReadProcessMemory.argtypes = [wt.HANDLE, wt.LPCVOID, wt.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wt.BOOL


# ============================================================
# Process / memory reader (ctypes-only)
# ============================================================
@dataclass
class CS2Target:
    pid: int
    handle: int
    client_base: int

class RPM:
    """Small safe ReadProcessMemory wrapper."""
    __slots__ = ("handle",)

    def __init__(self, handle: int):
        self.handle = handle

    def close(self) -> None:
        h = wt.HANDLE(self.handle)
        if self.handle:
            kernel32.CloseHandle(h)
        self.handle = 0

    def read_bytes(self, addr: int, size: int) -> Optional[bytes]:
        if not addr or addr > 0x7FFFFFFFFFFF:
            return None
        buf = (ctypes.c_ubyte * size)()
        n = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(wt.HANDLE(self.handle), wt.LPCVOID(addr), ctypes.byref(buf), size, ctypes.byref(n))
        if not ok or n.value != size:
            return None
        return bytes(buf)

    def read_u64(self, addr: int) -> int:
        b = self.read_bytes(addr, 8)
        if not b:
            return 0
        return int.from_bytes(b, "little", signed=False)

    def read_i32(self, addr: int) -> int:
        b = self.read_bytes(addr, 4)
        if not b:
            return 0
        return int.from_bytes(b, "little", signed=True)

    def read_f32(self, addr: int) -> float:
        b = self.read_bytes(addr, 4)
        if not b:
            return 0.0
        return ctypes.c_float.from_buffer_copy(b).value

    def read_vec3(self, addr: int) -> Tuple[float, float, float]:
        b = self.read_bytes(addr, 12)
        if not b:
            return (0.0, 0.0, 0.0)
        x, y, z = ctypes.c_float.from_buffer_copy(b[0:4]).value, ctypes.c_float.from_buffer_copy(b[4:8]).value, ctypes.c_float.from_buffer_copy(b[8:12]).value
        return (float(x), float(y), float(z))


def find_pid_by_name(exe_name: str) -> int:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == wt.HANDLE(-1).value:
        return 0

    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

    pid = 0
    if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
        while True:
            if entry.szExeFile.lower() == exe_name.lower():
                pid = int(entry.th32ProcessID)
                break
            if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                break

    kernel32.CloseHandle(snap)
    return pid


def get_module_base(pid: int, module_name: str) -> int:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == wt.HANDLE(-1).value:
        return 0

    entry = MODULEENTRY32()
    entry.dwSize = ctypes.sizeof(MODULEENTRY32)

    base = 0
    if kernel32.Module32FirstW(snap, ctypes.byref(entry)):
        while True:
            if entry.szModule.lower() == module_name.lower():
                base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value or 0
                break
            if not kernel32.Module32NextW(snap, ctypes.byref(entry)):
                break

    kernel32.CloseHandle(snap)
    return int(base)


def connect_cs2(process_name: str = "cs2.exe", client_mod: str = "client.dll", timeout_s: float = 30.0) -> Optional[CS2Target]:
    """Wait for CS2 and return (pid, process handle, client base)."""
    deadline = time.time() + float(timeout_s)
    while time.time() < deadline:
        pid = find_pid_by_name(process_name)
        if pid:
            base = get_module_base(pid, client_mod)
            if base:
                h = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
                if h:
                    return CS2Target(pid=pid, handle=int(h), client_base=int(base))
        time.sleep(0.5)
    return None


# ============================================================
# Radar data model
# ============================================================
@dataclass
class RadarBlip:
    x: float
    y: float
    yaw: float
    team: int

@dataclass
class RadarSnapshot:
    local_x: float = 0.0
    local_y: float = 0.0
    local_yaw: float = 0.0
    local_team: int = 0
    blips: List[RadarBlip] = None  # type: ignore
    last_ok: float = 0.0
    connected: bool = False

    def __post_init__(self):
        if self.blips is None:
            self.blips = []


# ============================================================
# Memory polling thread (ESP-matched entity traversal)
# ============================================================
class RadarReader(threading.Thread):
    def __init__(self, snapshot: RadarSnapshot, lock: threading.Lock, cfg_ref=None, fps: float = 60.0):
        super().__init__(daemon=True)
        self.snapshot = snapshot
        self.lock = lock
        self.cfg_ref = cfg_ref if cfg_ref is not None else Config
        self.fps = max(10.0, float(fps))
        self._stop = threading.Event()

        self._target: Optional[CS2Target] = None
        self._rpm: Optional[RPM] = None
        self._o = Offsets() if callable(getattr(Offsets, "__call__", None)) else Offsets  # support class or instance

    def stop(self) -> None:
        self._stop.set()

    def _set_disconnected(self) -> None:
        with self.lock:
            self.snapshot.connected = False
            self.snapshot.blips = []
        if self._rpm:
            self._rpm.close()
            self._rpm = None
        self._target = None

    def _ensure_connected(self) -> bool:
        if self._target and self._rpm and self._target.handle:
            return True

        self._set_disconnected()
        tgt = connect_cs2(timeout_s=2.0)
        if not tgt:
            return False

        self._target = tgt
        self._rpm = RPM(tgt.handle)
        with self.lock:
            self.snapshot.connected = True
        return True

    def run(self) -> None:
        while not self._stop.is_set() and not bool(getattr(self.cfg_ref, 'radar_stop', False)):
            t0 = time.perf_counter()
            try:
                if not self._ensure_connected():
                    time.sleep(0.5)
                    continue

                assert self._target and self._rpm
                base = self._target.client_base
                rpm = self._rpm
                o = self._o

                # "In game" check mirrors ESP helper: local pawn != 0
                local_pawn = rpm.read_u64(base + o.dwLocalPlayerPawn)
                if not local_pawn:
                    with self.lock:
                        self.snapshot.blips = []
                        self.snapshot.last_ok = time.time()
                    time.sleep(0.05)
                    continue

                local_team = rpm.read_i32(local_pawn + o.m_iTeamNum)
                lx, ly, _lz = rpm.read_vec3(local_pawn + o.m_vOldOrigin)
                local_yaw = rpm.read_f32(base + o.dwViewAngles + 0x4)

                ent_list = rpm.read_u64(base + o.dwEntityList)
                local_ctrl = rpm.read_u64(base + o.dwLocalPlayerController)

                blips: List[RadarBlip] = []

                if ent_list:
                    for i in range(1, 65):
                        # ---- Controller lookup (matches radar.py + ESP patterns) ----
                        list_offset = ((i & 0x7FFF) >> 9) * 8 + 0x10
                        entry = rpm.read_u64(ent_list + list_offset)
                        if not entry:
                            continue

                        ctrl = rpm.read_u64(entry + 112 * (i & 0x1FF))
                        if not ctrl or ctrl == local_ctrl:
                            continue

                        pawn_handle = rpm.read_u64(ctrl + o.m_hPlayerPawn)
                        if not pawn_handle:
                            continue

                        pawn_index = pawn_handle & 0x7FFF
                        pawn_entry = rpm.read_u64(ent_list + ((pawn_index >> 9) * 8 + 0x10))
                        if not pawn_entry:
                            continue

                        pawn = rpm.read_u64(pawn_entry + 112 * (pawn_index & 0x1FF))
                        if not pawn:
                            continue

                        hp = rpm.read_i32(pawn + o.m_iHealth)
                        if hp <= 0:
                            continue

                        dormant = rpm.read_i32(pawn + o.m_bDormant)
                        if dormant:
                            continue

                        team = rpm.read_i32(pawn + o.m_iTeamNum)
                        ex, ey, _ez = rpm.read_vec3(pawn + o.m_vOldOrigin)
                        eyaw = rpm.read_f32(pawn + o.m_angEyeAngles + 0x4)

                        blips.append(RadarBlip(x=ex, y=ey, yaw=eyaw, team=team))

                with self.lock:
                    self.snapshot.local_x = lx
                    self.snapshot.local_y = ly
                    self.snapshot.local_yaw = local_yaw
                    self.snapshot.local_team = local_team
                    self.snapshot.blips = blips
                    self.snapshot.last_ok = time.time()
                    self.snapshot.connected = True

            except Exception:
                # Any read failure (process closing, map changing, etc) -> reconnect softly
                self._set_disconnected()

            dt = time.perf_counter() - t0
            try:
                desired = float(getattr(self.cfg_ref, 'radar_reader_fps', self.fps))
            except Exception:
                desired = self.fps
            desired = max(5.0, min(240.0, desired))
            tick = 1.0 / desired
            if dt < tick:
                time.sleep(tick - dt)


# ============================================================
# Radar overlay window (small draggable HUD)
# ============================================================
@dataclass
class RadarStyle:
    width: int = 280
    height: int = 280
    header_h: int = 22
    padding: int = 10

    bg: int = _rgb(20, 20, 32)
    border: int = _rgb(255, 255, 255)
    border_shadow: int = _rgb(64, 64, 64)

    title_text: int = _rgb(245, 245, 247)
    sub_text: int = _rgb(200, 200, 210)

    me_dot: int = _rgb(255, 255, 255)
    me_dir: int = _rgb(0, 255, 0)

    enemy_dot: int = _rgb(255, 0, 0)
    team_dot: int = _rgb(0, 128, 255)
    enemy_dir: int = _rgb(255, 255, 0)


class RadarOverlay:
    def __init__(self, snapshot: RadarSnapshot, lock: threading.Lock, cfg_ref=None, title: str = "GFusion Radar", fps: float = 60.0):
        self.snapshot = snapshot
        self.lock = lock
        self.title = title
        self.fps = max(20.0, float(fps))
        self.style = RadarStyle()
        self.cfg_ref = cfg_ref if cfg_ref is not None else Config
        # OBS protection toggle tracking (mirrors esp.py behavior)
        self._last_obs_check_time = 0.0
        self._obs_check_interval = 0.5  # seconds
        self._last_obs_value = None

        # Apply initial config size/fps if present
        try:
            self.style.width = int(getattr(self.cfg_ref, 'radar_width', self.style.width))
            self.style.height = int(getattr(self.cfg_ref, 'radar_height', self.style.height))
        except Exception:
            pass
        try:
            self.fps = max(20.0, float(getattr(self.cfg_ref, 'radar_fps', fps)))
        except Exception:
            self.fps = max(20.0, float(fps))

        # window state
        self.hwnd: wt.HWND = wt.HWND(0)
        self._running = False
        self._dragging = False
        self._drag_dx = 0
        self._drag_dy = 0

        # resize state (manual, since WS_POPUP has no frame)
        self._resizing = False
        self._resize_edge = ""  # e.g. "l", "r", "b", "tl", "br"
        self._resize_margin = 8
        self._min_w = 180
        self._min_h = 180
        self._rs_start_pt = wt.POINT()
        self._rs_start_rect = wt.RECT()
        self._last_realloc = 0.0

        # GDI resources
        self._hdc_win: wt.HDC = wt.HDC(0)
        self._hdc_mem: wt.HDC = wt.HDC(0)
        self._bmp: wt.HBITMAP = wt.HBITMAP(0)
        self._old_bmp: wt.HGDIOBJ = wt.HGDIOBJ(0)

        # cached stock objects
        self._dc_pen = gdi32.GetStockObject(DC_PEN)
        self._dc_brush = gdi32.GetStockObject(DC_BRUSH)

        self._class_name = "GFusionRadarWindow"

        # keep a reference to prevent GC
        self._wndproc = WNDPROC(self._on_wndproc)

    # ------------- window setup -------------
    def create(self, x: int = 40, y: int = 120, alpha: int = 235) -> None:
        self._register_class()

        ex_style = WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_LAYERED
        style = WS_POPUP | WS_VISIBLE

        hinst = kernel32.GetModuleHandleW(None)
        self.hwnd = user32.CreateWindowExW(
            ex_style,
            self._class_name,
            self.title,
            style,
            int(x), int(y),
            int(self.style.width), int(self.style.height),
            None, None, hinst, None
        )
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())


        # Apply OBS protection immediately (matches esp.py behavior)
        try:
            self._last_obs_value = bool(self._cfg_get('obs_protection_enabled', False))
        except Exception:
            self._last_obs_value = False
        self._update_obs_protection(self._last_obs_value)
        # overall window alpha (simple + stable)
        user32.SetLayeredWindowAttributes(self.hwnd, 0, wt.BYTE(max(30, min(alpha, 255))), LWA_ALPHA)

        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)

        self._init_gdi()

    def _register_class(self) -> None:
        # WNDCLASSEXW struct (manual to avoid pulling win32con)
        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wt.UINT),
                ("style", wt.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE),
                ("hIcon", wt.HICON),
                ("hCursor", wt.HCURSOR),
                ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR),
                ("hIconSm", wt.HICON),
            ]

        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0
        wc.lpfnWndProc = self._wndproc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinst
        wc.hIcon = None
        wc.hCursor = user32.LoadCursorW(None, wt.LPCWSTR(32512))  # IDC_ARROW
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = self._class_name
        wc.hIconSm = None

        atom = user32.RegisterClassExW(ctypes.byref(wc))
        # If already registered, RegisterClassExW returns 0 and GetLastError is ERROR_CLASS_ALREADY_EXISTS (1410)
        if not atom:
            err = ctypes.get_last_error()
            if err != 1410:
                raise ctypes.WinError(err)

    def _init_gdi(self) -> None:
        # double-buffer: window DC -> mem DC -> compatible bitmap
        self._hdc_win = user32.GetDC(self.hwnd)
        if not self._hdc_win:
            raise ctypes.WinError(ctypes.get_last_error())

        self._hdc_mem = gdi32.CreateCompatibleDC(self._hdc_win)
        if not self._hdc_mem:
            raise ctypes.WinError(ctypes.get_last_error())

        self._bmp = gdi32.CreateCompatibleBitmap(self._hdc_win, self.style.width, self.style.height)
        if not self._bmp:
            raise ctypes.WinError(ctypes.get_last_error())

        self._old_bmp = gdi32.SelectObject(self._hdc_mem, self._bmp)

        # select DC pen/brush
        gdi32.SelectObject(self._hdc_mem, self._dc_pen)
        gdi32.SelectObject(self._hdc_mem, self._dc_brush)

        # text setup
        gdi32.SetBkMode(self._hdc_mem, TRANSPARENT)

    def _shutdown_gdi(self) -> None:
        if self._hdc_mem:
            if self._old_bmp:
                gdi32.SelectObject(self._hdc_mem, self._old_bmp)
            if self._bmp:
                gdi32.DeleteObject(self._bmp)
            gdi32.DeleteDC(self._hdc_mem)
        self._hdc_mem = wt.HDC(0)
        self._bmp = wt.HBITMAP(0)
        self._old_bmp = wt.HGDIOBJ(0)

        if self._hdc_win:
            user32.ReleaseDC(self.hwnd, self._hdc_win)
        self._hdc_win = wt.HDC(0)


    # ------------- resize helpers -------------
    def _hit_test_edge(self, x: int, y: int) -> str:
        # Return which edge/corner the mouse is over for resizing.
        m = int(self._resize_margin)
        w = int(self.style.width)
        h = int(self.style.height)

        on_l = x <= m
        on_r = x >= (w - 1 - m)
        on_t = y <= m
        on_b = y >= (h - 1 - m)

        # corners first
        if on_t and on_l:
            return "tl"
        if on_t and on_r:
            return "tr"
        if on_b and on_l:
            return "bl"
        if on_b and on_r:
            return "br"

        if on_l:
            return "l"
        if on_r:
            return "r"
        if on_t:
            return "t"
        if on_b:
            return "b"
        return ""

    def _start_resize(self, hwnd: wt.HWND, edge: str) -> None:
        self._resizing = True
        self._resize_edge = edge

        # capture starting rect + cursor
        user32.GetWindowRect(hwnd, ctypes.byref(self._rs_start_rect))
        user32.GetCursorPos(ctypes.byref(self._rs_start_pt))
        user32.SetCapture(hwnd)

    def _apply_resize(self, hwnd: wt.HWND) -> None:
        pt = wt.POINT()
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return

        dx = int(pt.x - self._rs_start_pt.x)
        dy = int(pt.y - self._rs_start_pt.y)

        r0 = self._rs_start_rect
        left = int(r0.left)
        top = int(r0.top)
        right = int(r0.right)
        bottom = int(r0.bottom)

        edge = self._resize_edge

        if "l" in edge:
            left += dx
        if "r" in edge:
            right += dx
        if "t" in edge:
            top += dy
        if "b" in edge:
            bottom += dy

        # enforce minimums
        min_w = int(self._min_w)
        min_h = int(self._min_h)

        w = right - left
        h = bottom - top

        if w < min_w:
            if "l" in edge and "r" not in edge:
                left = right - min_w
            else:
                right = left + min_w
            w = min_w

        if h < min_h:
            if "t" in edge and "b" not in edge:
                top = bottom - min_h
            else:
                bottom = top + min_h
            h = min_h

        # apply window resize/move
        insert_after = HWND_TOPMOST if bool(getattr(self.cfg_ref, "radar_always_on_top", True)) else HWND_NOTOPMOST

        user32.SetWindowPos(hwnd, insert_after, left, top, w, h, SWP_NOACTIVATE)

        self._cfg_set("radar_x", left)

        self._cfg_set("radar_y", top)

        self._cfg_set("radar_width", w)

        self._cfg_set("radar_height", h)

        # update backbuffer (throttle realloc a bit to keep it smooth)
        now = time.perf_counter()
        if now - self._last_realloc > 0.02:
            self._last_realloc = now
            self._resize_backbuffer(w, h)

    def _resize_backbuffer(self, new_w: int, new_h: int) -> None:
        new_w = int(max(self._min_w, new_w))
        new_h = int(max(self._min_h, new_h))

        if new_w == int(self.style.width) and new_h == int(self.style.height):
            return

        self.style.width = new_w
        self.style.height = new_h
        self._cfg_set('radar_width', int(new_w))
        self._cfg_set('radar_height', int(new_h))

        # if GDI isn't ready yet, nothing to do
        if not self._hdc_win or not self._hdc_mem:
            return

        # recreate compatible bitmap at new size (keep DCs)
        if self._hdc_mem and self._old_bmp:
            gdi32.SelectObject(self._hdc_mem, self._old_bmp)
        if self._bmp:
            gdi32.DeleteObject(self._bmp)

        bmp = gdi32.CreateCompatibleBitmap(self._hdc_win, new_w, new_h)
        if not bmp:
            return

        self._bmp = bmp
        self._old_bmp = gdi32.SelectObject(self._hdc_mem, self._bmp)

        # ensure DC pen/brush still selected (safe)
        gdi32.SelectObject(self._hdc_mem, self._dc_pen)
        gdi32.SelectObject(self._hdc_mem, self._dc_brush)

    # ------------- wndproc -------------
    def _on_wndproc(self, hwnd: wt.HWND, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_DESTROY:
            self._running = False
            user32.PostQuitMessage(0)
            return 0

        if msg == WM_ERASEBKGND:
            return 1  # no flicker

        if msg == WM_LBUTTONDOWN:
            x = _sign16(_lo_word(lparam))
            y = _sign16(_hi_word(lparam))

            # priority: resizing if we're close to an edge/corner
            edge = self._hit_test_edge(x, y)
            if edge:
                self._start_resize(hwnd, edge)
                return 0

            # otherwise: header drag
            if 0 <= x < self.style.width and 0 <= y < self.style.header_h:
                self._dragging = True
                self._drag_dx = x
                self._drag_dy = y
                user32.SetCapture(hwnd)
                return 0

            return 0

        if msg == WM_LBUTTONUP:
            if self._dragging or self._resizing:
                self._dragging = False
                self._resizing = False
                self._resize_edge = ""
                user32.ReleaseCapture()
            return 0

        if msg == WM_MOUSEMOVE:
            if self._resizing:
                self._apply_resize(hwnd)
                return 0

            if self._dragging:
                # move window based on current cursor
                pt = wt.POINT()
                if user32.GetCursorPos(ctypes.byref(pt)):
                    new_x = int(pt.x - self._drag_dx)
                    new_y = int(pt.y - self._drag_dy)
                    insert_after = HWND_TOPMOST if bool(getattr(self.cfg_ref, "radar_always_on_top", True)) else HWND_NOTOPMOST

                    user32.SetWindowPos(hwnd, insert_after, new_x, new_y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)

                    self._cfg_set("radar_x", new_x)

                    self._cfg_set("radar_y", new_y)
                return 0
        return int(user32.DefWindowProcW(hwnd, msg, wparam, lparam))


    # ------------- config sync -------------
    def _cfg_get(self, key: str, default):
        try:
            return getattr(self.cfg_ref, key)
        except Exception:
            return default

    def _cfg_set(self, key: str, value) -> None:
        try:
            setattr(self.cfg_ref, key, value)
        except Exception:
            pass


    # ------------- OBS / capture protection -------------
    def _update_obs_protection(self, enabled: bool | None = None) -> None:
        """Apply SetWindowDisplayAffinity to hide/show this overlay in capture sources.

        Uses WDA_EXCLUDEFROMCAPTURE when enabled (Windows 10 2004+). Falls back to WDA_MONITOR
        when EXCLUDEFROMCAPTURE is not supported.
        """
        if not self.hwnd:
            return
        if enabled is None:
            enabled = bool(self._cfg_get('obs_protection_enabled', False))
        try:
            if enabled:
                # Prefer EXCLUDEFROMCAPTURE; fallback if OS rejects it.
                ok = bool(user32.SetWindowDisplayAffinity(self.hwnd, WDA_EXCLUDEFROMCAPTURE))
                if not ok:
                    user32.SetWindowDisplayAffinity(self.hwnd, WDA_MONITOR)
            else:
                user32.SetWindowDisplayAffinity(self.hwnd, WDA_NONE)
        except Exception:
            # Don't crash the overlay if the API isn't available / supported.
            return

    def _check_and_update_obs_toggle(self) -> None:
        now = time.perf_counter()
        if (now - float(self._last_obs_check_time)) < float(self._obs_check_interval):
            return
        self._last_obs_check_time = now
        try:
            val = bool(self._cfg_get('obs_protection_enabled', False))
        except Exception:
            val = False
        if self._last_obs_value is None or val != self._last_obs_value:
            self._last_obs_value = val
            self._update_obs_protection(val)
    def _sync_window_rect_to_cfg(self) -> None:
        if not self.hwnd:
            return
        rect = wt.RECT()
        if not user32.GetWindowRect(self.hwnd, ctypes.byref(rect)):
            return
        self._cfg_set("radar_x", int(rect.left))
        self._cfg_set("radar_y", int(rect.top))
        self._cfg_set("radar_width", int(rect.right - rect.left))
        self._cfg_set("radar_height", int(rect.bottom - rect.top))

    def _apply_cfg_runtime(self) -> None:
        # Don't fight the user while they are dragging/resizing.
        # (We update the window rect live from the mouse handlers.)
        if getattr(self, "_dragging", False) or getattr(self, "_resizing", False):
            return

        if not self.hwnd:
            return
        try:
            x = int(self._cfg_get("radar_x", 40))
            y = int(self._cfg_get("radar_y", 120))
            w = int(self._cfg_get("radar_width", self.style.width))
            h = int(self._cfg_get("radar_height", self.style.height))
        except Exception:
            x, y, w, h = 40, 120, self.style.width, self.style.height

        w = max(self._min_w, w)
        h = max(self._min_h, h)

        try:
            alpha = int(self._cfg_get("radar_alpha", 235))
        except Exception:
            alpha = 235
        alpha = max(60, min(255, alpha))

        topmost = bool(self._cfg_get("radar_always_on_top", True))
        insert_after_hwnd = HWND_TOPMOST if topmost else HWND_NOTOPMOST

        user32.SetWindowPos(self.hwnd, insert_after_hwnd, x, y, w, h, SWP_NOACTIVATE)
        user32.SetLayeredWindowAttributes(self.hwnd, 0, alpha, LWA_ALPHA)

        if w != self.style.width or h != self.style.height:
            self._resize_backbuffer(w, h)

    def stop(self) -> None:
        """Request the radar overlay to stop (thread-safe)."""
        self._running = False
        self._cfg_set("radar_stop", True)
        if self.hwnd:
            try:
                user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass

    # ------------- drawing primitives -------------
    def _clear(self, color: int) -> None:
        # Fill entire client area
        rect = wt.RECT(0, 0, self.style.width, self.style.height)
        brush = gdi32.CreateSolidBrush(color)
        user32.FillRect(self._hdc_mem, ctypes.byref(rect), brush)
        gdi32.DeleteObject(brush)

    def _rect(self, x1: int, y1: int, x2: int, y2: int, border: int, fill: Optional[int] = None) -> None:
        # fill
        if fill is not None:
            gdi32.SetDCBrushColor(self._hdc_mem, fill)
            # rectangle uses currently selected pen/brush
        else:
            # no fill: use NULL_BRUSH
            gdi32.SelectObject(self._hdc_mem, gdi32.GetStockObject(NULL_BRUSH))

        gdi32.SetDCPenColor(self._hdc_mem, border)
        gdi32.Rectangle(self._hdc_mem, x1, y1, x2, y2)

        # restore brush
        gdi32.SelectObject(self._hdc_mem, self._dc_brush)

    def _circle(self, cx: int, cy: int, r: int, border: int, fill: Optional[int] = None) -> None:
        if fill is not None:
            gdi32.SetDCBrushColor(self._hdc_mem, fill)
        else:
            gdi32.SelectObject(self._hdc_mem, gdi32.GetStockObject(NULL_BRUSH))
        gdi32.SetDCPenColor(self._hdc_mem, border)
        gdi32.Ellipse(self._hdc_mem, cx - r, cy - r, cx + r, cy + r)
        gdi32.SelectObject(self._hdc_mem, self._dc_brush)

    def _line(self, x1: int, y1: int, x2: int, y2: int, color: int, width: int = 1) -> None:
        # pen width needs a real pen
        pen = gdi32.CreatePen(0, int(width), color)
        old = gdi32.SelectObject(self._hdc_mem, pen)
        gdi32.MoveToEx(self._hdc_mem, int(x1), int(y1), None)
        gdi32.LineTo(self._hdc_mem, int(x2), int(y2))
        gdi32.SelectObject(self._hdc_mem, old)
        gdi32.DeleteObject(pen)

    def _text(self, s: str, x: int, y: int, w: int, h: int, color: int, center_y: bool = True) -> None:
        rect = wt.RECT(int(x), int(y), int(x + w), int(y + h))
        gdi32.SetTextColor(self._hdc_mem, color)
        fmt = DT_LEFT | DT_TOP | DT_SINGLELINE | DT_NOPREFIX
        if center_y:
            fmt = DT_LEFT | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX
        user32.DrawTextW(self._hdc_mem, s, -1, ctypes.byref(rect), fmt)

    def _draw_center_marker(self, cx: int, cy: int) -> None:
        """Draw a clear center reticle on top of everything (crosshair-style)."""
        # Larger + thicker than the 1px version so it stays visible through alpha + blips.
        size = int(self._cfg_get("radar_center_marker_size", 10))
        size = max(4, min(size, 40))
        thickness = int(self._cfg_get("radar_center_marker_thickness", 2))
        thickness = max(1, min(thickness, 6))

        # Outline trick for contrast: shadow line underneath, then bright line on top.
        shadow = getattr(self.style, "border_shadow", _rgb(64, 64, 64))
        color = getattr(self.style, "border", _rgb(255, 255, 255))

        # Shadow (slightly thicker)
        self._line(cx - size, cy, cx + size, cy, shadow, thickness + 1)
        self._line(cx, cy - size, cx, cy + size, shadow, thickness + 1)

        # Main
        self._line(cx - size, cy, cx + size, cy, color, thickness)
        self._line(cx, cy - size, cx, cy + size, color, thickness)


    # ------------- radar math -------------
    def _world_to_radar(self, ex: float, ey: float, lx: float, ly: float, local_yaw_deg: float, scale: float) -> Tuple[float, float]:
        # Mirrors the math in your PyQt radar (dx,dy swap + rotate by yaw+180)
        dx = ey - ly
        dy = ex - lx
        angle = math.radians(local_yaw_deg + 180.0)
        rx = dx * math.cos(angle) - dy * math.sin(angle)
        ry = dx * math.sin(angle) + dy * math.cos(angle)
        return rx * scale, ry * scale

    # ------------- frame render -------------
    def _render(self) -> None:
        st = self.style


        # Keep OBS protection in sync with config (throttled)
        self._check_and_update_obs_toggle()
        # snapshot copy (min lock time)
        with self.lock:
            snap = (
                self.snapshot.connected,
                self.snapshot.local_x,
                self.snapshot.local_y,
                self.snapshot.local_yaw,
                self.snapshot.local_team,
                list(self.snapshot.blips),
                self.snapshot.last_ok,
            )

        connected, lx, ly, lyaw, lteam, blips, last_ok = snap

        # dynamic scale like old radar (based on max distance of entities)
        # scale
        fixed = bool(self._cfg_get("radar_fixed_range", False))
        if fixed:
            try:
                max_dist = float(self._cfg_get("radar_range_units", 3000.0))
            except Exception:
                max_dist = 3000.0
        else:
            max_dist = 1.0
            for b in blips:
                d = math.hypot(b.x - lx, b.y - ly)
                if d > max_dist:
                    max_dist = d

        max_dist = max(250.0, max_dist)
        scale = (min(st.width, st.height) / 2.2) / max_dist
        scale = max(0.05, min(scale, 0.5))

        # clear bg
        self._clear(st.bg)

        # outer "win95-ish" border
        self._rect(0, 0, st.width - 1, st.height - 1, st.border, None)

        # header
        header_fill = _rgb(30, 30, 48)
        self._rect(1, 1, st.width - 2, st.header_h, st.border_shadow, header_fill)

        status = "CONNECTED" if connected else "WAITING"
        self._text(f"{self.title}  [{status}]", 8, 1, st.width - 16, st.header_h - 2, st.title_text, center_y=True)

        # radar area bounds
        pad = st.padding
        top = st.header_h + pad
        left = pad
        right = st.width - pad
        bottom = st.height - pad

        # radar background box
        radar_fill = _rgb(16, 16, 24)
        self._rect(left, top, right, bottom, st.border_shadow, radar_fill)

        # center
        cx = (left + right) // 2
        cy = (top + bottom) // 2

        # me dot
        self._circle(cx, cy, 3, st.me_dot, st.me_dot)

        # me direction line
        yaw_rad = math.radians(lyaw)
        fx, fy = math.cos(yaw_rad), math.sin(yaw_rad)
        dx = fy * 50.0
        dy = fx * 50.0
        angle = math.radians(lyaw + 180.0)
        rx = dx * math.cos(angle) - dy * math.sin(angle)
        ry = dx * math.sin(angle) + dy * math.cos(angle)
        if bool(self._cfg_get('radar_show_me_dir', True)):
            self._line(cx, cy, int(cx + rx * scale), int(cy + ry * scale), st.me_dir, 2)

        # blips
        show_team = bool(self._cfg_get('radar_show_team', True))
        show_enemy_dir = bool(self._cfg_get('radar_show_enemy_dir', True))
        show_team_dir = bool(self._cfg_get('radar_show_team_dir', False))
        for b in blips:
            if (b.team == lteam) and (not show_team):
                continue
            rx, ry = self._world_to_radar(b.x, b.y, lx, ly, lyaw, scale)

            px = int(cx + rx)
            py = int(cy + ry)

            # clamp inside radar box
            px = max(left + 4, min(right - 4, px))
            py = max(top + 4, min(bottom - 4, py))

            dot = st.enemy_dot if b.team != lteam else st.team_dot
            self._circle(px, py, 4, dot, dot)

            # direction line (yaw)
            if (b.team != lteam and show_enemy_dir) or (b.team == lteam and show_team_dir):
                eyaw_rad = math.radians(b.yaw)
                fx2, fy2 = math.cos(eyaw_rad), math.sin(eyaw_rad)
                ex2 = b.x + fx2 * 50.0
                ey2 = b.y + fy2 * 50.0

                rx2, ry2 = self._world_to_radar(ex2, ey2, lx, ly, lyaw, scale)
                px2 = int(cx + rx2)
                py2 = int(cy + ry2)
                px2 = max(left + 4, min(right - 4, px2))
                py2 = max(top + 4, min(bottom - 4, py2))

                self._line(px, py, px2, py2, st.enemy_dir, 1)

        # center marker (draw last so it stays on top)
        self._draw_center_marker(cx, cy)

        # footer info
        age = max(0.0, time.time() - float(last_ok or time.time()))
        # self._text(f"blips: {len(blips)}  scale: {scale:.2f}  age: {age:.1f}s", left, bottom + 2, right - left, 14, st.sub_text, center_y=False)

        # present
        gdi32.BitBlt(self._hdc_win, 0, 0, st.width, st.height, self._hdc_mem, 0, 0, SRCCOPY)

    # ------------- main loop -------------
    def run(self) -> None:
        if not self.hwnd:
            # spawn using current config
            self.create(x=int(self._cfg_get('radar_x', 40)), y=int(self._cfg_get('radar_y', 120)), alpha=int(self._cfg_get('radar_alpha', 235)))

        self._running = True
        self._last_frame = time.perf_counter()
        frame_dt = 1.0 / max(20.0, float(self._cfg_get('radar_fps', self.fps)))

        class MSG(ctypes.Structure):
            _fields_ = [("hwnd", wt.HWND), ("message", wt.UINT), ("wParam", wt.WPARAM), ("lParam", wt.LPARAM), ("time", wt.DWORD), ("pt", wt.POINT)]

        msg = MSG()

        while self._running and not bool(self._cfg_get('radar_stop', False)):
            # pump messages (non-blocking)
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            now = time.perf_counter()
            if (now - self._last_frame) >= frame_dt:
                self._apply_cfg_runtime()
                try:
                    frame_dt = 1.0 / max(20.0, float(self._cfg_get('radar_fps', self.fps)))
                except Exception:
                    pass
                self._last_frame = now
                self._render()
            else:
                time.sleep(0.001)

        self._shutdown_gdi()


# ============================================================
# Public runner
# ============================================================
class RadarApp:
    """Convenience wrapper so GFusion can start/stop this cleanly."""

    def __init__(self, title: str = "GFusion Radar", cfg_ref=None):
        self.lock = threading.Lock()
        self.snapshot = RadarSnapshot()
        self.cfg_ref = cfg_ref if cfg_ref is not None else Config

        # defaults (only if missing)
        defaults = {
            "radar_enabled": False,
            "radar_stop": False,
            "radar_x": 40,
            "radar_y": 120,
            "radar_width": 280,
            "radar_height": 280,
            "radar_alpha": 235,
            "radar_fps": 60.0,
            "radar_reader_fps": 60.0,
            "radar_always_on_top": True,
            "radar_show_team": True,
            "radar_show_me_dir": True,
            "radar_show_enemy_dir": True,
            "radar_show_team_dir": False,
            "radar_fixed_range": False,
            "radar_range_units": 3000.0,
        }
        for k, v in defaults.items():
            try:
                if not hasattr(self.cfg_ref, k):
                    setattr(self.cfg_ref, k, v)
            except Exception:
                pass

        self.reader = RadarReader(self.snapshot, self.lock, cfg_ref=self.cfg_ref, fps=float(getattr(self.cfg_ref, "radar_reader_fps", 60.0)))
        self.overlay = RadarOverlay(self.snapshot, self.lock, cfg_ref=self.cfg_ref, title=title, fps=float(getattr(self.cfg_ref, "radar_fps", 60.0)))

    def start(self) -> None:
        self.reader.start()
        self.overlay.run()

    def stop(self) -> None:
        try:
            setattr(self.cfg_ref, "radar_stop", True)
        except Exception:
            pass
        self.reader.stop()
        try:
            self.overlay.stop()
        except Exception:
            pass


def main() -> None:

    app = RadarApp(cfg_ref=Config)
    app.start()


if __name__ == "__main__":
    main()