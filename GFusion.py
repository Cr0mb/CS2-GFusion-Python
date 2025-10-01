import os
import sys
import json
import time
import threading
import ctypes
import datetime
import platform
import requests
import keyboard
import ctypes
import atexit
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTabWidget, QApplication
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QWindow
from PyQt5.QtCore import Qt, QPoint, QTimer, QThread, pyqtSignal, QEasingCurve, QPropertyAnimation
from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import (                                           
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QSlider,
    QLabel, QPushButton, QLineEdit, QComboBox, QTabWidget, QColorDialog,
    QGridLayout, QFrame, QScrollArea, QTextEdit, QMessageBox
)


from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from Process.config import Config

# Try to import DX11Backend, fallback to stub if broken
try:
    from render.dx11_backend import DX11Backend
except Exception as e:
    # print(f"[GUI] DX11Backend import failed: {e}")
    # print("[GUI] Using DX11Backend stub")
    from render.dx11_backend_stub import DX11Backend
import Features.esp
from Features.aimbot import start_aim_rcs
from Features.bhop import BHopProcess
from Features.glow import CS2GlowManager
from Features.triggerbot import TriggerBot
from Features.fov import FOVChanger
from Features.auto_pistol import run_auto_pistol

cfg = Config()
# ===========================
# Global Tab Registry
# ===========================
TAB_REGISTRY = []

import ctypes
import ctypes.wintypes

def wait_for_cs2():
    """Block until cs2.exe is detected AND client.dll is readable."""
    TH32CS_SNAPPROCESS = 0x00000002
    TH32CS_SNAPMODULE = 0x00000008

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.wintypes.DWORD),
            ("cntUsage", ctypes.wintypes.DWORD),
            ("th32ProcessID", ctypes.wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.wintypes.ULONG)),
            ("th32ModuleID", ctypes.wintypes.DWORD),
            ("cntThreads", ctypes.wintypes.DWORD),
            ("th32ParentProcessID", ctypes.wintypes.DWORD),
            ("pcPriClassBase", ctypes.wintypes.LONG),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("szExeFile", ctypes.c_char * ctypes.wintypes.MAX_PATH),
        ]

    class MODULEENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.wintypes.DWORD),
            ("th32ModuleID", ctypes.wintypes.DWORD),
            ("th32ProcessID", ctypes.wintypes.DWORD),
            ("GlblcntUsage", ctypes.wintypes.DWORD),
            ("ProccntUsage", ctypes.wintypes.DWORD),
            ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
            ("modBaseSize", ctypes.wintypes.DWORD),
            ("hModule", ctypes.wintypes.HMODULE),
            ("szModule", ctypes.c_char * 256),
            ("szExePath", ctypes.c_char * ctypes.wintypes.MAX_PATH),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def get_pid(exe_name: str):
        """Get PID of running process by name"""
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == ctypes.wintypes.HANDLE(-1).value:
            return None

        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

        success = kernel32.Process32First(snapshot, ctypes.byref(entry))
        while success:
            name = entry.szExeFile.split(b"\x00", 1)[0].decode(errors="ignore")
            if name.lower() == exe_name.lower():
                pid = entry.th32ProcessID
                kernel32.CloseHandle(snapshot)
                return pid
            success = kernel32.Process32Next(snapshot, ctypes.byref(entry))

        kernel32.CloseHandle(snapshot)
        return None

    def module_exists(pid: int, module_name: str) -> bool:
        """Check if a module (DLL) is loaded in the process"""
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)
        if snapshot == ctypes.wintypes.HANDLE(-1).value:
            return False

        entry = MODULEENTRY32()
        entry.dwSize = ctypes.sizeof(MODULEENTRY32)

        success = kernel32.Module32First(snapshot, ctypes.byref(entry))
        while success:
            mod_name = entry.szModule.split(b"\x00", 1)[0].decode(errors="ignore")
            if mod_name.lower() == module_name.lower():
                kernel32.CloseHandle(snapshot)
                return True
            success = kernel32.Module32Next(snapshot, ctypes.byref(entry))

        kernel32.CloseHandle(snapshot)
        return False

    print("[GFusion] Waiting for cs2.exe and client.dll to be ready...")
    while True:
        pid = get_pid("cs2.exe")
        if pid:
            if module_exists(pid, "client.dll"):
                print("[GFusion] cs2.exe and client.dll found! Starting GFusion...")
                return
            else:
                print("[GFusion] cs2.exe found but client.dll not loaded yet, waiting...")
        time.sleep(2)

def register_tab(tab):
    """Register tab for UI refresh calls from console/config changes"""
    if tab not in TAB_REGISTRY:
        TAB_REGISTRY.append(tab)

def refresh_all_tabs():
    """Force refresh across all registered tabs"""
    for tab in TAB_REGISTRY:
        try:
            if hasattr(tab, "refresh_ui"):
                tab.refresh_ui()
        except Exception as e:
            print(f"[UI] Refresh failed for {tab}: {e}")


aimbot_thread = None

auto_pistol_thread = None

bhop_thread = None
bhop_instance = None

glow_thread = None
glow_manager = None

triggerbot_thread = None
triggerbot_instance = None

fov_thread = None
fov_changer = None

walkbot_thread = None

def run_walkbot():
    from Features.walk_bot import walk_in_circle
    import threading
import hashlib
from PyQt5.QtCore import QTimer, QElapsedTimer
from PyQt5.QtWidgets import QApplication
try:
    import numpy as np  # optional: speeds up vector math if available
except Exception:
    np = None

    # Set both loops running in parallel
    def walk_loop():
        walk_in_circle()

    def click_loop_thread():
        click_loop()

    walk_thread = threading.Thread(target=walk_loop, daemon=True)
    click_thread = threading.Thread(target=click_loop_thread, daemon=True)

    walk_thread.start()
    click_thread.start()

    walk_thread.join()
    click_thread.join()

def start_walkbot_thread():
    global walkbot_thread
    if walkbot_thread is None or not walkbot_thread.is_alive():
        Config.walkbot_stop = False
        Config.walkbot_enabled = True
        walkbot_thread = threading.Thread(target=run_walkbot, daemon=True)
        walkbot_thread.start()

def stop_walkbot_thread():
    Config.walkbot_enabled = False
    Config.walkbot_stop = True

def start_auto_pistol_thread():
    global auto_pistol_thread
    if not cfg.auto_pistol_enabled:
        return
    if auto_pistol_thread is None or not auto_pistol_thread.is_alive():
        auto_pistol_thread = threading.Thread(target=run_auto_pistol, args=(cfg,), daemon=True)
        auto_pistol_thread.start()

def stop_auto_pistol_thread():
    cfg.auto_pistol_enabled = False

def run_fov():
    global fov_changer
    fov_changer = FOVChanger(cfg)
    fov_changer.run()

def start_fov_thread():
    global fov_thread
    if fov_thread is None or not fov_thread.is_alive():
        cfg.fov_changer_enabled = True
        fov_thread = threading.Thread(target=run_fov, daemon=True)
        fov_thread.start()

def stop_fov_thread():
    global fov_thread
    cfg.fov_changer_enabled = False
    fov_thread = None

def run_triggerbot():
    global triggerbot_instance
    triggerbot_instance = TriggerBot(shared_config=cfg)
    triggerbot_instance.run()

def start_triggerbot_thread():
    global triggerbot_thread
    if triggerbot_thread is None or not triggerbot_thread.is_alive():
        cfg.triggerbot_stop = False
        cfg.triggerbot_enabled = True
        triggerbot_thread = threading.Thread(target=run_triggerbot, daemon=True)
        triggerbot_thread.start()

def stop_triggerbot_thread():
    cfg.triggerbot_enabled = False
    cfg.triggerbot_stop = True

def run_glow():
    global glow_manager
    glow_manager = CS2GlowManager(cfg)
    glow_manager.run()

def start_glow_thread():
    global glow_thread
    if glow_thread is None or not glow_thread.is_alive():
        Config.glow_stop = False
        Config.glow = True
        glow_thread = threading.Thread(target=run_glow, daemon=True)
        glow_thread.start()

def stop_glow_thread():
    global glow_thread, glow_manager
    Config.glow = False
    Config.glow_stop = True
    glow_thread = None
    glow_manager = None

def run_bhop():
    global bhop_instance
    bhop_instance = BHopProcess()
    bhop_instance.run()

def start_bhop_thread():
    global bhop_thread
    if bhop_thread is None or not bhop_thread.is_alive():
        Config.bhop_stop = False
        Config.bhop_enabled = True
        bhop_thread = threading.Thread(target=run_bhop, daemon=True)
        bhop_thread.start()

def stop_bhop_thread():
    Config.bhop_enabled = False
    Config.bhop_stop = True

def run_aimbot():
    start_aim_rcs(cfg)

def start_aimbot_thread():
    global aimbot_thread
    if aimbot_thread is None or not aimbot_thread.is_alive():
        cfg.aim_stop = False
        aimbot_thread = threading.Thread(target=run_aimbot, daemon=True)
        aimbot_thread.start()

def stop_aimbot_thread():
    cfg.stop = True

def run_esp():
    Features.esp.main()

def start_esp_thread():
    esp_thread = threading.Thread(target=run_esp, daemon=True)
    esp_thread.start()

class KeyListenerThread(QThread):
    key_pressed = pyqtSignal(str)

    def run(self):
        key = keyboard.read_event(suppress=True)
        if key.event_type == keyboard.KEY_DOWN:
            self.key_pressed.emit(key.name)

def create_section_separator():
    """Create a horizontal line separator"""
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line

class ConfigTab(QWidget):
    def _tick(self):
            """Centralized per-frame updates. Move lightweight periodic checks here.
            Avoid heavy blocking and defer I/O to worker threads if needed.
            """
            # Example: refresh UI at ~15 FPS to reduce redraws
            if hasattr(self, 'refresh_ui'):
                # throttle refresh to ~15 FPS
                if not hasattr(self, '_last_refresh_ms'):
                    self._last_refresh_ms = 0
                now = self._elapsed.elapsed()
                if now - getattr(self, '_last_refresh_ms', 0) > 66:
                    try:
                        self.refresh_ui()
                    finally:
                        self._last_refresh_ms = now
    config_loaded = pyqtSignal()  # Signal to notify when config is loaded

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(8, 8, 8, 8)  # tighter margins

        # Row: Config name input
        name_row = QHBoxLayout()
        name_label = QLabel("Name:")
        name_label.setFixedWidth(40)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., default")
        name_row.addWidget(name_label)
        name_row.addWidget(self.name_input)
        layout.addLayout(name_row)

        # Row: Dropdown of existing configs
        list_row = QHBoxLayout()
        list_label = QLabel("Saved:")
        list_label.setFixedWidth(40)
        self.config_list = QComboBox()
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(28)
        refresh_btn.clicked.connect(self.refresh_config_list)
        list_row.addWidget(list_label)
        list_row.addWidget(self.config_list)
        list_row.addWidget(refresh_btn)
        layout.addLayout(list_row)

        # Row: Save + Load buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        load_btn = QPushButton("Load")
        save_btn.setFixedHeight(24)
        load_btn.setFixedHeight(24)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(load_btn)
        layout.addLayout(btn_row)

        save_btn.clicked.connect(self.save_config)
        load_btn.clicked.connect(self.load_config)

        self.setLayout(layout)
        self.refresh_config_list()

    def refresh_config_list(self):
        os.makedirs("config", exist_ok=True)
        self.config_list.clear()
        configs = [
            f[:-5] for f in os.listdir("config")
            if f.endswith(".json")
        ]
        self.config_list.addItems(configs)

    def save_config(self):
        name = self.name_input.text().strip()
        if name:
            try:
                cfg.save_to_file(name)
                self.refresh_config_list()
                print(f"[Config] Successfully saved config '{name}'")
            except Exception as e:
                print(f"[Config] Error saving config '{name}': {e}")

    def load_config(self):
        name = self.name_input.text().strip()
        if not name:
            name = self.config_list.currentText()
        if name:
            cfg.load_from_file(name)
            self.config_loaded.emit()  # Emit signal to refresh all tabs

class DataWatcher(QThread):
    data_updated = pyqtSignal()

    def __init__(self, interval=2):
        super().__init__()
        self.interval = interval
        self.running = True

    def run(self):
        while self.running:
            self.data_updated.emit()
            time.sleep(self.interval)

    def stop(self):
        self.running = False
        self.wait()

class TriggerBotTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # Main Enable Checkbox
        self.trigger_checkbox = CheatCheckBox("Enable TriggerBot")
        self.trigger_checkbox.setChecked(getattr(cfg, "triggerbot_enabled", False))
        self.trigger_checkbox.stateChanged.connect(self.toggle_triggerbot)
        layout.addWidget(self.trigger_checkbox)

        layout.addSpacing(10)


        # Trigger Key Section
        key_section = QVBoxLayout()
        key_section.setSpacing(5)

        key_label = QLabel("Key Settings:")
        key_label.setStyleSheet("font-weight: bold;")
        key_section.addWidget(key_label)

        self.trigger_key_label = QLabel(f"Trigger Key: {cfg.trigger_key}")
        self.set_key_btn = QPushButton("Set Trigger Key")
        self.set_key_btn.clicked.connect(self.set_trigger_key)

        key_layout = QHBoxLayout()
        key_layout.setSpacing(10)
        key_layout.addWidget(self.trigger_key_label)
        key_layout.addWidget(self.set_key_btn)
        key_section.addLayout(key_layout)

        layout.addLayout(key_section)
        layout.addWidget(create_section_separator())

        # Settings Section
        settings_section = QVBoxLayout()
        settings_section.setSpacing(8)

        settings_label = QLabel("Behavior Settings:")
        settings_label.setStyleSheet("font-weight: bold;")
        settings_section.addWidget(settings_label)

        # Allow Shooting Teammates Checkbox
        self.shoot_teammates_cb = CheatCheckBox("Allow Shooting Teammates")
        self.shoot_teammates_cb.setChecked(getattr(cfg, "shoot_teammates", False))
        self.shoot_teammates_cb.stateChanged.connect(
            lambda state: setattr(cfg, "shoot_teammates", state == Qt.Checked)
        )
        settings_section.addWidget(self.shoot_teammates_cb)

        # Always On Checkbox - MOVE IT HERE
        self.always_on_cb = CheatCheckBox("Always On (Ignore Trigger Key)")
        self.always_on_cb.setChecked(getattr(cfg, "triggerbot_always_on", False))
        self.always_on_cb.stateChanged.connect(
            lambda state: setattr(cfg, "triggerbot_always_on", state == Qt.Checked)
        )
        settings_section.addWidget(self.always_on_cb)

        settings_section.addSpacing(8)

        # TriggerBot Cooldown Slider and label
        cooldown_layout = QVBoxLayout()
        cooldown_layout.setSpacing(5)

        cooldown_title = QLabel("Cooldown Settings:")
        cooldown_title.setStyleSheet("font-weight: bold; font-size: 10pt;")
        cooldown_layout.addWidget(cooldown_title)

        cooldown_controls = QHBoxLayout()
        cooldown_controls.setSpacing(10)

        cooldown_label = QLabel("Cooldown:")
        cooldown_label.setFixedWidth(70)

        self.cooldown_value = QLabel(f"{cfg.triggerbot_cooldown:.2f}s")
        self.cooldown_value.setFixedWidth(50)
        self.cooldown_slider = NoScrollSlider(Qt.Horizontal)
        self.cooldown_slider.setMinimum(1)
        self.cooldown_slider.setMaximum(100)
        self.cooldown_slider.setValue(int(cfg.triggerbot_cooldown * 10))

        def update_cooldown(value):
            real_val = value / 10.0
            setattr(cfg, "triggerbot_cooldown", real_val)
            self.cooldown_value.setText(f"{real_val:.2f}s")

        self.cooldown_slider.valueChanged.connect(update_cooldown)

        cooldown_controls.addWidget(cooldown_label)
        cooldown_controls.addWidget(self.cooldown_slider)
        cooldown_controls.addWidget(self.cooldown_value)

        cooldown_layout.addLayout(cooldown_controls)
        settings_section.addLayout(cooldown_layout)

        layout.addLayout(settings_section)
        layout.addStretch()

        content_widget.setLayout(layout)
        scroll.setWidget(content_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def refresh_ui(self):
        try:
            self.setUpdatesEnabled(False)
            """Refresh all UI elements with current config values"""
            self.trigger_checkbox.setChecked(getattr(cfg, "triggerbot_enabled", False))
            self.trigger_key_label.setText(f"Trigger Key: {cfg.trigger_key}")
            self.shoot_teammates_cb.setChecked(getattr(cfg, "shoot_teammates", False))
            self.always_on_cb.setChecked(getattr(cfg, "triggerbot_always_on", False))  # ← Added this
            self.cooldown_slider.setValue(int(cfg.triggerbot_cooldown * 10))
            self.cooldown_value.setText(f"{cfg.triggerbot_cooldown:.2f}s")
        finally:
            self.setUpdatesEnabled(True)
    
    
    def toggle_triggerbot(self, state):
        if state == Qt.Checked:
            start_triggerbot_thread()
        else:
            stop_triggerbot_thread()

    def set_trigger_key(self):
        self.set_key_btn.setText("Press any key...")
        self.set_key_btn.setEnabled(False)

        self.listener_thread = KeyListenerThread()
        self.listener_thread.key_pressed.connect(self.key_set)
        self.listener_thread.start()

    def key_set(self, key_name):
        cfg.trigger_key = key_name
        self.trigger_key_label.setText(f"Trigger Key: {cfg.trigger_key}")
        self.set_key_btn.setText("Set Trigger Key")
        self.set_key_btn.setEnabled(True)

class MiscTab(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_elements = {"color_buttons": {}}
        self.init_ui()

    # ---------- Helpers ----------
    def section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; font-size: 12pt; color: #000000;")  # black section titles too
        return lbl

    def add_separator(self, layout: QVBoxLayout):
        layout.addWidget(create_section_separator())

    def rgb_to_stylesheet(self, rgb_or_rgba):
        """Convert RGB/RGBA tuple (int 0–255 or float 0–1) into a valid Qt stylesheet string"""
        if len(rgb_or_rgba) == 4:
            r, g, b, a = rgb_or_rgba
        else:
            r, g, b = rgb_or_rgba
            a = 255

        # Normalize floats in 0–1 range
        if isinstance(r, float) or (isinstance(r, int) and r <= 1):
            r, g, b, a = [int(c * 255) for c in (r, g, b, a)]

        if a >= 255:
            return f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
        else:
            return f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid black;"

    def add_checkbox(self, layout: QVBoxLayout, label: str, cfg_key: str,
                     default: bool = False, thread_start=None, thread_stop=None):
        cb = CheatCheckBox(label)
        cb.setChecked(getattr(Config, cfg_key, default))

        def toggle(state):
            val = (state == Qt.Checked)
            setattr(Config, cfg_key, val)
            if thread_start and val:
                thread_start()
            elif thread_stop and not val:
                thread_stop()

        cb.stateChanged.connect(toggle)
        layout.addWidget(cb)
        self.ui_elements[cfg_key] = cb
        return cb

    def add_color_picker(self, layout: QVBoxLayout, label: str,
                         cfg_key: str, default=(0, 0, 0)):
        row = QHBoxLayout()
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet("color: #000000; font-weight: 600; font-size: 10pt;")  # black labels
        row.addWidget(lbl)

        rgb = getattr(Config, cfg_key, default)
        btn = QPushButton()
        btn.setFixedSize(40, 20)
        btn.setStyleSheet(self.rgb_to_stylesheet(rgb))

        def choose_color():
            current = getattr(Config, cfg_key, default)
            if len(current) == 4:
                current = tuple(int(c * 255) if isinstance(c, float) else c for c in current[:3])
            initial = QColor(*current)
            color = QColorDialog.getColor(initial, self, f"Select {label}")
            if color.isValid():
                new_rgb = (color.red(), color.green(), color.blue())
                setattr(Config, cfg_key, new_rgb)
                btn.setStyleSheet(self.rgb_to_stylesheet(new_rgb))

        btn.clicked.connect(choose_color)
        row.addWidget(btn)
        layout.addLayout(row)

        self.ui_elements["color_buttons"][cfg_key] = btn
        return btn

    # ---------- UI ----------
    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # FOV Section
        fov_section = QVBoxLayout()
        fov_section.addWidget(self.section_title("FOV Changer"))
        self.fov_checkbox = self.add_checkbox(
            fov_section, "Enable FOV Changer", "fov_changer_enabled",
            default=True, thread_start=start_fov_thread, thread_stop=stop_fov_thread
        )
        self.fov_label = QLabel(f"Game FOV: {cfg.game_fov}")
        self.fov_slider = NoScrollSlider(Qt.Horizontal)
        self.fov_slider.setRange(60, 150)
        self.fov_slider.setValue(cfg.game_fov)
        self.fov_slider.valueChanged.connect(self.update_fov)
        fov_section.addWidget(self.fov_label)
        fov_section.addWidget(self.fov_slider)
        layout.addLayout(fov_section)
        self.add_separator(layout)

        # Glow Section
        glow_section = QVBoxLayout()
        glow_section.addWidget(self.section_title("Glow Effects"))
        self.glow_checkbox = self.add_checkbox(
            glow_section, "Enable Glow", "glow",
            default=False, thread_start=start_glow_thread, thread_stop=stop_glow_thread
        )
        self.add_checkbox(glow_section, "Glow Enemies", "glow_show_enemies", default=True)
        self.add_checkbox(glow_section, "Glow Team", "glow_show_team", default=True)
        self.add_color_picker(glow_section, "Enemy Glow Color", "glow_color_enemy", (255, 0, 0))
        self.add_color_picker(glow_section, "Team Glow Color", "glow_color_team", (0, 255, 0))
        layout.addLayout(glow_section)
        self.add_separator(layout)

        # Bunny Hop Section
        bhop_section = QVBoxLayout()
        bhop_section.addWidget(self.section_title("Bunny Hop"))
        self.bhop_checkbox = self.add_checkbox(
            bhop_section, "Enable Bunny Hop", "bhop_enabled",
            thread_start=start_bhop_thread, thread_stop=stop_bhop_thread
        )
        self.add_checkbox(bhop_section, "BHop Information Box", "show_local_info_box", default=True)
        for label, key in [
            ("Coords Text", "color_local_coords_text"),
            ("Velocity Text", "color_local_velocity_text"),
            ("Speed Text", "color_local_speed_text"),
            ("Box Background", "color_local_box_background"),
            ("Box Border", "color_local_box_border"),
        ]:
            self.add_color_picker(bhop_section, label, key, (0, 0, 0))  # all black defaults
        layout.addLayout(bhop_section)
        self.add_separator(layout)

        # Miscellaneous Features Section
        misc_section = QVBoxLayout()
        misc_section.addWidget(self.section_title("Miscellaneous Features"))
        self.add_checkbox(misc_section, "Enable WalkBot", "walkbot_enabled",
                          thread_start=start_walkbot_thread, thread_stop=stop_walkbot_thread)
        self.add_checkbox(misc_section, "Grenade Prediction (simple)", "grenade_prediction_enabled")
        self.add_checkbox(misc_section, "Enable No Flash", "noflash_enabled")
        self.add_checkbox(misc_section, "Spectator List", "spectator_list_enabled")
        self.add_checkbox(misc_section, "Enable Watermark", "watermark_enabled", default=True)
        layout.addLayout(misc_section)
        self.add_separator(layout)

        # Toggle Menu Key Section
        toggle_section = QVBoxLayout()
        toggle_section.addWidget(self.section_title("Toggle Menu Key"))
        self.toggle_key_label = QLabel(f"Current: {cfg.toggle_menu_key}")
        btn = QPushButton("Set Toggle Key")
        btn.clicked.connect(self.set_toggle_key)
        toggle_section.addWidget(self.toggle_key_label)
        toggle_section.addWidget(btn)
        layout.addLayout(toggle_section)

        layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ---------- Event Handlers ----------
    def update_fov(self, value):
        cfg.game_fov = value
        self.fov_label.setText(f"Game FOV: {value}")

    def set_toggle_key(self):
        self.toggle_key_label.setText("Press a key...")
        self.listener_thread = KeyListenerThread()
        self.listener_thread.key_pressed.connect(self.update_toggle_key)
        self.listener_thread.start()

    def update_toggle_key(self, key):
        cfg.toggle_menu_key = key
        self.toggle_key_label.setText(f"Current: {key}")

    def refresh_ui(self):
        """Refresh checkboxes, sliders, and button colors"""
        self.fov_checkbox.setChecked(getattr(cfg, "fov_changer_enabled", True))
        self.fov_slider.setValue(cfg.game_fov)
        self.fov_label.setText(f"Game FOV: {cfg.game_fov}")
        for key, btn in self.ui_elements.get("color_buttons", {}).items():
            rgb = getattr(Config, key, (0, 0, 0))
            btn.setStyleSheet(self.rgb_to_stylesheet(rgb))


class AimbotTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Scrollable container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        self.ui_elements = {}

        # ==============================
        # Main Aimbot Controls
        # ==============================
        main_row = QHBoxLayout()

        self.add_checkbox(main_row, "Enable Aimbot", "enabled")
        self.add_checkbox(main_row, "DeathMatch Mode", "DeathMatch")

        self.auto_pistol_cb = CheatCheckBox("Enable Auto Pistol")
        self.auto_pistol_cb.setChecked(Config.auto_pistol_enabled)
        self.auto_pistol_cb.stateChanged.connect(
            lambda state: self.toggle_auto_pistol(state)
        )
        main_row.addWidget(self.auto_pistol_cb)

        key_label = QLabel("Auto Pistol Key:")
        key_label.setStyleSheet("color: #c5c8c6; font-weight: 600; font-size: 10pt;")
        main_row.addWidget(key_label)

        key_combo = CheatComboBox(
            items=["mouse2", "mouse3", "mouse4", "mouse5", "alt",
                   "ctrl", "shift", "space"],
            width=80
        )
        key_combo.setCurrentText(Config.activation_key.lower())
        key_combo.currentTextChanged.connect(
            lambda val: setattr(Config, "activation_key", val)
        )
        main_row.addWidget(key_combo)

        # Fire rate
        fire_rate_vbox = QVBoxLayout()
        self.fire_rate_label = QLabel(f"Fire Rate: {Config.fire_rate:.2f}s")
        self.fire_rate_slider = NoScrollSlider(Qt.Horizontal)
        self.fire_rate_slider.setMinimum(1)
        self.fire_rate_slider.setMaximum(100)
        self.fire_rate_slider.setValue(int(Config.fire_rate * 100))
        self.fire_rate_slider.setFixedWidth(140)

        def update_fire_rate(val):
            Config.fire_rate = val / 100.0
            self.fire_rate_label.setText(f"Fire Rate: {Config.fire_rate:.2f}s")

        self.fire_rate_slider.valueChanged.connect(update_fire_rate)
        fire_rate_vbox.addWidget(self.fire_rate_label)
        fire_rate_vbox.addWidget(self.fire_rate_slider)

        main_row.addLayout(fire_rate_vbox)
        main_row.addStretch(1)
        layout.addLayout(main_row)
        layout.addWidget(create_section_separator())

        # ==============================
        # Kernel Mode Settings
        # ==============================
        kernel_group = QVBoxLayout()
        kernel_group.addWidget(self.section_title("Kernel Mode (NeacController)"))

        kernel_row = QHBoxLayout()
        self.kernel_mode_cb = CheatCheckBox("Enable Kernel Mode")
        self.kernel_mode_cb.setChecked(getattr(Config, "kernel_mode_enabled", False))
        self.kernel_mode_cb.stateChanged.connect(self.toggle_kernel_mode)
        kernel_row.addWidget(self.kernel_mode_cb)

        self.kernel_auto_start_cb = CheatCheckBox("Auto-start Driver")
        self.kernel_auto_start_cb.setChecked(
            getattr(Config, "kernel_driver_auto_start", True)
        )
        self.kernel_auto_start_cb.stateChanged.connect(
            lambda state: setattr(Config, "kernel_driver_auto_start", state == Qt.Checked)
        )
        kernel_row.addWidget(self.kernel_auto_start_cb)

        self.kernel_fallback_cb = CheatCheckBox("Fallback to Usermode")
        self.kernel_fallback_cb.setChecked(
            getattr(Config, "kernel_fallback_to_usermode", True)
        )
        self.kernel_fallback_cb.stateChanged.connect(
            lambda state: setattr(Config, "kernel_fallback_to_usermode", state == Qt.Checked)
        )
        kernel_row.addWidget(self.kernel_fallback_cb)
        kernel_row.addStretch(1)

        kernel_group.addLayout(kernel_row)

        self.kernel_status_label = QLabel("Status: Not initialized")
        self.kernel_status_label.setStyleSheet(
            "color: #888; font-size: 9pt; font-style: italic;"
        )
        kernel_group.addWidget(self.kernel_status_label)

        layout.addLayout(kernel_group)
        layout.addWidget(create_section_separator())

        # ==============================
        # Advanced Features
        # ==============================
        adv_group = QVBoxLayout()
        adv_group.addWidget(self.section_title("Advanced Features"))

        row1 = QHBoxLayout()
        self.add_checkbox(row1, "Enable Learning", "enable_learning")
        self.add_checkbox(row1, "Enable RCS", "rcs_enabled")
        self.add_checkbox(row1, "Mouse Recording", "enable_mouse_recording")
        self.add_checkbox(row1, "Velocity Prediction", "enable_velocity_prediction")
        self.add_checkbox(row1, "Closest to Crosshair", "closest_to_crosshair")
        row1.addStretch(1)

        adv_group.addLayout(row1)
        layout.addLayout(adv_group)
        layout.addWidget(create_section_separator())

        # ==============================
        # FOV Overlay Settings
        # ==============================
        fov_group = QVBoxLayout()
        fov_group.addWidget(self.section_title("FOV Overlay Settings"))

        row = QHBoxLayout()
        self.add_checkbox(row, "Show FOV Circle", "fov_circle_enabled")
        row.addStretch(1)
        fov_group.addLayout(row)

        color_row = QHBoxLayout()
        color_label = QLabel("FOV Circle Color:")
        color_label.setStyleSheet("color: #000000; font-weight: 600; font-size: 10pt;")
        color_picker = QPushButton()
        color_picker.setFixedSize(40, 20)
        color_picker.setStyleSheet(
            f"background-color: rgb{getattr(Config,'fov_overlay_color',(255,255,255))}; "
            "border: 1px solid black;"
        )

        def choose_color():
            new_color = QColorDialog.getColor(
                QColor(*getattr(Config, 'fov_overlay_color', (255, 255, 255)))
            )
            if new_color.isValid():
                rgb = (new_color.red(), new_color.green(), new_color.blue())
                setattr(Config, "fov_overlay_color", rgb)
                color_picker.setStyleSheet(
                    f"background-color: rgb{rgb}; border: 1px solid black;"
                )
        color_picker.clicked.connect(choose_color)

        color_row.addWidget(color_label)
        color_row.addWidget(color_picker)
        color_row.addStretch(1)
        fov_group.addLayout(color_row)

        layout.addLayout(fov_group)
        layout.addWidget(create_section_separator())

        # ==============================
        # Precision Settings
        # ==============================
        layout.addWidget(self.section_title("Precision Settings"))
        float_grid = QGridLayout()
        float_grid.setHorizontalSpacing(15)
        float_grid.setVerticalSpacing(10)

        self.add_float_slider_to_grid(float_grid, 0, 0, "FOV", "FOV", 0.1, 30.0, 0.1, 10)
        self.add_float_slider_to_grid(float_grid, 0, 1, "Aim Start Delay", "aim_start_delay", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 0, 2, "RCS Scale", "rcs_scale", 0.0, 5.0, 0.1, 10)
        self.add_float_slider_to_grid(float_grid, 0, 3, "Smoothing Base", "smooth_base", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 0, 4, "Smoothing Variance", "smooth_var", 0.0, 1.0, 0.01, 100)

        self.add_float_slider_to_grid(float_grid, 1, 0, "Velocity Prediction Factor", "velocity_prediction_factor", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 1, 1, "Target Switch Delay", "target_switch_delay", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 1, 2, "RCS Smooth Base", "rcs_smooth_base", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 1, 3, "RCS Smooth Variance", "rcs_smooth_var", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 1, 4, "RCS Grace After Damage", "rcs_grace_after_damage", 0.0, 1.0, 0.01, 100)

        layout.addLayout(float_grid)
        layout.addWidget(create_section_separator())

        # ==============================
        # Numeric Settings
        # ==============================
        layout.addWidget(self.section_title("Numeric Settings"))
        int_grid = QGridLayout()
        int_grid.setHorizontalSpacing(15)
        int_grid.setVerticalSpacing(8)

        self.add_int_slider_to_grid(int_grid, 0, 0, "Downward Offset", "downward_offset", 0, 100)
        self.add_int_slider_to_grid(int_grid, 0, 1, "Max Entities", "max_entities", 1, 128)
        self.add_int_slider_to_grid(int_grid, 0, 2, "Max Mouse Move", "max_mouse_move", 1, 50)
        self.add_int_slider_to_grid(int_grid, 0, 3, "Max Delta Angle", "max_delta_angle", 1, 180)

        layout.addLayout(int_grid)
        layout.addWidget(create_section_separator())

        # ==============================
        # Input Settings
        # ==============================
        input_group = QVBoxLayout()
        input_group.addWidget(self.section_title("Input Settings"))

        key_vbox = QVBoxLayout()
        aim_label = QLabel("Aim Activation Key:")
        aim_label.setStyleSheet("color: #000000; font-weight: 600; font-size: 10pt;")
        key_vbox.addWidget(aim_label)

        self.aim_key_combo = CheatComboBox(
            items=["mouse1", "mouse2", "mouse3", "mouse4", "mouse5",
                   "left_shift", "right_shift", "left_ctrl", "right_ctrl",
                   "left_alt", "right_alt", "space"],
            width=100
        )
        self.aim_key_combo.setCurrentText(Config.aim_key)
        self.aim_key_combo.currentTextChanged.connect(
            lambda val: setattr(Config, "aim_key", val)
        )
        key_vbox.addWidget(self.aim_key_combo)
        input_group.addLayout(key_vbox)

        sens_layout = QHBoxLayout()
        self.sens_label = QLabel(f"Sensitivity: {Config.sensitivity:.3f}")
        self.sens_slider = NoScrollSlider(Qt.Horizontal)
        self.sens_slider.setMinimum(8)
        self.sens_slider.setMaximum(1000)
        self.sens_slider.setFixedWidth(150)

        sens_val = max(0.008, min(1.0, getattr(Config, "sensitivity", 0.1)))
        slider_val = 1000 - int(sens_val * 1000) + 8
        self.sens_slider.setValue(slider_val)

        def update_sensitivity(val):
            real = (1000 - val + 8) / 1000.0
            real = max(0.008, min(1.0, real))
            setattr(Config, "sensitivity", real)
            self.sens_label.setText(f"Sensitivity: {real:.3f}")

        self.sens_slider.valueChanged.connect(update_sensitivity)
        sens_layout.addWidget(self.sens_label)
        sens_layout.addWidget(self.sens_slider)

        self.invert_y_cb = CheatCheckBox("Invert Y")
        self.invert_y_cb.setChecked(Config.invert_y == -1)
        self.invert_y_cb.stateChanged.connect(
            lambda state: setattr(Config, "invert_y", -1 if state == Qt.Checked else 1)
        )
        sens_layout.addWidget(self.invert_y_cb)
        sens_layout.addStretch(1)

        input_group.addLayout(sens_layout)
        layout.addLayout(input_group)
        layout.addWidget(create_section_separator())

        # ==============================
        # Target Settings
        # ==============================
        target_group = QVBoxLayout()
        target_group.addWidget(self.section_title("Target Settings"))

        self.bone_select = CheatComboBox(items=["head", "chest"], width=90)
        self.bone_select.setCurrentText(Config.target_bone_name)
        self.bone_select.currentTextChanged.connect(
            lambda val: setattr(Config, "target_bone_name", val)
        )
        target_group.addWidget(self.bone_select)

        self.learn_dir_label = QLabel(f"Learning Dir: {Config.learn_dir}")
        target_group.addWidget(self.learn_dir_label)
        layout.addLayout(target_group)
        layout.addWidget(create_section_separator())

        # --- Humanization (Anti-Detection) ---
        human_group = QVBoxLayout()
        human_group.addWidget(self.section_title("Humanization (Anti-Detection)"))
        
        # Main humanization toggle
        human_row1 = QHBoxLayout()
        self.add_checkbox(human_row1, "Enable Humanization", "humanization_enabled")
        human_group.addLayout(human_row1)
        
        # Jitter controls
        jitter_row = QHBoxLayout()
        self.add_checkbox(jitter_row, "Aim Jitter/Shake", "aim_jitter_enabled")
        human_group.addLayout(jitter_row)
        
        jitter_amount_layout = QVBoxLayout()
        self.jitter_amount_label = QLabel(f"Jitter Amount: {getattr(Config, 'aim_jitter_amount', 0.15):.2f}")
        self.jitter_amount_slider = NoScrollSlider(Qt.Horizontal)
        self.jitter_amount_slider.setMinimum(0)
        self.jitter_amount_slider.setMaximum(100)
        self.jitter_amount_slider.setValue(int(getattr(Config, 'aim_jitter_amount', 0.15) * 100))
        
        def update_jitter_amount(val):
            amount = val / 100.0
            setattr(Config, 'aim_jitter_amount', amount)
            self.jitter_amount_label.setText(f"Jitter Amount: {amount:.2f}")
        
        self.jitter_amount_slider.valueChanged.connect(update_jitter_amount)
        jitter_amount_layout.addWidget(self.jitter_amount_label)
        jitter_amount_layout.addWidget(self.jitter_amount_slider)
        human_group.addLayout(jitter_amount_layout)
        
        jitter_freq_layout = QVBoxLayout()
        self.jitter_freq_label = QLabel(f"Shake Frequency: {getattr(Config, 'aim_shake_frequency', 8.0):.1f} Hz")
        self.jitter_freq_slider = NoScrollSlider(Qt.Horizontal)
        self.jitter_freq_slider.setMinimum(1)
        self.jitter_freq_slider.setMaximum(20)
        self.jitter_freq_slider.setValue(int(getattr(Config, 'aim_shake_frequency', 8.0)))
        
        def update_jitter_freq(val):
            freq = float(val)
            setattr(Config, 'aim_shake_frequency', freq)
            self.jitter_freq_label.setText(f"Shake Frequency: {freq:.1f} Hz")
        
        self.jitter_freq_slider.valueChanged.connect(update_jitter_freq)
        jitter_freq_layout.addWidget(self.jitter_freq_label)
        jitter_freq_layout.addWidget(self.jitter_freq_slider)
        human_group.addLayout(jitter_freq_layout)
        
        # Smooth randomization
        smooth_row = QHBoxLayout()
        self.add_checkbox(smooth_row, "Randomize Smoothness", "smooth_randomization")
        human_group.addLayout(smooth_row)
        
        # Reaction delay
        delay_row = QHBoxLayout()
        self.add_checkbox(delay_row, "Reaction Delay", "reaction_delay_enabled")
        human_group.addLayout(delay_row)
        
        delay_layout = QVBoxLayout()
        self.delay_label = QLabel(f"Delay Range: {getattr(Config, 'reaction_delay_min', 0.01):.3f}s - {getattr(Config, 'reaction_delay_max', 0.08):.3f}s")
        self.delay_min_slider = NoScrollSlider(Qt.Horizontal)
        self.delay_min_slider.setMinimum(1)
        self.delay_min_slider.setMaximum(100)
        self.delay_min_slider.setValue(int(getattr(Config, 'reaction_delay_min', 0.01) * 1000))
        
        self.delay_max_slider = NoScrollSlider(Qt.Horizontal)
        self.delay_max_slider.setMinimum(1)
        self.delay_max_slider.setMaximum(200)
        self.delay_max_slider.setValue(int(getattr(Config, 'reaction_delay_max', 0.08) * 1000))
        
        def update_delay_range():
            min_val = self.delay_min_slider.value() / 1000.0
            max_val = self.delay_max_slider.value() / 1000.0
            setattr(Config, 'reaction_delay_min', min_val)
            setattr(Config, 'reaction_delay_max', max_val)
            self.delay_label.setText(f"Delay Range: {min_val:.3f}s - {max_val:.3f}s")
        
        self.delay_min_slider.valueChanged.connect(update_delay_range)
        self.delay_max_slider.valueChanged.connect(update_delay_range)
        delay_layout.addWidget(self.delay_label)
        delay_layout.addWidget(QLabel("Min:"))
        delay_layout.addWidget(self.delay_min_slider)
        delay_layout.addWidget(QLabel("Max:"))
        delay_layout.addWidget(self.delay_max_slider)
        human_group.addLayout(delay_layout)
        
        # Overshoot
        overshoot_row = QHBoxLayout()
        self.add_checkbox(overshoot_row, "Occasional Overshoot", "overshoot_enabled")
        human_group.addLayout(overshoot_row)
        
        overshoot_layout = QVBoxLayout()
        self.overshoot_label = QLabel(f"Overshoot Chance: {getattr(Config, 'overshoot_chance', 0.15):.0%} | Amount: {getattr(Config, 'overshoot_amount', 1.2):.1f}x")
        self.overshoot_chance_slider = NoScrollSlider(Qt.Horizontal)
        self.overshoot_chance_slider.setMinimum(0)
        self.overshoot_chance_slider.setMaximum(50)
        self.overshoot_chance_slider.setValue(int(getattr(Config, 'overshoot_chance', 0.15) * 100))
        
        self.overshoot_amount_slider = NoScrollSlider(Qt.Horizontal)
        self.overshoot_amount_slider.setMinimum(100)
        self.overshoot_amount_slider.setMaximum(200)
        self.overshoot_amount_slider.setValue(int(getattr(Config, 'overshoot_amount', 1.2) * 100))
        
        def update_overshoot():
            chance = self.overshoot_chance_slider.value() / 100.0
            amount = self.overshoot_amount_slider.value() / 100.0
            setattr(Config, 'overshoot_chance', chance)
            setattr(Config, 'overshoot_amount', amount)
            self.overshoot_label.setText(f"Overshoot Chance: {chance:.0%} | Amount: {amount:.1f}x")
        
        self.overshoot_chance_slider.valueChanged.connect(update_overshoot)
        self.overshoot_amount_slider.valueChanged.connect(update_overshoot)
        overshoot_layout.addWidget(self.overshoot_label)
        overshoot_layout.addWidget(QLabel("Chance:"))
        overshoot_layout.addWidget(self.overshoot_chance_slider)
        overshoot_layout.addWidget(QLabel("Amount:"))
        overshoot_layout.addWidget(self.overshoot_amount_slider)
        human_group.addLayout(overshoot_layout)
        
        layout.addLayout(human_group)

        # Final setup
        scroll.setWidget(content_widget)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        
        # Check actual kernel status on initialization
        self.check_actual_kernel_status()

    def toggle_auto_pistol(self, state):
        Config.auto_pistol_enabled = (state == Qt.Checked)
        if Config.auto_pistol_enabled:
            start_auto_pistol_thread()
        else:
            stop_auto_pistol_thread()
    
    def toggle_kernel_mode(self, state):
        """Toggle kernel mode and reinitialize memory interfaces"""
        import threading
        from PyQt5.QtCore import Qt
        
        # Update config
        Config.kernel_mode_enabled = (state == Qt.Checked)
        
        # Update status label
        self.kernel_status_label.setText("Status: Initializing..." if Config.kernel_mode_enabled else "Status: Disabled")
        self.kernel_status_label.setStyleSheet("color: #ff8800; font-size: 9pt; font-style: italic;")
        
        if Config.kernel_mode_enabled:
            # Try to initialize kernel mode in background thread
            def init_kernel():
                try:
                    # Test kernel driver initialization
                    import sys
                    import os
                    
                    # Add NeacController path
                    controller_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                                 'NeacController-main', 'NeacController')
                    if controller_path not in sys.path:
                        sys.path.insert(0, controller_path)
                    
                    import neac_controller
                    
                    # Test driver initialization
                    test_driver = neac_controller.NeacDriverManager()
                    
                    if test_driver.start_driver():
                        if test_driver.connect():
                            # Success - update status
                            self.kernel_status_label.setText("Status: ✓ Kernel mode active")
                            self.kernel_status_label.setStyleSheet("color: #00ff00; font-size: 9pt; font-style: italic;")
                            print("[GUI] Kernel mode successfully enabled")
                            
                            # Update status overlay
                            update_kernel_status(True)
                            
                            # Cleanup test instance
                            test_driver.disconnect()
                        else:
                            # Connection failed
                            self.kernel_status_label.setText("Status: ✗ Driver connection failed")
                            self.kernel_status_label.setStyleSheet("color: #ff0000; font-size: 9pt; font-style: italic;")
                            print("[GUI] Kernel driver connection failed")
                            test_driver.stop_driver()
                    else:
                        # Driver start failed
                        self.kernel_status_label.setText("Status: ✗ Driver start failed")
                        self.kernel_status_label.setStyleSheet("color: #ff0000; font-size: 9pt; font-style: italic;")
                        print("[GUI] Kernel driver start failed")
                        
                except ImportError:
                    # NeacController module not found
                    self.kernel_status_label.setText("Status: ✗ NeacController module not found")
                    self.kernel_status_label.setStyleSheet("color: #ff0000; font-size: 9pt; font-style: italic;")
                    print("[GUI] NeacController Python module not installed")
                    print("[GUI] Run 'build.bat' as Administrator to build the module")
                except Exception as e:
                    # Other error
                    self.kernel_status_label.setText(f"Status: ✗ Error: {str(e)[:30]}...")
                    self.kernel_status_label.setStyleSheet("color: #ff0000; font-size: 9pt; font-style: italic;")
                    print(f"[GUI] Kernel mode initialization error: {e}")
            
            # Run initialization in background thread
            init_thread = threading.Thread(target=init_kernel, daemon=True)
            init_thread.start()
            
        else:
            # Kernel mode disabled
            self.kernel_status_label.setText("Status: Disabled")
            self.kernel_status_label.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
            print("[GUI] Kernel mode disabled")
            
            # Update status overlay
            update_kernel_status(False)
            
            # Try to cleanup any existing kernel drivers
            try:
                import sys
                import os
                controller_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                             'NeacController-main', 'NeacController')
                if controller_path not in sys.path:
                    sys.path.insert(0, controller_path)
                
                import neac_controller
                
                # Create instance just to stop driver
                cleanup_driver = neac_controller.NeacDriverManager()
                cleanup_driver.stop_driver()
                print("[GUI] Kernel driver stopped")
            except:
                pass  # Ignore cleanup errors

    def refresh_ui(self):
        """Refresh all UI elements with current config values"""

        # --- Kernel Mode Settings ---
        if hasattr(self, 'kernel_mode_cb'):
            self.kernel_mode_cb.setChecked(getattr(Config, "kernel_mode_enabled", False))
        if hasattr(self, 'kernel_auto_start_cb'):
            self.kernel_auto_start_cb.setChecked(getattr(Config, "kernel_driver_auto_start", True))
        if hasattr(self, 'kernel_fallback_cb'):
            self.kernel_fallback_cb.setChecked(getattr(Config, "kernel_fallback_to_usermode", True))

    def check_actual_kernel_status(self):
        """Check the actual kernel mode status from config and update display"""
        try:
            # Just check config for now, don't initialize memory interface early
            if getattr(Config, "kernel_mode_enabled", False):
                self.kernel_status_label.setText("Status: ⚠️ Initializing...")
                self.kernel_status_label.setStyleSheet("color: #ff8800; font-size: 9pt; font-style: italic;")
                print("[GUI] Kernel status: Enabled in config")
                
                # Start a timer to check actual status later after initialization
                QTimer.singleShot(3000, self.check_kernel_status_delayed)
            else:
                self.kernel_status_label.setText("Status: Disabled")
                self.kernel_status_label.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
                print("[GUI] Kernel status: Disabled in config")
                
        except Exception as e:
            print(f"[GUI] Error checking kernel status: {e}")
            self.kernel_status_label.setText("Status: Error")
            self.kernel_status_label.setStyleSheet("color: #ff0000; font-size: 9pt; font-style: italic;")
    
    def check_kernel_status_delayed(self):
        """Check actual kernel status after memory interfaces are initialized"""
        try:
            # Check if any memory interface has kernel mode active
            # Look for global kernel status indicators
            if hasattr(Config, '_kernel_active_instances') and Config._kernel_active_instances > 0:
                self.kernel_status_label.setText("Status: ✓ Kernel mode active")
                self.kernel_status_label.setStyleSheet("color: #00ff00; font-size: 9pt; font-style: italic;")
                print("[GUI] Kernel status check: ACTIVE")
            elif getattr(Config, "kernel_mode_enabled", False):
                self.kernel_status_label.setText("Status: ⚠️ Starting...")
                self.kernel_status_label.setStyleSheet("color: #ff8800; font-size: 9pt; font-style: italic;")
                # Check again in a few seconds
                QTimer.singleShot(2000, self.check_kernel_status_delayed)
            
        except Exception as e:
            print(f"[GUI] Error in delayed kernel check: {e}")

        # --- Checkboxes ---
        for attr, checkbox in self.ui_elements.get('checkboxes', {}).items():
            checkbox.setChecked(getattr(Config, attr))

        # --- Float Sliders ---
        for attr, (slider, label, mult) in self.ui_elements.get('float_sliders', {}).items():
            val = getattr(Config, attr)
            slider.setValue(int(val * mult))
            label.setText(f"{attr.replace('_', ' ').title()}: {val:.2f}")

        # --- Int Sliders ---
        for attr, (slider, label) in self.ui_elements.get('int_sliders', {}).items():
            val = getattr(Config, attr)
            slider.setValue(val)
            label.setText(f"{attr.replace('_', ' ').title()}: {val}")

        # --- Line Edits ---
        for attr, edit in self.ui_elements.get('line_edits', {}).items():
            edit.setText(str(getattr(Config, attr)))

        # --- Comboboxes ---
        if hasattr(self, 'bone_select'):
            self.bone_select.setCurrentText(Config.target_bone_name)
        if hasattr(self, 'aim_key_combo'):
            self.aim_key_combo.setCurrentText(Config.aim_key)
        if hasattr(self, 'auto_pistol_key_combo'):
            self.auto_pistol_key_combo.setCurrentText(Config.activation_key.lower())

        # --- Labels ---
        if hasattr(self, 'learn_dir_label'):
            self.learn_dir_label.setText(f"Learning Dir: {Config.learn_dir}")
        if hasattr(self, 'fire_rate_label'):
            self.fire_rate_label.setText(f"Fire Rate: {Config.fire_rate:.2f}s")
        if hasattr(self, 'sens_label'):
            self.sens_label.setText(f"Sensitivity: {Config.sensitivity:.3f}")

        # --- Color Buttons ---
        for attr, btn in self.ui_elements.get('color_buttons', {}).items():
            color = getattr(Config, attr, (255, 255, 255))
            btn.setStyleSheet(f"background-color: rgb{color}; border: 1px solid black;")

        # --- Sliders ---
        if hasattr(self, 'fire_rate_slider'):
            self.fire_rate_slider.setValue(int(Config.fire_rate * 100))

        if hasattr(self, 'sens_slider'):
            sens_val = max(0.008, min(1.0, getattr(Config, "sensitivity", 0.1)))
            slider_val = 1000 - int(sens_val * 1000) + 8
            self.sens_slider.setValue(slider_val)

        # --- Individual Checkboxes ---
        if hasattr(self, 'auto_pistol_cb'):
            self.auto_pistol_cb.setChecked(Config.auto_pistol_enabled)
        if hasattr(self, 'invert_y_cb'):
            self.invert_y_cb.setChecked(Config.invert_y == -1)

    def section_title(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        return label

    def add_checkbox(self, layout, label, attr):
        cb = CheatCheckBox(label)
        cb.setChecked(getattr(Config, attr, False))  # Add default value
        cb.stateChanged.connect(lambda state: setattr(Config, attr, state == Qt.Checked))
        layout.addWidget(cb)

        # Store reference for refresh
        if 'checkboxes' not in self.ui_elements:
            self.ui_elements['checkboxes'] = {}
        self.ui_elements['checkboxes'][attr] = cb

    def add_float_slider_to_grid(self, grid, row, col, label_text, attr, min_val, max_val, step, mult):
        val = getattr(Config, attr)
        label_widget = QLabel(f"{label_text}: {val:.2f}")
        slider = NoScrollSlider(Qt.Horizontal)
        slider.setMinimum(int(min_val * mult))
        slider.setMaximum(int(max_val * mult))
        slider.setValue(int(val * mult))

        def update(val):
            real = val / mult
            setattr(Config, attr, real)
            label_widget.setText(f"{label_text}: {real:.2f}")

        slider.valueChanged.connect(update)

        vbox = QVBoxLayout()
        vbox.addWidget(label_widget)
        vbox.addWidget(slider)

        container = QWidget()
        container.setLayout(vbox)
        grid.addWidget(container, row, col)

        # Store reference for refresh
        if 'float_sliders' not in self.ui_elements:
            self.ui_elements['float_sliders'] = {}
        self.ui_elements['float_sliders'][attr] = (slider, label_widget, mult)

    def add_int_slider_to_grid(self, grid, row, col, label_text, attr, min_val, max_val):
        val = getattr(Config, attr)
        label_widget = QLabel(f"{label_text}: {val}")
        slider = NoScrollSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(val)

        def update(val):
            setattr(Config, attr, val)
            label_widget.setText(f"{label_text}: {val}")

        slider.valueChanged.connect(update)

        vbox = QVBoxLayout()
        vbox.addWidget(label_widget)
        vbox.addWidget(slider)

        container = QWidget()
        container.setLayout(vbox)
        grid.addWidget(container, row, col)

        # Store reference for refresh
        if 'int_sliders' not in self.ui_elements:
            self.ui_elements['int_sliders'] = {}
        self.ui_elements['int_sliders'][attr] = (slider, label_widget)

    def add_line_edit_to_grid(self, grid, row, col, label_text, attr, typ):
        val = getattr(Config, attr)
        label_widget = QLabel(f"{label_text}:")
        edit = QLineEdit(str(val))

        def update_cfg_value():
            try:
                new_val = typ(edit.text())
                if attr == "sensitivity":
                    # Delay the update to prevent QObject::killTimer crash
                    QTimer.singleShot(100, lambda: setattr(Config, attr, new_val))
                else:
                    setattr(Config, attr, new_val)
            except ValueError:
                print(f"[Warning] Invalid value entered for {attr}, keeping previous.")

        edit.editingFinished.connect(update_cfg_value)

        vbox = QVBoxLayout()
        vbox.addWidget(label_widget)
        vbox.addWidget(edit)

        container = QWidget()
        container.setLayout(vbox)
        grid.addWidget(container, row, col)

        # Store reference for refresh
        if 'line_edits' not in self.ui_elements:
            self.ui_elements['line_edits'] = {}
        self.ui_elements['line_edits'][attr] = edit

    def refresh_ui(self):
        """Refresh AimbotTab UI elements - minimal implementation"""
        try:
            # Only refresh aimbot-specific checkboxes stored in ui_elements
            for attr, checkbox in self.ui_elements.get('checkboxes', {}).items():
                checkbox.setChecked(getattr(Config, attr, False))
                
            # Refresh individual aimbot controls if they exist
            if hasattr(self, 'auto_pistol_cb'):
                self.auto_pistol_cb.setChecked(getattr(Config, 'auto_pistol_enabled', False))
        except Exception as e:
            print(f"[GUI] Error refreshing aimbot UI: {e}")


VK_CODES = {
    "delete": 0x2E,
    "f12": 0x7B,
    "end": 0x23,
    "insert": 0x2D,
    # add more keys as needed
}

def key_to_vk(key_name):
    return VK_CODES.get(key_name.lower(), 0x7B)  # default F12

VK_NAME = {v: k.upper() for k, v in VK_CODES.items()}

def vk_to_name(vk_code):
    return VK_NAME.get(vk_code, "UNKNOWN")

class ESPTab(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_elements = {"checkboxes": {}, "sliders": {}, "comboboxes": {}, "color_buttons": {}, "labels": {}}
        self.init_ui()

    # ----------------- Helpers -----------------
    def section_title(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; font-size: 12pt; color: #000000;")
        return lbl

    def add_separator(self, layout):
        layout.addWidget(create_section_separator())

    def add_checkbox(self, layout, label, cfg_key):
        cb = CheatCheckBox(label)
        cb.setChecked(getattr(Config, cfg_key, False))
        cb.stateChanged.connect(lambda st: setattr(Config, cfg_key, st == Qt.Checked))
        layout.addWidget(cb)
        self.ui_elements["checkboxes"][cfg_key] = cb
        return cb

    def add_checkbox_to_grid(self, grid, row, col, label, cfg_key):
        cb = CheatCheckBox(label)
        cb.setChecked(getattr(Config, cfg_key, False))

        def on_state(st):
            enabled = st == Qt.Checked
            setattr(Config, cfg_key, enabled)
            if cfg_key == "obs_protection_enabled" and hasattr(self, "main_window"):
                self.main_window.set_obs_protection(enabled)

        cb.stateChanged.connect(on_state)
        grid.addWidget(cb, row, col)
        self.ui_elements["checkboxes"][cfg_key] = cb
        return cb

    def add_combobox(self, layout, label, options, cfg_key, row=None, col=None):
        hbox = QHBoxLayout()
        hbox.addWidget(QLabel(label))
        combo = QComboBox()
        combo.addItems(options)
        current = getattr(Config, cfg_key, options[0]).lower()
        idx = combo.findText(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentTextChanged.connect(lambda v: setattr(Config, cfg_key, v.lower()))
        hbox.addWidget(combo)

        cont = QWidget()
        cont.setLayout(hbox)
        if isinstance(layout, QGridLayout) and row is not None and col is not None:
            layout.addWidget(cont, row, col)
        else:
            layout.addWidget(cont)

        self.ui_elements["comboboxes"][cfg_key] = combo
        return combo

    def add_slider(self, layout, label, cfg_key, min_val, max_val):
        val = getattr(Config, cfg_key, min_val)
        lbl = QLabel(f"{label}: {val}")
        slider = NoScrollSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(val)

        def on_change(v):
            setattr(Config, cfg_key, v)
            lbl.setText(f"{label}: {v}")

        slider.valueChanged.connect(on_change)
        layout.addWidget(lbl)
        layout.addWidget(slider)
        self.ui_elements["sliders"][cfg_key] = (slider, lbl)
        return slider

    def add_color_picker_to_grid(self, grid, row, col, label, cfg_key):
        rgb = getattr(Config, cfg_key, (255, 255, 255))
        btn = QPushButton()
        btn.setFixedSize(40, 20)
        btn.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")

        def choose():
            initial = QColor(*rgb)
            new = QColorDialog.getColor(initial, self, f"Select {label} Color")
            if new.isValid():
                new_rgb = (new.red(), new.green(), new.blue())
                setattr(Config, cfg_key, new_rgb)
                btn.setStyleSheet(f"background-color: rgb{new_rgb}; border: 1px solid black;")

        btn.clicked.connect(choose)

        row_layout = QHBoxLayout()
        row_layout.addWidget(QLabel(label))
        row_layout.addWidget(btn)
        cont = QWidget()
        cont.setLayout(row_layout)
        grid.addWidget(cont, row, col)

        self.ui_elements["color_buttons"][cfg_key] = btn
        return btn

    # ----------------- UI -----------------
    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # --- Team Filter ---
        layout.addWidget(self.section_title("Team Filter"))
        team_grid = QGridLayout()
        self.add_checkbox_to_grid(team_grid, 0, 0, "Enemy Only", "esp_show_enemies_only")
        self.add_checkbox_to_grid(team_grid, 0, 1, "Team Only", "esp_show_team_only")
        layout.addLayout(team_grid)
        self.add_separator(layout)

        # --- Panic ---
        layout.addWidget(self.section_title("Panic Settings"))
        panic_row = QHBoxLayout()
        panic_lbl = QLabel(f"Panic Key: {vk_to_name(getattr(Config, 'panic_key', 0x7B))}")
        panic_btn = QPushButton("Set Panic Key")

        def set_panic():
            panic_btn.setText("Press a key...")
            self.listener_thread = KeyListenerThread()
            self.listener_thread.key_pressed.connect(lambda key: self.update_panic_key(key, panic_lbl, panic_btn))
            self.listener_thread.start()

        panic_btn.clicked.connect(set_panic)
        panic_row.addWidget(panic_lbl)
        panic_row.addWidget(panic_btn)
        layout.addLayout(panic_row)
        self.ui_elements["labels"]["panic_key"] = panic_lbl
        self.add_separator(layout)

        # --- Basic ESP ---
        layout.addWidget(self.section_title("Basic ESP Features"))
        basic_grid = QGridLayout()
        features = [
            ("Hide from Screen Capture", "obs_protection_enabled"),
            ("Visible Only ESP", "visible_only_esp_enabled"),
            ("Show Box ESP", "show_box_esp"),
            ("Health Bar", "healthbar_enabled"),
            ("Armor Bar", "armorbar_enabled"),
            ("Health Text", "health_esp_enabled"),
            ("Name ESP", "name_esp_enabled"),
            ("Weapon ESP", "weapon_esp_enabled"),
            ("Armor Text", "armor_esp_enabled"),
            ("Distance ESP", "distance_esp_enabled"),
        ]
        for i, (label, attr) in enumerate(features):
            self.add_checkbox_to_grid(basic_grid, i // 3, i % 3, label, attr)

        # Box style dropdown
        combo = self.add_combobox(basic_grid, "Box ESP Style:", ["normal", "rounded", "corner"], "box_esp_style", row=4, col=0)
        layout.addLayout(basic_grid)
        self.add_separator(layout)

        # --- Overlay Mode ---
        layout.addWidget(self.section_title("Overlay Renderer"))
        self.add_checkbox(layout, "Use GPU (DX11) Overlay", "use_gpu_overlay")
        self.add_separator(layout)

        # --- Visibility ---
        layout.addWidget(self.section_title("Visibility ESP"))
        vis_row = QHBoxLayout()
        self.add_checkbox(vis_row, "Enable Visibility ESP", "visibility_esp_enabled")
        self.add_checkbox(vis_row, "Show Visibility Text", "visibility_text_enabled")
        vis_cont = QWidget(); vis_cont.setLayout(vis_row)
        layout.addWidget(vis_cont)

        # --- Advanced ESP ---
        layout.addWidget(self.section_title("Advanced ESP Features"))
        adv_grid = QGridLayout()
        adv_features = [
            ("Draw Dead Players", "draw_dead_entities"),
            ("Flash ESP", "flash_esp_enabled"),
            ("Scope ESP", "scope_esp_enabled"),
            ("Head ESP", "head_esp_enabled"),
            ("Skeleton ESP", "skeleton_esp_enabled"),
            ("Bomb ESP", "bomb_esp_enabled"),
            ("Money ESP", "money_esp_enabled"),
            ("Velocity ESP", "velocity_esp"),
            ("Velocity ESP Text", "velocity_esp_text"),
            ("Speed ESP", "speed_esp"),
            ("Coordinate ESP", "coordinates_esp_enabled"),
            ("Trace ESP", "trace_esp_enabled"),
            ("Show Drawing FPS", "show_overlay_fps"),
            ("Show Map Status Box", "show_map_status_box"),
        ]
        self.add_slider(layout, "Max Trace Points", "trace_esp_max_points", 10, 500)
        for i, (label, attr) in enumerate(adv_features):
            self.add_checkbox_to_grid(adv_grid, i // 3, i % 3, label, attr)
        layout.addLayout(adv_grid)
        self.add_separator(layout)

        # --- Crosshair ---
        layout.addWidget(self.section_title("Crosshair Settings"))
        self.add_checkbox(layout, "Enable External Crosshair", "draw_crosshair_enabled")
        self.add_slider(layout, "Crosshair Size", "crosshair_size", 1, 20)
        self.add_separator(layout)

        # --- Line ESP ---
        layout.addWidget(self.section_title("Line ESP"))
        line_row = QHBoxLayout()
        self.add_checkbox(line_row, "Enable Line ESP", "line_esp_enabled")
        self.add_combobox(line_row, "Line ESP Position:", ["top", "bottom"], "line_esp_position")
        cont = QWidget(); cont.setLayout(line_row)
        layout.addWidget(cont)
        self.add_separator(layout)

        # --- Bone Dot ESP ---
        layout.addWidget(self.section_title("Bone Dot ESP"))
        bone_row = QHBoxLayout()
        self.add_checkbox(bone_row, "Enable Bone Dot ESP", "bone_dot_esp_enabled")
        cont = QWidget(); cont.setLayout(bone_row)
        layout.addWidget(cont)
        self.add_slider(layout, "Bone Dot Size", "bone_dot_size", 1, 20)
        self.add_separator(layout)

        # --- Size Settings ---
        layout.addWidget(self.section_title("Size Settings"))
        self.add_slider(layout, "Head ESP Size", "head_esp_size", 1, 50)
        self.add_separator(layout)

        # --- Shape Settings ---
        layout.addWidget(self.section_title("Shape Settings"))
        shape_grid = QGridLayout()
        self.add_combobox(shape_grid, "Head ESP Shape:", ["circle", "square"], "head_esp_shape", 0, 0)
        self.add_combobox(shape_grid, "Bone Dot Shape:", ["circle", "square"], "bone_dot_shape", 0, 1)
        layout.addLayout(shape_grid)
        self.add_separator(layout)

        # --- Colors ---
        layout.addWidget(self.section_title("ESP Colors"))
        color_grid = QGridLayout()
        colors = [
            ("Box (T)", "color_box_t"), ("Box (CT)", "color_box_ct"), ("Bone", "color_bone"),
            ("Head", "color_head"), ("Health Bar", "color_healthbar"), ("Armor Bar", "color_armorbar"),
            ("Name", "color_name"), ("Name Effects", "color_name_effects"),
            ("HP Text", "color_hp_text"), ("Armor Text", "color_armor_text"),
            ("Distance", "color_distance"), ("Flash/Scope", "color_flash_scope"),
            ("Spectators", "color_spectators"), ("Skeleton", "color_bone"),
            ("Bone Dot", "bone_dot_color"), ("Weapon Text", "color_weapon_text"),
            ("Crosshair", "crosshair_color"), ("Velocity Text", "velocity_text_color"),
            ("Velocity ESP", "velocity_esp_color"), ("Speed ESP", "speed_esp_color"),
            ("Coordinate ESP", "coordinates_esp_color"), ("Trace ESP", "trace_esp_color"),
            ("Money ESP", "color_money_text"), ("Visible Text", "color_visible_text"),
            ("Not Visible Text", "color_not_visible_text"),
            ("Color Dead CT", "color_dead_ct"),
            ("Color Dead T", "color_dead_t"),
        ]
        for i, (label, attr) in enumerate(colors):
            self.add_color_picker_to_grid(color_grid, i // 3, i % 3, label, attr)
        layout.addLayout(color_grid)

        layout.addStretch()
        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ----------------- Panic Key -----------------
    def update_panic_key(self, key, label, btn):
        vk = key_to_vk(key)
        setattr(Config, "panic_key", vk)
        label.setText(f"Panic Key: {key}")
        btn.setText("Set Panic Key")
        btn.setEnabled(True)

    # ----------------- Refresh -----------------
    def refresh_ui(self):
        # Checkboxes
        for k, cb in self.ui_elements["checkboxes"].items():
            cb.setChecked(getattr(Config, k, False))
        # Sliders
        for k, (s, l) in self.ui_elements["sliders"].items():
            v = getattr(Config, k, 1)
            s.setValue(v)
            l.setText(f"{k.replace('_',' ').title()}: {v}")
        # Comboboxes
        for k, c in self.ui_elements["comboboxes"].items():
            if k == "visibility_map_file":
                self.refresh_map_list()
                current = getattr(Config, "visibility_map_file", "")
                if current:
                    idx = c.findText(current)
                    if idx >= 0: c.setCurrentIndex(idx)
            else:
                current = getattr(Config, k, "")
                idx = c.findText(current)
                if idx >= 0: c.setCurrentIndex(idx)
        # Colors
        for k, b in self.ui_elements["color_buttons"].items():
            rgb = getattr(Config, k, (255,255,255))
            b.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")
        # Panic
        if "panic_key" in self.ui_elements["labels"]:
            vk = getattr(Config, "panic_key", 0x7B)
            self.ui_elements["labels"]["panic_key"].setText(f"Panic Key: {vk_to_name(vk)}")

    # ----------------- Maps -----------------
    def refresh_map_list(self):
        maps_folder = "maps"; self.map_combo.clear(); os.makedirs(maps_folder, exist_ok=True)
        try:
            files = [f for f in os.listdir(maps_folder) if f.lower().endswith(".opt")]
            if files:
                files.sort(); self.map_combo.addItems(files)
                current = getattr(Config, "visibility_map_file", "")
                if current in files:
                    idx = self.map_combo.findText(current)
                    if idx >= 0: self.map_combo.setCurrentIndex(idx)
                else:
                    self.map_combo.setCurrentIndex(0)
                    setattr(Config, "visibility_map_file", files[0])
            else:
                self.map_combo.addItem("No maps found - add .opt files")
        except Exception as e:
            print(f"[VIS-CHECK] Error refreshing map list: {e}")
            self.map_combo.addItem("Error reading maps folder")

    def on_map_selection_changed(self, selected):
        if not selected or "No maps" in selected or "Error" in selected: return
        try:
            setattr(Config, "visibility_map_file", selected)
            if hasattr(Config, "current_loaded_map") and Config.current_loaded_map:
                print(f"[VIS-CHECK] Unloading: {Config.current_loaded_map}")
                self.unload_current_map()
            print(f"[VIS-CHECK] Request load: {selected}")
            if self.load_map_for_visibility_check(selected):
                Config.current_loaded_map = selected
                print(f"[VIS-CHECK] Loaded: {selected}")
            else:
                Config.current_loaded_map = None
        except Exception as e:
            print(f"[VIS-CHECK] Error changing map: {e}")

    def load_map_for_visibility_check(self, fn):
        path = os.path.join("maps", fn)
        if not os.path.exists(path): return False
        setattr(Config, "visibility_map_path", path)
        setattr(Config, "visibility_map_loaded", True)
        setattr(Config, "visibility_map_reload_needed", True)
        print(f"[VIS-CHECK] Map reload scheduled: {path}")
        return True

    def unload_current_map(self):
        setattr(Config, "visibility_map_path", "")
        setattr(Config, "visibility_map_loaded", False)
        setattr(Config, "visibility_map_reload_needed", True)
        print("[VIS-CHECK] Map unload scheduled")

def start_toggle_listener(main_window):
    def listen():
        while True:
            try:
                if keyboard.is_pressed(cfg.toggle_menu_key):
                    main_window.setVisible(not main_window.isVisible())
                    while keyboard.is_pressed(cfg.toggle_menu_key):
                        pass
                time.sleep(0.016)
            except Exception as e:
                print(f"[Toggle Listener] Exception occurred: {e}")
                break

    t = threading.Thread(target=listen, daemon=True)
    t.start()

# RecoilViewer.py — drop-in replacement for your class
# Mirrors aimbot.py learning format & math; respects Config.learn_dir
import os, re, json, math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QScrollArea
)
from PyQt5.QtCore import Qt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

try:
    # Use the same Config the aimbot uses
    from Process.config import Config
except Exception:
    class _F: pass
    Config = _F()
    setattr(Config, "learn_dir", "learn")
    setattr(Config, "sensitivity", 0.022)
    setattr(Config, "invert_y", -1)

LEARN_DIR = "aimbot_data"

class RecoilViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 600)

        self.weapon_ids = []
        self.all_data = {}
        self._last_aimbot_plot_hash = None

        self.spray_mode = True  # True = spray path, False = movement path
        self.init_ui()
        self.scan_aimbot_data()

        self.watcher_thread = DataWatcher()
        self.watcher_thread.data_updated.connect(self.scan_aimbot_data)
        self.watcher_thread.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # --- Header ---
        header_label = QLabel("Recoil Analyzer")
        header_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 10pt;
                color: #000000;
                background: #C0C0C0;
            }
        """)
        layout.addWidget(header_label)

        # --- Weapon Selector + Mode Toggle ---
        selector = QHBoxLayout()
        lbl = QLabel("Weapon:")
        lbl.setStyleSheet("color: #000000; font-size: 8pt;")

        self.dropdown = QComboBox()
        self.dropdown.setStyleSheet("""
            QComboBox {
                background: #FFFFFF;
                border: 1px solid #000000;
                padding: 1px 3px;
                min-height: 16px;
            }
            QComboBox::drop-down {
                width: 14px;
                border-left: 1px solid #000000;
            }
            QComboBox QAbstractItemView {
                background: #FFFFFF;
                color: #000000;
                selection-background-color: #000000;
                selection-color: #FFFFFF;
            }
        """)
        self.dropdown.currentTextChanged.connect(self.update_view)

        # Toggle button
        self.mode_checkbox = QCheckBox("Show Spray Path")
        self.mode_checkbox.setStyleSheet("color: #000000; font-size: 8pt;")
        self.mode_checkbox.setChecked(True)
        self.mode_checkbox.stateChanged.connect(self.toggle_mode)

        selector.addWidget(lbl)
        selector.addWidget(self.dropdown, 1)
        selector.addWidget(self.mode_checkbox)
        layout.addLayout(selector)

        # --- Content Split ---
        content = QHBoxLayout()

        # Graph
        self.canvas = FigureCanvas(Figure(facecolor="#C0C0C0"))
        self.ax = self.canvas.figure.add_subplot(111)
        self.ax.set_facecolor("#C0C0C0")
        self.ax.tick_params(axis="x", colors="black", labelsize=8)
        self.ax.tick_params(axis="y", colors="black", labelsize=8)
        self.ax.set_title("Trace Map", fontsize=9, color="black")
        content.addWidget(self.canvas, 2)

        # Stats panel
        self.stats_scroll = QScrollArea()
        self.stats_scroll.setWidgetResizable(True)
        self.stats_scroll.setStyleSheet("""
            QScrollArea {
                background: #E0E0E0;
                border: 1px solid #000000;
            }
        """)
        self.stats_widget = QWidget()
        self.stats_layout = QVBoxLayout(self.stats_widget)
        self.stats_layout.setContentsMargins(6, 6, 6, 6)
        self.stats_scroll.setWidget(self.stats_widget)
        content.addWidget(self.stats_scroll, 3)

        layout.addLayout(content)

    # -------------------------
    # Mode toggle
    # -------------------------
    def toggle_mode(self, state):
        self.spray_mode = bool(state)  # checked = spray path, unchecked = movement path
        self.update_view(self.dropdown.currentText())

    # -------------------------
    # Data scanning (merge raw_mouse + normal into one per weapon)
    # -------------------------
    def scan_aimbot_data(self):
        if not os.path.exists(LEARN_DIR):
            self.weapon_ids = []
            self.all_data = {}
            self.dropdown.clear()
            self.ax.clear()
            self.canvas.draw()
            return

        files = [f for f in os.listdir(LEARN_DIR) if f.endswith(".json")]
        new_weapon_ids = set()
        merged_data = {}

        for fname in files:
            wid = fname[:-5]
            path = os.path.join(LEARN_DIR, fname)
            if os.path.getsize(path) == 0:
                continue

            try:
                with open(path, "r") as f:
                    data = json.load(f)

                if wid.startswith("raw_mouse_"):
                    base = wid.replace("raw_mouse_", "")
                    new_weapon_ids.add(base)
                    if base not in merged_data:
                        merged_data[base] = {}
                    merged_data[base]["raw_mouse"] = data if isinstance(data, list) else []
                else:
                    base = wid
                    new_weapon_ids.add(base)
                    if base not in merged_data:
                        merged_data[base] = {}
                    if isinstance(data, dict):
                        merged_data[base].update(data)
                    elif isinstance(data, list):
                        merged_data[base]["raw_mouse"] = data
                    else:
                        merged_data[base] = {}

            except Exception as e:
                print(f"[RecoilViewer] Error loading {fname}: {e}")

        if set(new_weapon_ids) != set(self.weapon_ids):
            self.weapon_ids = sorted(new_weapon_ids)
            self.all_data = merged_data
            self.dropdown.clear()
            for wid in self.weapon_ids:
                self.dropdown.addItem(wid)

            if self.weapon_ids:
                self.dropdown.setCurrentText(self.weapon_ids[0])
                self.update_view(self.weapon_ids[0])

    # -------------------------
    # Update graph + stats
    # -------------------------
    def update_view(self, weapon_id):
        self.ax.clear()
        self.ax.set_facecolor("#C0C0C0")
        self.ax.grid(True, linestyle="--", color="#808080", alpha=0.6)
        self.ax.set_xlabel("Yaw Δ", color="black")
        self.ax.set_ylabel("Pitch Δ", color="black")
        self.ax.set_title(f"Trace Map ({weapon_id})", fontsize=9, color="black")

        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        data = self.all_data.get(weapon_id, {})
        items = data.items() if isinstance(data, dict) else []

        colors = ["black", "red", "blue", "green", "purple", "orange"]
        color_idx = 0
        drew_any = False

        for key, vectors in items:
            if not vectors:
                continue

            # Both modes use cumulative integration, but plotted differently
            x, y = [0], [0]
            for entry in vectors:
                try:
                    dp, dy = float(entry[0]), float(entry[1])
                except Exception:
                    continue
                x.append(x[-1] + dy)
                y.append(y[-1] + dp)

            if len(x) > 1:
                if self.spray_mode:
                    # Spray trajectory line
                    self.ax.plot(x, y,
                                 color=colors[color_idx % len(colors)],
                                 linewidth=1.5,
                                 alpha=0.9,
                                 marker=".", markersize=2,
                                 label=key)
                else:
                    # Movement animation line
                    self.ax.plot(x, y,
                                 color=colors[color_idx % len(colors)],
                                 linewidth=1,
                                 alpha=0.7,
                                 marker="o", markersize=2,
                                 label=key)
                drew_any = True

            color_idx += 1

            dataset_header = QLabel(f"Dataset: {key}")
            dataset_header.setStyleSheet("font-weight: bold; font-size: 9pt; color: #000000; margin-top: 6px;")
            self.stats_layout.addWidget(dataset_header)

            self.add_stats_summary(key, vectors)

            bursts = self.split_bursts(vectors)
            if bursts:
                burst_header = QLabel(f"Burst Analysis ({key})")
                burst_header.setStyleSheet(
                    "font-weight: bold; font-size: 9pt; color: #000000; margin-top: 4px;"
                )
                self.stats_layout.addWidget(burst_header)
                for b_idx, burst in enumerate(bursts, 1):
                    self.add_burst_summary(b_idx, burst)

        if drew_any:
            self.ax.relim()
            self.ax.autoscale()
        else:
            self.ax.text(0.5, 0.5, "No valid trace data", ha="center", va="center", color="black")

        self.canvas.draw()

    # -------------------------
    # Helpers
    # -------------------------
    def add_stats_summary(self, key, vectors):
        dp, dy, distances, bones = [], [], [], []
        for e in vectors:
            if not e:
                continue
            dp.append(e[0]); dy.append(e[1])
            if len(e) > 2: distances.append(e[2])
            if len(e) > 3: bones.append(e[3])

        avg_dx = sum(dp)/len(dp) if dp else 0
        avg_dy = sum(dy)/len(dy) if dy else 0
        bone_counts = {b: bones.count(b) for b in set(bones)} if bones else {}
        avg_dist = sum(distances)/len(distances) if distances else 0

        lbl = QLabel(
            f"Samples: {len(vectors)}\n"
            f"Avg ΔPitch={avg_dx:.2f}, Avg ΔYaw={avg_dy:.2f}\n"
            f"Avg Dist={avg_dist:.1f}\n"
            f"Bones: {bone_counts}"
        )
        lbl.setStyleSheet("""
            color: #000000;
            font-size: 8pt;
            border: 1px solid #000000;
            padding: 3px;
            margin: 3px 0;
            background: #FFFFFF;
        """)
        self.stats_layout.addWidget(lbl)

    def add_burst_summary(self, idx, burst):
        if not burst:
            return
        dxs, dys = zip(*[(b[0], b[1]) for b in burst])
        avg_dx, avg_dy = sum(dxs)/len(dxs), sum(dys)/len(dys)
        lbl = QLabel(f" Burst {idx}: {len(burst)} shots | Avg ΔPitch={avg_dx:.2f}, ΔYaw={avg_dy:.2f}")
        lbl.setStyleSheet("color: #000000; font-size: 8pt; margin-left: 8px;")
        self.stats_layout.addWidget(lbl)

    def split_bursts(self, vectors):
        bursts, current = [], []
        for dp, dy, *_ in vectors:
            if dp == 0 and dy == 0:
                if current:
                    bursts.append(current)
                    current = []
            else:
                current.append((dp, dy))
        if current:
            bursts.append(current)
        return bursts

import ctypes
import ctypes.wintypes
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTabWidget, QApplication,
    QCheckBox, QComboBox, QSlider, QGroupBox, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

# WinAPI constant for display affinity
user32 = ctypes.windll.user32
SetWindowDisplayAffinity = user32.SetWindowDisplayAffinity
SetWindowDisplayAffinity.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
SetWindowDisplayAffinity.restype = ctypes.wintypes.BOOL

WDA_NONE = 0x00
WDA_EXCLUDEFROMCAPTURE = 0x11

# =========================
#   Custom Controls (Helios/Win95 style)
# =========================

class CheatCheckBox(QCheckBox):
    def __init__(self, label="", parent=None):
        super().__init__(label, parent)
        self.setStyleSheet("""
        QCheckBox {
            color: #000000;
            font-family: "MS Sans Serif","Tahoma",sans-serif;
            font-size: 8pt;
            spacing: 2px;
        }
        QCheckBox::indicator {
            width: 11px; height: 11px;
            background: #C0C0C0;
            border: 1px solid #000000;
            /* raised bezel */
            border-top: 1px solid #FFFFFF;
            border-left: 1px solid #FFFFFF;
            border-right: 1px solid #808080;
            border-bottom: 1px solid #808080;
        }
        QCheckBox::indicator:checked {
            background: #000000;   /* solid black check box like screenshot */
        }
        """)


class CheatComboBox(QComboBox):
    def __init__(self, items=None, width=100, parent=None):
        super().__init__(parent)
        if items:
            self.addItems(items)
        self.setFixedWidth(width)
        self.setStyleSheet("""
        QComboBox {
            background: #FFFFFF;
            border: 1px solid #000000;
            padding: 1px 3px;
            font-family: "MS Sans Serif","Tahoma",sans-serif;
            font-size: 8pt;
            min-height: 16px;
        }
        QComboBox::drop-down {
            width: 14px;
            border-left: 1px solid #000000;
            background: #C0C0C0;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid #000000;
            border-top: 4px solid transparent;
            border-bottom: 4px solid transparent;
            margin-right: 2px;
        }
        """)


class NoScrollSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("""
        QSlider {
            background: transparent;
        }
        QSlider::groove:horizontal {
            height: 6px;
            background: #C0C0C0;
            border: 1px solid #000000;
        }
        QSlider::handle:horizontal {
            width: 10px; height: 14px;
            background: #E0E0E0;
            margin: -5px 0;
            /* sunken bevel */
            border-top: 1px solid #404040;
            border-left: 1px solid #404040;
            border-right: 1px solid #FFFFFF;
            border-bottom: 1px solid #FFFFFF;
        }
        """)
    def wheelEvent(self, event):
        pass  # disable scroll wheel

class ConsoleTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Output window
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("""
            background-color: white;
            color: black;
            font-family: Consolas, monospace;
            font-size: 9pt;
        """)
        layout.addWidget(self.output)

        # Input line
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Enter command (set/get/list/help)...")
        self.input_line.returnPressed.connect(self.handle_command)
        layout.addWidget(self.input_line)

    def log(self, text: str):
        self.output.append(text)

    def handle_command(self):
        text = self.input_line.text().strip()
        self.input_line.clear()
        if not text:
            return

        self.log(f"> {text}")
        parts = text.split()
        cmd = parts[0].lower()

        try:
            if cmd == "set" and len(parts) >= 3:
                key, val = parts[1], " ".join(parts[2:])
                # Try to cast to bool, int, float automatically
                if val.lower() in ["true", "false"]:
                    val_cast = val.lower() == "true"
                else:
                    try:
                        if "." in val:
                            val_cast = float(val)
                        else:
                            val_cast = int(val)
                    except ValueError:
                        val_cast = val
                setattr(Config, key, val_cast)
                self.log(f"[OK] {key} set to {val_cast}")

            elif cmd == "get" and len(parts) == 2:
                key = parts[1]
                val = getattr(Config, key, "<not found>")
                self.log(f"[VAL] {key} = {val}")

            elif cmd == "list":
                keys = sorted([k for k in dir(Config) if not k.startswith("__")])
                self.log("[Config Keys]")
                for k in keys:
                    self.log(f" - {k} = {getattr(Config, k)}")

            elif cmd == "help":
                self.log("Commands: set <key> <val>, get <key>, list, help")

            else:
                self.log(f"[ERR] Unknown or malformed command: {text}")

        except Exception as e:
            self.log(f"[ERR] {e}")

# =========================
#   Main Window
# =========================

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GFusion V1 - Artificial Aiming Style")
        self.setGeometry(100, 100, 950, 700)
        self.setMinimumSize(900, 650)

        # Frameless + topmost, but NOT translucent (prevents “clear” gaps)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # ---- Build UI -------------------------------------------------------
        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)     # outer black frame hugs edges
        root.setSpacing(0)

        # Outer panel with Win95 1px black border
        self.outer = QFrame()
        self.outer.setObjectName("outerPanel")
        outerL = QVBoxLayout(self.outer)
        outerL.setContentsMargins(2, 2, 2, 2)
        outerL.setSpacing(2)

        # Tabs (make instances attributes so refresh_all_tabs can see them)
        self.aimbot_tab     = AimbotTab()
        self.trigger_tab    = TriggerBotTab()
        self.esp_tab        = ESPTab()
        self.esp_tab.main_window = self   # give ESP tab a handle to apply OBS protection
        self.misc_tab       = MiscTab()
        self.config_tab     = ConfigTab()
        self.recoil_tab = RecoilViewer()
        self.console_tab    = ConsoleTab()
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self.aimbot_tab,  "Aimbot")
        self.tabs.addTab(self.trigger_tab, "Trigger")
        self.tabs.addTab(self.esp_tab,     "ESP")
        self.tabs.addTab(self.misc_tab,    "Misc")
        self.tabs.addTab(self.config_tab,  "Config")
        self.tabs.addTab(self.recoil_tab, "Recoil")
        self.tabs.addTab(self.console_tab, "Console")
        
        outerL.addWidget(self.tabs, 1)

        # Bottom row with a flat “Exit” like classic dialogs
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(4)
        bottom.addStretch(1)
        self.exit_btn = QPushButton("Exit")
        self.exit_btn.setFixedHeight(18)
        self.exit_btn.clicked.connect(self.exit_app)
        bottom.addWidget(self.exit_btn)
        outerL.addLayout(bottom)

        root.addWidget(self.outer)

        # ---- Apply Helios/Win95 QSS ----------------------------------------
        self.setStyleSheet(self._build_helios_qss())

        # OBS protection: keep behavior but delay until hwnd exists
        QTimer.singleShot(100, lambda: self.set_obs_protection(
            bool(getattr(Config, "obs_protection_enabled", False))
        ))

    # --------- Helios/Win95 stylesheet --------------------------------------
    def _build_helios_qss(self) -> str:
        # Palette
        bg  = "#C0C0C0"   # classic gray
        lt  = "#FFFFFF"   # light edge
        dk  = "#808080"   # dark edge
        dk2 = "#404040"   # darker edge
        blk = "#000000"   # black

        return f"""
        /* Global */
        QWidget {{
            background: {bg};
            color: {blk};
            font-family: "MS Sans Serif","Tahoma",sans-serif;
            font-size: 8pt;
        }}

        /* Outer 1px black frame */
        #outerPanel {{
            background: {bg};
            border: 1px solid {blk};
        }}

        /* ----- Tabs: raised (off), sunken (selected) --------------------- */
        QTabWidget::pane {{
            background: {bg};
            border: 1px solid {blk};
            top: -1px;   /* seam with tabs like the PNG */
        }}
        QTabBar::tab {{
            background: {bg};
            color: {blk};
            padding: 2px 10px;
            margin-right: -1px;
            min-height: 16px;
            border-top: 1px solid {lt};
            border-left: 1px solid {lt};
            border-right: 1px solid {dk2};
            border-bottom: 1px solid {dk2};
        }}
        QTabBar::tab:hover {{
            background: #D3D3D3;
        }}
        QTabBar::tab:selected {{
            /* sunken */
            background: #E0E0E0;
            border-top: 1px solid {dk2};
            border-left: 1px solid {dk2};
            border-right: 1px solid {lt};
            border-bottom: 1px solid {lt};
            margin-bottom: -1px;
        }}

        /* ----- GroupBoxes: flat title, 3D frame like screenshot ---------- */
        QGroupBox {{
            background: {bg};
            margin-top: 10px;
            padding: 4px;
            /* raised frame (top/left light, bottom/right dark) */
            border-top: 1px solid {lt};
            border-left: 1px solid {lt};
            border-right: 1px solid {dk2};
            border-bottom: 1px solid {dk2};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            color: {blk};
            background: {bg};
            font-weight: normal;
        }}

        /* ----- Buttons: raised, pressed -> sunken ------------------------ */
        QPushButton {{
            background: {bg};
            padding: 2px 8px;
            min-height: 16px;
            border-top: 1px solid {lt};
            border-left: 1px solid {lt};
            border-right: 1px solid {dk2};
            border-bottom: 1px solid {dk2};
        }}
        QPushButton:hover {{ background: #D3D3D3; }}
        QPushButton:pressed, QPushButton:checked {{
            /* sunken */
            border-top: 1px solid {dk2};
            border-left: 1px solid {dk2};
            border-right: 1px solid {lt};
            border-bottom: 1px solid {lt};
            background: #E0E0E0;
        }}

        /* ----- Edits ------------------------------------------------------ */
        QLineEdit, QComboBox, QTextEdit {{
            background: #FFFFFF;
            border: 1px solid {blk};
            padding: 1px 3px;
        }}
        QComboBox::drop-down {{ width: 14px; border-left: 1px solid {blk}; }}

        /* ----- Checkboxes / Radios: tiny, boxy --------------------------- */
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 11px; height: 11px;
            border: 1px solid {blk};
            background: {bg};
            /* raised bezel */
            border-top-color: {lt};
            border-left-color: {lt};
            border-right-color: {dk};
            border-bottom-color: {dk};
            margin-right: 4px;
        }}
        QCheckBox::indicator:checked {{
            background: #000000;   /* strong pixel check look */
        }}
        QRadioButton::indicator:checked {{
            background: #000000;
        }}

        /* ----- Sliders: flat groove w/ small sunken handle --------------- */
        QSlider::groove:horizontal {{
            height: 6px;
            background: {bg};
            border: 1px solid {blk};
        }}
        QSlider::handle:horizontal {{
            width: 10px; height: 14px;
            background: #E0E0E0;
            margin: -5px 0; /* taller handle like old UIs */
            border-top: 1px solid {dk2};
            border-left: 1px solid {dk2};
            border-right: 1px solid {lt};
            border-bottom: 1px solid {lt};
        }}

        /* ----- Scrollbars (simple boxy) ---------------------------------- */
        QScrollBar:vertical, QScrollBar:horizontal {{
            background: {bg};
            border: 1px solid {blk};
        }}
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
            background: #E0E0E0;
            border: 1px solid {blk};
        }}
        """

    # ----------------- OBS / capture protection -----------------------------
    def set_obs_protection(self, enabled: bool):
        hwnd = int(self.winId())  # get native HWND for this Qt window
        mode = WDA_EXCLUDEFROMCAPTURE if enabled else WDA_NONE
        success = SetWindowDisplayAffinity(hwnd, mode)
        if not success:
            print(f"[OBS Protection] Failed to apply mode={mode} to window")

    # ----------------- Drag the frameless window ----------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_active = True
            self._drag_start_pos = e.globalPos()

    def mouseMoveEvent(self, e):
        if getattr(self, "_drag_active", False):
            delta = e.globalPos() - self._drag_start_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._drag_start_pos = e.globalPos()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_active = False
            self._drag_start_pos = None

    def exit_app(self):
        stop_aimbot_thread()
        stop_bhop_thread()
        stop_glow_thread()
        stop_triggerbot_thread()
        QApplication.quit()

def _apply_global_qss(app):
    """Apply a single, lightweight global stylesheet to avoid repeated per-widget setStyleSheet() calls."""
    qss = """
    QWidget { font-size: 12px; }
    QPushButton { border-radius: 8px; padding: 6px 10px; }
    QCheckBox, QRadioButton { padding: 2px; }
    """
    app.setStyleSheet(qss)


def check_admin_privileges():
    """Check if running as administrator and request elevation if not"""
    import ctypes
    import sys
    import os
    
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False
    
    if not is_admin:
        # Request UAC elevation
        try:
            print("GFusion requires Administrator privileges for kernel mode support...")
            print("Requesting elevation...")
            
            # Re-run the script with elevated privileges
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                sys.executable, 
                f'"{os.path.abspath(__file__)}"',
                None, 
                1  # SW_SHOWNORMAL
            )
            sys.exit(0)  # Exit current instance
        except Exception as e:
            print(f"Failed to elevate privileges: {e}")
            print("Continuing without administrator rights (kernel mode unavailable)")
            return False
    
    print("[OK] Running with Administrator privileges - Kernel mode available")
    return True

def run():
    # Check and request admin privileges first
    is_admin = check_admin_privileges()
    
    print("Made by GitHub.com/Cr0mb/")
    if is_admin:
        print("[ADMIN] Administrator Mode - Full kernel access enabled")
    else:
        print("[WARNING] User Mode - Limited to usermode memory access")
    
    app = QApplication(sys.argv)

    # Apply global stylesheet
    _apply_global_qss(app)

    win = MainWindow()
    
    # Update window title to show admin status
    base_title = "GFusion V1 - Paint Edition"
    if is_admin:
        win.setWindowTitle(f"{base_title} - Administrator")
    else:
        win.setWindowTitle(f"{base_title} - User Mode")
    
    win.show()

    # Start features
    start_aimbot_thread()
    start_esp_thread()
    start_triggerbot_thread()
    start_auto_pistol_thread()

    # Start menu toggle listener
    start_toggle_listener(win)
    
    # Register shutdown handler to prevent daemon thread errors
    def cleanup_on_exit():
        """Suppress daemon thread output during shutdown"""
        try:
            # Redirect stdout/stderr to devnull during shutdown
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')
        except:
            pass
    
    atexit.register(cleanup_on_exit)

    app.exec_()  # <--- REQUIRED!


if __name__ == "__main__":
    wait_for_cs2()
    run()



def handle_console_command(cmd_line: str):
    """Parse and execute console commands"""
    try:
        parts = cmd_line.strip().split()
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]

        # ---- TOGGLE FEATURES ----
        if cmd == "toggle" and len(args) >= 2:
            feature, state_str = args[0].lower(), args[1].lower()
            state = state_str in ("1", "true", "on", "enable")

            def update_feature_state():
                if feature == "aimbot":
                    cfg.enabled = state
                    if state: start_aimbot_thread()
                    else: stop_aimbot_thread()

                elif feature == "glow":
                    cfg.glow = state
                    if state: start_glow_thread()
                    else: stop_glow_thread()

                elif feature == "bhop":
                    cfg.bhop_enabled = state
                    if state: start_bhop_thread()
                    else: stop_bhop_thread()

                elif feature == "triggerbot":
                    cfg.triggerbot_enabled = state
                    if state: start_triggerbot_thread()
                    else: stop_triggerbot_thread()

                elif feature == "walkbot":
                    cfg.walkbot_enabled = state
                    if state: start_walkbot_thread()
                    else: stop_walkbot_thread()

                print(f"[Console] {feature} set to {state}")

            # Schedule this on the GUI thread
            QTimer.singleShot(0, update_feature_state)

        # ---- SET CONFIG VALUES ----
        elif cmd == "set" and len(args) >= 2:
            key, value = args[0], " ".join(args[1:])
            if hasattr(cfg, key):
                old_val = getattr(cfg, key)
                try:
                    # Try type match with old value
                    if isinstance(old_val, bool):
                        new_val = value.lower() in ("1", "true", "on", "enable")
                    elif isinstance(old_val, int):
                        new_val = int(value)
                    elif isinstance(old_val, float):
                        new_val = float(value)
                    else:
                        new_val = value

                    # Schedule config update on GUI thread
                    QTimer.singleShot(0, lambda k=key, v=new_val: setattr(cfg, k, v))
                    print(f"[Console] {key} scheduled update to {new_val}")
                except Exception as e:
                    print(f"[Console] Failed to set {key}: {e}")
            else:
                print(f"[Console] Unknown config key: {key}")

        else:
            print(f"[Console] Unknown command: {cmd}")

    finally:
        # Always refresh UI after any command (safely)
        ui_refresher.trigger_refresh.emit()
