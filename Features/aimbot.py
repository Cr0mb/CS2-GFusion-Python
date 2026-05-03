# aimbot_humanized.py
"""
Legit-style Aimbot + RCS + Humanization
- Distance-aware reaction delay
- Overshoot with short decay window
- Smooth ramp (ease-in-out) and per-target randomized smoothing
- Micro-jitter + slow drift
- Contextual frame dithering + occasional micro-pauses
- Delayed RCS engagement
- Target stickiness window
This file is drop-in compatible with existing GFusion imports.
"""

import os
import time
import math
import random
import json
import threading
import ctypes
import struct
from ctypes import wintypes
from collections import deque

from Process.offsets import Offsets
from Process.config import Config
from Process.memory_interface import MemoryInterface

import logging

# Import ESP's visibility checking system
try:
    from Features.esp import check_player_visibility, get_current_map_name_cached
    ESP_VISCHECK_AVAILABLE = True
    print("[Aimbot] Using ESP's visibility checking system")
except Exception as e:
    ESP_VISCHECK_AVAILABLE = False
    print(f"[Aimbot] ESP visibility import failed: {e}")

logging.basicConfig(
    filename="aimbot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def log(msg):
    if getattr(Config, "enable_logging", True):
        logging.info(msg)
        print(msg)


# Map detection constants removed - using ESP's system


# -------------------------------
# Optional optimizer
# -------------------------------
try:
    from Performance.vischeck_optimizer import AsyncVisCheck, get_global_vischeck, PerformanceMetrics
    OPTIMIZER_AVAILABLE = True
    print("[Aimbot] Performance optimizer loaded")
except Exception:
    OPTIMIZER_AVAILABLE = False
    print("[Aimbot] Performance optimizer not available - using fallback")


# -------------------------------
# Windows constants & structs
# -------------------------------
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE  = 0x00000008
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

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


# -------------------------------
# Virtual Keys
# -------------------------------
VIRTUAL_KEYS = {
    "mouse1": 0x01, "mouse2": 0x02, "mouse3": 0x04, "mouse4": 0x05, "mouse5": 0x06,
    "left_shift": 0xA0, "left_ctrl": 0xA2, "left_alt": 0xA4, "caps_lock": 0x14,
}
def get_vk_code(key_name):
    key = str(key_name).lower()
    if key in VIRTUAL_KEYS:
        return VIRTUAL_KEYS[key]
    if len(key) == 1:
        return ord(key.upper())
    return None


# -------------------------------
# Windows API
# -------------------------------
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_PERMISSIONS = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

# NtReadVirtualMemory (fallback)
NtReadVirtualMemory = ntdll.NtReadVirtualMemory
NtReadVirtualMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
NtReadVirtualMemory.restype = ctypes.c_ulong


# -------------------------------
# SendInput mouse
# -------------------------------
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _fields_ = [("type", ctypes.c_ulong), ("ii", _INPUT)]

SendInput = ctypes.windll.user32.SendInput

def move_mouse(dx, dy):
    mi = MOUSEINPUT(dx=dx, dy=dy, mouseData=0, dwFlags=MOUSEEVENTF_MOVE, time=0, dwExtraInfo=None)
    inp = INPUT(type=INPUT_MOUSE, ii=INPUT._INPUT(mi=mi))
    if SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp)) == 0:
        print("[Aimbot] Warning: SendInput failed")


# Map Detection removed - using ESP's get_current_map_name_cached


# -------------------------------
# Memory Reader
# -------------------------------
class IMemoryReader:
    def read(self, addr, t="int"):
        raise NotImplementedError
    def read_vec3(self, address: int):
        raise NotImplementedError
    def read_bytes(self, addr, size):
        raise NotImplementedError

class RPMReader(IMemoryReader):
    """Unified memory reader with kernel support (MemoryInterface -> fallback RPM)."""
    def __init__(self, process_id, process_handle, config=None):
        self.process_id = process_id
        self.process_handle = process_handle
        self.memory_interface = None
        try:
            self.memory_interface = MemoryInterface(process_id, process_handle, config)
            mode = "kernel" if self.memory_interface.is_kernel_mode_active() else "usermode"
            print(f"[Aimbot] Using {mode} memory access")
        except Exception as e:
            print(f"[Aimbot] Failed to init MemoryInterface: {e}")

    def read(self, addr, t="int"):
        try:
            if self.memory_interface:
                if t == "int":    return self.memory_interface.read_int(addr)
                if t == "long":   return self.memory_interface.read_uint64(addr)
                if t == "float":  return self.memory_interface.read_float(addr)
                if t == "ushort": return self.memory_interface.read_uint32(addr) & 0xFFFF

            # fallback RPM
            size_map = {"int": 4, "long": 8, "float": 4, "ushort": 2}
            size = size_map.get(t, 4)
            buffer = (ctypes.c_ubyte * size)()
            bytes_read = ctypes.c_size_t()
            success = kernel32.ReadProcessMemory(self.process_handle, ctypes.c_void_p(addr), ctypes.byref(buffer), size, ctypes.byref(bytes_read))
            if not success or bytes_read.value != size:
                raise RuntimeError(f"RPM failed at {addr:#x}")
            raw = bytes(buffer[:size])
            if t == "int":    return int.from_bytes(raw, "little", signed=True)
            if t == "long":   return int.from_bytes(raw, "little", signed=False)
            if t == "float":  return struct.unpack("f", raw)[0]
            if t == "ushort": return int.from_bytes(raw, "little", signed=False)
        except Exception as e:
            print(f"[Aimbot] Memory read error ({t}) at {addr:#x}: {e}")
        return None

    def read_bytes(self, addr, size):
        try:
            if self.memory_interface:
                return self.memory_interface.read_bytes(addr, size)
            buffer = (ctypes.c_ubyte * size)()
            bytes_read = ctypes.c_size_t()
            success = kernel32.ReadProcessMemory(self.process_handle, ctypes.c_void_p(addr), ctypes.byref(buffer), size, ctypes.byref(bytes_read))
            if not success or bytes_read.value != size:
                raise RuntimeError(f"RPM bytes failed at {addr:#x}")
            return bytes(buffer[:bytes_read.value])
        except Exception as e:
            print(f"[Aimbot] read_bytes error at {addr:#x}: {e}")
            return None

    def read_vec3(self, address):
        raw = self.read_bytes(address, 12)
        if raw:
            return list(struct.unpack("fff", raw))
        return [0.0, 0.0, 0.0]


# -------------------------------
# Active-weapon resolution
# -------------------------------
# CS2 build 14154+ no longer exposes m_pClippingWeapon as a direct pointer
# on C_CSPlayerPawn. The active weapon is reached through:
#   pawn + m_pWeaponServices  (deref) -> CCSPlayer_WeaponServices
#   + m_hActiveWeapon         -> CHandle (uint32) into the entity list
# Then the handle resolves the same way as player handles:
#   chunk = *(entity_list + 8 * (idx >> 9) + 16)
#   entity = *(chunk + 0x70 * (idx & 0x1FF))
def _resolve_active_weapon(reader, client_base, pawn):
    if not pawn:
        return 0
    wsvcs_off = getattr(Offsets, "m_pWeaponServices", 0)
    hwep_off  = getattr(Offsets, "m_hActiveWeapon", 0)
    elist_off = getattr(Offsets, "dwEntityList", 0)
    if not (wsvcs_off and hwep_off and elist_off):
        return 0
    wsvcs = reader.read(pawn + wsvcs_off, "long")
    if not wsvcs:
        return 0
    handle = reader.read(wsvcs + hwep_off, "int")
    if not handle or handle == -1:
        return 0
    entity_list = reader.read(client_base + elist_off, "long")
    if not entity_list:
        return 0
    idx = handle & 0x7FFF
    chunk = reader.read(entity_list + 8 * (idx >> 9) + 16, "long")
    if not chunk:
        return 0
    return reader.read(chunk + 0x70 * (idx & 0x1FF), "long") or 0


# -------------------------------
# Process Handling
# -------------------------------
class CS2Process:
    def __init__(self, proc_name=None, mod_name=None, timeout=30):
        self.process_name = (proc_name or getattr(Config, "process_name", "cs2.exe")).encode()
        self.module_name  = (mod_name  or getattr(Config, "module_name", "client.dll")).encode()
        self.wait_timeout = timeout
        self.process_handle = None
        self.process_id = None
        self.module_base = None

    def _get_pid(self):
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == INVALID_HANDLE_VALUE:
            return None
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not kernel32.Process32First(snap, ctypes.byref(entry)):
            kernel32.CloseHandle(snap)
            return None
        while True:
            if entry.szExeFile == self.process_name:
                pid = entry.th32ProcessID
                kernel32.CloseHandle(snap)
                return pid
            if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                break
        kernel32.CloseHandle(snap)
        return None

    def _get_module_base(self):
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, self.process_id)
        if snap == INVALID_HANDLE_VALUE:
            return None
        mod = MODULEENTRY32()
        mod.dwSize = ctypes.sizeof(MODULEENTRY32)
        if not kernel32.Module32First(snap, ctypes.byref(mod)):
            kernel32.CloseHandle(snap)
            return None
        while True:
            if mod.szModule == self.module_name:
                base = ctypes.cast(mod.modBaseAddr, ctypes.c_void_p).value
                kernel32.CloseHandle(snap)
                return base
            if not kernel32.Module32Next(snap, ctypes.byref(mod)):
                break
        kernel32.CloseHandle(snap)
        return None

    def initialize(self):
        start = time.time()
        while time.time() - start < self.wait_timeout:
            self.process_id = self._get_pid()
            if self.process_id:
                self.process_handle = kernel32.OpenProcess(PROCESS_PERMISSIONS, False, self.process_id)
                if self.process_handle:
                    self.module_base = self._get_module_base()
                    if self.module_base:
                        return
            time.sleep(0.5)
        raise TimeoutError("CS2 process or client.dll not found")

    def __repr__(self):
        return f"<CS2Process pid={self.process_id} base=0x{self.module_base:x}>" if self.module_base else "<CS2Process not ready>"


# -------------------------------
# Weapon Tracking
# -------------------------------
class CS2WeaponTracker:
    INVALID_WEAPON_IDS = {
        41, 42, 59, 80, 500, 505, 506, 507, 508, 509, 512, 514, 515, 516, 519, 520, 522, 523,
        44, 43, 45, 46, 47, 48, 49
    }
    def __init__(self, config=None):
        self.cs2process = CS2Process()
        self.cs2process.initialize()
        self.process_handle = self.cs2process.process_handle
        self.client = self.cs2process.module_base
        self.reader = RPMReader(self.cs2process.process_id, self.process_handle, config)

    def get_current_weapon_id(self):
        local_pawn = self.reader.read(self.client + Offsets.dwLocalPlayerPawn, "long")
        if not local_pawn:
            return None
        weapon_ptr = _resolve_active_weapon(self.reader, self.client, local_pawn)
        if not weapon_ptr:
            return None
        item_idx_addr = weapon_ptr + Offsets.m_AttributeManager + Offsets.m_Item + Offsets.m_iItemDefinitionIndex
        return self.reader.read(item_idx_addr, "ushort")

    def is_weapon_valid_for_aim(self):
        weapon_id = self.get_current_weapon_id()
        if weapon_id is None:
            return False
        return weapon_id not in self.INVALID_WEAPON_IDS


# -----------------------------
# Aimbot + RCS + Mouse Recording
# -----------------------------
BONES = {
    # CS2 build 14154+ skeleton — see GHax_Free_v2/Game/Bone.h enum BONEINDEX.
    "head":       7,
    "neck":       6,   # neck_0

    # Upper torso (spine_2, closest to neck)
    "chest":      4,

    # Lower torso
    "stomach":    3,   # spine_1
    "pelvis":     1,

    # Arms / hands
    "right_hand": 15,  # hand_R
    "left_hand":  11,  # hand_L

    # Legs (ankle is the bottom-most aimable joint)
    "right_leg":  22,  # ankle_R
    "left_leg":   19,  # ankle_L
}

# sensible defaults for aiming
DEFAULT_AIM_BONES = (
    BONES["head"],
    BONES["neck"],
    BONES["chest"],
    BONES["pelvis"],
    BONES["left_hand"],
    BONES["right_hand"],
    BONES["left_leg"],
    BONES["right_leg"],
)

# Hot-loop config keys + defaults. Snapshotted every ~0.5s into a SimpleNamespace
# so the run() loop reads attributes (one C-level dict lookup) instead of
# calling getattr() with a default ~30+ times per tick. Runtime config edits
# from the UI propagate within the refresh interval.
_HOT_CFG_DEFAULTS = (
    ("enabled",                    True),
    ("DeathMatch",                 False),
    ("aim_key",                    "mouse5"),
    ("max_entities",               256),
    ("enable_velocity_prediction", False),
    ("velocity_prediction_factor", 1.0),
    ("downward_offset",            0.0),
    ("stickiness_time",            0.25),
    ("post_switch_shaky_time",     0.18),
    ("micro_pause_chance",         0.02),
    ("rcs_delay_seconds",          0.04),
    ("rcs_scale",                  1.0),
    ("enable_mouse_recording",     True),
    ("human_blend",                0.35),
    ("smooth_ramp_speed",          1.45),
    ("overshoot_amount",           1.12),
    ("overshoot_decay_time",       0.12),
    ("m_yaw",                      0.022),
    ("invert_y",                   -1),
    ("max_mouse_move",             40),
    ("max_move_jitter",            0.6),
    ("humanization_enabled",       True),
    ("aim_jitter_enabled",         True),
    ("visibility_aim_enabled",     False),
    ("aim_tick_rate",              60),
    ("entity_cache_refresh",       0.20),
    ("idle_drop_probability",      0.03),
    ("engage_drop_probability",    0.012),
)
_HOT_CFG_REFRESH_S = 0.5


class _HC:
    __slots__ = tuple(k for k, _ in _HOT_CFG_DEFAULTS) + ("_refresh_at",)


def _snap_hot_cfg(cfg, hc=None):
    if hc is None:
        hc = _HC()
    g = getattr
    for k, d in _HOT_CFG_DEFAULTS:
        setattr(hc, k, g(cfg, k, d))
    return hc


class AimbotRCS:
    MAX_DELTA_ANGLE = 60
    SENSITIVITY = None
    INVERT_Y = -1
    LEARN_DIR = None

    def __init__(self, cfg):
        self.cfg = cfg
        self.o = Offsets()
        self.cs2 = CS2Process()
        self.cs2.initialize()
        self.base = self.cs2.module_base
        self.process_handle = self.cs2.process_handle

        self.reader = RPMReader(self.cs2.process_id, self.process_handle, cfg)
        self.local_player_controller = self.base + self.o.dwLocalPlayerController

        self.bone_indices = BONES


        # Runtime state
        self.left_down = False
        self.shots_fired = 0
        self.last_punch = (0.0, 0.0)
        self.target_id = None
        self.prev_target_id = None
        self.aim_start_time = None
        self.last_aim_angle = None

        # Overshoot decay window
        self.overshoot_decay_until = 0.0

        # RCS tracking
        self.recoil_active = False
        self.total_recoil_compensation = [0.0, 0.0]

        # Sub-pixel mouse remainders (carry fractional pixel motion across
        # frames so smoothed/long-distance aim still progresses). Mirrors
        # GHax_Free_v2/Features/Aimbot.cpp RemainderX/Y.
        self.remainder_x = 0.0
        self.remainder_y = 0.0

        # Live player sensitivity (read from client.dll each frame). Falls
        # back to 1.0 until the first successful read.
        self.player_sensitivity = 1.0
        self._sens_obj_ptr = 0  # cached *(client + dwSensitivity) deref

        # Locks & hot math refs
        self.lock = threading.Lock()
        self._isnan = math.isnan
        self._hypot = math.hypot
        self._atan2 = math.atan2
        self._degrees = math.degrees

        # Mouse sampling
        self.mouse_buffer = deque(maxlen=1000)
        self.raw_recordings_dirty = False

        # Per-target humanization
        self.target_profiles = {}
        self.rcs_grace_until = 0.0

        # Humanization toggles/state
        self.humanization_enabled = getattr(cfg, "humanization_enabled", True)
        self.jitter_time = 0.0
        self.last_jitter_update = time.time()
        self.current_smooth_multiplier = 1.0
        self.reaction_delay_until = 0.0
        self.should_overshoot = False
        self.overshoot_completed = False
        self.stickiness_timer = 0.0
        self.smooth_ramp = 0.0

        # Visibility - using ESP's global vis_checker (shared between ESP and aimbot)
        self.vis_checker = None
        self.use_esp_vischeck = ESP_VISCHECK_AVAILABLE

        self.weapon_tracker = CS2WeaponTracker(cfg)

        # Perf stats
        self.performance_stats = {'visibility_checks': 0, 'cache_hits': 0, 'avg_check_time': 0.0, 'last_reset': time.time()}

        # Learning
        self.learning_data = {}
        self.learning_dirty = False

        # Background tasks
        threading.Thread(target=self.periodic_save, daemon=True).start()
        if getattr(self.cfg, 'enable_mouse_recording', True):
            threading.Thread(target=self.mouse_recorder_thread, daemon=True).start()
        if OPTIMIZER_AVAILABLE:
            threading.Thread(target=self.performance_monitor_thread, daemon=True).start()
        
        # No map loading thread needed - ESP handles all map detection and loading

    # -----------------------------
    # Easing
    # -----------------------------
    @staticmethod
    def ease_out_quint(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return 1 - (1 - t) ** 5
    @staticmethod
    def ease_out_cubic(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return 1 - (1 - t) ** 3
    @staticmethod
    def ease_in_out_quad(t: float) -> float:
        t = max(0.0, min(1.0, t))
        return 2*t*t if t < 0.5 else -1 + (4 - 2*t)*t

    def reset_recoil(self, reason="unknown"):
        with self.lock:
            self.shots_fired = 0
            self.last_punch = (0.0, 0.0)
            self.recoil_active = False
            self.total_recoil_compensation = [0.0, 0.0]

            # Reset humanization state so runtime toggles behave immediately.
            self.should_overshoot = False
            self.overshoot_completed = False
            self.overshoot_decay_until = 0.0
            self.reaction_delay_until = 0.0

    # Reader redirects
    def read_vec3(self, addr): return self.reader.read_vec3(addr)
    def read(self, addr, t="int"): return self.reader.read(addr, t)

    # -----------------------------
    # Focus & periodic save
    # -----------------------------
    def is_cs2_focused(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return False

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        PROCESS_VM_READ = 0x0010
        PROCESS_QUERY_INFORMATION = 0x0400

        hProcess = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid.value)
        if not hProcess:
            return False

        try:
            buffer_len = wintypes.DWORD(260)
            exe_path_buffer = ctypes.create_unicode_buffer(buffer_len.value)
            QueryFullProcessImageName = kernel32.QueryFullProcessImageNameW
            if not QueryFullProcessImageName(hProcess, 0, exe_path_buffer, ctypes.byref(buffer_len)):
                return False
            exe_name = exe_path_buffer.value.split("\\")[-1].lower()
            return exe_name == "cs2.exe"
        finally:
            kernel32.CloseHandle(hProcess)

    def periodic_save(self):
        last_raw_save = time.time()
        raw_save_every = getattr(self.cfg, 'raw_save_every', 30)
        while not self.cfg.aim_stop:
            time.sleep(30)
            if self.cfg.enable_learning and self.learning_dirty:
                self.save_learning()
                self.learning_dirty = False
            if getattr(self.cfg, 'enable_mouse_recording', True) and (time.time() - last_raw_save) > raw_save_every:
                self.save_raw_recordings()
                last_raw_save = time.time()
                self.raw_recordings_dirty = False

    # -----------------------------
    # Learning I/O
    # -----------------------------
    def load_learning(self):
        self.learning_data = {}
        learn_dir = getattr(self.cfg, "learn_dir", "learn")
        os.makedirs(learn_dir, exist_ok=True)

        weapon_id = 0
        try:
            weapon_id = self.weapon_tracker.get_current_weapon_id() or 0
        except Exception as e:
            print(f"[Aimbot] Weapon tracker error during load_learning: {e}")

        filepath = os.path.join(learn_dir, f"{weapon_id}.json")
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print(f"[Aimbot] Failed to read learning file '{filepath}': {e}")
            return

        max_entries = getattr(self.cfg, "learn_max_entries", 150)
        for k, v in (raw or {}).items():
            try:
                parts = k.split(",")
                key = (float(parts[0]), float(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
            except Exception:
                continue
            dq = deque(maxlen=max_entries)
            for item in v:
                try:
                    dp = float(item[0]); dy = float(item[1])
                    distance = float(item[2]) if len(item) > 2 else 0.0
                    bone = int(item[3]) if len(item) > 3 else -1
                    vel = list(item[4]) if len(item) > 4 else [0.0, 0.0, 0.0]
                    dq.append([round(dp,5), round(dy,5), round(distance,2), int(bone), [round(float(vel[i]) if i < len(vel) else 0.0, 2) for i in range(3)]])
                except Exception:
                    continue
            if dq:
                self.learning_data[key] = dq

    def save_learning(self):
        if not getattr(self.cfg, "enable_learning", True):
            return
        learn_dir = getattr(self.cfg, "learn_dir", "learn")
        os.makedirs(learn_dir, exist_ok=True)

        try:
            weapon_id = self.weapon_tracker.get_current_weapon_id() or 0
        except Exception as e:
            print(f"[Aimbot] Weapon tracker error during save_learning: {e}")
            weapon_id = 0

        filepath = os.path.join(learn_dir, f"{weapon_id}.json")
        tmp_path = filepath + ".tmp"

        out = {}
        max_entries = getattr(self.cfg, "learn_max_entries", 150)
        with self.lock:
            for key, dq in self.learning_data.items():
                try:
                    kstr = f"{key[0]},{key[1]},{key[2]}"
                except Exception:
                    continue
                serial = []
                for entry in list(dq)[-max_entries:]:
                    try:
                        dp = float(entry[0]); dy = float(entry[1])
                        distance = float(entry[2]) if len(entry) > 2 else 0.0
                        bone = int(entry[3]) if len(entry) > 3 else -1
                        vel = list(entry[4]) if len(entry) > 4 else [0.0, 0.0, 0.0]
                    except Exception:
                        continue
                    serial.append([round(dp,5), round(dy,5), round(distance,2), int(bone), [round(float(vel[i]) if i < len(vel) else 0.0, 2) for i in range(3)]])
                if serial:
                    out[kstr] = serial
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
                f.flush(); os.fsync(f.fileno())
            os.replace(tmp_path, filepath)
        except Exception as e:
            print(f"[!] Failed saving learning data to '{filepath}': {e}")
            try:
                if os.path.exists(tmp_path): os.remove(tmp_path)
            except Exception:
                pass

    def save_raw_recordings(self):
        if not getattr(self.cfg, 'enable_mouse_recording', True):
            return
        weapon_id = self.weapon_tracker.get_current_weapon_id() or 0
        os.makedirs(self.cfg.learn_dir, exist_ok=True)
        filepath = os.path.join(self.cfg.learn_dir, f"raw_mouse_{weapon_id}.json")
        with self.lock:
            samples = list(self.mouse_buffer)
        try:
            filtered = [[int(s[0]), int(s[1])] for s in samples if not (s[0] == 0 and s[1] == 0)]
            if not filtered:
                return
            if len(filtered) > 1000:
                step = max(1, len(filtered) // 1000)
                trimmed = filtered[::step]
            else:
                trimmed = filtered
            with open(filepath, "w") as f:
                json.dump(trimmed, f)
        except Exception as e:
            print(f"[!] Failed saving raw mouse recordings: {e}")

    # -----------------------------
    # Entity helpers
    # -----------------------------
    kernel32 = ctypes.windll.kernel32

    def get_entity(self, base, idx):
        array_idx = (idx & 0x7FFF) >> 9
        entity_addr = self.read(base + 8 * array_idx + 16, "long")
        if not entity_addr:
            return 0
        ctrl = self.read(entity_addr + 0x70 * (idx & 0x1FF), "long")  # CS2 update: stride changed from 0x78 (120) to 0x70 (112)
        local_ctrl = self.read(self.local_player_controller, "long")
        return ctrl if ctrl and ctrl != local_ctrl else 0

    def read_bone_pos(self, pawn, idx):
        scene = self.read(pawn + self.o.m_pGameSceneNode, "long")
        if not scene:
            return None
        bones = self.read(scene + self.o.m_pBoneArray, "long")
        if not bones:
            return None
        return self.reader.read_vec3(bones + idx * 32)

    def read_player_sensitivity(self):
        """Read CS2 player sensitivity from client.dll. Mirrors the C++
        reference (Client::GetSensitivity in GHax_Free_v2/Game/Entity.cpp):
            ptr = *(client_dll + dwSensitivity)
            sens = *(ptr + dwSensitivity_sensitivity)
        Returns the cached value if a read fails; never returns 0."""
        try:
            sens_off = getattr(self.o, "dwSensitivity", 0)
            sub_off = getattr(self.o, "dwSensitivity_sensitivity", 88)
            if not sens_off:
                return self.player_sensitivity
            if not self._sens_obj_ptr:
                self._sens_obj_ptr = self.read(self.base + sens_off, "long") or 0
            if not self._sens_obj_ptr:
                return self.player_sensitivity
            sens = self.read(self._sens_obj_ptr + sub_off, "float")
            if sens and sens > 0.0001:
                self.player_sensitivity = float(sens)
        except Exception:
            # Force re-resolve next frame; client may have reloaded.
            self._sens_obj_ptr = 0
        return self.player_sensitivity

    def read_weapon_id(self, pawn):
        w = _resolve_active_weapon(self.reader, self.base, pawn)
        if not w:
            return 0
        return self.read(w + self.o.m_AttributeManager + self.o.m_Item + self.o.m_iItemDefinitionIndex, "ushort")

    # -----------------------------
    # Angles
    # -----------------------------
    def calc_angle(self, src, dst):
        dx, dy, dz = dst[0]-src[0], dst[1]-src[1], dst[2]-src[2]
        hyp = self._hypot(dx, dy)
        pitch = -self._degrees(self._atan2(dz, hyp))
        yaw = self._degrees(self._atan2(dy, dx))
        return pitch, yaw

    def normalize(self, pitch, yaw):
        if self._isnan(pitch) or self._isnan(yaw):
            return 0.0, 0.0
        pitch = max(min(pitch, 89.0), -89.0)
        yaw = (yaw + 180.0) % 360.0 - 180.0
        return pitch, yaw

    def angle_diff(self, a, b):
        return (a - b + 180) % 360 - 180

    def in_fov(self, pitch1, yaw1, pitch2, yaw2):
        dp = self.angle_diff(pitch2, pitch1)
        dy = self.angle_diff(yaw2, yaw1)
        fov = float(getattr(self.cfg, 'FOV', 60.0))
        return (dp * dp + dy * dy) <= (fov * fov)

    @staticmethod
    def lerp(a, b, t): return a + (b - a) * t

    def clamp_angle_diff(self, current, target, max_delta=MAX_DELTA_ANGLE):
        d = self.angle_diff(target, current)
        if abs(d) > max_delta:
            d = max_delta if d > 0 else -max_delta
        return current + d

    # -----------------------------
    # Bone selection
    # -----------------------------
    def get_current_bone_index(
        self,
        pawn,
        my_pos,
        pitch,
        yaw,
        frame_time=1.0 / 60.0,
    ):
        """
        If cfg.closest_to_crosshair is False:
            aim at cfg.target_bone_name (or first cfg.aim_bones entry).
        If True:
            scan cfg.aim_bones and pick the closest-to-crosshair bone.
        """
        if not pawn or not my_pos:
            return self.bone_indices.get("head", 7)

        # --- Fixed bone mode (HEAD-ONLY etc.) ---
        if not bool(getattr(self.cfg, "closest_to_crosshair", False)):
            name = str(getattr(self.cfg, "target_bone_name", "head")).lower().strip()
            if name in self.bone_indices:
                return self.bone_indices[name]

            # fallback: first aim_bones entry if target_bone_name is invalid
            bone_names = getattr(self.cfg, "aim_bones", ["head"])
            if bone_names:
                first = str(bone_names[0]).lower().strip()
                if first in self.bone_indices:
                    return self.bone_indices[first]

            return self.bone_indices.get("head", 7)

        # --- Multi-bone mode (closest-to-crosshair) ---
        bone_names = getattr(self.cfg, "aim_bones", ["head"])
        bone_ids = [self.bone_indices[b] for b in bone_names if b in self.bone_indices]
        if not bone_ids:
            return self.bone_indices.get("head", 7)

        best_bone = None
        best_delta = float("inf")

        vel = (
            self.read_vec3(pawn + self.o.m_vecVelocity)
            if getattr(self.cfg, "enable_velocity_prediction", False)
            else None
        )

        for bone in bone_ids:
            pos = self.read_bone_pos(pawn, bone)
            if not pos:
                continue

            if vel:
                factor = float(getattr(self.cfg, "velocity_prediction_factor", 1.0))
                pos = [pos[i] + vel[i] * frame_time * factor for i in range(3)]

            pos[2] -= float(getattr(self.cfg, "downward_offset", 0.0))

            p, y = self.calc_angle(my_pos, pos)
            if math.isnan(p) or math.isnan(y):
                continue

            delta = math.hypot(
                self.angle_diff(p, pitch),
                self.angle_diff(y, yaw),
            )

            if delta < best_delta:
                best_delta = delta
                best_bone = bone

        return best_bone if best_bone is not None else self.bone_indices.get("head", 6)


    # -----------------------------
    # Humanization
    # -----------------------------
    def get_target_profile(self, target_id: int):
        if target_id not in self.target_profiles:
            rnd = random.Random(target_id)
            self.target_profiles[target_id] = {
                "smoothing": rnd.uniform(0.02, 0.10),
                "jitter": rnd.uniform(0.10, 0.40),
                "smooth_mult": rnd.uniform(
                    getattr(self.cfg, "smooth_random_min", 0.85),
                    getattr(self.cfg, "smooth_random_max", 1.15),
                ),
            }
        return self.target_profiles[target_id]


    def _is_humanization_enabled(self) -> bool:
        """Read humanization toggle live from cfg to support runtime toggling."""
        return bool(getattr(self.cfg, "humanization_enabled", True))

    def _is_jitter_enabled(self) -> bool:
        """Master jitter gate. When OFF, all jitter-like randomness is disabled."""
        return self._is_humanization_enabled() and bool(getattr(self.cfg, "aim_jitter_enabled", True))


    def apply_aim_jitter(self, pitch, yaw):
        if not self._is_jitter_enabled():
            return pitch, yaw
        t = time.time()
        # sinusoidal micro-shake
        shake_x = math.sin(t * 6.5) * 0.08
        shake_y = math.cos(t * 7.3) * 0.08
        # slow drift
        drift_x = math.sin(t * 0.5) * 0.05
        drift_y = math.cos(t * 0.6) * 0.05
        return pitch + shake_x + drift_x, yaw + shake_y + drift_y

    def get_randomized_smooth(self, target_id):
        if not self._is_humanization_enabled() or not getattr(self.cfg, "smooth_randomization", True):
            return 1.0
        return self.get_target_profile(target_id).get("smooth_mult", 1.0)

    def check_reaction_delay(self):
        if not self._is_humanization_enabled() or not getattr(self.cfg, "reaction_delay_enabled", True):
            return False
        return time.time() < self.reaction_delay_until

    def trigger_reaction_delay(self, distance=0.0):
        if not self._is_humanization_enabled() or not getattr(self.cfg, "reaction_delay_enabled", True):
            return
        # Distance-aware reaction
        base_min, base_max = 0.02, 0.12
        dist_factor = min(distance / 2000.0, 1.0)
        min_delay = base_min + dist_factor * 0.05
        max_delay = base_max + dist_factor * 0.15
        self.reaction_delay_until = time.time() + random.uniform(min_delay, max_delay)

    def should_apply_overshoot(self):
        if not self._is_humanization_enabled() or not getattr(self.cfg, "overshoot_enabled", True):
            return False
        if not self.should_overshoot:
            chance = getattr(self.cfg, "overshoot_chance", 0.15)
            if random.random() < chance:
                self.should_overshoot = True
                self.overshoot_completed = False
                return True
        return self.should_overshoot and not self.overshoot_completed

    # -----------------------------
    # Visibility (using ESP's check_player_visibility directly)
    # -----------------------------
    def is_target_visible(self, local_pos, target_pos):
        """
        Check if target is visible using ESP's check_player_visibility function
        
        Args:
            local_pos: Local player position (list/tuple [x, y, z])
            target_pos: Target entity position (list/tuple [x, y, z])
        """
        if not getattr(self.cfg, "visibility_aim_enabled", False):
            return True
            
        if not self.use_esp_vischeck:
            return True  # ESP visibility not available
            
        if not local_pos or not target_pos:
            return True
        
        try:
            # Import ESP's vis_checker global if not already cached
            if not self.vis_checker:
                try:
                    import Features.esp as esp_module
                    # Get ESP's global vis_checker
                    self.vis_checker = getattr(esp_module, 'vis_checker', None)
                except Exception:
                    return True
            
            if not self.vis_checker:
                return True  # ESP's vis_checker not initialized yet
            
            # Create simple Vec3-like objects for ESP's function
            class Vec3:
                def __init__(self, x, y, z):
                    self.x = x
                    self.y = y
                    self.z = z
            
            local_vec = Vec3(local_pos[0], local_pos[1], local_pos[2])
            target_vec = Vec3(target_pos[0], target_pos[1], target_pos[2])
            
            # Use ESP's check_player_visibility function directly
            return check_player_visibility(local_vec, target_vec, self.vis_checker)
            
        except Exception as e:
            # On error, default to not visible for safety
            return False


    # -----------------------------
    # Recorder & perf monitor
    # -----------------------------
    def mouse_recorder_thread(self):
        user32 = ctypes.windll.user32
        GetCursorPos = user32.GetCursorPos
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        prev_pt = POINT()
        if not GetCursorPos(ctypes.byref(prev_pt)):
            prev_pt.x, prev_pt.y = 0, 0
        rate = float(getattr(self.cfg, 'mouse_record_rate', 125))  # Hz
        sleep_t = max(0.001, 1.0 / rate)
        while not self.cfg.aim_stop:
            pt = POINT()
            if GetCursorPos(ctypes.byref(pt)):
                dx = int(pt.x - prev_pt.x); dy = int(pt.y - prev_pt.y)
                prev_pt.x, prev_pt.y = pt.x, pt.y
                with self.lock:
                    self.mouse_buffer.append((dx, dy))
                    self.raw_recordings_dirty = True
            time.sleep(sleep_t)

    def performance_monitor_thread(self):
        while not self.cfg.aim_stop:
            time.sleep(30)
            now = time.time()
            if now - self.performance_stats['last_reset'] > 60:
                checks = self.performance_stats['visibility_checks']
                if checks > 0:
                    avg_time = self.performance_stats['avg_check_time']
                    cache_hit_rate = (self.performance_stats['cache_hits'] / checks) * 100 if checks else 0.0
                    mouse_samples = len(self.mouse_buffer)
                    print(f"[Aimbot Performance] Checks: {checks}, Avg: {avg_time:.2f}ms, Cache: {cache_hit_rate:.1f}%, MouseBuffer: {mouse_samples}")
                self.performance_stats = {'visibility_checks': 0, 'cache_hits': 0, 'avg_check_time': 0.0, 'last_reset': now}

    # -----------------------------
    # Learning helpers
    # -----------------------------
    def compute_burst_corrections(self):
        with self.lock:
            samples = list(self.mouse_buffer)
        bursts, current_burst = [], []
        for dx, dy in samples:
            if dx == 0 and dy == 0:
                if current_burst:
                    bursts.append(current_burst); current_burst = []
            else:
                current_burst.append((dx, dy))
        if current_burst:
            bursts.append(current_burst)
        corrections = []
        for burst in bursts[-10:]:
            dxs, dys = zip(*burst)
            median_dx = sorted(dxs)[len(dxs)//2]
            median_dy = sorted(dys)[len(dys)//2]
            sensitivity = float(getattr(self.cfg, 'sensitivity', 0.022))
            invert_y = float(getattr(self.cfg, 'invert_y', -1))
            dp = -median_dy * sensitivity * invert_y
            dy = -median_dx * sensitivity
            corrections.append((dp, dy, len(burst)))
        return corrections

    def dynamic_human_blend(self):
        bursts = self.compute_burst_corrections()
        if not bursts:
            return 0.1
        strengths = [math.hypot(dp, dy) for dp, dy, _ in bursts]
        avg_strength = sum(strengths) / len(strengths)
        return min(float(getattr(self.cfg, 'human_blend_max', 0.7)), max(float(getattr(self.cfg, 'human_blend_min', 0.05)), avg_strength * 5))

    def sample_recent_human_correction(self, sample_count=6):
        with self.lock:
            samples = [s for s in list(self.mouse_buffer)[-sample_count:] if not (s[0] == 0 and s[1] == 0)]
        if not samples:
            return 0.0, 0.0
        avg_dx = sum(s[0] for s in samples) / len(samples)
        avg_dy = sum(s[1] for s in samples) / len(samples)
        sensitivity = float(getattr(self.cfg, 'sensitivity', 0.022))
        invert_y = float(getattr(self.cfg, 'invert_y', -1))
        dp = -avg_dy * sensitivity * invert_y
        dy = -avg_dx * sensitivity
        return dp, dy

    def update_learning(self, key, dp, dy, alpha=0.12, distance=None, bone=None, velocity=None):
        with self.lock:
            if key not in self.learning_data:
                self.learning_data[key] = deque(maxlen=int(getattr(self.cfg, "learn_max_entries", 150)))
            if self.learning_data[key]:
                last_dp, last_dy = self.learning_data[key][-1][0], self.learning_data[key][-1][1]
                dp = (1 - alpha) * last_dp + alpha * dp
                dy = (1 - alpha) * last_dy + alpha * dy
            entry = (round(dp, 5), round(dy, 5), round(distance or 0, 2), int(bone or -1), tuple(round(v, 2) for v in (velocity or (0,0,0))))
            self.learning_data[key].append(entry)
            self.learning_dirty = True

    def get_learned_correction(self, key, distance=None, bone=None, velocity=None):
        if not getattr(self.cfg, "enable_learning", True):
            return 0.0, 0.0
        corrections = self.learning_data.get(key)
        if not corrections:
            return 0.0, 0.0
        def similarity(entry):
            _, _, d, b, v = entry
            score = 1.0
            if distance is not None: score *= max(0.1, 1.0 - abs(d - distance) / 500)
            if bone is not None and b == bone: score *= 1.2
            if velocity is not None and any(v): score *= max(0.1, 1.0 - (math.hypot(v[0]-velocity[0], v[1]-velocity[1]) / 200))
            return score
        weights = [similarity(c) for c in corrections]
        total_w = sum(weights) or 1.0
        dp = sum(c[0] * w for c, w in zip(corrections, weights)) / total_w
        dy = sum(c[1] * w for c, w in zip(corrections, weights)) / total_w
        return round(dp, 5), round(dy, 5)

    def quantize_angle(self, pitch, yaw, shots_fired, step=0.5):
        pitch_q = round(pitch / step) * step
        yaw_q = round(yaw / step) * step
        phase = 0 if shots_fired <= 5 else (1 if shots_fired <= 15 else 2)
        return (pitch_q, yaw_q, phase)

    # -----------------------------
    # Main loop
    # -----------------------------
    def run(self):
        from ctypes import windll
        GetAsyncKeyState = windll.user32.GetAsyncKeyState

        prev_weapon_id = None

        # Hot-config snapshot — refreshed every _HOT_CFG_REFRESH_S so the
        # tight loop avoids ~30+ getattr() calls per iteration.
        hc = _snap_hot_cfg(self.cfg)
        hc._refresh_at = time.perf_counter() + _HOT_CFG_REFRESH_S

        max_fps = int(hc.aim_tick_rate)
        frame_time = 1.0 / max(30, min(240, max_fps))

        entity_cache = {}
        cache_refresh_rate = float(hc.entity_cache_refresh)
        last_cache_time = 0.0

        post_switch_shaky_until = 0.0

        def squared_distance(a, b):
            return (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2

        def is_valid_target(pawn, my_team):
            if not pawn: return False
            health = self.read(pawn + self.o.m_iHealth)
            if not health or health <= 0: return False
            if self.read(pawn + self.o.m_lifeState) != 256: return False
            if self.read(pawn + self.o.m_bDormant, "int"): return False
            team = self.read(pawn + self.o.m_iTeamNum)
            return hc.DeathMatch or (team != my_team)

        while not self.cfg.aim_stop:
            start_time = time.perf_counter()
            mouse_dx = mouse_dy = 0

            # Refresh hot-config snapshot at ~2 Hz so UI edits propagate
            # without the per-iteration getattr() tax.
            if start_time >= hc._refresh_at:
                _snap_hot_cfg(self.cfg, hc)
                hc._refresh_at = start_time + _HOT_CFG_REFRESH_S

            try:
                aim_vk = get_vk_code(hc.aim_key) or get_vk_code('mouse5')
                if aim_vk is None or not self.is_cs2_focused():
                    time.sleep(0.1); continue

                curr_aim_state = (GetAsyncKeyState(aim_vk) & 0x8000) != 0

                # Press/release edges
                if curr_aim_state and not self.left_down:
                    self.aim_start_time = time.perf_counter()
                    self.reset_recoil()
                    self.smooth_ramp = 0.0
                if not curr_aim_state and self.left_down:
                    self.reset_recoil()
                    self.aim_start_time = None
                    self.smooth_ramp = 0.0
                    # Drop any unsent sub-pixel motion so the next aim press
                    # doesn't pop with a stale fractional remainder.
                    self.remainder_x = 0.0
                    self.remainder_y = 0.0

                self.left_down = curr_aim_state

                if not hc.enabled:
                    time.sleep(0.01); continue

                # Local
                base = self.base; o = self.o
                pawn = self.read(base + o.dwLocalPlayerPawn, "long")
                if not pawn: time.sleep(0.01); continue

                weapon_id = self.weapon_tracker.get_current_weapon_id()
                if weapon_id != prev_weapon_id:
                    self.load_learning()
                    prev_weapon_id = weapon_id

                health = self.read(pawn + o.m_iHealth)
                if not health or health <= 0: time.sleep(0.01); continue

                if not self.weapon_tracker.is_weapon_valid_for_aim():
                    time.sleep(0.01); continue

                ctrl = self.read(base + o.dwLocalPlayerController, "long")
                my_team = self.read(pawn + o.m_iTeamNum)
                my_pos = self.read_vec3(pawn + o.m_vOldOrigin)
                view_raw = self.reader.read_bytes(base + o.dwViewAngles, 8)
                pitch, yaw = struct.unpack("ff", view_raw) if view_raw else (0.0, 0.0)
                # CS2 build 14154+ removed m_aimPunchAngle from C_CSPlayerPawn.
                # Read via the new AimPunchServices chain:
                #   pawn + m_pAimPunchServices (deref) -> CCSPlayer_AimPunchServices
                #   + m_predictableBaseAngle -> Vec2 (pitch, yaw)
                aps = self.read(pawn + o.m_pAimPunchServices, "long") if getattr(o, "m_pAimPunchServices", 0) else 0
                if aps:
                    base_angle_off = getattr(o, "m_predictableBaseAngle", 80) or 80
                    recoil_pitch = self.read(aps + base_angle_off,     "float") or 0.0
                    recoil_yaw   = self.read(aps + base_angle_off + 4, "float") or 0.0
                else:
                    # Fallback for older builds where m_aimPunchAngle still exists.
                    legacy = getattr(o, "m_aimPunchAngle", 0) or 0
                    recoil_pitch = self.read(pawn + legacy,     "float") if legacy else 0.0
                    recoil_yaw   = self.read(pawn + legacy + 4, "float") if legacy else 0.0
                    recoil_pitch = recoil_pitch or 0.0
                    recoil_yaw   = recoil_yaw or 0.0

                entity_list = self.read(base + o.dwEntityList, "long")
                if not entity_list: time.sleep(0.01); continue

                # Cache refresh
                now = time.time()
                if now - last_cache_time > cache_refresh_rate:
                    entity_cache.clear()
                    max_e = int(hc.max_entities)
                    for i in range(max_e):
                        ctrl_ent = self.get_entity(entity_list, i)
                        if not ctrl_ent or ctrl_ent == ctrl: continue
                        pawn_ent = self.get_entity(entity_list, self.read(ctrl_ent + o.m_hPlayerPawn) & 0x7FFF)
                        if not pawn_ent or not is_valid_target(pawn_ent, my_team): continue
                        entity_cache[i] = (ctrl_ent, pawn_ent)
                    last_cache_time = now

                # Target selection
                target, target_pos = None, None
                use_vel = hc.enable_velocity_prediction
                vel_factor = float(hc.velocity_prediction_factor)
                downward_off = float(hc.downward_offset)

                if self.target_id in entity_cache:
                    _, t_pawn = entity_cache[self.target_id]
                    bone_idx = self.get_current_bone_index(t_pawn, my_pos, pitch, yaw, frame_time=frame_time)
                    pos = self.read_bone_pos(t_pawn, bone_idx) or self.read_vec3(t_pawn + o.m_vOldOrigin)
                    vel = self.read_vec3(t_pawn + o.m_vecVelocity) if use_vel else [0,0,0]
                    predicted = [pos[i] + vel[i] * frame_time * vel_factor for i in range(3)]
                    predicted[2] -= downward_off
                    tp, ty = self.calc_angle(my_pos, predicted)
                    if not self.in_fov(pitch, yaw, tp, ty) or not self.is_target_visible(my_pos, predicted):
                        self.target_id = None
                    else:
                        target, target_pos = t_pawn, predicted

                if target is None:
                    min_dist = float("inf")
                    for i, (_, pawn_ent) in entity_cache.items():
                        bone_idx = self.get_current_bone_index(pawn_ent, my_pos, pitch, yaw, frame_time=frame_time)
                        pos = self.read_bone_pos(pawn_ent, bone_idx) or self.read_vec3(pawn_ent + o.m_vOldOrigin)
                        vel = self.read_vec3(pawn_ent + o.m_vecVelocity) if use_vel else [0,0,0]
                        predicted = [pos[j] + vel[j] * frame_time * vel_factor for j in range(3)]
                        predicted[2] -= downward_off
                        tp, ty = self.calc_angle(my_pos, predicted)
                        if not self.in_fov(pitch, yaw, tp, ty) or not self.is_target_visible(my_pos, predicted):
                            continue
                        dist = squared_distance(my_pos, predicted)
                        if dist < min_dist:
                            min_dist, target, target_pos, self.target_id = dist, pawn_ent, predicted, i

                # Stickiness & switch handling
                if self.target_id != self.prev_target_id:
                    if self.prev_target_id is not None and (now - self.stickiness_timer) < float(hc.stickiness_time) and self.prev_target_id in entity_cache:
                        self.target_id = self.prev_target_id
                    else:
                        self.reset_recoil()
                        distance_for_delay = math.sqrt(min_dist) if target_pos else 0.0
                        self.trigger_reaction_delay(distance_for_delay)
                        self.should_overshoot = False
                        self.overshoot_completed = False
                        self.smooth_ramp = 0.0
                        self.stickiness_timer = now
                        post_switch_shaky_until = now + float(hc.post_switch_shaky_time)
                self.prev_target_id = self.target_id

                # Frame dithering / micro-pauses are jitter-like randomness.
                # When jitter is OFF the motion stays fully deterministic.
                jitter_on = hc.humanization_enabled and hc.aim_jitter_enabled
                if jitter_on:
                    engage_drop = float(hc.engage_drop_probability)
                    if now < post_switch_shaky_until:
                        engage_drop *= 1.6
                    if self.left_down and random.random() < engage_drop:
                        time.sleep(frame_time); continue
                    if not self.left_down and random.random() < float(hc.idle_drop_probability):
                        time.sleep(frame_time); continue
                    if self.left_down and random.random() < float(hc.micro_pause_chance):
                        time.sleep(random.uniform(0.010, 0.028))

                # Reaction delay wait
                if self.check_reaction_delay():
                    time.sleep(0.001); continue

                # ----------------- Aim Core -----------------
                if self.left_down and target and target_pos:
                    self.shots_fired += 1
                    tp, ty = self.calc_angle(my_pos, target_pos)

                    # RCS: delayed engagement based on time since aim start + shots
                    time_since_start = (time.perf_counter() - (self.aim_start_time or time.perf_counter()))
                    rcs_scale_t = max(0.0, min(1.0, time_since_start / max(0.005, float(hc.rcs_delay_seconds))))
                    burst_scale = min(self.shots_fired / 3.0, 1.0)
                    scale = float(hc.rcs_scale) * max(rcs_scale_t, 0.35) * burst_scale

                    comp_pitch = tp - (recoil_pitch * scale)
                    comp_yaw   = ty - (recoil_yaw   * scale)

                    # Per-frame clamp
                    comp_pitch = self.clamp_angle_diff(pitch, comp_pitch, max_delta=5.0)
                    comp_yaw   = self.clamp_angle_diff(yaw,   comp_yaw,   max_delta=5.0)

                    # Learning corrections
                    key = self.quantize_angle(comp_pitch, comp_yaw, self.shots_fired)
                    distance = math.dist(my_pos, target_pos) if my_pos and target_pos else 0.0
                    bone_idx = self.get_current_bone_index(target, my_pos, pitch, yaw)
                    vel = self.read_vec3(target + self.o.m_vecVelocity) if target else None

                    dp, dy = self.get_learned_correction(key, distance=distance, bone=bone_idx, velocity=vel)
                    self.update_learning(key, dp, dy, distance=distance, bone=bone_idx, velocity=vel)

                    # Blend recent human deltas
                    if hc.enable_mouse_recording:
                        human_dp, human_dy = self.sample_recent_human_correction(8)
                        magnitude = math.hypot(comp_pitch - pitch, comp_yaw - yaw)
                        dyn_blend = max(0.1, float(hc.human_blend) * (1.0 - min(magnitude / 15.0, 0.8)))
                        if abs(human_dp) < 2.0 and abs(human_dy) < 2.0:
                            dp = (1 - dyn_blend) * dp + dyn_blend * human_dp
                            dy = (1 - dyn_blend) * dy + dyn_blend * human_dy

                    comp_pitch += dp
                    comp_yaw   += dy

                    # Per-target profile + smoothing ramp
                    profile = self.get_target_profile(self.target_id or 0)
                    dyn_smooth = min(profile["smoothing"] + (self.shots_fired * 0.0013), 0.14)
                    self.smooth_ramp = min(1.0, self.smooth_ramp + frame_time * float(hc.smooth_ramp_speed))
                    # Start slightly jerky then smooth out
                    ramp = self.ease_in_out_quad(self.smooth_ramp)
                    smooth = max(0.01, dyn_smooth * (0.55 + 0.45 * ramp))
                    smooth *= self.get_randomized_smooth(self.target_id or 0)

                    # Overshoot & short decay (single time.time() call reused)
                    overshoot_decay_s = float(hc.overshoot_decay_time)
                    if self.should_apply_overshoot():
                        overshoot_mult = float(hc.overshoot_amount)
                        comp_pitch = pitch + (comp_pitch - pitch) * overshoot_mult
                        comp_yaw   = yaw  + (comp_yaw   - yaw)  * overshoot_mult
                        self.overshoot_completed = True
                        self.overshoot_decay_until = now + overshoot_decay_s

                    if now < self.overshoot_decay_until:
                        decay_factor = max(0.0, (self.overshoot_decay_until - now) / overshoot_decay_s)
                        comp_pitch = pitch + (comp_pitch - pitch) * decay_factor
                        comp_yaw   = yaw  + (comp_yaw   - yaw)  * decay_factor

                    # Interpolate once (ease-out-ish)
                    t = self.ease_out_cubic(smooth * 1.12)
                    sp = self.lerp(pitch, comp_pitch, t)
                    sy = self.lerp(yaw,   comp_yaw,   t)
                    sp, sy = self.normalize(sp, sy)

                    # Micro jitter & drift
                    if self._is_jitter_enabled():
                        jitter = profile.get("jitter", 0.22)
                        sp += random.uniform(-jitter, jitter)
                        sy += random.uniform(-jitter, jitter)
                        sp, sy = self.apply_aim_jitter(sp, sy)

                    # Snap if very close
                    if abs(sp - pitch) < 0.18: sp = comp_pitch
                    if abs(sy - yaw)   < 0.18: sy = comp_yaw

                    # Convert angle delta to mouse counts.
                    # CS2 mouse math:
                    #   degrees = mouse_count * m_yaw * player_sensitivity
                    # So:
                    #   mouse_count = degrees / (m_yaw * player_sensitivity)
                    # m_yaw is the fixed 0.022 cvar; player_sensitivity is
                    # read live from client.dll each frame so changing in-game
                    # sens no longer breaks aim distance.
                    player_sens = self.read_player_sensitivity() or 1.0
                    counts_per_deg = 1.0 / max(0.0001, float(hc.m_yaw) * player_sens)
                    raw_dx = -(sy - yaw)   * counts_per_deg
                    raw_dy = -(sp - pitch) * counts_per_deg * float(hc.invert_y)

                    max_move = float(hc.max_mouse_move)
                    if jitter_on:
                        jitter_clamp = float(hc.max_move_jitter)
                        local_max = max_move + random.uniform(-jitter_clamp, jitter_clamp)
                        raw_dx = max(min(raw_dx, local_max), -local_max)
                        raw_dy = max(min(raw_dy, local_max), -local_max)
                        raw_dx += random.uniform(-0.14, 0.14)
                        raw_dy += random.uniform(-0.14, 0.14)
                    else:
                        raw_dx = max(min(raw_dx, max_move), -max_move)
                        raw_dy = max(min(raw_dy, max_move), -max_move)

                    # Sub-pixel remainder accumulation (matches GHax_Free_v2
                    # AimControl::AimBot RemainderX/Y). Without this, smoothed
                    # deltas under 1 px/frame are int-truncated to zero and
                    # the aim stalls indefinitely on small adjustments.
                    raw_dx += self.remainder_x
                    raw_dy += self.remainder_y
                    mouse_dx = int(raw_dx)
                    mouse_dy = int(raw_dy)
                    self.remainder_x = raw_dx - mouse_dx
                    self.remainder_y = raw_dy - mouse_dy

                    self.last_aim_angle = (sp, sy)
                else:
                    self.reset_recoil()

                if mouse_dx or mouse_dy:
                    move_mouse(mouse_dx, mouse_dy)

            except Exception as e:
                print(f"[!] AimbotRCS error: {e}")
                time.sleep(0.05)

            elapsed = time.perf_counter() - start_time
            time.sleep(max(0.0, frame_time - elapsed))

        # Shutdown save
        if getattr(self.cfg, "enable_learning", True):
            self.save_learning()
        if getattr(self.cfg, 'enable_mouse_recording', True):
            self.save_raw_recordings()
        print("[AimbotRCS] Stopped.")


def start_aim_rcs(cfg):
    AimbotRCS(cfg).run()
