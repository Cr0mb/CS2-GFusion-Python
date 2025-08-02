import os
import time
import math
import random
import json
import threading
import ctypes
import struct
import requests
from ctypes import windll, wintypes
from collections import deque

from Process.offsets import Offsets
from Process.config import Config


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
    return VIRTUAL_KEYS.get(key_name.lower(), None)


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_PERMISSIONS = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION

TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008 | 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * wintypes.MAX_PATH)
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
        ("szExePath", ctypes.c_char * wintypes.MAX_PATH)
    ]

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

# === SendInput setup for external mouse movement ===
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
    
class CS2WeaponTracker:
    INVALID_WEAPON_IDS = {
        41, 42, 59, 80, 500, 505, 506, 507, 508, 509, 512, 514, 515, 516, 519, 520, 522, 523,
        44, 43, 45, 46, 47, 48, 49
    }

    def __init__(self):
        self.cs2process = CS2Process()
        self.cs2process.initialize()  # waits and attaches to process, sets module_base
        self.process_handle = self.cs2process.process_handle
        self.client = self.cs2process.module_base

    def read_memory(self, address, size):
        try:
            buffer = (ctypes.c_byte * size)()
            bytesRead = ctypes.c_size_t()
            if not kernel32.ReadProcessMemory(self.process_handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytesRead)):
                return None
            return bytes(buffer)
        except:
            return None

    def read_longlong(self, address):
        data = self.read_memory(address, 8)
        if data is None:
            return 0
        return int.from_bytes(data, byteorder='little')

    def read_int(self, address):
        data = self.read_memory(address, 4)
        if data is None:
            return 0
        return int.from_bytes(data, byteorder='little')

    def get_current_weapon_id(self):
        try:
            time.sleep(random.uniform(0.01, 0.03))
            local_player_ptr = self.read_longlong(self.client + Offsets.dwLocalPlayerPawn)
            if not local_player_ptr:
                return None

            weapon_ptr = self.read_longlong(local_player_ptr + Offsets.m_pClippingWeapon)
            if not weapon_ptr:
                return None

            # Read weapon ID directly as in the first version
            weapon_id = self.read_int(
                weapon_ptr + Offsets.m_AttributeManager + Offsets.m_Item + Offsets.m_iItemDefinitionIndex
            )
            return weapon_id
        except Exception:
            return None

    def is_weapon_valid_for_aim(self):
        weapon_id = self.get_current_weapon_id()
        if weapon_id is None:
            return True  # Unknown weapons are allowed
        return weapon_id not in self.INVALID_WEAPON_IDS

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

        self.weapon_tracker = CS2WeaponTracker()  # already uses CS2Process internally

        self.learning_data = {}
        self.learning_dirty = False

        threading.Thread(target=self.periodic_save, daemon=True).start()

        self._isnan = math.isnan
        self._hypot = math.hypot
        self._atan2 = math.atan2
        self._degrees = math.degrees


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
        while not self.cfg.aim_stop:
            time.sleep(30)
            if self.cfg.enable_learning and self.learning_dirty:
                self.save_learning()
                self.learning_dirty = False

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


    kernel32 = ctypes.windll.kernel32

    def read(self, addr, t="int"):
        # Handle bad input early
        if not isinstance(addr, int) or addr <= 0:
            print(f"[!] Invalid address passed to read(): {addr}")
            return 0.0 if t == "float" else 0

        size = {"int": 4, "long": 8, "float": 4, "ushort": 2}.get(t, 4)
        buffer = (ctypes.c_ubyte * size)()
        bytesRead = ctypes.c_size_t()

        try:
            success = kernel32.ReadProcessMemory(
                self.process_handle,
                ctypes.c_void_p(addr),                # <-- FIXED
                ctypes.byref(buffer),
                size,
                ctypes.byref(bytesRead)
            )
        except Exception as e:
            print(f"[!] ReadProcessMemory threw exception: {e}")
            return 0.0 if t == "float" else 0

        if not success or bytesRead.value != size:
            error_code = kernel32.GetLastError()
            print(f"[!] Failed to read memory at {hex(addr)} (size={size}), Error={error_code}")
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
    
    def get_entity(self, base, idx):
        array_idx = (idx & 0x7FFF) >> 9
        entity_addr = self.read(base + 8 * array_idx + 16, "long")
        if not entity_addr:
            return 0
        ctrl = self.read(entity_addr + 0x78 * (idx & 0x1FF), "long")
        local_ctrl = self.read(self.local_player_controller, "long")  # cached addr
        return ctrl if ctrl and ctrl != local_ctrl else 0

    def read_vec3(self, addr):
        r = self.read
        return [r(addr + i * 4, "float") for i in range(3)]

    def read_weapon_id(self, pawn):
        w = self.read(pawn + self.o.m_pClippingWeapon, "long")
        if not w:
            return 0
        item_idx_addr = w + self.o.m_AttributeManager + self.o.m_Item + self.o.m_iItemDefinitionIndex
        return self.read(item_idx_addr, "ushort")

    def read_bone_pos(self, pawn, idx):
        scene = self.read(pawn + self.o.m_pGameSceneNode, "long")
        if not scene:
            return None
        bones = self.read(scene + self.o.m_pBoneArray, "long")
        if not bones:
            return None
        return self.read_vec3(bones + idx * 32)

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

    @staticmethod
    def add_noise(value, max_noise=0.03):
        return value + random.uniform(-max_noise, max_noise)

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

    def get_current_bone_index(self, pawn=None, my_pos=None, pitch=None, yaw=None):
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
        smoothing = getattr(self.cfg, 'velocity_prediction_factor', 0.1)

        vel = None
        if enable_velocity_prediction:
            vel = read_vec = read(pawn + self.o.m_vecVelocity, "float")  # This needs 3 floats: fix below

        # Read velocity vector fully once outside loop if enabled
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
        
    def run(self):
        from ctypes import windll
        GetAsyncKeyState = windll.user32.GetAsyncKeyState

        prev_weapon_id = None
        sleep_base = 0.005
        sleep_no_target = 0.02  # more sleep when no target

        def normalize_angle_delta(delta):
            while delta > 180:
                delta -= 360
            while delta < -180:
                delta += 360
            return delta

        def squared_distance(a, b):
            return (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2

        def is_valid_target(pawn, my_team):
            if not pawn:
                return False
            health = self.read(pawn + self.o.m_iHealth)
            if health <= 0:
                return False
            life_state = self.read(pawn + self.o.m_lifeState)
            dormant = self.read(pawn + self.o.m_bDormant, "int")
            team = self.read(pawn + self.o.m_iTeamNum)
            return life_state == 256 and not dormant and (self.cfg.DeathMatch or team != my_team)

        while not self.cfg.aim_stop:
            aim_vk = get_vk_code(self.cfg.aim_key)
            if aim_vk is None:
                time.sleep(0.5)
                continue
            try:
            # Poll mouse button
                self.left_down = GetAsyncKeyState(aim_vk) & 0x8000 != 0

                if not self.left_down:
                    self.shots_fired = 0
                    self.last_punch = (0.0, 0.0)
                    self.last_aim_angle = None

                if not self.is_cs2_focused():
                    time.sleep(0.1)
                    continue

                if not self.cfg.enabled:
                    time.sleep(sleep_base)
                    continue

                base = self.base
                o = self.o

                pawn = self.read(base + o.dwLocalPlayerPawn, "long")
                if not pawn:
                    time.sleep(sleep_base)
                    continue

                weapon_id = self.weapon_tracker.get_current_weapon_id()
                if weapon_id != prev_weapon_id:
                    self.load_learning()
                    prev_weapon_id = weapon_id

                health = self.read(pawn + o.m_iHealth)
                if health <= 0:
                    time.sleep(sleep_base)
                    continue

                ctrl = self.read(base + o.dwLocalPlayerController, "long")
                if not self.weapon_tracker.is_weapon_valid_for_aim():
                    self.shots_fired = 0
                    self.last_punch = (0.0, 0.0)
                    time.sleep(sleep_base)
                    continue

                my_team = self.read(pawn + o.m_iTeamNum)
                my_pos = self.read_vec3(pawn + o.m_vOldOrigin)
                view_angles_addr = base + o.dwViewAngles
                pitch = self.read(view_angles_addr, "float")
                yaw = self.read(view_angles_addr + 4, "float")
                recoil_pitch = self.read(pawn + o.m_aimPunchAngle, "float")
                recoil_yaw = self.read(pawn + o.m_aimPunchAngle + 4, "float")
                entity_list = self.read(base + o.dwEntityList, "long")
                if not entity_list:
                    time.sleep(sleep_base)
                    continue

                target = None
                target_pos = None

                if self.target_id is not None:
                    t_ctrl = self.get_entity(entity_list, self.target_id)
                    t_pawn = self.get_entity(entity_list, self.read(t_ctrl + o.m_hPlayerPawn) & 0x7FFF) if t_ctrl else 0
                    if is_valid_target(t_pawn, my_team):
                        bone_index = self.get_current_bone_index(t_pawn, my_pos, pitch, yaw)
                        pos = self.read_bone_pos(t_pawn, bone_index) or self.read_vec3(t_pawn + o.m_vOldOrigin)
                        vel = self.read_vec3(t_pawn + o.m_vecVelocity) if self.cfg.enable_velocity_prediction else [0, 0, 0]
                        predicted = [pos[i] + vel[i] * 0.1 for i in range(3)]
                        predicted[2] -= self.cfg.downward_offset
                        tp, ty = self.calc_angle(my_pos, predicted)
                        if any(map(math.isnan, (tp, ty))) or not self.in_fov(pitch, yaw, tp, ty):
                            self.target_id = None
                            self.last_target_lost_time = time.time()
                        else:
                            target, target_pos = t_pawn, predicted
                    else:
                        self.target_id = None
                        self.last_target_lost_time = time.time()

                if target is None:
                    if self.last_target_lost_time and (time.time() - self.last_target_lost_time) < self.cfg.target_switch_delay:
                        time.sleep(sleep_no_target)
                        continue

                    min_dist_sq = float("inf")
                    for i in range(self.cfg.max_entities):
                        ctrl_ent = self.get_entity(entity_list, i)
                        if not ctrl_ent or ctrl_ent == ctrl:
                            continue
                        pawn_ent = self.get_entity(entity_list, self.read(ctrl_ent + o.m_hPlayerPawn) & 0x7FFF)
                        if not is_valid_target(pawn_ent, my_team):
                            continue
                        bone_index = self.get_current_bone_index(pawn_ent, my_pos, pitch, yaw)
                        pos = self.read_bone_pos(pawn_ent, bone_index) or self.read_vec3(pawn_ent + o.m_vOldOrigin)
                        vel = self.read_vec3(pawn_ent + o.m_vecVelocity) if self.cfg.enable_velocity_prediction else [0, 0, 0]
                        predicted = [pos[i] + vel[i] * 0.1 for i in range(3)]
                        predicted[2] -= self.cfg.downward_offset
                        tp, ty = self.calc_angle(my_pos, predicted)
                        if any(map(math.isnan, (tp, ty))) or not self.in_fov(pitch, yaw, tp, ty):
                            continue
                        dist_sq = squared_distance(my_pos, predicted)
                        if dist_sq < min_dist_sq:
                            min_dist_sq = dist_sq
                            target, target_pos, self.target_id = pawn_ent, predicted, i

                if self.left_down:
                    if self.aim_start_time and time.time() - self.aim_start_time < self.cfg.aim_start_delay:
                        continue

                    self.shots_fired += 1
                    if target and target_pos:
                        tp, ty = self.calc_angle(my_pos, target_pos)
                        if abs(self.angle_diff(ty, yaw)) > 90:
                            continue

                        scale = self.cfg.rcs_scale * min(self.shots_fired / 2, 1.0)
                        if self.cfg.rcs_enabled:
                            compensated_pitch = self.clamp_angle_diff(pitch, tp - recoil_pitch * scale)
                            compensated_yaw = self.clamp_angle_diff(yaw, ty - recoil_yaw * scale)
                        else:
                            compensated_pitch = self.clamp_angle_diff(pitch, tp)
                            compensated_yaw = self.clamp_angle_diff(yaw, ty)

                        if self.cfg.rcs_enabled:
                            smooth = max(0.01, min(self.cfg.rcs_smooth_base + random.uniform(-self.cfg.rcs_smooth_var, self.cfg.rcs_smooth_var), 0.25))
                        else:
                            smooth = max(0.01, min(self.cfg.smooth_base + random.uniform(-self.cfg.smooth_var, self.cfg.smooth_var), 0.25))
                        key = self.quantize_angle(compensated_pitch, compensated_yaw, self.shots_fired)
                        dp, dy = self.get_learned_correction(key)

                        compensated_pitch += dp
                        compensated_yaw += dy

                        interp_pitch = pitch + (compensated_pitch - pitch) * smooth
                        interp_yaw = yaw + (compensated_yaw - yaw) * smooth

                        sp = self.add_noise(interp_pitch, 0.03)
                        sy = self.add_noise(interp_yaw, 0.03)
                        sp, sy = self.normalize(sp, sy)

                        delta_pitch = normalize_angle_delta(sp - pitch)
                        delta_yaw = normalize_angle_delta(sy - yaw)

                        delta_pitch = max(min(delta_pitch, self.cfg.max_delta_angle), -self.cfg.max_delta_angle)
                        delta_yaw = max(min(delta_yaw, self.cfg.max_delta_angle), -self.cfg.max_delta_angle)

                        mouse_dx = int(-delta_yaw / self.cfg.sensitivity)
                        mouse_dy = int(-delta_pitch / self.cfg.sensitivity) * self.cfg.invert_y

                        max_mouse_move = self.cfg.max_mouse_move
                        mouse_dx = max(min(mouse_dx, max_mouse_move), -max_mouse_move)
                        mouse_dy = max(min(mouse_dy, max_mouse_move), -max_mouse_move)

                        move_mouse(mouse_dx, mouse_dy)

                        if self.last_aim_angle:
                            lp, ly = self.last_aim_angle
                            if abs(self.angle_diff(sp, lp)) > 0.002 or abs(self.angle_diff(sy, ly)) > 0.002:
                                dp_learn = max(min(sp - pitch, 1.0), -1.0)
                                dy_learn = max(min(sy - yaw, 1.0), -1.0)
                                if abs(dp_learn) > 0.05 or abs(dy_learn) > 0.05:
                                    self.update_learning(key, dp_learn, dy_learn)

                        self.last_aim_angle = (sp, sy)
                    else:
                        self.last_aim_angle = None
                else:
                    self.shots_fired = 0
                    self.last_aim_angle = None

                time.sleep(sleep_base + random.uniform(0, 0.003))

            except (EOFError, BrokenPipeError):
                break
            except Exception as e:
                print(f"[!] Exception in AimbotRCS: {e}")
                time.sleep(0.3)

        if self.cfg.enable_learning:
            self.save_learning()

        print("[AimbotRCS] Stopped.")

def start_aim_rcs(cfg):
    AimbotRCS(cfg).run()