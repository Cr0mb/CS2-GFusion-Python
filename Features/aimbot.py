# (Full file - updated with continuous mouse recording + blending learning)
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

# -------------------------------
# Define missing constants & structs
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
    key = key_name.lower()
    if key in VIRTUAL_KEYS:
        return VIRTUAL_KEYS[key]
    if len(key) == 1:
        # map single characters (a-z, 0-9)
        return ord(key.upper())
    return None


# -----------------------------
# NT ReadProcessMemory Setup
# -----------------------------
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_PERMISSIONS = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
NtReadVirtualMemory = ntdll.NtReadVirtualMemory
NtReadVirtualMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t)
]
NtReadVirtualMemory.restype = ctypes.c_ulong

# -----------------------------
# Mouse Movement (SendInput)
# -----------------------------
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
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

# -----------------------------
# Memory Readers
# -----------------------------
class IMemoryReader:
    def read(self, address: int, t: str = "int"):
        raise NotImplementedError

    def read_vec3(self, address: int):
        raise NotImplementedError

class RPMReader(IMemoryReader):
    """Read memory using kernel32.ReadProcessMemory"""
    def __init__(self, process_handle):
        self.process_handle = process_handle

    def read(self, addr, t="int"):
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
            return 0.0 if t == "float" else 0

        raw = bytes(buffer[:size])
        if t == "int":
            return int.from_bytes(raw, "little", signed=True)
        elif t == "long":
            return int.from_bytes(raw, "little", signed=False)
        elif t == "float":
            return struct.unpack("f", raw)[0]
        elif t == "ushort":
            return int.from_bytes(raw, "little", signed=False)
        return 0

    def read_vec3(self, address):
        raw = self.read_bytes(address, 12)
        if raw:
            return list(struct.unpack("fff", raw))
        return [0.0, 0.0, 0.0]

    def read_bytes(self, addr, size):
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
            return None
        return bytes(buffer[:bytes_read.value])

# -----------------------------
# Process Handling
# -----------------------------
class CS2Process:
    def __init__(self, proc_name="cs2.exe", mod_name="client.dll", timeout=30):
        self.process_name = proc_name.encode()
        self.module_name = mod_name.encode()
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

    def wait_for_process(self):
        start = time.time()
        while time.time() - start < self.wait_timeout:
            self.process_id = self._get_pid()
            if self.process_id:
                self.process_handle = kernel32.OpenProcess(PROCESS_PERMISSIONS, False, self.process_id)
                if self.process_handle:
                    return True
            time.sleep(0.5)
        raise TimeoutError("Process not found")

    def get_module_base(self):
        self.module_base = self._get_module_base()
        if not self.module_base:
            raise Exception("Module not found")

    def initialize(self):
        self.wait_for_process()
        self.get_module_base()

    def __repr__(self):
        return f"<CS2Process pid={self.process_id} module_base=0x{self.module_base:x}>" if self.module_base else "<CS2Process not ready>"

# -----------------------------
# Mouse Movement (SendInput) - duplicate kept for file compatibility
# -----------------------------
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
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


class MemoryReader:
    def __init__(self, process_handle):
        self.process_handle = process_handle

    def read(self, address, t="int"):
        size_map = {"int": 4, "long": 8, "float": 4, "ushort": 2}
        size = size_map.get(t, 4)
        raw = nt_read_memory(self.process_handle, address, size)
        if not raw:
            return 0.0 if t == "float" else 0
        if t == "int":
            return bytes_to_int(raw)
        elif t == "long":
            return bytes_to_int(raw, signed=False)
        elif t == "float":
            return bytes_to_float(raw)
        elif t == "ushort":
            return bytes_to_int(raw, signed=False)
        return 0

    def read_vec3(self, address):
        raw = nt_read_memory(self.process_handle, address, 12)
        if raw:
            return list(bytes_to_vec3(raw))
        return [0.0, 0.0, 0.0]


# -----------------------------
# Weapon Tracking
# -----------------------------
class CS2WeaponTracker:
    INVALID_WEAPON_IDS = {
        41, 42, 59, 80, 500, 505, 506, 507, 508, 509, 512, 514, 515, 516, 519, 520, 522, 523,
        44, 43, 45, 46, 47, 48, 49
    }

    def __init__(self):
        self.cs2process = CS2Process()
        self.cs2process.wait_for_process()
        self.cs2process.get_module_base()
        self.process_handle = self.cs2process.process_handle
        self.client = self.cs2process.module_base
        # Use unified reader here
        self.reader = RPMReader(self.process_handle)

    def read_longlong(self, address):
        return self.reader.read(address, "long")

    def read_int(self, address):
        return self.reader.read(address, "int")

    def get_current_weapon_id(self):
        local_player = self.read_longlong(self.client + Offsets.dwLocalPlayerPawn)
        if not local_player:
            return None
        weapon_ptr = self.read_longlong(local_player + Offsets.m_pClippingWeapon)
        if not weapon_ptr:
            return None
        item_idx_addr = weapon_ptr + Offsets.m_AttributeManager + Offsets.m_Item + Offsets.m_iItemDefinitionIndex
        return self.reader.read(item_idx_addr, "ushort")

    def is_weapon_valid_for_aim(self):
        weapon_id = self.get_current_weapon_id()
        if weapon_id is None:
            return True
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
        # Use unified reader
        self.reader = RPMReader(self.process_handle)
        self.local_player_controller = self.base + self.o.dwLocalPlayerController  # cached address

        self.bone_indices = {"head": 6, "chest": 18}
        self.left_down = False
        self.shots_fired = 0
        self.last_punch = (0.0, 0.0)
        self.target_id = None
        self.last_target_lost_time = 0
        self.aim_start_time = None
        self.last_aim_angle = None
        self.lock = threading.Lock()

        # continuous raw mouse recording buffer (stores recent raw dx,dy samples)
        self.mouse_buffer = deque(maxlen=1000)  # store recent deltas
        self.raw_recordings_dirty = False

        # track previous aim key state to detect press/release edges
        self.prev_aim_state = False

        # track previous target id and a short grace period to avoid phantom RCS after switching targets
        self.prev_target_id = None
        self.rcs_grace_until = 0.0
        # --- Visibility Checker ---
        self.vis_checker = None
        if getattr(self.cfg, "visibility_aim_enabled", False):
            try:
                import vischeck
                from Process.config import Config
                map_file = getattr(Config, "visibility_map_file", "de_mirage.opt")
                self.vis_checker = vischeck.VisCheck(map_file)
                print(f"[VisCheck] Loaded {map_file} for Aimbot visibility checking")
            except Exception as e:
                print(f"[VisCheck Error] Failed to load map file: {e}")
                self.vis_checker = None




        self.weapon_tracker = CS2WeaponTracker()  # already uses CS2Process internally

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

        self._isnan = math.isnan
        self._hypot = math.hypot
        self._atan2 = math.atan2
        self._degrees = math.degrees

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
        self.learning_data = {}
        if not os.path.exists(self.cfg.learn_dir):
            os.makedirs(self.cfg.learn_dir)

        weapon_id = self.weapon_tracker.get_current_weapon_id()
        if not weapon_id:
            return

        filepath = os.path.join(self.cfg.learn_dir, f"{weapon_id}.json")
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            # existing format: keys are "pitch,yaw" -> list of tuples
            self.learning_data = {
                tuple(map(float, k.split(','))): deque([tuple(x) for x in v], maxlen=50)
                for k, v in data.items()
            }
        except (FileNotFoundError, json.JSONDecodeError):
            self.learning_data = {}

    def save_learning(self):
        if not self.cfg.enable_learning:
            return

        weapon_id = self.weapon_tracker.get_current_weapon_id()
        if not weapon_id:
            return

        filepath = os.path.join(self.cfg.learn_dir, f"{weapon_id}.json")
        try:
            with self.lock, open(filepath, "w") as f:
                data = {f"{k[0]},{k[1]}": list(v) for k, v in self.learning_data.items()}
                json.dump(data, f)
        except Exception as e:
            print(f"[!] Failed saving learning data for weapon {weapon_id}: {e}")

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
        return (dp * dp + dy * dy) <= (self.cfg.FOV * self.cfg.FOV)

    @staticmethod
    def lerp(a, b, t):
        return a + (b - a) * t

    def clamp_angle_diff(self, current, target, max_delta=MAX_DELTA_ANGLE):
        d = self.angle_diff(target, current)
        if abs(d) > max_delta:
            d = max_delta if d > 0 else -max_delta
        return current + d

    def on_click(self, x, y, btn, pressed):
        if btn == mouse.Button.left:
            self.left_down = pressed
            self.aim_start_time = time.perf_counter() if pressed else None
            if not pressed:
                self.shots_fired = 0
                self.last_punch = (0.0, 0.0)
                self.last_aim_angle = None

    def update_learning(self, key, dp, dy, alpha=0.15):
        with self.lock:
            if key not in self.learning_data:
                self.learning_data[key] = deque(maxlen=50)
            if self.learning_data[key]:
                last_dp, last_dy = self.learning_data[key][-1]
                dp = (1 - alpha) * last_dp + alpha * dp
                dy = (1 - alpha) * last_dy + alpha * dy
            self.learning_data[key].append((dp, dy))
            self.learning_dirty = True

    def get_learned_correction(self, key):
        if not self.cfg.enable_learning:
            return 0.0, 0.0
        corrections = self.learning_data.get(key)
        if not corrections:
            return 0.0, 0.0
        dp_avg = sum(x[0] for x in corrections) / len(corrections)
        dy_avg = sum(x[1] for x in corrections) / len(corrections)
        return dp_avg, dy_avg

    def quantize_angle(self, pitch, yaw, shots_fired, step=1.0):
        pitch_q = round(pitch / step) * step
        yaw_q = round(yaw / step) * step
        sf_bin = shots_fired
        return (pitch_q, yaw_q, sf_bin)

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
    # Mouse recorder thread
    # -----------------------------
    
    def is_target_visible(self, local_pos, target_pos):
        if not getattr(self.cfg, "visibility_aim_enabled", False):
            return True
        if not self.vis_checker:
            return True
        if not local_pos or not target_pos:
            return False
            
        # Quick sync with ESP map if needed
        try:
            esp_map_path = getattr(self.cfg, 'visibility_map_path', '')
            if esp_map_path and os.path.exists(esp_map_path):
                if not hasattr(self.vis_checker, 'get_current_map') or self.vis_checker.get_current_map() != esp_map_path:
                    if hasattr(self.vis_checker, 'load_map'):
                        self.vis_checker.load_map(esp_map_path)
        except:
            pass
            
        eye_offset = 64.0
        local_eye = (local_pos[0], local_pos[1], local_pos[2] + eye_offset)
        target_eye = (target_pos[0], target_pos[1], target_pos[2] + eye_offset)
        try:
            return self.vis_checker.is_visible(local_eye, target_eye)
        except Exception:
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

    
    def reset_recoil(self):
        """Reset recoil state when switching targets or when target dies."""
        self.last_punch = (0.0, 0.0)
        self.shots_fired = 0
        self.last_aim_angle = None

    def run(self):
        from ctypes import windll
        GetAsyncKeyState = windll.user32.GetAsyncKeyState

        prev_weapon_id = None
        max_fps = 60
        frame_time = 1.0 / max_fps

        entity_cache = {}
        cache_refresh_rate = 0.2  # seconds
        last_cache_time = 0

        def normalize_angle_delta(delta):
            while delta > 180:
                delta -= 360
            while delta < -180:
                delta += 360
            return delta

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

            try:
                aim_vk = get_vk_code(self.cfg.aim_key)
                if aim_vk is None or not self.is_cs2_focused():
                    time.sleep(0.1)
                    continue

                # read current aim key state (edge-detection)
                curr_aim_state = (GetAsyncKeyState(aim_vk) & 0x8000) != 0

                # handle press edge
                if curr_aim_state and not self.prev_aim_state:
                    self.aim_start_time = time.perf_counter()
                    self.reset_recoil()

                # handle release edge
                if not curr_aim_state and self.prev_aim_state:
                    self.reset_recoil()
                    self.aim_start_time = None

                self.prev_aim_state = curr_aim_state
                self.left_down = curr_aim_state

                if not self.cfg.enabled:
                    time.sleep(0.01)
                    continue

                base = self.base
                o = self.o
                pawn = self.read(base + o.dwLocalPlayerPawn, "long")
                if not pawn:
                    continue

                weapon_id = self.weapon_tracker.get_current_weapon_id()
                if weapon_id != prev_weapon_id:
                    self.load_learning()
                    prev_weapon_id = weapon_id

                health = self.read(pawn + o.m_iHealth)
                if health <= 0:
                    continue

                if not self.weapon_tracker.is_weapon_valid_for_aim():
                    continue

                ctrl = self.read(base + o.dwLocalPlayerController, "long")
                my_team = self.read(pawn + o.m_iTeamNum)
                my_pos = self.read_vec3(pawn + o.m_vOldOrigin)
                pitch = self.read(base + o.dwViewAngles, "float")
                yaw = self.read(base + o.dwViewAngles + 4, "float")
                recoil_pitch = self.read(pawn + o.m_aimPunchAngle, "float")
                recoil_yaw = self.read(pawn + o.m_aimPunchAngle + 4, "float")
                entity_list = self.read(base + o.dwEntityList, "long")
                if not entity_list:
                    continue

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

                target, target_pos = None, None

                if self.target_id in entity_cache:
                    _, t_pawn = entity_cache[self.target_id]
                    bone_idx = self.get_current_bone_index(t_pawn, my_pos, pitch, yaw, frame_time=frame_time)
                    pos = self.read_bone_pos(t_pawn, bone_idx) or self.read_vec3(t_pawn + o.m_vOldOrigin)
                    vel = self.read_vec3(t_pawn + o.m_vecVelocity) if self.cfg.enable_velocity_prediction else [0, 0, 0]
                    predicted = [pos[i] + vel[i] * frame_time * getattr(self.cfg, "velocity_prediction_factor", 1.0) for i in range(3)]
                    predicted[2] -= self.cfg.downward_offset
                    tp, ty = self.calc_angle(my_pos, predicted)
                    if any(map(math.isnan, (tp, ty))) or not self.in_fov(pitch, yaw, tp, ty):
                        self.target_id = None
                    elif not self.is_target_visible(my_pos, predicted):
                        self.target_id = None
                    else:
                        target, target_pos = t_pawn, predicted

                if target is None:
                    min_dist = float("inf")
                    for i, (_, pawn_ent) in entity_cache.items():
                        bone_idx = self.get_current_bone_index(pawn_ent, my_pos, pitch, yaw, frame_time=frame_time)
                        pos = self.read_bone_pos(pawn_ent, bone_idx) or self.read_vec3(pawn_ent + o.m_vOldOrigin)
                        vel = self.read_vec3(pawn_ent + o.m_vecVelocity) if self.cfg.enable_velocity_prediction else [0, 0, 0]
                        predicted = [pos[j] + vel[j] * frame_time * getattr(self.cfg, "velocity_prediction_factor", 1.0) for j in range(3)]
                        predicted[2] -= self.cfg.downward_offset
                        tp, ty = self.calc_angle(my_pos, predicted)
                        if any(map(math.isnan, (tp, ty))) or not self.in_fov(pitch, yaw, tp, ty):
                            continue
                        if not self.is_target_visible(my_pos, predicted):
                            continue
                        dist = squared_distance(my_pos, predicted)
                        if dist < min_dist:
                            min_dist = dist
                            target, target_pos, self.target_id = pawn_ent, predicted, i

                # simplified recoil reset logic
                if self.target_id != self.prev_target_id:
                    self.reset_recoil()
                if target and self.read(target + self.o.m_iHealth) <= 0:
                    self.reset_recoil()
                self.prev_target_id = self.target_id

                mouse_dx, mouse_dy = 0, 0
                if self.left_down and target and target_pos:
                    self.shots_fired += 1
                    if self.aim_start_time and time.time() - self.aim_start_time < self.cfg.aim_start_delay:
                        continue

                    tp, ty = self.calc_angle(my_pos, target_pos)
                    if abs(self.angle_diff(ty, yaw)) > 90:
                        continue

                    # --- Improved RCS ---
                    scale = self.cfg.rcs_scale * min(self.shots_fired / 2, 1.0)

                    # compute compensated angles
                    comp_pitch = tp - recoil_pitch * scale
                    comp_yaw   = ty - recoil_yaw * scale

                    # clamp delta to avoid sudden jumps
                    comp_pitch = self.clamp_angle_diff(pitch, comp_pitch, max_delta=5.0)
                    comp_yaw   = self.clamp_angle_diff(yaw, comp_yaw,   max_delta=5.0)

                    # get learned + human correction
                    key = self.quantize_angle(comp_pitch, comp_yaw, self.shots_fired)
                    dp, dy = self.get_learned_correction(key)

                    if getattr(self.cfg, 'enable_mouse_recording', True):
                        human_dp, human_dy = self.sample_recent_human_correction(sample_count=8)
                        if abs(human_dp) < 2.0 and abs(human_dy) < 2.0:  # reject outliers
                            blend = getattr(self.cfg, 'human_blend', 0.35)
                            dp = (1.0 - blend) * dp + blend * human_dp
                            dy = (1.0 - blend) * dy + blend * human_dy

                    comp_pitch += dp
                    comp_yaw   += dy

                    # adaptive smoothing (faster settle with more bullets fired)
                    dyn_smooth = self.cfg.smooth_base + (self.shots_fired * 0.002)
                    dyn_smooth = min(dyn_smooth, 0.25)
                    smooth = max(0.01, dyn_smooth)

                    # final interpolation
                    sp = self.lerp(pitch, comp_pitch, smooth)
                    sy = self.lerp(yaw, comp_yaw, smooth)
                    sp, sy = self.normalize(sp, sy)

                    # low-pass filter small deltas
                    delta_pitch = (sp - pitch) * 0.9
                    delta_yaw   = (sy - yaw) * 0.9

                    # convert to mouse movement
                    mouse_dx = int(-delta_yaw / self.cfg.sensitivity)
                    mouse_dy = int(-delta_pitch / self.cfg.sensitivity) * self.cfg.invert_y

                    # clamp max move
                    mouse_dx = max(min(mouse_dx, self.cfg.max_mouse_move), -self.cfg.max_mouse_move)
                    mouse_dy = max(min(mouse_dy, self.cfg.max_mouse_move), -self.cfg.max_mouse_move)

                    self.last_aim_angle = (sp, sy)
                else:
                    self.reset_recoil()


                if mouse_dx != 0 or mouse_dy != 0:
                    move_mouse(mouse_dx, mouse_dy)

            except Exception as e:
                print(f"[!] AimbotRCS error: {e}")
                time.sleep(0.3)

            elapsed = time.perf_counter() - start_time
            sleep_time = max(0.0, frame_time - elapsed)
            time.sleep(sleep_time)

        if self.cfg.enable_learning:
            self.save_learning()
        if getattr(self.cfg, 'enable_mouse_recording', True):
            self.save_raw_recordings()
        print("[AimbotRCS] Stopped.")


def start_aim_rcs(cfg):
    AimbotRCS(cfg).run()