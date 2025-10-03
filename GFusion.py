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
import subprocess
import atexit
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTabWidget, QApplication
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QWindow
from PyQt5.QtCore import Qt, QPoint, QTimer, QThread, pyqtSignal, QEasingCurve, QPropertyAnimation
from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import (                                           
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QSlider,
    QLabel, QPushButton, QLineEdit, QComboBox, QTabWidget, QColorDialog,
    QGridLayout, QFrame, QScrollArea, QTextEdit, QMessageBox, QGroupBox,
    QTableWidget, QDoubleSpinBox, QTableWidgetItem
)


from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from Process.config import Config

# Dynamic accessor for offsets
def get_offsets():
    from Process import offsets
    return offsets.Offsets


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
import threading
import importlib
import time
from Process import offsets  # initial import

# ===========================
# Wait for cs2.exe & client.dll
# ===========================
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

# ===========================
# Tab Registry Utilities
# ===========================
def register_tab(tab):
    if tab not in TAB_REGISTRY:
        TAB_REGISTRY.append(tab)

def refresh_all_tabs():
    for tab in TAB_REGISTRY:
        try:
            if hasattr(tab, "refresh_ui"):
                tab.refresh_ui()
        except Exception as e:
            print(f"[UI] Refresh failed for {tab}: {e}")

# ===========================
# Thread Globals
# ===========================
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
esp_thread = None
esp_running = False  # <-- new flag for ESP safety

# ===========================
# Feature Threads
# ===========================
def run_walkbot():
    from Features.walk_bot import walk_in_circle
    walk_in_circle()

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

# ===========================
# ESP with safety guard
# ===========================
def run_esp():
    global esp_running
    if esp_running:
        print("[ESP] Already running, skipping duplicate start")
        return
    esp_running = True
    try:
        Features.esp.main()
    except Exception as e:
        print(f"[ESP] Crashed: {e}")
    finally:
        esp_running = False

def start_esp_thread():
    global esp_thread
    if esp_thread is None or not esp_thread.is_alive():
        esp_thread = threading.Thread(target=run_esp, daemon=True)
        esp_thread.start()

def stop_esp_thread():
    global esp_running
    esp_running = False
    # TODO: add cleanup/shutdown hook inside esp.py if overlay must be destroyed
    print("[ESP] Stop signal sent")

# ===========================
# Offsets Reload
# ===========================
def reload_offsets_and_restart_threads():
    """Reload offsets.py and restart feature threads safely."""
    try:
        importlib.reload(offsets)
        print("[Offsets] Reloaded offsets.py")
    except Exception as e:
        print(f"[Offsets] Failed to reload: {e}")
        return

    def restart():
        time.sleep(2)  # delay for safety
        try:
            stop_esp_thread()
            stop_aimbot_thread()
            stop_triggerbot_thread()
            stop_glow_thread()
            stop_bhop_thread()
        except Exception as e:
            print(f"[Offsets] Error stopping threads: {e}")

        try:
            start_esp_thread()
            start_aimbot_thread()
            start_triggerbot_thread()
            start_glow_thread()
            start_bhop_thread()
            print("[Offsets] All threads restarted")
        except Exception as e:
            print(f"[Offsets] Error restarting threads: {e}")

    threading.Thread(target=restart, daemon=True).start()


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



import os, sys, json
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QGroupBox, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QScrollArea, QMessageBox, QInputDialog, QFileDialog
)

# Assumes CheatCheckBox and NoScrollSlider exist in your project.

class ConfigTab(QWidget):
    config_loaded = pyqtSignal()

    _NEW_ITEM = "➕ New…"

    # ---------- small Win95 helpers ----------
    def _create_group_box(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet("""
            QGroupBox {
                background: #C0C0C0;
                border-top: 1px solid #FFFFFF;
                border-left: 1px solid #FFFFFF;
                border-right: 1px solid #404040;
                border-bottom: 1px solid #404040;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 8pt;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background: #C0C0C0;
            }
        """)
        return g

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#808080; background:#808080;")
        line.setFixedHeight(1)
        return line

    # ---------- ctor ----------
    def __init__(self):
        super().__init__()

        # accept both cfg (instance) or Config (class)
        self.CFG = globals().get("cfg", None) or globals().get("Config", None)
        if self.CFG is None:
            raise RuntimeError("Config/cfg not found in globals")

        from PyQt5.QtCore import QElapsedTimer
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._last_refresh_ms = 0

        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._on_autosave_tick)

        # ---- Scroll container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: #C0C0C0; border: none; }")

        content = QWidget(); content.setStyleSheet("background:#C0C0C0;")
        root = QVBoxLayout(content)
        root.setSpacing(8); root.setContentsMargins(8,8,8,8)

        # ================= Active Config =================
        active_g = self._create_group_box("Active Config")
        active = QVBoxLayout(active_g); active.setSpacing(6)

        row1 = QHBoxLayout()
        name_label = QLabel("Name:")
        name_label.setFixedWidth(40)
        name_label.setStyleSheet("color:#000000; font-size:8pt;")

        self.active_combo = QComboBox()
        self.active_combo.setEditable(False)
        self.active_combo.setInsertPolicy(QComboBox.NoInsert)
        self.active_combo.activated[str].connect(self._on_active_changed)

        self.save_btn = QPushButton("Save")
        self.load_btn = QPushButton("Load")
        self.apply_btn = QPushButton("Apply & Broadcast")
        for b in (self.save_btn, self.load_btn, self.apply_btn):
            b.setFixedHeight(24)

        row1.addWidget(name_label)
        row1.addWidget(self.active_combo, 1)
        row1.addWidget(self.save_btn)
        row1.addWidget(self.load_btn)
        row1.addWidget(self.apply_btn)
        active.addLayout(row1)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color:#000000; font-size:8pt;")
        active.addWidget(self.status_label)
        root.addWidget(active_g)

        # ================= Saved Configs =================
        saved_g = self._create_group_box("Saved Configs")
        saved = QVBoxLayout(saved_g); saved.setSpacing(6)

        lr1 = QHBoxLayout()
        list_label = QLabel("Saved:")
        list_label.setFixedWidth(40)
        list_label.setStyleSheet("color:#000; font-size:8pt;")
        self.config_list = QComboBox()
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedWidth(28)
        self.refresh_btn.setToolTip("Refresh list")
        lr1.addWidget(list_label)
        lr1.addWidget(self.config_list, 1)
        lr1.addWidget(self.refresh_btn, 0)

        lr2 = QHBoxLayout()
        self.rename_btn    = QPushButton("Rename")
        self.duplicate_btn = QPushButton("Duplicate")
        self.delete_btn    = QPushButton("Delete")
        for b in (self.rename_btn, self.duplicate_btn, self.delete_btn):
            b.setFixedHeight(24)
        lr2.addWidget(self.rename_btn)
        lr2.addWidget(self.duplicate_btn)
        lr2.addWidget(self.delete_btn)
        lr2.addStretch(1)

        saved.addLayout(lr1)
        saved.addLayout(lr2)
        root.addWidget(saved_g)

        # ================= Import / Export =================
        io_g = self._create_group_box("Import / Export")
        io = QHBoxLayout(io_g); io.setSpacing(10)

        self.import_btn = QPushButton("Import (.json)")
        self.export_btn = QPushButton("Export (.json)")
        for b in (self.import_btn, self.export_btn):
            b.setFixedHeight(24)

        io.addWidget(self.import_btn)
        io.addWidget(self.export_btn)
        io.addStretch(1)
        root.addWidget(io_g)

        # ================= Auto-save =================
        auto_g = self._create_group_box("Auto-Save")
        auto = QHBoxLayout(auto_g); auto.setSpacing(10)

        self.autosave_cb = CheatCheckBox("Enable Auto-Save")
        self.autosave_cb.setChecked(bool(getattr(self.CFG, "autosave_enabled", False)))
        self.autosave_cb.stateChanged.connect(self._toggle_autosave)

        self.autosave_slider = NoScrollSlider(Qt.Horizontal)
        self.autosave_slider.setMinimum(1)
        self.autosave_slider.setMaximum(30)
        cur_mins = int(getattr(self.CFG, "autosave_minutes", 5))
        self.autosave_slider.setValue(max(1, min(30, cur_mins)))

        self.autosave_label = QLabel(f"Interval: {self.autosave_slider.value()} min")
        self.autosave_label.setStyleSheet("color:#000; font-size:8pt;")

        def on_auto_change(v):
            setattr(self.CFG, "autosave_minutes", int(v))
            self.autosave_label.setText(f"Interval: {int(v)} min")
            if self._autosave_timer.isActive():
                self._autosave_timer.start(int(v) * 60_000)

        self.autosave_slider.valueChanged.connect(on_auto_change)

        auto.addWidget(self.autosave_cb)
        auto.addWidget(self.autosave_label)
        auto.addWidget(self.autosave_slider)
        auto.addStretch(1)
        root.addWidget(auto_g)

        # ================= Folder =================
        dir_g = self._create_group_box("Folder")
        di = QHBoxLayout(dir_g); di.setSpacing(10)

        self.open_folder_btn = QPushButton("Open Config Folder")
        self.open_folder_btn.setFixedHeight(24)
        di.addWidget(self.open_folder_btn)
        di.addStretch(1)
        root.addWidget(dir_g)

        # finalize scroll
        root.addStretch(1)
        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)

        # ---------- wire actions ----------
        self.refresh_btn.clicked.connect(self.refresh_config_list)
        self.save_btn.clicked.connect(self.save_config)
        self.load_btn.clicked.connect(self.load_config)
        self.apply_btn.clicked.connect(self._apply_broadcast)

        self.rename_btn.clicked.connect(self.rename_config)
        self.duplicate_btn.clicked.connect(self.duplicate_config)
        self.delete_btn.clicked.connect(self.delete_config)

        self.import_btn.clicked.connect(self.import_config)
        self.export_btn.clicked.connect(self.export_config)

        self.open_folder_btn.clicked.connect(self.open_config_folder)

        # initial fill
        self.refresh_config_list()
        self.refresh_ui()

        # heartbeat tick
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(16)  # ~60Hz; we throttle UI to ~15 FPS

    # ---------- periodic tick ----------
    def _tick(self):
        if hasattr(self, 'refresh_ui'):
            now = self._elapsed.elapsed()
            if now - getattr(self, '_last_refresh_ms', 0) > 66:  # ~15 FPS
                try:
                    self.refresh_ui()
                finally:
                    self._last_refresh_ms = now

    # ---------- core ops ----------
    def _configs_dir(self) -> str:
        return getattr(self.CFG, "configs_dir", "config")

    def _list_configs(self):
        path = self._configs_dir()
        os.makedirs(path, exist_ok=True)
        names = []
        for f in os.listdir(path):
            if f.lower().endswith(".json"):
                names.append(f[:-5])
        names.sort()
        return names

    def _populate_combo(self, combo: QComboBox, names, current: str = ""):
        combo.blockSignals(True)
        combo.clear()
        # For the ACTIVE combo, prepend a "New…" item
        if combo is self.active_combo:
            combo.addItem(self._NEW_ITEM)
        for n in names:
            combo.addItem(n)
        # select current if present
        if current:
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def refresh_config_list(self):
        try:
            names = self._list_configs()
            cur_active = getattr(self.CFG, "current_config_name", "") or (names[0] if names else "")
            self._populate_combo(self.active_combo, names, cur_active)
            self._populate_combo(self.config_list, names, cur_active)
        except Exception as e:
            print(f"[ConfigTab] refresh_config_list error: {e}")

    def _ensure_active_name(self) -> str:
        """
        Ensure we have a concrete active name. If the dropdown is on 'New…' or empty,
        prompt for a new name and (optionally) set it as current_config_name.
        """
        name = self.active_combo.currentText().strip()
        if not name or name == self._NEW_ITEM:
            base = "new_profile"
            name, ok = self._prompt_text("New Config", "Name:", base)
            if not ok or not name.strip():
                return ""
            name = name.strip()
            # If exists, find a unique variant
            if os.path.exists(os.path.join(self._configs_dir(), f"{name}.json")):
                name = self._unique_name(name)
            # set selected item to the newly created name
            # and set as current_config_name
            try:
                setattr(self.CFG, "current_config_name", name)
            except Exception:
                pass
            # Refresh and select
            self.refresh_config_list()
            idx = self.active_combo.findText(name)
            if idx >= 0:
                self.active_combo.setCurrentIndex(idx)
        return self.active_combo.currentText().strip()

    def save_config(self):
        name = self._ensure_active_name()
        if not name:
            self.status_label.setText("Status: ✗ Choose or create a name")
            return
        try:
            if hasattr(self.CFG, "save_to_file"):
                self.CFG.save_to_file(name)
            else:
                path = os.path.join(self._configs_dir(), f"{name}.json")
                os.makedirs(self._configs_dir(), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._serialize_cfg(), f, indent=2)
            # update lists
            self.refresh_config_list()
            self.status_label.setText(f"Status: ✓ Saved '{name}'")
        except Exception as e:
            print(f"[Config] Error saving '{name}': {e}")
            self.status_label.setText("Status: ✗ Save error")

    def load_config(self):
        # Prefer active dropdown; if it's 'New…', fall back to Saved combo
        name = self.active_combo.currentText().strip()
        if not name or name == self._NEW_ITEM:
            name = self.config_list.currentText().strip()
        if not name:
            self.status_label.setText("Status: ✗ Select a config")
            return
        try:
            if hasattr(self.CFG, "load_from_file"):
                self.CFG.load_from_file(name)
            else:
                path = os.path.join(self._configs_dir(), f"{name}.json")
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._deserialize_cfg(data)
            # remember current name if supported
            try: setattr(self.CFG, "current_config_name", name)
            except: pass
            self.refresh_config_list()
            self.status_label.setText(f"Status: ✓ Loaded '{name}'")
            self.config_loaded.emit()
        except Exception as e:
            print(f"[Config] Error loading '{name}': {e}")
            self.status_label.setText("Status: ✗ Load error")

    def _apply_broadcast(self):
        try:
            self.config_loaded.emit()
            self.status_label.setText("Status: ✓ Applied")
        except Exception as e:
            print(f"[ConfigTab] apply error: {e}")
            self.status_label.setText("Status: ✗ Apply error")

    # ---------- list actions ----------
    def rename_config(self):
        cur = self.config_list.currentText()
        if not cur:
            self.status_label.setText("Status: ✗ Nothing selected")
            return
        new, ok = self._prompt_text("Rename Config", "New name:", cur)
        if not ok or not new.strip():
            return
        new = new.strip()
        src = os.path.join(self._configs_dir(), f"{cur}.json")
        dst = os.path.join(self._configs_dir(), f"{new}.json")
        try:
            if os.path.exists(dst):
                self.status_label.setText("Status: ✗ Name exists")
                return
            os.rename(src, dst)
            # Update current name if it was active
            if getattr(self.CFG, "current_config_name", "") == cur:
                try: setattr(self.CFG, "current_config_name", new)
                except: pass
            self.refresh_config_list()
            # select renamed in both combos
            idx = self.active_combo.findText(new)
            if idx >= 0:
                self.active_combo.setCurrentIndex(idx)
            self.status_label.setText(f"Status: ✓ Renamed to '{new}'")
        except Exception as e:
            print(f"[ConfigTab] rename error: {e}")
            self.status_label.setText("Status: ✗ Rename error")

    def duplicate_config(self):
        cur = self.config_list.currentText()
        if not cur:
            self.status_label.setText("Status: ✗ Nothing selected")
            return
        copy_name = f"{cur}_copy"
        copy_name, ok = self._prompt_text("Duplicate Config", "Copy name:", copy_name)
        if not ok or not copy_name.strip():
            return
        src = os.path.join(self._configs_dir(), f"{cur}.json")
        dst = os.path.join(self._configs_dir(), f"{copy_name}.json")
        try:
            if os.path.exists(dst):
                self.status_label.setText("Status: ✗ Name exists")
                return
            import shutil
            shutil.copyfile(src, dst)
            self.refresh_config_list()
            # select the new copy in active
            idx = self.active_combo.findText(copy_name)
            if idx >= 0:
                self.active_combo.setCurrentIndex(idx)
            self.status_label.setText(f"Status: ✓ Duplicated to '{copy_name}'")
        except Exception as e:
            print(f"[ConfigTab] duplicate error: {e}")
            self.status_label.setText("Status: ✗ Duplicate error")

    def delete_config(self):
        cur = self.config_list.currentText()
        if not cur:
            self.status_label.setText("Status: ✗ Nothing selected")
            return
        if getattr(self.CFG, "current_config_name", "") == cur:
            # soft guard: don't accidentally delete active
            ret = QMessageBox.question(self, "Delete Active Config",
                                       f"'{cur}' is active. Delete anyway?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
        ret = QMessageBox.question(self, "Delete Config",
                                   f"Delete '{cur}' permanently?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret != QMessageBox.Yes:
            return
        try:
            path = os.path.join(self._configs_dir(), f"{cur}.json")
            if os.path.exists(path):
                os.remove(path)
            # clear active if it was deleted
            if getattr(self.CFG, "current_config_name", "") == cur:
                try: setattr(self.CFG, "current_config_name", "")
                except: pass
            self.refresh_config_list()
            self.status_label.setText(f"Status: ✓ Deleted '{cur}'")
        except Exception as e:
            print(f"[ConfigTab] delete error: {e}")
            self.status_label.setText("Status: ✗ Delete error")

    # ---------- import/export ----------
    def import_config(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Import Config", "", "Config (*.json)")
            if not path:
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = os.path.splitext(os.path.basename(path))[0]
            dst = os.path.join(self._configs_dir(), f"{name}.json")
            if os.path.exists(dst):
                name = self._unique_name(name)
                dst = os.path.join(self._configs_dir(), f"{name}.json")
            os.makedirs(self._configs_dir(), exist_ok=True)
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.refresh_config_list()
            idx = self.active_combo.findText(name)
            if idx >= 0:
                self.active_combo.setCurrentIndex(idx)
            self.status_label.setText(f"Status: ✓ Imported '{name}'")
        except Exception as e:
            print(f"[ConfigTab] import error: {e}")
            self.status_label.setText("Status: ✗ Import error")

    def export_config(self):
        name = self.active_combo.currentText().strip() or self.config_list.currentText().strip()
        if not name or name == self._NEW_ITEM:
            self.status_label.setText("Status: ✗ Choose a config")
            return
        try:
            path, _ = QFileDialog.getSaveFileName(self, "Export Config", f"{name}.json", "Config (*.json)")
            if not path:
                return
            if hasattr(self.CFG, "read_config_dict"):
                data = self.CFG.read_config_dict(name)
            else:
                src = os.path.join(self._configs_dir(), f"{name}.json")
                with open(src, "r", encoding="utf-8") as f:
                    data = json.load(f)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self.status_label.setText(f"Status: ✓ Exported to '{os.path.basename(path)}'")
        except Exception as e:
            print(f"[ConfigTab] export error: {e}")
            self.status_label.setText("Status: ✗ Export error")

    # ---------- folder ----------
    def open_config_folder(self):
        path = os.path.abspath(self._configs_dir())
        try:
            os.makedirs(path, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa
            elif sys.platform == "darwin":
                import subprocess; subprocess.Popen(["open", path])
            else:
                import subprocess; subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print(f"[ConfigTab] open folder error: {e}")

    # ---------- autosave ----------
    def _toggle_autosave(self, state):
        enabled = (state == Qt.Checked)
        setattr(self.CFG, "autosave_enabled", enabled)
        mins = int(getattr(self.CFG, "autosave_minutes", 5))
        if enabled:
            self._autosave_timer.start(max(1, mins) * 60_000)
            self.status_label.setText("Status: Auto-save ON")
        else:
            self._autosave_timer.stop()
            self.status_label.setText("Status: Auto-save OFF")

    def _on_autosave_tick(self):
        # Save to the currently active name (if any)
        name = getattr(self.CFG, "current_config_name", "") or self.active_combo.currentText().strip()
        if not name or name == self._NEW_ITEM:
            return
        try:
            if hasattr(self.CFG, "save_to_file"):
                self.CFG.save_to_file(name)
            else:
                path = os.path.join(self._configs_dir(), f"{name}.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._serialize_cfg(), f, indent=2)
        except Exception as e:
            print(f"[ConfigTab] autosave error: {e}")

    # ---------- UI sync ----------
    def refresh_ui(self):
        try:
            self.setUpdatesEnabled(False)
            cur_name = getattr(self.CFG, "current_config_name", "")
            # reflect current name into both combos if present
            if cur_name:
                idx_a = self.active_combo.findText(cur_name)
                if idx_a >= 0 and self.active_combo.currentIndex() != idx_a:
                    self.active_combo.setCurrentIndex(idx_a)
                idx_b = self.config_list.findText(cur_name)
                if idx_b >= 0 and self.config_list.currentIndex() != idx_b:
                    self.config_list.setCurrentIndex(idx_b)
            # autosave widgets
            self.autosave_cb.setChecked(bool(getattr(self.CFG, "autosave_enabled", False)))
            self.autosave_slider.setValue(int(getattr(self.CFG, "autosave_minutes", 5)))
            self.autosave_label.setText(f"Interval: {self.autosave_slider.value()} min")
        finally:
            self.setUpdatesEnabled(True)

    # ---------- handlers ----------
    def _on_active_changed(self, text: str):
        """Handle active dropdown selection, including 'New…'."""
        if text == self._NEW_ITEM:
            # prompt to create; selection will update in _ensure_active_name during save
            # Optionally, immediately prompt to set active:
            name = self._ensure_active_name()
            if name:
                try: setattr(self.CFG, "current_config_name", name)
                except: pass
                self.status_label.setText(f"Status: ✓ Active set to '{name}'")
        else:
            try: setattr(self.CFG, "current_config_name", text)
            except: pass
            # keep Saved list selection in sync
            idx = self.config_list.findText(text)
            if idx >= 0:
                self.config_list.setCurrentIndex(idx)
            self.status_label.setText(f"Status: Active = '{text}'")

    # ---------- tiny utils ----------
    def _prompt_text(self, title, label, text=""):
        s, ok = QInputDialog.getText(self, title, label, text=text)
        return s, ok

    def _unique_name(self, base: str) -> str:
        i = 1
        while True:
            cand = f"{base}_{i}"
            if not os.path.exists(os.path.join(self._configs_dir(), f"{cand}.json")):
                return cand
            i += 1

    def _serialize_cfg(self) -> dict:
        """Conservative fallback serializer; ignores callables/private fields."""
        d = {}
        for k in dir(self.CFG):
            if k.startswith("_"):
                continue
            try:
                v = getattr(self.CFG, k)
            except Exception:
                continue
            if callable(v):
                continue
            if isinstance(v, (str, int, float, bool, list, dict, type(None))):
                d[k] = v
        return d

    def _deserialize_cfg(self, data: dict):
        for k, v in data.items():
            try:
                setattr(self.CFG, k, v)
            except Exception:
                pass

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
    """
    TriggerBot tab styled like ESP/Misc: Win95 group boxes, compact rows,
    consistent helpers (checkboxes, sliders, key picker), logging-friendly.
    """
    def __init__(self):
        super().__init__()
        # Accept both cfg (instance) and Config (class) patterns safely
        self.CFG = globals().get("cfg", None) or globals().get("Config", None)
        if self.CFG is None:
            raise RuntimeError("Config/cfg not found in globals")

        self.ui = {"checkboxes": {}, "sliders": {}, "labels": {}}
        self.listener_thread = None
        self.init_ui()

    # ---------- Local helpers (match Misc/ESP look) ----------
    def create_group_box(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet("""
            QGroupBox {
                background: #C0C0C0;
                border-top: 1px solid #FFFFFF;
                border-left: 1px solid #FFFFFF;
                border-right: 1px solid #404040;
                border-bottom: 1px solid #404040;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 8pt;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background: #C0C0C0;
            }
        """)
        return g

    def add_checkbox(self, layout, label, cfg_key, on_toggle=None, default=False):
        cb = CheatCheckBox(label)
        cb.setChecked(bool(getattr(self.CFG, cfg_key, default)))
        def handler(st):
            enabled = (st == Qt.Checked)
            setattr(self.CFG, cfg_key, enabled)
            if on_toggle:
                try: on_toggle(enabled)
                except Exception as e: print(f"[TriggerBotTab] toggle {cfg_key} error: {e}")
        cb.stateChanged.connect(handler)
        layout.addWidget(cb)
        self.ui["checkboxes"][cfg_key] = cb
        return cb

    def add_float_slider(self, layout, label, cfg_key, min_v, max_v, step_mult, suffix=""):
        """Float slider with label, e.g. 0.01..1.00 (x step_mult)"""
        val = float(getattr(self.CFG, cfg_key, min_v))
        lab = QLabel(f"{label}: {val:.2f}{suffix}")
        lab.setStyleSheet("color: #000000; font-size: 8pt;")
        sld = NoScrollSlider(Qt.Horizontal)
        sld.setMinimum(int(min_v*step_mult)); sld.setMaximum(int(max_v*step_mult))
        sld.setValue(int(val*step_mult))
        def on_change(v):
            real = v / float(step_mult)
            setattr(self.CFG, cfg_key, real)
            lab.setText(f"{label}: {real:.2f}{suffix}")
        sld.valueChanged.connect(on_change)
        layout.addWidget(lab); layout.addWidget(sld)
        self.ui["sliders"][cfg_key] = (sld, lab, step_mult, suffix, label)
        return sld, lab

    def add_int_slider(self, layout, label, cfg_key, min_v, max_v, suffix=""):
        val = int(getattr(self.CFG, cfg_key, min_v))
        lab = QLabel(f"{label}: {val}{suffix}")
        lab.setStyleSheet("color: #000000; font-size: 8pt;")
        sld = NoScrollSlider(Qt.Horizontal)
        sld.setMinimum(min_v); sld.setMaximum(max_v); sld.setValue(val)
        def on_change(v):
            setattr(self.CFG, cfg_key, int(v))
            lab.setText(f"{label}: {int(v)}{suffix}")
        sld.valueChanged.connect(on_change)
        layout.addWidget(lab); layout.addWidget(sld)
        self.ui["sliders"][cfg_key] = (sld, lab, 1, suffix, label)
        return sld, lab

    # ---------- UI ----------
    def init_ui(self):
        # Scroll container (match other tabs)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: #C0C0C0; border: none; }")

        content = QWidget(); content.setStyleSheet("background: #C0C0C0;")
        root = QVBoxLayout(content)
        root.setSpacing(8); root.setContentsMargins(8, 8, 8, 8)

        # ===== Main =====
        main_g = self.create_group_box("Main")
        main = QHBoxLayout(main_g); main.setSpacing(10)

        left = QVBoxLayout()
        self.add_checkbox(left, "Enable TriggerBot", "triggerbot_enabled",
                          on_toggle=self._toggle_triggerbot)
        self.add_checkbox(left, "Always On (Ignore Trigger Key)", "triggerbot_always_on")
        self.add_checkbox(left, "Allow Shooting Teammates", "shoot_teammates")
        main.addLayout(left, 1)

        right = QVBoxLayout()
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color:#000000; font-size: 8pt;")
        right.addWidget(self.status_label)

        right.addStretch(1)
        main.addLayout(right, 1)
        root.addWidget(main_g)

        # ===== Key Settings =====
        key_g = self.create_group_box("Key Settings")
        key = QHBoxLayout(key_g); key.setSpacing(10)

        self.trigger_key_label = QLabel(f"Trigger Key: {getattr(self.CFG, 'trigger_key', 'mouse5')}")
        self.trigger_key_label.setStyleSheet("color:#000000; font-size:8pt;")
        key.addWidget(self.trigger_key_label)

        self.set_key_btn = QPushButton("Set Trigger Key")
        self.set_key_btn.clicked.connect(self.set_trigger_key)
        key.addWidget(self.set_key_btn)
        key.addStretch(1)

        root.addWidget(key_g)

        # ===== Behavior =====
        beh_g = self.create_group_box("Behavior")
        beh = QGridLayout(beh_g); beh.setHorizontalSpacing(12); beh.setVerticalSpacing(6)

        # Cooldown (fires-after delay)
        box1 = QVBoxLayout()
        self.add_float_slider(box1, "Cooldown (s)", "triggerbot_cooldown", 0.00, 1.00, 100, "s")
        w1 = QWidget(); w1.setLayout(box1); beh.addWidget(w1, 0, 0)

        # Anti-detection: small pre-fire delay range (min/max)
        box2 = QVBoxLayout()
        self.add_float_slider(box2, "Reaction Delay Min (s)", "trigger_delay_min", 0.000, 0.150, 1000, "s")
        self.add_float_slider(box2, "Reaction Delay Max (s)", "trigger_delay_max", 0.000, 0.250, 1000, "s")
        w2 = QWidget(); w2.setLayout(box2); beh.addWidget(w2, 0, 1)

        # Anti-detection: micro-jitter and burst control
        box3 = QVBoxLayout()
        self.add_float_slider(box3, "Shot Jitter (s)", "trigger_jitter", 0.000, 0.030, 1000, "s")
        self.add_int_slider(box3, "Burst Shots", "trigger_burst_shots", 1, 5)
        w3 = QWidget(); w3.setLayout(box3); beh.addWidget(w3, 0, 2)

        root.addWidget(beh_g)

        # ===== Safety =====
        safe_g = self.create_group_box("Safety")
        safe = QHBoxLayout(safe_g); safe.setSpacing(10)

        # Soft-guard to reduce AD risk: only when visible checks elsewhere pass
        self.add_checkbox(safe, "Require VisCheck (if available)", "trigger_require_vischeck", default=True)

        if hasattr(self.CFG, "panic_key_enabled"):
            self.add_checkbox(safe, "Panic Key Enabled", "panic_key_enabled")

        safe.addStretch(1)
        root.addWidget(safe_g)

        root.addStretch()
        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)

    # ---------- Start/Stop ----------
    def _toggle_triggerbot(self, enabled: bool):
        try:
            if enabled:
                self.status_label.setText("Status: Starting…")
                start_triggerbot_thread()
                self.status_label.setText("Status: Running")
            else:
                self.status_label.setText("Status: Stopping…")
                stop_triggerbot_thread()
                self.status_label.setText("Status: Idle")
        except Exception as e:
            print(f"[TriggerBotTab] toggle error: {e}")
            self.status_label.setText("Status: Error")

    # ---------- Key capture ----------
    def set_trigger_key(self):
        self.set_key_btn.setText("Press any key…")
        self.set_key_btn.setEnabled(False)

        try:
            if self.listener_thread and self.listener_thread.isRunning():
                self.listener_thread.requestInterruption()
                self.listener_thread.quit()
                self.listener_thread.wait(150)

            self.listener_thread = KeyListenerThread()
            self.listener_thread.key_pressed.connect(self.key_set)
            self.listener_thread.start()
        except Exception as e:
            print(f"[TriggerBotTab] key listener error: {e}")
            self.set_key_btn.setText("Set Trigger Key")
            self.set_key_btn.setEnabled(True)

    def key_set(self, key_name):
        setattr(self.CFG, "trigger_key", key_name)
        self.trigger_key_label.setText(f"Trigger Key: {getattr(self.CFG,'trigger_key','')}")
        self.set_key_btn.setText("Set Trigger Key")
        self.set_key_btn.setEnabled(True)

    # ---------- Sync ----------
    def refresh_ui(self):
        """
        Refresh all UI elements from current config values.
        Safe against missing keys (uses defaults).
        """
        try:
            self.setUpdatesEnabled(False)

            # checkboxes
            for key, cb in self.ui["checkboxes"].items():
                cb.setChecked(bool(getattr(self.CFG, key, cb.isChecked())))

            # sliders
            for key, (sld, lab, mult, suffix, base_label) in self.ui["sliders"].items():
                val = getattr(self.CFG, key, None)
                if val is None: 
                    continue
                if mult == 1:
                    sld.setValue(int(val))
                    lab.setText(f"{base_label}: {int(val)}{suffix}")
                else:
                    sld.setValue(int(float(val) * mult))
                    lab.setText(f"{base_label}: {float(val):.2f}{suffix}")

            # labels
            self.trigger_key_label.setText(f"Trigger Key: {getattr(self.CFG,'trigger_key','mouse5')}")

        finally:
            self.setUpdatesEnabled(True)

class MiscTab(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_elements = {"color_buttons": {}}
        self.init_ui()

    # ---------- Helpers ----------
    def section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; font-size: 9pt; color: #000000;")
        return lbl

    def add_separator(self, layout: QVBoxLayout):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #808080; max-height: 1px;")
        layout.addWidget(sep)

    # --------- COLOR SAFETY ---------
    @staticmethod
    def _clamp8(x) -> int:
        try:
            return max(0, min(255, int(round(float(x)))))
        except Exception:
            return 0

    @classmethod
    def _normalize_rgba(cls, rgba_tuple):
        """
        Accepts (r,g,b) or (r,g,b,a). Channels may be:
          - 0..1 floats (normalized) or
          - 0..255 ints
        Returns clamped ints in 0..255 for RGBA.
        """
        # Expand to 4 channels
        if len(rgba_tuple) == 3:
            r, g, b = rgba_tuple
            a = 255
        else:
            r, g, b, a = rgba_tuple[:4]

        # Detect normalized floats for RGB
        try:
            rf, gf, bf = float(r), float(g), float(b)
            is_norm = (0.0 <= rf <= 1.0) and (0.0 <= gf <= 1.0) and (0.0 <= bf <= 1.0)
        except Exception:
            is_norm = False

        if is_norm:
            r, g, b = rf * 255.0, gf * 255.0, bf * 255.0

        # Alpha can be float 0..1 as well
        try:
            af = float(a)
            if 0.0 <= af <= 1.0:
                a = af * 255.0
        except Exception:
            pass

        return (
            cls._clamp8(r),
            cls._clamp8(g),
            cls._clamp8(b),
            cls._clamp8(a),
        )

    @classmethod
    def rgb_to_stylesheet_safe(cls, rgb_or_rgba) -> str:
        """Safe stylesheet writer for rgb/rgba that clamps + normalizes."""
        r, g, b, a = cls._normalize_rgba(tuple(rgb_or_rgba))
        if a >= 255:
            return f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;"
        return f"background-color: rgba({r}, {g}, {b}, {a}); border: 1px solid black;"

    @classmethod
    def _sanitize_rgb3(cls, rgb_or_rgba):
        """Return a safe (r,g,b) tuple of ints 0..255 (drops alpha if present)."""
        r, g, b, _ = cls._normalize_rgba(tuple(rgb_or_rgba))
        return (r, g, b)

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
        """
        Generic color picker row.
        - Seeds QColor with a sanitized current color
        - Writes sanitized color back to config and preview button
        """
        row = QHBoxLayout()
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet("color: #000000; font-size: 8pt;")
        row.addWidget(lbl)

        rgb = self._sanitize_rgb3(getattr(Config, cfg_key, default))
        btn = QPushButton()
        btn.setFixedSize(40, 18)
        btn.setStyleSheet(self.rgb_to_stylesheet_safe(rgb))

        def choose_color():
            current = self._sanitize_rgb3(getattr(Config, cfg_key, default))
            initial = QColor(*current)  # safe ints 0..255
            color = QColorDialog.getColor(initial, self, f"Select {label}")
            if color.isValid():
                new_rgb = (color.red(), color.green(), color.blue())
                setattr(Config, cfg_key, new_rgb)
                btn.setStyleSheet(self.rgb_to_stylesheet_safe(new_rgb))

        btn.clicked.connect(choose_color)
        row.addWidget(btn)
        layout.addLayout(row)

        self.ui_elements["color_buttons"][cfg_key] = btn
        return btn

    def create_group_box(self, title: str) -> QGroupBox:
        """Create a Win95-style group box"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                background: #C0C0C0;
                border-top: 1px solid #FFFFFF;
                border-left: 1px solid #FFFFFF;
                border-right: 1px solid #404040;
                border-bottom: 1px solid #404040;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 8pt;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background: #C0C0C0;
            }
        """)
        return group

    # ---------- UI ----------
    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: #C0C0C0;
                border: none;
            }
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet("background: #C0C0C0;")
        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ===== ROW 1: FOV & Glow =====
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
        # FOV Section
        fov_group = self.create_group_box("FOV Changer")
        fov_layout = QVBoxLayout(fov_group)
        fov_layout.setSpacing(4)
        
        self.fov_checkbox = self.add_checkbox(
            fov_layout, "Enable FOV Changer", "fov_changer_enabled",
            default=True, thread_start=start_fov_thread, thread_stop=stop_fov_thread
        )
        self.fov_label = QLabel(f"Game FOV: {cfg.game_fov}")
        self.fov_label.setStyleSheet("color: #000000; font-size: 8pt;")
        self.fov_slider = NoScrollSlider(Qt.Horizontal)
        self.fov_slider.setRange(60, 150)
        self.fov_slider.setValue(cfg.game_fov)
        self.fov_slider.valueChanged.connect(self.update_fov)
        fov_layout.addWidget(self.fov_label)
        fov_layout.addWidget(self.fov_slider)
        fov_layout.addStretch()
        
        # Glow Section
        glow_group = self.create_group_box("Glow Effects")
        glow_layout = QVBoxLayout(glow_group)
        glow_layout.setSpacing(4)
        
        self.glow_checkbox = self.add_checkbox(
            glow_layout, "Enable Glow", "glow",
            default=False, thread_start=start_glow_thread, thread_stop=stop_glow_thread
        )
        self.add_checkbox(glow_layout, "Glow Enemies", "glow_show_enemies", default=True)
        self.add_checkbox(glow_layout, "Glow Team", "glow_show_team", default=True)
        self.add_color_picker(glow_layout, "Enemy Color", "glow_color_enemy", (255, 0, 0))
        self.add_color_picker(glow_layout, "Team Color", "glow_color_team", (0, 255, 0))
        glow_layout.addStretch()
        
        row1.addWidget(fov_group, 1)
        row1.addWidget(glow_group, 1)
        main_layout.addLayout(row1)

        # ===== ROW 2: Bunny Hop =====
        bhop_group = self.create_group_box("Bunny Hop")
        bhop_main = QHBoxLayout(bhop_group)
        bhop_main.setSpacing(12)
        
        # Left side
        left_side = QVBoxLayout()
        left_side.setSpacing(4)
        self.bhop_checkbox = self.add_checkbox(
            left_side, "Enable Bunny Hop", "bhop_enabled",
            thread_start=start_bhop_thread, thread_stop=stop_bhop_thread
        )
        self.add_checkbox(left_side, "Show Info Box", "show_local_info_box", default=True)
        left_side.addStretch()
        
        # Right side - colors in grid
        right_side = QVBoxLayout()
        colors_grid = QGridLayout()
        colors_grid.setSpacing(4)
        
        color_items = [
            ("Coords", "color_local_coords_text"),
            ("Velocity", "color_local_velocity_text"),
            ("Speed", "color_local_speed_text"),
            ("Background", "color_local_box_background"),
            ("Border", "color_local_box_border"),
        ]
        
        for idx, (label, key) in enumerate(color_items):
            row = idx // 2
            col = idx % 2
            
            item_layout = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #000000; font-size: 8pt;")
            lbl.setFixedWidth(70)
            item_layout.addWidget(lbl)
            
            rgb = self._sanitize_rgb3(getattr(Config, key, (0, 0, 0)))
            btn = QPushButton()
            btn.setFixedSize(30, 16)
            btn.setStyleSheet(self.rgb_to_stylesheet_safe(rgb))
            
            def make_color_callback(cfg_key, button, default_val=(0,0,0)):
                def choose():
                    current = self._sanitize_rgb3(getattr(Config, cfg_key, default_val))
                    initial = QColor(*current)
                    color = QColorDialog.getColor(initial, self, f"Select {cfg_key}")
                    if color.isValid():
                        new_rgb = (color.red(), color.green(), color.blue())
                        setattr(Config, cfg_key, new_rgb)
                        button.setStyleSheet(self.rgb_to_stylesheet_safe(new_rgb))
                return choose
            
            btn.clicked.connect(make_color_callback(key, btn))
            item_layout.addWidget(btn)
            item_layout.addStretch()
            
            self.ui_elements["color_buttons"][key] = btn
            colors_grid.addLayout(item_layout, row, col)
        
        right_side.addLayout(colors_grid)
        right_side.addStretch()
        
        bhop_main.addLayout(left_side, 1)
        bhop_main.addLayout(right_side, 1)
        main_layout.addWidget(bhop_group)

        # ===== ROW 3: Misc Features & Team List =====
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        
        # Miscellaneous Features
        misc_group = self.create_group_box("Miscellaneous")
        misc_layout = QVBoxLayout(misc_group)
        misc_layout.setSpacing(3)
        
        self.add_checkbox(misc_layout, "Watermark", "watermark_enabled", default=True)
        self.add_checkbox(misc_layout, "Spectator List", "spectator_list_enabled")
        self.add_checkbox(misc_layout, "Drawing FPS", "show_overlay_fps")
        self.add_checkbox(misc_layout, "Map Status", "show_map_status_box")
        self.add_checkbox(misc_layout, "WalkBot", "walkbot_enabled",
                          thread_start=start_walkbot_thread, thread_stop=stop_walkbot_thread)
        self.add_checkbox(misc_layout, "Grenade Prediction", "grenade_prediction_enabled")
        self.add_checkbox(misc_layout, "No Flash", "noflash_enabled")
        misc_layout.addStretch()
        
        # Team List Section
        team_group = self.create_group_box("Team List")
        team_layout = QVBoxLayout(team_group)
        team_layout.setSpacing(3)
        
        self.add_checkbox(team_layout, "Enable Team List", "team_list_enabled", default=True)
        self.add_checkbox(team_layout, "HP Bars", "team_list_show_hp_bars", default=True)
        self.add_checkbox(team_layout, "Alive Counts", "team_list_show_counts", default=True)
        self.add_checkbox(team_layout, "Sort by HP", "team_list_sort_by_hp", default=True)
        
        # Font slider
        font_box = QHBoxLayout()
        self.team_list_font_label = QLabel(f"Size: {getattr(Config, 'team_list_font_size', 11)}")
        self.team_list_font_label.setStyleSheet("color: #000000; font-size: 8pt;")
        self.team_list_font_slider = NoScrollSlider(Qt.Horizontal)
        self.team_list_font_slider.setRange(8, 16)
        self.team_list_font_slider.setValue(getattr(Config, 'team_list_font_size', 11))
        self.team_list_font_slider.valueChanged.connect(self.update_team_list_font)
        font_box.addWidget(self.team_list_font_label)
        font_box.addWidget(self.team_list_font_slider)
        team_layout.addLayout(font_box)
        team_layout.addStretch()
        
        row3.addWidget(misc_group, 1)
        row3.addWidget(team_group, 1)
        main_layout.addLayout(row3)

        # ===== ROW 4: Team List Colors =====
        colors_group = self.create_group_box("Team List Colors")
        colors_layout = QVBoxLayout(colors_group)
        colors_grid = QGridLayout()
        colors_grid.setSpacing(6)
        
        team_color_items = [
            ("T Header", "color_box_t", (255, 180, 0)),
            ("CT Header", "color_box_ct", (100, 200, 255)),
            ("Background", "team_list_background", (18, 18, 22)),
            ("Border", "team_list_border", (70, 75, 85)),
            ("Dead T", "team_list_dead_t", (100, 80, 60)),
            ("Dead CT", "team_list_dead_ct", (60, 80, 100)),
        ]
        
        for idx, (label, key, default) in enumerate(team_color_items):
            row = idx // 3
            col = idx % 3
            
            item_layout = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #000000; font-size: 8pt;")
            lbl.setFixedWidth(70)
            item_layout.addWidget(lbl)
            
            rgb = self._sanitize_rgb3(getattr(Config, key, default))
            btn = QPushButton()
            btn.setFixedSize(30, 16)
            btn.setStyleSheet(self.rgb_to_stylesheet_safe(rgb))
            
            def make_team_color_callback(cfg_key, button, default_val):
                def choose():
                    current = self._sanitize_rgb3(getattr(Config, cfg_key, default_val))
                    initial = QColor(*current)
                    color = QColorDialog.getColor(initial, self, f"Select {cfg_key}")
                    if color.isValid():
                        new_rgb = (color.red(), color.green(), color.blue())
                        setattr(Config, cfg_key, new_rgb)
                        button.setStyleSheet(self.rgb_to_stylesheet_safe(new_rgb))
                return choose
            
            btn.clicked.connect(make_team_color_callback(key, btn, default))
            item_layout.addWidget(btn)
            item_layout.addStretch()
            
            self.ui_elements["color_buttons"][key] = btn
            colors_grid.addLayout(item_layout, row, col)
        
        colors_layout.addLayout(colors_grid)
        main_layout.addWidget(colors_group)

        # ===== ROW 5: System Controls =====
        system_group = self.create_group_box("System Controls")
        system_layout = QHBoxLayout(system_group)
        system_layout.setSpacing(12)
        
        # Left: Offsets
        left_system = QVBoxLayout()
        offsets_label = QLabel("Offsets")
        offsets_label.setStyleSheet("font-weight: bold; font-size: 8pt; color: #000000;")
        left_system.addWidget(offsets_label)
        
        self.update_offsets_btn = QPushButton("Update Offsets")
        self.update_offsets_btn.setFixedHeight(20)
        self.update_offsets_btn.setToolTip("Run Process/offset_update.py")
        self.update_offsets_btn.clicked.connect(self.update_offsets)
        left_system.addWidget(self.update_offsets_btn)
        left_system.addStretch()
        
        # Right: Toggle Key
        right_system = QVBoxLayout()
        toggle_label = QLabel("Menu Toggle")
        toggle_label.setStyleSheet("font-weight: bold; font-size: 8pt; color: #000000;")
        right_system.addWidget(toggle_label)
        
        self.toggle_key_label = QLabel(f"Key: {cfg.toggle_menu_key}")
        self.toggle_key_label.setStyleSheet("color: #000000; font-size: 8pt;")
        right_system.addWidget(self.toggle_key_label)
        
        toggle_btn = QPushButton("Set Key")
        toggle_btn.setFixedHeight(20)
        toggle_btn.clicked.connect(self.set_toggle_key)
        right_system.addWidget(toggle_btn)
        right_system.addStretch()
        
        system_layout.addLayout(left_system, 1)
        system_layout.addLayout(right_system, 1)
        main_layout.addWidget(system_group)

        main_layout.addStretch()

        scroll.setWidget(content_widget)
        final_layout = QVBoxLayout(self)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addWidget(scroll)

    def update_offsets(self):
        try:
            self.update_offsets_btn.setEnabled(False)
            self.update_offsets_btn.setText("Updating...")

            process = subprocess.Popen(
                [sys.executable, "Process/offset_update.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                QMessageBox.information(
                    self,
                    "Offsets Updated",
                    "Offsets updated. Restarting GFusion..."
                )
                python = sys.executable
                os.execl(python, python, *sys.argv)
            else:
                QMessageBox.critical(
                    self,
                    "Offset Update Failed",
                    f"Error updating offsets:\n\nExit Code: {process.returncode}\n{stderr[:500]}"
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Offset Update Error",
                f"Failed to run offset update:\n\n{e}"
            )
        finally:
            self.update_offsets_btn.setEnabled(True)
            self.update_offsets_btn.setText("Update Offsets")

    # ---------- Event Handlers ----------
    def update_fov(self, value):
        cfg.game_fov = value
        self.fov_label.setText(f"Game FOV: {value}")
    
    def update_team_list_font(self, value):
        Config.team_list_font_size = value
        self.team_list_font_label.setText(f"Size: {value}")

    def set_toggle_key(self):
        self.toggle_key_label.setText("Press a key...")
        self.listener_thread = KeyListenerThread()
        self.listener_thread.key_pressed.connect(self.update_toggle_key)
        self.listener_thread.start()

    def update_toggle_key(self, key):
        cfg.toggle_menu_key = key
        self.toggle_key_label.setText(f"Key: {key}")

    def refresh_ui(self):
        """Refresh checkboxes, sliders, and button colors (safely)."""
        self.fov_checkbox.setChecked(getattr(cfg, "fov_changer_enabled", True))
        self.fov_slider.setValue(cfg.game_fov)
        self.fov_label.setText(f"Game FOV: {cfg.game_fov}")

        for key, btn in self.ui_elements.get("color_buttons", {}).items():
            rgb = self._sanitize_rgb3(getattr(Config, key, (0, 0, 0)))
            btn.setStyleSheet(self.rgb_to_stylesheet_safe(rgb))

class AimbotTab(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = {"checkboxes": {}, "sliders": {}, "combos": {}, "labels": {}}
        self.init_ui()

    # ---------- Local helpers (match Misc/ESP look) ----------
    def create_group_box(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet("""
            QGroupBox {
                background: #C0C0C0;
                border-top: 1px solid #FFFFFF;
                border-left: 1px solid #FFFFFF;
                border-right: 1px solid #404040;
                border-bottom: 1px solid #404040;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 8pt;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background: #C0C0C0;
            }
        """)
        return g

    def add_checkbox(self, layout, label, cfg_key, on_toggle=None):
        cb = CheatCheckBox(label)
        cb.setChecked(bool(getattr(Config, cfg_key, False)))
        def handler(st):
            enabled = (st == Qt.Checked)
            setattr(Config, cfg_key, enabled)
            if on_toggle:
                try: on_toggle(enabled)
                except Exception as e: print(f"[AimbotTab] toggle {cfg_key} error: {e}")
        cb.stateChanged.connect(handler)
        layout.addWidget(cb)
        self.ui["checkboxes"][cfg_key] = cb
        return cb

    def add_combo_row(self, layout, label, options, cfg_key, to_lower=True, width=100):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #000000; font-size: 8pt;")
        row.addWidget(lbl)
        combo = CheatComboBox(items=options, width=width)
        cur = getattr(Config, cfg_key, options[0])
        if to_lower: cur = str(cur).lower()
        idx = combo.findText(cur)
        if idx >= 0: combo.setCurrentIndex(idx)
        def on_sel(v):
            setattr(Config, cfg_key, v.lower() if to_lower else v)
        combo.currentTextChanged.connect(on_sel)
        row.addWidget(combo); row.addStretch()
        layout.addLayout(row)
        self.ui["combos"][cfg_key] = combo
        return combo

    def add_float_slider(self, layout, label, cfg_key, min_v, max_v, step_mult):
        val = float(getattr(Config, cfg_key, min_v))
        lab = QLabel(f"{label}: {val:.2f}")
        lab.setStyleSheet("color: #000000; font-size: 8pt;")
        sld = NoScrollSlider(Qt.Horizontal)
        sld.setMinimum(int(min_v*step_mult)); sld.setMaximum(int(max_v*step_mult))
        sld.setValue(int(val*step_mult))
        def on_change(v):
            real = v / float(step_mult)
            setattr(Config, cfg_key, real)
            lab.setText(f"{label}: {real:.2f}")
        sld.valueChanged.connect(on_change)
        layout.addWidget(lab); layout.addWidget(sld)
        self.ui["sliders"][cfg_key] = (sld, lab, step_mult)
        return sld, lab

    def add_int_slider(self, layout, label, cfg_key, min_v, max_v):
        val = int(getattr(Config, cfg_key, min_v))
        lab = QLabel(f"{label}: {val}")
        lab.setStyleSheet("color: #000000; font-size: 8pt;")
        sld = NoScrollSlider(Qt.Horizontal)
        sld.setMinimum(min_v); sld.setMaximum(max_v); sld.setValue(val)
        def on_change(v):
            setattr(Config, cfg_key, int(v))
            lab.setText(f"{label}: {int(v)}")
        sld.valueChanged.connect(on_change)
        layout.addWidget(lab); layout.addWidget(sld)
        self.ui["sliders"][cfg_key] = (sld, lab, 1)
        return sld, lab

    def _section_title(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; font-size: 9pt; color: #000000;")
        return lbl

    # ---------- UI ----------
    def init_ui(self):
        # scroll container (same pattern as other tabs)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: #C0C0C0; border: none; }")

        content = QWidget(); content.setStyleSheet("background: #C0C0C0;")
        root = QVBoxLayout(content)
        root.setSpacing(8); root.setContentsMargins(8, 8, 8, 8)

        # ===== Main controls =====
        main_g = self.create_group_box("Main")
        main = QHBoxLayout(main_g); main.setSpacing(10)

        # aimbot + dm
        col_left = QVBoxLayout(); col_left.setSpacing(4)
        self.add_checkbox(col_left, "Enable Aimbot", "enabled",
                          on_toggle=lambda en: (start_aimbot_thread() if en else stop_aimbot_thread()))
        self.add_checkbox(col_left, "DeathMatch Mode", "DeathMatch")
        main.addLayout(col_left, 1)

        # auto pistol cluster + key + fire rate
        col_mid = QVBoxLayout(); col_mid.setSpacing(6)
        self.auto_pistol_cb = self.add_checkbox(
            col_mid, "Auto Pistol", "auto_pistol_enabled",
            on_toggle=lambda en: (start_auto_pistol_thread() if en else stop_auto_pistol_thread())
        )
        # activation key
        self.add_combo_row(col_mid, "Auto Pistol Key:",
                           ["mouse2","mouse3","mouse4","mouse5","alt","ctrl","shift","space"],
                           "activation_key", to_lower=True, width=90)
        # fire rate
        fr_box = QVBoxLayout()
        self.fr_slider, self.fr_label_holder = self.add_float_slider(
            fr_box, "Fire Rate (s)", "fire_rate", 0.01, 1.00, 100
        )
        col_mid.addLayout(fr_box)
        main.addLayout(col_mid, 1)

        # general toggles
        col_right = QVBoxLayout(); col_right.setSpacing(6)
        self.add_checkbox(col_right, "Visible-check Aim", "visibility_aim_enabled")
        self.add_checkbox(col_right, "Closest to Crosshair", "closest_to_crosshair")
        main.addLayout(col_right, 1)

        root.addWidget(main_g)

        # ===== FOV overlay circle =====
        fov_g = self.create_group_box("FOV Overlay")
        fov = QVBoxLayout(fov_g); fov.setSpacing(6)
        row = QHBoxLayout()
        self.add_checkbox(row, "Show FOV Circle", "fov_circle_enabled")
        row.addStretch(1)
        fov.addLayout(row)
        root.addWidget(fov_g)

        # ===== Kernel Mode =====
        kern_g = self.create_group_box("Kernel Mode (NeacController)")
        kern = QVBoxLayout(kern_g); kern.setSpacing(6)

        row1 = QHBoxLayout()
        self.kernel_cb = self.add_checkbox(row1, "Enable Kernel Mode", "kernel_mode_enabled",
                                           on_toggle=self._toggle_kernel_mode)
        self.kernel_auto = self.add_checkbox(row1, "Auto-start Driver", "kernel_driver_auto_start")
        self.kernel_fallback = self.add_checkbox(row1, "Fallback to Usermode", "kernel_fallback_to_usermode")
        row1.addStretch(1)
        kern.addLayout(row1)

        self.kernel_status = QLabel("Status: Disabled")
        self.kernel_status.setStyleSheet("color: #888; font-size: 9pt; font-style: italic;")
        kern.addWidget(self.kernel_status)
        root.addWidget(kern_g)

        # ===== Precision / RCS / Timing =====
        prec_g = self.create_group_box("Precision & Timing")
        prec = QGridLayout(prec_g); prec.setHorizontalSpacing(12); prec.setVerticalSpacing(6)

        def add_float_cell(r,c, lbl, key, mn, mx, mult):
            box = QVBoxLayout()
            sld, lab = self.add_float_slider(box, lbl, key, mn, mx, mult)
            w = QWidget(); w.setLayout(box); prec.addWidget(w, r, c)
            return sld, lab

        add_float_cell(0,0, "FOV", "FOV", 0.1, 30.0, 10)
        add_float_cell(0,1, "Aim Start Delay", "aim_start_delay", 0.00, 1.00, 100)
        add_float_cell(0,2, "RCS Scale", "rcs_scale", 0.00, 5.00, 100)
        add_float_cell(0,3, "Smooth Base", "smooth_base", 0.00, 1.00, 100)
        add_float_cell(0,4, "Smooth Variance", "smooth_var", 0.00, 1.00, 100)

        add_float_cell(1,0, "Velocity Pred. Factor", "velocity_prediction_factor", 0.00, 1.00, 100)
        add_float_cell(1,1, "Target Switch Delay", "target_switch_delay", 0.00, 1.00, 100)
        add_float_cell(1,2, "RCS Smooth Base", "rcs_smooth_base", 0.00, 1.00, 100)
        add_float_cell(1,3, "RCS Smooth Var", "rcs_smooth_var", 0.00, 1.00, 100)
        add_float_cell(1,4, "RCS Grace After Damage", "rcs_grace_after_damage", 0.00, 1.00, 100)

        root.addWidget(prec_g)

        # ===== Numeric caps =====
        nums_g = self.create_group_box("Numeric Caps")
        nums = QGridLayout(nums_g); nums.setHorizontalSpacing(12); nums.setVerticalSpacing(6)
        def add_int_cell(r,c,lbl,key,mn,mx):
            box = QVBoxLayout()
            sld, lab = self.add_int_slider(box, lbl, key, mn, mx)
            w = QWidget(); w.setLayout(box); nums.addWidget(w, r, c)
            return sld, lab
        add_int_cell(0,0,"Downward Offset","downward_offset",0,100)
        add_int_cell(0,1,"Max Entities","max_entities",1,128)
        add_int_cell(0,2,"Max Mouse Move","max_mouse_move",1,50)
        add_int_cell(0,3,"Max Delta Angle","max_delta_angle",1,180)
        root.addWidget(nums_g)

        # ===== Input & Sensitivity =====
        input_g = self.create_group_box("Input")
        inp = QVBoxLayout(input_g); inp.setSpacing(6)
        self.add_combo_row(inp, "Aim Activation Key:",
                           ["mouse1","mouse2","mouse3","mouse4","mouse5",
                            "left_shift","right_shift","left_ctrl","right_ctrl",
                            "left_alt","right_alt","space"],
                           "aim_key", to_lower=True, width=110)

        # sensitivity + invert y
        sens_row = QHBoxLayout()
        self.sens_label = QLabel(f"Sensitivity: {getattr(Config,'sensitivity',0.1):.3f}")
        self.sens_label.setStyleSheet("color:#000000; font-size:8pt;")
        sens_row.addWidget(self.sens_label)

        self.sens_slider = NoScrollSlider(Qt.Horizontal)
        self.sens_slider.setMinimum(8); self.sens_slider.setMaximum(1000)
        # slider inverted mapping used in existing code
        s_val = max(0.008, min(1.0, float(getattr(Config, "sensitivity", 0.1))))
        self.sens_slider.setValue(1000 - int(s_val * 1000) + 8)

        def on_sens(v):
            real = max(0.008, min(1.0, (1000 - v + 8)/1000.0))
            setattr(Config, "sensitivity", real)
            self.sens_label.setText(f"Sensitivity: {real:.3f}")
        self.sens_slider.valueChanged.connect(on_sens)
        sens_row.addWidget(self.sens_slider)

        self.invert_y = CheatCheckBox("Invert Y")
        self.invert_y.setChecked(int(getattr(Config, "invert_y", 1)) == -1)
        self.invert_y.stateChanged.connect(lambda st: setattr(Config, "invert_y", -1 if st == Qt.Checked else 1))
        sens_row.addWidget(self.invert_y)
        sens_row.addStretch(1)
        inp.addLayout(sens_row)

        root.addWidget(input_g)

        # ===== Targeting =====
        tgt_g = self.create_group_box("Target")
        tgt = QVBoxLayout(tgt_g); tgt.setSpacing(6)
        self.add_combo_row(tgt, "Target Bone:", ["head","chest"], "target_bone_name", to_lower=True, width=90)
        self.learn_dir_label = QLabel(f"Learning Dir: {getattr(Config,'learn_dir','')}")
        self.learn_dir_label.setStyleSheet("color:#000000; font-size:8pt;")
        tgt.addWidget(self.learn_dir_label)
        root.addWidget(tgt_g)

        # ===== Humanization (Anti-Detection) =====
        human_g = self.create_group_box("Humanization (Anti-Detection)")
        human = QVBoxLayout(human_g); human.setSpacing(6)

        row_h1 = QHBoxLayout()
        self.add_checkbox(row_h1, "Enable Humanization", "humanization_enabled")
        self.add_checkbox(row_h1, "Aim Jitter/Shake", "aim_jitter_enabled")
        self.add_checkbox(row_h1, "Randomize Smoothness", "smooth_randomization")
        self.add_checkbox(row_h1, "Reaction Delay", "reaction_delay_enabled")
        self.add_checkbox(row_h1, "Occasional Overshoot", "overshoot_enabled")
        row_h1.addStretch(1)
        human.addLayout(row_h1)

        # jitter controls
        jitter_box = QHBoxLayout()
        j_col = QVBoxLayout()
        self.add_float_slider(j_col, "Jitter Amount", "aim_jitter_amount", 0.00, 1.00, 100)
        jitter_box.addLayout(j_col)

        jf_col = QVBoxLayout()
        sld, lab = self.add_float_slider(jf_col, "Shake Frequency (Hz)", "aim_shake_frequency", 1.0, 20.0, 1)
        # clamp integer for display
        sld.valueChanged.connect(lambda v: lab.setText(f"Shake Frequency (Hz): {float(v):.1f}"))
        jitter_box.addLayout(jf_col)
        jitter_box.addStretch(1)
        human.addLayout(jitter_box)

        # reaction delay range
        delay_box = QVBoxLayout()
        self.add_float_slider(delay_box, "Delay Min (s)", "reaction_delay_min", 0.001, 0.200, 1000)
        self.add_float_slider(delay_box, "Delay Max (s)", "reaction_delay_max", 0.010, 0.300, 1000)
        human.addLayout(delay_box)

        # overshoot params
        overshoot_box = QVBoxLayout()
        self.add_float_slider(overshoot_box, "Overshoot Chance", "overshoot_chance", 0.00, 0.50, 100)
        self.add_float_slider(overshoot_box, "Overshoot Amount (x)", "overshoot_amount", 1.00, 2.00, 100)
        human.addLayout(overshoot_box)

        root.addWidget(human_g)

        root.addStretch()
        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)

        # initial kernel status check (deferred)
        QTimer.singleShot(300, self._check_kernel_status_delayed)

    # ---------- Kernel handling ----------
    def _toggle_kernel_mode(self, enabled: bool):
        # UI feedback immediately
        self.kernel_status.setText("Status: Initializing..." if enabled else "Status: Disabled")
        self.kernel_status.setStyleSheet("color: #ff8800; font-size: 9pt; font-style: italic;" if enabled
                                         else "color: #888; font-size: 9pt; font-style: italic;")
        # reuse your background init logic from current implementation
        try:
            import threading
            def init_kernel():
                try:
                    import sys, os
                    controller_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                                   'NeacController-main', 'NeacController')
                    if controller_path not in sys.path:
                        sys.path.insert(0, controller_path)
                    import neac_controller
                    m = neac_controller.NeacDriverManager()
                    if enabled:
                        if m.start_driver() and m.connect():
                            self.kernel_status.setText("Status: ✓ Kernel mode active")
                            self.kernel_status.setStyleSheet("color: #00ff00; font-size: 9pt; font-style: italic;")
                            try: m.disconnect()
                            except: pass
                        else:
                            self.kernel_status.setText("Status: ✗ Driver error")
                            self.kernel_status.setStyleSheet("color: #ff0000; font-size: 9pt; font-style: italic;")
                            try: m.stop_driver()
                            except: pass
                    else:
                        try: m.stop_driver()
                        except: pass
                except ImportError:
                    self.kernel_status.setText("Status: ✗ NeacController not found")
                    self.kernel_status.setStyleSheet("color: #ff0000; font-size: 9pt; font-style: italic;")
                except Exception as e:
                    self.kernel_status.setText(f"Status: ✗ Error: {str(e)[:30]}...")
                    self.kernel_status.setStyleSheet("color: #ff0000; font-size: 9pt; font-style: italic;")
            threading.Thread(target=init_kernel, daemon=True).start()
        except Exception as e:
            print(f"[AimbotTab] Kernel toggle error: {e}")

    def _check_kernel_status_delayed(self):
        # Mirrors your delayed status check style
        try:
            if hasattr(Config, "_kernel_active_instances") and Config._kernel_active_instances > 0:
                self.kernel_status.setText("Status: ✓ Kernel mode active")
                self.kernel_status.setStyleSheet("color: #00ff00; font-size: 9pt; font-style: italic;")
        except Exception as e:
            print(f"[AimbotTab] Kernel delayed check error: {e}")

    # ---------- Sync ----------
    def refresh_ui(self):
        try:
            # checkboxes
            for key, cb in self.ui["checkboxes"].items():
                cb.setChecked(bool(getattr(Config, key, False)))

            # combos
            for key, combo in self.ui["combos"].items():
                val = str(getattr(Config, key, combo.currentText()))
                idx = combo.findText(val.lower())
                if idx >= 0: combo.setCurrentIndex(idx)

            # sliders
            for key, (sld, lab, mult) in self.ui["sliders"].items():
                val = getattr(Config, key, None)
                if val is None: continue
                if mult == 1:
                    sld.setValue(int(val)); lab.setText(f"{lab.text().split(':',1)[0]}: {int(val)}")
                else:
                    sld.setValue(int(float(val) * mult))
                    lab.setText(f"{lab.text().split(':',1)[0]}: {float(val):.2f}")

            # special labels
            if hasattr(self, "sens_label"):
                self.sens_label.setText(f"Sensitivity: {getattr(Config,'sensitivity',0.1):.3f}")
            if hasattr(self, "learn_dir_label"):
                self.learn_dir_label.setText(f"Learning Dir: {getattr(Config,'learn_dir','')}")
        except Exception as e:
            print(f"[AimbotTab] refresh_ui error: {e}")


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
    def create_group_box(self, title: str) -> QGroupBox:
        """Create a Win95-style group box"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                background: #C0C0C0;
                border-top: 1px solid #FFFFFF;
                border-left: 1px solid #FFFFFF;
                border-right: 1px solid #404040;
                border-bottom: 1px solid #404040;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 8pt;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background: #C0C0C0;
            }
        """)
        return group

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

    def add_combobox(self, layout, label, options, cfg_key):
        hbox = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #000000; font-size: 8pt;")
        hbox.addWidget(lbl)
        
        combo = CheatComboBox(items=options, width=100)
        current = getattr(Config, cfg_key, options[0]).lower()
        idx = combo.findText(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentTextChanged.connect(lambda v: setattr(Config, cfg_key, v.lower()))
        hbox.addWidget(combo)
        hbox.addStretch()
        
        layout.addLayout(hbox)
        self.ui_elements["comboboxes"][cfg_key] = combo
        return combo

    def add_slider(self, layout, label, cfg_key, min_val, max_val):
        val = getattr(Config, cfg_key, min_val)
        lbl = QLabel(f"{label}: {val}")
        lbl.setStyleSheet("color: #000000; font-size: 8pt;")
        
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

    def add_color_picker_to_grid(self, grid, row, col, label, cfg_key, default=(255, 255, 255)):
        rgb = getattr(Config, cfg_key, default)
        
        item_layout = QHBoxLayout()
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet("color: #000000; font-size: 8pt;")
        lbl.setFixedWidth(100)
        item_layout.addWidget(lbl)
        
        btn = QPushButton()
        btn.setFixedSize(30, 16)
        btn.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")

        def choose():
            initial = QColor(*rgb)
            new = QColorDialog.getColor(initial, self, f"Select {label} Color")
            if new.isValid():
                new_rgb = (new.red(), new.green(), new.blue())
                setattr(Config, cfg_key, new_rgb)
                btn.setStyleSheet(f"background-color: rgb{new_rgb}; border: 1px solid black;")

        btn.clicked.connect(choose)
        item_layout.addWidget(btn)
        item_layout.addStretch()
        
        cont = QWidget()
        cont.setLayout(item_layout)
        grid.addWidget(cont, row, col)

        self.ui_elements["color_buttons"][cfg_key] = btn
        return btn

    # ----------------- UI -----------------
    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: #C0C0C0; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: #C0C0C0;")
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- Team Filter & Panic ---
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
        # Team Filter
        team_group = self.create_group_box("Team Filter")
        team_layout = QVBoxLayout(team_group)
        team_layout.setSpacing(3)
        self.add_checkbox(team_layout, "Enemy Only", "esp_show_enemies_only")
        self.add_checkbox(team_layout, "Team Only", "esp_show_team_only")
        team_layout.addStretch()
        
        # Panic Settings
        panic_group = self.create_group_box("Panic Settings")
        panic_layout = QVBoxLayout(panic_group)
        panic_layout.setSpacing(3)
        
        panic_lbl = QLabel(f"Key: {vk_to_name(getattr(Config, 'panic_key', 0x7B))}")
        panic_lbl.setStyleSheet("color: #000000; font-size: 8pt;")
        panic_layout.addWidget(panic_lbl)
        
        panic_btn = QPushButton("Set Panic Key")
        panic_btn.setFixedHeight(20)
        
        def set_panic():
            panic_btn.setText("Press a key...")
            self.listener_thread = KeyListenerThread()
            self.listener_thread.key_pressed.connect(lambda key: self.update_panic_key(key, panic_lbl, panic_btn))
            self.listener_thread.start()

        panic_btn.clicked.connect(set_panic)
        panic_layout.addWidget(panic_btn)
        panic_layout.addStretch()
        
        self.ui_elements["labels"]["panic_key"] = panic_lbl
        
        row1.addWidget(team_group, 1)
        row1.addWidget(panic_group, 1)
        layout.addLayout(row1)

        # --- Basic ESP Features ---
        basic_group = self.create_group_box("Basic ESP Features")
        basic_layout = QVBoxLayout(basic_group)
        basic_layout.setSpacing(3)
        
        basic_grid = QGridLayout()
        basic_grid.setSpacing(4)
        features = [
            ("Hide from Capture", "obs_protection_enabled"),
            ("Visible Only", "visible_only_esp_enabled"),
            ("Box ESP", "show_box_esp"),
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
        
        basic_layout.addLayout(basic_grid)
        self.add_combobox(basic_layout, "Box Style:", ["normal", "rounded", "corner"], "box_esp_style")
        basic_layout.addStretch()
        layout.addWidget(basic_group)

        # --- Renderer & Visibility ---
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        
        # Renderer
        render_group = self.create_group_box("Overlay Renderer")
        render_layout = QVBoxLayout(render_group)
        render_layout.setSpacing(3)
        self.add_checkbox(render_layout, "Use GPU (DX11)", "use_gpu_overlay")
        render_layout.addStretch()
        
        # Visibility
        vis_group = self.create_group_box("Visibility ESP")
        vis_layout = QVBoxLayout(vis_group)
        vis_layout.setSpacing(3)
        self.add_checkbox(vis_layout, "Enable Visibility", "visibility_esp_enabled")
        self.add_checkbox(vis_layout, "Show Vis Text", "visibility_text_enabled")
        vis_layout.addStretch()
        
        row2.addWidget(render_group, 1)
        row2.addWidget(vis_group, 1)
        layout.addLayout(row2)

        # --- Advanced ESP Features ---
        adv_group = self.create_group_box("Advanced ESP Features")
        adv_layout = QVBoxLayout(adv_group)
        adv_layout.setSpacing(3)
        
        adv_grid = QGridLayout()
        adv_grid.setSpacing(4)
        adv_features = [
            ("Dead Players", "draw_dead_entities"),
            ("Flash ESP", "flash_esp_enabled"),
            ("Scope ESP", "scope_esp_enabled"),
            ("Head ESP", "head_esp_enabled"),
            ("Skeleton ESP", "skeleton_esp_enabled"),
            ("Bomb ESP", "bomb_esp_enabled"),
            ("Money ESP", "money_esp_enabled"),
            ("Velocity ESP", "velocity_esp"),
            ("Velocity Text", "velocity_esp_text"),
            ("Speed ESP", "speed_esp"),
            ("Coordinates", "coordinates_esp_enabled"),
            ("Trace ESP", "trace_esp_enabled"),
        ]
        for i, (label, attr) in enumerate(adv_features):
            self.add_checkbox_to_grid(adv_grid, i // 3, i % 3, label, attr)
        
        adv_layout.addLayout(adv_grid)
        self.add_slider(adv_layout, "Max Trace Points", "trace_esp_max_points", 10, 500)
        adv_layout.addStretch()
        layout.addWidget(adv_group)

        # --- Crosshair & Line ESP ---
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        
        # Crosshair
        cross_group = self.create_group_box("Crosshair")
        cross_layout = QVBoxLayout(cross_group)
        cross_layout.setSpacing(3)
        self.add_checkbox(cross_layout, "Enable Crosshair", "draw_crosshair_enabled")
        self.add_slider(cross_layout, "Size", "crosshair_size", 1, 20)
        cross_layout.addStretch()
        
        # Line ESP
        line_group = self.create_group_box("Line ESP")
        line_layout = QVBoxLayout(line_group)
        line_layout.setSpacing(3)
        self.add_checkbox(line_layout, "Enable Line ESP", "line_esp_enabled")
        self.add_combobox(line_layout, "Position:", ["top", "bottom"], "line_esp_position")
        line_layout.addStretch()
        
        row3.addWidget(cross_group, 1)
        row3.addWidget(line_group, 1)
        layout.addLayout(row3)

        # --- Bone Dot & Sizes ---
        row4 = QHBoxLayout()
        row4.setSpacing(8)
        
        # Bone Dot
        bone_group = self.create_group_box("Bone Dot ESP")
        bone_layout = QVBoxLayout(bone_group)
        bone_layout.setSpacing(3)
        self.add_checkbox(bone_layout, "Enable Bone Dots", "bone_dot_esp_enabled")
        self.add_slider(bone_layout, "Dot Size", "bone_dot_size", 1, 20)
        bone_layout.addStretch()
        
        # Size Settings
        size_group = self.create_group_box("Size Settings")
        size_layout = QVBoxLayout(size_group)
        size_layout.setSpacing(3)
        self.add_slider(size_layout, "Head ESP Size", "head_esp_size", 1, 50)
        size_layout.addStretch()
        
        row4.addWidget(bone_group, 1)
        row4.addWidget(size_group, 1)
        layout.addLayout(row4)

        # --- Shape Settings ---
        shape_group = self.create_group_box("Shape Settings")
        shape_layout = QHBoxLayout(shape_group)
        shape_layout.setSpacing(8)
        
        shape_left = QVBoxLayout()
        self.add_combobox(shape_left, "Head Shape:", ["circle", "square"], "head_esp_shape")
        shape_left.addStretch()
        
        shape_right = QVBoxLayout()
        self.add_combobox(shape_right, "Bone Shape:", ["circle", "square"], "bone_dot_shape")
        shape_right.addStretch()
        
        shape_layout.addLayout(shape_left, 1)
        shape_layout.addLayout(shape_right, 1)
        layout.addWidget(shape_group)

        # --- ESP Colors ---
        colors_group = self.create_group_box("ESP Colors")
        colors_layout = QVBoxLayout(colors_group)
        colors_layout.setSpacing(3)
        
        color_grid = QGridLayout()
        color_grid.setSpacing(6)
        
        colors = [
            ("Box (T)", "color_box_t", (255, 180, 0)),
            ("Box (CT)", "color_box_ct", (100, 200, 255)),
            ("Bone", "color_bone", (255, 255, 255)),
            ("Head", "color_head", (255, 0, 0)),
            ("Health Bar", "color_healthbar", (0, 255, 0)),
            ("Armor Bar", "color_armorbar", (0, 0, 255)),
            ("Name", "color_name", (255, 255, 255)),
            ("Name FX", "color_name_effects", (255, 255, 255)),
            ("HP Text", "color_hp_text", (0, 255, 0)),
            ("Armor Text", "color_armor_text", (0, 0, 255)),
            ("Distance", "color_distance", (255, 255, 255)),
            ("Flash/Scope", "color_flash_scope", (255, 255, 0)),
            ("Spectators", "color_spectators", (180, 180, 180)),
            ("Bone Dot", "bone_dot_color", (255, 0, 255)),
            ("Weapon", "color_weapon_text", (255, 255, 255)),
            ("Crosshair", "crosshair_color", (255, 255, 255)),
            ("Velocity Text", "velocity_text_color", (255, 255, 255)),
            ("Velocity ESP", "velocity_esp_color", (255, 255, 0)),
            ("Speed ESP", "speed_esp_color", (0, 255, 255)),
            ("Coordinates", "coordinates_esp_color", (255, 255, 255)),
            ("Trace ESP", "trace_esp_color", (255, 0, 255)),
            ("Money", "color_money_text", (0, 255, 255)),
            ("Visible", "color_visible_text", (0, 255, 0)),
            ("Not Visible", "color_not_visible_text", (255, 0, 0)),
            ("Dead CT", "color_dead_ct", (0, 0, 128)),
            ("Dead T", "color_dead_t", (128, 0, 0)),
        ]
        
        for i, (label, attr, default) in enumerate(colors):
            self.add_color_picker_to_grid(color_grid, i // 3, i % 3, label, attr, default)
        
        colors_layout.addLayout(color_grid)
        layout.addWidget(colors_group)

        layout.addStretch()
        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ----------------- Panic Key -----------------
    def update_panic_key(self, key, label, btn):
        vk = key_to_vk(key)
        setattr(Config, "panic_key", vk)
        label.setText(f"Key: {key}")
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
            current = getattr(Config, k, "")
            idx = c.findText(current)
            if idx >= 0:
                c.setCurrentIndex(idx)
        # Colors
        for k, b in self.ui_elements["color_buttons"].items():
            rgb = getattr(Config, k, (255, 255, 255))
            b.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")
        # Panic
        if "panic_key" in self.ui_elements["labels"]:
            vk = getattr(Config, "panic_key", 0x7B)
            self.ui_elements["labels"]["panic_key"].setText(f"Key: {vk_to_name(vk)}")
            
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

# -----------------------------
# RecoilViewer (Win95-styled)
# Drop-in replacement
# -----------------------------
LEARN_DIR = "aimbot_data"

class RecoilViewer(QWidget):
    """
    Win95-styled recoil analyzer:
    - Data Source: choose dir, reload, auto-watch
    - Display: spray vs movement, grid/legend toggles, line/marker tuning
    - Plot: integrated FigureCanvas
    - Stats: scrollable per-dataset + burst summaries
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 600)

        # runtime state
        self.learn_dir = LEARN_DIR
        self.weapon_ids = []
        self.all_data = {}
        self._last_aimbot_plot_hash = None
        self.spray_mode = True    # True = spray path (line), False = movement markers
        self.show_grid = True
        self.show_legend = True
        self.line_width = 1.5
        self.marker_size = 2

        self._init_ui()
        self.scan_aimbot_data()

        # optional watcher thread (provided by your project)
        try:
            self.watcher_thread = DataWatcher()
            self.watcher_thread.data_updated.connect(self._on_data_updated)
            self.watcher_thread.start()
            self._watching = True
        except Exception as e:
            print(f"[RecoilViewer] Watcher not available: {e}")
            self._watching = False

    # ---------- small Win95 helpers ----------
    def _create_group_box(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet("""
            QGroupBox {
                background: #C0C0C0;
                border-top: 1px solid #FFFFFF;
                border-left: 1px solid #FFFFFF;
                border-right: 1px solid #404040;
                border-bottom: 1px solid #404040;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 8pt;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background: #C0C0C0;
            }
        """)
        return g

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#808080; background:#808080;")
        line.setFixedHeight(1)
        return line

    # ---------- UI ----------
    def _init_ui(self):
        # === Scroll container (match other tabs) ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: #C0C0C0; border: none; }")  # same as others

        content = QWidget()
        content.setStyleSheet("background:#C0C0C0;")
        root = QVBoxLayout(content)
        root.setSpacing(8)
        root.setContentsMargins(8, 8, 8, 8)

        # Header (title + status)
        header = QHBoxLayout()
        title = QLabel("Recoil Analyzer")
        title.setStyleSheet("font-weight:bold; font-size:10pt; color:#000000;")
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color:#000000; font-size:8pt;")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)
        root.addLayout(header)

        # Top controls (Data Source + Display) side-by-side
        top = QHBoxLayout()
        top.setSpacing(8)

        # ==== Data Source ====
        src_g = self._create_group_box("Data Source")
        src = QGridLayout(src_g)
        src.setHorizontalSpacing(8)
        src.setVerticalSpacing(6)

        # learn dir row
        src.addWidget(QLabel("Folder:"), 0, 0)
        self.dir_edit = QLineEdit(self.learn_dir)
        self.dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        reload_btn = QPushButton("Reload")
        src.addWidget(self.dir_edit, 0, 1, 1, 2)
        src.addWidget(browse_btn, 0, 3)
        src.addWidget(reload_btn, 0, 4)

        # weapon selector row
        src.addWidget(QLabel("Weapon:"), 1, 0)
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
        src.addWidget(self.dropdown, 1, 1, 1, 4)

        # watcher toggle + export
        self.watch_cb = CheatCheckBox("Auto-Watch")
        self.watch_cb.setChecked(getattr(self, "_watching", False))
        export_btn = QPushButton("Export PNG")
        src.addWidget(self.watch_cb, 2, 1)
        src.addWidget(export_btn, 2, 4)

        top.addWidget(src_g, 3)

        # ==== Display ====
        dsp_g = self._create_group_box("Display")
        dsp = QGridLayout(dsp_g)
        dsp.setHorizontalSpacing(8)
        dsp.setVerticalSpacing(6)

        self.mode_checkbox = CheatCheckBox("Show Spray Path")
        self.mode_checkbox.setChecked(True)
        self.grid_cb = CheatCheckBox("Grid")
        self.grid_cb.setChecked(True)
        self.leg_cb = CheatCheckBox("Legend")
        self.leg_cb.setChecked(True)

        dsp.addWidget(self.mode_checkbox, 0, 0)
        dsp.addWidget(self.grid_cb,     0, 1)
        dsp.addWidget(self.leg_cb,      0, 2)

        # line width
        dsp.addWidget(QLabel("Line W:"), 1, 0)
        self.line_slider = NoScrollSlider(Qt.Horizontal)
        self.line_slider.setMinimum(1)   # 0.1..4.0 (x10)
        self.line_slider.setMaximum(40)
        self.line_slider.setValue(int(self.line_width * 10))
        self.line_label = QLabel(f"{self.line_width:.1f}")
        dsp.addWidget(self.line_slider, 1, 1)
        dsp.addWidget(self.line_label,  1, 2)

        # marker size
        dsp.addWidget(QLabel("Marker:"), 2, 0)
        self.marker_slider = NoScrollSlider(Qt.Horizontal)
        self.marker_slider.setMinimum(1)  # 0.1..5.0 (x10)
        self.marker_slider.setMaximum(50)
        self.marker_slider.setValue(int(self.marker_size * 10))
        self.marker_label = QLabel(f"{self.marker_size:.1f}")
        dsp.addWidget(self.marker_slider, 2, 1)
        dsp.addWidget(self.marker_label,  2, 2)

        top.addWidget(dsp_g, 2)
        root.addLayout(top)

        # ==== Plot + Stats split ====
        split = QHBoxLayout()
        split.setSpacing(8)

        # Plot
        self.canvas = FigureCanvas(Figure(facecolor="#C0C0C0"))
        self.ax = self.canvas.figure.add_subplot(111)
        self._style_axes()
        split.addWidget(self.canvas, 2)

        # Stats (scroll)
        stats_g = self._create_group_box("Stats")
        stats_v = QVBoxLayout(stats_g)
        stats_v.setSpacing(6)
        self.stats_scroll = QScrollArea()
        self.stats_scroll.setWidgetResizable(True)
        self.stats_scroll.setStyleSheet("QScrollArea { background: #E0E0E0; border: 1px solid #000000; }")
        self.stats_widget = QWidget()
        self.stats_layout = QVBoxLayout(self.stats_widget)
        self.stats_layout.setContentsMargins(6, 6, 6, 6)
        self.stats_scroll.setWidget(self.stats_widget)
        stats_v.addWidget(self.stats_scroll)
        split.addWidget(stats_g, 3)

        root.addLayout(split)
        root.addStretch(1)

        # put content into scroll, then mount
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # ---------- wiring ----------
        self.dropdown.currentTextChanged.connect(self.update_view)
        self.mode_checkbox.stateChanged.connect(self._toggle_mode)
        self.grid_cb.stateChanged.connect(self._toggle_grid)
        self.leg_cb.stateChanged.connect(self._toggle_legend)
        self.line_slider.valueChanged.connect(self._change_line)
        self.marker_slider.valueChanged.connect(self._change_marker)

        browse_btn.clicked.connect(self._browse_dir)
        reload_btn.clicked.connect(self.scan_aimbot_data)
        export_btn.clicked.connect(self._export_png)
        self.watch_cb.stateChanged.connect(self._toggle_watch)

    # ---------- axis cosmetics ----------
    def _style_axes(self):
        self.ax.clear()
        self.ax.set_facecolor("#C0C0C0")
        self.ax.tick_params(axis="x", colors="black", labelsize=8)
        self.ax.tick_params(axis="y", colors="black", labelsize=8)
        self.ax.set_xlabel("Yaw Δ", color="black")
        self.ax.set_ylabel("Pitch Δ", color="black")

    # ---------- watch events ----------
    def _on_data_updated(self):
        if getattr(self, "_watching", False):
            self.scan_aimbot_data()

    def _toggle_watch(self, st):
        self._watching = (st == Qt.Checked)
        self.status_label.setText(f"Status: {'Watching' if self._watching else 'Idle'}")

    # ---------- display toggles ----------
    def _toggle_mode(self, st):
        self.spray_mode = (st == Qt.Checked)
        self.update_view(self.dropdown.currentText())

    def _toggle_grid(self, st):
        self.show_grid = (st == Qt.Checked)
        self.update_view(self.dropdown.currentText())

    def _toggle_legend(self, st):
        self.show_legend = (st == Qt.Checked)
        self.update_view(self.dropdown.currentText())

    def _change_line(self, v):
        self.line_width = max(0.1, (v / 10.0))
        self.line_label.setText(f"{self.line_width:.1f}")
        self.update_view(self.dropdown.currentText())

    def _change_marker(self, v):
        self.marker_size = max(0.1, (v / 10.0))
        self.marker_label.setText(f"{self.marker_size:.1f}")
        self.update_view(self.dropdown.currentText())

    # ---------- dir ops ----------
    def _browse_dir(self):
        try:
            from PyQt5.QtWidgets import QFileDialog
            path = QFileDialog.getExistingDirectory(self, "Select Aimbot Data Folder", self.learn_dir or "")
            if not path:
                return
            self.learn_dir = path
            self.dir_edit.setText(self.learn_dir)
            self.scan_aimbot_data()
        except Exception as e:
            print(f"[RecoilViewer] browse error: {e}")

    # ---------- export ----------
    def _export_png(self):
        try:
            from PyQt5.QtWidgets import QFileDialog
            wid = self.dropdown.currentText().strip() or "recoil"
            path, _ = QFileDialog.getSaveFileName(self, "Export PNG", f"{wid}.png", "PNG Image (*.png)")
            if not path:
                return
            self.canvas.figure.savefig(path, dpi=150, bbox_inches="tight")
            self.status_label.setText(f"Status: ✓ Exported {os.path.basename(path)}")
        except Exception as e:
            print(f"[RecoilViewer] export error: {e}")
            self.status_label.setText("Status: ✗ Export failed")

    # ---------- data scanning (merge raw_mouse + normal) ----------
    def scan_aimbot_data(self):
        path = self.learn_dir or LEARN_DIR
        if not os.path.exists(path):
            self.weapon_ids = []
            self.all_data = {}
            self.dropdown.clear()
            self._style_axes()
            self.ax.set_title("Trace Map", fontsize=9, color="black")
            self.canvas.draw()
            return

        files = [f for f in os.listdir(path) if f.endswith(".json")]
        new_weapon_ids = set()
        merged_data = {}

        for fname in files:
            wid = fname[:-5]
            full = os.path.join(path, fname)
            if os.path.getsize(full) == 0:
                continue
            try:
                with open(full, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if wid.startswith("raw_mouse_"):
                    base = wid.replace("raw_mouse_", "")
                    new_weapon_ids.add(base)
                    merged_data.setdefault(base, {})
                    merged_data[base]["raw_mouse"] = data if isinstance(data, list) else []
                else:
                    base = wid
                    new_weapon_ids.add(base)
                    merged_data.setdefault(base, {})
                    if isinstance(data, dict):
                        merged_data[base].update(data)
                    elif isinstance(data, list):
                        merged_data[base]["raw_mouse"] = data
                    else:
                        merged_data[base] = {}
            except Exception as e:
                print(f"[RecoilViewer] Error loading {fname}: {e}")

        changed = set(new_weapon_ids) != set(self.weapon_ids)
        self.weapon_ids = sorted(new_weapon_ids)
        self.all_data = merged_data

        self.dropdown.blockSignals(True)
        self.dropdown.clear()
        for wid in self.weapon_ids:
            self.dropdown.addItem(wid)
        self.dropdown.blockSignals(False)

        if self.weapon_ids:
            cur = self.dropdown.currentText()
            if cur in self.weapon_ids:
                self.update_view(cur)
            else:
                self.dropdown.setCurrentText(self.weapon_ids[0])
                self.update_view(self.weapon_ids[0])
        else:
            self._style_axes()
            self.ax.set_title("Trace Map", fontsize=9, color="black")
            self.ax.text(0.5, 0.5, "No data files", ha="center", va="center", color="black")
            self.canvas.draw()

    # ---------- draw / stats ----------
    def update_view(self, weapon_id):
        self._style_axes()
        title = f"Trace Map ({weapon_id})" if weapon_id else "Trace Map"
        self.ax.set_title(title, fontsize=9, color="black")
        if self.show_grid:
            self.ax.grid(True, linestyle="--", color="#808080", alpha=0.6)

        # clear stats panel
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        data = self.all_data.get(weapon_id, {}) if weapon_id else {}
        items = data.items() if isinstance(data, dict) else []

        # rotating palette (contrasty on gray bg)
        colors = ["black", "red", "blue", "green", "purple", "orange", "brown", "teal"]
        color_idx, drew_any = 0, False
        legends = []

        for key, vectors in items:
            if not vectors:
                continue

            x, y = [0.0], [0.0]
            for entry in vectors:
                try:
                    dp, dy = float(entry[0]), float(entry[1])
                except Exception:
                    continue
                x.append(x[-1] + dy)
                y.append(y[-1] + dp)

            if len(x) > 1:
                c = colors[color_idx % len(colors)]
                if self.spray_mode:
                    self.ax.plot(
                        x, y,
                        linewidth=self.line_width,
                        alpha=0.9,
                        marker=".",
                        markersize=self.marker_size,
                        color=c,
                        label=key
                    )
                else:
                    self.ax.plot(
                        x, y,
                        linewidth=max(1.0, self.line_width - 0.5),
                        alpha=0.7,
                        marker="o",
                        markersize=self.marker_size,
                        color=c,
                        label=key
                    )
                legends.append(key)
                drew_any = True

            color_idx += 1

            # stats blocks
            dataset_header = QLabel(f"Dataset: {key}")
            dataset_header.setStyleSheet("font-weight:bold; font-size:9pt; color:#000000; margin-top:6px;")
            self.stats_layout.addWidget(dataset_header)

            self._add_stats_summary(key, vectors)

            bursts = self._split_bursts(vectors)
            if bursts:
                burst_header = QLabel(f"Burst Analysis ({key})")
                burst_header.setStyleSheet("font-weight:bold; font-size:9pt; color:#000000; margin-top:4px;")
                self.stats_layout.addWidget(burst_header)
                for b_idx, burst in enumerate(bursts, 1):
                    self._add_burst_summary(b_idx, burst)

        if drew_any:
            self.ax.relim()
            self.ax.autoscale()
            if self.show_legend and legends:
                self.ax.legend(prop={"size": 8})
        else:
            self.ax.text(0.5, 0.5, "No valid trace data", ha="center", va="center", color="black")

        self.canvas.draw()

    # ---------- stats helpers ----------
    def _add_stats_summary(self, key, vectors):
        dp, dy, distances, bones = [], [], [], []
        for e in vectors:
            if not e:
                continue
            try:
                dp.append(float(e[0])); dy.append(float(e[1]))
                if len(e) > 2: distances.append(float(e[2]))
                if len(e) > 3: bones.append(e[3])
            except Exception:
                continue

        avg_dp = sum(dp)/len(dp) if dp else 0.0
        avg_dy = sum(dy)/len(dy) if dy else 0.0
        avg_dist = sum(distances)/len(distances) if distances else 0.0
        bone_counts = {b: bones.count(b) for b in set(bones)} if bones else {}

        lbl = QLabel(
            f"Samples: {len(vectors)}\n"
            f"Avg ΔPitch={avg_dp:.2f}, Avg ΔYaw={avg_dy:.2f}\n"
            f"Avg Dist={avg_dist:.1f}\n"
            f"Bones: {bone_counts}"
        )
        lbl.setStyleSheet("""
            color:#000000; font-size:8pt; border:1px solid #000000;
            padding:3px; margin:3px 0; background:#FFFFFF;
        """)
        self.stats_layout.addWidget(lbl)

    def _add_burst_summary(self, idx, burst):
        if not burst:
            return
        try:
            dxs, dys = zip(*[(float(b[0]), float(b[1])) for b in burst])
        except Exception:
            return
        avg_dx, avg_dy = (sum(dxs)/len(dxs)), (sum(dys)/len(dys))
        lbl = QLabel(f" Burst {idx}: {len(burst)} shots | Avg ΔPitch={avg_dx:.2f}, ΔYaw={avg_dy:.2f}")
        lbl.setStyleSheet("color:#000000; font-size:8pt; margin-left:8px;")
        self.stats_layout.addWidget(lbl)

    def _split_bursts(self, vectors):
        bursts, current = [], []
        for item in vectors:
            try:
                dp, dy = float(item[0]), float(item[1])
            except Exception:
                dp, dy = 0.0, 0.0
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
    """
    Retro-styled (Win95/Paint) console with:
      - Scrollable log output (timestamped), copy-friendly
      - Command prompt with history (↑/↓) and tab-completion popup
      - Panic button + quick actions row (clear, save log, help)
      - Robust command router:
          help, get/set/toggle/list,
          start/stop (esp, aimbot, triggerbot, glow, bhop, fov, walkbot),
          threads, panic, reload_offsets, restart_features,
          bind/unbind actions, gfx passthrough (to ExecutionTab/ExecFramework if present)
      - Safe, reflective Config access with type coercion
      - Emits refresh_all_tabs() after config mutations
    """
    def __init__(self):
        super().__init__()
        # Cross-tab references
        self.CFG = globals().get("cfg", None) or globals().get("Config", None)
        self.execfw = None  # will try to access ExecutionTab’s framework at runtime
        self.history = []
        self.history_index = -1
        self._known_cmds = set()
        self._build_known_cmds()

        self._init_ui()
        register_tab(self)  # allow refresh_all_tabs() to poke us

        # Periodic discover of ExecFramework (if ExecutionTab loads after us)
        self._discover_timer = QTimer(self)
        self._discover_timer.timeout.connect(self._try_discover_execfw)
        self._discover_timer.start(1000)

    # ---------- UI ----------
    def _create_group_box(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet("""
            QGroupBox {
                background: #C0C0C0;
                border-top: 1px solid #FFFFFF;
                border-left: 1px solid #FFFFFF;
                border-right: 1px solid #404040;
                border-bottom: 1px solid #404040;
                margin-top: 8px;
                padding-top: 8px;
                font-weight: bold;
                font-size: 8pt;
                color: #000000;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background: #C0C0C0;
            }
        """)
        return g

    def _init_ui(self):
        # Scroll shell (match other tabs)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:#C0C0C0; border:none; }")

        content = QWidget(); content.setStyleSheet("background:#C0C0C0;")
        root = QVBoxLayout(content); root.setSpacing(8); root.setContentsMargins(8,8,8,8)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Console")
        title.setStyleSheet("font-weight:bold; font-size:10pt; color:#000;")
        self.status = QLabel("Status: Ready")
        self.status.setStyleSheet("color:#000; font-size:8pt;")
        hdr.addWidget(title); hdr.addStretch(1); hdr.addWidget(self.status)
        root.addLayout(hdr)

        # Output group
        out_g = self._create_group_box("Output")
        out_l = QVBoxLayout(out_g); out_l.setSpacing(6)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet(
            "background:#FFFFFF; color:#000; border:1px solid #000; "
            "font-family:Consolas,monospace; font-size:9pt;"
        )
        out_l.addWidget(self.output)
        root.addWidget(out_g)

        # Quick actions
        qa_g = self._create_group_box("Quick Actions")
        qa = QHBoxLayout(qa_g); qa.setSpacing(8)
        self.panic_btn = QPushButton("PANIC")
        self.panic_btn.setStyleSheet("font-weight:bold;")
        self.panic_btn.clicked.connect(lambda: self._cmd_panic([]))

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(lambda: self.output.clear())
        btn_save = QPushButton("Save Log…")
        btn_save.clicked.connect(self._save_log)
        btn_help = QPushButton("Help")
        btn_help.clicked.connect(lambda: self._handle("help"))
        qa.addWidget(self.panic_btn)
        qa.addWidget(btn_clear)
        qa.addWidget(btn_save)
        qa.addWidget(btn_help)
        qa.addStretch(1)
        root.addWidget(qa_g)

        # Input group
        in_g = self._create_group_box("Command")
        in_l = QVBoxLayout(in_g); in_l.setSpacing(6)

        # Input + completion popup
        row = QHBoxLayout(); row.setSpacing(6)
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Enter command (help for list)…")
        self.input_line.returnPressed.connect(self._on_enter)
        self.input_line.textEdited.connect(self._on_text_edited)
        self.input_line.installEventFilter(self)  # capture Up/Down history
        row.addWidget(self.input_line, 1)

        btn_run = QPushButton("Run")
        btn_run.clicked.connect(self._on_enter)
        row.addWidget(btn_run, 0)
        in_l.addLayout(row)

        # tiny status row
        self.cmd_status = QLabel("Examples: get FOV  |  set FOV 110  |  toggle aimbot_enabled")
        self.cmd_status.setStyleSheet("color:#000; font-size:8pt;")
        in_l.addWidget(self.cmd_status)

        root.addWidget(in_g)

        root.addStretch(1)
        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)

        # Completion popup
        from PyQt5.QtWidgets import QListWidget
        self.completion = QListWidget()
        self.completion.setWindowFlags(self.completion.windowFlags() | Qt.Popup)
        self.completion.itemClicked.connect(self._completion_pick)
        self.completion.setStyleSheet("""
            QListWidget { background:#FFFFFF; color:#000; border:1px solid #000; font-family:Consolas; font-size:9pt; }
            QListWidget::item { padding:2px 6px; }
            QListWidget::item:selected { background:#C0D0FF; }
        """)

        self._log("[OK] Console initialized")

    # ---------- Event filter for history navigation ----------
    def eventFilter(self, obj, ev):
        if obj is self.input_line and ev.type() == ev.KeyPress:
            key = ev.key()
            if key == Qt.Key_Up:
                self._history_prev(); return True
            if key == Qt.Key_Down:
                self._history_next(); return True
            if key == Qt.Key_Tab:
                self._show_completion(); return True
        return super().eventFilter(obj, ev)

    # ---------- History ----------
    def _push_history(self, text: str):
        if text and (len(self.history) == 0 or self.history[-1] != text):
            self.history.append(text)
        self.history_index = len(self.history)

    def _history_prev(self):
        if not self.history: return
        self.history_index = max(0, self.history_index - 1)
        self.input_line.setText(self.history[self.history_index])

    def _history_next(self):
        if not self.history: return
        self.history_index = min(len(self.history), self.history_index + 1)
        if self.history_index == len(self.history):
            self.input_line.clear()
        else:
            self.input_line.setText(self.history[self.history_index])

    # ---------- Completion ----------
    def _build_known_cmds(self):
        base = {
            "help", "get", "set", "toggle", "list",
            "start", "stop", "threads",
            "panic", "reload_offsets", "restart_features",
            "bind", "unbind", "gfx"
        }
        # Add Config attribute names (so completion can offer them)
        try:
            for k in dir(self.CFG):
                if not k.startswith("_"):
                    base.add(k)
        except Exception:
            pass
        self._known_cmds = base

    def _on_text_edited(self, _s):
        # lazy completion refresh only when popup visible
        if self.completion.isVisible():
            self._show_completion()

    def _show_completion(self):
        text = self.input_line.text().strip()
        if not text:
            self.completion.hide(); return
        parts = text.split()
        last = parts[-1] if parts else ""
        if not last:
            self.completion.hide(); return

        cand = [w for w in sorted(self._known_cmds) if w.lower().startswith(last.lower())]
        if not cand:
            self.completion.hide(); return

        self.completion.clear()
        self.completion.addItems(cand[:50])

        # Position under input_line
        p = self.input_line.mapToGlobal(self.input_line.rect().bottomLeft())
        self.completion.move(p)
        self.completion.resize(self.input_line.width(), min(200, 12 + 18*len(cand)))
        self.completion.show()

    def _completion_pick(self, item):
        text = self.input_line.text().strip()
        parts = text.split()
        if parts:
            parts[-1] = item.text()
            self.input_line.setText(" ".join(parts))
        else:
            self.input_line.setText(item.text())
        self.completion.hide()
        self.input_line.setFocus()

    # ---------- ExecFW discovery ----------
    def _try_discover_execfw(self):
        # Look for ExecutionTab instance in TAB_REGISTRY and borrow its ExecFramework
        try:
            for tab in TAB_REGISTRY:
                if tab.__class__.__name__ == "ExecutionTab" and hasattr(tab, "execfw"):
                    self.execfw = tab.execfw
                    self._discover_timer.stop()
                    self._log("[OK] Linked to Execution engine")
                    return
        except Exception as e:
            self._log(f"[WARN] ExecFW discovery: {e}")

    # ---------- Actions ----------
    def _on_enter(self):
        text = self.input_line.text().strip()
        if not text:
            return
        self.input_line.clear()
        self._push_history(text)
        self._handle(text)

    def _save_log(self):
        try:
            from PyQt5.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(self, "Save Console Log", "console.log", "Log (*.log)")
            if not path: return
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.output.toPlainText())
            self._log(f"[OK] Saved: {os.path.basename(path)}")
        except Exception as e:
            self._log(f"[ERR] Save log: {e}")

    # ---------- Logging ----------
    def _log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.output.append(f"[{ts}] {text}")
        self.output.moveCursor(self.output.textCursor().End)

    def _set_status(self, txt: str):
        self.status.setText(f"Status: {txt}")

    # ---------- Router ----------
    def _handle(self, line: str):
        self._log(f"> {line}")
        try:
            parts = line.split()
            if not parts: return
            cmd, args = parts[0].lower(), parts[1:]

            # core
            if cmd == "help":                 return self._cmd_help(args)
            if cmd == "get":                  return self._cmd_get(args)
            if cmd == "set":                  return self._cmd_set(args)
            if cmd == "toggle":               return self._cmd_toggle(args)
            if cmd == "list":                 return self._cmd_list(args)

            if cmd == "start":                return self._cmd_start(args)
            if cmd == "stop":                 return self._cmd_stop(args)
            if cmd == "threads":              return self._cmd_threads(args)

            if cmd == "panic":                return self._cmd_panic(args)
            if cmd == "reload_offsets":       return self._cmd_reload_offsets(args)
            if cmd == "restart_features":     return self._cmd_restart_features(args)

            if cmd == "bind":                 return self._cmd_bind(args)
            if cmd == "unbind":               return self._cmd_unbind(args)

            # optional passthrough to ExecFW (gfx …)
            if cmd == "gfx":
                if self.execfw:
                    return self.execfw.handle(line)
                else:
                    return self._log("[ERR] Exec framework not available (open Execution tab)")

            self._log(f"[ERR] Unknown command '{cmd}'. Type 'help'.")

        except Exception as e:
            self._log(f"[ERR] {e}")

    # ---------- Command impls ----------
    def _cmd_help(self, _):
        help_text = (
            "Commands:\n"
            "  get <key>                       - read a Config value\n"
            "  set <key> <value>               - set a Config value (auto type)\n"
            "  toggle <key>                    - flip boolean Config value\n"
            "  list [prefix]                   - list Config keys (optional startswith)\n"
            "  start|stop <feature>            - aimbot, esp, triggerbot, glow, bhop, fov, walkbot\n"
            "  threads                         - list running feature threads\n"
            "  panic                           - stop all features (panic key)\n"
            "  reload_offsets                  - reload Process.offsets and restart threads\n"
            "  restart_features                - stop and start all feature threads\n"
            "  bind <action> <key>             - set keys (e.g., bind toggle_menu insert)\n"
            "  unbind <action>                 - clear action key\n"
            "  gfx ...                         - forward to Execution gfx (text/line/box/circle)\n"
        )
        for line in help_text.splitlines():
            self._log(line)

    def _cmd_get(self, args):
        if len(args) < 1: return self._log("Usage: get <key>")
        key = args[0]
        if not hasattr(self.CFG, key): return self._log(f"[ERR] No such key '{key}'")
        self._log(f"{key} = {getattr(self.CFG, key)}")

    def _cmd_set(self, args):
        if len(args) < 2: return self._log("Usage: set <key> <value>")
        key, val = args[0], " ".join(args[1:])
        if not hasattr(self.CFG, key): return self._log(f"[ERR] No such key '{key}'")
        try:
            cur = getattr(self.CFG, key)
            newv = self._coerce_value(val, type(cur))
            setattr(self.CFG, key, newv)
            self._log(f"[OK] {key} = {newv!r}")
            refresh_all_tabs()
        except Exception as e:
            self._log(f"[ERR] set: {e}")

    def _cmd_toggle(self, args):
        if len(args) < 1: return self._log("Usage: toggle <key>")
        key = args[0]
        if not hasattr(self.CFG, key): return self._log(f"[ERR] No such key '{key}'")
        cur = getattr(self.CFG, key)
        if not isinstance(cur, bool): return self._log(f"[ERR] '{key}' is not a bool")
        setattr(self.CFG, key, not cur)
        self._log(f"[OK] {key} = {getattr(self.CFG, key)}")
        refresh_all_tabs()

    def _cmd_list(self, args):
        pref = args[0].lower() if args else ""
        keys = [k for k in dir(self.CFG) if not k.startswith("_")]
        keys.sort()
        shown = 0
        for k in keys:
            if pref and not k.lower().startswith(pref): continue
            try:
                v = getattr(self.CFG, k)
                if callable(v): continue
                self._log(f"{k} = {v}")
                shown += 1
                if shown >= 200:
                    self._log("… (truncated)")
                    break
            except Exception:
                pass
        if shown == 0:
            self._log("(no matching keys)")

    def _cmd_start(self, args):
        if len(args) < 1: return self._log("Usage: start <feature>")
        feat = args[0].lower()
        try:
            if   feat == "esp":         start_esp_thread()
            elif feat == "aimbot":      start_aimbot_thread()
            elif feat == "triggerbot":  start_triggerbot_thread()
            elif feat == "glow":        start_glow_thread()
            elif feat == "bhop":        start_bhop_thread()
            elif feat == "fov":         start_fov_thread()
            elif feat == "walkbot":     start_walkbot_thread()
            else: return self._log(f"[ERR] Unknown feature '{feat}'")
            self._log(f"[OK] started {feat}")
        except Exception as e:
            self._log(f"[ERR] start {feat}: {e}")

    def _cmd_stop(self, args):
        if len(args) < 1: return self._log("Usage: stop <feature>")
        feat = args[0].lower()
        try:
            if   feat == "esp":         stop_esp_thread()
            elif feat == "aimbot":      stop_aimbot_thread()
            elif feat == "triggerbot":  stop_triggerbot_thread()
            elif feat == "glow":        stop_glow_thread()
            elif feat == "bhop":        stop_bhop_thread()
            elif feat == "fov":         stop_fov_thread()
            elif feat == "walkbot":     stop_walkbot_thread()
            else: return self._log(f"[ERR] Unknown feature '{feat}'")
            self._log(f"[OK] stopped {feat}")
        except Exception as e:
            self._log(f"[ERR] stop {feat}: {e}")

    def _cmd_threads(self, _args):
        # uses globals from GFusion.py
        mapping = {
            "esp": globals().get("esp_thread"),
            "aimbot": globals().get("aimbot_thread"),
            "triggerbot": globals().get("triggerbot_thread"),
            "glow": globals().get("glow_thread"),
            "bhop": globals().get("bhop_thread"),
            "fov": globals().get("fov_thread"),
            "walkbot": globals().get("walkbot_thread"),
        }
        for name, th in mapping.items():
            state = "running" if th is not None and th.is_alive() else "stopped"
            self._log(f"{name:<10} {state}")

    def _cmd_panic(self, _args):
        # Stop everything fast; set panic flags if present
        try:
            if hasattr(self.CFG, "panic_key_enabled"): setattr(self.CFG, "panic_key_enabled", True)
            stop_esp_thread()
            stop_aimbot_thread()
            stop_triggerbot_thread()
            stop_glow_thread()
            stop_bhop_thread()
            stop_fov_thread()
            stop_walkbot_thread()
            self._set_status("PANIC")
            self._log("[OK] All features stopped")
            refresh_all_tabs()
        except Exception as e:
            self._log(f"[ERR] panic: {e}")

    def _cmd_reload_offsets(self, _args):
        try:
            reload_offsets_and_restart_threads()
            self._log("[OK] Offsets reloaded; restarting features…")
        except Exception as e:
            self._log(f"[ERR] reload_offsets: {e}")

    def _cmd_restart_features(self, _args):
        try:
            stop_esp_thread(); stop_aimbot_thread(); stop_triggerbot_thread()
            stop_glow_thread(); stop_bhop_thread(); stop_fov_thread(); stop_walkbot_thread()
            time.sleep(0.5)
            start_esp_thread(); start_aimbot_thread(); start_triggerbot_thread()
            start_glow_thread(); start_bhop_thread(); start_fov_thread(); start_walkbot_thread()
            self._log("[OK] Features restarted")
        except Exception as e:
            self._log(f"[ERR] restart_features: {e}")

    def _cmd_bind(self, args):
        if len(args) < 2: return self._log("Usage: bind <action> <key>")
        action, key = args[0], args[1]
        try:
            # Basic: store into Config under "<action>_key"
            setattr(self.CFG, f"{action}_key", key)
            self._log(f"[OK] bound {action} -> {key}")
            refresh_all_tabs()
        except Exception as e:
            self._log(f"[ERR] bind: {e}")

    def _cmd_unbind(self, args):
        if len(args) < 1: return self._log("Usage: unbind <action>")
        action = args[0]
        try:
            k = f"{action}_key"
            if hasattr(self.CFG, k):
                setattr(self.CFG, k, "")
                self._log(f"[OK] unbound {action}")
                refresh_all_tabs()
            else:
                self._log(f"[ERR] no binding for '{action}'")
        except Exception as e:
            self._log(f"[ERR] unbind: {e}")

    # ---------- Helpers ----------
    def _coerce_value(self, text, typ):
        """Convert CLI text to the type of current config value."""
        if typ is bool:
            t = text.strip().lower()
            return t in ("1", "true", "on", "yes", "enable", "enabled")
        if typ is int:
            t = text.strip().lower()
            return int(t, 16) if t.startswith("0x") else int(t)
        if typ is float:
            return float(text.strip())
        if typ in (list, tuple):
            # try json first
            try:
                import json
                v = json.loads(text)
                return typ(v) if typ is tuple else v
            except Exception:
                # fallback: comma/space split
                parts = [p for p in text.replace(",", " ").split() if p]
                return typ(parts) if typ is tuple else parts
        # default: string
        return text

    # public hook for tab refreshes
    def refresh_ui(self):
        pass

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
        self.recoil_tab     = RecoilViewer()
        self.console_tab    = ConsoleTab()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.aimbot_tab,       "Aimbot")
        self.tabs.addTab(self.trigger_tab,      "Trigger")
        self.tabs.addTab(self.esp_tab,          "ESP")
        self.tabs.addTab(self.misc_tab,         "Misc")
        self.tabs.addTab(self.config_tab,       "Config")
        self.tabs.addTab(self.recoil_tab,       "Recoil")
        self.tabs.addTab(self.console_tab,      "Console")

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
