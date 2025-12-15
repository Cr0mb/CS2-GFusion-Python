"""
2D Radar for CS2 - Integrated with ESP overlay
Draws on the same overlay as ESP for correct screen positioning
"""
import math
from Process.config import Config
from Process.offsets import Offsets

# Radar state
_radar_cache = {
    'players': [],
    'local_pos': None,
    'local_team': None,
    'local_yaw': None,
    'last_update': 0
}

def world_to_radar(world_pos, local_pos, local_yaw, radar_size, radar_range):
    """Convert world coordinates to radar coordinates"""
    dx = world_pos[0] - local_pos[0]
    dy = world_pos[1] - local_pos[1]
    
    # Rotate based on local player's yaw (add 90° to align forward with up)
    yaw_rad = math.radians(-local_yaw + 90)
    cos_yaw = math.cos(yaw_rad)
    sin_yaw = math.sin(yaw_rad)
    
    # Rotate coordinates so forward = up on radar
    rotated_x = dx * cos_yaw - dy * sin_yaw
    rotated_y = dx * sin_yaw + dy * cos_yaw
    
    # Scale to radar (forward = up, so negate Y)
    scale = radar_size / (2 * radar_range)
    radar_x = rotated_x * scale + radar_size // 2
    radar_y = -rotated_y * scale + radar_size // 2
    
    return int(radar_x), int(radar_y)

def update_radar_cache(entities, local_pos, local_team, local_yaw):
    """Update radar player cache from ESP entities"""
    global _radar_cache
    
    players = []
    for ent in entities:
        if ent.hp <= 0:
            continue
        players.append({
            'pos': (ent.pos.x, ent.pos.y, ent.pos.z),
            'team': ent.team,
            'is_enemy': ent.team != local_team
        })
    
    _radar_cache['players'] = players
    _radar_cache['local_pos'] = (local_pos.x, local_pos.y, local_pos.z) if local_pos else None
    _radar_cache['local_team'] = local_team
    _radar_cache['local_yaw'] = local_yaw

def draw_radar(overlay, local_pos, local_team, local_yaw, entities=None):
    """Draw 2D radar on ESP overlay"""
    if not getattr(Config, "radar_enabled", False):
        return
    
    # Update cache if entities provided
    if entities is not None and local_pos is not None:
        try:
            update_radar_cache(entities, local_pos, local_team, local_yaw)
        except Exception as e:
            print(f"[Radar] Cache update error: {e}")
            return
    
    cache = _radar_cache
    if not cache['local_pos']:
        return
    
    # Radar settings
    radar_size = getattr(Config, "radar_size", 200)
    radar_range = getattr(Config, "radar_range", 1500)
    radar_x = getattr(Config, "radar_x", 20)
    radar_y = getattr(Config, "radar_y", 20)
    show_team = getattr(Config, "radar_show_team", True)
    show_background = getattr(Config, "radar_show_background", True)
    radar_shape = getattr(Config, "radar_shape", "square")
    is_circle = radar_shape == "circle"
    
    # Colors (RGB only, no alpha for GDI)
    bg_color = getattr(Config, "radar_bg_color", (20, 20, 20))[:3]
    border_color = getattr(Config, "radar_border_color", (100, 100, 100))[:3]
    enemy_color = getattr(Config, "radar_color_enemy", (255, 50, 50))[:3]
    team_color = getattr(Config, "radar_color_team", (50, 150, 255))[:3]
    local_color = (0, 255, 0)  # Green for local player
    
    center_x = radar_x + radar_size // 2
    center_y = radar_y + radar_size // 2
    
    try:
        # Draw radar background based on shape (only if enabled)
        if show_background:
            if is_circle:
                overlay.draw_circle(center_x, center_y, radar_size // 2, border_color)
                for r in range(radar_size // 2 - 1, 0, -2):
                    overlay.draw_circle(center_x, center_y, r, bg_color)
            else:
                overlay.draw_filled_rect(radar_x, radar_y, radar_size, radar_size, bg_color)
                overlay.draw_box(radar_x, radar_y, radar_size, radar_size, border_color)
            
            # Draw crosshairs
            line_color = (60, 60, 60)
            if is_circle:
                half = radar_size // 2 - 5
                overlay.draw_line(center_x - half, center_y, center_x + half, center_y, line_color)
                overlay.draw_line(center_x, center_y - half, center_x, center_y + half, line_color)
            else:
                overlay.draw_line(radar_x, center_y, radar_x + radar_size, center_y, line_color)
                overlay.draw_line(center_x, radar_y, center_x, radar_y + radar_size, line_color)
        
        # Draw local player dot (center)
        overlay.draw_filled_rect(center_x - 3, center_y - 3, 6, 6, local_color)
        
        # Draw direction indicator (small triangle pointing up)
        overlay.draw_line(center_x, center_y - 8, center_x - 4, center_y - 2, local_color)
        overlay.draw_line(center_x, center_y - 8, center_x + 4, center_y - 2, local_color)
    except Exception as e:
        print(f"[Radar] Draw background error: {e}")
        return
    
    # Draw players
    local_pos_tuple = cache['local_pos']
    local_yaw_val = cache['local_yaw'] or 0
    radius = radar_size // 2
    
    for player in cache['players']:
        # Skip teammates if not showing team
        if not player['is_enemy'] and not show_team:
            continue
        
        # Convert world position to radar position
        px, py = world_to_radar(
            player['pos'], local_pos_tuple, local_yaw_val,
            radar_size, radar_range
        )
        
        # Check if point is within radar bounds
        if is_circle:
            # For circle, check distance from center
            dist = math.sqrt((px - radius)**2 + (py - radius)**2)
            if dist > radius - 2:
                continue
        else:
            # For square, check bounds
            if px < 0 or px > radar_size or py < 0 or py > radar_size:
                continue
        
        # Choose color based on team
        color = enemy_color if player['is_enemy'] else team_color
        
        # Draw player dot
        dot_x = radar_x + px
        dot_y = radar_y + py
        dot_size = 5
        overlay.draw_filled_rect(dot_x - dot_size//2, dot_y - dot_size//2, dot_size, dot_size, color)

def draw_radar_label(overlay):
    """Draw radar label"""
    if not getattr(Config, "radar_enabled", False):
        return
    
    radar_x = getattr(Config, "radar_x", 20)
    radar_y = getattr(Config, "radar_y", 20)
    radar_size = getattr(Config, "radar_size", 200)
    
    # Draw "RADAR" label above
    # overlay.draw_text("RADAR", radar_x + radar_size // 2, radar_y - 16, (200, 200, 200), 12, centered=True)


# Legacy class for backwards compatibility (if GFusion.py imports it)
class CS2RadarManager:
    """Legacy wrapper - radar now integrated into ESP"""
    def __init__(self, shared_config=None):
        self.shared_config = shared_config
        print("[Radar] Radar is now integrated into ESP overlay")
    
    def run(self):
        """No-op - radar runs through ESP now"""
        print("[Radar] Radar draws through ESP overlay - no separate thread needed")
        pass
