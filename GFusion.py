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

import hashlib

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from Process.config import Config
import win32ui  
import Features.esp
from Features.aimbot import start_aim_rcs
from Features.bhop import BHopProcess
from Features.glow import CS2GlowManager
from Features.triggerbot import TriggerBot
from Features.fov import FOVChanger
from Features.auto_pistol import run_auto_pistol

cfg = Config()

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
        self.ui_elements = {}
        self.init_ui()

    def init_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # --- FOV Changer Section ---
        fov_section = QVBoxLayout()
        fov_section.setSpacing(8)

        fov_title = QLabel("FOV Changer:")
        fov_title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        fov_section.addWidget(fov_title)

        self.fov_checkbox = CheatCheckBox("Enable FOV Changer")
        self.fov_checkbox.setChecked(getattr(cfg, "fov_changer_enabled", True))
        self.fov_checkbox.stateChanged.connect(
            lambda state: start_fov_thread() if state == Qt.Checked else stop_fov_thread()
        )
        fov_section.addWidget(self.fov_checkbox)

        self.fov_label = QLabel(f"Game FOV: {cfg.game_fov}")
        self.fov_slider = NoScrollSlider(Qt.Horizontal)
        self.fov_slider.setMinimum(60)
        self.fov_slider.setMaximum(150)
        self.fov_slider.setValue(cfg.game_fov)
        self.fov_slider.valueChanged.connect(
            lambda value: (
                setattr(cfg, "game_fov", value),
                self.fov_label.setText(f"Game FOV: {value}"),
            )
        )
        fov_section.addWidget(self.fov_label)
        fov_section.addWidget(self.fov_slider)

        layout.addLayout(fov_section)
        layout.addWidget(create_section_separator())

        # --- Glow Section ---
        glow_section = QVBoxLayout()
        glow_section.setSpacing(8)

        glow_title = QLabel("Glow Effects:")
        glow_title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        glow_section.addWidget(glow_title)

        self.glow_checkbox = CheatCheckBox("Enable Glow")
        self.glow_checkbox.setChecked(getattr(Config, "glow", False))
        self.glow_checkbox.stateChanged.connect(
            lambda state: (
                setattr(Config, "glow", state == Qt.Checked),
                start_glow_thread() if state == Qt.Checked else stop_glow_thread()
            )
        )
        glow_section.addWidget(self.glow_checkbox)

        # Glow enemies checkbox
        self.glow_show_enemies_cb = CheatCheckBox("Glow Enemies")
        self.glow_show_enemies_cb.setChecked(getattr(Config, "glow_show_enemies", True))
        self.glow_show_enemies_cb.stateChanged.connect(
            lambda state: setattr(Config, "glow_show_enemies", state == Qt.Checked)
        )
        glow_section.addWidget(self.glow_show_enemies_cb)

        # Glow team checkbox
        self.glow_show_team_cb = CheatCheckBox("Glow Team")
        self.glow_show_team_cb.setChecked(getattr(Config, "glow_show_team", True))
        self.glow_show_team_cb.stateChanged.connect(
            lambda state: setattr(Config, "glow_show_team", state == Qt.Checked)
        )
        glow_section.addWidget(self.glow_show_team_cb)

        # Enemy color picker row
        enemy_color_row = QHBoxLayout()
        enemy_color_label = QLabel("Enemy Glow Color:")
        enemy_color_label.setStyleSheet("color: #c5c8c6; font-weight: 600; font-size: 10pt;")
        enemy_color_row.addWidget(enemy_color_label)

        enemy_current_color = getattr(Config, "glow_color_enemy", (1, 0, 0, 1))
        enemy_rgb = tuple(int(c * 255) for c in enemy_current_color[:3])
        enemy_color_btn = QPushButton()
        enemy_color_btn.setFixedSize(40, 20)
        enemy_color_btn.setStyleSheet(f"background-color: rgb{enemy_rgb}; border: 1px solid black;")
        enemy_color_row.addWidget(enemy_color_btn)

        def choose_enemy_color():
            nonlocal enemy_rgb
            initial_color = QColor(*enemy_rgb)
            new_color = QColorDialog.getColor(initial_color, self, "Select Enemy Glow Color")
            if new_color.isValid():
                rgb = (new_color.red(), new_color.green(), new_color.blue())
                setattr(Config, "glow_color_enemy", (rgb[0]/255, rgb[1]/255, rgb[2]/255, 1))
                enemy_rgb = rgb
                enemy_color_btn.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")

        enemy_color_btn.clicked.connect(choose_enemy_color)
        glow_section.addLayout(enemy_color_row)

        # Team color picker row
        team_color_row = QHBoxLayout()
        team_color_label = QLabel("Team Glow Color:")
        team_color_label.setStyleSheet("color: #c5c8c6; font-weight: 600; font-size: 10pt;")
        team_color_row.addWidget(team_color_label)

        team_current_color = getattr(Config, "glow_color_team", (0, 1, 0, 1))
        team_rgb = tuple(int(c * 255) for c in team_current_color[:3])
        team_color_btn = QPushButton()
        team_color_btn.setFixedSize(40, 20)
        team_color_btn.setStyleSheet(f"background-color: rgb({team_rgb[0]}, {team_rgb[1]}, {team_rgb[2]}); border: 1px solid black;")
        team_color_row.addWidget(team_color_btn)

        def choose_team_color():
            nonlocal team_rgb
            initial_color = QColor(*team_rgb)
            new_color = QColorDialog.getColor(initial_color, self, "Select Team Glow Color")
            if new_color.isValid():
                rgb = (new_color.red(), new_color.green(), new_color.blue())
                setattr(Config, "glow_color_team", (rgb[0]/255, rgb[1]/255, rgb[2]/255, 1))
                team_rgb = rgb
                team_color_btn.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")

        team_color_btn.clicked.connect(choose_team_color)
        glow_section.addLayout(team_color_row)

        # Store references for refresh
        if 'color_buttons' not in self.ui_elements:
            self.ui_elements['color_buttons'] = {}
        self.ui_elements['color_buttons']["glow_color_enemy"] = enemy_color_btn
        self.ui_elements['color_buttons']["glow_color_team"] = team_color_btn

        layout.addLayout(glow_section)
        layout.addWidget(create_section_separator())

        # --- BHop Section ---
        bhop_section = QVBoxLayout()
        bhop_section.setSpacing(8)

        bhop_title = QLabel("Bunny Hop:")
        bhop_title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        bhop_section.addWidget(bhop_title)

        self.bhop_checkbox = CheatCheckBox("Enable Bunny Hop")
        self.bhop_checkbox.setChecked(getattr(Config, "bhop_enabled", False))
        self.bhop_checkbox.stateChanged.connect(
            lambda state: start_bhop_thread() if state == Qt.Checked else stop_bhop_thread()
        )
        bhop_section.addWidget(self.bhop_checkbox)

        # --- Local Info Box Subsection ---
        self.local_info_box_cb = CheatCheckBox("BHop Information Box")
        self.local_info_box_cb.setChecked(getattr(Config, "show_local_info_box", True))
        self.local_info_box_cb.stateChanged.connect(
            lambda state: setattr(Config, "show_local_info_box", state == Qt.Checked)
        )
        bhop_section.addWidget(self.local_info_box_cb)

        # Color pickers layout
        local_color_labels = [
            ("Coords Text", "color_local_coords_text", (200, 200, 255)),
            ("Velocity Text", "color_local_velocity_text", (255, 255, 255)),
            ("Speed Text", "color_local_speed_text", (180, 255, 180)),
            ("Box Background", "color_local_box_background", (30, 30, 30)),
            ("Box Border", "color_local_box_border", (100, 100, 100))
        ]

        for label, cfg_key, default in local_color_labels:
            row = QHBoxLayout()
            text = QLabel(f"{label}:")
            text.setStyleSheet("color: #c5c8c6; font-weight: 600; font-size: 10pt;")
            row.addWidget(text)

            current_rgb = getattr(Config, cfg_key, default)
            btn = QPushButton()
            btn.setFixedSize(40, 20)
            btn.setStyleSheet(f"background-color: rgb{current_rgb}; border: 1px solid black;")

            def make_color_callback(key, button):
                def choose_color():
                    current = getattr(Config, key, (255, 255, 255))
                    initial = QColor(*current)
                    color = QColorDialog.getColor(initial, self, f"Select {label}")
                    if color.isValid():
                        rgb = (color.red(), color.green(), color.blue())
                        setattr(Config, key, rgb)
                        button.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")
                return choose_color

            btn.clicked.connect(make_color_callback(cfg_key, btn))
            row.addWidget(btn)
            bhop_section.addLayout(row)

            # Store for refresh
            if "color_buttons" not in self.ui_elements:
                self.ui_elements["color_buttons"] = {}
            self.ui_elements["color_buttons"][cfg_key] = btn


        layout.addLayout(bhop_section)
        layout.addWidget(create_section_separator())

        # --- Miscellaneous Features Section ---
        misc_section = QVBoxLayout()
        misc_section.setSpacing(8)

        misc_title = QLabel("Miscellaneous Features:")
        misc_title.setStyleSheet("font-weight: bold; font-size: 12pt;")
        misc_section.addWidget(misc_title)

        self.walkbot_cb = CheatCheckBox("Enable WalkBot")
        self.walkbot_cb.setChecked(getattr(Config, "walkbot_enabled", False))
        self.walkbot_cb.stateChanged.connect(
            lambda state: start_walkbot_thread() if state == Qt.Checked else stop_walkbot_thread()
        )
        misc_section.addWidget(self.walkbot_cb)


        self.grenade_pred_cb = CheatCheckBox("Grenade Prediction (simple)")
        self.grenade_pred_cb.setChecked(getattr(Config, "grenade_prediction_enabled", False))
        self.grenade_pred_cb.stateChanged.connect(
            lambda state: setattr(Config, "grenade_prediction_enabled", state == Qt.Checked)
        )
        misc_section.addWidget(self.grenade_pred_cb)

        self.noflash_cb = CheatCheckBox("Enable No Flash")
        self.noflash_cb.setChecked(getattr(Config, "noflash_enabled", False))
        self.noflash_cb.stateChanged.connect(
            lambda state: setattr(Config, "noflash_enabled", state == Qt.Checked)
        )
        misc_section.addWidget(self.noflash_cb)

        self.spectator_list_cb = CheatCheckBox("Spectator List")
        self.spectator_list_cb.setChecked(getattr(Config, "spectator_list_enabled", False))
        self.spectator_list_cb.stateChanged.connect(
            lambda state: setattr(Config, "spectator_list_enabled", state == Qt.Checked)
        )
        misc_section.addWidget(self.spectator_list_cb)

        self.watermark_cb = CheatCheckBox("Enable Watermark")
        self.watermark_cb.setChecked(getattr(Config, "watermark_enabled", True))
        self.watermark_cb.stateChanged.connect(
            lambda state: setattr(Config, "watermark_enabled", state == Qt.Checked)
        )
        misc_section.addWidget(self.watermark_cb)

        layout.addLayout(misc_section)
        layout.addWidget(create_section_separator())

        layout.addStretch()

        # --- Toggle Menu Key Section ---
        toggle_section = QVBoxLayout()
        toggle_section.setSpacing(8)

        toggle_label = QLabel(f"Toggle Menu Key: {cfg.toggle_menu_key}")
        self.toggle_key_label = toggle_label

        set_toggle_key_btn = QPushButton("Set Toggle Key")
        set_toggle_key_btn.clicked.connect(self.set_toggle_key)

        toggle_section.addWidget(QLabel("Menu Toggle Hotkey:"))
        toggle_section.addWidget(toggle_label)
        toggle_section.addWidget(set_toggle_key_btn)

        layout.addLayout(toggle_section)

        content_widget.setLayout(layout)
        scroll.setWidget(content_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def pick_enemy_color(self):
        current = getattr(Config, "glow_color_enemy", (1, 0, 0, 1))
        initial = self.rgba_to_qcolor(current)
        color = QColorDialog.getColor(initial, self, "Select Enemy Glow Color")
        if color.isValid():
            rgba = self.qcolor_to_rgba(color)
            setattr(Config, "glow_color_enemy", rgba)

    def pick_team_color(self):
        current = getattr(Config, "glow_color_team", (0, 1, 0, 1))
        initial = self.rgba_to_qcolor(current)
        color = QColorDialog.getColor(initial, self, "Select Team Glow Color")
        if color.isValid():
            rgba = self.qcolor_to_rgba(color)
            setattr(Config, "glow_color_team", rgba)

    def rgba_to_qcolor(self, rgba):
        r, g, b, a = [int(c * 255) for c in rgba]
        return QColor(r, g, b, a)

    def qcolor_to_rgba(self, qcolor):
        return (qcolor.red() / 255, qcolor.green() / 255, qcolor.blue() / 255, qcolor.alpha() / 255)


    def set_toggle_key(self):
        self.toggle_key_label.setText("Press a key...")
        self.listener_thread = KeyListenerThread()
        self.listener_thread.key_pressed.connect(self.update_toggle_key)
        self.listener_thread.start()

    def update_toggle_key(self, key):
        cfg.toggle_menu_key = key
        self.toggle_key_label.setText(f"Toggle Menu Key: {key}")

    def refresh_ui(self):
        """Refresh all UI elements with current config values"""
        self.fov_checkbox.setChecked(getattr(cfg, "fov_changer_enabled", True))
        self.fov_slider.setValue(cfg.game_fov)
        self.fov_label.setText(f"Game FOV: {cfg.game_fov}")

        self.glow_checkbox.setChecked(getattr(Config, "glow", False))
        self.glow_show_enemies_cb.setChecked(getattr(Config, "glow_show_enemies", True))
        self.glow_show_team_cb.setChecked(getattr(Config, "glow_show_team", True))

        self.bhop_checkbox.setChecked(getattr(Config, "bhop_enabled", False))
        self.local_info_box_cb.setChecked(getattr(Config, "show_local_info_box", True))

        self.walkbot_cb.setChecked(getattr(Config, "walkbot_enabled", False))

        self.grenade_pred_cb.setChecked(getattr(Config, "grenade_prediction_enabled", False))
        self.noflash_cb.setChecked(getattr(Config, "noflash_enabled", False))
        self.spectator_list_cb.setChecked(getattr(Config, "spectator_list_enabled", False))
        self.watermark_cb.setChecked(getattr(Config, "watermark_enabled", True))

        self.toggle_key_label.setText(f"Toggle Menu Key: {cfg.toggle_menu_key}")

        # Update button colors
        for key, btn in self.ui_elements.get("color_buttons", {}).items():
            rgb = getattr(Config, key, (255, 255, 255))
            # rgb might be either tuple of 3 ints or 4 floats in 0-1 range, normalize accordingly:
            if len(rgb) == 4:  # assume float rgba (0-1)
                r, g, b, a = rgb
                r = int(r * 255)
                g = int(g * 255)
                b = int(b * 255)
            else:  # assume integer rgb
                r, g, b = rgb[:3]
            btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;")


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

        self.ui_elements = {}  # store references for refresh

        # --- Main Aimbot Controls ---
        main_group = QVBoxLayout()
        main_group.addWidget(self.section_title("Main Controls"))

        row = QHBoxLayout()
        self.add_checkbox(row, "Enable Aimbot", "enabled")
        self.add_checkbox(row, "Visibility Check", "visibility_aim_enabled")
        self.add_checkbox(row, "DeathMatch Mode", "DeathMatch")
        main_group.addLayout(row)

        self.auto_pistol_cb = CheatCheckBox("Enable Auto Pistol")
        self.auto_pistol_cb.setChecked(Config.auto_pistol_enabled)
        self.auto_pistol_cb.stateChanged.connect(lambda state: self.toggle_auto_pistol(state))
        main_group.addWidget(self.auto_pistol_cb)

        # Auto Pistol Key
        key_layout = QHBoxLayout()
        key_label = QLabel("Auto Pistol Key:")
        key_label.setStyleSheet("color: #c5c8c6; font-weight: 600; font-size: 10pt;")
        key_combo = CheatComboBox(
            items=["mouse2","mouse3","mouse4","mouse5","alt","ctrl","shift","space"], width=70
        )
        key_combo.setCurrentText(Config.activation_key.lower())
        key_combo.currentTextChanged.connect(lambda val: setattr(Config, "activation_key", val))
        key_layout.addWidget(key_label)
        key_layout.addWidget(key_combo)
        main_group.addLayout(key_layout)

        layout.addLayout(main_group)
        layout.addWidget(create_section_separator())

        # --- Auto Pistol Fire Rate Slider ---
        fire_rate_layout = QVBoxLayout()
        self.fire_rate_label = QLabel(f"Fire Rate: {Config.fire_rate:.2f}s")
        self.fire_rate_slider = NoScrollSlider(Qt.Horizontal)
        self.fire_rate_slider.setMinimum(1)        # 0.01s min
        self.fire_rate_slider.setMaximum(100)      # 1.0s max
        self.fire_rate_slider.setValue(int(Config.fire_rate * 100))

        def update_fire_rate(val):
            Config.fire_rate = val / 100.0
            self.fire_rate_label.setText(f"Fire Rate: {Config.fire_rate:.2f}s")

        self.fire_rate_slider.valueChanged.connect(update_fire_rate)

        fire_rate_layout.addWidget(self.fire_rate_label)
        fire_rate_layout.addWidget(self.fire_rate_slider)
        layout.addLayout(fire_rate_layout)
        layout.addWidget(create_section_separator())

        # --- Advanced Features ---
        adv_group = QVBoxLayout()
        adv_group.addWidget(self.section_title("Advanced Features"))

        row1 = QHBoxLayout()
        self.add_checkbox(row1, "Enable Learning", "enable_learning")
        self.add_checkbox(row1, "Velocity Prediction", "enable_velocity_prediction")
        adv_group.addLayout(row1)

        row2 = QHBoxLayout()
        self.add_checkbox(row2, "Closest to Crosshair", "closest_to_crosshair")
        self.add_checkbox(row2, "Enable RCS", "rcs_enabled")
        adv_group.addLayout(row2)

        layout.addLayout(adv_group)
        layout.addWidget(create_section_separator())

        # --- Aimbot FOV Overlay ---
        fov_group = QVBoxLayout()
        fov_group.addWidget(self.section_title("FOV Overlay Settings"))

        row = QHBoxLayout()
        self.add_checkbox(row, "Show FOV Circle", "fov_circle_enabled")
        fov_group.addLayout(row)

        color_row = QHBoxLayout()
        color_label = QLabel("FOV Circle Color:")
        color_label.setStyleSheet("color: #c5c8c6; font-weight: 600; font-size: 10pt;")
        color_picker = QPushButton()
        color_picker.setFixedSize(40, 20)
        color_picker.setStyleSheet(f"background-color: rgb{getattr(Config,'fov_overlay_color',(255,255,255))}; border: 1px solid black;")
        
        def choose_color():
            new_color = QColorDialog.getColor(QColor(*getattr(Config,'fov_overlay_color',(255,255,255))))
            if new_color.isValid():
                rgb = (new_color.red(), new_color.green(), new_color.blue())
                setattr(Config, "fov_overlay_color", rgb)
                color_picker.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")
        color_picker.clicked.connect(choose_color)

        color_row.addWidget(color_label)
        color_row.addWidget(color_picker)
        fov_group.addLayout(color_row)

        layout.addLayout(fov_group)
        layout.addWidget(create_section_separator())

        # --- Precision Settings (Float Sliders, 3 columns) ---
        float_grid = QGridLayout()
        float_grid.setHorizontalSpacing(20)
        float_grid.setVerticalSpacing(15)
        layout.addWidget(self.section_title("Precision Settings"))

        self.add_float_slider_to_grid(float_grid, 0, 0, "FOV", "FOV", 0.1, 30.0, 0.1, 10)
        self.add_float_slider_to_grid(float_grid, 0, 1, "Aim Start Delay", "aim_start_delay", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 0, 2, "RCS Scale", "rcs_scale", 0.0, 5.0, 0.1, 10)
        self.add_float_slider_to_grid(float_grid, 1, 0, "Smoothing Base", "smooth_base", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 1, 1, "Smoothing Variance", "smooth_var", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 1, 2, "Velocity Prediction Factor", "velocity_prediction_factor", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 2, 0, "Target Switch Delay", "target_switch_delay", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 2, 1, "RCS Smooth Base", "rcs_smooth_base", 0.0, 1.0, 0.01, 100)
        self.add_float_slider_to_grid(float_grid, 2, 2, "RCS Smooth Variance", "rcs_smooth_var", 0.0, 1.0, 0.01, 100)

        layout.addLayout(float_grid)
        layout.addWidget(create_section_separator())

        # --- Numeric Settings (Int Sliders, 3 columns) ---
        int_grid = QGridLayout()
        int_grid.setHorizontalSpacing(20)
        int_grid.setVerticalSpacing(15)
        layout.addWidget(self.section_title("Numeric Settings"))

        self.add_int_slider_to_grid(int_grid, 0, 0, "Downward Offset", "downward_offset", 0, 100)
        self.add_int_slider_to_grid(int_grid, 0, 1, "Max Entities", "max_entities", 1, 128)
        self.add_int_slider_to_grid(int_grid, 0, 2, "Max Mouse Move", "max_mouse_move", 1, 50)
        self.add_int_slider_to_grid(int_grid, 1, 0, "Max Delta Angle", "max_delta_angle", 1, 180)

        layout.addLayout(int_grid)
        layout.addWidget(create_section_separator())

        # --- Input Settings ---
        input_group = QVBoxLayout()
        input_group.addWidget(self.section_title("Input Settings"))

        # Aim Key
        key_vbox = QVBoxLayout()
        aim_label = QLabel("Aim Activation Key:")
        aim_label.setStyleSheet("color: #c5c8c6; font-weight: 600; font-size: 10pt;")
        key_vbox.addWidget(aim_label)
        self.aim_key_combo = CheatComboBox(items=["mouse1","mouse2","mouse3","mouse4","mouse5","left_shift","right_shift","left_ctrl","right_ctrl","left_alt","right_alt","space"], width=90)
        self.aim_key_combo.setCurrentText(Config.aim_key)
        self.aim_key_combo.currentTextChanged.connect(lambda val: setattr(Config,"aim_key",val))
        key_vbox.addWidget(self.aim_key_combo)
        input_group.addLayout(key_vbox)

        # Sensitivity & Invert Y
        sens_layout = QHBoxLayout()
        self.sens_label = QLabel(f"Sensitivity: {Config.sensitivity:.3f}")
        self.sens_slider = NoScrollSlider(Qt.Horizontal)
        self.sens_slider.setMinimum(8)       # matches your refresh_ui scaling
        self.sens_slider.setMaximum(1000)

        # Set initial value from Config
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
        self.invert_y_cb.stateChanged.connect(lambda state: setattr(Config,"invert_y",-1 if state==Qt.Checked else 1))
        sens_layout.addWidget(self.invert_y_cb)

        input_group.addLayout(sens_layout)
        layout.addLayout(input_group)
        layout.addWidget(create_section_separator())

        # --- Target Settings ---
        target_group = QVBoxLayout()
        target_group.addWidget(self.section_title("Target Settings"))

        self.bone_select = CheatComboBox(items=["head","chest"], width=80)
        self.bone_select.setCurrentText(Config.target_bone_name)
        self.bone_select.currentTextChanged.connect(lambda val: setattr(Config,"target_bone_name",val))
        target_group.addWidget(self.bone_select)

        self.learn_dir_label = QLabel(f"Learning Dir: {Config.learn_dir}")
        target_group.addWidget(self.learn_dir_label)

        layout.addLayout(target_group)

        # Final setup
        scroll.setWidget(content_widget)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def toggle_auto_pistol(self, state):
        Config.auto_pistol_enabled = (state == Qt.Checked)
        if Config.auto_pistol_enabled:
            start_auto_pistol_thread()
        else:
            stop_auto_pistol_thread()

    def refresh_ui(self):
        """Refresh all UI elements with current config values"""

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
        self.ui_elements = {}
        self.init_ui()

    def init_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # --- Team Filtering Options ---
        layout.addWidget(self.section_title("Team Filter:"))
        filter_grid = QGridLayout()
        filter_grid.setHorizontalSpacing(15)
        filter_grid.setVerticalSpacing(8)

        self.add_checkbox_to_grid(filter_grid, 0, 0, "Enemy Only", "esp_show_enemies_only")
        self.add_checkbox_to_grid(filter_grid, 0, 1, "Team Only", "esp_show_team_only")

        layout.addLayout(filter_grid)
        layout.addWidget(create_section_separator())

        layout.addWidget(self.section_title("Panic Settings:"))
        panic_row = QHBoxLayout()

        # Panic Key selector
        panic_key_label = QLabel(f"Panic Key: {getattr(Config, 'panic_key', 'F12')}")
        set_panic_key_btn = QPushButton("Set Panic Key")

        def set_panic_key():
            set_panic_key_btn.setText("Press any key...")
            self.listener_thread = KeyListenerThread()
            self.listener_thread.key_pressed.connect(lambda key: self.update_panic_key(key, panic_key_label, set_panic_key_btn))
            self.listener_thread.start()

        set_panic_key_btn.clicked.connect(set_panic_key)

        panic_row.addWidget(panic_key_label)
        panic_row.addWidget(set_panic_key_btn)
        layout.addLayout(panic_row)

        # Store reference for refresh
        if 'labels' not in self.ui_elements:
            self.ui_elements['labels'] = {}
        self.ui_elements['labels']['panic_key'] = panic_key_label

        # --- Basic ESP Features ---
        layout.addWidget(self.section_title("Basic ESP Features:"))
        basic_grid = QGridLayout()
        basic_grid.setHorizontalSpacing(15)
        basic_grid.setVerticalSpacing(8)

        # Add checkboxes first
        basic_features = [
            ("Hide from Screen Capture", "obs_protection_enabled"),
            ("Show Box ESP", "show_box_esp"),
            ("Health Bar", "healthbar_enabled"),
            ("Armor Bar", "armorbar_enabled"),
            ("Health Text", "health_esp_enabled"),
            ("Armor Text", "armor_esp_enabled"),
            ("Distance ESP", "distance_esp_enabled"),
            ("Name ESP", "name_esp_enabled"),
            ("Weapon ESP", "weapon_esp_enabled"),
            ("Debug Maps", "debug_mode"),
        ]

        for i, (label, attr) in enumerate(basic_features):
            self.add_checkbox_to_grid(basic_grid, i // 3, i % 3, label, attr)

        # --- Instead of adding the dropdown to the grid, nest it next to Show Box ESP ---
        show_box_esp_cb = self.ui_elements['checkboxes'].get("show_box_esp")
        if show_box_esp_cb:
            dropdown_layout = QHBoxLayout()
            dropdown_layout.setSpacing(5)
            dropdown_layout.addWidget(QLabel("Box ESP Style:"))

            combo = QComboBox()
            combo.addItems(["normal", "rounded", "corner"])
            current_value = getattr(Config, "box_esp_style", "normal").lower()
            index = combo.findText(current_value)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.currentTextChanged.connect(lambda val: setattr(Config, "box_esp_style", val.lower()))
            dropdown_layout.addWidget(combo)

            # store reference for refresh
            if 'comboboxes' not in self.ui_elements:
                self.ui_elements['comboboxes'] = {}
            self.ui_elements['comboboxes']['box_esp_style'] = combo

            # Put the dropdown below the Show Box ESP checkbox
            container = QWidget()
            container.setLayout(dropdown_layout)
            basic_grid.addWidget(container, 1, 1)  # adjust row/col as needed

            
        layout.addLayout(basic_grid)
        layout.addWidget(create_section_separator())

        # --- Visibility ESP Settings ---
        layout.addWidget(self.section_title("Visibility ESP Settings:"))
        visibility_layout = QHBoxLayout()
        self.add_checkbox(visibility_layout, "Enable Visibility ESP", "visibility_esp_enabled")
        # Show Visibility Text checkbox with proper default
        visibility_text_cb = CheatCheckBox("Show Visibility Text")
        visibility_text_cb.setChecked(getattr(Config, "visibility_text_enabled", True))  # Default to True
        visibility_text_cb.stateChanged.connect(
            lambda state: setattr(Config, "visibility_text_enabled", state == Qt.Checked)
        )
        visibility_layout.addWidget(visibility_text_cb)
        
        # Map file selection
        map_layout = QHBoxLayout()
        map_layout.addWidget(QLabel("Map File:"))
        
        # Create dropdown for map selection from maps folder
        self.map_combo = QComboBox()
        self.refresh_map_list()
        
        # Connect to update config and load map when selection changes
        self.map_combo.currentTextChanged.connect(self.on_map_selection_changed)
        
        # Add refresh button for maps
        refresh_maps_btn = QPushButton("↻")
        refresh_maps_btn.setFixedWidth(28)
        refresh_maps_btn.clicked.connect(self.refresh_map_list)
        
        if 'comboboxes' not in self.ui_elements:
            self.ui_elements['comboboxes'] = {}
        self.ui_elements['comboboxes']['visibility_map_file'] = self.map_combo
        
        map_layout.addWidget(self.map_combo)
        map_layout.addWidget(refresh_maps_btn)
        
        visibility_container = QWidget()
        visibility_container.setLayout(visibility_layout)
        layout.addWidget(visibility_container)
        
        map_container = QWidget()
        map_container.setLayout(map_layout)
        layout.addWidget(map_container)
        layout.addWidget(create_section_separator())

        # --- Advanced ESP Features ---
        layout.addWidget(self.section_title("Advanced ESP Features:"))
        advanced_grid = QGridLayout()
        advanced_grid.setHorizontalSpacing(15)
        advanced_grid.setVerticalSpacing(8)
        advanced_features = [
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
        ]
        self.add_slider(layout, "Max Trace Points", "trace_esp_max_points", 10, 500)
        for i, (label, attr) in enumerate(advanced_features):
            self.add_checkbox_to_grid(advanced_grid, i // 3, i % 3, label, attr)
        layout.addLayout(advanced_grid)
        layout.addWidget(create_section_separator())

        # --- Crosshair Settings ---
        layout.addWidget(self.section_title("Crosshair Settings:"))
        self.add_checkbox(layout, "Enable External Crosshair", "draw_crosshair_enabled")
        self.add_slider(layout, "Crosshair Size", "crosshair_size", 1, 20)

        # --- Line ESP ---
        layout.addWidget(self.section_title("Line ESP Settings:"))
        line_row = QHBoxLayout()
        self.add_checkbox(line_row, "Enable Line ESP", "line_esp_enabled")
        self.add_combobox(line_row, "Line ESP Position:", ["top", "bottom"], "line_esp_position")
        container = QWidget()
        container.setLayout(line_row)
        layout.addWidget(container)
        layout.addWidget(create_section_separator())

        # --- Bone Dot ESP ---
        layout.addWidget(self.section_title("Bone Dot ESP Settings:"))
        bone_row = QHBoxLayout()
        self.add_checkbox(bone_row, "Enable Bone Dot ESP", "bone_dot_esp_enabled")
        bone_container = QWidget()
        bone_container.setLayout(bone_row)
        layout.addWidget(bone_container)
        self.add_slider(layout, "Bone Dot Size", "bone_dot_size", 1, 20)
        layout.addWidget(create_section_separator())

        # --- Size Settings ---
        layout.addWidget(self.section_title("Size Settings:"))
        self.add_slider(layout, "Head ESP Size", "head_esp_size", 1, 50)
        layout.addWidget(create_section_separator())

        # --- Shape Settings ---
        layout.addWidget(self.section_title("Shape Settings:"))
        shape_grid = QGridLayout()
        self.add_combobox(shape_grid, "Head ESP Shape:", ["circle", "square"], "head_esp_shape", row=0, col=0)
        self.add_combobox(shape_grid, "Bone Dot Shape:", ["circle", "square"], "bone_dot_shape", row=0, col=1)
        layout.addLayout(shape_grid)
        layout.addWidget(create_section_separator())

        # --- Color Settings - Use 3 columns for better spacing ---
        layout.addWidget(self.section_title("ESP Colors:"))
        color_grid = QGridLayout()
        color_grid.setHorizontalSpacing(20)
        color_grid.setVerticalSpacing(15)
        color_settings = [
            ("Box (T)", "color_box_t"),
            ("Box (CT)", "color_box_ct"),
            ("Bone", "color_bone"),
            ("Head", "color_head"),
            ("Health Bar", "color_healthbar"),
            ("Armor Bar", "color_armorbar"),
            ("Name", "color_name"),
            ("Name Effects", "color_name_effects"),
            ("HP Text", "color_hp_text"),
            ("Armor Text", "color_armor_text"),
            ("Distance", "color_distance"),
            ("Flash/Scope", "color_flash_scope"),
            ("Spectators", "color_spectators"),
            ("Skeleton Color", "color_bone"),
            ("Bone Dot Color", "bone_dot_color"),
            ("Weapon Text", "color_weapon_text"),
            ("Crosshair Color", "crosshair_color"),
            ("Velocity Text Color", "velocity_text_color"),
            ("Velocity ESP Color", "velocity_esp_color"),
            ("Speed ESP Color", "speed_esp_color"),
            ("Coordinate ESP Color", "coordinates_esp_color"),
            ("Trace ESP Color", "trace_esp_color"),
            ("Money ESP Color", "color_money_text"),
            ("Visible Text Color", "color_visible_text"),
            ("Not Visible Text Color", "color_not_visible_text"),
        ]
        for i, (label, attr) in enumerate(color_settings):
            self.add_color_picker_to_grid(color_grid, i // 3, i % 3, label, attr)

        layout.addLayout(color_grid)
        layout.addStretch()

        content_widget.setLayout(layout)
        scroll.setWidget(content_widget)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def update_panic_key(self, key_name, label_widget, button_widget):
        vk_code = key_to_vk(key_name)  # Returns int
        setattr(Config, "panic_key", vk_code)
        label_widget.setText(f"Panic Key: {key_name}")
        button_widget.setText("Set Panic Key")
        button_widget.setEnabled(True)



    def refresh_ui(self):
        """Refresh all UI elements with current config values"""
        # Update checkboxes
        # Update GPU/CPU overlay toggle
        if hasattr(self, "gpu_overlay_cb"):
            self.gpu_overlay_cb.setChecked(getattr(Config, "use_gpu_overlay", False))

        for attr, checkbox in self.ui_elements.get('checkboxes', {}).items():
            checkbox.setChecked(getattr(Config, attr, False))

        # Update sliders
        for attr, (slider, label) in self.ui_elements.get('sliders', {}).items():
            val = getattr(Config, attr, 1)
            slider.setValue(val)
            label.setText(f"{attr.replace('_', ' ').title()}: {val}")

        # Update comboboxes
        for attr, combo in self.ui_elements.get('comboboxes', {}).items():
            if attr == 'visibility_map_file':
                # Special handling for map file - refresh list first
                self.refresh_map_list()
                # Load the currently selected map if visibility ESP is enabled
                current_map = getattr(Config, 'visibility_map_file', '')
                if current_map and getattr(Config, 'visibility_esp_enabled', False):
                    if not hasattr(Config, 'current_loaded_map') or Config.current_loaded_map != current_map:
                        print(f"[VIS-CHECK] Initial map load triggered: {current_map}")
                        self.on_map_selection_changed(current_map)
            else:
                current_value = getattr(Config, attr, "").lower()
                index = combo.findText(current_value)
                if index >= 0:
                    combo.setCurrentIndex(index)

        # Update color buttons
        for attr, btn in self.ui_elements.get('color_buttons', {}).items():
            color = getattr(Config, attr, (255, 255, 255))
            btn.setStyleSheet(f"background-color: rgb{color}; border: 1px solid black;")

        # Update text inputs
        for attr, text_input in self.ui_elements.get('text_inputs', {}).items():
            value = getattr(Config, attr, "")
            text_input.setText(str(value))

        panic_label = self.ui_elements.get('labels', {}).get('panic_key', None)
        if panic_label:
            vk_code = getattr(Config, 'panic_key', 0x7B)
            panic_label.setText(f"Panic Key: {vk_to_name(vk_code)}")

    def section_title(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        return label

    def add_checkbox_to_grid(self, grid, row, col, label, config_attr):
        cb = CheatCheckBox(label)
        cb.setChecked(getattr(Config, config_attr, False))

        def on_state_change(state):
            enabled = state == Qt.Checked
            setattr(Config, config_attr, enabled)
            if config_attr == "obs_protection_enabled" and hasattr(self, 'main_window'):
                self.main_window.set_obs_protection(enabled)

        cb.stateChanged.connect(on_state_change)
        grid.addWidget(cb, row, col)

        # Store reference for refresh
        if 'checkboxes' not in self.ui_elements:
            self.ui_elements['checkboxes'] = {}
        self.ui_elements['checkboxes'][config_attr] = cb


    def add_checkbox(self, layout, label, config_attr):
        cb = CheatCheckBox(label)
        cb.setChecked(getattr(Config, config_attr, False))
        cb.stateChanged.connect(lambda state: setattr(Config, config_attr, state == Qt.Checked))
        layout.addWidget(cb)

        # Store reference for refresh
        if 'checkboxes' not in self.ui_elements:
            self.ui_elements['checkboxes'] = {}
        self.ui_elements['checkboxes'][config_attr] = cb

    def add_combobox(self, layout, label, options, config_attr, row=None, col=None):
        h_layout = QHBoxLayout()
        h_layout.setSpacing(10)
        h_layout.addWidget(QLabel(label))

        combo = QComboBox()
        combo.addItems(options)

        current_value = getattr(Config, config_attr, options[0]).lower()
        index = combo.findText(current_value)
        if index >= 0:
            combo.setCurrentIndex(index)

        combo.currentTextChanged.connect(lambda val: setattr(Config, config_attr, val.lower()))
        h_layout.addWidget(combo)

        container = QWidget()
        container.setLayout(h_layout)

        if isinstance(layout, QGridLayout) and row is not None and col is not None:
            layout.addWidget(container, row, col)
        else:
            layout.addWidget(container)

        # Store reference for refresh
        if 'comboboxes' not in self.ui_elements:
            self.ui_elements['comboboxes'] = {}
        self.ui_elements['comboboxes'][config_attr] = combo

    def add_slider(self, layout, label, config_attr, min_val, max_val):
        current_val = getattr(Config, config_attr, min_val)
        label_widget = QLabel(f"{label}: {current_val}")
        slider = NoScrollSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(current_val)

        def on_value_changed(val):
            setattr(Config, config_attr, val)
            label_widget.setText(f"{label}: {val}")

        slider.valueChanged.connect(on_value_changed)
        layout.addWidget(label_widget)
        layout.addWidget(slider)

        # Store reference for refresh
        if 'sliders' not in self.ui_elements:
            self.ui_elements['sliders'] = {}
        self.ui_elements['sliders'][config_attr] = (slider, label_widget)

    def add_color_picker_to_grid(self, grid, row, col, label, attr):
        color = getattr(Config, attr, (255, 255, 255))
        initial_color = QColor(*color)

        h_layout = QHBoxLayout()
        h_layout.setSpacing(10)
        h_layout.addWidget(QLabel(label))

        btn = QPushButton()
        btn.setFixedSize(40, 20)
        btn.setStyleSheet(f"background-color: rgb{color}; border: 1px solid black;")

        def on_pick_color():
            color_dialog = QColorDialog.getColor(initial_color, self, f"Select {label} Color")
            if color_dialog.isValid():
                rgb = (color_dialog.red(), color_dialog.green(), color_dialog.blue())
                setattr(Config, attr, rgb)
                btn.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")

        btn.clicked.connect(on_pick_color)
        h_layout.addWidget(btn)

        container = QWidget()
        container.setLayout(h_layout)
        grid.addWidget(container, row, col)

        # Store reference for refresh
        if 'color_buttons' not in self.ui_elements:
            self.ui_elements['color_buttons'] = {}
        self.ui_elements['color_buttons'][attr] = btn

    def refresh_map_list(self):
        """Refresh the map dropdown with available .opt files from maps folder"""
        maps_folder = "maps"
        self.map_combo.clear()
        
        # Create maps folder if it doesn't exist
        os.makedirs(maps_folder, exist_ok=True)
        
        try:
            # Get all .opt files from maps folder
            opt_files = [f for f in os.listdir(maps_folder) if f.lower().endswith('.opt')]
            
            if opt_files:
                # Sort files alphabetically
                opt_files.sort()
                self.map_combo.addItems(opt_files)
                
                # Try to select the current configured map
                current_map = getattr(Config, 'visibility_map_file', '')
                if current_map in opt_files:
                    index = self.map_combo.findText(current_map)
                    if index >= 0:
                        self.map_combo.setCurrentIndex(index)
                elif opt_files:
                    # If current map not found, select first available and update config
                    self.map_combo.setCurrentIndex(0)
                    setattr(Config, 'visibility_map_file', opt_files[0])
            else:
                # No maps found - add placeholder
                self.map_combo.addItem("No maps found - add .opt files to maps folder")
                
        except Exception as e:
            print(f"Error refreshing map list: {e}")
            self.map_combo.addItem("Error reading maps folder")

    def on_map_selection_changed(self, selected_map):
        """Handle map selection change - load/unload maps for visibility checking"""
        if not selected_map or selected_map == "No maps found - add .opt files to maps folder" or selected_map == "Error reading maps folder":
            return
        
        try:
            # Update config
            setattr(Config, 'visibility_map_file', selected_map)
            
            # Unload current map if one is loaded
            if hasattr(Config, 'current_loaded_map') and Config.current_loaded_map:
                print(f"[VIS-CHECK] Unloading map: {Config.current_loaded_map}")
                self.unload_current_map()
            
            # Load the new map
            print(f"[VIS-CHECK] Requesting map load: {selected_map}")
            success = self.load_map_for_visibility_check(selected_map)
            
            if success:
                Config.current_loaded_map = selected_map
                print(f"[VIS-CHECK] Map load request sent: {selected_map}")
            else:
                Config.current_loaded_map = None
                print(f"[VIS-CHECK] Failed to request map load: {selected_map}")
                
        except Exception as e:
            print(f"[VIS-CHECK] Error changing map: {e}")
            Config.current_loaded_map = None

    def load_map_for_visibility_check(self, map_filename):
        """Load a map file for visibility checking"""
        try:
            map_path = os.path.join("maps", map_filename)
            
            if not os.path.exists(map_path):
                print(f"[VIS-CHECK] Map file not found: {map_path}")
                return False
            
            # Set the map file path in config for visibility system to use
            setattr(Config, 'visibility_map_path', map_path)
            setattr(Config, 'visibility_map_loaded', True)
            setattr(Config, 'visibility_map_reload_needed', True)  # Signal ESP to reload
            
            # The actual map loading will happen in ESP thread
            print(f"[VIS-CHECK] Map reload scheduled: {map_path}")
            
            return True
            
        except Exception as e:
            print(f"[VIS-CHECK] Error loading map {map_filename}: {e}")
            return False

    def unload_current_map(self):
        """Unload the currently loaded map"""
        try:
            # Clear map-related config
            setattr(Config, 'visibility_map_path', '')
            setattr(Config, 'visibility_map_loaded', False)
            setattr(Config, 'visibility_map_reload_needed', True)  # Signal ESP to unload
            
            # The actual map unloading will happen in ESP thread
            print("[VIS-CHECK] Map unload scheduled")
            
        except Exception as e:
            print(f"[VIS-CHECK] Error unloading map: {e}")

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

LEARN_DIR = "aimbot_data"

class RecoilViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMinimumSize(850, 550)
        self.setStyleSheet("""
            background-color: #111;
            border-radius: 10px;
            border: 2px solid #00ffff;
        """)

        self.weapon_ids = []
        self.all_data = {}
        self._last_aimbot_plot_hash = None  # ✅ initialize before first use

        self.init_ui()
        self.scan_aimbot_data()  # Initial scan

        # Watcher: rescan every 2 seconds
        self.watcher_thread = DataWatcher()
        self.watcher_thread.data_updated.connect(self.scan_aimbot_data)
        self.watcher_thread.start()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        header = QHBoxLayout()
        header_label = QLabel("GFusion Recoil Analyzer")
        header_label.setStyleSheet("color: #00ffff; font-size: 14px; font-weight: bold;")
        header.addWidget(header_label)
        header.addStretch()
        self.layout.addLayout(header)

        selector = QHBoxLayout()
        label = QLabel("Weapon:")
        label.setStyleSheet("color: white; font-size: 12px;")
        self.dropdown = QComboBox()
        self.dropdown.currentTextChanged.connect(self.update_plot)
        self.dropdown.setStyleSheet("""
            QComboBox {
                background-color: #1e1e1e; color: white;
                border: 1px solid #00ffff; padding: 2px; font-size: 12px;
                border-radius: 5px;
            }
            QComboBox::drop-down { border: none; background: #1e1e1e; }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e; color: white;
                selection-background-color: #00ffff; selection-color: black;
                border: 1px solid #00ffff; outline: 0;
            }
        """)
        selector.addWidget(label)
        selector.addWidget(self.dropdown)
        self.layout.addLayout(selector)

        content = QHBoxLayout()
        self.canvas = FigureCanvas(Figure(facecolor='#1e1e1e'))
        self.ax = self.canvas.figure.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        self.ax.set_aspect('equal')
        content.addWidget(self.canvas, 4)

        self.legend_scroll = QScrollArea()
        self.legend_scroll.setMinimumWidth(200)
        self.legend_scroll.setStyleSheet("""
            QScrollArea {
                background: #111;
                border: 1px solid #444;
                border-radius: 5px;
            }
        """)
        self.legend_widget = QWidget()
        self.legend_layout = QVBoxLayout(self.legend_widget)
        self.legend_layout.setContentsMargins(6, 6, 6, 6)
        self.legend_scroll.setWidgetResizable(True)
        self.legend_scroll.setWidget(self.legend_widget)
        content.addWidget(self.legend_scroll, 1)

        self.layout.addLayout(content)

    def scan_aimbot_data(self):
        if not os.path.exists(LEARN_DIR):
            self.weapon_ids = []
            self.all_data = {}
            self.dropdown.clear()
            self.ax.clear()
            self.canvas.draw()
            return

        new_weapon_ids = [f[:-5] for f in os.listdir(LEARN_DIR) if f.endswith(".json")]
        if set(new_weapon_ids) != set(self.weapon_ids):
            self.weapon_ids = new_weapon_ids
            self.all_data = {}
            self.dropdown.clear()

            for wid in self.weapon_ids:
                try:
                    with open(os.path.join(LEARN_DIR, f"{wid}.json")) as f:
                        data = json.load(f)

                    # Normalize: dict stays dict, list gets wrapped
                    if isinstance(data, list):
                        # raw mouse data → wrap in one entry
                        self.all_data[wid] = {"raw_mouse": data}
                    elif isinstance(data, dict):
                        self.all_data[wid] = data
                    else:
                        self.all_data[wid] = {}

                    self.dropdown.addItem(wid)
                except Exception as e:
                    print(f"Error loading {wid}.json: {e}")

            if self.weapon_ids:
                self.dropdown.setCurrentText(self.weapon_ids[0])
                self.update_plot(self.weapon_ids[0])

    def update_plot(self, weapon_id):
        self.ax.clear()
        self.ax.set_title(f"Recoil & Compensate: {weapon_id}", color='white', fontsize=10)
        self.ax.set_xlabel("Yaw", color='white', fontsize=9)
        self.ax.set_ylabel("Pitch", color='white', fontsize=9)
        self.ax.tick_params(axis='x', colors='white', labelsize=8)
        self.ax.tick_params(axis='y', colors='white', labelsize=8)

        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        data = self.all_data.get(weapon_id, {})

        # Handle both dict (learning) and raw list
        if isinstance(data, dict):
            items = data.items()
        elif isinstance(data, list):
            items = [("raw_mouse", data)]
        else:
            items = []

        for idx, (key, vectors) in enumerate(items):
            x, y = [0], [0]
            inv_x, inv_y = [0], [0]
            for dx, dy in vectors:
                x.append(x[-1] + dy)
                y.append(y[-1] + dx)
                inv_x.append(inv_x[-1] - dy)
                inv_y.append(inv_y[-1] - dx)

            color = f"C{idx % 10}"
            self.ax.plot(x, y, marker='o', color=color, linewidth=2, label=f"Recoil {key}")
            self.ax.plot(inv_x, inv_y, marker='x', linestyle='--', color=color, alpha=0.6,
                         linewidth=2, label=f"Compensate {key}")
            self.add_legend_item(f"Recoil {key}", color)
            self.add_legend_item(f"Compensate {key}", color, dashed=True)

        self.ax.plot(0, 0, 'bo', markersize=8, markeredgecolor='black', zorder=10)
        self.add_legend_item("Center (0,0)", "#00ffff", bold=True)
        self.ax.grid(True, linestyle='--', alpha=0.3)
        self.canvas.draw()

    def add_legend_item(self, text, color, dashed=False, bold=False):
        label = QLabel(text)
        style = f"""
            color: {'#00ffff' if bold else 'white'};
            border-left: 8px {'dashed' if dashed else 'solid'} {color};
            padding: 2px;
            margin-bottom: 2px;
            font-weight: {'bold' if bold else 'normal'};
            font-size: 11px;
        """
        label.setStyleSheet(style)
        self.legend_layout.addWidget(label)

# WinAPI constant for display affinity
WDA_EXCLUDEFROMCAPTURE = 0x11

# Load SetWindowDisplayAffinity
user32 = ctypes.windll.user32
SetWindowDisplayAffinity = user32.SetWindowDisplayAffinity
SetWindowDisplayAffinity.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
SetWindowDisplayAffinity.restype = ctypes.wintypes.BOOL

class CheatCheckBox(QCheckBox):
    def __init__(self, label="", parent=None):
        super().__init__(label, parent)
        self.setStyleSheet("""
            QCheckBox {
                color: black;
                font-size: 10pt;
                font-family: "Comic Sans MS", "Arial", sans-serif;
                padding-left: 8px;
            }

            QCheckBox::indicator {
                width: 24px;
                height: 24px;
                border: 4px solid black;
                background-color: #ffffff;
            }

            QCheckBox::indicator:hover {
                background-color: #ffeb3b;
            }

            QCheckBox::indicator:checked {
                background-color: #f44336;
                border: 4px solid black;
            }

            QCheckBox::indicator:checked:hover {
                background-color: #ff5555;          /* brighter red on hover */
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
                background-color: #ffffff;
                border: 2px solid black;
                border-radius: 0px;
                padding: 2px 6px;
                color: black;
                font-family: "Comic Sans MS", "Arial", sans-serif;
                font-size: 10pt;
            }
            QComboBox:hover {
                background-color: #ffeb3b;
            }
            QComboBox::drop-down {
                border-left: 2px solid black;
                width: 20px;
                background: #00ffff;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0; 
                height: 0;
                border-left: 6px solid black;
                border-top: 4px solid transparent;
                border-bottom: 4px solid transparent;
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 2px solid black;
                selection-background-color: #ff0000;
                selection-color: black;
                font-family: "Comic Sans MS", "Arial", sans-serif;
                font-size: 10pt;
            }
        """)


        
        self.wheelEvent = lambda event: None  # disable scroll


class NoScrollSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("""
            QWidget {
                background-color: #e9e9e9;
                color: black;
                font-family: "Comic Sans MS", sans-serif;
                font-size: 11pt;
            }

            QTabWidget::pane {
                border: 4px solid #000;
                background-color: #ffffff;
            }

            QTabBar::tab {
                width: 84px;
                height: 84px;
                margin: 4px;
                border: 4px solid #000;
                background-color: #ffeb3b;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #2196f3;
                color: #fff;
            }
            QTabBar::tab:hover {
                background-color: #4caf50;
                color: #fff;
            }

            QPushButton {
                background-color: #f44336;
                color: #fff;
                border: 4px solid #000;
                padding: 10px 16px;
                font-weight: bold;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #ff5555;
            }
            QPushButton:pressed {
                background-color: #aa0000;
            }

            QScrollBar:vertical {
                background: #e9e9e9;
                width: 20px;
                border: 3px solid #000;
            }
            QScrollBar::handle:vertical {
                background: #2196f3;
                min-height: 28px;
                border: 3px solid #000;
            }
            QScrollBar::handle:vertical:hover {
                background: #5555ff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)


    def wheelEvent(self, event):
        pass  # disable scroll wheel changes

    def refresh_ui(self):
        """Refresh UI elements - RecoilViewer doesn't have config-dependent UI"""
        pass


import ctypes
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTabWidget, QApplication
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

# --- WinAPI setup for capture protection ---
import ctypes.wintypes
user32 = ctypes.windll.user32
SetWindowDisplayAffinity = user32.SetWindowDisplayAffinity
SetWindowDisplayAffinity.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]
SetWindowDisplayAffinity.restype = ctypes.wintypes.BOOL

# Constant: exclude from capture (OBS, Snipping Tool, Teams, etc.)
WDA_EXCLUDEFROMCAPTURE = 0x11


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GFusion V1 - Paint Edition")
        self.setGeometry(100, 100, 950, 700)
        self.setMinimumSize(900, 650)

        # Frameless, always on top
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Paint-style styling
        self.setStyleSheet("""
            QWidget {
                background-color: #e9e9e9;
                color: black;
                font-family: "Comic Sans MS", sans-serif;
                font-size: 11pt;
            }

            QTabWidget::pane {
                border: 4px solid #000;
                background-color: #ffffff;
            }

            QTabBar::tab {
                width: 84px;
                height: 84px;
                margin: 4px;
                border: 4px solid #000;
                background-color: #ffeb3b;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #2196f3;
                color: #fff;
            }
            QTabBar::tab:hover {
                background-color: #4caf50;
                color: #fff;
            }

            QPushButton {
                background-color: #f44336;
                color: #fff;
                border: 4px solid #000;
                padding: 10px 16px;
                font-weight: bold;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #ff5555;
            }
            QPushButton:pressed {
                background-color: #aa0000;
            }

            QScrollBar:vertical {
                background: #e9e9e9;
                width: 20px;
                border: 3px solid #000;
            }
            QScrollBar::handle:vertical {
                background: #2196f3;
                min-height: 28px;
                border: 3px solid #000;
            }
            QScrollBar::handle:vertical:hover {
                background: #5555ff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Drag movement
        self._drag_active = False
        self._drag_start_pos = None

        # Tabs setup
        self.tabs = QTabWidget()
        self.aimbot_tab = AimbotTab()
        self.esp_tab = ESPTab()
        self.esp_tab.main_window = self

        self.triggerbot_tab = TriggerBotTab()
        self.misc_tab = MiscTab()
        self.config_tab = ConfigTab()
        self.recoil_viewer_tab = RecoilViewer()

        from PyQt5.QtCore import QSize
        self.tabs.setIconSize(QSize(64, 64))
        self.tabs.addTab(self.aimbot_tab, QIcon("icons/aimbot.png"), "")
        self.tabs.addTab(self.esp_tab, QIcon("icons/esp.png"), "")
        self.tabs.addTab(self.triggerbot_tab, QIcon("icons/triggerbot.png"), "")
        self.tabs.addTab(self.misc_tab, QIcon("icons/misc.png"), "")
        self.tabs.addTab(self.recoil_viewer_tab, QIcon("icons/aim_learning.png"), "")
        self.tabs.addTab(self.config_tab, QIcon("icons/config.png"), "")

        # Connect config refresh signals to all tabs
        self.config_tab.config_loaded.connect(self.refresh_all_tabs)

        # Layout
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.tabs)

        # Exit button
        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(self.exit_app)
        layout.addWidget(exit_btn)
        self.setLayout(layout)

        # --- OBS protection init ---
        if getattr(Config, "obs_protection_enabled", False):
            QTimer.singleShot(100, lambda: self.set_obs_protection(True))
        else:
            QTimer.singleShot(100, lambda: self.set_obs_protection(False))

    def refresh_all_tabs(self):
        """Refresh all tab UIs when config is loaded"""
        try:
            if hasattr(self.aimbot_tab, 'refresh_ui'):
                self.aimbot_tab.refresh_ui()
            if hasattr(self.esp_tab, 'refresh_ui'):
                self.esp_tab.refresh_ui()
            if hasattr(self.triggerbot_tab, 'refresh_ui'):
                self.triggerbot_tab.refresh_ui()
            if hasattr(self.misc_tab, 'refresh_ui'):
                self.misc_tab.refresh_ui()
            if hasattr(self.recoil_viewer_tab, 'refresh_ui'):
                self.recoil_viewer_tab.refresh_ui()
            print("[Config] All tabs refreshed successfully")
        except Exception as e:
            print(f"[Config] Error refreshing tabs: {e}")


    # --- OBS / screen capture protection ---
    def set_obs_protection(self, enabled: bool):
        hwnd = int(self.winId())  # get native HWND for this Qt window
        if enabled:
            # Hide from capture
            SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        else:
            # Reset to normal
            SetWindowDisplayAffinity(hwnd, 0)

    def make_obs_proof(self):
        hwnd = int(self.winId())
        success = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        if not success:
            print("[!] Failed to cloak window from screen capture.")

    # Drag events
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_active = True
            self._drag_start_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self._drag_active and self._drag_start_pos is not None:
            delta = event.globalPos() - self._drag_start_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._drag_start_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
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


def run():
    print("Made by GitHub.com/Cr0mb/")
    app = QApplication(sys.argv)

    # Apply global stylesheet
    _apply_global_qss(app)

    win = MainWindow()
    win.show()

    # Start features
    start_aimbot_thread()
    start_esp_thread()
    start_triggerbot_thread()
    start_auto_pistol_thread()

    # Start menu toggle listener
    start_toggle_listener(win)

    app.exec_()  # <--- REQUIRED!


if __name__ == "__main__":
    run()
