                            
         
                            
import atexit
import ctypes
import ctypes.wintypes
import datetime
import Features.esp
import importlib
import json
import keyboard
import os
import os, re, json, math
import os, sys, json
import platform
import requests
import subprocess
import sys
import threading
import time
from Features.aimbot import start_aim_rcs
from Features.auto_pistol import run_auto_pistol
from Features.bhop import BHopProcess
from Features.fov import FOVChanger
from Features.glow import CS2GlowManager
from Features.triggerbot import TriggerBot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from Process import offsets                  
from Process.config import Config
from PyQt5.QtCore import Qt
from PyQt5.QtCore import Qt, QPoint, QTimer, QThread, pyqtSignal, QEasingCurve, QPropertyAnimation
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPalette, QFontDatabase
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QWindow
from PyQt5.QtWidgets import (
    QWidget, QGroupBox, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QScrollArea, QMessageBox, QInputDialog, QFileDialog
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QScrollArea
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTabWidget, QApplication,
    QCheckBox, QComboBox, QSlider, QGroupBox, QLineEdit
)
from PyQt5.QtWidgets import (                                           
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QSlider,
    QLabel, QPushButton, QLineEdit, QComboBox, QTabWidget, QColorDialog,
    QGridLayout, QFrame, QScrollArea, QTextEdit, QMessageBox, QGroupBox,
    QTableWidget, QDoubleSpinBox, QTableWidgetItem
)
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTabWidget, QApplication
from PyQt5.QtWidgets import QTabWidget, QGraphicsOpacityEffect
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFontDatabase
   
                       
                            

try:
                                         
    from Process.config import Config
except Exception:
    class _F: pass
    Config = _F()
    setattr(Config, "learn_dir", "learn")
    setattr(Config, "sensitivity", 0.022)
    setattr(Config, "invert_y", -1)

                            
           
                            
# ========================================
# CRASH PREVENTION & LOGGING SYSTEM
# ========================================
import logging
from logging.handlers import RotatingFileHandler
from PyQt5.QtCore import QObject, pyqtSignal, QMutex, QMutexLocker

class GFusionLogger(QObject):
    """
    Thread-safe centralized logging system.
    Writes to:
      - gfusion_debug.log (rotating file, max 10MB, 3 backups)
      - Console tab (if available)
      - stdout (for debugging)
    """
    log_signal = pyqtSignal(str, str)  # (level, message)
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if '_initialized' in self.__dict__:
            return
        super().__init__()
        self._initialized = True
        self._console_tab = None
        self._qt_mutex = QMutex()
        
        # Setup file logging
        self.logger = logging.getLogger('GFusion')
        self.logger.setLevel(logging.DEBUG)
        
        # Rotating file handler (10MB max, 3 backups)
        try:
            file_handler = RotatingFileHandler(
                'gfusion_debug.log',
                maxBytes=10*1024*1024,  # 10MB
                backupCount=3,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"[LOGGER] Failed to create log file: {e}")
        
        # Console handler (for development)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        self.logger.info("="*60)
        self.logger.info("GFusion Logger Initialized")
        self.logger.info("="*60)
    
    def set_console_tab(self, console_tab):
        """Register the Console tab for GUI logging."""
        with QMutexLocker(self._qt_mutex):
            self._console_tab = console_tab
            self.logger.info("Console tab registered for GUI logging")
    
    def _format_message(self, level, message, category=""):
        """Format message with category prefix."""
        if category:
            return f"[{category}] {message}"
        return message
    
    def _log_to_console_tab(self, level, message):
        """Send log to Console tab if available (thread-safe)."""
        try:
            with QMutexLocker(self._qt_mutex):
                if self._console_tab and hasattr(self._console_tab, '_log'):
                    # Use signal to safely cross thread boundary
                    self.log_signal.emit(level, message)
        except Exception as e:
            print(f"[LOGGER] Failed to log to console tab: {e}")
    
    def debug(self, message, category=""):
        msg = self._format_message("DEBUG", message, category)
        self.logger.debug(msg)
        self._log_to_console_tab("DEBUG", msg)
    
    def info(self, message, category=""):
        msg = self._format_message("INFO", message, category)
        self.logger.info(msg)
        self._log_to_console_tab("INFO", msg)
    
    def warning(self, message, category=""):
        msg = self._format_message("WARNING", message, category)
        self.logger.warning(msg)
        self._log_to_console_tab("WARNING", msg)
    
    def error(self, message, category="", exc_info=False):
        msg = self._format_message("ERROR", message, category)
        self.logger.error(msg, exc_info=exc_info)
        self._log_to_console_tab("ERROR", msg)
    
    def critical(self, message, category="", exc_info=False):
        msg = self._format_message("CRITICAL", message, category)
        self.logger.critical(msg, exc_info=exc_info)
        self._log_to_console_tab("CRITICAL", msg)
    
    def exception(self, message, category=""):
        """Log exception with full traceback."""
        msg = self._format_message("EXCEPTION", message, category)
        self.logger.exception(msg)
        self._log_to_console_tab("EXCEPTION", msg)

# Global logger instance
logger = GFusionLogger()

# ----------------------------------------
# UI refresher: safely update all tabs
# ----------------------------------------
class UIRefresher(QObject):
    """
    Small helper that exposes a Qt signal we can emit from anywhere
    (console commands, background threads, etc.) and then perform
    a safe, main-thread UI refresh of all registered tabs.
    """
    trigger_refresh = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.trigger_refresh.connect(self._on_trigger_refresh)

    def _on_trigger_refresh(self):
        try:
            # Uses global TAB_REGISTRY / refresh_all_tabs
            refresh_all_tabs()
        except Exception as e:
            print(f"[UIRefresher] UI refresh failed: {e}")


# Global instance used by console / other helpers
ui_refresher = UIRefresher()

class MenuToggleBridge(QObject):
    toggle_menu = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)


menu_toggle_bridge = MenuToggleBridge()

def safe_thread_wrapper(func, thread_name="UnknownThread"):
    """
    Wrapper for thread functions to catch and log all exceptions.
    Prevents threads from silently crashing.
    """
    def wrapper(*args, **kwargs):
        logger.info(f"Thread started", category=thread_name)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Thread crashed: {e}", category=thread_name)
            return None
        finally:
            logger.info(f"Thread stopped", category=thread_name)
    return wrapper

def safe_call(func, *args, error_msg="Operation failed", category="", **kwargs):
    """
    Safely call a function with error handling and logging.
    Returns (success: bool, result: any)
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        logger.error(f"{error_msg}: {e}", category=category, exc_info=True)
        return False, None

                            

def _apply_global_qss(app, font_family=None, font_size=None):
    """
    Apply a modern dark + red global stylesheet.
    All custom widgets rely on this instead of per-widget Win95 QSS.
    This version slightly increases spacing, adds nicer scrollbars,
    and cleans up the tab / header look.

    Supports runtime font customization via:
      - passed params: font_family / font_size
      - config fields: cfg.ui_font_family / cfg.ui_font_size (or Config.*)
    """
    # --- UI font customization (SAFE: do Python work outside the CSS string) ---
    _cfg = globals().get("cfg", None) or globals().get("Config", None)

    try:
        ff = font_family or getattr(_cfg, "ui_font_family", None) or "Segoe UI"
    except Exception:
        ff = font_family or "Segoe UI"

    try:
        fs = int(font_size or getattr(_cfg, "ui_font_size", 11) or 11)
    except Exception:
        fs = int(font_size or 11)

    fs = max(7, min(24, fs))  # clamp
    ff_esc = str(ff).replace('"', r'\"')  # avoid breaking the CSS string

    qss = f"""
    /* === Global base === */
    QWidget {{
        background-color: #080812;
        color: #f5f5f7;
        font-family: "{ff_esc}", "Segoe UI", "Inter", "Tahoma", sans-serif;
        font-size: {fs}px;
    }}

    QLabel {{
        color: #f5f5f7;
    }}

    /* === Outer shell === */
    #outerPanel {{
        background-color: qlineargradient(
            x1:0, y1:0, x2:1, y2:1,
            stop:0 #151520,
            stop:1 #11111c
        );
        border-radius: 14px;
        border: 1px solid #26263a;
    }}

    /* Small header tweaks (safe even if IDs don't exist) */
    #headerTitle {{
        font-size: 12pt;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}
    #headerSubtitle {{
        font-size: 8.5pt;
        color: #a3a5c0;
    }}

    /* === Tabs === */
    QTabWidget::pane {{
        border: none;
        top: 0px;
    }}
    QTabBar {{
        qproperty-drawBase: 0;
    }}
    QTabBar::tab {{
        background: transparent;
        padding: 8px 16px;
        margin-right: 4px;
        color: #8a8fa2;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        color: #ffffff;
        border-bottom: 2px solid #ff3b4a;
    }}
    QTabBar::tab:hover {{
        color: #ffffff;
        border-bottom: 2px solid #ff3b4a88;
    }}

    /* === Group boxes / cards === */
    QGroupBox {{
        background-color: #181828;
        border-radius: 10px;
        border: 1px solid #26263a;
        margin-top: 10px;
        padding: 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 4px;
        color: #ffffff;
        background-color: transparent;
    }}

    /* === Buttons === */
    QPushButton {{
        background-color: #1f1f2b;
        border-radius: 9px;
        border: 1px solid #2b2b3c;
        padding: 7px 10px;
        min-height: 22px;
        color: #f5f5f7;
    }}
    QPushButton:hover {{
        background-color: #282838;
        border-color: #ff3b4a;
    }}
    QPushButton:pressed {{
        background-color: #ff3b4a;
        border-color: #ff3b4a;
        color: #ffffff;
    }}
    QPushButton:disabled {{
        background-color: #101018;
        color: #5c5f74;
        border-color: #202030;
    }}

    /* === Checkboxes === */
    QCheckBox {{
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid #3a3a4d;
        background-color: #151520;
    }}
    QCheckBox::indicator:hover {{
        border-color: #ff3b4a;
    }}
    QCheckBox::indicator:checked {{
        background-color: #ff3b4a;
        border-color: #ff3b4a;
    }}

    /* === Combobox === */
    QComboBox {{
        background-color: #151520;
        border-radius: 6px;
        border: 1px solid #2b2b3c;
        padding: 4px 8px;
        color: #f5f5f7;
    }}
    QComboBox:hover {{
        border-color: #ff3b4a;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 18px;
    }}
    QComboBox::down-arrow {{
        image: none;
        width: 0;
        height: 0;
        border-left: 5px solid #f5f5f7;
        border-top: 4px solid transparent;
        border-bottom: 4px solid transparent;
        margin-right: 4px;
    }}

    /* === Sliders === */
    QSlider::groove:horizontal {{
        height: 6px;
        background: #2a2a3a;
        border-radius: 3px;
        margin: 0px 0;
    }}

    QSlider::sub-page:horizontal {{
        background: qlineargradient(
            x1:0, y1:0, x2:1, y2:0,
            stop:0 #ff3b4a,
            stop:1 #ff5164
        );
        border-radius: 3px;
    }}

    QSlider::add-page:horizontal {{
        background: #202030;
        border-radius: 3px;
    }}

    QSlider::handle:horizontal {{
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
        background-color: #ff3b4a;
        border: 1px solid #ff6b75;
    }}

    QSlider::handle:horizontal:hover {{
        background-color: #ff4e5c;
        border: 1px solid #ff7f89;
    }}

    QSlider::handle:horizontal:pressed {{
        background-color: #ff2e3b;
        border: 1px solid #ff606b;
    }}

    /* === Scroll areas === */
    QScrollArea {{
        background: transparent;
        border: none;
    }}

    /* === Scrollbars === */
    QScrollBar:vertical {{
        width: 10px;
        background: transparent;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: #2a2a3a;
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #343449;
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
        border: none;
        background: transparent;
    }}

    QScrollBar:horizontal {{
        height: 10px;
        background: transparent;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: #2a2a3a;
        border-radius: 5px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: #343449;
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0px;
        border: none;
        background: transparent;
    }}

    /* === Edits === */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: #151520;
        border-radius: 6px;
        border: 1px solid #2b2b3c;
        padding: 4px 8px;
        color: #f5f5f7;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: #ff3b4a;
    }}

    /* === Tables === */
    QTableWidget {{
        background-color: #151520;
        gridline-color: #26263a;
        border-radius: 8px;
        border: 1px solid #26263a;
    }}
    QHeaderView::section {{
        background-color: #1c1c28;
        color: #f5f5f7;
        padding: 4px 8px;
        border: none;
        border-bottom: 1px solid #26263a;
    }}

    /* Startup overlay */
    #startupOverlay {{
        background-color: rgba(7, 7, 12, 230);
        border-radius: 14px;
    }}
    #startupTitle {{
        font-size: 20px;
        font-weight: 700;
    }}
    #startupSubtitle {{
        font-size: 11px;
        color: #b0b2c8;
    }}

    /* Tiny square ESP color buttons */
    #espColorButton {{
        min-width: 16px;
        max-width: 16px;
        min-height: 16px;
        max-height: 16px;
        padding: 0;              /* overrides the global 7px padding */
        border-radius: 4px;
        border: 1px solid #3a3a4d;
    }}

    #espColorButton:hover {{
        border-color: #ff3b4a;
    }}

    #espColorButton:pressed {{
        border-color: #ff3b4a;
    }}
    """

    app.setStyleSheet(qss)
    # Force re-polish so runtime font changes actually propagate even for widgets
    # that cache font metrics or were created before the stylesheet update.
    try:
        for w in app.allWidgets():
            try:
                st = w.style()
                st.unpolish(w)
                st.polish(w)
                w.update()
            except Exception:
                pass
        app.processEvents()
    except Exception:
        pass

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
                               
        try:
            print("GFusion requires Administrator privileges for kernel mode support...")
            print("Requesting elevation...")
            
                                                        
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                sys.executable, 
                f'"{os.path.abspath(__file__)}"',
                None, 
                1                 
            )
            sys.exit(0)                         
        except Exception as e:
            print(f"Failed to elevate privileges: {e}")
            print("Continuing without administrator rights (kernel mode unavailable)")
            return False
    
    print("[OK] Running with Administrator privileges - Kernel mode available")
    return True

def create_section_separator():
    """Create a horizontal line separator"""
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line

def get_offsets():
    from Process import offsets
    return offsets.Offsets

def handle_console_command(cmd_line: str):
    """Parse and execute console commands"""
    try:
        parts = cmd_line.strip().split()
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]

                                   
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

                                             
            QTimer.singleShot(0, update_feature_state)

                                     
        elif cmd == "set" and len(args) >= 2:
            key, value = args[0], " ".join(args[1:])
            if hasattr(cfg, key):
                old_val = getattr(cfg, key)
                try:
                                                   
                    if isinstance(old_val, bool):
                        new_val = value.lower() in ("1", "true", "on", "enable")
                    elif isinstance(old_val, int):
                        new_val = int(value)
                    elif isinstance(old_val, float):
                        new_val = float(value)
                    else:
                        new_val = value

                                                          
                    QTimer.singleShot(0, lambda k=key, v=new_val: setattr(cfg, k, v))
                    print(f"[Console] {key} scheduled update to {new_val}")
                except Exception as e:
                    print(f"[Console] Failed to set {key}: {e}")
            else:
                print(f"[Console] Unknown config key: {key}")

        else:
            print(f"[Console] Unknown command: {cmd}")

    finally:
        # Always try to refresh the UI after a console command,
        # but never let a refresh failure crash the app.
        try:
            refresher = globals().get("ui_refresher", None)
            if refresher is not None and hasattr(refresher, "trigger_refresh"):
                refresher.trigger_refresh.emit()
        except Exception as e:
            print(f"[Console] UI refresh failed: {e}")


def key_to_vk(key_name):
    return VK_CODES.get(key_name.lower(), 0x7B)               

def refresh_all_tabs():
    for tab in TAB_REGISTRY:
        try:
            if hasattr(tab, "refresh_ui"):
                tab.refresh_ui()
        except Exception as e:
            print(f"[UI] Refresh failed for {tab}: {e}")

def register_tab(tab):
    if tab not in TAB_REGISTRY:
        TAB_REGISTRY.append(tab)

def reload_offsets_and_restart_threads():
    """Reload offsets.py and restart feature threads safely."""
    try:
        importlib.reload(offsets)
        print("[Offsets] Reloaded offsets.py")
    except Exception as e:
        print(f"[Offsets] Failed to reload: {e}")
        return

    def restart():
        time.sleep(2)                    
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

def run():
    logger.info("="*60, category="System")
    logger.info("GFusion Starting", category="System")
    logger.info("="*60, category="System")
                                              
    is_admin = check_admin_privileges()
    
    print("Made by GitHub.com/Cr0mb/")
    if is_admin:
        print("[ADMIN] Administrator Mode - Full kernel access enabled")
        logger.info("Running with administrator privileges", category="System")
    else:
        print("[WARNING] User Mode - Limited to usermode memory access")
        logger.warning("Running without administrator privileges", category="System")
    
    app = QApplication(sys.argv)
    
    # Install global exception handler for Qt
    def qt_exception_handler(exc_type, exc_value, exc_traceback):
        """Global exception handler for unhandled Qt exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            f"Unhandled exception: {exc_type.__name__}: {exc_value}",
            category="System",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    sys.excepthook = qt_exception_handler
    logger.info("Global exception handler installed", category="System")

    # Apply global stylesheet
    _apply_global_qss(app, getattr(cfg, 'ui_font_family', None), getattr(cfg, 'ui_font_size', None))

    try:
        win = MainWindow()
        logger.info("MainWindow created successfully", category="System")
    except Exception as e:
        logger.critical(f"Failed to create MainWindow: {e}", category="System", exc_info=True)
        return
    
    base_title = "GFusion V1 - Paint Edition"
    if is_admin:
        win.setWindowTitle(f"{base_title} - Administrator")
    else:
        win.setWindowTitle(f"{base_title} - User Mode")
    
    win.show()
    logger.info("MainWindow shown", category="System")

    # Start feature threads
    logger.info("Starting feature threads", category="System")
    start_aimbot_thread()
    start_esp_thread()
    start_triggerbot_thread()
    start_auto_pistol_thread()
    logger.info("Feature threads started", category="System")

    start_toggle_listener(win)
    
    # Register shutdown handler to prevent daemon thread errors
    def cleanup_on_exit():
        """Suppress daemon thread output during shutdown"""
        logger.info("Application shutting down", category="System")
        try:
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')
        except:
            pass
    
    atexit.register(cleanup_on_exit)

    logger.info("Entering Qt event loop", category="System")
    app.exec_()                  

def run_aimbot():
    logger.info("Starting aimbot", category="Aimbot")
    try:
        start_aim_rcs(cfg)
    except Exception as e:
        logger.exception(f"Aimbot crashed: {e}", category="Aimbot")

def run_bhop():
    global bhop_instance
    logger.info("Starting bhop", category="BHop")
    try:
        bhop_instance = BHopProcess()
        bhop_instance.run()
    except Exception as e:
        logger.exception(f"BHop crashed: {e}", category="BHop")

def run_esp():
    global esp_running
    if esp_running:
        logger.warning("ESP already running, skipping duplicate start", category="ESP")
        return
    esp_running = True
    logger.info("Starting ESP", category="ESP")
    try:
        Features.esp.main()
    except Exception as e:
        logger.exception(f"ESP crashed: {e}", category="ESP")
    finally:
        esp_running = False
        logger.info("ESP stopped", category="ESP")

def run_fov():
    global fov_changer
    logger.info("Starting FOV changer", category="FOV")
    try:
        fov_changer = FOVChanger(cfg)
        fov_changer.run()
    except Exception as e:
        logger.exception(f"FOV changer crashed: {e}", category="FOV")

def run_glow():
    global glow_manager
    logger.info("Starting glow", category="Glow")
    try:
        glow_manager = CS2GlowManager(cfg)
        glow_manager.run()
    except Exception as e:
        logger.exception(f"Glow crashed: {e}", category="Glow")

def run_triggerbot():
    global triggerbot_instance
    logger.info("Starting triggerbot", category="Triggerbot")
    try:
        triggerbot_instance = TriggerBot(shared_config=cfg)
        triggerbot_instance.run()
    except Exception as e:
        logger.exception(f"Triggerbot crashed: {e}", category="Triggerbot")

def run_walkbot():
    logger.info("Starting walkbot", category="Walkbot")
    try:
        from Features.walk_bot import walk_in_circle
        walk_in_circle()
    except Exception as e:
        logger.exception(f"Walkbot crashed: {e}", category="Walkbot")

def start_aimbot_thread():
    global aimbot_thread
    try:
        if aimbot_thread is None or not aimbot_thread.is_alive():
            cfg.aim_stop = False
            aimbot_thread = threading.Thread(target=run_aimbot, daemon=True, name="AimbotThread")
            aimbot_thread.start()
            logger.info("Aimbot thread started", category="Threading")
        else:
            logger.debug("Aimbot thread already running", category="Threading")
    except Exception as e:
        logger.error(f"Failed to start aimbot thread: {e}", category="Threading", exc_info=True)

def start_auto_pistol_thread():
    global auto_pistol_thread
    try:
        if not cfg.auto_pistol_enabled:
            logger.debug("Auto pistol not enabled", category="Threading")
            return
        if auto_pistol_thread is None or not auto_pistol_thread.is_alive():
            auto_pistol_thread = threading.Thread(target=run_auto_pistol, args=(cfg,), daemon=True, name="AutoPistolThread")
            auto_pistol_thread.start()
            logger.info("Auto pistol thread started", category="Threading")
    except Exception as e:
        logger.error(f"Failed to start auto pistol thread: {e}", category="Threading", exc_info=True)

def start_bhop_thread():
    global bhop_thread
    try:
        if bhop_thread is None or not bhop_thread.is_alive():
            Config.bhop_stop = False
            Config.bhop_enabled = True
            bhop_thread = threading.Thread(target=run_bhop, daemon=True, name="BHopThread")
            bhop_thread.start()
            logger.info("BHop thread started", category="Threading")
    except Exception as e:
        logger.error(f"Failed to start bhop thread: {e}", category="Threading", exc_info=True)

def start_esp_thread():
    global esp_thread
    try:
        if esp_thread is None or not esp_thread.is_alive():
            esp_thread = threading.Thread(target=run_esp, daemon=True, name="ESPThread")
            esp_thread.start()
            logger.info("ESP thread started", category="Threading")
    except Exception as e:
        logger.error(f"Failed to start ESP thread: {e}", category="Threading", exc_info=True)

def start_fov_thread():
    global fov_thread
    try:
        if fov_thread is None or not fov_thread.is_alive():
            cfg.fov_changer_enabled = True
            fov_thread = threading.Thread(target=run_fov, daemon=True, name="FOVThread")
            fov_thread.start()
            logger.info("FOV thread started", category="Threading")
    except Exception as e:
        logger.error(f"Failed to start FOV thread: {e}", category="Threading", exc_info=True)

def start_glow_thread():
    global glow_thread
    try:
        if glow_thread is None or not glow_thread.is_alive():
            Config.glow_stop = False
            Config.glow = True
            glow_thread = threading.Thread(target=run_glow, daemon=True, name="GlowThread")
            glow_thread.start()
            logger.info("Glow thread started", category="Threading")
    except Exception as e:
        logger.error(f"Failed to start glow thread: {e}", category="Threading", exc_info=True)

def start_toggle_listener(main_window):
    def _toggle_menu():
        """Runs on the Qt (GUI) thread via signal."""
        try:
            if main_window.isVisible():
                # Close menu
                main_window.hide()
            else:
                # Open menu and grab mouse/keyboard focus immediately
                main_window.show()
                main_window.activateWindow()
                main_window.raise_()
                main_window.setFocus()
        except Exception as e:
            logger.exception(f"Toggle menu failed: {e}", category="MenuToggle")

    # Connect the bridge signal to our GUI-side toggle slot
    try:
        menu_toggle_bridge.toggle_menu.disconnect()
    except TypeError:
        # No previous connections
        pass
    menu_toggle_bridge.toggle_menu.connect(_toggle_menu)

    def listen():
        logger.info("Menu toggle listener started", category="MenuToggle")
        while True:
            try:
                if keyboard.is_pressed(cfg.toggle_menu_key):
                    # Ask GUI thread to toggle the menu
                    menu_toggle_bridge.toggle_menu.emit()

                    # Debounce: wait until key released so it only toggles once
                    while keyboard.is_pressed(cfg.toggle_menu_key):
                        time.sleep(0.05)

                time.sleep(0.016)
            except Exception as e:
                logger.exception(f"Toggle listener error: {e}", category="MenuToggle")
                time.sleep(1.0)  # Prevent tight error loop

    try:
        t = threading.Thread(target=listen, daemon=True, name="MenuToggleThread")
        t.start()
        logger.info("Menu toggle thread started", category="Threading")
    except Exception as e:
        logger.error(f"Failed to start toggle listener: {e}", category="Threading", exc_info=True)

_triggerbot_lock = threading.Lock()

def start_triggerbot_thread():
    global triggerbot_thread

    try:
        if not getattr(cfg, "triggerbot_enabled", False):
            logger.debug("Triggerbot not starting: disabled in config", category="Triggerbot")
            return False

        with _triggerbot_lock:
            if triggerbot_thread is not None and triggerbot_thread.is_alive():
                logger.debug("Triggerbot thread already running", category="Triggerbot")
                return True

            setattr(cfg, "triggerbot_stop", False)

            triggerbot_thread = threading.Thread(
                target=run_triggerbot,
                name="TriggerBotThread",
                daemon=True,
            )
            triggerbot_thread.start()
            logger.info("Triggerbot thread started", category="Threading")
            return True
    except Exception as e:
        logger.error(f"Failed to start triggerbot thread: {e}", category="Threading", exc_info=True)
        return False


def stop_triggerbot_thread(join: bool = False, timeout: float = 1.0):
    global triggerbot_thread

    with _triggerbot_lock:
        setattr(cfg, "triggerbot_stop", True)

    if join and triggerbot_thread is not None:
        triggerbot_thread.join(timeout)

    print("[TriggerBot] Stop signaled")


def set_triggerbot_enabled(enabled: bool, start_if_enabled: bool = True):
    cfg.triggerbot_enabled = bool(enabled)

    if not enabled:
        stop_triggerbot_thread()
        print("[TriggerBot] Disabled")
        return False

    if start_if_enabled:
        return start_triggerbot_thread()

    print("[TriggerBot] Enabled (not started)")
    return False

def start_walkbot_thread():
    global walkbot_thread
    if walkbot_thread is None or not walkbot_thread.is_alive():
        Config.walkbot_stop = False
        Config.walkbot_enabled = True
        walkbot_thread = threading.Thread(target=run_walkbot, daemon=True)
        walkbot_thread.start()

def stop_aimbot_thread():
    try:
        cfg.stop = True
        logger.info("Aimbot stop signal sent", category="Threading")
    except Exception as e:
        logger.error(f"Failed to stop aimbot: {e}", category="Threading", exc_info=True)

def stop_auto_pistol_thread():
    try:
        cfg.auto_pistol_enabled = False
        logger.info("Auto pistol stop signal sent", category="Threading")
    except Exception as e:
        logger.error(f"Failed to stop auto pistol: {e}", category="Threading", exc_info=True)

def stop_bhop_thread():
    try:
        Config.bhop_enabled = False
        Config.bhop_stop = True
        logger.info("BHop stop signal sent", category="Threading")
    except Exception as e:
        logger.error(f"Failed to stop bhop: {e}", category="Threading", exc_info=True)

def stop_esp_thread():
    global esp_running
    try:
        esp_running = False
        logger.info("ESP stop signal sent", category="Threading")
    except Exception as e:
        logger.error(f"Failed to stop ESP: {e}", category="Threading", exc_info=True)

def stop_fov_thread():
    global fov_thread
    try:
        cfg.fov_changer_enabled = False
        fov_thread = None
        logger.info("FOV changer stop signal sent", category="Threading")
    except Exception as e:
        logger.error(f"Failed to stop FOV changer: {e}", category="Threading", exc_info=True)

def stop_glow_thread():
    global glow_thread, glow_manager
    try:
        Config.glow = False
        Config.glow_stop = True
        glow_thread = None
        glow_manager = None
        logger.info("Glow stop signal sent", category="Threading")
    except Exception as e:
        logger.error(f"Failed to stop glow: {e}", category="Threading", exc_info=True)

def stop_triggerbot_thread():
    try:
        cfg.triggerbot_enabled = False
        cfg.triggerbot_stop = True
        logger.info("Triggerbot stop signal sent", category="Threading")
    except Exception as e:
        logger.error(f"Failed to stop triggerbot: {e}", category="Threading", exc_info=True)

def stop_walkbot_thread():
    try:
        Config.walkbot_enabled = False
        Config.walkbot_stop = True
        logger.info("Walkbot stop signal sent", category="Threading")
    except Exception as e:
        logger.error(f"Failed to stop walkbot: {e}", category="Threading", exc_info=True)

def vk_to_name(vk_code):
    return VK_NAME.get(vk_code, "UNKNOWN")

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

                            
# Classes
                            
class AimbotTab(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = {"checkboxes": {}, "sliders": {}, "combos": {}, "labels": {}}
        self.init_ui()

                                                               
    def create_group_box(self, title: str) -> QGroupBox:
        """Create a modern card-style group box that uses the global theme."""
        g = QGroupBox(title)
        g.setObjectName("cardGroup")
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

    def add_color_button(self, layout, cfg_key, tooltip=""):
        btn = QPushButton()
        btn.setObjectName("espColorButton")
        btn.setToolTip(tooltip)
        btn.setFixedSize(16, 16)

        def update_btn():
            col = getattr(Config, cfg_key, (255, 0, 0))
            btn.setStyleSheet(
                f"#espColorButton {{ background-color: rgb({col[0]}, {col[1]}, {col[2]}); }}"
            )

        def on_click():
            cur = getattr(Config, cfg_key, (255, 0, 0))
            color = QColorDialog.getColor(QColor(*cur), self)
            if color.isValid():
                new = (color.red(), color.green(), color.blue())
                setattr(Config, cfg_key, new)
                update_btn()

        btn.clicked.connect(on_click)
        update_btn()
        layout.addWidget(btn)
        return btn

    def add_combo_row(self, layout, label, options, cfg_key, to_lower=True, width=100):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #f5f5f7; ")
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
        lab.setStyleSheet("color: #f5f5f7; ")
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
        lab.setStyleSheet("color: #f5f5f7; ")
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
        lbl.setStyleSheet("font-weight: bold; color: #f5f5f7;")
        return lbl

                              
    def init_ui(self):
        # scroll container (same pattern as other tabs)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #151520; border: none; }")

        content = QWidget(); content.setStyleSheet("background-color: #151520;")
        root = QVBoxLayout(content)
        root.setSpacing(8); root.setContentsMargins(8, 8, 8, 8)

                                   
        main_g = self.create_group_box("Main")
        main = QHBoxLayout(main_g); main.setSpacing(10)

                     
        col_left = QVBoxLayout(); col_left.setSpacing(4)
        self.add_checkbox(col_left, "Enable Aimbot", "enabled",
                          on_toggle=lambda en: (start_aimbot_thread() if en else stop_aimbot_thread()))
        self.add_checkbox(col_left, "DeathMatch Mode", "DeathMatch")
        main.addLayout(col_left, 1)

                                               
        col_mid = QVBoxLayout(); col_mid.setSpacing(6)
        self.auto_pistol_cb = self.add_checkbox(
            col_mid, "Auto Pistol", "auto_pistol_enabled",
            on_toggle=lambda en: (start_auto_pistol_thread() if en else stop_auto_pistol_thread())
        )
                        
        self.add_combo_row(col_mid, "Auto Pistol Key:",
                           ["mouse2","mouse3","mouse4","mouse5","alt","ctrl","shift","space"],
                           "activation_key", to_lower=True, width=90)
                   
        fr_box = QVBoxLayout()
        self.fr_slider, self.fr_label_holder = self.add_float_slider(
            fr_box, "Fire Rate (s)", "fire_rate", 0.01, 1.00, 100
        )
        col_mid.addLayout(fr_box)
        main.addLayout(col_mid, 1)

                         
        col_right = QVBoxLayout(); col_right.setSpacing(6)
        self.add_checkbox(col_right, "Visible-check Aim", "visibility_aim_enabled")
        self.add_checkbox(col_right, "Closest to Crosshair", "closest_to_crosshair")
        main.addLayout(col_right, 1)

        root.addWidget(main_g)

                                        
        fov_g = self.create_group_box("FOV Overlay")
        fov = QVBoxLayout(fov_g); fov.setSpacing(6)

        row = QHBoxLayout()
        self.add_checkbox(row, "Show FOV Circle", "fov_circle_enabled")

        self.add_color_button(
            row,
            "fov_overlay_color",
            tooltip="FOV circle color"
        )

        row.addStretch(1)
        fov.addLayout(row)
        root.addWidget(fov_g)


                                 
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
        self.kernel_status.setStyleSheet("color: #888; font-style: italic;")
        kern.addWidget(self.kernel_status)
        root.addWidget(kern_g)

                                              
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

                                         
        input_g = self.create_group_box("Input")
        inp = QVBoxLayout(input_g); inp.setSpacing(6)
        self.add_combo_row(inp, "Aim Activation Key:",
                           ["mouse1","mouse2","mouse3","mouse4","mouse5",
                            "left_shift","right_shift","left_ctrl","right_ctrl",
                            "left_alt","right_alt","space"],
                           "aim_key", to_lower=True, width=110)

                                
        sens_row = QHBoxLayout()
        self.sens_label = QLabel(f"Sensitivity: {getattr(Config,'sensitivity',0.1):.3f}")
        self.sens_label.setStyleSheet("color:#f5f5f7; ")
        sens_row.addWidget(self.sens_label)

        self.sens_slider = NoScrollSlider(Qt.Horizontal)
        self.sens_slider.setMinimum(8); self.sens_slider.setMaximum(1000)
                                                       
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

                               
        tgt_g = self.create_group_box("Target")
        tgt = QVBoxLayout(tgt_g); tgt.setSpacing(6)
        self.add_combo_row(tgt, "Target Bone:", ["head","neck","chest","pelvis","left_hand","right_hand","left_leg","right_leg"], "target_bone_name", to_lower=True, width=90)
        self.learn_dir_label = QLabel(f"Learning Dir: {getattr(Config,'learn_dir','')}")
        self.learn_dir_label.setStyleSheet("color:#f5f5f7; ")
        tgt.addWidget(self.learn_dir_label)
        root.addWidget(tgt_g)

                                                   
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

                         
        jitter_box = QHBoxLayout()
        j_col = QVBoxLayout()
        self.add_float_slider(j_col, "Jitter Amount", "aim_jitter_amount", 0.00, 1.00, 100)
        jitter_box.addLayout(j_col)

        jf_col = QVBoxLayout()
        sld, lab = self.add_float_slider(jf_col, "Shake Frequency (Hz)", "aim_shake_frequency", 1.0, 20.0, 1)
                                   
        sld.valueChanged.connect(lambda v: lab.setText(f"Shake Frequency (Hz): {float(v):.1f}"))
        jitter_box.addLayout(jf_col)
        jitter_box.addStretch(1)
        human.addLayout(jitter_box)

                              
        delay_box = QVBoxLayout()
        self.add_float_slider(delay_box, "Delay Min (s)", "reaction_delay_min", 0.001, 0.200, 1000)
        self.add_float_slider(delay_box, "Delay Max (s)", "reaction_delay_max", 0.010, 0.300, 1000)
        human.addLayout(delay_box)

                          
        overshoot_box = QVBoxLayout()
        self.add_float_slider(overshoot_box, "Overshoot Chance", "overshoot_chance", 0.00, 0.50, 100)
        self.add_float_slider(overshoot_box, "Overshoot Amount (x)", "overshoot_amount", 1.00, 2.00, 100)
        human.addLayout(overshoot_box)

        root.addWidget(human_g)

        root.addStretch()
        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)

                                                
        QTimer.singleShot(300, self._check_kernel_status_delayed)

                                           
    def _toggle_kernel_mode(self, enabled: bool):
                                 
        self.kernel_status.setText("Status: Initializing..." if enabled else "Status: Disabled")
        self.kernel_status.setStyleSheet("color: #ff8800; font-style: italic;" if enabled else "color: #888; font-style: italic;")
                                                                      
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
                            self.kernel_status.setStyleSheet("color: #00ff00; font-style: italic;")
                            try: m.disconnect()
                            except: pass
                        else:
                            self.kernel_status.setText("Status: ✗ Driver error")
                            self.kernel_status.setStyleSheet("color: #ff0000; font-style: italic;")
                            try: m.stop_driver()
                            except: pass
                    else:
                        try: m.stop_driver()
                        except: pass
                except ImportError:
                    self.kernel_status.setText("Status: ✗ NeacController not found")
                    self.kernel_status.setStyleSheet("color: #ff0000; font-style: italic;")
                except Exception as e:
                    self.kernel_status.setText(f"Status: ✗ Error: {str(e)[:30]}...")
                    self.kernel_status.setStyleSheet("color: #ff0000; font-style: italic;")
            threading.Thread(target=init_kernel, daemon=True).start()
        except Exception as e:
            print(f"[AimbotTab] Kernel toggle error: {e}")

    def _check_kernel_status_delayed(self):
                                                 
        try:
            if hasattr(Config, "_kernel_active_instances") and Config._kernel_active_instances > 0:
                self.kernel_status.setText("Status: ✓ Kernel mode active")
                self.kernel_status.setStyleSheet("color: #00ff00; font-style: italic;")
        except Exception as e:
            print(f"[AimbotTab] Kernel delayed check error: {e}")

                                
    def refresh_ui(self):
        try:
                        
            for key, cb in self.ui["checkboxes"].items():
                cb.setChecked(bool(getattr(Config, key, False)))

                    
            for key, combo in self.ui["combos"].items():
                val = str(getattr(Config, key, combo.currentText()))
                idx = combo.findText(val.lower())
                if idx >= 0: combo.setCurrentIndex(idx)

                     
            for key, (sld, lab, mult) in self.ui["sliders"].items():
                val = getattr(Config, key, None)
                if val is None: continue
                if mult == 1:
                    sld.setValue(int(val)); lab.setText(f"{lab.text().split(':',1)[0]}: {int(val)}")
                else:
                    sld.setValue(int(float(val) * mult))
                    lab.setText(f"{lab.text().split(':',1)[0]}: {float(val):.2f}")

                            
            if hasattr(self, "sens_label"):
                self.sens_label.setText(f"Sensitivity: {getattr(Config,'sensitivity',0.1):.3f}")
            if hasattr(self, "learn_dir_label"):
                self.learn_dir_label.setText(f"Learning Dir: {getattr(Config,'learn_dir','')}")
        except Exception as e:
            print(f"[AimbotTab] refresh_ui error: {e}")

class CheatCheckBox(QCheckBox):
    def __init__(self, label: str = "", parent=None):
        super().__init__(label, parent)
        # Use global dark theme styling; only tag with objectName if extra rules are desired.
        self.setObjectName("cheatCheckBox")

class CheatComboBox(QComboBox):
    def __init__(self, items=None, width: int = 100, parent=None):
        super().__init__(parent)
        self.setObjectName("cheatComboBox")
        if items:
            self.addItems(items)
        self.setFixedWidth(width)

class ConfigTab(QWidget):
    config_loaded = pyqtSignal()

                                               
    def _create_group_box(self, title: str) -> QGroupBox:
        """Create a modern card-style group box that uses the global theme."""
        g = QGroupBox(title)
        g.setObjectName("cardGroup")
        return g

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#808080; background:#808080;")
        line.setFixedHeight(1)
        return line

                                
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

                               
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #151520; border: none; }")

        content = QWidget(); content.setStyleSheet("background-color:#151520;")
        root = QVBoxLayout(content)
        root.setSpacing(8); root.setContentsMargins(8,8,8,8)

                                                           
        active_g = self._create_group_box("Active Config")
        active = QVBoxLayout(active_g); active.setSpacing(6)

        row1 = QHBoxLayout()
        name_label = QLabel("Name:")
        name_label.setFixedWidth(40)
        name_label.setStyleSheet("color:#f5f5f7; ")

        self.active_combo = QComboBox()
        self.active_combo.setEditable(False)
        self.active_combo.setInsertPolicy(QComboBox.NoInsert)
        self.active_combo.activated[str].connect(self._on_active_changed)

        self.new_btn = QPushButton("New")
        self.save_btn = QPushButton("Save")
        self.load_btn = QPushButton("Load")
        self.apply_btn = QPushButton("Apply & Broadcast")
        for b in (self.new_btn, self.save_btn, self.load_btn, self.apply_btn):
            b.setFixedHeight(24)

        row1.addWidget(name_label)
        row1.addWidget(self.active_combo, 1)
        row1.addWidget(self.new_btn)
        row1.addWidget(self.save_btn)
        row1.addWidget(self.load_btn)
        row1.addWidget(self.apply_btn)
        active.addLayout(row1)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color:#f5f5f7; ")
        active.addWidget(self.status_label)
        root.addWidget(active_g)

                                                           
        saved_g = self._create_group_box("Saved Configs")
        saved = QVBoxLayout(saved_g); saved.setSpacing(6)

        lr1 = QHBoxLayout()
        list_label = QLabel("Saved:")
        list_label.setFixedWidth(40)
        list_label.setStyleSheet("color:#f5f5f7; ")
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
        self.autosave_label.setStyleSheet("color:#f5f5f7; ")

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
        appearance_g = self._create_group_box("Appearance")
        ap = QHBoxLayout(appearance_g); ap.setSpacing(10)

        font_label = QLabel("Font:")
        font_label.setFixedWidth(40)
        font_label.setStyleSheet("color:#f5f5f7; ")

        self.font_combo = QComboBox()
        self.font_combo.setEditable(True)
        self.font_combo.setInsertPolicy(QComboBox.NoInsert)
        # Populate with system fonts (sorted)
        try:
            families = sorted(QFontDatabase().families(), key=lambda s: s.lower())
        except Exception:
            families = []
        if families:
            self.font_combo.addItems(families)

        # Default/current font from config
        cur_font = str(getattr(self.CFG, "ui_font_family", "Segoe UI") or "Segoe UI")
        _idx = self.font_combo.findText(cur_font)
        if _idx >= 0:
            self.font_combo.setCurrentIndex(_idx)
        else:
            self.font_combo.setEditText(cur_font)

        size_label = QLabel("Size:")
        size_label.setFixedWidth(38)
        size_label.setStyleSheet("color:#f5f5f7; ")

        self.font_size_slider = NoScrollSlider(Qt.Horizontal)
        self.font_size_slider.setMinimum(7)
        self.font_size_slider.setMaximum(24)
        cur_size = int(getattr(self.CFG, "ui_font_size", 11) or 11)
        self.font_size_slider.setValue(max(7, min(24, cur_size)))

        self.font_size_value = QLabel(f"{self.font_size_slider.value()}px")
        self.font_size_value.setFixedWidth(44)
        self.font_size_value.setStyleSheet("color:#a3a5c0; ")

        self.font_apply_btn = QPushButton("Apply Font")
        self.font_apply_btn.setFixedHeight(24)

        def _on_font_size(v):
            try:
                self.font_size_value.setText(f"{int(v)}px")
            except Exception:
                pass
        self.font_size_slider.valueChanged.connect(_on_font_size)

        def _apply_font():
            try:
                ff = self.font_combo.currentText().strip() or "Segoe UI"
                fs = int(self.font_size_slider.value())
                setattr(self.CFG, "ui_font_family", ff)
                setattr(self.CFG, "ui_font_size", fs)
                app = QApplication.instance()
                if app is not None:
                    _apply_global_qss(app, ff, fs)
                self.status_label.setText(f"Status: ✓ Font set to {ff} ({fs}px)")
            except Exception as e:
                print(f"[ConfigTab] font apply error: {e}")
                self.status_label.setText("Status: ✗ Font apply error")

        self.font_apply_btn.clicked.connect(_apply_font)

        ap.addWidget(font_label)
        ap.addWidget(self.font_combo, 1)
        ap.addWidget(size_label)
        ap.addWidget(self.font_size_slider, 1)
        ap.addWidget(self.font_size_value)
        ap.addWidget(self.font_apply_btn)
        root.addWidget(appearance_g)


        root.addWidget(auto_g)

                                                    
        dir_g = self._create_group_box("Folder")
        di = QHBoxLayout(dir_g); di.setSpacing(10)

        self.open_folder_btn = QPushButton("Open Config Folder")
        self.open_folder_btn.setFixedHeight(24)
        di.addWidget(self.open_folder_btn)
        di.addStretch(1)
        root.addWidget(dir_g)


        


                         
        root.addStretch(1)
        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)

                                            
        self.refresh_btn.clicked.connect(self.refresh_config_list)
        self.new_btn.clicked.connect(self.create_new_config)
        self.save_btn.clicked.connect(self.save_config)
        self.load_btn.clicked.connect(self.load_config)
        self.apply_btn.clicked.connect(self._apply_broadcast)

        self.rename_btn.clicked.connect(self.rename_config)
        self.duplicate_btn.clicked.connect(self.duplicate_config)
        self.delete_btn.clicked.connect(self.delete_config)

        self.import_btn.clicked.connect(self.import_config)
        self.export_btn.clicked.connect(self.export_config)

        self.open_folder_btn.clicked.connect(self.open_config_folder)
        self.refresh_config_list()
        self.refresh_ui()

                                    
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
        for n in names:
            combo.addItem(n)
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

    def create_new_config(self):
        """Create a new config with user-provided name."""
        base = "new_profile"
        name, ok = self._prompt_text("New Config", "Name:", base)
        if not ok or not name.strip():
            logger.debug("Config creation cancelled", category="Config")
            return
        name = name.strip()
        logger.info(f"Creating new config: {name}", category="Config")
        # Ensure unique
        if os.path.exists(os.path.join(self._configs_dir(), f"{name}.json")):
            name = self._unique_name(name)
            logger.debug(f"Name collision, using unique name: {name}", category="Config")
        # Create and save immediately
        try:
            setattr(self.CFG, "current_config_name", name)
            path = os.path.join(self._configs_dir(), f"{name}.json")
            os.makedirs(self._configs_dir(), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._serialize_cfg(), f, indent=2)
            self.refresh_config_list()
            idx = self.active_combo.findText(name)
            if idx >= 0:
                self.active_combo.setCurrentIndex(idx)
            self.status_label.setText(f"Status: ✓ Created & saved '{name}'")
            logger.info(f"Config created successfully: {name}", category="Config")
        except Exception as e:
            logger.exception(f"Failed to create config '{name}': {e}", category="Config")
            self.status_label.setText("Status: ✗ Create error")

    def save_config(self):
        name = self.active_combo.currentText().strip()
        if not name:
            self.status_label.setText("Status: ✗ Select a config to save")
            logger.warning("Save config called with no name selected", category="Config")
            return
        logger.info(f"Saving config: {name}", category="Config")
        try:
            if hasattr(self.CFG, "save_to_file"):
                self.CFG.save_to_file(name)
            else:
                path = os.path.join(self._configs_dir(), f"{name}.json")
                os.makedirs(self._configs_dir(), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._serialize_cfg(), f, indent=2)
                          
            self.refresh_config_list()
            self.status_label.setText(f"Status: ✓ Saved '{name}'")
            logger.info(f"Config saved successfully: {name}", category="Config")
        except Exception as e:
            logger.exception(f"Failed to save config '{name}': {e}", category="Config")
            self.status_label.setText("Status: ✗ Save error")

    def load_config(self):
        # Load from active combo only
        name = self.active_combo.currentText().strip()
        if not name:
            self.status_label.setText("Status: ✗ Select a config to load")
            logger.warning("Load config called with no name selected", category="Config")
            return
        logger.info(f"Loading config: {name}", category="Config")
        try:
            if hasattr(self.CFG, "load_from_file"):
                self.CFG.load_from_file(name)
            else:
                path = os.path.join(self._configs_dir(), f"{name}.json")
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._deserialize_cfg(data)
                                                
            try: setattr(self.CFG, "current_config_name", name)
            except: pass
            self.refresh_config_list()
            self.status_label.setText(f"Status: ✓ Loaded '{name}'")
            logger.info(f"Config loaded successfully: {name}", category="Config")
            self.config_loaded.emit()
            logger.debug("Config loaded signal emitted", category="Config")
        except Exception as e:
            logger.exception(f"Failed to load config '{name}': {e}", category="Config")
            self.status_label.setText("Status: ✗ Load error")

    def _apply_broadcast(self):
        try:
            logger.info("Broadcasting config to all tabs", category="Config")
            self.config_loaded.emit()
            self.status_label.setText("Status: ✓ Applied")
            logger.info("Config broadcast completed", category="Config")
        except Exception as e:
            logger.exception(f"Failed to broadcast config: {e}", category="Config")
            self.status_label.setText("Status: ✗ Apply error")

                                        
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
                                                  
            if getattr(self.CFG, "current_config_name", "") == cur:
                try: setattr(self.CFG, "current_config_name", new)
                except: pass
            self.refresh_config_list()
                                           
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
                                            
            if getattr(self.CFG, "current_config_name", "") == cur:
                try: setattr(self.CFG, "current_config_name", "")
                except: pass
            self.refresh_config_list()
            self.status_label.setText(f"Status: ✓ Deleted '{cur}'")
        except Exception as e:
            print(f"[ConfigTab] delete error: {e}")
            self.status_label.setText("Status: ✗ Delete error")

                                         
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
        if not name:
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

                                  
    def open_config_folder(self):
        path = os.path.abspath(self._configs_dir())
        try:
            os.makedirs(path, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(path)        
            elif sys.platform == "darwin":
                import subprocess; subprocess.Popen(["open", path])
            else:
                import subprocess; subprocess.Popen(["xdg-open", path])
        except Exception as e:
            print(f"[ConfigTab] open folder error: {e}")

                                    
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
        name = getattr(self.CFG, "current_config_name", "") or self.active_combo.currentText().strip()
        if not name:
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

                                   
    def refresh_ui(self):
        # Lightweight refresh only when config_loaded signal fires
        pass

    # ---------- handlers ----------
    def _on_active_changed(self, text: str):
        """Handle active dropdown selection."""
        if not text:
            return
        try:
            setattr(self.CFG, "current_config_name", text)
        except:
            pass
        idx = self.config_list.findText(text)
        if idx >= 0:
            self.config_list.setCurrentIndex(idx)
        self.status_label.setText(f"Status: Active = '{text}'")

                                      
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

class ConsoleTab(QWidget):
    def __init__(self):
        super().__init__()
        # Cross-tab references
        self.CFG = globals().get("cfg", None) or globals().get("Config", None)
        self.execfw = None  # will try to access ExecutionTab's framework at runtime
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
        
        # Register with global logger
        try:
            global logger
            logger.set_console_tab(self)
            logger.log_signal.connect(self._on_log_signal)
            self._log("[OK] Console registered with global logger")
        except Exception as e:
            self._log(f"[WARN] Failed to register with logger: {e}")

                              
    def _create_group_box(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet(""" QGroupBox { background-color: #151520; border-top: 1px solid #FFFFFF; border-left: 1px solid #FFFFFF; border-right: 1px solid #404040; border-bottom: 1px solid #404040; margin-top: 8px; padding-top: 8px; font-weight: bold; color: #f5f5f7; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; background-color: #151520; } """)
        return g

    def _init_ui(self):
        # Scroll shell (match other tabs)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color:#151520; border:none; }")

        content = QWidget(); content.setStyleSheet("background-color:#151520;")
        root = QVBoxLayout(content); root.setSpacing(8); root.setContentsMargins(8,8,8,8)

                
        hdr = QHBoxLayout()
        title = QLabel("Console")
        title.setStyleSheet("font-weight:bold; color:#f5f5f7;")
        self.status = QLabel("Status: Ready")
        self.status.setStyleSheet("color:#f5f5f7; ")
        hdr.addWidget(title); hdr.addStretch(1); hdr.addWidget(self.status)
        root.addLayout(hdr)

                      
        out_g = self._create_group_box("Output")
        out_l = QVBoxLayout(out_g); out_l.setSpacing(6)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet(""" QTextEdit { background: #0f0f14; color: #e6e6e9; border: 1px solid #2b2b3c; font-family: Consolas, monospace; padding: 6px; selection-background-color: #ff3b4a; selection-color: #ffffff; } """)
        out_l.addWidget(self.output)
        root.addWidget(out_g)

                       
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

                     
        in_g = self._create_group_box("Command")
        in_l = QVBoxLayout(in_g); in_l.setSpacing(6)

                                  
        row = QHBoxLayout(); row.setSpacing(6)
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Enter command (help for list)…")
        self.input_line.returnPressed.connect(self._on_enter)
        self.input_line.textEdited.connect(self._on_text_edited)
        self.input_line.installEventFilter(self)                           
        row.addWidget(self.input_line, 1)

        btn_run = QPushButton("Run")
        btn_run.clicked.connect(self._on_enter)
        row.addWidget(btn_run, 0)
        in_l.addLayout(row)

                         
        self.cmd_status = QLabel("Examples: get FOV  |  set FOV 110  |  toggle aimbot_enabled")
        self.cmd_status.setStyleSheet("color:#f5f5f7; ")
        in_l.addWidget(self.cmd_status)

        root.addWidget(in_g)

        root.addStretch(1)
        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)

                          
        from PyQt5.QtWidgets import QListWidget
        self.completion = QListWidget()
        self.completion.setWindowFlags(self.completion.windowFlags() | Qt.Popup)
        self.completion.itemClicked.connect(self._completion_pick)
        self.completion.setStyleSheet(""" QListWidget { background:#FFFFFF; color:#f5f5f7; border:1px solid #000; font-family:Consolas; } QListWidget::item { padding:2px 6px; } QListWidget::item:selected { background:#C0D0FF; } """)

        self._log("[OK] Console initialized")

                                                               
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

                                      
    def _build_known_cmds(self):
        base = {
            "help", "get", "set", "toggle", "list",
            "start", "stop", "threads",
            "panic", "reload_offsets", "restart_features",
            "bind", "unbind", "gfx"
        }
                                                                   
        try:
            for k in dir(self.CFG):
                if not k.startswith("_"):
                    base.add(k)
        except Exception:
            pass
        self._known_cmds = base

    def _on_text_edited(self, _s):
                                                         
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

                                   
    def _log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.output.append(f"[{ts}] {text}")
        self.output.moveCursor(self.output.textCursor().End)
    
    def _on_log_signal(self, level, message):
        """Receive log from global logger (thread-safe via signal)."""
        try:
            # Color-code by level
            if level in ("ERROR", "CRITICAL", "EXCEPTION"):
                color_msg = f'<span style="color: red;">{message}</span>'
            elif level == "WARNING":
                color_msg = f'<span style="color: orange;">{message}</span>'
            elif level == "DEBUG":
                color_msg = f'<span style="color: gray;">{message}</span>'
            else:
                color_msg = message
            
            ts = time.strftime("%H:%M:%S")
            self.output.append(f"[{ts}] {color_msg}")
            self.output.moveCursor(self.output.textCursor().End)
        except Exception as e:
            print(f"[ConsoleTab] Error handling log signal: {e}")

    def _set_status(self, txt: str):
        self.status.setText(f"Status: {txt}")

                                  
    def _handle(self, line: str):
        self._log(f"> {line}")
        try:
            parts = line.split()
            if not parts: return
            cmd, args = parts[0].lower(), parts[1:]

                  
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

                                                    
            if cmd == "gfx":
                if self.execfw:
                    return self.execfw.handle(line)
                else:
                    return self._log("[ERR] Exec framework not available (open Execution tab)")

            self._log(f"[ERR] Unknown command '{cmd}'. Type 'help'.")

        except Exception as e:
            self._log(f"[ERR] {e}")

                                         
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
                            
            try:
                import json
                v = json.loads(text)
                return typ(v) if typ is tuple else v
            except Exception:
                                             
                parts = [p for p in text.replace(",", " ").split() if p]
                return typ(parts) if typ is tuple else parts
                         
        return text

    # public hook for tab refreshes
    def refresh_ui(self):
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

class ESPTab(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_elements = {"checkboxes": {}, "sliders": {}, "comboboxes": {}, "color_buttons": {}, "labels": {}}
        self.init_ui()

                                                 
    def create_group_box(self, title: str) -> QGroupBox:
        """Create a Win95-style group box"""
        group = QGroupBox(title)
        group.setStyleSheet(""" QGroupBox { background-color: #151520; border-top: 1px solid #FFFFFF; border-left: 1px solid #FFFFFF; border-right: 1px solid #404040; border-bottom: 1px solid #404040; margin-top: 8px; padding-top: 8px; font-weight: bold; color: #f5f5f7; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; background-color: #151520; } """)
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
        lbl.setStyleSheet("color: #f5f5f7; ")
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
        lbl.setStyleSheet("color: #f5f5f7; ")
        
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

    def add_color_section(self, parent_layout, title, colors):
        section = QGroupBox(title)
        section.setStyleSheet("""
            QGroupBox {
                background-color: #11111a;
                border: 1px solid #303040;
                margin-top: 6px;
                padding-top: 6px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 6px;
                padding: 0 4px;
            }
        """)

        grid = QGridLayout(section)
        grid.setSpacing(6)

        for i, (label, attr, default) in enumerate(colors):
            self.add_color_picker_to_grid(
                grid, i // 3, i % 3, label, attr, default
            )

        parent_layout.addWidget(section)

    def add_color_picker_to_grid(self, grid, row, col, label, cfg_key, default=(255, 255, 255)):
        rgb = getattr(Config, cfg_key, default)
        
        item_layout = QHBoxLayout()
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet("color: #f5f5f7; ")
        lbl.setFixedWidth(80)
        item_layout.addWidget(lbl)
        
        btn = QPushButton()
        btn.setObjectName("espColorButton")  # <- important
        btn.setFixedSize(16, 16)             # base size, QSS will enforce it
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

                                            
    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #151520; border: none; }")

        content = QWidget()
        content.setStyleSheet("background-color: #151520;")
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

                                     
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
                     
        team_group = self.create_group_box("Team Filter")
        team_layout = QVBoxLayout(team_group)
        team_layout.setSpacing(3)
        self.add_checkbox(team_layout, "Enemy Only", "esp_show_enemies_only")
        self.add_checkbox(team_layout, "Team Only", "esp_show_team_only")
        team_layout.addStretch()
        
                        
        panic_group = self.create_group_box("Panic Settings")
        panic_layout = QVBoxLayout(panic_group)
        panic_layout.setSpacing(3)
        
        panic_lbl = QLabel(f"Key: {vk_to_name(getattr(Config, 'panic_key', 0x7B))}")
        panic_lbl.setStyleSheet("color: #f5f5f7; ")
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
            ("World ESP", "world_esp_enabled"),
        ]
        for i, (label, attr) in enumerate(features):
            self.add_checkbox_to_grid(basic_grid, i // 3, i % 3, label, attr)
        
        basic_layout.addLayout(basic_grid)
        self.add_combobox(basic_layout, "Box Style:", ["normal", "rounded", "corner"], "box_esp_style")
        basic_layout.addStretch()
        layout.addWidget(basic_group)

                                       
        row2 = QHBoxLayout()
        row2.setSpacing(8)
                    
        vis_group = self.create_group_box("Visibility ESP")
        vis_layout = QVBoxLayout(vis_group)
        vis_layout.setSpacing(3)
        self.add_checkbox(vis_layout, "Enable Visibility", "visibility_esp_enabled")
        self.add_checkbox(vis_layout, "Show Vis Text", "visibility_text_enabled")
        vis_layout.addStretch()
        
        row2.addWidget(vis_group, 1)
        layout.addLayout(row2)

                                       
        adv_group = self.create_group_box("Advanced ESP Features")
        adv_layout = QVBoxLayout(adv_group)
        adv_layout.setSpacing(3)
        
        adv_grid = QGridLayout()
        adv_grid.setSpacing(4)
        adv_features = [
            ("Dead Players", "draw_dead_entities"),
            ("Flash ESP", "flash_esp_enabled"),
            ("Scope ESP", "scope_esp_enabled"),
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

                                      
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        
                   
        cross_group = self.create_group_box("Crosshair")
        cross_layout = QVBoxLayout(cross_group)
        cross_layout.setSpacing(3)
        self.add_checkbox(cross_layout, "Enable Crosshair", "draw_crosshair_enabled")
        self.add_slider(cross_layout, "Size", "crosshair_size", 1, 20)
        cross_layout.addStretch()
        
                  
        line_group = self.create_group_box("Line ESP")
        line_layout = QVBoxLayout(line_group)
        line_layout.setSpacing(3)
        self.add_checkbox(line_layout, "Enable Line ESP", "line_esp_enabled")
        self.add_combobox(line_layout, "Position:", ["top", "bottom"], "line_esp_position")
        line_layout.addStretch()
        
        row3.addWidget(cross_group, 1)
        row3.addWidget(line_group, 1)
        layout.addLayout(row3)

                                  
        row4 = QHBoxLayout()
        row4.setSpacing(8)
        
                  
        bone_group = self.create_group_box("Bone Dot ESP")
        bone_layout = QVBoxLayout(bone_group)
        bone_layout.setSpacing(3)
        self.add_checkbox(bone_layout, "Enable Bone Dots", "bone_dot_esp_enabled")
        self.add_slider(bone_layout, "Dot Size", "bone_dot_size", 1, 20)
        bone_layout.addStretch()
        
                       
        size_group = self.create_group_box("Head ESP")
        size_layout = QVBoxLayout(size_group)
        size_layout.setSpacing(3)

        # --- Head ESP Toggle (fixed: no default= param) ---
        self.add_checkbox(size_layout, "Enable Head ESP", "head_esp_enabled")

        # --- Head ESP Size Slider ---
        self.add_slider(size_layout, "Head ESP Size", "head_esp_size", 1, 50)

        size_layout.addStretch()

        
        row4.addWidget(bone_group, 1)
        row4.addWidget(size_group, 1)
        layout.addLayout(row4)

                                
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

                            
        colors_group = self.create_group_box("ESP Colors")
        colors_layout = QVBoxLayout(colors_group)
        colors_layout.setSpacing(8)

        # --------------------------------------------------
        # Box ESP (Base)
        # --------------------------------------------------
        self.add_color_section(colors_layout, "Box ESP", [
            ("Box (T)", "color_box_t", (255, 180, 0)),
            ("Box (CT)", "color_box_ct", (100, 200, 255)),
        ])

        # --------------------------------------------------
        # Box ESP (Visibility)
        # --------------------------------------------------
        self.add_color_section(colors_layout, "Box ESP – Visibility", [
            ("Visible (T)", "color_box_visible_t", (255, 200, 0)),
            ("Hidden (T)", "color_box_invisible_t", (120, 70, 0)),
            ("Visible (CT)", "color_box_visible_ct", (0, 200, 255)),
            ("Hidden (CT)", "color_box_invisible_ct", (0, 70, 120)),
        ])

        # --------------------------------------------------
        # Skeleton ESP
        # --------------------------------------------------
        self.add_color_section(colors_layout, "Skeleton ESP", [
            ("Bone", "color_bone", (255, 255, 255)),
            ("Bone Dot", "bone_dot_color", (255, 0, 255)),
        ])

        # --------------------------------------------------
        # Skeleton ESP (Visibility)
        # --------------------------------------------------
        self.add_color_section(colors_layout, "Skeleton ESP – Visibility", [
            ("Visible (T)", "color_skeleton_visible_t", (255, 200, 0)),
            ("Hidden (T)", "color_skeleton_invisible_t", (120, 70, 0)),
            ("Visible (CT)", "color_skeleton_visible_ct", (0, 200, 255)),
            ("Hidden (CT)", "color_skeleton_invisible_ct", (0, 70, 120)),
        ])

        # --------------------------------------------------
        # Text & HUD
        # --------------------------------------------------
        self.add_color_section(colors_layout, "Text & HUD", [
            ("Name", "color_name", (255, 255, 255)),
            ("Name FX", "color_name_effects", (255, 215, 0)),
            ("HP Text", "color_hp_text", (0, 255, 0)),
            ("Armor Text", "color_armor_text", (0, 0, 255)),
            ("Distance", "color_distance", (255, 255, 255)),
            ("Weapon", "color_weapon_text", (255, 255, 255)),
            ("Money", "color_money_text", (0, 255, 255)),
        ])

        # --------------------------------------------------
        # Visibility Text
        # --------------------------------------------------
        self.add_color_section(colors_layout, "Visibility Text", [
            ("Visible", "color_visible_text", (0, 255, 0)),
            ("Hidden", "color_not_visible_text", (255, 0, 0)),
        ])

        # --------------------------------------------------
        # Movement / Utility
        # --------------------------------------------------
        self.add_color_section(colors_layout, "Movement & Utility", [
            ("Velocity Text", "velocity_text_color", (255, 255, 255)),
            ("Velocity ESP", "velocity_esp_color", (255, 255, 0)),
            ("Speed ESP", "speed_esp_color", (0, 255, 255)),
            ("Coordinates", "coordinates_esp_color", (255, 255, 255)),
            ("Trace ESP", "trace_esp_color", (255, 0, 255)),
        ])

        # --------------------------------------------------
        # Misc
        # --------------------------------------------------
        self.add_color_section(colors_layout, "Misc", [
            ("Crosshair", "crosshair_color", (255, 255, 255)),
            ("Flash / Scope", "color_flash_scope", (255, 255, 0)),
            ("Spectators", "color_spectators", (180, 180, 180)),
        ])

        # --------------------------------------------------
        # Dead Players
        # --------------------------------------------------
        self.add_color_section(colors_layout, "Dead Players", [
            ("Dead CT", "color_dead_ct", (0, 0, 128)),
            ("Dead T", "color_dead_t", (128, 0, 0)),
        ])

        layout.addWidget(colors_group)


        layout.addStretch()
        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

                                                   
    def update_panic_key(self, key, label, btn):
        vk = key_to_vk(key)
        setattr(Config, "panic_key", vk)
        label.setText(f"Key: {key}")
        btn.setText("Set Panic Key")
        btn.setEnabled(True)

                                                 
    def refresh_ui(self):
                    
        for k, cb in self.ui_elements["checkboxes"].items():
            cb.setChecked(getattr(Config, k, False))
                 
        for k, (s, l) in self.ui_elements["sliders"].items():
            v = getattr(Config, k, 1)
            s.setValue(v)
            l.setText(f"{k.replace('_',' ').title()}: {v}")
                    
        for k, c in self.ui_elements["comboboxes"].items():
            current = getattr(Config, k, "")
            idx = c.findText(current)
            if idx >= 0:
                c.setCurrentIndex(idx)
                
        for k, b in self.ui_elements["color_buttons"].items():
            rgb = getattr(Config, k, (255, 255, 255))
            b.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid black;")
               
        if "panic_key" in self.ui_elements["labels"]:
            vk = getattr(Config, "panic_key", 0x7B)
            self.ui_elements["labels"]["panic_key"].setText(f"Key: {vk_to_name(vk)}")

class KeyListenerThread(QThread):
    key_pressed = pyqtSignal(str)

    def run(self):
        key = keyboard.read_event(suppress=True)
        if key.event_type == keyboard.KEY_DOWN:
            self.key_pressed.emit(key.name)

class AnimatedTabWidget(QTabWidget):
    def __init__(self, duration=900, parent=None):
        super().__init__(parent)
        self.duration = duration

        self._fade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fade)

        self._anim = QPropertyAnimation(self._fade, b"opacity", self)
        self._anim.setDuration(self.duration)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)


        self.currentChanged.connect(self._animate)

    def _animate(self, idx):
        self._fade.setOpacity(0.0)
        self._anim.stop()
        self._anim.start()

class MainWindow(QWidget):
    def __init__(self):
        logger.info("Initializing MainWindow", category="UI")
        super().__init__()
        try:
            self.setWindowTitle("GFusion V3.6")
            self.setGeometry(100, 100, 950, 700)
            self.setMinimumSize(600, 450)
            logger.debug("Window geometry set", category="UI")

            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            # Enable hover tracking so edge-resize cursors work on a frameless window
            self.setMouseTracking(True)

            logger.debug("Window flags configured", category="UI")

            root = QVBoxLayout(self)
            root.setContentsMargins(1, 1, 1, 1)
            root.setSpacing(0)

            self.outer = QFrame()
            self.outer.setObjectName("outerPanel")
            outerL = QVBoxLayout(self.outer)
            outerL.setContentsMargins(2, 2, 2, 2)
            outerL.setSpacing(2)
            logger.debug("Layout structure created", category="UI")

            # Tabs with LAZY LOADING - only create when first accessed
            logger.info("Initializing lazy-loaded tab system", category="UI")
            
            # Tab cache (None = not yet created)
            self._aimbot_tab = None
            self._trigger_tab = None
            self._esp_tab = None
            self._misc_tab = None
            self._config_tab = None
            self._recoil_tab = None
            self._console_tab = None
            
            # Create placeholder widgets for tabs
            self.tabs = AnimatedTabWidget(duration=220)
            self.tabs.addTab(self._create_placeholder("Aimbot"), "Aimbot")
            self.tabs.addTab(self._create_placeholder("Trigger"), "Trigger")
            self.tabs.addTab(self._create_placeholder("ESP"), "ESP")
            self.tabs.addTab(self._create_placeholder("Misc"), "Misc")
            self.tabs.addTab(self._create_placeholder("Config"), "Config")
            self.tabs.addTab(self._create_placeholder("Recoil"), "Recoil")
            self.tabs.addTab(self._create_placeholder("Console"), "Console")
            
            # Connect tab change to lazy loader
            self.tabs.currentChanged.connect(self._on_tab_changed)
            
            logger.info("Tab placeholders created (lazy loading enabled)", category="UI")

            # Defer signal connection until config tab is created
            self._config_signal_connected = False
            logger.debug("Config signal will be connected when tab is loaded", category="UI")

            outerL.addWidget(self.tabs, 1)

            # Bottom row with a flat "Exit" like classic dialogs
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

            self.setStyleSheet(self._build_helios_qss())

            # Run a short welcome fade-in the first time the menu opens
            QTimer.singleShot(0, self._run_startup_animation)

            # Set OBS protection after a short delay
            QTimer.singleShot(100, lambda: self.set_obs_protection(
                bool(getattr(Config, "obs_protection_enabled", False))
            ))
            # Load first tab after window is shown (deferred)
            QTimer.singleShot(10, lambda: self._on_tab_changed(0))
            
        except Exception as e:
            logger.error(f"Error initializing MainWindow: {e}", category="UI", exc_info=True)
            raise

    def _build_helios_qss(self) -> str:
        """
        Additional window-level styling. Most of the look comes from _apply_global_qss.
        This only defines a few object-specific tweaks if needed.
        """
        return """
        #outerPanel {
            background-color: #151520;
            border-radius: 14px;
            border: 1px solid #26263a;
        }
        """

                                                                              
    def set_obs_protection(self, enabled: bool):
        hwnd = int(self.winId())                                      
        mode = WDA_EXCLUDEFROMCAPTURE if enabled else WDA_NONE
        success = SetWindowDisplayAffinity(hwnd, mode)
        if not success:
            print(f"[OBS Protection] Failed to apply mode={mode} to window")

                                                                              
    
    # -------------------------
    # Frameless window: drag + resize
    # -------------------------
    _RESIZE_MARGIN = 8  # px grab area along the edges

    def _hit_test_edges(self, pos):
        """Return a string describing which edge(s) the mouse is on (e.g. 'L', 'RB', 'LT')."""
        r = self.rect()
        m = getattr(self, "_RESIZE_MARGIN", 8)

        left = pos.x() <= m
        right = pos.x() >= (r.width() - m)
        top = pos.y() <= m
        bottom = pos.y() >= (r.height() - m)

        d = ""
        if left:
            d += "L"
        elif right:
            d += "R"
        if top:
            d += "T"
        elif bottom:
            d += "B"
        return d

    def _cursor_for_dir(self, d):
        # Corners first
        if d in ("LT", "RB"):
            return Qt.SizeFDiagCursor
        if d in ("RT", "LB"):
            return Qt.SizeBDiagCursor
        if d in ("L", "R"):
            return Qt.SizeHorCursor
        if d in ("T", "B"):
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            # Prefer resize when clicking edges/corners
            d = self._hit_test_edges(e.pos())
            if d:
                self._resize_active = True
                self._resize_dir = d
                self._resize_start_pos = e.globalPos()
                self._resize_start_geo = self.geometry()
                e.accept()
                return

            # Otherwise: normal drag move
            self._drag_active = True
            self._drag_start_pos = e.globalPos()
            e.accept()
            return

        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        # Active resize
        if getattr(self, "_resize_active", False):
            d = getattr(self, "_resize_dir", "")
            start_geo = getattr(self, "_resize_start_geo", self.geometry())
            start_pos = getattr(self, "_resize_start_pos", e.globalPos())

            delta = e.globalPos() - start_pos
            dx, dy = delta.x(), delta.y()

            x = start_geo.x()
            y = start_geo.y()
            w = start_geo.width()
            h = start_geo.height()

            min_w = self.minimumWidth() if self.minimumWidth() > 0 else 100
            min_h = self.minimumHeight() if self.minimumHeight() > 0 else 100

            # Horizontal resize
            if "L" in d:
                new_w = max(min_w, w - dx)
                x = x + (w - new_w)
                w = new_w
            elif "R" in d:
                w = max(min_w, w + dx)

            # Vertical resize
            if "T" in d:
                new_h = max(min_h, h - dy)
                y = y + (h - new_h)
                h = new_h
            elif "B" in d:
                h = max(min_h, h + dy)

            self.setGeometry(x, y, w, h)
            e.accept()
            return

        # Active drag
        if getattr(self, "_drag_active", False):
            delta = e.globalPos() - self._drag_start_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._drag_start_pos = e.globalPos()
            e.accept()
            return

        # Hover cursor update (only when not resizing/dragging)
        d = self._hit_test_edges(e.pos())
        cur = self._cursor_for_dir(d)
        self.setCursor(cur)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        # Reset cursor when leaving window
        try:
            if not getattr(self, "_resize_active", False) and not getattr(self, "_drag_active", False):
                self.unsetCursor()
        finally:
            super().leaveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_active = False
            self._drag_start_pos = None
            self._resize_active = False
            self._resize_dir = ""
            self._resize_start_pos = None
            self._resize_start_geo = None
            self.unsetCursor()
            e.accept()
            return

        super().mouseReleaseEvent(e)

    def exit_app(self):

        stop_aimbot_thread()
        stop_bhop_thread()
        stop_glow_thread()
        stop_triggerbot_thread()
        QApplication.quit()

    def _create_placeholder(self, name):
        """Create a simple placeholder widget for lazy-loaded tabs."""
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(f"Loading {name} tab...")
        label.setStyleSheet("color: #f5f5f7; ")
        layout.addWidget(label)
        return placeholder
    
    def _on_tab_changed(self, index):
        """Lazy load tab when it's first accessed."""
        try:
            tab_names = ["aimbot", "trigger", "esp", "misc", "config", "recoil", "console"]
            if index < 0 or index >= len(tab_names):
                return
            
            tab_name = tab_names[index]
            cache_attr = f"_{tab_name}_tab"
            
            # Check if already loaded
            if getattr(self, cache_attr) is not None:
                return
            
            logger.info(f"Lazy loading {tab_name} tab", category="UI")
            
            # Create the actual tab
            if tab_name == "aimbot":
                self._aimbot_tab = AimbotTab()
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self._aimbot_tab, "Aimbot")
            elif tab_name == "trigger":
                self._trigger_tab = TriggerBotTab()
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self._trigger_tab, "Trigger")
            elif tab_name == "esp":
                self._esp_tab = ESPTab()
                self._esp_tab.main_window = self
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self._esp_tab, "ESP")
            elif tab_name == "misc":
                self._misc_tab = MiscTab()
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self._misc_tab, "Misc")
            elif tab_name == "config":
                self._config_tab = ConfigTab()
                # Connect config_loaded signal now
                if not self._config_signal_connected:
                    self._config_tab.config_loaded.connect(self.refresh_all_tabs_on_config_load)
                    self._config_signal_connected = True
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self._config_tab, "Config")
            elif tab_name == "recoil":
                self._recoil_tab = RecoilViewer()
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self._recoil_tab, "Recoil")
            elif tab_name == "console":
                self._console_tab = ConsoleTab()
                # Console tab registers itself with logger in __init__
                self.tabs.removeTab(index)
                self.tabs.insertTab(index, self._console_tab, "Console")
            
            # Set the tab to be current again
            self.tabs.setCurrentIndex(index)
            logger.debug(f"{tab_name} tab loaded successfully", category="UI")
            
        except Exception as e:
            logger.error(f"Error lazy loading tab {index}: {e}", category="UI", exc_info=True)
    
    # Property accessors for backward compatibility
    @property
    def aimbot_tab(self):
        if self._aimbot_tab is None:
            self._on_tab_changed(0)
        return self._aimbot_tab
    
    @property
    def trigger_tab(self):
        if self._trigger_tab is None:
            self._on_tab_changed(1)
        return self._trigger_tab
    
    @property
    def esp_tab(self):
        if self._esp_tab is None:
            self._on_tab_changed(2)
        return self._esp_tab
    
    @property
    def misc_tab(self):
        if self._misc_tab is None:
            self._on_tab_changed(3)
        return self._misc_tab
    
    @property
    def config_tab(self):
        if self._config_tab is None:
            self._on_tab_changed(4)
        return self._config_tab
    
    @property
    def recoil_tab(self):
        if self._recoil_tab is None:
            self._on_tab_changed(5)
        return self._recoil_tab
    
    @property
    def console_tab(self):
        if self._console_tab is None:
            self._on_tab_changed(6)
        return self._console_tab
    
    def refresh_all_tabs_on_config_load(self):
        """Refresh all tab UIs when config is loaded/applied."""
        logger.info("Refreshing all tabs after config load", category="UI")
        try:
            tab_names = []
            # Only refresh tabs that have been loaded
            for tab_name in ["aimbot", "trigger", "esp", "misc", "recoil", "console"]:
                cache_attr = f"_{tab_name}_tab"
                tab = getattr(self, cache_attr)
                if tab is not None and hasattr(tab, "refresh_ui") and callable(getattr(tab, "refresh_ui")):
                    try:
                        logger.debug(f"Refreshing {tab_name}", category="UI")
                        tab.refresh_ui()
                        tab_names.append(tab_name)
                    except Exception as e:
                        logger.error(f"Error refreshing {tab_name}: {e}", category="UI", exc_info=True)
            logger.info(f"Refreshed {len(tab_names)} loaded tabs: {', '.join(tab_names)}", category="UI")
        except Exception as e:
            logger.exception("Error in refresh_all_tabs_on_config_load", category="UI")

    def _run_startup_animation(self):
        """
        Simple fade-in welcome overlay at launch.
        Does nothing if it has already been shown once.
        """
        if getattr(self, "_startup_animation_done", False):
            return
        self._startup_animation_done = True

        try:
            from PyQt5.QtWidgets import QLabel, QGraphicsOpacityEffect, QWidget, QVBoxLayout
        except Exception:
            return

        overlay = QWidget(self.outer)
        overlay.setObjectName("startupOverlay")
        overlay.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(overlay)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(6)

        title = QLabel("GFusion V3.6.3")
        title.setObjectName("startupTitle")
        subtitle = QLabel("External Cheat by Cr0mb & SameOldMistakes")
        subtitle.setObjectName("startupSubtitle")

        title.setAlignment(Qt.AlignCenter)
        subtitle.setAlignment(Qt.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch(1)

        overlay.setGeometry(self.outer.rect())
        overlay.raise_()
        overlay.show()

        effect = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)

        fade_in = QPropertyAnimation(effect, b"opacity", overlay)
        fade_in.setDuration(1400)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)

        fade_out = QPropertyAnimation(effect, b"opacity", overlay)
        fade_out.setDuration(700)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InCubic)

        def start_fade_out():
            fade_out.start()

        def cleanup():
            overlay.hide()
            overlay.deleteLater()

        fade_in.finished.connect(start_fade_out)
        fade_out.finished.connect(cleanup)
        fade_in.start()


class MiscTab(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_elements = {"color_buttons": {}}
        self.init_ui()

                                   
    def section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; color: #f5f5f7;")
        return lbl

    def add_separator(self, layout: QVBoxLayout):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #808080; max-height: 1px;")
        layout.addWidget(sep)

                                      
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
                              
        if len(rgba_tuple) == 3:
            r, g, b = rgba_tuple
            a = 255
        else:
            r, g, b, a = rgba_tuple[:4]

                                          
        try:
            rf, gf, bf = float(r), float(g), float(b)
            is_norm = (0.0 <= rf <= 1.0) and (0.0 <= gf <= 1.0) and (0.0 <= bf <= 1.0)
        except Exception:
            is_norm = False

        if is_norm:
            r, g, b = rf * 255.0, gf * 255.0, bf * 255.0

                                         
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
        lbl.setStyleSheet("color: #f5f5f7; ")
        row.addWidget(lbl)

        rgb = self._sanitize_rgb3(getattr(Config, cfg_key, default))
        btn = QPushButton()
        btn.setFixedSize(40, 18)
        btn.setStyleSheet(self.rgb_to_stylesheet_safe(rgb))

        def choose_color():
            current = self._sanitize_rgb3(getattr(Config, cfg_key, default))
            initial = QColor(*current)                    
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
        group.setStyleSheet(""" QGroupBox { background-color: #151520; border-top: 1px solid #FFFFFF; border-left: 1px solid #FFFFFF; border-right: 1px solid #404040; border-bottom: 1px solid #404040; margin-top: 8px; padding-top: 8px; font-weight: bold; color: #f5f5f7; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; background-color: #151520; } """)
        return group

                              
    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(""" QScrollArea { background-color: #151520; border: none; } """)

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #151520;")
        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

                                       
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        
                     
        fov_group = self.create_group_box("FOV Changer")
        fov_layout = QVBoxLayout(fov_group)
        fov_layout.setSpacing(4)
        
        self.fov_checkbox = self.add_checkbox(
            fov_layout, "Enable FOV Changer", "fov_changer_enabled",
            default=True, thread_start=start_fov_thread, thread_stop=stop_fov_thread
        )
        self.fov_label = QLabel(f"Game FOV: {cfg.game_fov}")
        self.fov_label.setStyleSheet("color: #f5f5f7; ")
        self.fov_slider = NoScrollSlider(Qt.Horizontal)
        self.fov_slider.setRange(60, 150)
        self.fov_slider.setValue(cfg.game_fov)
        self.fov_slider.valueChanged.connect(self.update_fov)
        fov_layout.addWidget(self.fov_label)
        fov_layout.addWidget(self.fov_slider)
        fov_layout.addStretch()
        
                      
        glow_group = self.create_group_box("Glow Effects")
        glow_layout = QVBoxLayout(glow_group)
        glow_layout.setSpacing(4)

        self.glow_checkbox = self.add_checkbox(
            glow_layout, "Enable Glow", "glow",
            default=False, thread_start=start_glow_thread, thread_stop=stop_glow_thread
        )
        self.add_checkbox(glow_layout, "Glow Enemies", "glow_show_enemies", default=True)
        self.add_checkbox(glow_layout, "Glow Team", "glow_show_team", default=True)

        # --- Glow colors with small square buttons ---
        glow_color_items = [
            ("Enemy Color", "glow_color_enemy", (255, 0, 0)),
            ("Team Color", "glow_color_team", (0, 255, 0)),
        ]

        for label, key, default in glow_color_items:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #f5f5f7; ")
            lbl.setFixedWidth(80)
            row.addWidget(lbl)

            rgb = self._sanitize_rgb3(getattr(Config, key, default))
            btn = QPushButton()
            btn.setObjectName("espColorButton")      # reuse the tiny square style
            btn.setFixedSize(16, 16)                 # square base size
            btn.setStyleSheet(self.rgb_to_stylesheet_safe(rgb))

            def make_glow_color_callback(cfg_key, button, default_val):
                def choose():
                    current = self._sanitize_rgb3(getattr(Config, cfg_key, default_val))
                    initial = QColor(*current)
                    color = QColorDialog.getColor(initial, self, f"Select {cfg_key}")
                    if color.isValid():
                        new_rgb = (color.red(), color.green(), color.blue())
                        setattr(Config, cfg_key, new_rgb)
                        button.setStyleSheet(self.rgb_to_stylesheet_safe(new_rgb))
                return choose

            btn.clicked.connect(make_glow_color_callback(key, btn, default))
            row.addWidget(btn)
            row.addStretch()

            self.ui_elements["color_buttons"][key] = btn
            glow_layout.addLayout(row)

        glow_layout.addStretch()

        row1.addWidget(fov_group, 1)
        row1.addWidget(glow_group, 1)
        main_layout.addLayout(row1)


                                      
        bhop_group = self.create_group_box("Bunny Hop")
        bhop_main = QHBoxLayout(bhop_group)
        bhop_main.setSpacing(12)

        left_side = QVBoxLayout()
        left_side.setSpacing(4)
        self.bhop_checkbox = self.add_checkbox(
            left_side, "Enable Bunny Hop", "bhop_enabled",
            thread_start=start_bhop_thread, thread_stop=stop_bhop_thread
        )
        self.add_checkbox(left_side, "Show Info Box", "show_local_info_box", default=True)
        left_side.addStretch()

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
            lbl.setStyleSheet("color: #f5f5f7; ")
            lbl.setFixedWidth(70)
            item_layout.addWidget(lbl)

            rgb = self._sanitize_rgb3(getattr(Config, key, (0, 0, 0)))
            btn = QPushButton()
            btn.setObjectName("espColorButton")      # <- reuse the square color button style
            btn.setFixedSize(16, 16)                 # <- force it to be a small square
            btn.setStyleSheet(self.rgb_to_stylesheet_safe(rgb))

            def make_color_callback(cfg_key, button, default_val=(0, 0, 0)):
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
                                                      
        row3 = QHBoxLayout()
        row3.setSpacing(8)
        
                                
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
        
        team_group = self.create_group_box("Team List")
        team_layout = QVBoxLayout(team_group)
        team_layout.setSpacing(3)

        self.add_checkbox(team_layout, "Enable Team List", "team_list_enabled", default=True)
        self.add_checkbox(team_layout, "HP Bars", "team_list_show_hp_bars", default=True)
        self.add_checkbox(team_layout, "Alive Counts", "team_list_show_counts", default=True)
        self.add_checkbox(team_layout, "Sort by HP", "team_list_sort_by_hp", default=True)

        font_box = QHBoxLayout()
        self.team_list_font_label = QLabel(f"Size: {getattr(Config, 'team_list_font_size', 11)}")
        self.team_list_font_label.setStyleSheet("color: #f5f5f7; ")
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

        # ==========================
        # Team List Colors (patched)
        # ==========================
        colors_group = self.create_group_box("Team List Colors")
        colors_layout = QVBoxLayout(colors_group)

        colors_grid = QGridLayout()
        colors_grid.setSpacing(6)

        team_color_items = [
            ("T Header",    "color_box_t",          (255, 180, 0)),
            ("CT Header",   "color_box_ct",         (100, 200, 255)),
            ("Background",  "team_list_background", (18, 18, 22)),
            ("Border",      "team_list_border",     (70, 75, 85)),
            ("Dead T",      "team_list_dead_t",     (100, 80, 60)),
            ("Dead CT",     "team_list_dead_ct",    (60, 80, 100)),
        ]

        for idx, (label, key, default) in enumerate(team_color_items):
            row = idx // 3
            col = idx % 3

            item_layout = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #f5f5f7; ")
            lbl.setFixedWidth(80)  # small but readable
            item_layout.addWidget(lbl)

            rgb = self._sanitize_rgb3(getattr(Config, key, default))
            btn = QPushButton()
            btn.setObjectName("espColorButton")       # <- reuse tiny square style
            btn.setFixedSize(16, 16)                  # <- square base size
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


        system_group = self.create_group_box("System Controls")
        system_layout = QHBoxLayout(system_group)
        system_layout.setSpacing(12)
        
                       
        left_system = QVBoxLayout()
        offsets_label = QLabel("Offsets")
        offsets_label.setStyleSheet("font-weight: bold; color: #f5f5f7;")
        left_system.addWidget(offsets_label)
        
        self.update_offsets_btn = QPushButton("Update Offsets")
        self.update_offsets_btn.setFixedHeight(20)
        self.update_offsets_btn.setToolTip("Run Process/offset_update.py")
        self.update_offsets_btn.clicked.connect(self.update_offsets)
        left_system.addWidget(self.update_offsets_btn)
        left_system.addStretch()
        
                           
        right_system = QVBoxLayout()
        toggle_label = QLabel("Menu Toggle")
        toggle_label.setStyleSheet("font-weight: bold; color: #f5f5f7;")
        right_system.addWidget(toggle_label)
        
        self.toggle_key_label = QLabel(f"Key: {cfg.toggle_menu_key}")
        self.toggle_key_label.setStyleSheet("color: #f5f5f7; ")
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
        try:
            # Use whichever config reference is available
            CFG = globals().get("cfg", None) or globals().get("Config", None)
            if not CFG:
                print("[MiscTab] Warning: No config found during refresh")
                return
            
            # Refresh all checkboxes stored in ui_elements (not in sub-dict)
            for key, widget in self.ui_elements.items():
                if key != "color_buttons" and isinstance(widget, CheatCheckBox):
                    try:
                        widget.setChecked(bool(getattr(CFG, key, False)))
                    except Exception as e:
                        print(f"[MiscTab] Error refreshing checkbox {key}: {e}")
            
            # Refresh FOV controls
            if hasattr(self, 'fov_checkbox'):
                self.fov_checkbox.setChecked(bool(getattr(CFG, "fov_changer_enabled", True)))
            if hasattr(self, 'fov_slider'):
                fov_val = getattr(CFG, 'game_fov', 90)
                self.fov_slider.setValue(fov_val)
                self.fov_label.setText(f"Game FOV: {fov_val}")
            
            # Refresh team list font slider
            if hasattr(self, 'team_list_font_slider'):
                size = getattr(CFG, 'team_list_font_size', 11)
                self.team_list_font_slider.setValue(size)
                self.team_list_font_label.setText(f"Size: {size}")
            
            # Refresh all color buttons
            for key, btn in self.ui_elements.get("color_buttons", {}).items():
                rgb = self._sanitize_rgb3(getattr(CFG, key, (0, 0, 0)))
                btn.setStyleSheet(self.rgb_to_stylesheet_safe(rgb))
                
            print("[MiscTab] UI refreshed successfully")
        except Exception as e:
            print(f"[MiscTab] refresh_ui error: {e}")
            import traceback
            traceback.print_exc()

class NoScrollSlider(QSlider):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setFocusPolicy(Qt.StrongFocus)
        # Visual style comes from the global QSlider rules; this class just disables wheel scrolling.

    def wheelEvent(self, event):
        # Block scroll-wheel to avoid accidental value changes while scrolling the menu.
        event.ignore()

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

                       
        self.learn_dir = LEARN_DIR
        self.weapon_ids = []
        self.all_data = {}
        self._last_aimbot_plot_hash = None
        self.spray_mode = True                                                        
        self.show_grid = True
        self.show_legend = True
        self.line_width = 1.5
        self.marker_size = 2

        self._init_ui()
        self.scan_aimbot_data()

                                                            
        try:
            self.watcher_thread = DataWatcher()
            self.watcher_thread.data_updated.connect(self._on_data_updated)
            self.watcher_thread.start()
            self._watching = True
        except Exception as e:
            print(f"[RecoilViewer] Watcher not available: {e}")
            self._watching = False

                                               
    def _create_group_box(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet(""" QGroupBox { background-color: #151520; border-top: 1px solid #FFFFFF; border-left: 1px solid #FFFFFF; border-right: 1px solid #404040; border-bottom: 1px solid #404040; margin-top: 8px; padding-top: 8px; font-weight: bold; color: #f5f5f7; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; background-color: #151520; } """)
        return g

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#808080; background:#808080;")
        line.setFixedHeight(1)
        return line

                              
    def _init_ui(self):
        # === Scroll container (match other tabs) ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #151520; border: none; }")                  

        content = QWidget()
        content.setStyleSheet("background-color:#151520;")
        root = QVBoxLayout(content)
        root.setSpacing(8)
        root.setContentsMargins(8, 8, 8, 8)

                                 
        header = QHBoxLayout()
        title = QLabel("Recoil Analyzer")
        title.setStyleSheet("font-weight:bold; color:#f5f5f7;")
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color:#f5f5f7; ")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.status_label)
        root.addLayout(header)

                                                           
        top = QHBoxLayout()
        top.setSpacing(8)

                               
        src_g = self._create_group_box("Data Source")
        src = QGridLayout(src_g)
        src.setHorizontalSpacing(8)
        src.setVerticalSpacing(6)

                       
        src.addWidget(QLabel("Folder:"), 0, 0)
        self.dir_edit = QLineEdit(self.learn_dir)
        self.dir_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        reload_btn = QPushButton("Reload")
        src.addWidget(self.dir_edit, 0, 1, 1, 2)
        src.addWidget(browse_btn, 0, 3)
        src.addWidget(reload_btn, 0, 4)

                             
        src.addWidget(QLabel("Weapon:"), 1, 0)
        self.dropdown = QComboBox()
        self.dropdown.setStyleSheet(""" QComboBox { background: #FFFFFF; border: 1px solid #000000; padding: 1px 3px; min-height: 16px; } QComboBox::drop-down { width: 14px; border-left: 1px solid #000000; } QComboBox QAbstractItemView { background: #FFFFFF; color: #f5f5f7; selection-background-color: #f5f5f7; selection-color: #FFFFFF; } """)
        src.addWidget(self.dropdown, 1, 1, 1, 4)

                                 
        self.watch_cb = CheatCheckBox("Auto-Watch")
        self.watch_cb.setChecked(getattr(self, "_watching", False))
        export_btn = QPushButton("Export PNG")
        src.addWidget(self.watch_cb, 2, 1)
        src.addWidget(export_btn, 2, 4)

        top.addWidget(src_g, 3)

                           
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

                    
        dsp.addWidget(QLabel("Line W:"), 1, 0)
        self.line_slider = NoScrollSlider(Qt.Horizontal)
        self.line_slider.setMinimum(1)                   
        self.line_slider.setMaximum(40)
        self.line_slider.setValue(int(self.line_width * 10))
        self.line_label = QLabel(f"{self.line_width:.1f}")
        dsp.addWidget(self.line_slider, 1, 1)
        dsp.addWidget(self.line_label,  1, 2)

                     
        dsp.addWidget(QLabel("Marker:"), 2, 0)
        self.marker_slider = NoScrollSlider(Qt.Horizontal)
        self.marker_slider.setMinimum(1)                  
        self.marker_slider.setMaximum(50)
        self.marker_slider.setValue(int(self.marker_size * 10))
        self.marker_label = QLabel(f"{self.marker_size:.1f}")
        dsp.addWidget(self.marker_slider, 2, 1)
        dsp.addWidget(self.marker_label,  2, 2)

        top.addWidget(dsp_g, 2)
        root.addLayout(top)

                                      
        split = QHBoxLayout()
        split.setSpacing(8)

              
        self.canvas = FigureCanvas(Figure(facecolor="#C0C0C0"))
        self.ax = self.canvas.figure.add_subplot(111)
        self._style_axes()
        split.addWidget(self.canvas, 2)

                        
        stats_g = self._create_group_box("Stats")
        stats_v = QVBoxLayout(stats_g)
        stats_v.setSpacing(6)
        self.stats_scroll = QScrollArea()
        self.stats_scroll.setWidgetResizable(True)
        self.stats_scroll.setStyleSheet("QScrollArea { background-color: #202030; border: 1px solid #000000; }")
        self.stats_widget = QWidget()
        self.stats_layout = QVBoxLayout(self.stats_widget)
        self.stats_layout.setContentsMargins(6, 6, 6, 6)
        self.stats_scroll.setWidget(self.stats_widget)
        stats_v.addWidget(self.stats_scroll)
        split.addWidget(stats_g, 3)

        root.addLayout(split)
        root.addStretch(1)

                                             
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

                                      
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

                                          
    def _style_axes(self):
        self.ax.clear()
        self.ax.set_facecolor("#C0C0C0")
        self.ax.tick_params(axis="x", colors="black", labelsize=8)
        self.ax.tick_params(axis="y", colors="black", labelsize=8)
        self.ax.set_xlabel("Yaw Δ", color="black")
        self.ax.set_ylabel("Pitch Δ", color="black")

                                        
    def _on_data_updated(self):
        if getattr(self, "_watching", False):
            self.scan_aimbot_data()

    def _toggle_watch(self, st):
        self._watching = (st == Qt.Checked)
        self.status_label.setText(f"Status: {'Watching' if self._watching else 'Idle'}")

                                           
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

        # Remember current selection before scanning
        current_selection = self.dropdown.currentText() if self.dropdown.count() > 0 else None

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
            # Try to restore previous selection, otherwise use first item
            if current_selection and current_selection in self.weapon_ids:
                idx = self.weapon_ids.index(current_selection)
                self.dropdown.setCurrentIndex(idx)
                self.update_view(current_selection)
            else:
                self.dropdown.setCurrentIndex(0)
                self.update_view(self.weapon_ids[0])
        else:
            self._style_axes()
            self.ax.set_title("Trace Map", fontsize=9, color="black")
            self.ax.text(0.5, 0.5, "No data files", ha="center", va="center", color="black")
            self.canvas.draw()

                                        
    def update_view(self, weapon_id):
        self._style_axes()
        title = f"Trace Map ({weapon_id})" if weapon_id else "Trace Map"
        self.ax.set_title(title, fontsize=9, color="black")
        if self.show_grid:
            self.ax.grid(True, linestyle="--", color="#808080", alpha=0.6)

                           
        while self.stats_layout.count():
            item = self.stats_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        data = self.all_data.get(weapon_id, {}) if weapon_id else {}
        items = data.items() if isinstance(data, dict) else []

                                                 
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

                          
            dataset_header = QLabel(f"Dataset: {key}")
            dataset_header.setStyleSheet("font-weight:bold; color:#f5f5f7; margin-top:6px;")
            self.stats_layout.addWidget(dataset_header)

            self._add_stats_summary(key, vectors)

            bursts = self._split_bursts(vectors)
            if bursts:
                burst_header = QLabel(f"Burst Analysis ({key})")
                burst_header.setStyleSheet("font-weight:bold; color:#f5f5f7; margin-top:4px;")
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
        lbl.setStyleSheet(""" color:#f5f5f7; border:1px solid #000000; padding:3px; margin:3px 0; background:#FFFFFF; """)
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
        lbl.setStyleSheet("color:#f5f5f7; margin-left:8px;")
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

                                                               
    def create_group_box(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet(""" QGroupBox { background-color: #151520; border-top: 1px solid #FFFFFF; border-left: 1px solid #FFFFFF; border-right: 1px solid #404040; border-bottom: 1px solid #404040; margin-top: 8px; padding-top: 8px; font-weight: bold; color: #f5f5f7; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; background-color: #151520; } """)
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
        lab.setStyleSheet("color: #f5f5f7; ")
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
        lab.setStyleSheet("color: #f5f5f7; ")
        sld = NoScrollSlider(Qt.Horizontal)
        sld.setMinimum(min_v); sld.setMaximum(max_v); sld.setValue(val)
        def on_change(v):
            setattr(self.CFG, cfg_key, int(v))
            lab.setText(f"{label}: {int(v)}{suffix}")
        sld.valueChanged.connect(on_change)
        layout.addWidget(lab); layout.addWidget(sld)
        self.ui["sliders"][cfg_key] = (sld, lab, 1, suffix, label)
        return sld, lab

                              
    def init_ui(self):
        # Scroll container (match other tabs)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #151520; border: none; }")

        content = QWidget(); content.setStyleSheet("background-color: #151520;")
        root = QVBoxLayout(content)
        root.setSpacing(8); root.setContentsMargins(8, 8, 8, 8)

                          
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
        self.status_label.setStyleSheet("color:#f5f5f7; ")
        right.addWidget(self.status_label)

        right.addStretch(1)
        main.addLayout(right, 1)
        root.addWidget(main_g)

                                  
        key_g = self.create_group_box("Key Settings")
        key = QHBoxLayout(key_g); key.setSpacing(10)

        self.trigger_key_label = QLabel(f"Trigger Key: {getattr(self.CFG, 'trigger_key', 'mouse5')}")
        self.trigger_key_label.setStyleSheet("color:#f5f5f7; ")
        key.addWidget(self.trigger_key_label)

        self.set_key_btn = QPushButton("Set Trigger Key")
        self.set_key_btn.clicked.connect(self.set_trigger_key)
        key.addWidget(self.set_key_btn)
        key.addStretch(1)

        root.addWidget(key_g)

                              
        beh_g = self.create_group_box("Behavior")
        beh = QGridLayout(beh_g); beh.setHorizontalSpacing(12); beh.setVerticalSpacing(6)

                                      
        box1 = QVBoxLayout()
        self.add_float_slider(box1, "Cooldown (s)", "triggerbot_cooldown", 0.00, 1.00, 100, "s")
        w1 = QWidget(); w1.setLayout(box1); beh.addWidget(w1, 0, 0)

                                                              
        box2 = QVBoxLayout()
        self.add_float_slider(box2, "Reaction Delay Min (s)", "trigger_delay_min", 0.000, 0.150, 1000, "s")
        self.add_float_slider(box2, "Reaction Delay Max (s)", "trigger_delay_max", 0.000, 0.250, 1000, "s")
        w2 = QWidget(); w2.setLayout(box2); beh.addWidget(w2, 0, 1)

                                                        
        box3 = QVBoxLayout()
        self.add_float_slider(box3, "Shot Jitter (s)", "trigger_jitter", 0.000, 0.030, 1000, "s")
        self.add_int_slider(box3, "Burst Shots", "trigger_burst_shots", 1, 5)
        w3 = QWidget(); w3.setLayout(box3); beh.addWidget(w3, 0, 2)

        root.addWidget(beh_g)

                            
        safe_g = self.create_group_box("Safety")
        safe = QHBoxLayout(safe_g); safe.setSpacing(10)

                                                                               
        self.add_checkbox(safe, "Require VisCheck (if available)", "trigger_require_vischeck", default=True)

        if hasattr(self.CFG, "panic_key_enabled"):
            self.add_checkbox(safe, "Panic Key Enabled", "panic_key_enabled")

        safe.addStretch(1)
        root.addWidget(safe_g)

        root.addStretch()
        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)

                                      
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

                                
    def refresh_ui(self):
        """
        Refresh all UI elements from current config values.
        Safe against missing keys (uses defaults).
        """
        try:
            self.setUpdatesEnabled(False)
            
            # Refresh CFG reference in case it changed
            self.CFG = globals().get("cfg", None) or globals().get("Config", None)
            if not self.CFG:
                print("[TriggerBotTab] Warning: CFG not found in globals during refresh")
                return

            print(f"[TriggerBotTab] Refreshing UI with CFG={type(self.CFG).__name__}")

            # Refresh checkboxes
            for key, cb in self.ui["checkboxes"].items():
                try:
                    val = bool(getattr(self.CFG, key, False))
                    cb.blockSignals(True)
                    cb.setChecked(val)
                    cb.blockSignals(False)
                    print(f"[TriggerBotTab] Checkbox {key} set to {val}")
                except Exception as e:
                    print(f"[TriggerBotTab] Error refreshing checkbox {key}: {e}")

            # Refresh sliders
            for key, (sld, lab, mult, suffix, base_label) in self.ui["sliders"].items():
                try:
                    val = getattr(self.CFG, key, None)
                    if val is None: 
                        print(f"[TriggerBotTab] Slider {key} has no value in config")
                        continue
                    sld.blockSignals(True)
                    if mult == 1:
                        sld.setValue(int(val))
                        lab.setText(f"{base_label}: {int(val)}{suffix}")
                    else:
                        sld.setValue(int(float(val) * mult))
                        lab.setText(f"{base_label}: {float(val):.2f}{suffix}")
                    sld.blockSignals(False)
                    print(f"[TriggerBotTab] Slider {key} set to {val}")
                except Exception as e:
                    print(f"[TriggerBotTab] Error refreshing slider {key}: {e}")

            # Refresh trigger key label
            try:
                trigger_key = getattr(self.CFG, 'trigger_key', 'mouse5')
                self.trigger_key_label.setText(f"Trigger Key: {trigger_key}")
                print(f"[TriggerBotTab] Trigger key set to {trigger_key}")
            except Exception as e:
                print(f"[TriggerBotTab] Error refreshing trigger key label: {e}")
            
            print("[TriggerBotTab] UI refresh complete")

        except Exception as e:
            print(f"[TriggerBotTab] refresh_ui error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.setUpdatesEnabled(True)

                            
# Globals / Runtime Initialization
                                                       
                            
cfg = Config()

TAB_REGISTRY = []

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

esp_running = False                               

VK_CODES = {
    "delete": 0x2E,
    "f12": 0x7B,
    "end": 0x23,
    "insert": 0x2D,
                             
}

VK_NAME = {v: k.upper() for k, v in VK_CODES.items()}

LEARN_DIR = "aimbot_data"

user32 = ctypes.windll.user32

SetWindowDisplayAffinity = user32.SetWindowDisplayAffinity

SetWindowDisplayAffinity.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.DWORD]

SetWindowDisplayAffinity.restype = ctypes.wintypes.BOOL

WDA_NONE = 0x00

WDA_EXCLUDEFROMCAPTURE = 0x11

if __name__ == "__main__":
    wait_for_cs2()
    run()
