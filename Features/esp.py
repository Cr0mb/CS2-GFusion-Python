import math
import struct
import time
import ctypes
from ctypes import wintypes, windll, byref, c_float, c_size_t

import win32api
import win32con
import win32gui
import win32ui

from Process.offsets import Offsets
from Process.config import Config


# === Weapon ID to Name Mapping ===
WEAPON_NAMES = {
    1: "Deagle", 2: "Dualies", 3: "5-7", 4: "Glock", 7: "AK", 8: "AUG", 9: "AWP",
    10: "FAMAS", 11: "G3SG1", 14: "M249", 16: "M4A4", 17: "MAC-10", 19: "P90", 23: "MP5",
    24: "UMP", 25: "XM1014", 26: "Bizon", 27: "MAG-7", 28: "Negev", 29: "Sawed-Off", 30: "Tec-9",
    31: "Taser", 32: "P2000", 33: "MP7", 34: "MP9", 35: "Nova", 36: "P250", 38: "SCAR", 39: "SG553",
    40: "SSG08", 42: "Knife", 43: "Galil", 44: "HE", 45: "Smoke", 46: "Molotov", 47: "Decoy",
    48: "Incendiary", 49: "C4", 59: "Knife", 60: "M4A1-S", 61: "USP-S", 63: "CZ", 64: "R8"
}

PROCESS_ALL_ACCESS = 0x1F0FFF


class Vec3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]

class Grenade:
    def __init__(self, position, velocity, gravity=800.0):
        self.position = position
        self.velocity = velocity
        self.gravity = gravity
        self.path = []

    def simulate(self, steps=150, interval=0.015):
        pos = Vec3(self.position.x, self.position.y, self.position.z)
        vel = Vec3(self.velocity.x, self.velocity.y, self.velocity.z)

        for _ in range(steps):
            # Save the current position
            self.path.append(Vec3(pos.x, pos.y, pos.z))

            # Apply gravity
            vel.z -= self.gravity * interval

            # Update position
            pos.x += vel.x * interval
            pos.y += vel.y * interval
            pos.z += vel.z * interval

            # Stop if grenade hits the ground (basic check)
            if pos.z < 0:
                break

def estimate_grenade_velocity(view_angle, throw_strength=1.3, base_velocity=550.0):
    pitch, yaw = math.radians(view_angle[0]), math.radians(view_angle[1])
    velocity = base_velocity * throw_strength

    out = Vec3(
        math.cos(pitch) * math.cos(yaw),
        math.cos(pitch) * math.sin(yaw),
        -math.sin(pitch)
    )

    out.x *= velocity
    out.y *= velocity
    out.z *= velocity

    return out


# --- Memory Reading Utilities ---

def read_bytes(handle, addr, size):
    if not addr or addr > 0x7FFFFFFFFFFF:
        return b'\x00' * size
    buf = ctypes.create_string_buffer(size)
    windll.kernel32.ReadProcessMemory(handle, ctypes.c_void_p(addr), buf, size, None)
    return buf.raw

def unpack(fmt, data): return struct.unpack(fmt, data)[0]

def read_int(handle, addr): return unpack("i", read_bytes(handle, addr, 4))
def read_float(handle, addr): return unpack("f", read_bytes(handle, addr, 4))
def read_uint64(handle, addr): return unpack("Q", read_bytes(handle, addr, 8))
def safe_read_uint64(handle, addr): return read_uint64(handle, addr) if addr and addr <= 0x7FFFFFFFFFFF else 0
def read_vec3(handle, addr): return Vec3.from_buffer_copy(read_bytes(handle, addr, 12))
def read_matrix(handle, addr): return struct.unpack("f" * 16, read_bytes(handle, addr, 64))

WriteProcessMemory = ctypes.windll.kernel32.WriteProcessMemory
WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
WriteProcessMemory.restype = wintypes.BOOL

def write_float(process_handle, address, value):
    float_value = c_float(value)
    bytes_written = c_size_t(0)
    result = WriteProcessMemory(
        process_handle,
        ctypes.c_void_p(address),
        ctypes.byref(float_value),
        ctypes.sizeof(float_value),
        byref(bytes_written)
    )
    if not result or bytes_written.value != ctypes.sizeof(float_value):
        raise ctypes.WinError()
    return True

# --- Screen Projection ---

def world_to_screen(matrix, pos, width, height):
    if pos is None:
        return None

    x = matrix[0] * pos.x + matrix[1] * pos.y + matrix[2] * pos.z + matrix[3]
    y = matrix[4] * pos.x + matrix[5] * pos.y + matrix[6] * pos.z + matrix[7]
    w = matrix[12] * pos.x + matrix[13] * pos.y + matrix[14] * pos.z + matrix[15]

    if w < 0.1:
        return None

    inv_w = 1.0 / w
    return {
        "x": width / 2 + (x * inv_w) * width / 2,
        "y": height / 2 - (y * inv_w) * height / 2
    }

# --- Entity Wrapper ---

class Entity:
    def __init__(self, controller, pawn, handle):
        self.handle, self.controller, self.pawn = handle, controller, pawn

    def read_data(self):
        h, t, p = Offsets.m_iHealth, Offsets.m_iTeamNum, Offsets.m_vOldOrigin
        self.hp = read_int(self.handle, self.pawn + h)
        self.team = read_int(self.handle, self.pawn + t)
        self.pos = read_vec3(self.handle, self.pawn + p)

        scene_node = safe_read_uint64(self.handle, self.pawn + Offsets.m_pGameSceneNode)
        self.bone_base = safe_read_uint64(self.handle, scene_node + Offsets.m_pBoneArray)
        self.head = read_vec3(self.handle, self.bone_base + 6 * 0x20) if self.bone_base else None

        self.name = self.read_name()

        # Get money from CCSPlayerController_InGameMoneyServices
        try:
            money_services = safe_read_uint64(self.handle, self.controller + Offsets.m_pInGameMoneyServices)
            self.money = read_int(self.handle, money_services + Offsets.m_iAccount)
        except:
            self.money = 0


    def read_name(self):
        try:
            raw = read_bytes(self.handle, self.controller + Offsets.m_iszPlayerName, 32)
            return raw.split(b'\x00')[0].decode(errors='ignore')
        except:
            return "Unknown"

    def BonePos(self, index):
        if not hasattr(self, 'bone_base'):
            node = safe_read_uint64(self.handle, self.pawn + Offsets.m_pGameSceneNode)
            self.bone_base = safe_read_uint64(self.handle, node + Offsets.m_pBoneArray)
        return read_vec3(self.handle, self.bone_base + index*0x20) if self.bone_base else None

    def wts(self, matrix, width, height):
        self.feet2d = world_to_screen(matrix, self.pos, width, height)
        self.head2d = world_to_screen(matrix, self.head, width, height)
        return self.feet2d is not None and self.head2d is not None

class SpectatorList:
    def __init__(self, handle, client_base):
        self.handle = handle
        self.client_base = client_base
        self.last_spec_check = 0
        self.cached_spectators = []

    def _safe_read_int64(self, addr):
        return 0 if not addr or addr > 0x7FFFFFFFFFFF else read_uint64(self.handle, addr)

    def _safe_read_int(self, addr):
        return 0 if not addr or addr > 0x7FFFFFFFFFFF else read_int(self.handle, addr)

    def _safe_read_string(self, addr, max_length=32):
        if not addr or addr > 0x7FFFFFFFFFFF:
            return ""
        try:
            raw = read_bytes(self.handle, addr, max_length)
            return raw.split(b'\x00')[0].decode(errors='ignore')
        except:
            return ""

    def _get_entity(self, entity_list, handle):
        # Decode handle into indices and get entity pointer safely
        hi = handle >> 9
        lo = handle & 0x1FF
        entry_addr = entity_list + 0x8 * hi + 0x10
        entry = self._safe_read_int64(entry_addr)
        if not entry:
            return 0
        return self._safe_read_int64(entry + 120 * lo)

    def GetSpectatorsCached(self):
        now = time.time()
        if now - self.last_spec_check > 1:
            self.cached_spectators = self.GetSpectators()
            self.last_spec_check = now
        return self.cached_spectators

    def GetSpectators(self):
        try:
            entity_list = self._safe_read_int64(self.client_base + Offsets.dwEntityList)
            local_controller = self._safe_read_int64(self.client_base + Offsets.dwLocalPlayerController)
            if not local_controller:
                return []

            local_pawn_handle = self._safe_read_int(local_controller + Offsets.m_hPawn) & 0x7FFF
            local_pawn = self._get_entity(entity_list, local_pawn_handle)
            if not local_pawn:
                return []

            spectators = []
            for i in range(1, 65):
                if i == local_controller:
                    continue

                controller = self._get_entity(entity_list, i)
                if not controller or controller == local_controller:
                    continue

                obs_pawn_handle = self._safe_read_int(controller + Offsets.m_hPawn) & 0x7FFF
                observer_pawn = self._get_entity(entity_list, obs_pawn_handle)
                if not observer_pawn:
                    continue

                observer_services = self._safe_read_int64(observer_pawn + Offsets.m_pObserverServices)
                if not observer_services:
                    continue

                target_handle = self._safe_read_int(observer_services + Offsets.m_hObserverTarget) & 0x7FFF
                target_pawn = self._get_entity(entity_list, target_handle)
                if target_pawn == local_pawn:
                    name = self._safe_read_string(controller + Offsets.m_iszPlayerName)
                    if name:
                        spectators.append(name)

            return spectators
        except Exception as e:
            print(f"[Spectator Error] {type(e).__name__}: {e}")
            return []

# --- Entity Collection ---

def get_entities(handle, base):
    local = safe_read_uint64(handle, base + Offsets.dwLocalPlayerController)
    entity_list = safe_read_uint64(handle, base + Offsets.dwEntityList)
    result = []

    for i in range(1, 65):
        try:
            list_entry = entity_list + ((i & 0x7FFF) >> 9) * 8 + 16
            entry = safe_read_uint64(handle, list_entry)
            ctrl = safe_read_uint64(handle, entry + 120 * (i & 0x1FF))
            if not ctrl or ctrl == local:
                continue

            hPawn = safe_read_uint64(handle, ctrl + Offsets.m_hPlayerPawn)
            pawn_entry = safe_read_uint64(handle, entity_list + ((hPawn & 0x7FFF) >> 9) * 8 + 16)
            pawn = safe_read_uint64(handle, pawn_entry + 120 * (hPawn & 0x1FF))
            if not pawn:
                continue

            ent = Entity(ctrl, pawn, handle)
            ent.read_data()
            result.append(ent)
        except:
            continue
    return result

class Overlay:
    BONE_POSITIONS = {
        "head": 6, "chest": 15, "left_hand": 10,
        "right_hand": 2, "left_leg": 23, "right_leg": 26,
    }
    BONE_CONNECTIONS = [
        (0, 2), (2, 4), (4, 5), (5, 6),
        (4, 8), (8, 9), (9, 10),
        (4, 13), (13, 14), (14, 15),
        (0, 22), (22, 23), (23, 24),
        (0, 25), (25, 26), (26, 27)
    ]

    def __init__(self, title="GHax", fps=144):
        self.width, self.height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
        self.fps = fps
        self.font_cache, self.pen_cache, self.brush_cache = {}, {}, {}
        self._last_time = time.perf_counter()
        self.init_window(title)
        self.black_brush = self.get_brush((0, 0, 0))

    def __del__(self):
        for gdi_cache in (self.font_cache, self.pen_cache, self.brush_cache):
            for obj in gdi_cache.values():
                win32gui.DeleteObject(obj)
        for attr in ('buffer', 'memdc', 'hdc_obj'):
            if hasattr(self, attr):
                getattr(self, attr).DeleteDC() if 'dc' in attr else getattr(self, attr).DeleteObject()
        if hasattr(self, 'hdc'):
            win32gui.ReleaseDC(self.hwnd, self.hdc)
        if hasattr(self, 'hwnd'):
            win32gui.DestroyWindow(self.hwnd)

    def get_font(self, size):
        if size not in self.font_cache:
            lf = win32gui.LOGFONT()
            lf.lfHeight, lf.lfWeight, lf.lfFaceName = size, 700, "Segoe UI"
            self.font_cache[size] = win32gui.CreateFontIndirect(lf)
        return self.font_cache[size]

    def get_pen(self, color):
        if color not in self.pen_cache:
            self.pen_cache[color] = win32gui.CreatePen(win32con.PS_SOLID, 1, win32api.RGB(*color))
        return self.pen_cache[color]

    def get_brush(self, color):
        if color not in self.brush_cache:
            self.brush_cache[color] = win32gui.CreateSolidBrush(win32api.RGB(*color))
        return self.brush_cache[color]

    def draw_circle(self, x, y, r, color):
        r *= 0.8
        hdc = self.memdc.GetSafeHdc()
        old_pen = win32gui.SelectObject(hdc, self.get_pen(color))
        old_brush = win32gui.SelectObject(hdc, win32gui.GetStockObject(win32con.NULL_BRUSH))
        win32gui.Ellipse(hdc, int(x-r), int(y-r), int(x+r), int(y+r))
        win32gui.SelectObject(hdc, old_pen)
        win32gui.SelectObject(hdc, old_brush)

    def draw_text(self, text, x, y, color=(255,255,255), size=14, centered=False):
        hdc = self.memdc.GetSafeHdc()
        old_font = win32gui.SelectObject(hdc, self.get_font(size))
        win32gui.SetTextColor(hdc, win32api.RGB(*color))
        win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
        if centered:
            w, h = win32gui.GetTextExtentPoint32(hdc, text)
            x -= w//2; y -= h//2
        self.memdc.TextOut(int(x), int(y), text)
        win32gui.SelectObject(hdc, old_font)

    def draw_box(self, x, y, w, h, color):
        self._draw_shape(win32gui.Rectangle, x, y, x+w, y+h, color)

    def draw_filled_rect(self, x, y, w, h, color):
        win32gui.FillRect(self.memdc.GetSafeHdc(), (int(x), int(y), int(x+w), int(y+h)), self.get_brush(color))

    def draw_line(self, x1, y1, x2, y2, color):
        hdc = self.memdc.GetSafeHdc()
        old_pen = win32gui.SelectObject(hdc, self.get_pen(color))
        win32gui.MoveToEx(hdc, int(x1), int(y1))
        win32gui.LineTo(hdc, int(x2), int(y2))
        win32gui.SelectObject(hdc, old_pen)

    def _draw_shape(self, func, x1, y1, x2, y2, color):
        hdc = self.memdc.GetSafeHdc()
        old_pen = win32gui.SelectObject(hdc, self.get_pen(color))
        old_brush = win32gui.SelectObject(hdc, win32gui.GetStockObject(win32con.NULL_BRUSH))
        func(hdc, int(x1), int(y1), int(x2), int(y2))
        win32gui.SelectObject(hdc, old_pen)
        win32gui.SelectObject(hdc, old_brush)

    def check_and_update_obs_toggle(self):
        from Process.config import Config
        if not hasattr(self, '_last_obs_value'):
            self._last_obs_value = Config.obs_protection_enabled
            self.update_obs_protection()
        elif self._last_obs_value != Config.obs_protection_enabled:
            self._last_obs_value = Config.obs_protection_enabled
            self.update_obs_protection()

    def begin_scene(self):
        from Process.config import Config
        self.update_obs_protection()  # <- Add this line
        elapsed = time.perf_counter() - self._last_time
        if elapsed < 1/self.fps:
            time.sleep(1/self.fps - elapsed)
        self._last_time = time.perf_counter()
        win32gui.FillRect(self.memdc.GetSafeHdc(), (0,0,self.width,self.height), self.black_brush)
        return True


    def end_scene(self):
        self.hdc_obj.BitBlt((0,0), (self.width,self.height), self.memdc, (0,0), win32con.SRCCOPY)

    def update_obs_protection(self):
        from Process.config import Config
        if hasattr(self, 'hwnd'):
            if getattr(Config, "obs_protection_enabled", True):
                windll.user32.SetWindowDisplayAffinity(self.hwnd, 0x11)
            else:
                windll.user32.SetWindowDisplayAffinity(self.hwnd, 0x00)

    def init_window(self, title):
        from Process.config import Config  # ensure config is accessible
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = title
        wc.hInstance = win32api.GetModuleHandle(None)
        class_atom = win32gui.RegisterClass(wc)

        ex_style = win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST | win32con.WS_EX_TOOLWINDOW

        self.hwnd = win32gui.CreateWindowEx(ex_style, class_atom, title,
                                            win32con.WS_POPUP, 0, 0, self.width, self.height,
                                            None, None, wc.hInstance, None)

        self.update_obs_protection()

        win32gui.SetLayeredWindowAttributes(self.hwnd, 0, 0, win32con.LWA_COLORKEY)
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        self.hdc = win32gui.GetDC(self.hwnd)
        self.hdc_obj = win32ui.CreateDCFromHandle(self.hdc)
        self.memdc = self.hdc_obj.CreateCompatibleDC()
        self.buffer = win32ui.CreateBitmap()
        self.buffer.CreateCompatibleBitmap(self.hdc_obj, self.width, self.height)
        self.memdc.SelectObject(self.buffer)


    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def get_module_base(self, pid, module_name):
        TH32CS_SNAPMODULE = 0x00000008
        snapshot = windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)

        class MODULEENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("GlblcntUsage", wintypes.DWORD), ("ProccntUsage", wintypes.DWORD),
                ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)), ("modBaseSize", wintypes.DWORD),
                ("hModule", wintypes.HMODULE), ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260)
            ]

        me32 = MODULEENTRY32()
        me32.dwSize = ctypes.sizeof(MODULEENTRY32)

        base = None
        if windll.kernel32.Module32First(snapshot, byref(me32)):
            while True:
                if me32.szModule.decode() == module_name:
                    base = ctypes.cast(me32.modBaseAddr, ctypes.c_void_p).value
                    break
                if not windll.kernel32.Module32Next(snapshot, byref(me32)):
                    break
        windll.kernel32.CloseHandle(snapshot)
        return base


def RenderBoneESP(overlay, entity, matrix):
    skeleton_enabled = getattr(Config, "skeleton_esp_enabled", False)
    bone_dot_enabled = getattr(Config, "bone_dot_esp_enabled", False)
    if not (skeleton_enabled or bone_dot_enabled):
        return

    color_bone = getattr(Config, "color_bone", (255, 255, 255))
    bone_dot_size = getattr(Config, "bone_dot_size", 6)
    bone_dot_color = getattr(Config, "bone_dot_color", (255, 0, 255))
    bone_dot_shape = getattr(Config, "bone_dot_shape", "circle").lower()

    needed_bones = set()
    if skeleton_enabled:
        needed_bones.update(b for conn in overlay.BONE_CONNECTIONS for b in conn)
    if bone_dot_enabled:
        needed_bones.update(overlay.BONE_POSITIONS.values())

    bone_screens = {}
    for bone in needed_bones:
        pos = entity.BonePos(bone)
        if pos is None:
            bone_screens[bone] = None
            continue
        screen = world_to_screen(matrix, pos, overlay.width, overlay.height)
        bone_screens[bone] = screen if screen and "x" in screen and "y" in screen else None

    if skeleton_enabled:
        for start, end in overlay.BONE_CONNECTIONS:
            a, b = bone_screens.get(start), bone_screens.get(end)
            if not (a and b):
                continue
            overlay.draw_line(a["x"], a["y"], b["x"], b["y"], color_bone)

    if bone_dot_enabled:
        for bone in overlay.BONE_POSITIONS.values():
            screen = bone_screens.get(bone)
            if not screen:
                continue
            x, y = screen["x"], screen["y"]
            if bone_dot_shape == "circle":
                overlay.draw_circle(x, y, bone_dot_size, bone_dot_color)
            else:  # square or fallback
                s = bone_dot_size
                overlay.draw_box(x - s, y - s, s * 2, s * 2, bone_dot_color)

class BombStatus:
    def __init__(self, handle, base):
        self.handle = handle
        self.base = base
        self.offsets = Offsets()
        self.bomb_plant_time = 0
        self.bomb_defuse_time = 0

    def read_bomb(self):
        try:
            c4_ptr = read_uint64(self.handle, self.base + self.offsets.dwPlantedC4)
            planted_flag = read_bytes(self.handle, self.base + self.offsets.dwPlantedC4 - 0x8, 1)[0]
            if not planted_flag:
                self.bomb_plant_time = 0
                self.bomb_defuse_time = 0
                return None

            if self.bomb_plant_time == 0:
                self.bomb_plant_time = time.time()

            c4class = read_uint64(self.handle, c4_ptr)
            node = read_uint64(self.handle, c4class + self.offsets.m_pGameSceneNode)
            pos = read_vec3(self.handle, node + self.offsets.m_vecAbsOrigin)

            time_remaining = read_float(self.handle, c4class + self.offsets.m_flTimerLength) - (time.time() - self.bomb_plant_time)
            time_remaining = max(0, time_remaining)

            defusing = read_bytes(self.handle, c4class + self.offsets.m_bBeingDefused, 1)[0]

            if defusing:
                if self.bomb_defuse_time == 0:
                    self.bomb_defuse_time = time.time()
                defuse_time = read_float(self.handle, c4class + self.offsets.m_flDefuseLength) - (time.time() - self.bomb_defuse_time)
                defuse_time = max(0, defuse_time)
            else:
                self.bomb_defuse_time = 0
                defuse_time = None

            return {
                "position": pos,
                "time_remaining": round(time_remaining, 1),
                "defuse_time": round(defuse_time, 1) if defuse_time is not None else None
            }

        except Exception as e:
            print(f"[BombStatus] Error: {e}")
            return None

spectator_list_pos = [20, 300]  # initial x,y position on screen
spectator_list_dragging = False
spectator_list_drag_offset = [0, 0]


watermark_pos = [20, 20]
watermark_dragging = False
watermark_drag_offset = [0, 0]

def calculate_speed(vel):
    return math.sqrt(vel['x']**2 + vel['y']**2 + vel['z']**2)

def is_in_game(handle, base):
    pawn = safe_read_uint64(handle, base + Offsets.dwLocalPlayerPawn)
    return pawn != 0

entity_traces = {}  # {entity_id: [Vec3, Vec3, ...]}

local_info_box_pos = [100, 400]
local_info_drag_offset = [0, 0]
local_info_dragging = False

def main():
    hwnd = windll.user32.FindWindowW(None, "Counter-Strike 2")
    if not hwnd:
        return print("[!] CS2 not running.")

    pid = wintypes.DWORD()
    windll.user32.GetWindowThreadProcessId(hwnd, byref(pid))
    handle = windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid.value)

    overlay = Overlay("CS2 Box ESP")
    base = overlay.get_module_base(pid.value, "client.dll")
    spectator_list = SpectatorList(handle, base)
    bomb_status = BombStatus(handle, base)

    # === Drawing Helpers ===

    def draw_crosshair(overlay, size=6, color=(255, 255, 255)):
        cx, cy = overlay.width // 2, overlay.height // 2
        overlay.draw_line(cx - size, cy, cx + size, cy, color)
        overlay.draw_line(cx, cy - size, cx, cy + size, color)

    def draw_aimbot_fov(overlay, fov_degrees, game_fov=90.0, fudge=1.6):
        cx, cy = overlay.width // 2, overlay.height // 2
        radius = int((math.tan(math.radians(fov_degrees / 2)) / math.tan(math.radians(game_fov / 2))) * (overlay.width / 2) * fudge)
        color = getattr(Config, "fov_overlay_color", (0, 255, 0))
        overlay.draw_circle(cx, cy, radius, color)

    def draw_health_bar(ent, x, y, h):
        hp_ratio = max(min(ent.hp / 100, 1), 0)
        bar_h = h * hp_ratio
        color = (0, 255, 0) if hp_ratio > 0.66 else (255, 255, 0) if hp_ratio > 0.33 else (255, 0, 0)
        overlay.draw_box(x - 6, y + h - bar_h - 1, 5, bar_h + 2, (0, 0, 0))
        overlay.draw_filled_rect(x - 5, y + h - bar_h, 3, bar_h, color)

    def draw_armor_bar(ent, x, y, h):
        armor = read_int(handle, ent.pawn + Offsets.m_ArmorValue)
        if armor <= 0: return
        bar_h = h * (armor / 100)
        overlay.draw_box(x - 13, y + h - bar_h - 1, 5, bar_h + 2, (0, 0, 0))
        overlay.draw_filled_rect(x - 12, y + h - bar_h, 3, bar_h, (173, 216, 230))

    def get_local_player():
        pawn_ptr = safe_read_uint64(handle, base + Offsets.dwLocalPlayerPawn)
        return read_vec3(handle, pawn_ptr + Offsets.m_vOldOrigin) if pawn_ptr else None

    # === Draggable UI Elements ===

    def handle_dragging(dragging, pos, offset, box_width, box_height):
        mx, my = win32gui.ScreenToClient(hwnd, win32api.GetCursorPos())
        left_down = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000

        if dragging:
            if not left_down:
                dragging = False
            else:
                pos[0] = mx - offset[0]
                pos[1] = my - offset[1]
        else:
            px, py = pos
            if left_down and px <= mx <= px + box_width and py <= my <= py + box_height:
                dragging = True
                offset[0] = mx - px
                offset[1] = my - py

        return dragging, offset



    def handle_spectator_list_drag():
        global spectator_list_dragging, spectator_list_drag_offset
        box_width = 180
        box_height = 24  # optional, for future use
        spectator_list_dragging, spectator_list_drag_offset = handle_dragging(
            spectator_list_dragging, spectator_list_pos, spectator_list_drag_offset, box_width, box_height
        )

    def handle_watermark_drag():
        global watermark_dragging, watermark_drag_offset
        box_width = 140
        watermark_dragging, watermark_drag_offset = handle_dragging(
            watermark_dragging, watermark_pos, watermark_drag_offset, box_width, 24
        )

    def handle_local_info_drag():
        global local_info_dragging, local_info_drag_offset
        box_width = 240
        local_info_dragging, local_info_drag_offset = handle_dragging(
            local_info_dragging, local_info_box_pos, local_info_drag_offset, box_width, 24
        )



    while overlay.begin_scene():
        try:
            msg = wintypes.MSG()
            while windll.user32.PeekMessageW(byref(msg), 0, 0, 0, win32con.PM_REMOVE):
                windll.user32.TranslateMessage(byref(msg))
                windll.user32.DispatchMessageW(byref(msg))

            if not is_in_game(handle, base):
                overlay.end_scene()
                win32api.Sleep(1)
                continue

            # Cache all config flags once
            cfg = Config
            flags = {
                "head_esp_enabled": getattr(cfg, "head_esp_enabled", False),
                "head_esp_shape": getattr(cfg, "head_esp_shape", "circle").lower(),
                "box_esp_enabled": getattr(cfg, "show_box_esp", False),
                "name_esp_enabled": getattr(cfg, "name_esp_enabled", True),
                "skeleton_esp_enabled": getattr(cfg, "skeleton_esp_enabled", False),
                "healthbar_enabled": getattr(cfg, "healthbar_enabled", False),
                "armorbar_enabled": getattr(cfg, "armorbar_enabled", False),
                "health_esp_enabled": getattr(cfg, "health_esp_enabled", False),
                "armor_esp_enabled": getattr(cfg, "armor_esp_enabled", False),
                "distance_esp_enabled": getattr(cfg, "distance_esp_enabled", False),
                "flash_esp_enabled": getattr(cfg, "flash_esp_enabled", False),
                "scope_esp_enabled": getattr(cfg, "scope_esp_enabled", False),
                "spectator_list_enabled": getattr(cfg, "spectator_list_enabled", True),
                "watermark_enabled": getattr(cfg, "watermark_enabled", True),
                "bone_esp_enabled": getattr(cfg, "bone_dot_esp_enabled", True),
                "bone_esp_shape": getattr(cfg, "bone_dot_shape", "circle"),
                "bone_esp_size": getattr(cfg, "bone_dot_size", 6),
                "bone_esp_color": getattr(cfg, "bone_dot_color", (255, 0, 255)),
                "noflash_enabled": getattr(cfg, "noflash_enabled", False),
                "grenade_prediction_enabled": getattr(cfg, "grenade_prediction_enabled", True),
                "fov_circle_enabled": getattr(cfg, "fov_circle_enabled", True),
                "draw_crosshair_enabled": getattr(cfg, "draw_crosshair_enabled", True),
                "esp_show_enemies_only": getattr(cfg, "esp_show_enemies_only", True),
                "esp_show_team_only": getattr(cfg, "esp_show_team_only", False),
                "trace_esp_enabled": getattr(cfg, "trace_esp_enabled", True),
                "trace_esp_max_points": getattr(cfg, "trace_esp_max_points", 150),
                "velocity_esp": getattr(cfg, "velocity_esp", False),
                "speed_esp": getattr(cfg, "speed_esp", False),
                "velocity_esp_text": getattr(cfg, "velocity_esp_text", False),
                "weapon_esp_enabled": getattr(cfg, "weapon_esp_enabled", True),
                "line_esp_enabled": getattr(cfg, "line_esp_enabled", False),
                "line_esp_position": getattr(cfg, "line_esp_position", "bottom").lower(),
                "coordinates_esp_enabled": getattr(cfg, "coordinates_esp_enabled", True),
                "bomb_esp_enabled": getattr(cfg, "bomb_esp_enabled", False),
                "color_name": getattr(cfg, "color_name", (255, 255, 255)),
                "color_head": getattr(cfg, "color_head", (255, 0, 0)),
                "color_box_t": getattr(cfg, "color_box_t", (255, 0, 0)),
                "color_box_ct": getattr(cfg, "color_box_ct", (0, 0, 255)),
                "color_weapon_text": getattr(cfg, "color_weapon_text", (255, 255, 255)),
                "color_line": getattr(cfg, "color_line", (255, 255, 255)),
                "color_hp_text": getattr(cfg, "color_hp_text", (0, 255, 0)),
                "color_armor_text": getattr(cfg, "color_armor_text", (0, 0, 255)),
                "color_distance": getattr(cfg, "color_distance", (255, 255, 255)),
                "color_flash_scope": getattr(cfg, "color_flash_scope", (255, 255, 255)),
                "color_spectators": getattr(cfg, "color_spectators", (180, 180, 180)),
                "velocity_esp_color": getattr(cfg, "velocity_esp_color", (255, 255, 255)),
                "velocity_text_color": getattr(cfg, "velocity_text_color", (255, 255, 255)),
                "speed_esp_color": getattr(cfg, "speed_esp_color", (255, 255, 255)),
                "crosshair_size": getattr(cfg, "crosshair_size", 6),
                "crosshair_color": getattr(cfg, "crosshair_color", (255, 255, 255)),
                "FOV": getattr(cfg, "FOV", 5.0),
                "show_local_info_box": getattr(cfg, "show_local_info_box", True),
                "color_local_box_background": getattr(cfg, "color_local_box_background", (30, 30, 30)),
                "color_local_box_border": getattr(cfg, "color_local_box_border", (100, 100, 100)),
                "color_local_velocity_text": getattr(cfg, "color_local_velocity_text", (255, 255, 255)),
                "color_local_speed_text": getattr(cfg, "color_local_speed_text", (180, 255, 180)),
                "color_local_coords_text": getattr(cfg, "color_local_coords_text", (200, 200, 255)),
                "money_esp_enabled": getattr(cfg, "money_esp_enabled", True),
                "money_esp_text": getattr(cfg, "money_esp_text", True),
                "color_money_text": getattr(cfg, "color_money_text", (0, 255, 255)),
            }

            matrix = read_matrix(handle, base + Offsets.dwViewMatrix)
            local_pos = get_local_player()

            if flags["watermark_enabled"]:
                handle_watermark_drag()
                wm_x, wm_y = watermark_pos
                wm_w, wm_h = 140, 36
                overlay.draw_filled_rect(wm_x, wm_y, wm_w, wm_h // 2, (30, 30, 30))
                overlay.draw_filled_rect(wm_x, wm_y + wm_h // 2, wm_w, wm_h // 2, (40, 40, 40))
                overlay.draw_box(wm_x, wm_y, wm_w, wm_h, (70, 120, 255))
                overlay.draw_box(wm_x + 1, wm_y + 1, wm_w - 2, wm_h - 2, (20, 20, 30))
                overlay.draw_text("GFusion", wm_x + wm_w // 2 + 1, wm_y + wm_h // 3 + 2, (10, 10, 30), 18, centered=True)
                overlay.draw_text("GFusion", wm_x + wm_w // 2, wm_y + wm_h // 3, (180, 200, 255), 18, centered=True)
                overlay.draw_text("Made by Cr0mb", wm_x + wm_w // 2, wm_y + (wm_h * 2) // 3, (120, 120, 150), 12, centered=True)
                overlay.draw_filled_rect(wm_x + wm_w // 4, wm_y + wm_h - 8, wm_w // 2, 2, (70, 120, 255))

            if flags.get("show_local_info_box", True) and local_pos:
                handle_local_info_drag()
                box_x, box_y = local_info_box_pos
                box_w, box_h = 240, 72
                velocity = read_vec3(handle, safe_read_uint64(handle, base + Offsets.dwLocalPlayerPawn) + Offsets.m_vecVelocity)
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)

                # Background and border
                overlay.draw_filled_rect(box_x, box_y, box_w, box_h, flags.get("color_local_box_background", (30, 30, 30)))
                overlay.draw_box(box_x, box_y, box_w, box_h, flags.get("color_local_box_border", (100, 100, 100)))
                overlay.draw_filled_rect(box_x, box_y, box_w, 24, (50, 50, 50))
                overlay.draw_text("BHop Info", box_x + box_w // 2, box_y + 4, (200, 200, 255), 16, centered=True)

                # Text lines
                overlay.draw_text(f"Coords: {local_pos.x:.1f}, {local_pos.y:.1f}, {local_pos.z:.1f}",
                                  box_x + 6, box_y + 26, flags["color_local_coords_text"], 14)

                overlay.draw_text(f"Velocity: {velocity.x:.1f}, {velocity.y:.1f}, {velocity.z:.1f}",
                                  box_x + 6, box_y + 42, flags["color_local_velocity_text"], 14)

                overlay.draw_text(f"Speed: {speed:.1f} u/s", box_x + 6, box_y + 58, flags["color_local_speed_text"], 14)

            if flags["noflash_enabled"]:
                try:
                    local_pawn = safe_read_uint64(handle, base + Offsets.dwLocalPlayerPawn)
                    if local_pawn:
                        write_float(handle, local_pawn + Offsets.m_flFlashDuration, 0.0)
                except Exception as e:
                    print(f"[NoFlash Error] {e}")

            if flags["grenade_prediction_enabled"]:
                local_pawn = safe_read_uint64(handle, base + Offsets.dwLocalPlayerPawn)
                if local_pawn:
                    view_angles = [read_float(handle, base + Offsets.dwViewAngles + i * 4) for i in range(2)]
                    origin_pos = read_vec3(handle, local_pawn + Offsets.m_vOldOrigin)
                    origin_pos.z += 64

                    left_click = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000
                    right_click = win32api.GetAsyncKeyState(win32con.VK_RBUTTON) & 0x8000

                    if left_click:
                        vel = estimate_grenade_velocity(view_angles, throw_strength=1.3, base_velocity=1350.0)
                    elif right_click:
                        vel = estimate_grenade_velocity(view_angles, throw_strength=1.3, base_velocity=550.0)
                    else:
                        vel = None

                    if vel:
                        nade = Grenade(origin_pos, vel)
                        nade.simulate()
                        for pos in nade.path:
                            try:
                                screen = world_to_screen(matrix, pos, overlay.width, overlay.height)
                                overlay.draw_circle(screen["x"], screen["y"], 2, (255, 255, 0))
                            except: pass

            if flags["fov_circle_enabled"]:
                draw_aimbot_fov(overlay, flags["FOV"])

            if flags["draw_crosshair_enabled"]:
                draw_crosshair(overlay, size=flags["crosshair_size"], color=flags["crosshair_color"])

            local_team = read_int(handle, safe_read_uint64(handle, base + Offsets.dwLocalPlayerPawn) + Offsets.m_iTeamNum)

            for ent in get_entities(handle, base):
                is_enemy = ent.team != local_team
                is_teammate = ent.team == local_team
                if (flags["esp_show_enemies_only"] and not is_enemy) or (flags["esp_show_team_only"] and not is_teammate):
                    continue
                if ent.hp <= 0 or not ent.wts(matrix, overlay.width, overlay.height):
                    continue

                h = (ent.feet2d["y"] - ent.head2d["y"]) * 1.08
                w = h / 2
                x, y = ent.head2d["x"] - w / 2, ent.head2d["y"] - h * 0.08
                text_x, text_y = x + w + 6, y + 2
                line_spacing, line_index = 16, 0
                font_color = flags["color_name"]
                font_size = max(12, min(12, int(h * 0.14)))

                if flags["money_esp_enabled"]:
                    overlay.draw_text(f"${ent.money}", text_x, text_y + line_spacing * line_index, flags["color_money_text"], font_size)
                    line_index += 1

                if flags["head_esp_enabled"]:
                    radius = int(getattr(cfg, "head_esp_size", int(h * 0.15)))
                    color = flags["color_head"]
                    if flags["head_esp_shape"] == "circle":
                        overlay.draw_circle(ent.head2d["x"], ent.head2d["y"], radius, color)
                    else:
                        side = radius * 2
                        overlay.draw_box(ent.head2d["x"] - radius, ent.head2d["y"] - radius, side, side, color)

                if flags["box_esp_enabled"]:
                    color = flags["color_box_t"] if ent.team == 2 else flags["color_box_ct"]
                    overlay.draw_box(x, y, w, h, color)

                if flags["trace_esp_enabled"]:
                    try:
                        trace_list = entity_traces.setdefault(ent.pawn, [])
                        trace_list.append(Vec3(ent.pos.x, ent.pos.y, ent.pos.z))
                        if len(trace_list) > flags["trace_esp_max_points"]:
                            trace_list.pop(0)

                        screen_points = []
                        for pos in trace_list:
                            try:
                                s = world_to_screen(matrix, pos, overlay.width, overlay.height)
                                screen_points.append((s["x"], s["y"]))
                            except: continue

                        for i in range(1, len(screen_points)):
                            overlay.draw_line(*screen_points[i-1], *screen_points[i], cfg.trace_esp_color)
                    except Exception as e:
                        print(f"[Trace ESP Error] {e}")

                if flags["velocity_esp"] or flags["speed_esp"] or flags["velocity_esp_text"]:
                    try:
                        velocity = read_vec3(handle, ent.pawn + Offsets.m_vecVelocity) or Vec3(0,0,0)
                        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                        start = world_to_screen(matrix, ent.pos, overlay.width, overlay.height)

                        if flags["velocity_esp"]:
                            scale = 0.1
                            end_pos = Vec3(ent.pos.x + velocity.x*scale, ent.pos.y + velocity.y*scale, ent.pos.z + velocity.z*scale)
                            end = world_to_screen(matrix, end_pos, overlay.width, overlay.height)
                            overlay.draw_line(start["x"], start["y"], end["x"], end["y"], cfg.velocity_esp_color)
                            overlay.draw_filled_rect(end["x"] - 2, end["y"] - 2, 4, 4, cfg.velocity_esp_color)

                        if flags["velocity_esp_text"]:
                            overlay.draw_text(f"V: {velocity.x:.1f} {velocity.y:.1f} {velocity.z:.1f}", start["x"], start["y"] - 14, cfg.velocity_text_color, 14, centered=True)

                        if flags["speed_esp"]:
                            overlay.draw_text(f"{int(speed)} u/s", ent.head2d["x"], ent.head2d["y"] - 35, cfg.speed_esp_color, font_size, centered=True)
                    except Exception as e:
                        print(f"[Velocity/Speed ESP Error] {e}")

                if flags["weapon_esp_enabled"]:
                    try:
                        weapon = read_uint64(handle, ent.pawn + Offsets.m_pClippingWeapon)
                        idx = read_int(handle, weapon + Offsets.m_AttributeManager + Offsets.m_Item + Offsets.m_iItemDefinitionIndex)
                        weapon_name = WEAPON_NAMES.get(idx, f"Weapon ID: {idx}")
                        overlay.draw_text(weapon_name, x + w/2, y + h + 4, cfg.color_weapon_text, font_size, centered=True)
                    except Exception as e:
                        print(f"[Weapon ESP Error] {e}")

                if flags["line_esp_enabled"]:
                    start_x = overlay.width // 2
                    start_y = 0 if flags["line_esp_position"] == "top" else overlay.height
                    end_x, end_y = int(x + w/2), int(y if start_y == 0 else y + h)
                    overlay.draw_line(start_x, start_y, end_x, end_y, cfg.color_line)

                if flags["name_esp_enabled"]:
                    overlay.draw_text(ent.name, x + w / 2, y - 16, font_color, font_size, centered=True)

                if flags["coordinates_esp_enabled"]:
                    try:
                        scr = world_to_screen(matrix, ent.pos, overlay.width, overlay.height)
                        txt = f"X: {ent.pos.x:.1f} Y: {ent.pos.y:.1f} Z: {ent.pos.z:.1f}"
                        overlay.draw_text(txt, scr["x"], scr["y"] + 20, getattr(cfg, "coordinates_esp_color", (255,255,255)), 14, centered=True)
                    except Exception as e:
                        print(f"[Coordinates ESP Error] {e}")

                if flags["skeleton_esp_enabled"] or flags["bone_esp_enabled"]:
                    RenderBoneESP(overlay, ent, matrix)

                if flags["healthbar_enabled"]:
                    draw_health_bar(ent, x, y, h)

                if flags["armorbar_enabled"]:
                    draw_armor_bar(ent, x, y, h)

                if flags["health_esp_enabled"]:
                    overlay.draw_text(f"HP: {ent.hp}%", text_x, text_y + line_spacing * line_index, cfg.color_hp_text, font_size)
                    line_index += 1

                if flags["armor_esp_enabled"]:
                    armor = read_int(handle, ent.pawn + Offsets.m_ArmorValue)
                    overlay.draw_text(f"AR: {armor}%", text_x, text_y + line_spacing * line_index, cfg.color_armor_text, font_size)
                    line_index += 1

                if flags["distance_esp_enabled"] and local_pos:
                    dx, dy, dz = local_pos.x - ent.pos.x, local_pos.y - ent.pos.y, local_pos.z - ent.pos.z
                    dist = int((dx*dx + dy*dy + dz*dz)**0.5 / 10)
                    overlay.draw_text(f"{dist}m", text_x, text_y + line_spacing * line_index, cfg.color_distance, font_size)
                    line_index += 1

                if flags["flash_esp_enabled"] or flags["scope_esp_enabled"]:
                    try:
                        flash = read_float(handle, ent.pawn + Offsets.m_flFlashDuration) if flags["flash_esp_enabled"] else 0.0
                        scoped = bool(read_int(handle, ent.pawn + Offsets.m_bIsScoped)) if flags["scope_esp_enabled"] else False
                        status = " | ".join(s for s in ("FLASHED" if flash > 0.1 else "", "SCOPED" if scoped else "") if s)
                        if status:
                            overlay.draw_text(status, text_x, text_y + line_spacing * line_index, cfg.color_flash_scope, font_size)
                            line_index += 1
                    except Exception as e:
                        print(f"[State ESP Error] {e}")

            if flags["bomb_esp_enabled"]:
                bomb_info = bomb_status.read_bomb()
                if bomb_info:
                    try:
                        scr = world_to_screen(matrix, bomb_info["position"], overlay.width, overlay.height)
                        text = f"BOMB {bomb_info['time_remaining']}s"
                        if bomb_info["defuse_time"] is not None:
                            text += f" | DEF {bomb_info['defuse_time']}s"
                            color = (255, 80, 80)
                        else:
                            color = (255, 255, 0)
                        overlay.draw_text(text, scr["x"], scr["y"], color, 14, centered=True)
                    except: pass

            if flags["spectator_list_enabled"]:
                handle_spectator_list_drag()
                spectators = spectator_list.GetSpectatorsCached()
                bx, by = spectator_list_pos
                line_h = 18
                w, h = 180, line_h * (len(spectators) + 1) + 12

                overlay.draw_filled_rect(bx - 6, by - 6, w + 12, h + 12, (20, 20, 20))
                overlay.draw_box(bx - 6, by - 6, w + 12, h + 12, (100, 100, 100))
                overlay.draw_filled_rect(bx - 6, by - 6, w + 12, 24, (60, 60, 60))
                overlay.draw_text("Spectator list", bx + w // 2, by + 4, (200, 200, 255), 16, centered=True)

                for i, name in enumerate(spectators):
                    overlay.draw_text(name, bx, by + 24 + i * line_h, flags["color_spectators"], 14)

        except Exception as e:
            print("[!] ESP Error:", e)

        overlay.end_scene()
        win32api.Sleep(1)

if __name__ == "__main__":
    main()
