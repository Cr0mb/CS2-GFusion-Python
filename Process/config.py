import json
import os
import shutil
import time
import win32con

class Config:
    """
    GFusion Configuration (with safe persistence)
    - Atomic JSON save with backup
    - Tuple<->list normalization for colors
    - Runtime-only key filtering on save
    - Backfill defaults for new fields on load
    - Simple schema versioning
    """

    # ------------------------------
    # Persistence meta
    # ------------------------------
    schema_version = 1
    configs_dir = "config"
    current_config_name = "default"

    # ---- Config persistence (UI will read/write these) ----
    autosave_enabled = True
    autosave_minutes = 5

    # ============================================================
    #   GFusion Configuration
    # ============================================================

    # ===========================
    #  Watermark / Overlay
    # ===========================
    watermark_enabled = True
    use_gpu_overlay = False
    show_overlay_fps = False
    obs_protection_enabled = False

    team_list_enabled = False
    color_box_t = (255, 200, 0)
    color_box_ct = (255, 200, 255)
    color_local_box_background = (30, 30, 30)
    color_local_box_border = (100, 100, 100)

    # Panic key
    panic_key_enabled = True
    panic_key = 0x2E  # VK_DELETE
    panic_mode_active = False

    # ===========================
    #  Walk Bot
    # ===========================
    circle_enabled = False
    circle_stop = False
    walkbot_enabled = False

    # ===========================
    #  ESP Toggles
    # ===========================
    show_map_status_box = False
    visible_only_esp_enabled = False

    show_box_esp = True
    box_esp_style = "normal"  # options: normal, rounded, corner

    draw_dead_entities = False

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

    velocity_esp = False
    speed_esp = False
    velocity_esp_text = False
    coordinates_esp_enabled = False

    trace_esp_enabled = False
    trace_esp_max_points = 150

    money_esp_enabled = False

    # Local info box
    show_local_info_box = False
    color_local_box_background = (30, 30, 30)
    color_local_box_border = (100, 100, 100)
    color_local_velocity_text = (255, 255, 255)
    color_local_speed_text = (180, 255, 180)
    color_local_coords_text = (200, 200, 255)

    # Visibility Check ESP
    visibility_esp_enabled = True
    visibility_text_enabled = False
    visibility_map_file = "de_mirage.opt"

    # ===========================
    #  ESP Customization
    # ===========================
    head_esp_size = 5
    head_esp_shape = "circle"

    bone_dot_shape = "circle"
    bone_dot_size = 6

    line_esp_position = "bottom"
    color_line = (255, 255, 255)
    crosshair_size = 6

    # ===========================
    #  ESP Colors
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
    color_money_text = (0, 255, 0)

    fov_overlay_color = (0, 255, 0)
    crosshair_color = (255, 255, 255)

    trace_esp_color = (0, 255, 255)
    velocity_text_color = (255, 0, 0)
    velocity_esp_color = (255, 0, 0)
    speed_esp_color = (0, 255, 255)
    coordinates_esp_color = (0, 255, 255)

    # Visibility ESP Colors
    color_visible_text = (0, 255, 0)
    color_not_visible_text = (255, 0, 0)

    # ===========================
    #  FOV & Overlay
    # ===========================
    fov_circle_enabled = False
    draw_crosshair_enabled = False
    fov_info_overlay_enabled = False

    # ===========================
    #  Misc Visuals
    # ===========================
    grenade_prediction_enabled = False
    noflash_enabled = False

    # ===========================
    #  GUI
    # ===========================
    toggle_menu_key = 'insert'

    # ===========================
    #  Bunny Hop (BHop)
    # ===========================
    bhop_enabled = False
    bhop_stop = False

    # ===========================
    #  Glow ESP
    # ===========================
    glow = False
    glow_stop = False
    glow_show_enemies = True
    glow_show_team = True
    glow_color_enemy = (1, 0, 0, 1)
    glow_color_team = (0, 0, 1, 1)

    # ===========================
    #  TriggerBot
    # ===========================
    triggerbot_enabled = False
    triggerbot_stop = False
    trigger_key = "alt"
    triggerbot_cooldown = 0.2
    shoot_teammates = False
    triggerbot_always_on = False
    # Optional anti-detection fields used by new UI (safe if absent)
    trigger_delay_min = 0.000
    trigger_delay_max = 0.120
    trigger_jitter = 0.0
    trigger_burst_shots = 1
    trigger_require_vischeck = True

    # ===========================
    #  Auto Pistol
    # ===========================
    auto_pistol_enabled = False
    activation_key = "alt"
    fire_rate = 1.0

    # ===========================
    #  FOV Changer
    # ===========================
    fov_changer_enabled = False
    game_fov = 90

    # ===========================
    #  Aimbot Core Settings
    # ===========================
    enabled = True
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
    rcs_grace_time = 0.12  # renamed for clarity

    visibility_aim_enabled = True
    enable_logging = True

    # ===========================
    #  Aimbot Humanization
    # ===========================
    humanization_enabled = True
    aim_jitter_enabled = True
    aim_jitter_amount = 0.15
    aim_shake_frequency = 8.0
    smooth_randomization = True
    smooth_random_min = 0.8
    smooth_random_max = 1.2
    reaction_delay_enabled = True
    reaction_delay_min = 0.01
    reaction_delay_max = 0.08
    overshoot_enabled = True
    overshoot_chance = 0.15
    overshoot_amount = 1.2

    # ===========================
    #  Aimbot Learning & Prediction
    # ===========================
    enable_learning = True
    learn_dir = "aimbot_data"
    enable_velocity_prediction = False
    velocity_prediction_factor = 0.1
    enable_mouse_recording = True

    # ===========================
    #  Aimbot Smooth / Sensitivity
    # ===========================
    smooth_base = 0.24
    smooth_var = 0.00
    sensitivity = 0.022
    invert_y = -1
    max_mouse_move = 5

    # ===========================
    #  Recoil Control System (RCS)
    # ===========================
    rcs_enabled = True
    rcs_scale = 2.0
    rcs_smooth_base = 1.00
    rcs_smooth_var = 0.01

    # ===========================
    #  Kernel Mode Driver (NeacController)
    # ===========================
    kernel_mode_enabled = False
    kernel_driver_auto_start = False
    kernel_fallback_to_usermode = False

    # ===========================
    #  Utility
    # ===========================
    aim_stop = False

    # ------------------------------
    # Serialization helpers
    # ------------------------------
    @classmethod
    def _json_safe(cls, value):
        """Convert tuples -> lists (JSON), keep primitives, lists, dicts as-is."""
        if isinstance(value, tuple):
            return list(value)
        return value

    @classmethod
    def _normalize_loaded_value(cls, key, loaded_value):
        """Convert lists back to tuples when the default is a tuple; clamp color types."""
        try:
            default = getattr(cls, key)
        except AttributeError:
            return loaded_value

        # tuple restoration
        if isinstance(default, tuple) and isinstance(loaded_value, list):
            loaded_value = tuple(loaded_value)

        # basic color sanity (0..255 for rgb[a] ints; allow floats 0..1 in glow colors)
        if "color" in key:
            if isinstance(loaded_value, tuple):
                if all(isinstance(x, (int, float)) for x in loaded_value):
                    # if default is float rgba (like glow), keep floats in 0..1
                    if all(isinstance(x, float) for x in default):
                        loaded_value = tuple(max(0.0, min(1.0, float(x))) for x in loaded_value)
                    else:
                        loaded_value = tuple(max(0, min(255, int(x))) for x in loaded_value)
        return loaded_value

    @classmethod
    def to_dict(cls):
        """Class -> plain dict suitable for JSON (filters dunders/callables)."""
        result = {"schema_version": cls.schema_version}
        for key in dir(cls):
            if key.startswith("_"):
                continue
            try:
                value = getattr(cls, key)
            except Exception:
                continue
            if callable(value):
                continue
            # Skip properties (rare)
            if isinstance(value, property):
                continue
            result[key] = cls._json_safe(value)
        return result

    @classmethod
    def from_dict(cls, data: dict):
        """Apply values conservatively; ignore unknown, normalize types."""
        for key, value in data.items():
            if key == "schema_version":
                continue
            if hasattr(cls, key):
                try:
                    norm = cls._normalize_loaded_value(key, value)
                    setattr(cls, key, norm)
                except Exception as e:
                    print(f"[Config] Warn: Could not set {key} = {value}: {e}")
            else:
                # stay quiet or log once if you prefer
                # print(f"[Config] Info: Unknown key '{key}' ignored")
                pass

        # Backfill new keys if missing (keeps older configs working)
        if not hasattr(cls, "autosave_enabled"):
            cls.autosave_enabled = False
        if not hasattr(cls, "autosave_minutes"):
            cls.autosave_minutes = 5
        if not hasattr(cls, "configs_dir"):
            cls.configs_dir = "config"
        if not hasattr(cls, "current_config_name"):
            cls.current_config_name = "default"

    # ------------------------------
    # Persistence API
    # ------------------------------
    @classmethod
    def _config_path(cls, filename: str) -> str:
        os.makedirs(cls.configs_dir, exist_ok=True)
        return os.path.join(cls.configs_dir, f"{filename}.json")

    @classmethod
    def save_to_file(cls, filename: str):
        """
        Atomic save:
          - writes to <name>.json.tmp
          - renames existing file to .bak (one backup)
          - renames tmp -> final
        Filters runtime-only keys if you add them below.
        """
        path = cls._config_path(filename)
        tmp_path = path + ".tmp"
        bak_path = path + ".bak"

        try:
            data = cls.to_dict()

            # ---- strip runtime-only keys here if any appear in class namespace
            runtime_only = {
                # visibility runtime state (kept in-memory only)
                "visibility_map_path",
                "visibility_map_loaded",
                "visibility_map_reload_needed",
                # ephemeral flags
                "panic_mode_active",
            }
            for k in runtime_only:
                data.pop(k, None)

            # DO NOT persist map file name if you prefer auto-detect per session:
            # (If you actually want to persist it, comment out the next line.)
            data.pop("visibility_map_file", None)

            # write tmp
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # rotate backup (best-effort)
            if os.path.exists(path):
                try:
                    # keep 1 .bak; overwrite
                    shutil.copyfile(path, bak_path)
                except Exception as e:
                    print(f"[Config] Backup warn: {e}")

            # commit
            os.replace(tmp_path, path)
            cls.current_config_name = filename
            print(f"[Config] Saved {len(data)} settings to {os.path.basename(path)}")

        except Exception as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            print(f"[Config] Error saving '{filename}': {e}")
            raise

    @classmethod
    def load_from_file(cls, filename: str):
        """
        Load config safely:
          - reads JSON
          - applies with type normalization
          - backfills defaults for newly added fields
        """
        path = cls._config_path(filename)
        if not os.path.exists(path):
            print(f"[Config] {os.path.basename(path)} not found, using defaults")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # migrate if older schemas appear (hook for future upgrades)
            file_schema = data.get("schema_version", 0)
            if file_schema < cls.schema_version:
                data = cls._migrate_schema(data, file_schema)

            cls.from_dict(data)

            # Ensure visibility defaults exist even if older file lacked them
            if not hasattr(cls, 'visibility_esp_enabled'):
                cls.visibility_esp_enabled = False
            if not hasattr(cls, 'visibility_text_enabled'):
                cls.visibility_text_enabled = True
            if not hasattr(cls, 'color_visible_text'):
                cls.color_visible_text = (0, 255, 0)
            if not hasattr(cls, 'color_not_visible_text'):
                cls.color_not_visible_text = (255, 0, 0)

            cls.current_config_name = filename
            print(f"[Config] Loaded config from {os.path.basename(path)}")

        except json.JSONDecodeError as e:
            print(f"[Config] Error: Invalid JSON in {os.path.basename(path)}: {e}")
        except Exception as e:
            print(f"[Config] Error loading '{filename}': {e}")

    @classmethod
    def read_config_dict(cls, filename: str):
        """Helper used by Export in the Config tab."""
        path = cls._config_path(filename)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------
    # Schema migration (stub)
    # ------------------------------
    @classmethod
    def _migrate_schema(cls, data: dict, from_version: int) -> dict:
        """If we bump schema_version later, transform older data -> new format."""
        migrated = dict(data)
        # Example: if from_version == 0: (perform mappings)
        # migrated["schema_version"] = cls.schema_version
        migrated["schema_version"] = cls.schema_version
        return migrated
