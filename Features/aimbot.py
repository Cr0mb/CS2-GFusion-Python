# ============================================================
# CS2 Aimbot / Memory Interface
# Cleaned & optimized version
# ============================================================

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

logging.basicConfig(
    filename="aimbot.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def log(msg):
    if getattr(Config, "enable_logging", True):
        logging.info(msg)
        print(msg)  # Optional: also show in console


# -------------------------------
# VisCheck Optimizer
# -------------------------------
try:
    from Performance.vischeck_optimizer import AsyncVisCheck, get_global_vischeck, PerformanceMetrics
    OPTIMIZER_AVAILABLE = True
    print("[Aimbot] Performance optimizer loaded")
except ImportError:
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
    "mouse1": 0x01,
    "mouse2": 0x02,
    "mouse3": 0x04,
    "mouse4": 0x05,
    "mouse5": 0x06,
    "left_shift": 0xA0,
    "left_ctrl": 0xA2,
    "left_alt": 0xA4,
    "caps_lock": 0x14,
}

def get_vk_code(key_name):
    """Return Windows virtual key code for given key name."""
    key = key_name.lower()
    if key in VIRTUAL_KEYS:
        return VIRTUAL_KEYS[key]
    if len(key) == 1:
        return ord(key.upper())
    return None

# -------------------------------
# Windows API setup
# -------------------------------
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_PERMISSIONS = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

# NtReadVirtualMemory (fallback)
NtReadVirtualMemory = ntdll.NtReadVirtualMemory
NtReadVirtualMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t)
]
NtReadVirtualMemory.restype = ctypes.c_ulong

# -------------------------------
# Mouse movement via SendInput
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
    """Move mouse relative by dx/dy."""
    mi = MOUSEINPUT(dx=dx, dy=dy, mouseData=0,
                    dwFlags=MOUSEEVENTF_MOVE,
                    time=0, dwExtraInfo=None)
    inp = INPUT(type=INPUT_MOUSE, ii=INPUT._INPUT(mi=mi))
    result = SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    if result == 0:
        print("[Aimbot] Warning: SendInput failed")

# -------------------------------
# Memory Reader
# -------------------------------
class IMemoryReader:
    def read(self, addr, t="int"):
        val = self.reader.read(addr, t)
        if val is None:
            print(f"[AimbotRCS] Warning: Failed to read {t} at {hex(addr)}")
        return val


    def read_vec3(self, address: int):
        raise NotImplementedError

class RPMReader(IMemoryReader):
    """Unified memory reader with kernel support."""
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
        """Read value of type t from addr."""
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
            success = kernel32.ReadProcessMemory(
                self.process_handle,
                ctypes.c_void_p(addr),
                ctypes.byref(buffer),
                size,
                ctypes.byref(bytes_read)
            )
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

    def read_vec3(self, address):
        raw = self.read_bytes(address, 12)
        if raw:
            return list(struct.unpack("fff", raw))
        return [0.0, 0.0, 0.0]

    def read_bytes(self, addr, size):
        try:
            if self.memory_interface:
                return self.memory_interface.read_bytes(addr, size)
            buffer = (ctypes.c_ubyte * size)()
            bytes_read = ctypes.c_size_t()
            success = kernel32.ReadProcessMemory(
                self.process_handle,
                ctypes.c_void_p(addr),
                ctypes.byref(buffer),
                size,
                ctypes.byref(bytes_read)
            )
            if not success or bytes_read.value != size:
                raise RuntimeError(f"RPM bytes failed at {addr:#x}")
            return bytes(buffer[:bytes_read.value])
        except Exception as e:
            print(f"[Aimbot] read_bytes error at {addr:#x}: {e}")
            return None

# -------------------------------
# Process Handling
# -------------------------------
class CS2Process:
    def __init__(self, proc_name=None, mod_name=None, timeout=30):
        self.process_name = (proc_name or getattr(Config, "process_name", "cs2.exe")).encode()
        self.module_name  = (mod_name or getattr(Config, "module_name", "client.dll")).encode()
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
        41, 42, 59, 80, 500, 505, 506, 507, 508, 509,
        512, 514, 515, 516, 519, 520, 522, 523,
        44, 43, 45, 46, 47, 48, 49
    }

    def __init__(self, config=None):
        self.cs2process = CS2Process()
        self.cs2process.initialize()
        self.process_handle = self.cs2process.process_handle
        self.client = self.cs2process.module_base
        self.reader = RPMReader(self.cs2process.process_id, self.process_handle, config)

    def get_current_weapon_id(self):
        local_player = self.reader.read(self.client + Offsets.dwLocalPlayerPawn, "long")
        if not local_player:
            return None
        weapon_ptr = self.reader.read(local_player + Offsets.m_pClippingWeapon, "long")
        if not weapon_ptr:
            return None
        item_idx_addr = weapon_ptr + Offsets.m_AttributeManager + Offsets.m_Item + Offsets.m_iItemDefinitionIndex
        return self.reader.read(item_idx_addr, "ushort")

    def is_weapon_valid_for_aim(self):
        weapon_id = self.get_current_weapon_id()
        if weapon_id is None:
            return False  # Explicitly reject None now
        return weapon_id not in self.INVALID_WEAPON_IDS


# -----------------------------
# Aimbot + RCS + Mouse Recording
# -----------------------------
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
        # Use unified reader with kernel support
        self.reader = RPMReader(self.cs2.process_id, self.process_handle, cfg)
        self.local_player_controller = self.base + self.o.dwLocalPlayerController  # cached address

        self.bone_indices = {"head": 6, "chest": 18}
        self.left_down = False
        self.shots_fired = 0
        self.last_punch = (0.0, 0.0)
        self.target_id = None
        self.last_target_lost_time = 0
        self.aim_start_time = None
        self.last_aim_angle = None

        # Enhanced RCS tracking
        self.recoil_active = False
        self.total_recoil_compensation = [0.0, 0.0]
        self.lock = threading.Lock()

        # Math function optimizations
        self._isnan = math.isnan
        self._hypot = math.hypot
        self._atan2 = math.atan2
        self._degrees = math.degrees

        # continuous raw mouse recording buffer (stores recent raw dx,dy samples)
        self.mouse_buffer = deque(maxlen=1000)  # store recent deltas
        self.raw_recordings_dirty = False

        # track previous aim key state to detect press/release edges
        self.prev_aim_state = False
        self.prev_target_id = None
        # Per-target randomized aiming profiles
        self.target_profiles = {}
        self.rcs_grace_until = 0.0
        
        # Humanization state variables
        self.humanization_enabled = getattr(cfg, "humanization_enabled", True)
        self.jitter_time = 0
        self.last_jitter_update = time.time()
        self.current_smooth_multiplier = 1.0
        self.reaction_delay_until = 0
        self.should_overshoot = False
        self.overshoot_completed = False
        
        # --- Enhanced Visibility Checker with Performance Optimization ---
        self.vis_checker = None
        self.optimized_vischeck = None

        if getattr(self.cfg, "visibility_aim_enabled", False):
            # Try optimized version first
            if OPTIMIZER_AVAILABLE:
                try:
                    self.optimized_vischeck = get_global_vischeck()
                    print("[Aimbot] Using optimized VisCheck with caching")
                except Exception as e:
                    print(f"[Aimbot] Failed to initialize optimized VisCheck: {e}")
                    print("[Aimbot] Falling back to standard VisCheck for stability")
                    self.optimized_vischeck = None

            # Fallback to original VisCheck if optimized not available
            if not self.optimized_vischeck:
                try:
                    import vischeck
                    from Process.config import Config

                    # Try to detect current map first
                    detected_map = None
                    try:
                        # Import the map detection from ESP
                        import sys
                        import os
                        sys.path.insert(0, os.path.dirname(__file__))
                        from esp import get_current_map_name, current_detected_map

                        # Try to get matchmaking base (simplified)
                        try:
                            import win32process
                            modules = win32process.EnumProcessModules(self.process_handle)
                            matchmaking_base = None
                            for module in modules:
                                name = win32process.GetModuleFileNameEx(self.process_handle, module).lower()
                                if 'matchmaking' in name:
                                    matchmaking_base = module
                                    break

                            if matchmaking_base:
                                detected_map = get_current_map_name(self.process_handle, matchmaking_base)
                                if detected_map and detected_map != "<empty>":
                                    print(f"[VisCheck] Aimbot detected current map: {detected_map}")
                        except:
                            pass
                    except:
                        pass

                    # Load detected map or fallback to configured
                    if detected_map and detected_map != "<empty>":
                        map_path = f"maps/{detected_map}.opt"
                        if os.path.exists(map_path):
                            self.vis_checker = vischeck.VisCheck(map_path)
                            print(f"[VisCheck] Aimbot auto-loaded detected map: {detected_map}")
                        else:
                            print(f"[VisCheck] Detected map file not found: {map_path}")
                            self.vis_checker = vischeck.VisCheck()
                            print("[VisCheck] Created empty aimbot instance")
                    else:
                        # Fallback to configured map
                        map_file = getattr(Config, "visibility_map_file", None)
                        if map_file and map_file != "de_mirage.opt":
                            map_path = f"maps/{map_file}" if not map_file.startswith("maps/") else map_file
                            self.vis_checker = vischeck.VisCheck(map_path)
                            print(f"[VisCheck] Aimbot loaded configured map: {map_file}")
                        else:
                            if self.optimized_vischeck:
                                print("[VisCheck] Using optimized VisCheck - no initial map configured")
                            else:
                                self.vis_checker = vischeck.VisCheck()
                                print("[VisCheck] No map detected or configured for aimbot - waiting for selection")

                except Exception as e:  # ✅ FIXED: aligned correctly with the try
                    print(f"[VisCheck Error] Failed to auto-load map: {e}")
                    self.vis_checker = None
                    self.optimized_vischeck = None



        self.weapon_tracker = CS2WeaponTracker(cfg)  # Pass config for kernel support
        
        # Performance monitoring
        self.performance_stats = {
            'visibility_checks': 0,
            'cache_hits': 0,
            'avg_check_time': 0.0,
            'last_reset': time.time()
        }

        # learning structures (existing)
        self.learning_data = {}
        self.learning_dirty = False

        # continuous raw mouse recording buffer (stores recent raw dx,dy samples)
        self.mouse_buffer = deque(maxlen=1000)  # store recent deltas
        self.raw_recordings_dirty = False

        # start background tasks
        threading.Thread(target=self.periodic_save, daemon=True).start()
        if getattr(self.cfg, 'enable_mouse_recording', True):
            threading.Thread(target=self.mouse_recorder_thread, daemon=True).start()
        
        # Start performance monitoring thread
        if OPTIMIZER_AVAILABLE:
            threading.Thread(target=self.performance_monitor_thread, daemon=True).start()
    
    def reset_recoil(self, reason="unknown"):
        """Clean reset of recoil compensation state"""
        with self.lock:
            self.shots_fired = 0
            self.last_punch = (0.0, 0.0)
            self.recoil_active = False
            self.total_recoil_compensation = [0.0, 0.0]

    # All "self.read" calls now redirect to self.reader.read
    def read_vec3(self, addr):
        return self.reader.read_vec3(addr)

    def read(self, addr, t="int"):
        return self.reader.read(addr, t)


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
            # Query full process image name
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
            # save raw recordings occasionally
            if getattr(self.cfg, 'enable_mouse_recording', True) and (time.time() - last_raw_save) > raw_save_every:
                self.save_raw_recordings()
                last_raw_save = time.time()
                self.raw_recordings_dirty = False

    def load_learning(self):
        """
        Load learning data for the current weapon into self.learning_data.

        Expected on-disk schema (JSON):
          {
            "<pitch_q>,<yaw_q>,<phase>": [
                [dp, dy, distance, bone, [vel_x, vel_y, vel_z]],
                ...
            ],
            ...
          }

        Backwards-compat:
          - If file entries are simple [dp, dy], we convert to the new richer entry with zeros.
        """
        self.learning_data = {}
        # Ensure learn_dir exists
        learn_dir = getattr(self.cfg, "learn_dir", "learn")
        if not os.path.exists(learn_dir):
            try:
                os.makedirs(learn_dir, exist_ok=True)
            except Exception as e:
                print(f"[Aimbot] Failed to create learn dir '{learn_dir}': {e}")
                return

        weapon_id = None
        try:
            weapon_id = self.weapon_tracker.get_current_weapon_id()
        except Exception as e:
            # If weapon tracker fails, we still attempt to load generic file '0.json' as fallback
            print(f"[Aimbot] Weapon tracker error during load_learning: {e}")

        if not weapon_id:
            weapon_id = 0

        filepath = os.path.join(learn_dir, f"{weapon_id}.json")
        if not os.path.exists(filepath):
            # Nothing to load
            self.learning_data = {}
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print(f"[Aimbot] Failed to read learning file '{filepath}': {e}")
            return

        max_entries = getattr(self.cfg, "learn_max_entries", 150)

        try:
            # Raw file keys are strings like "pitch_q,yaw_q,phase"
            for k, v in raw.items():
                # parse key
                try:
                    parts = k.split(",")
                    key = (float(parts[0]), float(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
                except Exception:
                    # Skip malformed keys
                    continue

                # Convert each entry in v to canonical form:
                # [dp, dy, distance, bone, [vx, vy, vz]]
                entries = []
                for item in v:
                    # old format: [dp, dy]
                    if isinstance(item, (list, tuple)) and len(item) >= 2 and all(isinstance(x, (int, float)) for x in item[:2]):
                        if len(item) == 2:
                            dp = float(item[0])
                            dy = float(item[1])
                            distance = 0.0
                            bone = -1
                            vel = [0.0, 0.0, 0.0]
                        elif len(item) == 5:
                            # new format already: dp, dy, distance, bone, [vx,vy,vz]
                            dp = float(item[0])
                            dy = float(item[1])
                            distance = float(item[2]) if item[2] is not None else 0.0
                            bone = int(item[3]) if item[3] is not None else -1
                            vel = list(item[4]) if isinstance(item[4], (list, tuple)) else [0.0, 0.0, 0.0]
                        else:
                            # best-effort parse for varied lengths
                            dp = float(item[0])
                            dy = float(item[1])
                            distance = float(item[2]) if len(item) > 2 and isinstance(item[2], (int, float)) else 0.0
                            bone = int(item[3]) if len(item) > 3 and isinstance(item[3], int) else -1
                            vel = list(item[4]) if len(item) > 4 and isinstance(item[4], (list, tuple)) else [0.0, 0.0, 0.0]

                        # clamp/round to reduce JSON size
                        entries.append((
                            round(dp, 5),
                            round(dy, 5),
                            round(distance, 2),
                            int(bone),
                            [round(float(vel[i]) if i < len(vel) else 0.0, 2) for i in range(3)]
                        ))
                    else:
                        # ignore malformed item
                        continue

                if entries:
                    self.learning_data[key] = deque(entries, maxlen=max_entries)

        except Exception as e:
            print(f"[Aimbot] Error parsing learning data '{filepath}': {e}")
            # attempt to backup corrupted file
            try:
                backup = filepath + ".bak"
                os.rename(filepath, backup)
                print(f"[Aimbot] Corrupted learning file renamed to {backup}")
            except Exception:
                pass
            self.learning_data = {}


    def save_learning(self):
        """
        Persist self.learning_data to disk for the current weapon.

        File schema (JSON):
          { "<pitch_q>,<yaw_q>,<phase>": [[dp,dy,distance,bone,[vx,vy,vz]], ...], ... }

        Uses atomic write (tmp -> rename) to avoid partial writes during crashes.
        """
        if not getattr(self.cfg, "enable_learning", True):
            return

        learn_dir = getattr(self.cfg, "learn_dir", "learn")
        if not os.path.exists(learn_dir):
            try:
                os.makedirs(learn_dir, exist_ok=True)
            except Exception as e:
                print(f"[Aimbot] Failed to create learn dir '{learn_dir}' for saving: {e}")
                return

        try:
            weapon_id = self.weapon_tracker.get_current_weapon_id() or 0
        except Exception as e:
            print(f"[Aimbot] Weapon tracker error during save_learning: {e}")
            weapon_id = 0

        filepath = os.path.join(learn_dir, f"{weapon_id}.json")
        tmp_path = filepath + ".tmp"

        # Prepare serializable dict
        out = {}
        max_entries = getattr(self.cfg, "learn_max_entries", 150)

        with self.lock:
            for key, dq in self.learning_data.items():
                # key is tuple -> stringify as "pitch_q,yaw_q,phase"
                try:
                    kstr = f"{key[0]},{key[1]},{key[2]}"
                except Exception:
                    # ignore malformed key
                    continue

                serial = []
                # ensure deque is iterated from oldest->newest
                for entry in list(dq):
                    # entry should be (dp,dy,distance,bone,[vx,vy,vz])
                    try:
                        dp = float(entry[0])
                        dy = float(entry[1])
                        distance = float(entry[2]) if len(entry) > 2 else 0.0
                        bone = int(entry[3]) if len(entry) > 3 else -1
                        vel = list(entry[4]) if len(entry) > 4 else [0.0, 0.0, 0.0]
                    except Exception:
                        # try best-effort fallback for older simple tuple
                        try:
                            dp = float(entry[0]); dy = float(entry[1])
                            distance = 0.0; bone = -1; vel = [0.0, 0.0, 0.0]
                        except Exception:
                            continue

                    # reduce precision for storage
                    serial.append([
                        round(dp, 5),
                        round(dy, 5),
                        round(distance, 2),
                        int(bone),
                        [round(float(vel[i]) if i < len(vel) else 0.0, 2) for i in range(3)]
                    ])

                if serial:
                    # trim to configured max_entries to avoid huge files
                    if len(serial) > max_entries:
                        serial = serial[-max_entries:]
                    out[kstr] = serial

        try:
            # Atomic write
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, filepath)
        except Exception as e:
            print(f"[!] Failed saving learning data to '{filepath}': {e}")
            # cleanup tmp file if present
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def save_raw_recordings(self):
        """Persist a small summary of raw mouse deltas per current weapon."""
        if not getattr(self.cfg, 'enable_mouse_recording', True):
            return
        weapon_id = self.weapon_tracker.get_current_weapon_id() or 0
        if not os.path.exists(self.cfg.learn_dir):
            os.makedirs(self.cfg.learn_dir)
        filepath = os.path.join(self.cfg.learn_dir, f"raw_mouse_{weapon_id}.json")
        # Save last N samples (downsampled) to limit size
        with self.lock:
            samples = list(self.mouse_buffer)

        try:
            # CHANGED: filter out pure-zero samples before writing to disk
            filtered = [ [int(s[0]), int(s[1])] for s in samples if not ( (s[0] == 0 and s[1] == 0) or (s == [0,0]) ) ]
            if not filtered:
                # Nothing meaningful to write — do not overwrite existing file with zeros.
                # If you prefer to write an empty file instead, change this behavior.
                # We still mark dirty False to avoid repeated attempts.
                # print("[*] No non-zero mouse samples to save; skipping write.")
                return

            # limit saved samples to 1000 and downsample if needed
            if len(filtered) > 1000:
                step = max(1, len(filtered) // 1000)
                trimmed = filtered[::step]
            else:
                trimmed = filtered

            with open(filepath, "w") as f:
                json.dump(trimmed, f)
        except Exception as e:
            print(f"[!] Failed saving raw mouse recordings: {e}")

    kernel32 = ctypes.windll.kernel32

    def get_entity(self, base, idx):
        array_idx = (idx & 0x7FFF) >> 9
        entity_addr = self.read(base + 8 * array_idx + 16, "long")
        if not entity_addr:
            return 0
        ctrl = self.read(entity_addr + 0x78 * (idx & 0x1FF), "long")
        local_ctrl = self.read(self.local_player_controller, "long")  # cached addr
        return ctrl if ctrl and ctrl != local_ctrl else 0

    def read_bone_pos(self, pawn, idx):
        scene = self.read(pawn + self.o.m_pGameSceneNode, "long")
        if not scene:
            return None
        bones = self.read(scene + self.o.m_pBoneArray, "long")
        if not bones:
            return None
        return self.read_vec3(bones + idx * 32)

    def read_weapon_id(self, pawn):
        w = self.read(pawn + self.o.m_pClippingWeapon, "long")
        if not w:
            return 0
        return self.read(w + self.o.m_AttributeManager + self.o.m_Item + self.o.m_iItemDefinitionIndex, "ushort")

    def calc_angle(self, src, dst):
        dx = dst[0] - src[0]
        dy = dst[1] - src[1]
        dz = dst[2] - src[2]
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
        d = (a - b + 180) % 360 - 180
        return d

    def in_fov(self, pitch1, yaw1, pitch2, yaw2):
        dp = self.angle_diff(pitch2, pitch1)
        dy = self.angle_diff(yaw2, yaw1)
        # squared distance (optional optimization)
        try:
            fov = getattr(self.cfg, 'FOV', 60.0)  # Default FOV if not available
            return (dp * dp + dy * dy) <= (fov * fov)
        except Exception as e:
            print(f"[Aimbot] FOV config error: {e}")
            return (dp * dp + dy * dy) <= (60.0 * 60.0)  # Fallback FOV

    @staticmethod
    def lerp(a, b, t):
        return a + (b - a) * t

    @staticmethod
    def add_noise(value, max_noise=0.03):
        return value + random.uniform(-max_noise, max_noise)

    def clamp_angle_diff(self, current, target, max_delta=MAX_DELTA_ANGLE):
        d = self.angle_diff(target, current)
        if abs(d) > max_delta:
            d = max_delta if d > 0 else -max_delta
        return current + d

    def get_target_profile(self, target_id):
        """Return (and cache) a deterministic aiming profile for each target entity."""
        if target_id not in self.target_profiles:
            rnd = random.Random(target_id)  # seed by target_id for determinism
            profile = {
                "smoothing": rnd.uniform(0.02, 0.12),        # base smoothing factor
                "jitter": rnd.uniform(0.1, 0.5),             # micro jitter scale
                "micro_freq": rnd.uniform(3.0, 6.0),         # frequency of jitter oscillation
                "human_blend": rnd.uniform(0.25, 0.55),      # how much to weight human correction
            }
            self.target_profiles[target_id] = profile
        return self.target_profiles[target_id]

    def on_click(self, x, y, btn, pressed):
        if btn == mouse.Button.left:
            self.left_down = pressed
            self.aim_start_time = time.perf_counter() if pressed else None
            if not pressed:
                self.shots_fired = 0
                self.last_punch = (0.0, 0.0)
                self.last_aim_angle = None

    def update_learning(self, key, dp, dy, alpha=0.12, distance=None, bone=None, velocity=None):
        """Update learning data with weighted smoothing + extra metadata."""
        with self.lock:
            if key not in self.learning_data:
                self.learning_data[key] = deque(maxlen=150)

            if self.learning_data[key]:
                last = self.learning_data[key][-1]
                last_dp, last_dy = last[0], last[1]
                dp = (1 - alpha) * last_dp + alpha * dp
                dy = (1 - alpha) * last_dy + alpha * dy

            entry = (
                round(dp, 5), 
                round(dy, 5),
                round(distance or 0, 2),
                bone or -1,
                tuple(round(v, 2) for v in velocity) if velocity else (0,0,0)
            )
            self.learning_data[key].append(entry)
            self.learning_dirty = True

    def get_learned_correction(self, key, distance=None, bone=None, velocity=None):
        if not self.cfg.enable_learning:
            return 0.0, 0.0

        corrections = self.learning_data.get(key)
        if not corrections:
            return 0.0, 0.0

        # Weight by similarity to current context
        def similarity(entry):
            _, _, d, b, v = entry
            score = 1.0
            if distance: 
                score *= max(0.1, 1.0 - abs(d - distance) / 500)
            if bone and b == bone:
                score *= 1.2
            if velocity and any(v):
                score *= max(0.1, 1.0 - (math.hypot(v[0]-velocity[0], v[1]-velocity[1]) / 200))
            return score

        weights = [similarity(c) for c in corrections]
        total_w = sum(weights) or 1.0

        dp = sum(c[0] * w for c, w in zip(corrections, weights)) / total_w
        dy = sum(c[1] * w for c, w in zip(corrections, weights)) / total_w
        return round(dp, 5), round(dy, 5)

    def quantize_angle(self, pitch, yaw, shots_fired, step=0.5):
        """Quantize angles into smaller bins for finer learning."""
        pitch_q = round(pitch / step) * step
        yaw_q = round(yaw / step) * step

        # Group shots into phases: early (0-5), mid (6-15), late (16+)
        if shots_fired <= 5:
            phase = 0
        elif shots_fired <= 15:
            phase = 1
        else:
            phase = 2

        return (pitch_q, yaw_q, phase)


    def get_current_bone_index(self, pawn=None, my_pos=None, pitch=None, yaw=None, frame_time=1.0/60):
        if not self.cfg.closest_to_crosshair:
            return self.bone_indices.get(self.cfg.target_bone_name, 6)

        if not pawn or not my_pos:
            return self.bone_indices.get("head", 6)

        read = self.read
        bone_pos_fn = self.read_bone_pos
        angle_diff = self.angle_diff
        isnan = self._isnan

        best_index = None
        best_distance = float('inf')

        cfg_bones = self.cfg.bone_indices_to_try
        enable_velocity_prediction = self.cfg.enable_velocity_prediction
        downward_offset = self.cfg.downward_offset

        # velocity_prediction_factor in cfg is now a multiplier (tunable). We scale it by frame_time
        vp_factor = getattr(self.cfg, 'velocity_prediction_factor', 1.0)
        smoothing = vp_factor * frame_time

        vel = None
        if enable_velocity_prediction:
            vel = self.read_vec3(pawn + self.o.m_vecVelocity)

        for idx in cfg_bones:
            pos = bone_pos_fn(pawn, idx)
            if not pos:
                continue

            if enable_velocity_prediction and vel:
                pos = [pos[i] + vel[i] * smoothing for i in range(3)]

            pos[2] -= downward_offset

            p, y = self.calc_angle(my_pos, pos)
            if isnan(p) or isnan(y):
                continue

            dist = math.hypot(angle_diff(p, pitch), angle_diff(y, yaw))
            if dist < best_distance:
                best_distance = dist
                best_index = idx

        return best_index if best_index is not None else self.bone_indices.get("head", 6)

    # -----------------------------
    # Humanization Methods
    # -----------------------------
    
    def apply_aim_jitter(self, pitch, yaw):
        """Add realistic jitter/shake to aim angles"""
        if not self.humanization_enabled or not getattr(self.cfg, "aim_jitter_enabled", True):
            return pitch, yaw
        
        current_time = time.time()
        jitter_amount = getattr(self.cfg, "aim_jitter_amount", 0.15)
        shake_freq = getattr(self.cfg, "aim_shake_frequency", 8.0)
        
        # Use sine wave for smooth shake + small random component
        self.jitter_time += (current_time - self.last_jitter_update) * shake_freq
        self.last_jitter_update = current_time
        
        # Sine-based shake (smooth oscillation)
        shake_x = math.sin(self.jitter_time) * jitter_amount * 0.1
        shake_y = math.cos(self.jitter_time * 1.3) * jitter_amount * 0.1  # Different frequency for Y
        
        # Add small random jitter
        random_x = random.uniform(-jitter_amount, jitter_amount) * 0.05
        random_y = random.uniform(-jitter_amount, jitter_amount) * 0.05
        
        return pitch + shake_x + random_x, yaw + shake_y + random_y
    
    def get_randomized_smooth(self, target_id):
        """Get a randomized smooth value for this target"""
        if not self.humanization_enabled or not getattr(self.cfg, "smooth_randomization", True):
            return 1.0
        
        # Generate consistent random smooth for this target
        if target_id not in self.target_profiles:
            min_mult = getattr(self.cfg, "smooth_random_min", 0.8)
            max_mult = getattr(self.cfg, "smooth_random_max", 1.2)
            self.target_profiles[target_id] = {
                'smooth_mult': random.uniform(min_mult, max_mult),
                'created_time': time.time()
            }
        else:
            # Profile exists but may not have smooth_mult (legacy entry)
            if 'smooth_mult' not in self.target_profiles[target_id]:
                min_mult = getattr(self.cfg, "smooth_random_min", 0.8)
                max_mult = getattr(self.cfg, "smooth_random_max", 1.2)
                self.target_profiles[target_id]['smooth_mult'] = random.uniform(min_mult, max_mult)
        
        return self.target_profiles[target_id]['smooth_mult']
    
    def check_reaction_delay(self):
        """Check if we should delay aim due to human reaction time"""
        if not self.humanization_enabled or not getattr(self.cfg, "reaction_delay_enabled", True):
            return False
        
        current_time = time.time()
        if current_time < self.reaction_delay_until:
            return True  # Still in delay period
        
        return False
    
    def trigger_reaction_delay(self):
        """Set a random reaction delay for new target"""
        if not self.humanization_enabled or not getattr(self.cfg, "reaction_delay_enabled", True):
            return
        
        min_delay = getattr(self.cfg, "reaction_delay_min", 0.01)
        max_delay = getattr(self.cfg, "reaction_delay_max", 0.08)
        delay = random.uniform(min_delay, max_delay)
        self.reaction_delay_until = time.time() + delay
    
    def should_apply_overshoot(self):
        """Determine if we should overshoot target (human-like behavior)"""
        if not self.humanization_enabled or not getattr(self.cfg, "overshoot_enabled", True):
            return False
        
        if not self.should_overshoot:
            # Roll for overshoot chance
            chance = getattr(self.cfg, "overshoot_chance", 0.15)
            if random.random() < chance:
                self.should_overshoot = True
                self.overshoot_completed = False
                return True
        
        return self.should_overshoot and not self.overshoot_completed

    # -----------------------------
    # Mouse recorder thread
    # -----------------------------
    
    def is_target_visible(self, local_pos, target_pos):
        """Check if target is visible - MATCHES ESP LOGIC"""
        visibility_enabled = getattr(self.cfg, "visibility_aim_enabled", False)
        
        if not visibility_enabled:
            print("[Aimbot Debug] Visibility check DISABLED in config")
            return True  # If visibility check is disabled, allow all targets
            
        if not local_pos or not target_pos:
            print("[Aimbot Debug] No position data, allowing target")
            return True  # No position data, allow targeting
        
        # Try to get ESP's vis_checker first (shared instance with map loaded)
        checker = None
        
        # Import ESP module to access its GLOBAL vis_checker
        try:
            from Features import esp
            if esp.vis_checker is not None:
                checker = esp.vis_checker
                # print(f"[Aimbot Debug] Using ESP's shared vis_checker")  # Reduced spam
        except Exception as e:
            print(f"[Aimbot Debug] Failed to get ESP vis_checker: {e}")
        
        # Fallback to aimbot's own checkers if ESP's not available
        if not checker:
            checker = self.vis_checker or self.optimized_vischeck
            if checker:
                print(f"[Aimbot Debug] Using aimbot's own checker (ESP checker not available)")
        
        if checker:
            try:
                # Check if checker has a map loaded (SAME AS ESP)
                has_map = False
                if hasattr(checker, 'is_map_loaded'):
                    has_map = checker.is_map_loaded()
                elif hasattr(checker, 'is_loaded'):
                    has_map = checker.is_loaded()
                
                if not has_map:
                    # If no map is loaded, default to visible (SAME AS ESP)
                    print("[Aimbot Debug] No map loaded, allowing target")
                    return True
                
                # Add eye level offset (SAME AS ESP)
                eye_offset = 64.0  # CS2 player eye height
                local_eye = (local_pos[0], local_pos[1], local_pos[2] + eye_offset)
                target_eye = (target_pos[0], target_pos[1], target_pos[2] + eye_offset)
                
                # Use VisCheck module (SAME AS ESP)
                is_visible = checker.is_visible(local_eye, target_eye)
                
                # Debug output - only print when blocking or on first few checks
                if not is_visible:
                    return
                
                # If checker returns None, default to visible (SAME AS ESP)
                if is_visible is None:
                    return True
                
                return bool(is_visible)
                
            except Exception as e:
                print(f"[Aimbot] Visibility check error: {e}")
                import traceback
                print(traceback.format_exc())
                return True  # Default to visible on error (SAME AS ESP)
        else:
            print("[Aimbot Debug] No vis_checker or optimized_vischeck available, allowing target")
        
        # If no vis_checker available, default to visible
        return True

    def mouse_recorder_thread(self):
        """Continuously record raw mouse deltas (GetCursorPos) into mouse_buffer."""
        user32 = ctypes.windll.user32
        GetCursorPos = user32.GetCursorPos
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        prev_pt = POINT()
        # initialize
        if not GetCursorPos(ctypes.byref(prev_pt)):
            prev_pt.x, prev_pt.y = 0, 0
        rate = getattr(self.cfg, 'mouse_record_rate', 125)  # Hz
        sleep_t = max(0.001, 1.0 / float(rate))
        while not self.cfg.aim_stop:
            pt = POINT()
            if GetCursorPos(ctypes.byref(pt)):
                dx = int(pt.x - prev_pt.x)
                dy = int(pt.y - prev_pt.y)
                prev_pt.x, prev_pt.y = pt.x, pt.y
                # store tuple
                with self.lock:
                    self.mouse_buffer.append((dx, dy))
                    self.raw_recordings_dirty = True
            time.sleep(sleep_t)

    def performance_monitor_thread(self):
        """Monitor and report performance statistics"""
        while not self.cfg.aim_stop:
            time.sleep(30)  # Report every 30 seconds
            now = time.time()

            if now - self.performance_stats['last_reset'] > 60:  # Reset every minute
                checks = self.performance_stats['visibility_checks']
                if checks > 0:
                    avg_time = self.performance_stats['avg_check_time']
                    cache_hit_rate = (self.performance_stats['cache_hits'] / checks) * 100
                    mouse_samples = len(self.mouse_buffer)
                    
                    print(
                        f"[Aimbot Performance] "
                        f"Checks: {checks}, "
                        f"Avg: {avg_time:.2f}ms, "
                        f"Cache: {cache_hit_rate:.1f}%, "
                        f"MouseBuffer: {mouse_samples} samples"
                    )

                # Reset stats cleanly
                self.performance_stats = {
                    'visibility_checks': 0,
                    'cache_hits': 0,
                    'avg_check_time': 0.0,
                    'last_reset': now
                }


    def dynamic_human_blend(self):
        bursts = self.compute_burst_corrections()
        if not bursts:
            return 0.1  # mostly idle
        # compute burst strength = mean of burst magnitudes
        strengths = [math.hypot(dp, dy) for dp, dy, _ in bursts]
        avg_strength = sum(strengths) / len(strengths)
        # scale to blend factor
        max_blend = getattr(self.cfg, 'human_blend_max', 0.7)
        min_blend = getattr(self.cfg, 'human_blend_min', 0.05)
        blend = min(max_blend, max(min_blend, avg_strength * 5))  # factor adjustable
        return blend

    def compute_burst_corrections(self):
        """Return a list of per-burst angle corrections."""
        with self.lock:
            samples = list(self.mouse_buffer)
        bursts = []
        current_burst = []

        for dx, dy in samples:
            if dx == 0 and dy == 0:
                if current_burst:
                    bursts.append(current_burst)
                    current_burst = []
            else:
                current_burst.append((dx, dy))
        if current_burst:
            bursts.append(current_burst)

        # Compute median correction per burst
        corrections = []
        for burst in bursts[-10:]:  # last 10 bursts
            dxs, dys = zip(*burst)
            median_dx = sorted(dxs)[len(dxs)//2]
            median_dy = sorted(dys)[len(dys)//2]
            sensitivity = getattr(self.cfg, 'sensitivity', 0.022)
            invert_y = getattr(self.cfg, 'invert_y', -1)
            dp = -median_dy * sensitivity * invert_y
            dy = -median_dx * sensitivity
            corrections.append((dp, dy, len(burst)))
        return corrections

    def filter_outliers(self, samples, threshold=None):
        """Reject deltas exceeding threshold (in pixels)."""
        if threshold is None:
            threshold = getattr(self.cfg, 'human_outlier_threshold', 50)  # default 50 pixels
        filtered = [s for s in samples if abs(s[0]) <= threshold and abs(s[1]) <= threshold]
        return filtered

    def preprocess_raw_file(self, filepath, downsample_factor=5):
        """Load existing raw mouse file, remove zeros, downsample, return stats."""
        try:
            with open(filepath, "r") as f:
                samples = json.load(f)
            # normalize (ensure list of tuples)
            norm = []
            for s in samples:
                if isinstance(s, list) and len(s) >= 2:
                    dx, dy = int(s[0]), int(s[1])
                elif isinstance(s, tuple) and len(s) >= 2:
                    dx, dy = int(s[0]), int(s[1])
                else:
                    continue
                # remove zeros
                if dx == 0 and dy == 0:
                    continue
                norm.append((dx, dy))

            # downsample
            if not norm:
                return [], 0, 0, 0, 0

            ds = norm[::downsample_factor]
            dxs, dys = zip(*ds)
            avg_dx, avg_dy = sum(dxs)/len(dxs), sum(dys)/len(dys)
            max_dx, max_dy = max(dxs), max(dys)
            # return as list of lists for consistency
            return [ [int(x), int(y)] for x, y in ds ], avg_dx, avg_dy, max_dx, max_dy
        except Exception:
            return [], 0, 0, 0, 0

    # utility to convert recent mouse deltas to angle corrections (pitch, yaw)
    def sample_recent_human_correction(self, sample_count=6):
        """Take the last N samples and convert to angle-space correction."""
        with self.lock:
            samples = [s for s in list(self.mouse_buffer)[-sample_count:] if not (s[0] == 0 and s[1] == 0)]
        if not samples:
            return 0.0, 0.0

        sum_dx = sum(s[0] for s in samples)
        sum_dy = sum(s[1] for s in samples)
        avg_dx = sum_dx / len(samples)
        avg_dy = sum_dy / len(samples)

        sensitivity = getattr(self.cfg, 'sensitivity', 0.022)
        invert_y = getattr(self.cfg, 'invert_y', -1)

        dp = -avg_dy * sensitivity * invert_y
        dy = -avg_dx * sensitivity
        return dp, dy

    def run(self):
        """
        Main aimbot + RCS loop. Patched version:
        - smoothing applied once
        - clamp before rounding
        - max_mouse_move enforced properly
        """
        from ctypes import windll
        GetAsyncKeyState = windll.user32.GetAsyncKeyState

        prev_weapon_id = None
        max_fps = 60
        frame_time = 1.0 / max_fps

        entity_cache = {}
        cache_refresh_rate = 0.2  # seconds
        last_cache_time = 0

        def squared_distance(a, b):
            return sum((a[i] - b[i]) ** 2 for i in range(3))

        def is_valid_target(pawn, my_team):
            if not pawn:
                return False
            health = self.read(pawn + self.o.m_iHealth)
            if health <= 0:
                return False
            if self.read(pawn + self.o.m_lifeState) != 256:
                return False
            if self.read(pawn + self.o.m_bDormant, "int"):
                return False
            team = self.read(pawn + self.o.m_iTeamNum)
            return self.cfg.DeathMatch or team != my_team

        while not self.cfg.aim_stop:
            start_time = time.perf_counter()
            mouse_dx, mouse_dy = 0, 0

            try:
                # --- Prechecks & aim key ---
                aim_key_cfg = getattr(self.cfg, 'aim_key', 'mouse5')
                try:
                    aim_vk = get_vk_code(aim_key_cfg)
                except Exception:
                    aim_vk = get_vk_code('mouse5')

                if aim_vk is None or not self.is_cs2_focused():
                    time.sleep(0.1)
                    continue

                curr_aim_state = (GetAsyncKeyState(aim_vk) & 0x8000) != 0

                if curr_aim_state and not self.prev_aim_state:
                    self.aim_start_time = time.perf_counter()
                    self.reset_recoil()
                if not curr_aim_state and self.prev_aim_state:
                    self.reset_recoil()
                    self.aim_start_time = None

                self.prev_aim_state = curr_aim_state
                self.left_down = curr_aim_state

                if not getattr(self.cfg, 'enabled', True):
                    time.sleep(0.01)
                    continue

                # --- Read local player ---
                base = self.base
                o = self.o
                pawn = self.read(base + o.dwLocalPlayerPawn, "long")
                if not pawn:
                    time.sleep(0.01)
                    continue

                weapon_id = self.weapon_tracker.get_current_weapon_id()
                if weapon_id != prev_weapon_id:
                    self.load_learning()
                    prev_weapon_id = weapon_id

                health = self.read(pawn + o.m_iHealth)
                if health <= 0:
                    time.sleep(0.01)
                    continue

                if not self.weapon_tracker.is_weapon_valid_for_aim():
                    time.sleep(0.01)
                    continue

                ctrl = self.read(base + o.dwLocalPlayerController, "long")
                my_team = self.read(pawn + o.m_iTeamNum)
                my_pos = self.read_vec3(pawn + o.m_vOldOrigin)
                view_raw = self.reader.read_bytes(base + o.dwViewAngles, 8)
                pitch, yaw = struct.unpack("ff", view_raw) if view_raw else (0.0, 0.0)
                recoil_pitch = self.read(pawn + o.m_aimPunchAngle, "float")
                recoil_yaw = self.read(pawn + o.m_aimPunchAngle + 4, "float")

                entity_list = self.read(base + o.dwEntityList, "long")
                if not entity_list:
                    time.sleep(0.01)
                    continue

                # refresh cache occasionally
                if time.time() - last_cache_time > cache_refresh_rate:
                    entity_cache.clear()
                    for i in range(self.cfg.max_entities):
                        ctrl_ent = self.get_entity(entity_list, i)
                        if not ctrl_ent or ctrl_ent == ctrl:
                            continue
                        pawn_ent = self.get_entity(entity_list, self.read(ctrl_ent + o.m_hPlayerPawn) & 0x7FFF)
                        if not pawn_ent or not is_valid_target(pawn_ent, my_team):
                            continue
                        entity_cache[i] = (ctrl_ent, pawn_ent)
                    last_cache_time = time.time()

                # --- Target selection (simplified from your version) ---
                target, target_pos = None, None
                # keep previous target if valid, else pick nearest visible
                if self.target_id in entity_cache:
                    _, t_pawn = entity_cache[self.target_id]
                    bone_idx = self.get_current_bone_index(t_pawn, my_pos, pitch, yaw, frame_time=frame_time)
                    pos = self.read_bone_pos(t_pawn, bone_idx) or self.read_vec3(t_pawn + o.m_vOldOrigin)
                    vel = self.read_vec3(t_pawn + o.m_vecVelocity) if self.cfg.enable_velocity_prediction else [0,0,0]
                    predicted = [pos[i] + vel[i]*frame_time*self.cfg.velocity_prediction_factor for i in range(3)]
                    predicted[2] -= self.cfg.downward_offset
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
                        vel = self.read_vec3(pawn_ent + o.m_vecVelocity) if self.cfg.enable_velocity_prediction else [0,0,0]
                        predicted = [pos[j] + vel[j]*frame_time*self.cfg.velocity_prediction_factor for j in range(3)]
                        predicted[2] -= self.cfg.downward_offset
                        tp, ty = self.calc_angle(my_pos, predicted)
                        if not self.in_fov(pitch, yaw, tp, ty) or not self.is_target_visible(my_pos, predicted):
                            continue
                        dist = squared_distance(my_pos, predicted)
                        if dist < min_dist:
                            min_dist, target, target_pos, self.target_id = dist, pawn_ent, predicted, i

                if self.target_id != self.prev_target_id:
                    self.reset_recoil()
                    # Trigger reaction delay for new target (humanization)
                    self.trigger_reaction_delay()
                    # Reset overshoot state for new target
                    self.should_overshoot = False
                    self.overshoot_completed = False
                self.prev_target_id = self.target_id
                
                # Check reaction delay (humanization)
                if self.check_reaction_delay():
                    time.sleep(0.001)
                    continue

                # --- Core aiming + RCS ---
                if self.left_down and target and target_pos:
                    self.shots_fired += 1
                    tp, ty = self.calc_angle(my_pos, target_pos)

                    # Recoil scale
                    scale = getattr(self.cfg, "rcs_scale", 1.0) * min(self.shots_fired / 2.0, 1.0)

                    # Compensated angles
                    comp_pitch = tp - recoil_pitch * scale
                    comp_yaw   = ty - recoil_yaw * scale

                    comp_pitch = self.clamp_angle_diff(pitch, comp_pitch, max_delta=5.0)
                    comp_yaw   = self.clamp_angle_diff(yaw, comp_yaw,   max_delta=5.0)

                    # Quantize learning key
                    key = self.quantize_angle(comp_pitch, comp_yaw, self.shots_fired)
                    distance = math.dist(my_pos, target_pos) if my_pos and target_pos else 0
                    bone_idx = self.get_current_bone_index(target, my_pos, pitch, yaw)
                    vel = self.read_vec3(target + self.o.m_vecVelocity) if target else None

                    # Correction from learning
                    dp, dy = self.get_learned_correction(key, distance=distance, bone=bone_idx, velocity=vel)
                    self.update_learning(key, dp, dy, distance=distance, bone=bone_idx, velocity=vel)

                    # Blend with recent human correction
                    if getattr(self.cfg, 'enable_mouse_recording', True):
                        human_dp, human_dy = self.sample_recent_human_correction(8)
                        if abs(human_dp) < 2.0 and abs(human_dy) < 2.0:
                            blend = getattr(self.cfg, 'human_blend', 0.35)
                            dp = (1 - blend) * dp + blend * human_dp
                            dy = (1 - blend) * dy + blend * human_dy

                    comp_pitch += dp
                    comp_yaw   += dy

                    profile = self.get_target_profile(self.target_id or 0)

                    # Adaptive smoothing (capped lower to ensure convergence)
                    dyn_smooth = profile["smoothing"] + (self.shots_fired * 0.0015)
                    dyn_smooth = min(dyn_smooth, 0.15)
                    smooth = max(0.01, dyn_smooth)
                    
                    # Apply randomized smooth multiplier (humanization)
                    smooth_mult = self.get_randomized_smooth(self.target_id or 0)
                    smooth = smooth * smooth_mult

                    # Apply overshoot if determined (humanization)
                    if self.should_apply_overshoot():
                        overshoot_mult = getattr(self.cfg, "overshoot_amount", 1.2)
                        comp_pitch = pitch + (comp_pitch - pitch) * overshoot_mult
                        comp_yaw = yaw + (comp_yaw - yaw) * overshoot_mult
                        # Mark overshoot as completed after one frame
                        self.overshoot_completed = True
                    
                    # Interpolate once
                    sp = self.lerp(pitch, comp_pitch, smooth)
                    sy = self.lerp(yaw, comp_yaw, smooth)
                    sp, sy = self.normalize(sp, sy)

                    # Add small random jitter instead of circular
                    sp += random.uniform(-profile["jitter"], profile["jitter"])
                    sy += random.uniform(-profile["jitter"], profile["jitter"])
                    
                    # Apply humanization jitter/shake
                    sp, sy = self.apply_aim_jitter(sp, sy)

                    # Snap if nearly on target
                    delta_pitch = sp - pitch
                    delta_yaw   = sy - yaw
                    if abs(delta_pitch) < 0.2: sp = comp_pitch
                    if abs(delta_yaw) < 0.2:   sy = comp_yaw

                    # Convert to mouse move
                    sensitivity = getattr(self.cfg, 'sensitivity', 0.022)
                    invert_y = getattr(self.cfg, 'invert_y', -1)

                    raw_dx = - (sy - yaw) / sensitivity
                    raw_dy = - (sp - pitch) / sensitivity * invert_y

                    max_move = getattr(self.cfg, 'max_mouse_move', 25)
                    clamped_dx = max(min(raw_dx, max_move), -max_move)
                    clamped_dy = max(min(raw_dy, max_move), -max_move)

                    mouse_dx = int(clamped_dx)
                    mouse_dy = int(clamped_dy)

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

        # save on exit
        if self.cfg.enable_learning:
            self.save_learning()
        if getattr(self.cfg, 'enable_mouse_recording', True):
            self.save_raw_recordings()
        print("[AimbotRCS] Stopped.")

def start_aim_rcs(cfg):
    AimbotRCS(cfg).run()