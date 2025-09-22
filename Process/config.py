import json
import os
import win32con

class Config:    
    # ===========================
    # Watermark
    # ===========================

    watermark_enabled = True

    use_gpu_overlay = False

    # ===========================
    # Walk Bot
    # ===========================

    circle_enabled = False
    circle_stop = False

    # ===========================
    # ESP Toggles
    # ===========================
    obs_protection_enabled = False
    show_overlay_fps = False

    # Config defaults
    panic_key_enabled = True
    panic_key = 0x2E  # VK_DELETE
    panic_mode_active = False

    show_box_esp = True
    box_esp_style = "normal"   # options: normal, rounded, corner



    healthbar_enabled = False
    armorbar_enabled = False
    health_esp_enabled = False
    armor_esp_enabled = False
    flash_esp_enabled = False
    scope_esp_enabled = False
    spectator_list_enabled = False
    skeleton_esp_enabled = False
    head_esp_enabled = False
    distance_esp_enabled = False
    name_esp_enabled = False
    bone_dot_esp_enabled = False
    line_esp_enabled = False
    bomb_esp_enabled = False
    weapon_esp_enabled = False
    esp_show_enemies_only = True
    esp_show_team_only = False
    crosshair_size = 6

    velocity_esp = False
    speed_esp = False
    velocity_esp_text = False
    
    coordinates_esp_enabled = False
    
    trace_esp_enabled = False
    trace_esp_max_points = 150
    
    show_local_info_box = False
    color_local_box_background = (30, 30, 30)
    color_local_box_border = (100, 100, 100)
    color_local_velocity_text = (255, 255, 255)
    color_local_speed_text = (180, 255, 180)
    color_local_coords_text = (200, 200, 255)
    
    money_esp_enabled = False
    
    # Visibility Check ESP
    visibility_esp_enabled = True
    visibility_text_enabled = True  # Show/hide "VISIBLE" text overlay
    visibility_map_file = "de_mirage.opt"  # Map file for visibility checking

    # ===========================
    # ESP Customization
    # ===========================
    head_esp_size = 5
    head_esp_shape = "circle"

    bone_dot_shape = "circle"
    bone_dot_size = 6

    line_esp_position = "bottom"
    color_line = (255, 255, 255)

    # ===========================
    # ESP Colors
    # ===========================
    
    color_box_visible_ct = (0, 200, 255)
    color_box_invisible_ct = (0, 70, 120)
    color_box_visible_t = (255, 200, 0)
    color_box_invisible_t = (120, 70, 0)

    color_skeleton_visible_ct = (0, 200, 255)
    color_skeleton_invisible_ct = (0, 70, 120)
    color_skeleton_visible_t = (255, 200, 0)
    color_skeleton_invisible_t = (120, 70, 0)



    color_box_t = (255, 0, 0)
    color_box_ct = (0, 0, 255)
    color_bone = (0, 255, 0)
    color_head = (255, 255, 255)
    bone_dot_color = (255, 0, 255)

    color_healthbar = (0, 255, 0)
    color_armorbar = (173, 216, 230)
    color_hp_text = (0, 255, 0)
    color_armor_text = (173, 216, 230)

    color_name = (255, 255, 255)
    color_name_effects = (255, 215, 0)
    color_distance = (255, 255, 255)
    color_flash_scope = (255, 255, 0)
    color_spectators = (255, 165, 0)

    color_weapon_text = (200, 200, 255)
    
    fov_overlay_color = (0, 255, 0)
    
    crosshair_color = (255, 255, 255)

    trace_esp_color = (0, 255, 255)
    velocity_text_color = (255, 0, 0)
    velocity_esp_color = (255, 0, 0)
    speed_esp_color = (0, 255, 255)
    coordinates_esp_color = (0, 255, 255)
    
    color_money_text = (0, 255, 0)
    
    # Visibility ESP Colors
    color_visible_text = (0, 255, 0)      # Green for visible
    color_not_visible_text = (255, 0, 0)  # Red for not visible

    # ===========================
    # FOV & Overlay
    # ===========================
    fov_circle_enabled = False
    fov_overlay_color = (0, 255, 0)
    draw_crosshair_enabled = False

    # ===========================
    # Misc Visuals
    # ===========================
    grenade_prediction_enabled = False
    noflash_enabled = False
    fov_info_overlay_enabled = False 
    # ===========================
    # GUI
    # ===========================
    toggle_menu_key = 'insert'

    # ===========================
    # Bunny Hop (BHop)
    # ===========================
    bhop_enabled = False
    bhop_stop = False
    # ===========================
    # Glow ESP
    # ===========================
    glow = False
    glow_stop = False

    glow_show_enemies = True
    glow_show_team = True
    
    glow_color_enemy = (1, 0, 0, 1)
    glow_color_team = (0, 0, 1, 1)

    # ===========================
    # TriggerBot
    # ===========================
    triggerbot_enabled = False
    triggerbot_stop = False
    trigger_key = "alt"
    triggerbot_cooldown = 0.2
    shoot_teammates = False
    triggerbot_always_on = False

    # ===========================
    # Auto Pistol
    # ===========================

    auto_pistol_enabled = False
    activation_key = "alt"
    fire_rate = 1.0

    # ===========================
    # FOV Changer
    # ===========================
    fov_changer_enabled = False
    game_fov = 90


    # ===========================
    # Aimbot Core Settings
    # ===========================
    enabled = False
    aim_key = "mouse1"
    target_bone_name = "head"
    bone_indices_to_try = [6, 18]
    closest_to_crosshair = False
    max_entities = 64
    FOV = 3.0
    max_delta_angle = 60
    target_switch_delay = 0
    aim_start_delay = 0
    downward_offset = 62
    DeathMatch = False

    rcs_grace_after_damage = True
    rcs_grace_after_damage = 0.12
    
    visibility_aim_enabled = True

    # ===========================
    # Aimbot Learning & Prediction
    # ===========================
    enable_learning = False
    learn_dir = "aimbot_data"
    enable_velocity_prediction = False
    velocity_prediction_factor = 0.1

    # ===========================
    # Aimbot Smooth / Sensitivity
    # ===========================
    smooth_base = 0.24
    smooth_var = 0.00
    sensitivity = 0.022
    invert_y = -1
    max_mouse_move = 5

    # ===========================
    # Recoil Control System (RCS)
    # ===========================
    rcs_enabled = False
    rcs_scale = 2.0
    rcs_smooth_base = 1.00
    rcs_smooth_var = 0.01

    # ===========================
    # Utility
    # ===========================
    aim_stop = False

    @classmethod
    def to_dict(cls):
        result = {}
        for key in dir(cls):
            if key.startswith("__") or callable(getattr(cls, key)):
                continue
            value = getattr(cls, key)
            # Convert tuples to lists for JSON compatibility
            if isinstance(value, tuple):
                result[key] = list(value)
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: dict):
        for key, value in data.items():
            if hasattr(cls, key):
                try:
                    current = getattr(cls, key)
                    # Convert lists back to tuples if original was a tuple
                    if isinstance(current, tuple) and isinstance(value, list):
                        setattr(cls, key, tuple(value))
                    else:
                        setattr(cls, key, value)
                except Exception as e:
                    print(f"[Config] Warning: Could not set {key} = {value}: {e}")
            else:
                print(f"[Config] Warning: Unknown config attribute '{key}' ignored")

    @classmethod
    def save_to_file(cls, filename):
        os.makedirs("config", exist_ok=True)
        try:
            config_data = cls.to_dict()
            # Ensure new attributes are included
            if not any('visibility' in key for key in config_data.keys()):
                print("[Config] Warning: Visibility ESP settings missing, adding defaults")
                config_data['visibility_esp_enabled'] = getattr(cls, 'visibility_esp_enabled', False)
                config_data['visibility_map_file'] = getattr(cls, 'visibility_map_file', 'de_mirage.opt')
                config_data['color_visible_text'] = getattr(cls, 'color_visible_text', (0, 255, 0))
                config_data['color_not_visible_text'] = getattr(cls, 'color_not_visible_text', (255, 0, 0))
            
            with open(f"config/{filename}.json", "w") as f:
                json.dump(config_data, f, indent=4)
            print(f"[Config] Saved {len(config_data)} settings to {filename}.json")
        except Exception as e:
            print(f"[Config] Error saving to {filename}.json: {e}")
            raise

    @classmethod
    def load_from_file(cls, filename):
        path = f"config/{filename}.json"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    cls.from_dict(data)
                    
                    # Ensure new visibility ESP settings have defaults if missing
                    if not hasattr(cls, 'visibility_esp_enabled') or not hasattr(cls, 'visibility_map_file'):
                        print("[Config] Adding missing visibility ESP defaults")
                        if not hasattr(cls, 'visibility_esp_enabled'):
                            cls.visibility_esp_enabled = False
                        if not hasattr(cls, 'visibility_text_enabled'):
                            cls.visibility_text_enabled = True
                        if not hasattr(cls, 'visibility_map_file'):
                            cls.visibility_map_file = 'de_mirage.opt'
                        if not hasattr(cls, 'color_visible_text'):
                            cls.color_visible_text = (0, 255, 0)
                        if not hasattr(cls, 'color_not_visible_text'):
                            cls.color_not_visible_text = (255, 0, 0)
                    
                    print(f"[Config] Loaded config from {filename}.json")
            except json.JSONDecodeError as e:
                print(f"[Config] Error: Invalid JSON in {filename}.json: {e}")
            except Exception as e:
                print(f"[Config] Error loading {filename}.json: {e}")
        else:
            print(f"[Config] Config file {filename}.json not found, using defaults")
