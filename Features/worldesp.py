import time
from Process.offsets import Offsets


class _SimpleVec3:
    __slots__ = ("x", "y", "z")
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


# Timers and caches
WORLD_SCAN_INTERVAL_SEC = 0.15
OWNER_RESOLVE_TTL_SEC = 0.30
TYPE_STR_TTL_SEC = 5.0

_world_items_cache = []            # [(screen_pos, origin, type_str)]
_world_items_cache_until = 0.0
_item_type_cache = {}              # {entity_addr: (type_str, expiry)}
_owner_resolve_cache = {}          # {entity_addr: (equipped, expiry)}


def _now():
    return time.perf_counter()


def features_active(cfg):
    """Return True if any world-item ESP feature is enabled."""
    return any([
        getattr(cfg, "dropped_weapon_esp_enabled", True),
        getattr(cfg, "projectile_esp_enabled", True),
        getattr(cfg, "chicken_esp_enabled", True),
        getattr(cfg, "hostage_esp_enabled", True),
        getattr(cfg, "bomb_esp_enabled", True),
    ])


def _read_type_str_cached(handle, entity_addr, safe_read_uint64, read_bytes):
    """Read designer name once per 5s per entity."""
    now = _now()
    hit = _item_type_cache.get(entity_addr)
    if hit and hit[1] > now:
        return hit[0]

    type_str = ""
    try:
        item_info = safe_read_uint64(handle, entity_addr + 0x10)
        if item_info and item_info < 0x7FFFFFFFFFFF:
            type_ptr = safe_read_uint64(handle, item_info + 0x20)
            if type_ptr and type_ptr < 0x7FFFFFFFFFFF:
                raw = read_bytes(handle, type_ptr, 64)
                if raw:
                    s = raw.split(b"\x00", 1)[0].decode("utf-8", "ignore")
                    if s:
                        type_str = s
    except Exception:
        pass

    if not type_str:
        # cache negative result briefly to avoid spamming reads
        _item_type_cache[entity_addr] = ("", _now() + 0.75)
        return ""

    _item_type_cache[entity_addr] = (type_str, now + TYPE_STR_TTL_SEC)
    return type_str


def _is_equipped_weapon_cached(handle, entity_list, entity_addr, safe_read_uint64, read_int):
    """Return True if this weapon is clearly owned by a valid pawn. Cached for 300ms."""
    now = _now()
    hit = _owner_resolve_cache.get(entity_addr)
    if hit and hit[1] > now:
        return hit[0]

    equipped = False
    try:
        owner_handle = read_int(handle, entity_addr + Offsets.m_hOwnerPawn) & 0x7FFF
        if owner_handle != 0x7FFF:
            pawn_list_entry = safe_read_uint64(handle, entity_list + ((owner_handle >> 9) * 8) + 16)
            if pawn_list_entry:
                pawn = safe_read_uint64(handle, pawn_list_entry + (120 * (owner_handle & 0x1FF)))
                if pawn:
                    equipped = True
    except Exception:
        equipped = False

    _owner_resolve_cache[entity_addr] = (equipped, now + OWNER_RESOLVE_TTL_SEC)
    return equipped


def _scan_world_items_once(handle, base, matrix, overlay, cfg,
                           safe_read_uint64, read_vec3, read_int, read_bytes, world_to_screen):
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
            list_entry = safe_read_uint64(handle, entity_list + (8 * ((i & 0x7FFF) >> 9) + 16))
            if not list_entry:
                continue

            ent = safe_read_uint64(handle, list_entry + (120 * (i & 0x1FF)))
            if not ent:
                continue

            # Read scene node and position
            node = safe_read_uint64(handle, ent + Offsets.m_pGameSceneNode)
            if not node:
                continue
            pos = read_vec3(handle, node + Offsets.m_vecAbsOrigin)
            if not pos or not getattr(pos, 'x', None):
                continue

            # Compute once; skip offscreen early
            scr = world_to_screen(matrix, pos, W, H)
            if not scr:
                continue

            # Type string with cache (read only for on-screen items)
            t = _read_type_str_cached(handle, ent, safe_read_uint64, read_bytes)
            if not t:
                t = f"entity_{i}"

            # If it's a weapon, skip equipped ones
            if t.startswith("weapon_"):
                if _is_equipped_weapon_cached(handle, entity_list, ent, safe_read_uint64, read_int):
                    continue

            items.append((scr, pos, t))
        except Exception:
            continue

    return items


def render_world_items(handle, base, matrix, overlay, cfg,
                       safe_read_uint64, read_vec3, read_int, read_bytes, world_to_screen,
                       weapon_lookup, projectile_lookup):
    """Render world items: direct-scan for fast items and cached draw for the rest."""
    global _world_items_cache, _world_items_cache_until

    # Refresh cached scan periodically (for heavy/rare items)
    try:
        now = _now()
        if now >= _world_items_cache_until:
            try:
                _world_items_cache = _scan_world_items_once(
                    handle, base, matrix, overlay, cfg,
                    safe_read_uint64, read_vec3, read_int, read_bytes, world_to_screen
                )
            except Exception as e:
                print(f"[WorldItemsESP] Scan error: {e}")
                _world_items_cache = []

            # Adaptive throttle
            refresh_int = WORLD_SCAN_INTERVAL_SEC
            if len(_world_items_cache) > 200:
                refresh_int *= 1.5
            elif len(_world_items_cache) < 50:
                refresh_int *= 0.75
            _world_items_cache_until = now + refresh_int
    except Exception as e:
        print(f"[WorldItemsESP] Cache refresh error: {e}")

    # ---- Direct-scan weapons/projectiles/chickens/bomb (no caching) ----
    try:
        entity_list = safe_read_uint64(handle, base + Offsets.dwEntityList)
        if entity_list:
            W, H = overlay.width, overlay.height
            spacing_px = getattr(cfg, "dropped_weapon_stack_spacing", 14)
            max_stack  = getattr(cfg, "dropped_weapon_stack_max", 6)
            pos_stacks_direct = {}

            for i in range(64, 2048):
                try:
                    list_entry = safe_read_uint64(handle, entity_list + (8 * ((i & 0x7FFF) >> 9) + 16))
                    if not list_entry:
                        continue
                    ent = safe_read_uint64(handle, list_entry + (120 * (i & 0x1FF)))
                    if not ent:
                        continue
                    node = safe_read_uint64(handle, ent + Offsets.m_pGameSceneNode)
                    if not node:
                        continue
                    pos = read_vec3(handle, node + Offsets.m_vecAbsOrigin)
                    if not pos or not getattr(pos, 'x', None):
                        continue
                    scr = world_to_screen(matrix, pos, W, H)
                    if not scr or 'x' not in scr or 'y' not in scr:
                        continue
                    sx, sy = int(scr["x"]), int(scr["y"])
                    if sx < 0 or sy < 0 or sx >= W or sy >= H:
                        continue

                    # Read type string directly (balanced size)
                    t = ""
                    try:
                        item_info = safe_read_uint64(handle, ent + 0x10)
                        if item_info and item_info < 0x7FFFFFFFFFFF:
                            type_ptr = safe_read_uint64(handle, item_info + 0x20)
                            if type_ptr and type_ptr < 0x7FFFFFFFFFFF:
                                raw = read_bytes(handle, type_ptr, 64)
                                if raw:
                                    t = raw.split(b'\x00', 1)[0].decode('utf-8', 'ignore')
                    except Exception:
                        continue
                    if not t:
                        continue

                    key = (sx >> 3, sy >> 3)
                    count = pos_stacks_direct.get(key, 0)
                    if count >= max_stack:
                        continue
                    y_offset = count * spacing_px

                    # Dropped weapons
                    if getattr(cfg, "dropped_weapon_esp_enabled", True) and t.startswith("weapon_"):
                        try:
                            owner_handle = read_int(handle, ent + Offsets.m_hOwnerPawn) & 0x7FFF
                            if owner_handle != 0x7FFF and owner_handle > 0:
                                continue  # equipped, skip
                        except Exception:
                            pass
                        weapon_name = weapon_lookup(t)
                        if weapon_name:
                            overlay.draw_text(weapon_name, sx, sy + y_offset,
                                              getattr(cfg, "dropped_weapon_esp_color", (200, 200, 255)),
                                              12, centered=True)
                            pos_stacks_direct[key] = count + 1
                            continue

                    # Projectiles
                    if getattr(cfg, "projectile_esp_enabled", True):
                        projectile_name = projectile_lookup(t)
                        if projectile_name:
                            overlay.draw_text(projectile_name, sx, sy + y_offset,
                                              getattr(cfg, "projectile_esp_color", (255, 100, 100)),
                                              12, centered=True)
                            pos_stacks_direct[key] = count + 1
                            continue

                    # Chickens
                    if getattr(cfg, "chicken_esp_enabled", True) and "chicken" in t:
                        overlay.draw_text("Chicken", sx, sy + y_offset,
                                          getattr(cfg, "chicken_esp_color", (255, 255, 0)),
                                          12, centered=True)
                        pos_stacks_direct[key] = count + 1
                        continue

                    # Bomb
                    if getattr(cfg, "bomb_esp_enabled", True) and "c4" in t:
                        top = _SimpleVec3(pos.x, pos.y, pos.z + 36)
                        top_screen = world_to_screen(matrix, top, W, H)
                        if top_screen:
                            size = abs(top_screen["y"] - sy) * 0.65
                            overlay.draw_box(sx - size / 2, sy - size + 2 + y_offset, size, size,
                                             getattr(cfg, "bomb_esp_color", (255, 50, 50)))
                            pos_stacks_direct[key] = count + 1
                        continue
                except Exception:
                    continue
    except Exception as e:
        print(f"[WorldItemsESP] Direct-scan error: {e}")

    # ---- Draw cached results (hostages only) ----
    try:
        W, H = overlay.width, overlay.height
        spacing_px = getattr(cfg, "dropped_weapon_stack_spacing", 14)
        max_stack  = getattr(cfg, "dropped_weapon_stack_max", 6)
        pos_stacks = {}
        hostage_enabled = getattr(cfg, "hostage_esp_enabled", True)

        for screen_pos, item_origin, t in _world_items_cache:
            try:
                sx, sy = int(screen_pos["x"]), int(screen_pos["y"])
                if sx < 0 or sy < 0 or sx >= W or sy >= H:
                    continue
                key = (sx >> 3, sy >> 3)
                count = pos_stacks.get(key, 0)
                if count >= max_stack:
                    continue
                y_offset = count * spacing_px

                if hostage_enabled and "hostage_entity" in t:
                    overlay.draw_text("Hostage", sx, sy + y_offset,
                                      getattr(cfg, "hostage_esp_color", (0, 255, 0)), 12, centered=True)
                    pos_stacks[key] = count + 1
                    continue
            except Exception:
                continue
    except Exception as e:
        print(f"[WorldItemsESP] Cached draw error: {e}")
