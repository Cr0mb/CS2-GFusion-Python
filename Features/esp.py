import math
import time

# ---------------------------------------------
# FORCE SAFE GLOBAL IMPORT FOR win32api
# ---------------------------------------------
try:
    import win32api as _win32api
except Exception:
    _win32api = None

# expose it globally under the expected name
win32api = _win32api
del _win32api

# Fail fast: pywin32 is required for ESP overlay renderers.
if win32api is None:
    raise ImportError(
        "pywin32 is required (win32api/win32gui/win32con/win32ui). "
        "Install it with: pip install pywin32"
    )

import win32gui
import win32con
import win32ui
import ctypes
import struct
from ctypes import windll, wintypes, byref, c_float, c_size_t
from ctypes.wintypes import RECT
import sys
import os
import threading
from Process.config import Config
from Process.offsets import Offsets
from Process.memory_interface import MemoryInterface
from Features import worldesp
from Features import radar as radar_module

# Add current directory to path for vischeck.pyd
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import performance optimizer
try:
    from Performance.vischeck_optimizer import AsyncVisCheck, get_global_vischeck, PerformanceMetrics
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False
    print("[Warning] VisCheck optimizer not available")

try:
    import vischeck
    VISCHECK_AVAILABLE = True
    print("[VisCheck] Module loaded successfully")
except ImportError as e:
    VISCHECK_AVAILABLE = False
    print(f"[Warning] VisCheck module import error: {e}")
    print("[Info] Make sure vischeck.pyd is in the main directory and compiled for your Python version")
except Exception as e:
    VISCHECK_AVAILABLE = False
    print(f"[Error] VisCheck module unexpected error: {e}")

# Old:
# PROCESS_PERMISSIONS = 0x0010 | 0x0400  # PROCESS_VM_READ | PROCESS_QUERY_INFORMATION

# New: add VM_OPERATION + VM_WRITE
PROCESS_VM_OPERATION   = 0x0008
PROCESS_VM_READ        = 0x0010
PROCESS_VM_WRITE       = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400

PROCESS_PERMISSIONS = (
    PROCESS_VM_OPERATION |
    PROCESS_VM_READ |
    PROCESS_VM_WRITE |
    PROCESS_QUERY_INFORMATION
)

# Global variables for threaded map loading
map_loading_in_progress = False
map_load_lock = threading.Lock()

# Performance monitoring
performance_metrics = PerformanceMetrics() if OPTIMIZER_AVAILABLE else None
last_performance_update = time.time()
# Global VisCheck instance with optimization
optimized_vischeck = None
if OPTIMIZER_AVAILABLE:
    try:
        optimized_vischeck = get_global_vischeck()
        print("[ESP] VisCheck optimizer initialized successfully")
    except Exception as e:
        print(f"[ESP] VisCheck optimizer failed to initialize: {e}")
        print("[ESP] Falling back to standard VisCheck")
        optimized_vischeck = None

# Map detection offsets (hardcoded)
DW_GAME_TYPES = 1793760  # absolute offset in matchmaking.dll
DW_GAME_TYPES_MAP_NAME = 0x120  # field offset inside GameTypes

# Global variables for map name checking
last_map_check_time = time.time()
current_detected_map = ""



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
# Global memory interface - will be set in main()
_memory_interface = None

def set_memory_interface(memory_interface):
    """Set the global memory interface for this module"""
    global _memory_interface
    _memory_interface = memory_interface

def get_weapon_name_from_entity(handle, weapon_entity):
    """
    - weapon_entity + 0x10 → entity identity
    - identity + 0x20 → pDesignerName (string ptr)
    - deref & read string
    """
    try:
        entity_identity = safe_read_uint64(handle, weapon_entity + 0x10)
        if not entity_identity:
            return ""

        designer_name_ptr = safe_read_uint64(handle, entity_identity + 0x20)
        if not designer_name_ptr:
            return ""

        sBuffer = read_string(handle, designer_name_ptr, 64)
        if not sBuffer:
            return ""

        # Strip "weapon_" prefix if present
        if sBuffer.startswith("weapon_"):
            return sBuffer[7:]
        else:
            return sBuffer  # leave skins, knives, gloves, etc untouched
    except Exception as e:
        print(f"[get_weapon_name_from_entity] Error: {e}")
        return ""

def read_bytes(handle, addr, size):
    """Read bytes using unified memory interface"""
    if _memory_interface:
        return _memory_interface.read_bytes(addr, size)
    
    # Fallback to original implementation
    if not addr or addr > 0x7FFFFFFFFFFF:
        return b"\x00" * size

    buf = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t(0)

    ok = windll.kernel32.ReadProcessMemory(
        handle,
        ctypes.c_void_p(addr),
        buf,
        size,
        ctypes.byref(bytes_read)
    )

    if not ok or bytes_read.value != size:
        return b"\x00" * size

    return buf.raw

def read_string(handle, addr, max_len=64):
    """Read a null-terminated string from memory"""
    try:
        raw = read_bytes(handle, addr, max_len)
        if not raw:
            return ""
        return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
    except Exception:
        return ""

def unpack(fmt, data): return struct.unpack(fmt, data)[0]

def read_int(handle, addr): 
    if _memory_interface:
        return _memory_interface.read_int(addr)
    return unpack("i", read_bytes(handle, addr, 4))

def read_float(handle, addr): 
    if _memory_interface:
        return _memory_interface.read_float(addr)
    return unpack("f", read_bytes(handle, addr, 4))

def read_uint64(handle, addr): 
    if _memory_interface:
        return _memory_interface.read_uint64(addr)
    return unpack("Q", read_bytes(handle, addr, 8))

def safe_read_uint64(handle, addr): 
    if not addr or addr > 0x7FFFFFFFFFFF:
        return 0
    return read_uint64(handle, addr)

def read_vec3(handle, addr): 
    if _memory_interface:
        vec = _memory_interface.read_vec3(addr)
        return Vec3(vec[0], vec[1], vec[2])
    return Vec3.from_buffer_copy(read_bytes(handle, addr, 12))

def read_matrix(handle, addr): 
    return struct.unpack("f" * 16, read_bytes(handle, addr, 64))

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
    """Write float using unified memory interface when in kernel mode; fallback to usermode WriteProcessMemory."""
    # Only use memory_interface if it actually supports kernel writes
    if _memory_interface and getattr(_memory_interface, "is_kernel_mode_active", lambda: False)():
        return _memory_interface.write_float(address, value)

    # Pure usermode fallback
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

class Entity:
    """Lightweight entity wrapper with aggressive caching.

    Top-3 perf upgrades implemented:
      1) Entity objects are reusable (see get_entities() cache).
      2) Bone reads are batched (single RPM for a contiguous bone range).
      3) Slow-changing fields (name/team/money) use TTL refresh.
    """

    # --- Per-field refresh (seconds) ---
    _NAME_TTL  = 2.5
    _TEAM_TTL  = 1.0
    _MONEY_TTL = 0.25

    # Bone buffer micro-cache (seconds). Small but very effective because skeleton draws
    # request many bones in the same frame.
    _BONEBUF_TTL = 0.020  # 20ms

    _BONE_STRIDE = 0x20

    def __init__(self, controller, pawn, handle):
        self.handle = handle
        self.controller = controller
        self.pawn = pawn

        # bookkeeping for caching/eviction
        self.cached_frame = -1
        self.last_seen_frame = -1

        # Cached pointers
        self.bone_base = None

        # Cache offsets locally for speed (avoid global lookups in hot loops)
        self._h = Offsets.m_iHealth
        self._t = Offsets.m_iTeamNum
        self._p = Offsets.m_vOldOrigin
        self._scene_node_off = Offsets.m_pGameSceneNode
        self._bone_array_off = Offsets.m_pBoneArray
        self._player_name_off = Offsets.m_iszPlayerName
        self._money_services_off = Offsets.m_pInGameMoneyServices
        self._money_acc_off = Offsets.m_iAccount

        # --- Safe defaults so draw code never crashes on partial reads ---
        self.hp = 0
        self.team = 0
        self.pos = Vec3(0.0, 0.0, 0.0)
        self.head = None
        self.money = 0
        self.name = "Unknown"

        # --- TTL refresh timestamps (perf_counter time) ---
        now = time.perf_counter()
        self._next_name_refresh = 0.0  # load asap
        self._next_team_refresh = 0.0
        self._next_money_refresh = 0.0

        # --- Bone bulk-read cache ---
        self._bone_buf = None
        self._bone_buf_min = 0
        self._bone_buf_max = -1
        self._bone_buf_expiry = 0.0

    def touch(self, frame_id: int):
        self.last_seen_frame = frame_id

    def update_refs(self, controller: int, pawn: int, handle):
        # Keep objects reusable across frames (controller/pawn can change)
        self.handle = handle
        self.controller = controller
        self.pawn = pawn

    def update(self, current_frame: int, now=None):
        if self.cached_frame == current_frame:
            return
        self.cached_frame = current_frame
        self.read_data(now=now)

    def _refresh_bone_base(self):
        # Resolve bone_base pointer (scene_node -> bone_array)
        scene_node = safe_read_uint64(self.handle, self.pawn + self._scene_node_off)
        if not scene_node:
            self.bone_base = None
            return None
        self.bone_base = safe_read_uint64(self.handle, scene_node + self._bone_array_off)
        return self.bone_base

    def read_data(self, now=None):
        """Update entity state.

        Hot fields (hp/pos/head pointer) update every call.
        Slow fields (name/team/money) update only on TTL.
        """
        if now is None:
            now = time.perf_counter()

        # Always refresh fast-moving data
        try:
            self.hp = read_int(self.handle, self.pawn + self._h)
        except Exception:
            self.hp = 0

        try:
            self.pos = read_vec3(self.handle, self.pawn + self._p)
        except Exception:
            self.pos = Vec3(0.0, 0.0, 0.0)

        # Refresh bone_base (cheap pointer chain) every frame because it can be invalidated on respawn.
        bone_base = self._refresh_bone_base()
        if bone_base:
            # Head is bone 6; grab it using bulk path for cache friendliness.
            head = self.get_bone_positions((6,), now=now).get(6)
            self.head = head
        else:
            self.head = None

        # TTL refresh: team
        if now >= self._next_team_refresh:
            try:
                self.team = read_int(self.handle, self.pawn + self._t)
            except Exception:
                self.team = 0
            self._next_team_refresh = now + self._TEAM_TTL

        # TTL refresh: name
        if (self.name == "Unknown") or (now >= self._next_name_refresh):
            self.name = self.read_name() or "Unknown"
            self._next_name_refresh = now + self._NAME_TTL

        # TTL refresh: money
        if now >= self._next_money_refresh:
            money = 0
            try:
                money_services = safe_read_uint64(self.handle, self.controller + self._money_services_off)
                if money_services:
                    money = read_int(self.handle, money_services + self._money_acc_off)
            except Exception:
                money = 0
            self.money = money
            self._next_money_refresh = now + self._MONEY_TTL

    def read_name(self) -> str:
        try:
            raw = read_bytes(self.handle, self.controller + self._player_name_off, 32)
            if raw:
                s = raw.split(b'\x00')[0].decode(errors='ignore')
                return s.strip() if s else "Unknown"
        except Exception:
            pass
        return "Unknown"

    def get_bone_positions(self, indices, now=None):
        """Bulk-read a contiguous bone range and return {index: Vec3|None}.

        Uses a tiny per-entity buffer cache to avoid re-reading bones multiple times per frame.
        """
        if now is None:
            now = time.perf_counter()

        out = {int(i): None for i in indices}
        if not out:
            return out

        if not self.bone_base:
            if not self._refresh_bone_base():
                return out

        # Compute contiguous range to read
        idxs = [int(i) for i in out.keys() if int(i) >= 0]
        if not idxs:
            return out
        bmin = min(idxs)
        bmax = max(idxs)

        # If our cached buffer doesn't cover the request or expired -> read a new block
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
            # Defensive: if RPM failed, don't cache garbage
            if not buf or len(buf) != size:
                return out
            self._bone_buf = buf
            self._bone_buf_min = bmin
            self._bone_buf_max = bmax
            self._bone_buf_expiry = now + self._BONEBUF_TTL

        buf = self._bone_buf
        stride = self._BONE_STRIDE
        base_min = self._bone_buf_min

        # Parse only the requested bones (position at offset 0: 3 floats)
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

    def BonePos(self, index):
        # Backwards-compatible API: now uses bulk read under the hood.
        idx = int(index)
        return self.get_bone_positions((idx,)).get(idx)

    def wts(self, matrix, width, height):
        feet2d = world_to_screen(matrix, self.pos, width, height)
        head2d = world_to_screen(matrix, self.head, width, height)
        self.feet2d, self.head2d = feet2d, head2d
        return feet2d is not None and head2d is not None

# Map detection with caching
def get_current_map_name_cached(handle, matchmaking_base):
    """Get current map name with caching.

    IMPORTANT: The map name field is treated as a pointer-to-string (64-bit) to match
    get_current_map_name(). This avoids inconsistent reads that can return garbage.
    """
    global current_detected_map
    now = time.time()

    # Use cached value if recent (within 5 seconds)
    last_check = getattr(get_current_map_name_cached, "last_check", 0.0)
    if (now - last_check) < 5.0 and current_detected_map:
        return current_detected_map

    try:
        if not handle or not matchmaking_base:
            get_current_map_name_cached.last_check = now
            return current_detected_map

        ptr_addr = matchmaking_base + DW_GAME_TYPES + DW_GAME_TYPES_MAP_NAME

        # Read pointer (8 bytes) then dereference to read the actual string
        ptr_bytes = read_bytes(handle, ptr_addr, 8)
        if not ptr_bytes:
            get_current_map_name_cached.last_check = now
            return current_detected_map

        map_name_ptr = struct.unpack("Q", ptr_bytes)[0]
        if not map_name_ptr or map_name_ptr > 0x7FFFFFFFFFFF:
            get_current_map_name_cached.last_check = now
            return current_detected_map

        raw = read_bytes(handle, map_name_ptr, 128)
        if raw:
            map_name = raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
            if map_name and len(map_name) > 2 and not map_name.isspace():
                current_detected_map = map_name
    except Exception:
        pass

    get_current_map_name_cached.last_check = now
    return current_detected_map

    
    try:
        # Read map name from memory
        map_name_addr = matchmaking_base + DW_GAME_TYPES + DW_GAME_TYPES_MAP_NAME
        raw_bytes = read_bytes(handle, map_name_addr, 64)
        if raw_bytes:
            map_name = raw_bytes.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
            if map_name and len(map_name) > 2:  # Valid map name
                current_detected_map = map_name
                get_current_map_name_cached.last_check = now
                return map_name
    except Exception as e:
        pass
    
    get_current_map_name_cached.last_check = now
    return current_detected_map

# ---------------------------------------------
# Spectator list & bomb status
# ---------------------------------------------

class SpectatorList:
    def __init__(self, handle, client_base):
        self.handle = handle
        self.client_base = client_base
        self.last_spec_check = 0.0
        self.cached_spectators = []

    def _safe_read_uint64(self, addr):
        return 0 if not addr or addr > 0x7FFFFFFFFFFF else read_uint64(self.handle, addr)

    def _safe_read_int(self, addr):
        return 0 if not addr or addr > 0x7FFFFFFFFFFF else read_int(self.handle, addr)

    def _safe_read_string(self, addr, max_length=32):
        if not addr or addr > 0x7FFFFFFFFFFF:
            return ""
        try:
            raw = read_bytes(self.handle, addr, max_length)
            return raw.split(b'\x00')[0].decode(errors='ignore')
        except Exception:
            return ""

    def _get_entity(self, entity_list, handle):
        hi = handle >> 9
        lo = handle & 0x1FF
        entry_addr = entity_list + 0x8 * hi + 0x10
        entry = self._safe_read_uint64(entry_addr)
        if not entry:
            return 0
        return self._safe_read_uint64(entry + 112 * lo)

    def GetSpectatorsCached(self):
        now = time.time()
        if now - self.last_spec_check > 1.0:
            self.cached_spectators = self.GetSpectators()
            self.last_spec_check = now
        return self.cached_spectators

    def GetSpectators(self):
        try:
            entity_list = self._safe_read_uint64(self.client_base + Offsets.dwEntityList)
            local_controller = self._safe_read_uint64(self.client_base + Offsets.dwLocalPlayerController)
            if not local_controller:
                return []
            local_pawn_handle = self._safe_read_int(local_controller + Offsets.m_hPawn) & 0x7FFF
            local_pawn = self._get_entity(entity_list, local_pawn_handle)
            if not local_pawn:
                return []

            spectators = []
            for i in range(1, 65):
                controller = self._get_entity(entity_list, i)
                if not controller or controller == local_controller:
                    continue
                obs_pawn_handle = self._safe_read_int(controller + Offsets.m_hPawn) & 0x7FFF
                observer_pawn = self._get_entity(entity_list, obs_pawn_handle)
                if not observer_pawn:
                    continue
                observer_services = self._safe_read_uint64(observer_pawn + Offsets.m_pObserverServices)
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

# ---------------------------------------------
# Drawing helpers (shared UI style)
# ---------------------------------------------

def draw_info_box(overlay, x, y, w, h, title, lines, font_size=12, title_color=None, body_color=None):
    """Generic styled info box used by Map Status, Spectators, and Watermark."""
    bg = getattr(Config, "color_local_box_background", (30, 30, 30))
    bd = getattr(Config, "color_local_box_border", (100, 100, 100))
    tcol = title_color if title_color else (255, 255, 255)
    bcol = body_color if body_color else (220, 220, 220)

    overlay.draw_filled_rect(x, y, w, h, bg)
    overlay.draw_box(x, y, w, h, bd)

    if title:
        overlay.draw_text(str(title), x + 6, y + 6, tcol, font_size)
    # Start body below title
    ty = y + 6 + (font_size + 4)
    if lines:
        for i, line in enumerate(lines):
            overlay.draw_text(str(line), x + 6, ty + i * (font_size + 2), bcol, font_size)

def clamp_box_to_screen(pos, w, h, screen_w, screen_h):
    x = max(0, min(pos[0], screen_w - w))
    y = max(0, min(pos[1], screen_h - h))
    pos[0], pos[1] = x, y

# === Drawing small UI blocks ===

def draw_map_status_box(overlay, vis_checker):
    """Styled box: current map + VisCheck status + perf metrics."""
    global current_detected_map, performance_metrics, last_performance_update
    x, y = map_status_pos
    w, h = 300, 86  # a bit taller for consistent spacing
    clamp_box_to_screen(map_status_pos, w, h, overlay.width, overlay.height)

    # Status line
    if optimized_vischeck and hasattr(optimized_vischeck, "is_loading") and optimized_vischeck.is_loading():
        status, scol = "Loading...", (255, 255, 0)
        perf_lines = []
    elif optimized_vischeck and hasattr(optimized_vischeck, "is_loaded") and optimized_vischeck.is_loaded():
        metrics = optimized_vischeck.get_metrics() if hasattr(optimized_vischeck, "get_metrics") else None
        cache_indicator = "(Cached)" if (metrics and getattr(metrics, 'cache_hit', False)) else "(Disk)"
        status, scol = f"Loaded {cache_indicator}", (0, 255, 0)
    elif vis_checker and hasattr(vis_checker, 'is_map_loaded') and vis_checker.is_map_loaded():
        cur_map = vis_checker.get_current_map() if hasattr(vis_checker, 'get_current_map') else None
        fname = os.path.basename(cur_map) if cur_map else 'unknown'
        status, scol = f"Loaded ({fname})", (0, 255, 0)
    else:
        status, scol = "Not Loaded", (255, 0, 0)

    # Perf metrics
    perf_lines = []
    if optimized_vischeck and performance_metrics:
        now = time.time()
        if now - last_performance_update > 2.0:
            try:
                pm = optimized_vischeck.get_metrics()
                if pm:
                    performance_metrics = pm
            except Exception:
                pass
            last_performance_update = now
        if getattr(performance_metrics, "load_time_ms", 0) > 0:
            txt = f"Load: {performance_metrics.load_time_ms}ms"
            if getattr(performance_metrics, "triangle_count", 0) > 0:
                txt += f" | Tris: {performance_metrics.triangle_count:,}"
            perf_lines.append(txt)
        if getattr(performance_metrics, "memory_usage_mb", 0.0) > 0.0:
            perf_lines.append(f"Memory: {performance_metrics.memory_usage_mb:.1f}MB")

    title = f"Map: {current_detected_map or 'Unknown'}"
    lines = [f"VisCheck: {status}"] + perf_lines
    draw_info_box(overlay, x, y, w, h, title, lines, font_size=12, title_color=(255,255,255), body_color=(200,200,200))
    # colored status text override
    overlay.draw_text(f"VisCheck: {status}", x + 6, y + 6 + (12 + 4), scol, 12)

def draw_spectator_list(overlay, spectators):
    global spectator_list_pos
    rows = spectators if spectators else ["None"]
    font_size = 12
    h = 6 + font_size + 4 + max(1, len(rows)) * (font_size + 2) + 6
    w = 220
    clamp_box_to_screen(spectator_list_pos, w, h, overlay.width, overlay.height)

    # Cache the rows and size for drag hit-testing
    overlay._last_spectator_rows = rows
    # Save size on both overlay and its renderer
    overlay._last_spectator_box = (w, h)
    if hasattr(overlay, "renderer"):
        overlay.renderer._last_spectator_box = (w, h)

    draw_info_box(overlay, spectator_list_pos[0], spectator_list_pos[1], w, h, "Spectators", rows, font_size=font_size)


def draw_watermark(overlay, version="GFusion v1"):
    x, y = watermark_pos
    font_size = 12
    lines = [version, time.strftime("%H:%M:%S")]
    h = 6 + font_size + 4 + len(lines) * (font_size + 2) + 6
    w = 200
    clamp_box_to_screen(watermark_pos, w, h, overlay.width, overlay.height)
    draw_info_box(overlay, x, y, w, h, "Watermark", lines, font_size=font_size)
	

# Entity type mappings (from C++)
ENTITY_TYPES = {
    "chicken": "Chicken",
    "hostage_entity": "Hostage",
    "c4": "Bomb"
}

PROJECTILE_TYPES = {
    "smokegrenade_projectile": "Smoke",
    "flashbang_projectile": "Flash",
    "hegrenade_projectile": "HE",
    "molotov_projectile": "Molotov",
    "incendiarygrenade_projectile": "Incendiary",
    "decoy_projectile": "Decoy"
}

WEAPON_TYPES = {
    "weapon_ak47": "AK-47",
    "weapon_m4a1": "M4A1",
    "weapon_awp": "AWP",
    "weapon_elite": "Dual Berettas",
    "weapon_famas": "FAMAS",
    "weapon_g3sg1": "G3SG1",
    "weapon_galilar": "Galil AR",
    "weapon_m249": "M249",
    "weapon_m4a1_silencer": "M4A1-S",
    "weapon_mac10": "MAC-10",
    "weapon_mag7": "MAG-7",
    "weapon_mp5sd": "MP5-SD",
    "weapon_mp7": "MP7",
    "weapon_mp9": "MP9",
    "weapon_negev": "Negev",
    "weapon_nova": "Nova",
    "weapon_p90": "P90",
    "weapon_sawedoff": "Sawed-Off",
    "weapon_scar20": "SCAR-20",
    "weapon_sg556": "SG 553",
    "weapon_ssg08": "SSG 08",
    "weapon_ump45": "UMP-45",
    "weapon_xm1014": "XM1014",
    "weapon_aug": "AUG",
    "weapon_bizon": "PP-Bizon",
    "weapon_fiveseven": "Five-SeveN",
    "weapon_hkp2000": "P2000",
    "weapon_usp_silencer": "USP-S",
    "weapon_p250": "P250",
    "weapon_tec9": "Tec-9",
    "weapon_cz75a": "CZ75-Auto",
    "weapon_deagle": "Desert Eagle",
    "weapon_revolver": "R8 Revolver",
    "weapon_glock": "Glock-18"
}

def get_weapon_type(identifier):
    """Get weapon display name from identifier"""
    return WEAPON_TYPES.get(identifier, None)

def get_projectile_type(identifier):
    """Get projectile display name from identifier"""
    return PROJECTILE_TYPES.get(identifier, None)

def get_entity_type(identifier):
    """Get entity display name from identifier"""
    return ENTITY_TYPES.get(identifier, None)

# --- Entity cache for performance (reuses Entity objects across frames) ---
_ENTITY_CACHE = {}     # {pawn_addr: Entity}
_ENTITY_FRAME = 0      # incremented each get_entities() call

def get_entities(handle, base):
    """Return list[Entity] using an object cache to reduce allocations and RPM overhead."""
    global _ENTITY_CACHE, _ENTITY_FRAME
    _ENTITY_FRAME += 1
    frame_id = _ENTITY_FRAME
    now = time.perf_counter()

    try:
        local = safe_read_uint64(handle, base + Offsets.dwLocalPlayerController)
        entity_list = safe_read_uint64(handle, base + Offsets.dwEntityList)
    except Exception as e:
        print(f"[ESP] Failed to read entity list base: {e}")
        return []

    result = []
    seen_pawns = set()
    max_entities = 64  # Safety limit

    # Localize hot functions for tiny speedups in the loop
    _safe_u64 = safe_read_uint64
    _read_u64 = read_uint64

    for i in range(1, min(65, max_entities + 1)):
        i_mask_7FFF = i & 0x7FFF
        i_mask_1FF = i & 0x1FF

        list_offset = ((i_mask_7FFF) >> 9) * 8 + 16
        try:
            entry = _safe_u64(handle, entity_list + list_offset)
            if not entry:
                continue

            ctrl = _safe_u64(handle, entry + (112 * i_mask_1FF))
            if not ctrl or ctrl == local:
                continue

            hPawn = _safe_u64(handle, ctrl + Offsets.m_hPlayerPawn)
            if not hPawn:
                continue

            pawn_list_offset = ((hPawn & 0x7FFF) >> 9) * 8 + 16
            pawn_entry = _safe_u64(handle, entity_list + pawn_list_offset)
            if not pawn_entry:
                continue

            pawn = _safe_u64(handle, pawn_entry + (112 * (hPawn & 0x1FF)))
            if not pawn:
                continue

            seen_pawns.add(pawn)

            ent = _ENTITY_CACHE.get(pawn)
            if ent is None:
                ent = Entity(ctrl, pawn, handle)
                _ENTITY_CACHE[pawn] = ent
            else:
                ent.update_refs(ctrl, pawn, handle)

            ent.touch(frame_id)
            ent.update(frame_id, now=now)
            result.append(ent)

        except Exception:
            continue

    # Evict stale entries occasionally (keeps cache bounded)
    # Remove entities not seen for ~2 seconds at 144fps (~288 frames). Use frame count, not wall clock.
    if (frame_id % 60) == 0 and _ENTITY_CACHE:
        stale_before = frame_id - 300
        # Avoid "changed size during iteration"
        for pawn_addr, ent in list(_ENTITY_CACHE.items()):
            if getattr(ent, "last_seen_frame", -1) < stale_before:
                _ENTITY_CACHE.pop(pawn_addr, None)

    return result

class GDIRenderer:
    BONE_POSITIONS = {"head": 6, "chest": 15, "left_hand": 10, "right_hand": 2, "left_leg": 23, "right_leg": 26}
    BONE_CONNECTIONS = [
        (0, 2), (2, 4), (4, 5), (5, 6), (4, 8), (8, 9), (9, 10),
        (4, 13), (13, 14), (14, 15), (0, 22), (22, 23), (23, 24),
        (0, 25), (25, 26), (26, 27)
    ]

    def __init__(self, title="GHax", fps=144):
        self.width, self.height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
        self.fps = fps
        self._frame_time = 1 / fps
        self._accumulator = 0.0
        self._last_time = time.perf_counter()

        self._frame_count = 0
        self._fps_timer = time.perf_counter()
        self.current_fps = 0

        self.font_cache = {}
        self.pen_cache = {}
        self.brush_cache = {}

        self._last_obs_check_time = 0
        self._obs_check_interval = 0.5  # check OBS toggle twice per second
        self._last_obs_value = None

        self.init_window(title)
        self.black_brush = self.get_brush((0, 0, 0))

        # State caching for the current frame to minimize GDI calls
        self._current_pen = None
        self._current_brush = None
        self._current_font = None
        self._hdc = None

    def __del__(self):
        for cache in (self.font_cache, self.pen_cache, self.brush_cache):
            for obj in cache.values():
                try:
                    win32gui.DeleteObject(obj)
                except Exception:
                    pass

        for attr in ('buffer', 'memdc', 'hdc_obj'):
            dc = getattr(self, attr, None)
            if dc:
                try:
                    dc.DeleteDC() if 'dc' in attr else dc.DeleteObject()
                except Exception:
                    pass

        if hasattr(self, 'hdc'):
            try:
                win32gui.ReleaseDC(self.hwnd, self.hdc)
            except Exception:
                pass

        if hasattr(self, 'hwnd'):
            try:
                win32gui.DestroyWindow(self.hwnd)
            except Exception:
                pass

    def draw_corner_box(self, x, y, w, h, color, line_len=6):
        # Draws only the corners of the box
        self.select_pen(color)
        null_brush = win32gui.GetStockObject(win32con.NULL_BRUSH)
        win32gui.SelectObject(self._hdc, null_brush)

        # Top left
        win32gui.MoveToEx(self._hdc, int(x), int(y))
        win32gui.LineTo(self._hdc, int(x + line_len), int(y))
        win32gui.MoveToEx(self._hdc, int(x), int(y))
        win32gui.LineTo(self._hdc, int(x), int(y + line_len))

        # Top right
        win32gui.MoveToEx(self._hdc, int(x + w), int(y))
        win32gui.LineTo(self._hdc, int(x + w - line_len), int(y))
        win32gui.MoveToEx(self._hdc, int(x + w), int(y))
        win32gui.LineTo(self._hdc, int(x + w), int(y + line_len))

        # Bottom left
        win32gui.MoveToEx(self._hdc, int(x), int(y + h))
        win32gui.LineTo(self._hdc, int(x), int(y + h - line_len))
        win32gui.MoveToEx(self._hdc, int(x), int(y + h))
        win32gui.LineTo(self._hdc, int(x + line_len), int(y + h))

        # Bottom right
        win32gui.MoveToEx(self._hdc, int(x + w), int(y + h))
        win32gui.LineTo(self._hdc, int(x + w - line_len), int(y + h))
        win32gui.MoveToEx(self._hdc, int(x + w), int(y + h))
        win32gui.LineTo(self._hdc, int(x + w), int(y + h - line_len))

    def draw_rounded_box(self, x, y, w, h, radius, color):
        self.select_pen(color)
        null_brush = win32gui.GetStockObject(win32con.NULL_BRUSH)
        win32gui.SelectObject(self._hdc, null_brush)
        # Use Windows GDI RoundRect function
        win32gui.RoundRect(
            self._hdc,
            int(x), int(y), int(x + w), int(y + h),
            int(radius), int(radius)
        )

    def get_font(self, size):
        if size not in self.font_cache:
            lf = win32gui.LOGFONT()
            lf.lfHeight = -int(size)  # negative for pixel size
            lf.lfWeight = 700
            lf.lfFaceName = "Segoe UI"
            font = win32gui.CreateFontIndirect(lf)
            self.font_cache[size] = font
        return self.font_cache[size]

    def get_pen(self, color):
        if color not in self.pen_cache:
            pen = win32gui.CreatePen(win32con.PS_SOLID, 1, win32api.RGB(*color))
            self.pen_cache[color] = pen
        return self.pen_cache[color]

    def get_brush(self, color):
        if color not in self.brush_cache:
            brush = win32gui.CreateSolidBrush(win32api.RGB(*color))
            self.brush_cache[color] = brush
        return self.brush_cache[color]

    def select_pen(self, color):
        if self._current_pen != color:
            pen = self.get_pen(color)
            win32gui.SelectObject(self._hdc, pen)
            self._current_pen = color

    def select_brush(self, color):
        if self._current_brush != color:
            brush = self.get_brush(color)
            win32gui.SelectObject(self._hdc, brush)
            self._current_brush = color

    def select_font(self, size):
        if self._current_font != size:
            font = self.get_font(size)
            win32gui.SelectObject(self._hdc, font)
            self._current_font = size

    def draw_circle(self, x, y, r, color):
        r = int(r * 0.8)
        self.select_pen(color)
        null_brush = win32gui.GetStockObject(win32con.NULL_BRUSH)
        win32gui.SelectObject(self._hdc, null_brush)
        win32gui.Ellipse(self._hdc, int(x - r), int(y - r), int(x + r), int(y + r))

    def draw_text(self, text, x, y, color=(255, 255, 255), size=14, centered=False):
        self.select_font(size)
        win32gui.SetTextColor(self._hdc, win32api.RGB(*color))
        win32gui.SetBkMode(self._hdc, win32con.TRANSPARENT)
        if centered:
            w, h = win32gui.GetTextExtentPoint32(self._hdc, text)
            x -= w // 2
            y -= h // 2
        self.memdc.TextOut(int(x), int(y), text)

    def draw_box(self, x, y, w, h, color):
        self.select_pen(color)
        null_brush = win32gui.GetStockObject(win32con.NULL_BRUSH)
        win32gui.SelectObject(self._hdc, null_brush)
        win32gui.Rectangle(self._hdc, int(x), int(y), int(x + w), int(y + h))

    def draw_filled_rect(self, x, y, w, h, color):
        rect = (int(x), int(y), int(x + w), int(y + h))
        win32gui.FillRect(self._hdc, rect, self.get_brush(color))

    def draw_line(self, x1, y1, x2, y2, color):
        self.select_pen(color)
        win32gui.MoveToEx(self._hdc, int(x1), int(y1))
        win32gui.LineTo(self._hdc, int(x2), int(y2))

    def check_and_update_obs_toggle(self):
        now = time.perf_counter()
        if now - self._last_obs_check_time >= self._obs_check_interval:
            from Process.config import Config
            val = Config.obs_protection_enabled
            if self._last_obs_value != val:
                self._last_obs_value = val
                self.update_obs_protection()
            self._last_obs_check_time = now


    def begin_scene(self):
        now = time.perf_counter()
        delta = now - self._last_time
        self._last_time = now
        self._accumulator += delta

        if self._accumulator < self._frame_time:
            return False  # skip frame, too soon

        self._accumulator -= self._frame_time

        # Clear screen to black once per frame
        win32gui.FillRect(self.memdc.GetSafeHdc(), (0, 0, self.width, self.height), self.black_brush)
        self.check_and_update_obs_toggle()

        # Cache HDC and reset selected objects
        self._hdc = self.memdc.GetSafeHdc()
        self._current_pen = None
        self._current_brush = None
        self._current_font = None

        return True

    def end_scene(self):
        self._frame_count += 1
        now = time.perf_counter()
        if now - self._fps_timer >= 1.0:
            self.current_fps = self._frame_count
            self._frame_count = 0
            self._fps_timer = now
        self.hdc_obj.BitBlt((0, 0), (self.width, self.height), self.memdc, (0, 0), win32con.SRCCOPY)

    def update_obs_protection(self):
        from Process.config import Config
        if hasattr(self, 'hwnd'):
            affinity = 0x11 if Config.obs_protection_enabled else 0x00
            windll.user32.SetWindowDisplayAffinity(self.hwnd, affinity)

    def init_window(self, title):
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = title
        wc.hInstance = win32api.GetModuleHandle(None)
        class_atom = win32gui.RegisterClass(wc)

        style = (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_TOOLWINDOW
        )
        self.hwnd = win32gui.CreateWindowEx(
            style,
            class_atom,
            title,
            win32con.WS_POPUP,
            0,
            0,
            self.width,
            self.height,
            None,
            None,
            wc.hInstance,
            None,
        )

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
        global spectator_list_dragging, spectator_list_drag_offset, spectator_list_pos
        global map_status_dragging, map_status_drag_offset, map_status_pos
        global watermark_dragging, watermark_drag_offset, watermark_pos

        x = lparam & 0xFFFF
        y = (lparam >> 16) & 0xFFFF

        if msg == win32con.WM_LBUTTONDOWN:
            # Use cached spectator list size if available
            w, h = getattr(self, "_last_spectator_box", (220, 120))
            if point_in_box(x, y, spectator_list_pos, w, h):
                spectator_list_dragging = True
                spectator_list_drag_offset = [x - spectator_list_pos[0], y - spectator_list_pos[1]]
            elif point_in_box(x, y, map_status_pos, 300, 86):
                map_status_dragging = True
                map_status_drag_offset = [x - map_status_pos[0], y - map_status_pos[1]]
            elif point_in_box(x, y, watermark_pos, 200, 60):
                watermark_dragging = True
                watermark_drag_offset = [x - watermark_pos[0], y - watermark_pos[1]]
            return 0

        elif msg == win32con.WM_MOUSEMOVE and (wparam & win32con.MK_LBUTTON):
            if spectator_list_dragging:
                spectator_list_pos[0] = x - spectator_list_drag_offset[0]
                spectator_list_pos[1] = y - spectator_list_drag_offset[1]
            elif map_status_dragging:
                map_status_pos[0] = x - map_status_drag_offset[0]
                map_status_pos[1] = y - map_status_drag_offset[1]
            elif watermark_dragging:
                watermark_pos[0] = x - watermark_drag_offset[0]
                watermark_pos[1] = y - watermark_drag_offset[1]
            return 0

        elif msg == win32con.WM_LBUTTONUP:
            spectator_list_dragging = False
            map_status_dragging = False
            watermark_dragging = False
            return 0

        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def get_module_base(self, pid, module_name):
        snapshot = windll.kernel32.CreateToolhelp32Snapshot(0x8, pid)  # TH32CS_SNAPMODULE = 0x8

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

        entry = MODULEENTRY32()
        entry.dwSize = ctypes.sizeof(MODULEENTRY32)

        if windll.kernel32.Module32First(snapshot, byref(entry)):
            while True:
                if entry.szModule.decode() == module_name:
                    base = ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value
                    windll.kernel32.CloseHandle(snapshot)
                    return base
                if not windll.kernel32.Module32Next(snapshot, byref(entry)):
                    break
        windll.kernel32.CloseHandle(snapshot)
        return None


class DX11Renderer:
    def __init__(self, title="GHax", fps=144):
        # Fully GPU-based renderer: no GDI delegate.
        # Create our own transparent, click-through overlay window and initialize DX11 on it.
        self.width, self.height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
        self.fps = fps
        self.current_fps = 0
        # Frame pacing (independent of vsync)
        self._frame_time = 1.0 / max(1, int(fps))
        self._accumulator = 0.0
        self._last_time = time.perf_counter()
        self._frame_count = 0
        self._fps_timer = self._last_time

        # Placeholders for future DX11/DirectComposition resources
        self._dx_initialized = False
        self._dx = None
        self._dx_ctx = None
        # self._d3d_device = None
        # self._d3d_context = None
        # self._dxgi_swapchain = None
        # self._dcomp_device = None
        # self._dcomp_target = None
        # self._dcomp_visual = None

        # Initialize window/resources (own Win32 window, no GDI rendering)
        self.init_window(title)

    def init_window(self, title):
        # Create a transparent, click-through, topmost Win32 window for the overlay.
        import ctypes
        hInstance = win32api.GetModuleHandle(None)
        class_name = "DX11OverlayWindow"

        # Window proc: basic handling and default defwindowproc
        def wndproc(hWnd, msg, wParam, lParam):
            if msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)

        wndclass = win32gui.WNDCLASS()
        wndclass.hInstance = hInstance
        wndclass.lpszClassName = class_name
        wndclass.lpfnWndProc = wndproc
        wndclass.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wndclass.hbrBackground = win32con.COLOR_WINDOW
        try:
            win32gui.RegisterClass(wndclass)
        except Exception:
            pass  # Already registered

        ex_style = (
            win32con.WS_EX_TOPMOST
            | win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | 0x08000000  # WS_EX_NOACTIVATE
            | 0x00000080  # WS_EX_TOOLWINDOW
        )
        style = win32con.WS_POPUP

        hwnd = win32gui.CreateWindowEx(
            ex_style,
            class_name,
            title,
            style,
            0,
            0,
            self.width,
            self.height,
            0,
            0,
            hInstance,
            None,
        )
        # Set transparency attributes (fully opaque alpha; actual transparency from premultiplied content)
        LWA_ALPHA = 0x2
        win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOSIZE | win32con.SWP_NOMOVE | win32con.SWP_NOACTIVATE)

        self.hwnd = hwnd

        # Initialize DX11 backend safely
        try:
            from render import dx11_backend as _dx
            self._dx = _dx
            self._dx_ctx = _dx.initialize(self.hwnd, self.width, self.height)
            self._dx_initialized = self._dx_ctx is not None
        except Exception:
            self._dx_initialized = False
            self._dx = None
            self._dx_ctx = None
        return True

    def begin_scene(self):
        # Frame pacing using high-resolution timer (no sleeps), similar to GDI renderer
        now = time.perf_counter()
        delta = now - self._last_time
        self._last_time = now
        self._accumulator += delta

        if self._accumulator < self._frame_time:
            return False  # skip this frame to maintain target FPS
        self._accumulator -= self._frame_time

        gpu_ready = self._dx_initialized and self._dx is not None and self._dx_ctx is not None and getattr(self._dx, 'pipeline_ready', None) and self._dx.pipeline_ready(self._dx_ctx)
        if gpu_ready:
            try:
                self._dx.begin_scene(self._dx_ctx)
                return True
            except Exception:
                return False
        return False

    def end_scene(self):
        gpu_ready = self._dx_initialized and self._dx is not None and self._dx_ctx is not None and getattr(self._dx, 'pipeline_ready', None) and self._dx.pipeline_ready(self._dx_ctx)
        if gpu_ready:
            try:
                ok = self._dx.end_scene(self._dx_ctx)
                # Update FPS counter once per second
                self._frame_count += 1
                now = time.perf_counter()
                if now - self._fps_timer >= 1.0:
                    self.current_fps = self._frame_count
                    self._frame_count = 0
                    self._fps_timer = now
                return ok
            except Exception:
                return False
        return False

    def draw_corner_box(self, x, y, w, h, color, line_len=6):
        if not (self._dx_initialized and self._dx and self._dx_ctx and self._dx.pipeline_ready(self._dx_ctx)):
            return False
        try:
            # Top left
            self._dx.queue_line(self._dx_ctx, x, y, x + line_len, y, color)
            self._dx.queue_line(self._dx_ctx, x, y, x, y + line_len, color)
            # Top right
            self._dx.queue_line(self._dx_ctx, x + w, y, x + w - line_len, y, color)
            self._dx.queue_line(self._dx_ctx, x + w, y, x + w, y + line_len, color)
            # Bottom left
            self._dx.queue_line(self._dx_ctx, x, y + h, x + line_len, y + h, color)
            self._dx.queue_line(self._dx_ctx, x, y + h, x, y + h - line_len, color)
            # Bottom right
            self._dx.queue_line(self._dx_ctx, x + w, y + h, x + w - line_len, y + h, color)
            self._dx.queue_line(self._dx_ctx, x + w, y + h, x + w, y + h - line_len, color)
            return True
        except Exception:
            return False

    def draw_rounded_box(self, x, y, w, h, radius, color):
        gpu_ready = self._dx_initialized and self._dx and self._dx_ctx and self._dx.pipeline_ready(self._dx_ctx)
        if gpu_ready:
            try:
                self._dx.queue_rect(self._dx_ctx, float(x), float(y), float(w), float(h), color, filled=False, radius=float(radius))
                return True
            except Exception:
                return False
        return False

    # --- Drawing API: enqueue to DX backend (and still delegate to GDI for now) ---
    def draw_line(self, x1, y1, x2, y2, color):
        gpu_ready = self._dx_initialized and self._dx is not None and self._dx_ctx is not None and getattr(self._dx, 'pipeline_ready', None) and self._dx.pipeline_ready(self._dx_ctx)
        if gpu_ready:
            try:
                self._dx.queue_line(self._dx_ctx, float(x1), float(y1), float(x2), float(y2), color)
                return True
            except Exception:
                return False
        return False

    def draw_box(self, x, y, w, h, color):
        gpu_ready = self._dx_initialized and self._dx is not None and self._dx_ctx is not None and getattr(self._dx, 'pipeline_ready', None) and self._dx.pipeline_ready(self._dx_ctx)
        if gpu_ready:
            try:
                self._dx.queue_rect(self._dx_ctx, float(x), float(y), float(w), float(h), color, filled=False)
                return True
            except Exception:
                return False
        return False

    def draw_filled_rect(self, x, y, w, h, color):
        gpu_ready = self._dx_initialized and self._dx is not None and self._dx_ctx is not None and getattr(self._dx, 'pipeline_ready', None) and self._dx.pipeline_ready(self._dx_ctx)
        if gpu_ready:
            try:
                self._dx.queue_rect(self._dx_ctx, float(x), float(y), float(w), float(h), color, filled=True)
                return True
            except Exception:
                return False
        return False

    def draw_circle(self, x, y, r, color):
        gpu_ready = self._dx_initialized and self._dx is not None and self._dx_ctx is not None and getattr(self._dx, 'pipeline_ready', None) and self._dx.pipeline_ready(self._dx_ctx)
        if gpu_ready:
            try:
                self._dx.queue_circle(self._dx_ctx, float(x), float(y), float(r), color, filled=False)
                return True
            except Exception:
                return False
        return False

    def draw_text(self, text, x, y, color=(255,255,255), size=14, centered=False):
        gpu_ready = self._dx_initialized and self._dx is not None and self._dx_ctx is not None and getattr(self._dx, 'pipeline_ready', None) and self._dx.pipeline_ready(self._dx_ctx)
        if gpu_ready:
            try:
                self._dx.queue_text(self._dx_ctx, str(text), float(x), float(y), color, int(size), bool(centered))
                return True
            except Exception:
                return False
        return False

    


class Overlay:
    def __init__(self, title="GHax", fps=144):
        from Process.config import Config
        if getattr(Config, "use_gpu_overlay", False):
            self.renderer = DX11Renderer(title, fps)
        else:
            self.renderer = GDIRenderer(title, fps)

    def __getattr__(self, name):
        return getattr(self.renderer, name)


        
def RenderBoneESP(overlay, entity, matrix, local_pos, vis_checker, local_team, flags):
    skeleton_enabled = flags.get("skeleton_esp_enabled", False)
    bone_dot_enabled = flags.get("bone_dot_esp_enabled", False)
    if not (skeleton_enabled or bone_dot_enabled):
        return

    # --- Skeleton color selection ---
    if entity.hp <= 0:
        # Dead skeleton colors use same config as box
        color_bone = flags.get("color_dead_t", (128, 0, 0)) if entity.team == 2 else flags.get("color_dead_ct", (0, 0, 128))
    else:
        # Alive skeleton colors
        if flags.get("visibility_esp_enabled", False) and vis_checker and local_pos:
            try:
                is_visible = check_player_visibility(local_pos, entity.pos, vis_checker)
            except Exception as e:
                print(f"[VisCheck Skeleton Error] {e}")
                is_visible = None

            if is_visible is not None:
                if entity.team == 2:  # T
                    color_bone = flags.get("color_skeleton_visible_t", (255, 0, 0)) if is_visible else flags.get("color_skeleton_invisible_t", (128, 0, 0))
                else:  # CT
                    color_bone = flags.get("color_skeleton_visible_ct", (0, 0, 255)) if is_visible else flags.get("color_skeleton_invisible_ct", (0, 0, 128))
            else:
                # fallback if vischeck failed
                color_bone = getattr(Config, "color_bone", (255, 255, 255))
        else:
            # fallback if vischeck disabled
            color_bone = getattr(Config, "color_bone", (255, 255, 255))

    # --- Bone rendering ---
    bone_dot_size = flags.get("bone_dot_size", flags.get("bone_esp_size", 6))
    bone_dot_color = flags.get("bone_dot_color", flags.get("bone_esp_color", (255, 0, 255)))
    draw_circle = str(
        flags.get("bone_dot_shape", flags.get("bone_esp_shape", "circle"))
    ).lower() == "circle"


    needed_bones = set()
    if skeleton_enabled:
        needed_bones.update(b for conn in overlay.BONE_CONNECTIONS for b in conn)
    if bone_dot_enabled:
        needed_bones.update(overlay.BONE_POSITIONS.values())

    width, height = overlay.width, overlay.height
    bone_screens = {}

    # Bulk bone read (single RPM for a contiguous range) + tiny cache inside Entity
    now = time.perf_counter()
    bone_positions = entity.get_bone_positions(needed_bones, now=now)

    for bone in needed_bones:
        pos = bone_positions.get(bone)
        if pos:
            screen = world_to_screen(matrix, pos, width, height)
            if screen and "x" in screen and "y" in screen:
                bone_screens[bone] = (screen["x"], screen["y"])
                continue
        bone_screens[bone] = None
    # Skeleton lines
    if skeleton_enabled:
        for start, end in overlay.BONE_CONNECTIONS:
            a, b = bone_screens.get(start), bone_screens.get(end)
            if a and b:
                overlay.draw_line(a[0], a[1], b[0], b[1], color_bone)

    # Bone dots
    if bone_dot_enabled:
        for bone in overlay.BONE_POSITIONS.values():
            screen = bone_screens.get(bone)
            if screen:
                x, y = screen
                if draw_circle:
                    overlay.draw_circle(x, y, bone_dot_size, bone_dot_color)
                else:
                    overlay.draw_box(x - bone_dot_size, y - bone_dot_size, bone_dot_size * 2, bone_dot_size * 2, bone_dot_color)

                 
class BombStatus:
    def __init__(self, handle, base):
        self.handle = handle
        self.base = base
        self.offsets = Offsets()
        self.bomb_plant_time = 0
        self.bomb_defuse_time = 0
        # Caching to reduce memory reads and improve FPS
        self.cached_bomb_info = None
        self.last_update_time = 0
        self.update_interval = 0.05  # Update every 50ms (20 times per second) instead of every frame

    def read_bomb(self):
        # Use cached data if updated recently
        current_time = time.time()
        if self.cached_bomb_info is not None and (current_time - self.last_update_time) < self.update_interval:
            # Just update the timers using cached plant/defuse times
            try:
                info = self.cached_bomb_info.copy()
                if self.bomb_plant_time > 0:
                    info["time_remaining"] = max(0, round(info["timer_length"] - (current_time - self.bomb_plant_time), 1))
                if self.bomb_defuse_time > 0 and info.get("defuse_length"):
                    info["defuse_time"] = max(0, round(info["defuse_length"] - (current_time - self.bomb_defuse_time), 1))
                return info
            except:
                pass  # Fall through to full read
        
        # Full memory read (only every 50ms)
        try:
            c4_ptr = read_uint64(self.handle, self.base + self.offsets.dwPlantedC4)
            planted_flag = read_bytes(self.handle, self.base + self.offsets.dwPlantedC4 - 0x8, 1)[0]
            if not planted_flag:
                self.bomb_plant_time = 0
                self.bomb_defuse_time = 0
                self.cached_bomb_info = None
                self.last_update_time = current_time
                return None

            if self.bomb_plant_time == 0:
                self.bomb_plant_time = current_time

            c4class = read_uint64(self.handle, c4_ptr)
            node = read_uint64(self.handle, c4class + self.offsets.m_pGameSceneNode)
            pos = read_vec3(self.handle, node + self.offsets.m_vecAbsOrigin)

            timer_length = read_float(self.handle, c4class + self.offsets.m_flTimerLength)
            time_remaining = timer_length - (current_time - self.bomb_plant_time)
            time_remaining = max(0, time_remaining)

            defusing = read_bytes(self.handle, c4class + self.offsets.m_bBeingDefused, 1)[0]

            defuse_time = None
            defuse_length = None
            if defusing:
                if self.bomb_defuse_time == 0:
                    self.bomb_defuse_time = current_time
                defuse_length = read_float(self.handle, c4class + self.offsets.m_flDefuseLength)
                defuse_time = defuse_length - (current_time - self.bomb_defuse_time)
                defuse_time = max(0, defuse_time)
            else:
                self.bomb_defuse_time = 0

            # Cache the result
            self.cached_bomb_info = {
                "position": pos,
                "time_remaining": round(time_remaining, 1),
                "defuse_time": round(defuse_time, 1) if defuse_time is not None else None,
                "timer_length": timer_length,  # Store for interpolation
                "defuse_length": defuse_length  # Store for interpolation
            }
            self.last_update_time = current_time
            
            return self.cached_bomb_info

        except Exception as e:
            # print(f"[BombStatus] Error: {e}")  # Reduced spam
            return self.cached_bomb_info  # Return last known good data on error

def point_in_box(px, py, pos, w, h):
    return pos[0] <= px <= pos[0] + w and pos[1] <= py <= pos[1] + h

spectator_list_pos = [20, 300]  # initial x,y position on screen
spectator_list_dragging = False
spectator_list_drag_offset = [0, 0]


watermark_pos = [20, 20]
watermark_dragging = False
watermark_drag_offset = [0, 0]

# NEW: Map status draggable globals
map_status_pos = [20, 60]
map_status_dragging = False
map_status_drag_offset = [0, 0]

# Radar draggable globals
radar_dragging = False
radar_drag_offset = [0, 0]

def calculate_speed(vel):
    return math.sqrt(vel['x']**2 + vel['y']**2 + vel['z']**2)

def is_in_game(handle, base):
    pawn = safe_read_uint64(handle, base + Offsets.dwLocalPlayerPawn)
    return pawn != 0

def check_player_visibility(local_pos, entity_pos, vis_checker):
    """
    Check if a player is visible using external map parsing with VisCheck module.
    Returns True if the player is visible, False otherwise.
    
    Args:
        local_pos: Local player position (Vec3)
        entity_pos: Target entity position (Vec3)  
        vis_checker: VisCheck module instance
    """
    try:
        if not local_pos or not entity_pos or not vis_checker:
            return False
            
        # Check if vis_checker has a map loaded
        if not vis_checker.is_map_loaded():
            # If no map is loaded or loading, default to visible to not break ESP
            return True
            
        # Add small height offset to simulate eye level
        eye_offset = 64.0  # CS2 player eye height offset
        
        local_eye_pos = (local_pos.x, local_pos.y, local_pos.z + eye_offset)
        entity_eye_pos = (entity_pos.x, entity_pos.y, entity_pos.z + eye_offset)
        
        # Use VisCheck module to perform ray-triangle intersection
        is_visible = vis_checker.is_visible(local_eye_pos, entity_eye_pos)
        
        # Debug output to see what's happening (uncomment for debugging)
        # print(f"[VisCheck Debug] Map loaded: {vis_checker.is_map_loaded()}, Visibility: {is_visible}")
        
        # If vis_checker is not working properly, default to True (visible)
        if is_visible is None:
            print("[VisCheck Debug] Null result from vis_checker - defaulting to VISIBLE")
            return True
            
        return bool(is_visible)  # Ensure boolean return
        
    except Exception as e:
        print(f"[VisCheck Error] {e}")
        print("[VisCheck Debug] Exception occurred - defaulting to VISIBLE")
        return True

entity_traces = {}  # {entity_id: [Vec3, Vec3, ...]}

local_info_box_pos = [100, 400]
local_info_drag_offset = [0, 0]
local_info_dragging = False

def get_current_map_name(handle, matchmaking_base):
    """
    Read the current map name from matchmaking.dll using existing read_bytes function
    The map name is stored as a pointer to string, so we need to dereference it
    Returns the map name as string or None if failed
    """
    try:
        if not handle or not matchmaking_base:
            print(f"[Map Debug] Invalid handle ({handle}) or matchmaking_base ({hex(matchmaking_base) if matchmaking_base else 'None'})")
            return None
        
        # Compute the address where the map name pointer is stored
        map_name_ptr_address = matchmaking_base + DW_GAME_TYPES + DW_GAME_TYPES_MAP_NAME
        # print(f"[Map Debug] Reading pointer from: {hex(map_name_ptr_address)}")
        
        # Read the pointer (8 bytes on 64-bit)
        ptr_bytes = read_bytes(handle, map_name_ptr_address, 8)
        if not ptr_bytes:
            print(f"[Map Debug] Failed to read pointer")
            return None
            
        # Convert bytes to pointer value
        map_name_ptr = struct.unpack("Q", ptr_bytes)[0]  # Q = unsigned long long (64-bit)
        
        if map_name_ptr == 0 or map_name_ptr > 0x7FFFFFFFFFFF:
            print(f"[Map Debug] Invalid pointer: {hex(map_name_ptr)}")
            return None
            
        # print(f"[Map Debug] Following pointer to: {hex(map_name_ptr)}")
        
        # Now read the actual string from the pointer location
        string_bytes = read_bytes(handle, map_name_ptr, 128)
        if not string_bytes:
            # print(f"[Map Debug] Failed to read string from pointer")
            return None
            
        # Convert to string
        map_name = string_bytes.split(b'\x00')[0].decode('utf-8', errors='ignore')
        
        if map_name and len(map_name) >= 3 and not map_name.isspace():
            # print(f"[Map Debug] Successfully read map name: {map_name}")
            return map_name
        else:
            # Empty or invalid map name (probably not in game)
            # print(f"[Map Debug] Successfully read map name: <empty>")
            return "<empty>"
            
    except Exception as e:
        print(f"[Map Debug] Error reading map name: {e}")
        return None

def auto_map_loader(handle, matchmaking_base, vis_checker):
    """
    Automatically loads the correct map when CS2 map changes
    Only loads when detected map differs from currently loaded map
    """
    global last_map_check_time, current_detected_map
    
    current_time = time.time()
    if current_time - last_map_check_time >= 3.0:  # Check every 3 seconds (less frequent)
        last_map_check_time = current_time
        
        # Get current map from CS2 memory
        detected_map = get_current_map_name(handle, matchmaking_base)
        if not detected_map or detected_map == "<empty>":
            # No valid map detected (probably not in game) - ignore silently
            return
        
        # Get currently loaded map in VisCheck
        if vis_checker and vis_checker.is_map_loaded():
            loaded_map_path = vis_checker.get_current_map()
            # Extract map name from path (e.g., "maps/de_mirage.opt" -> "de_mirage")
            if loaded_map_path:
                loaded_map_name = os.path.basename(loaded_map_path).replace('.opt', '')
            else:
                loaded_map_name = None
        else:
            loaded_map_name = None
        
        # Compare detected vs loaded
        if detected_map != current_detected_map:
            print(f"[Auto-Map] Detected map change: {current_detected_map} -> {detected_map}")
            current_detected_map = detected_map
        
        if detected_map != loaded_map_name:
            # Map mismatch - need to load correct map
            target_map_file = f"{detected_map}.opt"
            target_map_path = os.path.join("maps", target_map_file)
            
            if os.path.exists(target_map_path):
                print(f"[Auto-Map] Auto-loading map: {detected_map} (was: {loaded_map_name})")
                
                # Trigger automatic map load through config
                from Process.config import Config
                setattr(Config, 'visibility_map_path', target_map_path)
                setattr(Config, 'visibility_map_reload_needed', True)
                
            else:
                print(f"[Auto-Map] Map file not found: {target_map_path}")
                print(f"[Auto-Map] Detected: {detected_map}, Loaded: {loaded_map_name}")
        else:
            # Maps match - no action needed
            if current_detected_map != detected_map:  # Only print on first detection
                print(f"[Auto-Map] Map synchronized: {detected_map}")

def debug_map_check(handle, matchmaking_base):
    """
    Debug function that checks and prints current map name every second  
    """
    global last_map_check_time, current_detected_map
    
    current_time = time.time()
    if current_time - last_map_check_time >= 1.0:  # Check every second
        last_map_check_time = current_time
        
        map_name = get_current_map_name(handle, matchmaking_base)
        if map_name and map_name != "<empty>":
            current_detected_map = map_name
            # print(f"[Map Debug] Current map: {map_name}")
        elif map_name == "<empty>":
            # Silent when not in game
            pass
        else:
            print(f"[Map Debug] Failed to read map name")

def load_map_threaded(vis_checker, map_path):
    """Load map in background thread to prevent GUI blocking"""
    global map_loading_in_progress
    
    def load_worker():
        global map_loading_in_progress
        try:
            map_loading_in_progress = True
            print(f"[VisCheck] Background loading: {map_path}")
            
            # Add small delay to prevent issues
            time.sleep(0.1)
            
            if vis_checker.load_map(map_path):
                print(f"[VisCheck] Background load complete: {map_path}")
            else:
                print(f"[VisCheck] Background load failed: {map_path}")
                    
        except Exception as e:
            print(f"[VisCheck] Background load error: {e}")
        finally:
            map_loading_in_progress = False
            print(f"[VisCheck] Background loading finished for: {map_path}")
    
    # Start loading in background thread
    thread = threading.Thread(target=load_worker, daemon=True)
    thread.start()
    print(f"[VisCheck] Started background thread for: {map_path}")

# === World-items FPS optimizer ==============================================
# Drop this near the other globals in esp.py

_WORLD_SCAN_INTERVAL_SEC = 0.15   # rescan every 150ms
_OWNER_RESOLVE_TTL_SEC   = 0.30   # cache owner result for 300ms
_TYPE_STR_TTL_SEC        = 5.00   # refresh designer names occasionally

_world_items_cache = []           # [(screen_pos, origin, type_str)]
_world_items_cache_until = 0.0

_item_type_cache = {}             # {entity_addr: (type_str, expiry_time)}
_owner_resolve_cache = {}         # {entity_addr: (is_equipped_bool, expiry_time)}


def _cached_now():
    return time.perf_counter()


def _read_type_str_cached(handle, entity_addr):
    """Read designer name once per 5s per entity."""
    now = _cached_now()
    hit = _item_type_cache.get(entity_addr)
    if hit and hit[1] > now:
        return hit[0]

    type_str = None
    try:
        item_info = safe_read_uint64(handle, entity_addr + 0x10)
        if item_info:
            type_ptr = safe_read_uint64(handle, item_info + 0x20)
            if type_ptr:
                raw = read_bytes(handle, type_ptr, 64)
                s = raw.split(b'\x00', 1)[0].decode('utf-8', 'ignore')
                if s:
                    type_str = s
    except Exception:
        pass

    if not type_str:
        # cache negative result briefly to avoid spamming reads
        _item_type_cache[entity_addr] = ("", _cached_now() + 0.75)
        return ""

    _item_type_cache[entity_addr] = (type_str, now + _TYPE_STR_TTL_SEC)
    return type_str


def _is_equipped_weapon_cached(handle, entity_list, entity_addr):
    """Return True if this weapon is clearly owned by a valid pawn. Cached for 300ms."""
    now = _cached_now()
    hit = _owner_resolve_cache.get(entity_addr)
    if hit and hit[1] > now:
        return hit[0]

    equipped = False
    try:
        owner_handle = read_int(handle, entity_addr + Offsets.m_hOwnerPawn) & 0x7FFF
        if owner_handle != 0x7FFF:
            pawn_list_entry = safe_read_uint64(handle, entity_list + ((owner_handle >> 9) * 8) + 16)
            if pawn_list_entry:
                pawn = safe_read_uint64(handle, pawn_list_entry + (112 * (owner_handle & 0x1FF)))
                if pawn:
                    equipped = True
    except Exception:
        equipped = False

    _owner_resolve_cache[entity_addr] = (equipped, now + _OWNER_RESOLVE_TTL_SEC)
    return equipped


def _features_active(cfg):
    """If nothing is enabled, skip scanning altogether."""
    return any([
        getattr(cfg, "dropped_weapon_esp_enabled", True),
        getattr(cfg, "projectile_esp_enabled", True),
        getattr(cfg, "chicken_esp_enabled", True),
        getattr(cfg, "hostage_esp_enabled", True),
        getattr(cfg, "bomb_esp_enabled", True),
    ])


def _scan_world_items_once(handle, base, matrix, overlay, cfg):
    """One heavy scan pass, called at most every WORLD_SCAN_INTERVAL_SEC."""
    entity_list = safe_read_uint64(handle, base + Offsets.dwEntityList)
    if not entity_list:
        return []

    items = []

    # Dynamic cap: trim work if some features are off
    max_entities = getattr(cfg, "max_entities_esp", 1024)
    if not getattr(cfg, "projectile_esp_enabled", True):
        max_entities = min(max_entities, 512)
    if not getattr(cfg, "dropped_weapon_esp_enabled", True):
        max_entities = min(max_entities, 768)

    # Local aliases and rotating scan window to distribute cost
    o = Offsets
    sru64 = safe_read_uint64
    rvec3 = read_vec3
    w2s = world_to_screen
    W, H = overlay.width, overlay.height
    start_idx = 64
    end_idx = max_entities
    phase = getattr(_scan_world_items_once, "phase", 0)
    mid_idx = start_idx + max(0, (end_idx - start_idx) // 2)
    if end_idx > start_idx:
        scan_start, scan_end = (start_idx, mid_idx) if phase == 0 else (mid_idx, end_idx)
        _scan_world_items_once.phase = 1 - phase
    else:
        scan_start, scan_end = (start_idx, end_idx)

    # Scan only a slice per call (rest will be scanned next refresh)
    for i in range(scan_start, scan_end):
        try:
            list_entry = sru64(handle, entity_list + (8 * ((i & 0x7FFF) >> 9) + 16))
            if not list_entry:
                continue

            ent = sru64(handle, list_entry + (112 * (i & 0x1FF)))
            if not ent:
                continue

            # Read scene node and position
            node = sru64(handle, ent + o.m_pGameSceneNode)
            if not node:
                continue
            pos = rvec3(handle, node + o.m_vecAbsOrigin)
            if not pos or not pos.x:
                continue

            # Compute once; skip offscreen early
            scr = w2s(matrix, pos, W, H)
            if not scr:
                continue

            # Type string with cache (read only for on-screen items)
            t = _read_type_str_cached(handle, ent)
            if not t:
                t = f"entity_{i}"

            # If it's a weapon, skip equipped ones
            if t.startswith("weapon_"):
                if _is_equipped_weapon_cached(handle, entity_list, ent):
                    continue

            items.append((scr, pos, t))
        except Exception:
            continue

    return items
# ============================================================================


def draw_bomb_carrier_esp(handle, base, entities, overlay, cfg):
    """Draw ESP indicator on players carrying the bomb"""
    try:
        if not getattr(cfg, "bomb_carrier_esp_enabled", True):
            return
        
        entity_list = safe_read_uint64(handle, base + Offsets.dwEntityList)
        if not entity_list:
            return
        
        for ent in entities:
            try:
                if not ent or not hasattr(ent, 'pawn') or not ent.pawn:
                    continue
                
                # Check if player has the bomb in their inventory
                # Read weapon services
                weapon_services = safe_read_uint64(handle, ent.pawn + Offsets.m_pWeaponServices)
                if not weapon_services:
                    continue
                
                # Read weapon handles array (MyWeapons offset)
                # Typically at weapon_services + 0x8 or nearby
                has_bomb = False
                
                # Check multiple weapon slots (0-4 typically covers all weapons)
                for slot in range(5):
                    try:
                        weapon_handle = read_int(handle, weapon_services + 0x8 + (slot * 0x4))
                        if not weapon_handle or weapon_handle == -1:
                            continue
                        
                        # Read weapon entity
                        weapon_index = weapon_handle & 0x7FFF
                        weapon_entry = safe_read_uint64(handle, entity_list + (8 * ((weapon_index >> 9) & 0x3F) + 16))
                        if not weapon_entry:
                            continue
                        
                        weapon_entity = safe_read_uint64(handle, weapon_entry + (112 * (weapon_index & 0x1FF)))
                        if not weapon_entity:
                            continue
                        
                        # Check if it's the bomb
                        weapon_name = get_weapon_name_from_entity(handle, weapon_entity)
                        if weapon_name and "c4" in weapon_name.lower():
                            has_bomb = True
                            break
                    except:
                        continue
                
                if has_bomb and hasattr(ent, 'head2d') and ent.head2d:
                    # Player has the bomb! Draw indicator
                    color = getattr(cfg, "bomb_carrier_esp_color", (255, 200, 0))
                    text_y = ent.head2d["y"] - 30  # Above head
                    overlay.draw_text("💣 BOMB", ent.head2d["x"], text_y, color, 14, centered=True)
                
            except Exception:
                continue
                
    except Exception as e:
        print(f"[Bomb Carrier ESP Error] {e}")

def esp_weapon(handle, pawn_addr):
    try:
        weapon_pointer = safe_read_uint64(handle, pawn_addr + Offsets.m_pClippingWeapon)
        if not weapon_pointer:
            return None

        # New way: read weapon name directly from entity
        return get_weapon_name_from_entity(handle, weapon_pointer)
    except Exception as e:
        print(f"[esp_weapon] Error: {e}")
        return None


def cleanup_vischeck_resources():
    """Cleanup VisCheck resources on exit"""
    global optimized_vischeck
    if optimized_vischeck:
        try:
            optimized_vischeck.cleanup()
        except:
            pass
        optimized_vischeck = None

def get_vischeck_cache_stats():
    """Get VisCheck cache statistics for display"""
    if optimized_vischeck:
        try:
            return optimized_vischeck.get_cache_stats()
        except:
            pass
    return {"total_entries": 0, "valid_entries": 0, "cache_dir_size_mb": 0.0}

# Global vis_checker so aimbot can access it
vis_checker = None

def main():
    global vis_checker  # Make it accessible to other modules
    global win32api
    
    hwnd = windll.user32.FindWindowW(None, "Counter-Strike 2")
    if not hwnd:
        return print("[!] CS2 not running.")

    pid = wintypes.DWORD()
    windll.user32.GetWindowThreadProcessId(hwnd, byref(pid))
    handle = windll.kernel32.OpenProcess(PROCESS_PERMISSIONS, False, pid.value)
    
    # Initialize unified memory interface with kernel mode support
    print(f"[Memory] Initializing memory interface for PID {pid.value}")
    try:
        memory = MemoryInterface(pid.value, handle, Config)
        set_memory_interface(memory)  # Set global memory interface
        if memory.is_kernel_mode_active():
            print("[Memory] ✓ Kernel mode active via NeacController")
        else:
            print("[Memory] ⚠ Using usermode memory access")
    except Exception as e:
        print(f"[Memory] Failed to initialize memory interface: {e}")
        return
    
    # ESP state tracking
    esp_active_count = 0
    last_entity_count = 0
    last_esp_status_time = time.time()
    
    # Initialize VisCheck module for map-based visibility checking (global so aimbot can use it)
    if VISCHECK_AVAILABLE:
        try:
            # Create VisCheck instance
            vis_checker = vischeck.VisCheck()
            print("[VisCheck] Module initialized")
            
            # Try to detect current map from CS2 and load it
            detected_map = None
            try:
                # Get matchmaking base for map detection
                base = None
                for module_name in ["matchmaking.dll", "matchmaking"]:
                    base = vis_checker.get_module_base(memory.process_id, module_name) if hasattr(vis_checker, 'get_module_base') else None
                    if base:
                        break
                
                if not base:
                    # Try to get it from the renderer or use a different method
                    import win32process
                    import win32api
                    try:
                        modules = win32process.EnumProcessModules(handle)
                        for module in modules:
                            name = win32process.GetModuleFileNameEx(handle, module).lower()
                            if 'matchmaking' in name:
                                base = module
                                break
                    except:
                        pass
                
                if base:
                    detected_map = get_current_map_name(handle, base)
                    if detected_map and detected_map != "<empty>":
                        print(f"[VisCheck] Detected current map: {detected_map}")
                        global current_detected_map
                        current_detected_map = detected_map
                        
                        # Try to load the detected map
                        map_file = f"{detected_map}.opt"
                        map_path = os.path.join("maps", map_file)
                        
                        if os.path.exists(map_path):
                            if vis_checker.load_map(map_path):
                                print(f"[VisCheck] Auto-loaded detected map: {detected_map}")
                                setattr(Config, 'visibility_map_file', map_file)
                                setattr(Config, 'visibility_map_path', map_path)
                                setattr(Config, 'visibility_map_loaded', True)
                            else:
                                print(f"[VisCheck] Failed to load detected map: {detected_map}")
                        else:
                            print(f"[VisCheck] Map file not found for detected map: {map_path}")
                    else:
                        print("[VisCheck] No map detected or not in-game - no auto-loading")
                else:
                    print("[VisCheck] Could not find matchmaking.dll base - no map detection")
                    
            except Exception as e:
                print(f"[VisCheck] Map detection failed: {e}")
            
            # Fallback: only load configured map if no detection worked
            if not detected_map or detected_map == "<empty>":
                initial_map = getattr(Config, 'visibility_map_file', None)
                if initial_map and initial_map != 'de_mirage.opt':  # Don't load default static map
                    # Try different possible paths
                    possible_paths = [
                        initial_map,  # Direct path
                        os.path.join("maps", initial_map),  # maps subdirectory
                        os.path.join(".", initial_map),  # current directory
                        os.path.join("..", initial_map)  # parent directory
                    ]
                
                    map_loaded = False
                    for map_path in possible_paths:
                        if os.path.exists(map_path):
                            print(f"[VisCheck] Starting async load of: {map_path}")
                            
                            # Check map file integrity first
                            try:
                                file_size = os.path.getsize(map_path)
                                print(f"[VisCheck] Map file size: {file_size:,} bytes")
                                
                                if file_size < 1000:  # Suspiciously small map file
                                    print(f"[VisCheck] Map file too small, skipping: {map_path}")
                                    continue
                                    
                            except Exception as e:
                                print(f"[VisCheck] Cannot read map file: {e}")
                                continue
                        
                            # Try synchronous load first (safer)
                            try:
                                print(f"[VisCheck] Trying synchronous load first...")
                                if vis_checker.load_map(map_path):
                                    print(f"[VisCheck] Synchronous load successful: {map_path}")
                                    setattr(Config, 'visibility_map_path', map_path)
                                    setattr(Config, 'visibility_map_loaded', True)
                                    map_loaded = True
                                    break
                                else:
                                    print(f"[VisCheck] Synchronous load failed, trying async...")
                            except Exception as e:
                                print(f"[VisCheck] Synchronous load error: {e}")
                                print(f"[VisCheck] Trying async as fallback...")
                        
                            # If sync failed, try async with extra protection
                            try:
                                print(f"[VisCheck] Attempting async load with protection...")
                                
                                # Create a fresh VisCheck instance to avoid state issues
                                temp_checker = vischeck.VisCheck()
                                
                                if temp_checker.load_map(map_path):
                                    print(f"[VisCheck] Map loaded successfully: {map_path}")
                                    vis_checker = temp_checker
                                    setattr(Config, 'visibility_map_path', map_path)
                                    setattr(Config, 'visibility_map_loaded', True)
                                    map_loaded = True
                                    break
                                else:
                                    print(f"[VisCheck] Failed to load map: {map_path}")
                            except Exception as e:
                                print(f"[VisCheck] CRITICAL ERROR loading {map_path}: {e}")
                                print(f"[VisCheck] This map file causes crashes - skipping")
                                continue  # Try next map path
                
                    if not map_loaded:
                        print(f"[VisCheck] Could not find map file '{initial_map}' in any location")
                        print(f"[VisCheck] Searched: {possible_paths}")
                else:
                    print("[VisCheck] No valid map file configured (skipping default)")
            else:
                print("[VisCheck] No initial map configured - waiting for user selection")
                
        except Exception as e:
            print(f"[VisCheck Error] Failed to initialize module: {e}")
            print("[VisCheck] Visibility ESP will default to NOT VISIBLE")
            vis_checker = None
    else:
        print("[VisCheck] Module not available - Visibility ESP will be disabled")
        print("[Info] To enable Visibility ESP:")
        print("  1. Compile vischeck.pyd for your Python version")
        print("  2. Place vischeck.pyd in the main directory")
        print("  3. Place your map .opt file (e.g., de_mirage.opt) in the main directory")

    overlay = Overlay("GFusion")
    base = overlay.get_module_base(pid.value, "client.dll")
    matchmaking_base = overlay.get_module_base(pid.value, "matchmaking.dll")
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

    def handle_map_status_drag():
        global map_status_dragging, map_status_drag_offset
        map_status_dragging, map_status_drag_offset = handle_dragging(
            map_status_dragging, map_status_pos, map_status_drag_offset, 240, 40
        )

    def handle_local_info_drag():
        global local_info_dragging, local_info_drag_offset
        box_width = 240
        local_info_dragging, local_info_drag_offset = handle_dragging(
            local_info_dragging, local_info_box_pos, local_info_drag_offset, box_width, 24
        )

    def handle_radar_drag():
        global radar_dragging, radar_drag_offset
        if not getattr(Config, "radar_enabled", False):
            return
        radar_size = getattr(Config, "radar_size", 200)
        radar_pos = [getattr(Config, "radar_x", 20), getattr(Config, "radar_y", 20)]
        radar_dragging, radar_drag_offset = handle_dragging(
            radar_dragging, radar_pos, radar_drag_offset, radar_size, radar_size
        )
        Config.radar_x = radar_pos[0]
        Config.radar_y = radar_pos[1]

    # Error tracking for stability
    consecutive_errors = 0
    max_consecutive_errors = 10
    last_error_time = time.time()
    error_cooldown = 5.0  # seconds between error resets
    
    while True:
        try:
            # Windows message pump every tick
            msg = wintypes.MSG()
            while windll.user32.PeekMessageW(byref(msg), 0, 0, 0, win32con.PM_REMOVE):
                windll.user32.TranslateMessage(byref(msg))
                windll.user32.DispatchMessageW(byref(msg))

            # Begin a new frame when the renderer's pacing allows it.
            if not overlay.begin_scene():
                # Not time to render yet; yield to avoid busy-wait and try again.
                time.sleep(0)
                continue

            if not is_in_game(handle, base):
                overlay.end_scene()
                time.sleep(1)
                continue
            
            # Reset error counter on successful iteration
            current_time = time.time()
            if current_time - last_error_time > error_cooldown:
                consecutive_errors = 0

            # Cache config reference first
            cfg = Config
            
            # Auto-load correct maps based on CS2 detection
            auto_map_loader(handle, matchmaking_base, vis_checker)
            
            # Handle dynamic map switching (simplified - back to sync for debugging)
            if vis_checker and getattr(cfg, 'visibility_map_reload_needed', False):
                try:
                    map_path = getattr(cfg, 'visibility_map_path', '')
                    if map_path and os.path.exists(map_path):
                        print(f"[VisCheck] Switching to map: {map_path}")
                        
                        # Check if map is already loaded (compare full paths)
                        current_map = vis_checker.get_current_map() if vis_checker.is_map_loaded() else ""
                        if current_map == map_path:
                            print(f"[VisCheck] Map already loaded: {map_path}")
                        else:
                            # Unload current map first if loaded
                            if vis_checker.is_map_loaded():
                                print(f"[VisCheck] Unloading current map: {current_map}")
                                vis_checker.unload_map()
                            
                            # Load new map
                            print(f"[VisCheck] Loading new map: {map_path}")
                            if vis_checker.load_map(map_path):
                                print(f"[VisCheck] Successfully loaded: {map_path}")
                                setattr(cfg, 'visibility_map_loaded', True)
                            else:
                                print(f"[VisCheck] Failed to load: {map_path}")
                                setattr(cfg, 'visibility_map_loaded', False)
                    else:
                        # Unload map if no valid path
                        if vis_checker.is_map_loaded():
                            current_map = vis_checker.get_current_map()
                            print(f"[VisCheck] Unloading map: {current_map}")
                            vis_checker.unload_map()
                            setattr(cfg, 'visibility_map_loaded', False)
                    
                    # Clear reload flag
                    setattr(cfg, 'visibility_map_reload_needed', False)
                    
                except Exception as e:
                    print(f"[VisCheck] Error during dynamic map switch: {e}")
                    setattr(cfg, 'visibility_map_reload_needed', False)

            # Cache all config flags once
            flags = {

                # =======================================================================
                # ───────────────────────────── COLOR FLAGS ──────────────────────────────
                # =======================================================================

                ## --- Team / Box Colors ---
                "color_box_t": getattr(cfg, "color_box_t", (255, 0, 0)),
                "color_box_ct": getattr(cfg, "color_box_ct", (0, 0, 255)),
                "color_box_dead_t": getattr(cfg, "color_box_dead_t", (128, 0, 0)),
                "color_box_dead_ct": getattr(cfg, "color_box_dead_ct", (0, 0, 128)),

                # Synonyms (backwards compatibility)
                "color_dead_t": getattr(cfg, "color_box_dead_t", (128, 0, 0)),
                "color_dead_ct": getattr(cfg, "color_box_dead_ct", (0, 0, 128)),

                ## --- Box Visibility ---
                "color_box_visible_ct": getattr(cfg, "color_box_visible_ct",
                                                getattr(cfg, "color_box_visible", (0, 255, 0))),
                "color_box_visible_t": getattr(cfg, "color_box_visible_t",
                                               getattr(cfg, "color_box_visible", (0, 255, 0))),
                "color_box_invisible_ct": getattr(cfg, "color_box_invisible_ct",
                                                  getattr(cfg, "color_box_not_visible", (255, 0, 0))),
                "color_box_invisible_t": getattr(cfg, "color_box_invisible_t",
                                                 getattr(cfg, "color_box_not_visible", (255, 0, 0))),

                ## --- Skeleton Visibility ---
                "color_skeleton_visible_ct": getattr(cfg, "color_skeleton_visible_ct",
                                                     getattr(cfg, "color_skeleton_visible", (0, 255, 0))),
                "color_skeleton_visible_t": getattr(cfg, "color_skeleton_visible_t",
                                                    getattr(cfg, "color_skeleton_visible", (0, 255, 0))),
                "color_skeleton_invisible_ct": getattr(cfg, "color_skeleton_invisible_ct",
                                                       getattr(cfg, "color_skeleton_not_visible", (255, 0, 0))),
                "color_skeleton_invisible_t": getattr(cfg, "color_skeleton_invisible_t",
                                                      getattr(cfg, "color_skeleton_not_visible", (255, 0, 0))),

                ## --- Text/General Colors ---
                "color_name": getattr(cfg, "color_name", (255, 255, 255)),
                "color_head": getattr(cfg, "color_head", (255, 0, 0)),
                "color_weapon_text": getattr(cfg, "color_weapon_text", (255, 255, 255)),
                "color_line": getattr(cfg, "color_line", (255, 255, 255)),
                "color_hp_text": getattr(cfg, "color_hp_text", (0, 255, 0)),
                "color_armor_text": getattr(cfg, "color_armor_text", (0, 0, 255)),
                "color_distance": getattr(cfg, "color_distance", (255, 255, 255)),
                "color_flash_scope": getattr(cfg, "color_flash_scope", (255, 255, 255)),
                "color_spectators": getattr(cfg, "color_spectators", (180, 180, 180)),

                ## --- Local Info Box Colors ---
                "color_local_box_background": getattr(cfg, "color_local_box_background", (30, 30, 30)),
                "color_local_box_border": getattr(cfg, "color_local_box_border", (100, 100, 100)),
                "color_local_velocity_text": getattr(cfg, "color_local_velocity_text", (255, 255, 255)),
                "color_local_speed_text": getattr(cfg, "color_local_speed_text", (180, 255, 180)),
                "color_local_coords_text": getattr(cfg, "color_local_coords_text", (200, 200, 255)),

                ## --- Velocity / Speed Colors ---
                "velocity_esp_color": getattr(cfg, "velocity_esp_color", (255, 255, 255)),
                "velocity_text_color": getattr(cfg, "velocity_text_color", (255, 255, 255)),
                "speed_esp_color": getattr(cfg, "speed_esp_color", (255, 255, 255)),

                ## --- Money ESP Colors ---
                "color_money_text": getattr(cfg, "color_money_text", (0, 255, 255)),

                ## --- Visibility text ---
                "color_visible_text": getattr(cfg, "color_visible_text", (0, 255, 0)),
                "color_not_visible_text": getattr(cfg, "color_not_visible_text", (255, 0, 0)),


                # =======================================================================
                # ───────────────────────────── ESP FEATURE FLAGS ───────────────────────
                # =======================================================================

                ## Core ESP
                "box_esp_enabled": getattr(cfg, "show_box_esp", False),
                "name_esp_enabled": getattr(cfg, "name_esp_enabled", True),
                "skeleton_esp_enabled": getattr(cfg, "skeleton_esp_enabled", False),
                "weapon_esp_enabled": getattr(cfg, "weapon_esp_enabled", True),

                ## Additional Info ESP
                "healthbar_enabled": getattr(cfg, "healthbar_enabled", False),
                "armorbar_enabled": getattr(cfg, "armorbar_enabled", False),
                "health_esp_enabled": getattr(cfg, "health_esp_enabled", False),
                "armor_esp_enabled": getattr(cfg, "armor_esp_enabled", False),
                "distance_esp_enabled": getattr(cfg, "distance_esp_enabled", False),

                ## Special ESP
                "flash_esp_enabled": getattr(cfg, "flash_esp_enabled", False),
                "scope_esp_enabled": getattr(cfg, "scope_esp_enabled", False),
                "bomb_esp_enabled": getattr(cfg, "bomb_esp_enabled", False),
                "trace_esp_enabled": getattr(cfg, "trace_esp_enabled", True),
                "trace_esp_max_points": getattr(cfg, "trace_esp_max_points", 150),
                "visibility_esp_enabled": getattr(cfg, "visibility_esp_enabled", False),
                "visibility_text_enabled": getattr(cfg, "visibility_text_enabled", True),

                ## Filters
                "esp_show_enemies_only": getattr(cfg, "esp_show_enemies_only", True),
                "esp_show_team_only": getattr(cfg, "esp_show_team_only", False),

                ## Head ESP
                "head_esp_enabled": getattr(cfg, "head_esp_enabled", False),
                "head_esp_shape": getattr(cfg, "head_esp_shape", "circle").lower(),

                ## Line ESP
                "line_esp_enabled": getattr(cfg, "line_esp_enabled", False),
                "line_esp_position": getattr(cfg, "line_esp_position", "bottom").lower(),

                ## Coordinates ESP
                "coordinates_esp_enabled": getattr(cfg, "coordinates_esp_enabled", True),


                # =======================================================================
                # ─────────────────────────── BONE DOT ESP OPTIONS ──────────────────────
                # =======================================================================

                ## New system (RenderBoneESP)
                "bone_dot_esp_enabled": getattr(cfg, "bone_dot_esp_enabled", False),
                "bone_dot_shape": getattr(cfg, "bone_dot_shape", "circle").lower(),
                "bone_dot_size": getattr(cfg, "bone_dot_size", 6),
                "bone_dot_color": getattr(cfg, "bone_dot_color", (255, 0, 255)),

                ## Backwards compatibility
                "bone_esp_enabled": getattr(cfg, "bone_dot_esp_enabled", False),
                "bone_esp_shape": getattr(cfg, "bone_dot_shape", "circle").lower(),
                "bone_esp_size": getattr(cfg, "bone_dot_size", 6),
                "bone_esp_color": getattr(cfg, "bone_dot_color", (255, 0, 255)),


                # =======================================================================
                # ───────────────────────────── OTHER FEATURES ──────────────────────────
                # =======================================================================

                "grenade_prediction_enabled": getattr(cfg, "grenade_prediction_enabled", True),
                "noflash_enabled": getattr(cfg, "noflash_enabled", False),

                "fov_circle_enabled": getattr(cfg, "fov_circle_enabled", True),
                "draw_crosshair_enabled": getattr(cfg, "draw_crosshair_enabled", True),
                "crosshair_size": getattr(cfg, "crosshair_size", 6),
                "crosshair_color": getattr(cfg, "crosshair_color", (255, 255, 255)),

                "FOV": getattr(cfg, "FOV", 5.0),

                ## Velocity / Speed ESP
                "velocity_esp": getattr(cfg, "velocity_esp", False),
                "speed_esp": getattr(cfg, "speed_esp", False),
                "velocity_esp_text": getattr(cfg, "velocity_esp_text", False),

                ## Money ESP
                "money_esp_enabled": getattr(cfg, "money_esp_enabled", True),
                "money_esp_text": getattr(cfg, "money_esp_text", True),


                # =======================================================================
                # ───────────────────────── OVERLAY / UI ELEMENTS ───────────────────────
                # =======================================================================

                "spectator_list_enabled": getattr(cfg, "spectator_list_enabled", True),
                "watermark_enabled": getattr(cfg, "watermark_enabled", True),

                "show_local_info_box": getattr(cfg, "show_local_info_box", True),
            }


            matrix = read_matrix(handle, base + Offsets.dwViewMatrix)
            local_pos = get_local_player()

            if getattr(cfg, "panic_key_enabled", True):
                if win32api.GetAsyncKeyState(int(cfg.panic_key)) & 0x1:
                    cfg.panic_mode_active = not cfg.panic_mode_active
                    print(f"[PANIC] Panic mode {'ENABLED' if cfg.panic_mode_active else 'DISABLED'}")



            if cfg.panic_mode_active:
                for key in flags.keys():
                    if key.endswith("_enabled"):
                        flags[key] = False
                        
            if getattr(cfg, "show_overlay_fps", False):
                fps_text = f"FPS: {overlay.current_fps}"
                overlay.draw_text(fps_text, overlay.width - 100, 20, (0, 255, 0), 16)

            # Watermark
            if flags["watermark_enabled"]:
                handle_watermark_drag()
                x, y = watermark_pos

                # Adjust height for extra text line
                overlay.draw_filled_rect(x, y, 260, 40, getattr(cfg, "color_local_box_background", (30, 30, 30)))
                overlay.draw_box(x, y, 260, 40, getattr(cfg, "color_local_box_border", (100, 100, 100)))

                # First line: FPS
                overlay.draw_text(f"GFusion | FPS: {overlay.current_fps}", x + 6, y + 4, (255, 255, 255), 14)

                # Second line: Credit
                overlay.draw_text("Made by Cr0mb & SameOldMistakes", x + 6, y + 20, (200, 200, 200), 12)

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

            # NEW: Map/VisCheck status
            if getattr(cfg, "show_map_status_box", True):
                handle_map_status_drag()
                draw_map_status_box(overlay, vis_checker)

            if flags["noflash_enabled"]:
                try:
                    local_pawn = safe_read_uint64(handle, base + Offsets.dwLocalPlayerPawn)
                    if local_pawn:
                        flash_addr = local_pawn + Offsets.m_flFlashDuration
                        cur_val = read_float(handle, flash_addr)
                        write_float(handle, flash_addr, 0.0)
                        new_val = read_float(handle, flash_addr)
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

            # Get local team safely
            try:
                local_pawn = safe_read_uint64(handle, base + Offsets.dwLocalPlayerPawn)
                if not local_pawn:
                    overlay.end_scene()
                    continue
                local_team = read_int(handle, local_pawn + Offsets.m_iTeamNum)
                
                # Get spectated player if in spectator mode
                spectated_pawn = None
                try:
                    local_controller = safe_read_uint64(handle, base + Offsets.dwLocalPlayerController)
                    if local_controller:
                        observer_mode = read_int(handle, local_controller + Offsets.m_iObserverMode)
                        # Observer modes: 0 = None, 1 = Deathcam, 4 = In-Eye, 5 = Chase, 6 = Roaming
                        if observer_mode in [4, 5, 6]:  # Spectating someone
                            observer_target = read_int(handle, local_controller + Offsets.m_hObserverTarget)
                            if observer_target > 0:
                                # Get the spectated player's pawn
                                entity_list = safe_read_uint64(handle, base + Offsets.dwEntityList)
                                target_index = observer_target & 0x7FFF
                                target_list_entry = safe_read_uint64(handle, entity_list + (8 * ((target_index >> 9) & 0x3F) + 16))
                                if target_list_entry:
                                    target_controller = safe_read_uint64(handle, target_list_entry + (112 * (target_index & 0x1FF)))
                                    if target_controller:
                                        spectated_pawn_handle = safe_read_uint64(handle, target_controller + Offsets.m_hPlayerPawn)
                                        if spectated_pawn_handle:
                                            spectated_index = spectated_pawn_handle & 0x7FFF
                                            spectated_list_entry = safe_read_uint64(handle, entity_list + (8 * ((spectated_index >> 9) & 0x3F) + 16))
                                            if spectated_list_entry:
                                                spectated_pawn = safe_read_uint64(handle, spectated_list_entry + (112 * (spectated_index & 0x1FF)))
                except:
                    pass  # Not spectating or error reading
                
            except Exception as e:
                print(f"[ESP Error] Failed to read local team: {e}")
                overlay.end_scene()
                continue

            # Process entities with error handling
            try:
                entities = get_entities(handle, base)
            except Exception as e:
                print(f"[ESP Error] Failed to get entities: {e}")
                overlay.end_scene()
                continue

            # --- Radar ---
            try:
                if getattr(cfg, "radar_enabled", False) and local_pos:
                    handle_radar_drag()
                    local_yaw = read_float(handle, base + Offsets.dwViewAngles + 4)
                    radar_module.draw_radar(overlay, local_pos, local_team, local_yaw, entities)
                    radar_module.draw_radar_label(overlay)
            except Exception as e:
                print(f"[Radar Error] {e}")

            # ESP status tracking
            current_time = time.time()
            if current_time - last_esp_status_time > 10:  # Every 10 seconds
                esp_enabled_flags = [
                    flags.get("box_esp_enabled", False),
                    flags.get("name_esp_enabled", False),
                    flags.get("head_esp_enabled", False),
                    flags.get("skeleton_esp_enabled", False)
                ]
                esp_enabled_count = sum(esp_enabled_flags)
                print(f"[ESP Status] Entities: {len(entities)}, ESP features enabled: {esp_enabled_count}/4")
                last_esp_status_time = current_time

            for ent in entities:
                try:
                    # Skip local player (check by pawn address)
                    if ent.pawn == local_pawn:
                        continue
                    
                    # Skip spectated player (don't draw ESP on who you're watching)
                    if spectated_pawn and ent.pawn == spectated_pawn:
                        continue
                    
                    is_enemy = ent.team != local_team
                    is_teammate = ent.team == local_team
                    if (flags["esp_show_enemies_only"] and not is_enemy) or (flags["esp_show_team_only"] and not is_teammate):
                        continue

                    # Configurable death handling
                    if not getattr(Config, "draw_dead_entities", True) and ent.hp <= 0:
                        continue

                    # Keep the WTS (world-to-screen) check separate
                    if not ent.wts(matrix, overlay.width, overlay.height):
                        continue

                    # --- Visible Only Toggle (safe version) ---
                    if getattr(cfg, "visible_only_esp_enabled", False):
                        is_visible = True  # default fallback
                        if vis_checker and hasattr(vis_checker, "is_map_loaded") and vis_checker.is_map_loaded():
                            try:
                                # Use spectated player's position if spectating, otherwise local player
                                if spectated_pawn:
                                    view_pos = read_vec3(handle, spectated_pawn + Offsets.m_vOldOrigin)
                                else:
                                    view_pos = get_local_player()
                                
                                is_visible = check_player_visibility(view_pos, ent.pos, vis_checker)
                            except Exception as e:
                                print(f"[ESP] Visibility check error: {e}")
                                is_visible = True  # fail-safe: still draw if check fails
                        if not is_visible:
                            continue  # skip invisible players only when map is valid

                    # Count active ESP draws
                    esp_active_count += 1

                except Exception as e:
                    print(f"[ESP Error] Entity processing error: {e}")
                    continue

                try:
                    h = (ent.feet2d["y"] - ent.head2d["y"]) * 1.08
                    w = h / 2
                    x, y = ent.head2d["x"] - w / 2, ent.head2d["y"] - h * 0.08
                    text_x, text_y = x + w + 6, y + 2
                    line_spacing = 16  # shared spacing for all stacked texts
                    font_color = flags["color_name"]
                    font_size = max(12, min(12, int(h * 0.14)))
                except Exception as e:
                    print(f"[ESP Error] Failed to calculate ESP box dimensions: {e}")
                    continue

                try:
                    # --- Right-side stacked info: money + weapon name ---
                    side_line_index = 0

                    if flags["money_esp_enabled"]:
                        overlay.draw_text(
                            f"${ent.money}",
                            text_x,
                            text_y + line_spacing * side_line_index,
                            flags["color_money_text"],
                            font_size,
                        )
                        side_line_index += 1

                    # --- Head ESP (unchanged) ---
                    if flags["head_esp_enabled"]:
                        radius = int(getattr(cfg, "head_esp_size", int(h * 0.15)))
                        color = flags["color_head"]
                        if flags["head_esp_shape"] == "circle":
                            overlay.draw_circle(ent.head2d["x"], ent.head2d["y"], radius, color)
                        else:
                            side = radius * 2
                            overlay.draw_box(
                                ent.head2d["x"] - radius,
                                ent.head2d["y"] - radius,
                                side,
                                side,
                                color,
                            )
                except Exception as e:
                    print(f"[ESP Error] Drawing error (money/weapon/head): {e}")


                try:
                    if flags["box_esp_enabled"]:
                        if ent.hp <= 0:
                            # Dead player color
                            color = flags["color_box_dead_t"] if ent.team == 2 else flags["color_box_dead_ct"]
                        else:
                            # Alive colors
                            if ent.team == 2:  # T
                                color = flags["color_box_t"]
                            else:              # CT
                                color = flags["color_box_ct"]

                            # Apply visibility overrides only for alive players
                            if flags["visibility_esp_enabled"] and vis_checker and local_pos:
                                is_visible = None
                                try:
                                    is_visible = check_player_visibility(local_pos, ent.pos, vis_checker)
                                except Exception as e:
                                    print(f"[VisCheck BoxESP Error] {e}")
                                    is_visible = None
                                if is_visible is not None:
                                    if ent.team == 2:
                                        color = flags["color_box_visible_t"] if is_visible else flags["color_box_invisible_t"]
                                    else:
                                        color = flags["color_box_visible_ct"] if is_visible else flags["color_box_invisible_ct"]


                        style = getattr(cfg, "box_esp_style", "normal")
                        radius = 8
                        if style == "corner" and hasattr(overlay, "draw_corner_box"):
                            overlay.draw_corner_box(x, y, w, h, color, getattr(cfg, "corner_box_len", 8))
                        elif style == "rounded" and hasattr(overlay, "draw_rounded_box"):
                            overlay.draw_rounded_box(x, y, w, h, radius, color)
                        else:
                            overlay.draw_box(x, y, w, h, color)
                except Exception as e:
                    print(f"[ESP Error] Box ESP drawing error: {e}")


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
                        velocity = read_vec3(handle, ent.pawn + Offsets.m_vecVelocity) or Vec3(0, 0, 0)
                        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                        start = world_to_screen(matrix, ent.pos, overlay.width, overlay.height)

                        if flags["velocity_esp"]:
                            scale = 0.1
                            end_pos = Vec3(
                                ent.pos.x + velocity.x * scale,
                                ent.pos.y + velocity.y * scale,
                                ent.pos.z + velocity.z * scale,
                            )
                            end = world_to_screen(matrix, end_pos, overlay.width, overlay.height)
                            overlay.draw_line(start["x"], start["y"], end["x"], end["y"], cfg.velocity_esp_color)
                            overlay.draw_filled_rect(end["x"] - 2, end["y"] - 2, 4, 4, cfg.velocity_esp_color)

                        # Velocity / Speed text stacked under the box
                        if (flags["velocity_esp_text"] or flags["speed_esp"]) and 'velocity' in locals():
                            try:
                                if flags["velocity_esp_text"]:
                                    txt = f"V: {velocity.x:.1f} {velocity.y:.1f} {velocity.z:.1f}"
                                    overlay.draw_text(
                                        txt,
                                        base_x,
                                        base_y + line_index * line_spacing,
                                        getattr(cfg, "velocity_text_color", cfg.velocity_text_color),
                                        14,
                                        centered=True,
                                    )
                                    line_index += 1

                                if flags["speed_esp"]:
                                    txt = f"Speed: {speed:.1f} u/s"
                                    overlay.draw_text(
                                        txt,
                                        base_x,
                                        base_y + line_index * line_spacing,
                                        getattr(cfg, "speed_esp_color", cfg.speed_esp_color),
                                        14,
                                        centered=True,
                                    )
                                    line_index += 1
                            except Exception as e:
                                print(f"[Velocity/Speed Text ESP Error] {e}")

                    except Exception as e:
                        print(f"[Velocity/Speed ESP Error] {e}")


                if flags["weapon_esp_enabled"]:
                    weapon_name = esp_weapon(handle, ent.pawn)
                    if weapon_name:
                        overlay.draw_text(
                            weapon_name,
                            text_x,
                            text_y + line_spacing * side_line_index,
                            cfg.color_weapon_text,
                            font_size,
                        )
                        side_line_index += 1


                if flags["line_esp_enabled"]:
                    start_x = overlay.width // 2
                    start_y = 0 if flags["line_esp_position"] == "top" else overlay.height
                    end_x, end_y = int(x + w/2), int(y if start_y == 0 else y + h)
                    overlay.draw_line(start_x, start_y, end_x, end_y, cfg.color_line)

                if flags["name_esp_enabled"]:
                    overlay.draw_text(ent.name, x + w / 2, y - 16, font_color, font_size, centered=True)

                # Base screen position for text (just below the box)
                base_x = x + w/2
                base_y = y + h + 20
                line_spacing = 14  # pixels between lines
                line_index = 0

                # Coordinates ESP
                if flags["coordinates_esp_enabled"]:
                    try:
                        txt = f"X: {ent.pos.x:.1f} Y: {ent.pos.y:.1f} Z: {ent.pos.z:.1f}"
                        overlay.draw_text(
                            txt,
                            base_x,
                            base_y + line_index * line_spacing,
                            getattr(cfg, "coordinates_esp_color", (255, 255, 255)),
                            14,
                            centered=True
                        )
                        line_index += 1
                    except Exception as e:
                        print(f"[Coordinates ESP Error] {e}")

                # Visibility Text ESP
                if flags["visibility_esp_enabled"] and vis_checker and local_pos:
                    is_visible = None
                    try:
                        is_visible = check_player_visibility(local_pos, ent.pos, vis_checker)
                    except Exception as e:
                        if flags["visibility_esp_enabled"] and vis_checker:
                            is_visible = check_player_visibility(handle, base, vis_checker, local_pos, ent.pos)

                    if is_visible is not None and flags["visibility_text_enabled"]:
                        visibility_text = "VISIBLE" if is_visible else "NOT VISIBLE"
                        visibility_color = (
                            flags["color_visible_text"] if is_visible else flags["color_not_visible_text"]
                        )
                        overlay.draw_text(
                            visibility_text,
                            base_x,
                            base_y + line_index * line_spacing,
                            visibility_color,
                            font_size,
                            centered=True
                        )


                if flags.get("skeleton_esp_enabled") or flags.get("bone_dot_esp_enabled"):
                    RenderBoneESP(overlay, ent, matrix, local_pos, vis_checker, local_team, flags)

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
            
            # END OF ENTITY LOOP - Bomb ESP below runs once per frame, not once per entity
            if flags["bomb_esp_enabled"]:
                bomb_info = bomb_status.read_bomb()
                if bomb_info:
                    try:
                        scr = world_to_screen(matrix, bomb_info["position"], overlay.width, overlay.height)
                        if scr:  # Only draw if world_to_screen succeeded
                            text = f"BOMB {bomb_info['time_remaining']}s"
                            if bomb_info["defuse_time"] is not None:
                                text += f" | DEF {bomb_info['defuse_time']}s"
                                color = (255, 80, 80)
                            else:
                                color = (255, 255, 0)
                            overlay.draw_text(text, scr["x"], scr["y"], color, 14, centered=True)
                    except: pass
            
            # === World Items ESP (module) ===
            if worldesp.features_active(Config):
                worldesp.render_world_items(
                    handle, base, matrix, overlay, Config,
                    safe_read_uint64, read_vec3, read_int, read_bytes, world_to_screen,
                    get_weapon_type, get_projectile_type
                )

            # Bomb Carrier ESP (shows who has the bomb)
            draw_bomb_carrier_esp(handle, base, entities, overlay, cfg)

            # Spectator list
            if getattr(Config, "spectator_list_enabled", False):
                specs = spectator_list.GetSpectatorsCached()
                draw_spectator_list(overlay, specs)

        except Exception as e:
            consecutive_errors += 1
            current_time = time.time()
            last_error_time = current_time
            
            # Detailed error logging with rate limiting
            import traceback
            error_type = type(e).__name__
            print(f"[!] ESP Error ({consecutive_errors}/{max_consecutive_errors}): {error_type}: {e}")
            
            # Print full traceback only for first few errors to avoid spam
            if consecutive_errors <= 3:
                print(traceback.format_exc())
            
            # Check if errors are happening too frequently
            if consecutive_errors >= max_consecutive_errors:
                print(f"[!] ESP CRITICAL: {max_consecutive_errors} consecutive errors detected!")
                print("[!] ESP may be unstable. Attempting recovery...")
                
                # Try to recover overlay
                try:
                    print("[ESP] Attempting to reinitialize overlay...")
                    overlay.end_scene()
                    time.sleep(500)  # Longer pause for recovery
                    
                    # Try to clear any stuck resources
                    try:
                        # Force garbage collection
                        import gc
                        gc.collect()
                        print("[ESP] Garbage collection completed")
                    except:
                        pass
                    
                    # Reset error counter after recovery attempt
                    consecutive_errors = max_consecutive_errors // 2
                    print("[ESP] Recovery attempt complete, continuing...")
                except Exception as recovery_error:
                    print(f"[ESP] Recovery failed: {recovery_error}")
                    consecutive_errors = 0  # Reset anyway to avoid infinite loop
            
            # Try to properly end the scene to avoid DirectX issues
            try:
                overlay.end_scene()
            except:
                pass
            
            # Brief pause to prevent error spam and allow recovery
            time.sleep(100)
            continue

        overlay.end_scene()
        # Avoid capping framerate to ~60-65 FPS due to Windows default 15.6ms timer granularity.
        # DX11Renderer already handles precise frame pacing; yield without enforcing a minimum sleep.
        time.sleep(0)

if __name__ == "__main__":
    main()