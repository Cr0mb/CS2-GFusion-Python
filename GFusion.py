                            
         
                            
import atexit
import ctypes
import sys as _sys_early
# Reconfigure stdio to UTF-8 *before* any module imports — many GFusion modules
# print emojis at import time, and the default Windows console codepage
# (cp1252) raises UnicodeEncodeError on '✓ ✗ ⚠ 🚀', aborting init mid-call.
for _s in (_sys_early.stdout, _sys_early.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
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

                            

class SectionFrame(QFrame):
    """DayZ-External / GHaxLabs style panel.

    Draws a single-pixel bordered card with a gradient header strip
    (dark→red) and a 3px red accent bar on the left of the header. Layout
    contents go below the header — the QFrame's ContentsMargins reserve
    room for it. This replaces QGroupBox to get pixel-perfect, consistent
    section headers across every tab.
    """
    HEADER_H = 24
    BORDER_C = QColor(55, 55, 60)
    HEADER_DARK = QColor(28, 22, 24)
    HEADER_RED  = QColor(70, 26, 26)
    ACCENT      = QColor(235, 60, 60)
    BODY_BG     = QColor(20, 20, 26)
    TITLE_C     = QColor(240, 234, 234)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = (title or "").upper()
        self.setObjectName("sectionFrame")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent; border: none;")
        # Reserve space for header at the top.
        self.setContentsMargins(8, self.HEADER_H + 8, 8, 8)

    def setTitle(self, t: str) -> None:
        self._title = (t or "").upper()
        self.update()

    def title(self) -> str:
        return self._title

    def paintEvent(self, ev):
        from PyQt5.QtGui import QPainter, QLinearGradient, QPen, QBrush
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        r = self.rect()

        # Body
        p.fillRect(r, self.BODY_BG)

        # Header gradient strip
        hr = r.adjusted(0, 0, 0, -(r.height() - self.HEADER_H))
        grad = QLinearGradient(hr.topLeft(), hr.topRight())
        grad.setColorAt(0.0, self.HEADER_DARK)
        grad.setColorAt(1.0, self.HEADER_RED)
        p.fillRect(hr, QBrush(grad))

        # Red accent bar (left)
        p.fillRect(0, 0, 3, self.HEADER_H, self.ACCENT)

        # Title text
        f = self.font()
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        p.setFont(f)
        p.setPen(self.TITLE_C)
        p.drawText(hr.adjusted(12, 0, -8, 0),
                   Qt.AlignVCenter | Qt.AlignLeft, self._title)

        # Outer 1px border (bottom + sides + bottom of header == card border)
        p.setPen(QPen(self.BORDER_C, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(0, 0, -1, -1))


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

    # Palette derived from the DayZ-External (GHaxLabs) ImGui theme:
    #   bg #14141a, panel #1c1c20, frame #18181c, border #37373c,
    #   accent red #eb3c3c, header strip gradient (dark→red).
    qss = f"""
    /* === Global base === */
    QWidget {{
        background-color: #14141a;
        color: #ebebeb;
        font-family: "{ff_esc}", "Segoe UI", "Inter", "Tahoma", sans-serif;
        font-size: {fs}px;
    }}

    QLabel, QCheckBox, QRadioButton, QGroupBox, QFrame {{
        background: transparent;
        border: none;
    }}
    #sectionFrame {{
        background-color: #14141a;
    }}
    QToolTip {{
        background-color: #18181e;
        color: #ebebeb;
        border: 1px solid #eb3c3c;
        padding: 4px 6px;
    }}

    /* === Outer shell === */
    #outerPanel {{
        background-color: #14141a;
        border: 1px solid #37373c;
    }}

    #headerTitle {{
        font-size: 11pt;
        font-weight: 700;
        letter-spacing: 1px;
        color: #f0eaea;
    }}
    #headerSubtitle {{
        font-size: 8pt;
        color: #8a8a90;
        letter-spacing: 0.5px;
    }}

    /* === Tabs === */
    QTabWidget::pane {{
        border: 1px solid #37373c;
        background: #14141a;
        top: -1px;
    }}
    QTabBar {{ qproperty-drawBase: 0; }}
    QTabBar::tab {{
        background: #18181c;
        padding: 6px 18px;
        margin-right: 1px;
        color: #8a8a90;
        border: 1px solid #2c2c30;
        border-bottom: none;
        min-width: 60px;
    }}
    QTabBar::tab:selected {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #2a1c1c, stop:1 #461a1a);
        color: #ffffff;
        border: 1px solid #37373c;
        border-bottom: 2px solid #eb3c3c;
    }}
    QTabBar::tab:hover:!selected {{
        background: #1f1f24;
        color: #ebebeb;
    }}

    /* === Group boxes — DayZ-style header strip === */
    QGroupBox {{
        background-color: #1c1c20;
        border: 1px solid #37373c;
        margin-top: 22px;
        padding: 10px 8px 8px 8px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 0px;
        top: 0px;
        padding: 5px 12px 5px 16px;
        color: #f0eaea;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #1c1618, stop:1 #461a1a);
        border-left: 3px solid #eb3c3c;
        border-top: 1px solid #37373c;
        border-right: 1px solid #37373c;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}

    /* === Buttons === */
    QPushButton {{
        background-color: #18181c;
        border: 1px solid #37373c;
        padding: 5px 10px;
        min-height: 20px;
        color: #ebebeb;
    }}
    QPushButton:hover {{
        background-color: #26262c;
        border-color: #eb3c3c;
    }}
    QPushButton:pressed {{
        background-color: #3c1414;
        border-color: #eb3c3c;
        color: #ffffff;
    }}
    QPushButton:disabled {{
        background-color: #101014;
        color: #5a5a60;
        border-color: #25252a;
    }}
    QPushButton:checked {{
        background-color: #3c1414;
        border-color: #eb3c3c;
        color: #ffffff;
    }}

    /* === Checkboxes === */
    QCheckBox {{ 
        spacing: 7px; 
        color: #ebebeb; 
        background: transparent;
    }}
    QCheckBox:focus {{
        border: none;
        outline: none;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid #4a4a50;
        background-color: #1c1c20;
    }}
    QCheckBox::indicator:hover {{ border-color: #eb3c3c; }}
    QCheckBox::indicator:checked {{
        background-color: #eb3c3c;
        border-color: #eb3c3c;
        image: none;
    }}
    QCheckBox::indicator:checked:hover {{
        background-color: #f54a4a;
        border-color: #f54a4a;
    }}

    /* === Radio buttons === */
    QRadioButton {{ 
        spacing: 7px; 
        color: #ebebeb; 
        background: transparent;
    }}
    QRadioButton::indicator {{
        width: 14px; height: 14px;
        border: 1px solid #4a4a50;
        background-color: #1c1c20;
        border-radius: 7px;
    }}
    QRadioButton::indicator:checked {{
        background-color: #eb3c3c;
        border-color: #eb3c3c;
    }}

    /* === Combobox & Dropdowns === */
    QComboBox, #cheatComboBox {{
        background-color: #18181c;
        border: 1px solid #37373c;
        border-radius: 0px;
        padding: 4px 10px;
        color: #ffffff;
        min-height: 24px;
        font-weight: 700;
    }}
    QComboBox:hover, #cheatComboBox:hover {{ 
        background-color: #1f1f26;
        border-color: #eb3c3c;
    }}
    QComboBox::drop-down, #cheatComboBox::drop-down {{
        border: none;
        background: #1f1f26;
        width: 24px;
        border-left: 1px solid #37373c;
    }}
    QComboBox::down-arrow, #cheatComboBox::down-arrow {{
        image: none;
        width: 0; height: 0;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid #8a8a90;
    }}
    QComboBox QAbstractItemView, #cheatComboBox QAbstractItemView {{
        background-color: #14141a;
        border: 1px solid #eb3c3c;
        color: #ffffff;
        selection-background-color: #3c1414;
        selection-color: #ffffff;
        outline: none;
    }}
    QComboBox QAbstractItemView::item, #cheatComboBox QAbstractItemView::item {{
        min-height: 28px;
        padding-left: 10px;
        background-color: #14141a;
        color: #f0eaea;
    }}
    QComboBox QAbstractItemView::item:selected, #cheatComboBox QAbstractItemView::item:selected {{
        background-color: #3c1414;
        color: #ffffff;
    }}

    /* === Sliders === */
    QSlider::groove:horizontal {{
        height: 4px;
        background: #101014;
        border: 1px solid #2a2a30;
    }}
    QSlider::sub-page:horizontal {{
        background: #eb3c3c;
        border: 1px solid #eb3c3c;
    }}
    QSlider::add-page:horizontal {{
        background: #101014;
        border: 1px solid #2a2a30;
    }}
    QSlider::handle:horizontal {{
        width: 8px;
        height: 14px;
        margin: -6px 0;
        background-color: #eb3c3c;
        border: 1px solid #ff5e5e;
    }}
    QSlider::handle:horizontal:hover {{
        background-color: #f54a4a;
        border: 1px solid #ff7070;
    }}
    QSlider::handle:horizontal:pressed {{
        background-color: #d22e2e;
    }}

    /* === Scroll areas === */
    QScrollArea {{ background: transparent; border: none; }}
    QAbstractScrollArea {{ background: transparent; }}

    /* === Scrollbars === */
    QScrollBar:vertical {{
        width: 10px;
        background: #0c0c10;
        margin: 0px;
        border-left: 1px solid #2a2a30;
    }}
    QScrollBar::handle:vertical {{
        background: #2a2a30;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #46464c; }}
    QScrollBar::handle:vertical:pressed {{ background: #5a1c1c; }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{ height: 0px; border: none; background: transparent; }}

    QScrollBar:horizontal {{
        height: 10px;
        background: #0c0c10;
        margin: 0px;
        border-top: 1px solid #2a2a30;
    }}
    QScrollBar::handle:horizontal {{
        background: #2a2a30;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: #46464c; }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{ width: 0px; border: none; background: transparent; }}

    /* === Edits === */
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
        background-color: #18181c;
        border: 1px solid #37373c;
        padding: 3px 6px;
        color: #ebebeb;
        selection-background-color: #461a1a;
        selection-color: #ffffff;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: #eb3c3c;
    }}

    /* === Tables === */
    QTableWidget, QTableView {{
        background-color: #18181c;
        gridline-color: #2a2a30;
        border: 1px solid #37373c;
        alternate-background-color: #1c1c20;
        selection-background-color: #461a1a;
        selection-color: #ffffff;
    }}
    QHeaderView::section {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #1c1618, stop:1 #2a1c1c);
        color: #f0eaea;
        padding: 4px 10px;
        border: none;
        border-right: 1px solid #2a2a30;
        border-bottom: 1px solid #eb3c3c;
        font-weight: 600;
    }}

    /* === Menus & menubar === */
    QMenuBar {{ background: #14141a; color: #ebebeb; border-bottom: 1px solid #37373c; }}
    QMenuBar::item:selected {{ background: #461a1a; }}
    QMenu {{
        background: #18181c;
        color: #ebebeb;
        border: 1px solid #eb3c3c;
        padding: 4px;
    }}
    QMenu::item {{ padding: 4px 18px; }}
    QMenu::item:selected {{ background: #461a1a; color: #ffffff; }}
    QMenu::separator {{ height: 1px; background: #37373c; margin: 4px 6px; }}

    /* === Splitters === */
    QSplitter::handle {{ background: #37373c; }}
    QSplitter::handle:hover {{ background: #eb3c3c; }}

    /* === Progress bar === */
    QProgressBar {{
        background-color: #101014;
        border: 1px solid #37373c;
        text-align: center;
        color: #ebebeb;
        height: 14px;
    }}
    QProgressBar::chunk {{ background-color: #eb3c3c; }}

    /* Startup overlay */
    #startupOverlay {{ background-color: rgba(10, 10, 14, 235); }}
    #startupTitle {{ font-size: 20px; font-weight: 700; letter-spacing: 1px; color: #f0eaea; }}
    #startupSubtitle {{ font-size: 10px; color: #8a8a90; letter-spacing: 0.5px; }}

    /* Tiny square ESP color buttons */
    #espColorButton {{
        min-width: 14px; max-width: 14px;
        min-height: 14px; max-height: 14px;
        padding: 0;
        border: 1px solid #4a4a50;
    }}
    #espColorButton:hover {{ border-color: #eb3c3c; }}
    #espColorButton:pressed {{ border-color: #eb3c3c; }}

    /* Status pill labels (kernel state, etc.) */
    QLabel#kernelStatusOk {{ color: #58c873; font-weight: 600; }}
    QLabel#kernelStatusWarn {{ color: #ff9933; font-weight: 600; }}
    QLabel#kernelStatusErr {{ color: #eb3c3c; font-weight: 600; }}
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

    # Auto-start the kernel driver as early as possible so feature threads
    # (ESP/Aimbot/etc.) reuse the already-loaded backend instead of racing
    # to load it themselves. Stop it deterministically on Qt shutdown.
    if is_admin and getattr(cfg, "kernel_driver_auto_start", True) \
            and getattr(cfg, "kernel_mode_enabled", True):
        try:
            from Process.memory_interface import (
                ensure_kernel_driver_started, cleanup_kernel_driver,
            )
            if ensure_kernel_driver_started():
                logger.info("Kernel driver auto-started", category="System")
            else:
                logger.warning("Kernel driver auto-start failed; usermode fallback in effect", category="System")
            app.aboutToQuit.connect(cleanup_kernel_driver)
        except Exception as e:
            logger.exception(f"Kernel auto-start error: {e}", category="System")

    # Pattern-scan cs2.exe NOW so feature threads start with fresh offsets.
    # Without this the static Process/offsets.py snapshot wins; that snapshot
    # is regenerated by hand from a2x/cs2-dumper and goes stale on every CS2
    # update -- which is what made ESP draw nothing on builds past 14154.
    try:
        from Process.refresh_offsets import refresh_now
        ok = refresh_now(log=lambda m: logger.info(m, category="Offsets"))
        if ok:
            logger.info("Offsets refreshed from live cs2.exe", category="Offsets")
        else:
            logger.warning(
                "Offset refresh skipped/failed - using static Process/offsets.py "
                "snapshot. ESP may show nothing if CS2 has updated since the snapshot.",
                category="Offsets")
    except Exception as e:
        logger.exception(f"Offset refresh error: {e}", category="Offsets")
    
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

def run_radar():
    global radar_app
    logger.info("Starting radar overlay", category="Radar")
    try:
        # local import so GFusion still launches even if radar.py isn't present
        from radar import RadarApp  # type: ignore
    except Exception:
        try:
            from Features.radar import RadarApp  # type: ignore
        except Exception as e:
            logger.error(f"Radar module not found: {e}", category="Radar", exc_info=True)
            return

    try:
        radar_app = RadarApp(title="GFusion Radar", cfg_ref=Config)
        radar_app.start()
    except Exception as e:
        logger.exception(f"Radar crashed: {e}", category="Radar")



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

def start_radar_thread():
    global radar_thread
    if radar_thread is None or not radar_thread.is_alive():
        Config.radar_stop = False
        Config.radar_enabled = True
        radar_thread = threading.Thread(target=run_radar, daemon=True)
        radar_thread.start()

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

def stop_radar_thread():
    global radar_app, radar_thread
    try:
        Config.radar_enabled = False
        Config.radar_stop = True

        if radar_app is not None:
            radar_app.stop()
            radar_app = None

        if radar_thread is not None:
            radar_thread = None

        logger.info("[Radar] Stop complete and cleaned up", category="Threading")
    except Exception as e:
        logger.error(f"[Radar] Stop error: {e}", category="Radar", exc_info=True)


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

                                                               
    def create_group_box(self, title: str):
        return SectionFrame(title)

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
        # scroll container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #14141a; border: none; }")

        content = QWidget(); content.setStyleSheet("background-color: #14141a;")
        layout = QVBoxLayout(content)
        layout.setSpacing(10); layout.setContentsMargins(10, 10, 10, 10)

        # 2-column main layout
        cols = QHBoxLayout(); cols.setSpacing(10)
        col1 = QVBoxLayout(); col1.setSpacing(10)
        col2 = QVBoxLayout(); col2.setSpacing(10)

        # --- Column 1: Core Aim & Acquisition ---
        aim_g = self.create_group_box("Aimbot Master")
        aim_l = QVBoxLayout(aim_g)
        self.add_checkbox(aim_l, "Enable Aimbot", "enabled",
                          on_toggle=lambda en: (start_aimbot_thread() if en else stop_aimbot_thread()))
        self.add_checkbox(aim_l, "DeathMatch Mode", "DeathMatch")
        self.add_checkbox(aim_l, "Visible-check Aim", "visibility_aim_enabled")
        self.add_checkbox(aim_l, "Closest to Crosshair", "closest_to_crosshair")
        self.add_combo_row(aim_l, "Aim Key:", ["mouse1","mouse2","mouse3","mouse4","mouse5","left_alt","left_ctrl","left_shift","caps_lock","space"], "aim_key", width=110)
        self.add_combo_row(aim_l, "Target Bone:", ["head","neck","chest","pelvis","left_hand","right_hand","left_leg","right_leg"], "target_bone_name", width=110)
        col1.addWidget(aim_g)

        acq_g = self.create_group_box("Target Acquisition")
        acq_l = QVBoxLayout(acq_g)
        self.add_float_slider(acq_l, "FOV Radius", "FOV", 0.1, 30.0, 10)
        self.add_int_slider(acq_l, "Max Angle Δ", "max_delta_angle", 1, 180)
        self.add_int_slider(acq_l, "Max Entities", "max_entities", 1, 128)
        self.add_float_slider(acq_l, "Start Delay", "aim_start_delay", 0.00, 1.00, 100)
        self.add_float_slider(acq_l, "Switch Delay", "target_switch_delay", 0.00, 1.00, 100)
        col1.addWidget(acq_g)

        fov_g = self.create_group_box("FOV Visuals")
        fov_l = QVBoxLayout(fov_g)
        row = QHBoxLayout()
        self.add_checkbox(row, "Show FOV Circle", "fov_circle_enabled")
        self.add_color_button(row, "fov_overlay_color", "FOV circle color")
        row.addStretch()
        fov_l.addLayout(row)
        col1.addWidget(fov_g)

        kern_g = self.create_group_box("Security & Driver")
        kern_l = QVBoxLayout(kern_g)
        self.add_checkbox(kern_l, "Enable Kernel Mode", "kernel_mode_enabled", 
                          on_toggle=self._toggle_kernel_mode)
        self.kernel_status = QLabel("Status: Disabled")
        self.kernel_status.setStyleSheet("color: #8a8a90; font-style: italic;")
        kern_l.addWidget(self.kernel_status)
        col1.addWidget(kern_g)
        col1.addStretch()

        # --- Column 2: RCS, Smoothing & Humanization ---
        rcs_g = self.create_group_box("Recoil Control (RCS)")
        rcs_l = QVBoxLayout(rcs_g)
        self.add_checkbox(rcs_l, "Enable RCS", "rcs_enabled")
        self.add_float_slider(rcs_l, "RCS Intensity", "rcs_scale", 0.00, 5.00, 100)
        self.add_float_slider(rcs_l, "RCS Smooth", "rcs_smooth_base", 0.00, 1.00, 100)
        self.add_checkbox(rcs_l, "Grace After Kill", "rcs_grace_after_damage")
        self.add_float_slider(rcs_l, "Grace Time (s)", "rcs_grace_time", 0.00, 1.00, 100)
        col2.addWidget(rcs_g)

        # ----- Aim Feel (v4: 4 knobs + 1 toggle) -----
        feel_g = self.create_group_box("Aim Feel")
        feel_l = QVBoxLayout(feel_g)
        # Smoothness 0..100  ->  tau 10ms..250ms internally
        self.add_int_slider(feel_l, "Smoothness", "aim_smoothness", 0, 100)
        # Reaction delay in ms after target switch
        self.add_int_slider(feel_l, "Reaction Delay (ms)", "aim_reaction_delay_ms", 0, 250)
        # Sub-pixel cap on per-frame mouse move (anti-snap on giant flicks)
        self.add_int_slider(feel_l, "Max Mouse Move", "max_mouse_move", 1, 80)
        row_inv = QHBoxLayout()
        self.add_checkbox(row_inv, "Invert Y Axis", "invert_y")
        row_inv.addStretch()
        feel_l.addLayout(row_inv)
        col2.addWidget(feel_g)

        # ----- Humanization (one toggle, one knob) -----
        human_g = self.create_group_box("Humanization")
        human_l = QVBoxLayout(human_g)
        self.add_checkbox(human_l, "Enable Humanization", "humanization_enabled")
        # Curl amplitude. 0 = perfectly straight aim, 1 = noticeable wobble.
        self.add_float_slider(human_l, "Strength", "humanization_strength", 0.0, 1.0, 100)
        # Live learning toggle (per-weapon spray pattern EMA)
        self.add_checkbox(human_l, "Spray Pattern Learning", "enable_learning")
        col2.addWidget(human_g)

        pistol_g = self.create_group_box("Weapon Utility")
        pistol_l = QVBoxLayout(pistol_g)
        self.auto_pistol_cb = self.add_checkbox(
            pistol_l, "Enable Auto Pistol", "auto_pistol_enabled",
            on_toggle=lambda en: (start_auto_pistol_thread() if en else stop_auto_pistol_thread())
        )
        self.add_combo_row(pistol_l, "Hot Key:",
                           ["mouse2","mouse3","mouse4","mouse5","alt","ctrl","shift","space"],
                           "activation_key", width=90)
        col2.addWidget(pistol_g)
        col2.addStretch()

        cols.addLayout(col1, 1)
        cols.addLayout(col2, 1)
        layout.addLayout(cols)

        scroll.setWidget(content)
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)
        
        QTimer.singleShot(300, self._check_kernel_status_delayed)

                                           
    def _toggle_kernel_mode(self, enabled: bool):
        self.kernel_status.setText("Status: Initializing..." if enabled else "Status: Disabled")
        self.kernel_status.setStyleSheet(
            "color: #ff8800; font-style: italic;" if enabled else "color: #888; font-style: italic;"
        )
        try:
            import threading

            def init_kernel():
                try:
                    from Process.drivers import load_driver
                    name = getattr(Config, "kernel_driver", "binalyze_irec")
                    drv = load_driver(name)
                    if not drv:
                        self.kernel_status.setText(f"Status: ✗ Backend '{name}' unavailable")
                        self.kernel_status.setStyleSheet("color: #ff0000; font-style: italic;")
                        return
                    if enabled:
                        ok = drv.start()
                        if ok:
                            self.kernel_status.setText(f"Status: ✓ {drv.status()}")
                            self.kernel_status.setStyleSheet("color: #00ff00; font-style: italic;")
                            # Probe-only: stop after verifying. Real attach happens
                            # in MemoryInterface when CS2 is running.
                            try:
                                drv.stop()
                            except Exception:
                                pass
                        else:
                            self.kernel_status.setText(f"Status: ✗ {drv.status()}")
                            self.kernel_status.setStyleSheet("color: #ff0000; font-style: italic;")
                    else:
                        try:
                            drv.stop()
                        except Exception:
                            pass
                except Exception as e:
                    self.kernel_status.setText(f"Status: ✗ Error: {str(e)[:40]}")
                    self.kernel_status.setStyleSheet("color: #ff0000; font-style: italic;")

            threading.Thread(target=init_kernel, daemon=True).start()
        except Exception as e:
            print(f"[AimbotTab] Kernel toggle error: {e}")

    def _check_kernel_status_delayed(self):
        try:
            active = getattr(Config, "_kernel_active_instances", 0) > 0
            if active:
                self.kernel_status.setText("Status: ✓ Kernel mode active (MemoryInterface attached)")
                self.kernel_status.setStyleSheet("color: #00ff00; font-style: italic;")
                return

            # Driver may be auto-started but no MemoryInterface yet (cs2.exe
            # not running). Reflect the live backend state.
            try:
                from Process import memory_interface as _mi
                drv = getattr(_mi, "_kernel_driver", None)
                if drv is not None:
                    self.kernel_status.setText(f"Status: ✓ Driver loaded — {drv.status()}")
                    self.kernel_status.setStyleSheet("color: #00cc66; font-style: italic;")
                    # Re-poll: once cs2.exe boots and a MemoryInterface attaches,
                    # we want to flip the label to "kernel mode active".
                    QTimer.singleShot(2000, self._check_kernel_status_delayed)
                    return
            except Exception:
                pass

            if getattr(Config, "kernel_mode_enabled", False):
                self.kernel_status.setText("Status: ⏳ Waiting for driver / cs2.exe")
                self.kernel_status.setStyleSheet("color: #ff8800; font-style: italic;")
                QTimer.singleShot(2000, self._check_kernel_status_delayed)
        except Exception as e:
            print(f"[AimbotTab] Kernel status check error: {e}")

                                
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

    def __init__(self):
        super().__init__()
        # accept both cfg (instance) or Config (class)
        self.CFG = globals().get("cfg", None) or globals().get("Config", None)
        if self.CFG is None:
            raise RuntimeError("Config/cfg not found in globals")

        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._on_autosave_tick)
        self.init_ui()

    def _create_group_box(self, title: str):
        return SectionFrame(title)

    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #14141a; border: none; }")

        content = QWidget(); content.setStyleSheet("background-color: #14141a;")
        layout = QVBoxLayout(content)
        layout.setSpacing(25); layout.setContentsMargins(20, 20, 20, 20)

        # 2-column main layout
        cols = QHBoxLayout(); cols.setSpacing(25)
        col1 = QVBoxLayout(); col1.setSpacing(20)
        col2 = QVBoxLayout(); col2.setSpacing(20)

        # --- Column 1: Active Configuration ---
        active_g = self._create_group_box("ACTIVE SESSION")
        active = QVBoxLayout(active_g); active.setSpacing(15); active.setContentsMargins(15, 40, 15, 15)
        
        lbl_active = QLabel("CURRENT PROFILE SELECTION")
        lbl_active.setStyleSheet("font-weight: 800; color: #eb3c3c; font-size: 10pt; letter-spacing: 1px;")
        active.addWidget(lbl_active)
        
        self.active_combo = QComboBox(); self.active_combo.setFixedHeight(40)
        self.active_combo.activated[str].connect(self._on_active_changed)
        active.addWidget(self.active_combo)

        btn_row = QHBoxLayout(); btn_row.setSpacing(12)
        self.new_btn = QPushButton("NEW"); self.save_btn = QPushButton("SAVE"); self.load_btn = QPushButton("LOAD")
        for b in (self.new_btn, self.save_btn, self.load_btn): 
            b.setFixedHeight(35); b.setStyleSheet("font-weight: 800; min-width: 85px; color: #ffffff; background-color: #1c1c24; border: 1px solid #37373c;")
        btn_row.addWidget(self.new_btn); btn_row.addWidget(self.save_btn); btn_row.addWidget(self.load_btn)
        active.addLayout(btn_row)
        
        self.status_label = QLabel("ALL SYSTEMS OPERATIONAL")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #eb3c3c; font-weight: bold; letter-spacing: 1.5px; padding-top: 8px; border-top: 1px solid #2a2a30;")
        active.addWidget(self.status_label)
        col1.addWidget(active_g)

        saved_g = self._create_group_box("PROFILE OPERATIONS")
        saved = QVBoxLayout(saved_g); saved.setSpacing(15); saved.setContentsMargins(15, 40, 15, 15)
        
        lbl_saved = QLabel("LOCAL DATABASE")
        lbl_saved.setStyleSheet("font-weight: 800; color: #8a8a90; font-size: 9pt; letter-spacing: 1px;")
        saved.addWidget(lbl_saved)
        
        lr1 = QHBoxLayout(); lr1.setSpacing(10)
        self.config_list = QComboBox(); self.config_list.setFixedHeight(35)
        self.refresh_btn = QPushButton("↻"); self.refresh_btn.setFixedSize(35, 35)
        self.refresh_btn.setStyleSheet("font-size: 14pt; font-weight: bold;")
        lr1.addWidget(self.config_list, 1); lr1.addWidget(self.refresh_btn)
        saved.addLayout(lr1)

        lr2 = QHBoxLayout(); lr2.setSpacing(12)
        self.rename_btn = QPushButton("RENAME"); self.duplicate_btn = QPushButton("CLONE"); self.delete_btn = QPushButton("DELETE")
        for b in (self.rename_btn, self.duplicate_btn, self.delete_btn): b.setFixedHeight(32); b.setStyleSheet("background-color: #18181e;")
        lr2.addWidget(self.rename_btn); lr2.addWidget(self.duplicate_btn); lr2.addWidget(self.delete_btn)
        saved.addLayout(lr2)
        col1.addWidget(saved_g)

        io_g = self._create_group_box("CLOUD & STORAGE")
        io = QHBoxLayout(io_g); io.setSpacing(12); io.setContentsMargins(15, 40, 15, 15)
        self.import_btn = QPushButton("IMPORT JSON"); self.export_btn = QPushButton("EXPORT JSON")
        self.import_btn.setFixedHeight(35); self.export_btn.setFixedHeight(35)
        self.import_btn.setStyleSheet("font-weight: bold;"); self.export_btn.setStyleSheet("font-weight: bold;")
        io.addWidget(self.import_btn); io.addWidget(self.export_btn)
        col1.addWidget(io_g)
        col1.addStretch()

        # --- Column 2: System Settings ---
        appearance_g = self._create_group_box("INTERFACE VISUALS")
        ap = QVBoxLayout(appearance_g); ap.setSpacing(15); ap.setContentsMargins(15, 40, 15, 15)
        
        lbl_font = QLabel("PRIMARY UI FONT")
        lbl_font.setStyleSheet("font-weight: 800; color: #8a8a90; font-size: 9pt;")
        ap.addWidget(lbl_font)
        
        self.font_combo = QComboBox(); self.font_combo.setEditable(True); self.font_combo.setFixedHeight(35)
        try:
            families = sorted(QFontDatabase().families(), key=lambda s: s.lower())
            if families: self.font_combo.addItems(families)
        except Exception: pass
        cur_font = str(getattr(self.CFG, "ui_font_family", "Segoe UI") or "Segoe UI")
        self.font_combo.setCurrentText(cur_font)
        ap.addWidget(self.font_combo)

        ap.addSpacing(5)
        lbl_scale = QLabel("INTERFACE SCALING")
        lbl_scale.setStyleSheet("font-weight: 800; color: #8a8a90; font-size: 9pt;")
        ap.addWidget(lbl_scale)
        
        self.font_size_slider = NoScrollSlider(Qt.Horizontal)
        self.font_size_slider.setRange(7, 24)
        cur_size = int(getattr(self.CFG, "ui_font_size", 11) or 11)
        self.font_size_slider.setValue(cur_size)
        ap.addWidget(self.font_size_slider)
        
        self.font_apply_btn = QPushButton("APPLY SYSTEM SCALING")
        self.font_apply_btn.setFixedHeight(40); self.font_apply_btn.setStyleSheet("font-weight: 900; color: #ffffff; background-color: #eb3c3c; border-radius: 4px;")
        self.font_apply_btn.clicked.connect(self._apply_font)
        ap.addWidget(self.font_apply_btn)
        col2.addWidget(appearance_g)

        auto_g = self._create_group_box("MAINTENANCE")
        auto = QVBoxLayout(auto_g); auto.setSpacing(15); auto.setContentsMargins(15, 40, 15, 15)
        self.autosave_cb = CheatCheckBox("ENABLE AUTOMATIC BACKGROUND SYNC")
        self.autosave_cb.setChecked(bool(getattr(self.CFG, "autosave_enabled", False)))
        self.autosave_cb.stateChanged.connect(self._toggle_autosave)
        auto.addWidget(self.autosave_cb)
        
        self.open_folder_btn = QPushButton("OPEN CONFIGURATION DIRECTORY")
        self.open_folder_btn.setFixedHeight(35); self.open_folder_btn.setStyleSheet("font-weight: bold;")
        self.open_folder_btn.clicked.connect(self.open_config_folder)
        auto.addWidget(self.open_folder_btn)
        col2.addWidget(auto_g)
        col2.addStretch()

        cols.addLayout(col1, 1)
        cols.addLayout(col2, 1)
        layout.addLayout(cols)

        # Connections
        self.refresh_btn.clicked.connect(self.refresh_config_list)
        self.new_btn.clicked.connect(self.create_new_config)
        self.save_btn.clicked.connect(self.save_config)
        self.load_btn.clicked.connect(self.load_config)
        self.rename_btn.clicked.connect(self.rename_config)
        self.duplicate_btn.clicked.connect(self.duplicate_config)
        self.delete_btn.clicked.connect(self.delete_config)
        self.import_btn.clicked.connect(self.import_config)
        self.export_btn.clicked.connect(self.export_config)

        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(scroll)
        self.refresh_config_list()

    def _apply_font(self):
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

    def _on_autosave_tick(self):
        name = getattr(self.CFG, "current_config_name", "") or self.active_combo.currentText().strip()
        if not name: return
        try:
            path = os.path.join(getattr(self.CFG, "configs_dir", "config"), f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._serialize_cfg(), f, indent=2)
        except Exception as e: print(f"[ConfigTab] autosave error: {e}")

    def _toggle_autosave(self, state):
        enabled = (state == Qt.Checked)
        setattr(self.CFG, "autosave_enabled", enabled)
        if enabled: self._autosave_timer.start(5 * 60_000)
        else: self._autosave_timer.stop()

    def _serialize_cfg(self) -> dict:
        d = {}
        for k in dir(self.CFG):
            if k.startswith("_"): continue
            try:
                v = getattr(self.CFG, k)
                if not callable(v): d[k] = v
            except: continue
        return d

    def _deserialize_cfg(self, data: dict):
        for k, v in data.items():
            try: setattr(self.CFG, k, v)
            except: pass

    def _on_active_changed(self, text: str):
        if text: setattr(self.CFG, "current_config_name", text)

    def refresh_config_list(self):
        try:
            path = getattr(self.CFG, "configs_dir", "config")
            os.makedirs(path, exist_ok=True)
            names = [f[:-5] for f in os.listdir(path) if f.lower().endswith(".json")]
            names.sort()
            self.active_combo.clear(); self.active_combo.addItems(names)
            self.config_list.clear(); self.config_list.addItems(names)
            cur = getattr(self.CFG, "current_config_name", "")
            if cur:
                self.active_combo.setCurrentText(cur)
                self.config_list.setCurrentText(cur)
        except Exception as e: print(f"[ConfigTab] refresh_config_list error: {e}")

    def save_config(self):
        name = self.active_combo.currentText().strip()
        if not name: return
        try:
            path = os.path.join(getattr(self.CFG, "configs_dir", "config"), f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._serialize_cfg(), f, indent=2)
            self.status_label.setText(f"Status: ✓ Saved '{name}'")
        except Exception as e: self.status_label.setText("Status: ✗ Save error")

    def load_config(self):
        name = self.active_combo.currentText().strip()
        if not name: return
        try:
            path = os.path.join(getattr(self.CFG, "configs_dir", "config"), f"{name}.json")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._deserialize_cfg(data)
            self.config_loaded.emit()
            self.status_label.setText(f"Status: ✓ Loaded '{name}'")
        except Exception as e: self.status_label.setText("Status: ✗ Load error")

    def create_new_config(self): self.status_label.setText("Status: Use 'Save' as new name")
    def rename_config(self): pass
    def duplicate_config(self): pass
    def delete_config(self): pass
    def import_config(self): pass
    def export_config(self): pass
    def open_config_folder(self):
        path = os.path.abspath(getattr(self.CFG, "configs_dir", "config"))
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    def refresh_ui(self):
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
        return SectionFrame(title)

    def _init_ui(self):
        # Scroll shell (match other tabs)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color:#14141a; border:none; }")

        content = QWidget(); content.setStyleSheet("background-color:#14141a;")
        root = QVBoxLayout(content); root.setSpacing(10); root.setContentsMargins(10,10,10,10)

        # Output Window (Dominant)
        out_g = self._create_group_box("SYSTEM TERMINAL")
        out_l = QVBoxLayout(out_g); out_l.setSpacing(6)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(400)
        self.output.setStyleSheet(""" 
            QTextEdit { 
                background: #0d0d12; 
                color: #e6e6e9; 
                border: 1px solid #2b2b3c; 
                font-family: 'Consolas', 'Courier New', monospace; 
                font-size: 10pt;
                padding: 10px; 
                selection-background-color: #eb3c3c; 
                selection-color: #ffffff; 
            } 
        """)
        out_l.addWidget(self.output)
        root.addWidget(out_g, 1)

        # Command Input (Compact at bottom)
        in_g = self._create_group_box("EXECUTION")
        in_l = QVBoxLayout(in_g); in_l.setSpacing(6)
        
        in_row = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Enter command (type 'help' for list)...")
        self.input_line.setFixedHeight(30)
        self.input_line.setStyleSheet("font-family: 'Consolas'; font-size: 10pt;")
        self.input_line.returnPressed.connect(self._on_enter)
        self.input_line.installEventFilter(self)
        in_row.addWidget(self.input_line, 1)
        
        btn_run = QPushButton("RUN"); btn_run.setFixedWidth(80); btn_run.setFixedHeight(30)
        btn_run.setStyleSheet("font-weight: bold; background-color: #1c1c24;")
        btn_run.clicked.connect(self._on_enter)
        in_row.addWidget(btn_run)
        in_l.addLayout(in_row)
        
        root.addWidget(in_g)

        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.addWidget(scroll)
        self._log("[OK] Console system operational")

    def eventFilter(self, obj, ev):
        if obj is self.input_line and ev.type() == ev.KeyPress:
            key = ev.key()
            if key == Qt.Key_Up:
                self._history_prev(); return True
            if key == Qt.Key_Down:
                self._history_next(); return True
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
        if self.history_index == len(self.history): self.input_line.clear()
        else: self.input_line.setText(self.history[self.history_index])

    def _build_known_cmds(self):
        base = {"help", "get", "set", "toggle", "list", "start", "stop", "threads", "panic"}
        try:
            for k in dir(self.CFG):
                if not k.startswith("_"): base.add(k)
        except Exception: pass
        self._known_cmds = base

    def _try_discover_execfw(self):
        try:
            for tab in TAB_REGISTRY:
                if tab.__class__.__name__ == "ExecutionTab" and hasattr(tab, "execfw"):
                    self.execfw = tab.execfw
                    self._discover_timer.stop()
                    self._log("[OK] Linked to Execution engine")
                    return
        except Exception as e: pass

    def _on_enter(self):
        text = self.input_line.text().strip()
        if not text: return
        self.input_line.clear()
        self._push_history(text)
        self._handle(text)

    def _log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.output.append(f"[{ts}] {text}")
        self.output.moveCursor(self.output.textCursor().End)
    
    def _on_log_signal(self, level, message):
        if level in ("ERROR", "CRITICAL", "EXCEPTION"):
            color_msg = f'<span style="color: #ff3c3c;">{message}</span>'
        elif level == "WARNING":
            color_msg = f'<span style="color: #ffb83c;">{message}</span>'
        else: color_msg = message
        ts = time.strftime("%H:%M:%S")
        self.output.append(f"[{ts}] {color_msg}")
        self.output.moveCursor(self.output.textCursor().End)

    def _handle(self, line: str):
        self._log(f"> {line}")
        parts = line.split()
        if not parts: return
        cmd = parts[0].lower()
        if cmd == "help": self._log("Commands: help, get, set, toggle, list, start, stop, threads, panic")
        else: self._log(f"[ERR] Unknown command '{cmd}'")

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

                                                 
    def create_group_box(self, title: str):
        return SectionFrame(title)

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
        section = self.create_group_box(title)
        grid = QGridLayout(section)
        grid.setSpacing(10); grid.setContentsMargins(5, 5, 5, 5)

        for i, (label, attr, default) in enumerate(colors):
            self.add_color_picker_to_grid(grid, i // 3, i % 3, label, attr, default)
        parent_layout.addWidget(section)

    def add_color_picker_to_grid(self, grid, row, col, label, cfg_key, default=(255, 255, 255)):
        rgb = getattr(Config, cfg_key, default)
        item_layout = QHBoxLayout()
        lbl = QLabel(f"{label}:"); lbl.setFixedWidth(70)
        item_layout.addWidget(lbl)
        
        btn = QPushButton(); btn.setObjectName("espColorButton"); btn.setFixedSize(16, 16)
        btn.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid #37373c;")

        def choose():
            color = QColorDialog.getColor(QColor(*rgb), self, f"Select {label} Color")
            if color.isValid():
                new_rgb = (color.red(), color.green(), color.blue())
                setattr(Config, cfg_key, new_rgb)
                btn.setStyleSheet(f"background-color: rgb{new_rgb}; border: 1px solid #37373c;")
        btn.clicked.connect(choose)
        item_layout.addWidget(btn); item_layout.addStretch()
        
        cont = QWidget(); cont.setStyleSheet("background: transparent;")
        cont.setLayout(item_layout)
        grid.addWidget(cont, row, col)

        self.ui_elements["color_buttons"][cfg_key] = btn
        return btn

                                            
    def init_ui(self):
        # scroll container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #14141a; border: none; }")

        content = QWidget(); content.setStyleSheet("background-color: #14141a;")
        layout = QVBoxLayout(content)
        layout.setSpacing(10); layout.setContentsMargins(10, 10, 10, 10)

        # 2-column main layout
        cols = QHBoxLayout(); cols.setSpacing(10)
        col1 = QVBoxLayout(); col1.setSpacing(10)
        col2 = QVBoxLayout(); col2.setSpacing(10)

        # --- Column 1: Core Visuals ---
        vis_g = self.create_group_box("Player Visuals")
        vis_l = QVBoxLayout(vis_g)
        self.add_checkbox(vis_l, "Enable ESP", "show_box_esp")
        self.add_checkbox(vis_l, "Visible Only", "visible_only_esp_enabled")
        self.add_checkbox(vis_l, "Hide from Capture (OBS)", "obs_protection_enabled")
        self.add_combobox(vis_l, "Box Style:", ["normal", "rounded", "corner"], "box_esp_style")
        col1.addWidget(vis_g)

        health_g = self.create_group_box("Health & Armor")
        health_l = QVBoxLayout(health_g)
        self.add_checkbox(health_l, "Health Bar", "healthbar_enabled")
        self.add_checkbox(health_l, "Health Text", "health_esp_enabled")
        self.add_checkbox(health_l, "Armor Bar", "armorbar_enabled")
        self.add_checkbox(health_l, "Armor Text", "armor_esp_enabled")
        col1.addWidget(health_g)

        info_g = self.create_group_box("Player Info")
        info_l = QVBoxLayout(info_g)
        self.add_checkbox(info_l, "Name ESP", "name_esp_enabled")
        self.add_checkbox(info_l, "Weapon ESP", "weapon_esp_enabled")
        self.add_checkbox(info_l, "Distance ESP", "distance_esp_enabled")
        col1.addWidget(info_g)
        col1.addStretch()

        # --- Column 2: Filter & Extras ---
        filter_g = self.create_group_box("Team Filtering")
        filter_l = QVBoxLayout(filter_g)
        self.add_checkbox(filter_l, "Enemy Only", "esp_show_enemies_only")
        self.add_checkbox(filter_l, "Team Only", "esp_show_team_only")
        self.add_checkbox(filter_l, "Dead Players", "draw_dead_entities")
        col2.addWidget(filter_g)

        extra_g = self.create_group_box("Overlay Extras")
        extra_l = QVBoxLayout(extra_g)
        self.add_checkbox(extra_l, "Skeleton ESP", "skeleton_esp_enabled")
        self.add_checkbox(extra_l, "Velocity ESP", "velocity_esp")
        self.add_checkbox(extra_l, "Flash ESP", "flash_esp_enabled")
        self.add_checkbox(extra_l, "Bomb ESP", "bomb_esp_enabled")
        self.add_checkbox(extra_l, "Money ESP", "money_esp_enabled")
        col2.addWidget(extra_g)

        util_g = self.create_group_box("Utility")
        util_l = QVBoxLayout(util_g)
        self.add_checkbox(util_l, "Crosshair", "draw_crosshair_enabled")
        self.add_checkbox(util_l, "Line ESP", "line_esp_enabled")
        self.add_combobox(util_l, "Line Pos:", ["top", "bottom"], "line_esp_position")
        col2.addWidget(util_g)
        col2.addStretch()

        cols.addLayout(col1, 1)
        cols.addLayout(col2, 1)
        layout.addLayout(cols)

        # Separate Colors Section
        colors_g = self.create_group_box("ESP Colors")
        colors_l = QVBoxLayout(colors_g)
        self.add_color_section(colors_l, "Main Colors", [
            ("Box (T)", "color_box_t", (255, 180, 0)),
            ("Box (CT)", "color_box_ct", (100, 200, 255)),
            ("Skeleton", "color_bone", (255, 255, 255)),
            ("Name", "color_name", (255, 255, 255)),
        ])
        layout.addWidget(colors_g)

        scroll.setWidget(content)
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

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
            b.setStyleSheet(f"background-color: rgb{rgb}; border: 1px solid #37373c;")
               
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
            self.setWindowTitle("GFusion V3.6.5")
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
            background-color: #14141a;
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

        title = QLabel("GFusion V3.6.5")
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

    def create_group_box(self, title: str):
        return SectionFrame(title)

    def add_checkbox(self, layout, label, cfg_key, thread_start=None, thread_stop=None):
        cb = CheatCheckBox(label)
        cb.setChecked(bool(getattr(Config, cfg_key, False)))
        def handler(st):
            en = (st == Qt.Checked)
            setattr(Config, cfg_key, en)
            if en and thread_start: thread_start()
            elif not en and thread_stop: thread_stop()
        cb.stateChanged.connect(handler)
        layout.addWidget(cb)
        return cb

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
        return sld, lab

                                   
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

    def create_group_box(self, title: str):
        return SectionFrame(title)

                              
    def init_ui(self):
        # scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: #14141a; border: none; }")

        content = QWidget(); content.setStyleSheet("background-color: #14141a;")
        main_layout = QVBoxLayout(content)
        main_layout.setSpacing(10); main_layout.setContentsMargins(10, 10, 10, 10)

        # 2-column main layout
        cols = QHBoxLayout(); cols.setSpacing(10)
        col1 = QVBoxLayout(); col1.setSpacing(10)
        col2 = QVBoxLayout(); col2.setSpacing(10)

        # --- Column 1: Movement & Radar ---
        move_g = self.create_group_box("Movement")
        move_l = QVBoxLayout(move_g)
        self.add_checkbox(move_l, "BunnyHop", "bhop_enabled",
                          thread_start=start_bhop_thread, thread_stop=stop_bhop_thread)
        self.add_checkbox(move_l, "Auto Strafe", "auto_strafe_enabled")
        self.add_checkbox(move_l, "WalkBot", "walkbot_enabled",
                          thread_start=start_walkbot_thread, thread_stop=stop_walkbot_thread)
        col1.addWidget(move_g)

        radar_g = self.create_group_box("Radar Settings")
        radar_l = QVBoxLayout(radar_g)
        self.add_checkbox(radar_l, "Enable Radar", "radar_enabled")
        self.add_checkbox(radar_l, "Show Names", "radar_show_names")
        self.add_checkbox(radar_l, "Show Health", "radar_show_health")
        col1.addWidget(radar_g)

        sys_g = self.create_group_box("System Controls")
        sys_l = QVBoxLayout(sys_g)
        
        row_key = QHBoxLayout()
        self.toggle_key_label = QLabel(f"Menu Key: {cfg.toggle_menu_key}")
        self.toggle_key_label.setStyleSheet("color: #8a8a90; font-weight: bold;")
        row_key.addWidget(self.toggle_key_label)
        toggle_btn = QPushButton("CHANGE")
        toggle_btn.setFixedWidth(70)
        toggle_btn.setFixedHeight(28)
        toggle_btn.setStyleSheet("font-weight: bold; background-color: #1c1c24;")
        toggle_btn.clicked.connect(self.set_toggle_key)
        row_key.addWidget(toggle_btn)
        sys_l.addLayout(row_key)
        col1.addWidget(sys_g)
        col1.addStretch()

        # --- Column 2: Extras & Team List ---
        misc_g = self.create_group_box("Miscellaneous")
        misc_l = QVBoxLayout(misc_g)
        self.add_checkbox(misc_l, "Watermark", "watermark_enabled")
        self.add_checkbox(misc_l, "Spectator List", "spectator_list_enabled")
        self.add_checkbox(misc_l, "Show FPS", "show_overlay_fps")
        self.add_checkbox(misc_l, "Grenade Prediction", "grenade_prediction_enabled")
        self.add_checkbox(misc_l, "No Flash", "noflash_enabled")
        col2.addWidget(misc_g)

        team_g = self.create_group_box("Team List")
        team_l = QVBoxLayout(team_g)
        self.add_checkbox(team_l, "Enable Team List", "team_list_enabled")
        self.add_checkbox(team_l, "Show HP Bars", "team_list_show_hp_bars")
        self.add_int_slider(team_l, "Font Size", "team_list_font_size", 8, 16)
        col2.addWidget(team_g)
        col2.addStretch()

        cols.addLayout(col1, 1)
        cols.addLayout(col2, 1)
        main_layout.addLayout(cols)

        # Team List Colors
        tcolors_g = self.create_group_box("Team List Colors")
        tcolors_l = QGridLayout(tcolors_g)
        tcolors_l.setSpacing(8)
        
        team_color_items = [
            ("T Header",    "color_box_t",          (255, 180, 0)),
            ("CT Header",   "color_box_ct",         (100, 200, 255)),
            ("Background",  "team_list_background", (18, 18, 22)),
            ("Dead T",      "team_list_dead_t",     (100, 80, 60)),
            ("Dead CT",     "team_list_dead_ct",    (60, 80, 100)),
        ]
        for idx, (label, key, default) in enumerate(team_color_items):
            row, col = idx // 3, idx % 3
            item_lay = QHBoxLayout()
            lbl = QLabel(f"{label}:"); lbl.setFixedWidth(70)
            item_lay.addWidget(lbl)
            rgb = self._sanitize_rgb3(getattr(Config, key, default))
            btn = QPushButton(); btn.setObjectName("espColorButton"); btn.setFixedSize(16, 16)
            btn.setStyleSheet(self.rgb_to_stylesheet_safe(rgb))
            btn.clicked.connect(self._make_color_picker(key, btn, default))
            item_lay.addWidget(btn); item_lay.addStretch()
            tcolors_l.addLayout(item_lay, row, col)
        
        main_layout.addWidget(tcolors_g)

        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _make_color_picker(self, key, btn, default):
        def choose():
            cur = self._sanitize_rgb3(getattr(Config, key, default))
            color = QColorDialog.getColor(QColor(*cur), self, f"Select {key}")
            if color.isValid():
                new_rgb = (color.red(), color.green(), color.blue())
                setattr(Config, key, new_rgb)
                btn.setStyleSheet(self.rgb_to_stylesheet_safe(new_rgb))
        return choose

    # ---------- Event Handlers ----------
    def update_fov(self, value):
        cfg.game_fov = value
        self.fov_label.setText(f"Game FOV: {value}")
    

    # -----------------------------
    # Radar settings (live)
    # -----------------------------
    def update_radar_size(self, value: int):
        """Update radar overlay size (square) in config."""
        try:
            value = int(value)
        except Exception:
            return
        value = max(180, min(650, value))
        try:
            setattr(Config, "radar_width", value)
            setattr(Config, "radar_height", value)
        except Exception:
            pass

        try:
            if hasattr(self, "radar_size_label"):
                self.radar_size_label.setText(f"Size: {value} px")
        except Exception:
            pass

    def update_radar_opacity(self, value: int):
        """Update radar alpha/opacity (60-255)."""
        try:
            value = int(value)
        except Exception:
            return
        value = max(60, min(255, value))
        try:
            setattr(Config, "radar_alpha", value)
        except Exception:
            pass

        try:
            if hasattr(self, "radar_opacity_label"):
                self.radar_opacity_label.setText(f"Opacity: {value}")
        except Exception:
            pass

    def update_radar_fps(self, value: int):
        """Update radar overlay render FPS (20-144)."""
        try:
            value = int(value)
        except Exception:
            return
        value = max(20, min(144, value))
        try:
            setattr(Config, "radar_fps", float(value))
        except Exception:
            pass

        try:
            if hasattr(self, "radar_fps_label"):
                self.radar_fps_label.setText(f"Overlay FPS: {value}")
        except Exception:
            pass

    def update_radar_reader_fps(self, value: int):
        """Update radar reader (memory polling) FPS (5-144)."""
        try:
            value = int(value)
        except Exception:
            return
        value = max(5, min(144, value))
        try:
            setattr(Config, "radar_reader_fps", float(value))
        except Exception:
            pass

        try:
            if hasattr(self, "radar_reader_fps_label"):
                self.radar_reader_fps_label.setText(f"Reader FPS: {value}")
        except Exception:
            pass

    def update_radar_range(self, value: int):
        """Update radar fixed range units (500-8000)."""
        try:
            value = int(value)
        except Exception:
            return
        value = max(500, min(8000, value))
        try:
            setattr(Config, "radar_range_units", float(value))
        except Exception:
            pass

        try:
            if hasattr(self, "radar_range_label"):
                self.radar_range_label.setText(f"Range: {value}")
        except Exception:
            pass

    def update_team_list_font(self, value):
        Config.team_list_font_size = value
        self.team_list_font_label.setText(f"Size: {value}")

    def set_toggle_key(self):
        self.toggle_key_label.setText("Press any key...")
        self.toggle_key_label.setStyleSheet("color: #eb3c3c; font-weight: bold;")
        self.listener_thread = KeyListenerThread()
        self.listener_thread.key_pressed.connect(self.update_toggle_key)
        self.listener_thread.start()

    def update_toggle_key(self, key):
        cfg.toggle_menu_key = key
        self.toggle_key_label.setText(f"Menu Key: {key}")
        self.toggle_key_label.setStyleSheet("color: #ffffff; font-weight: bold;")

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

            # Refresh radar sliders/labels
            try:
                if hasattr(self, "radar_size_slider"):
                    v = int(getattr(CFG, "radar_width", 280))
                    self.radar_size_slider.blockSignals(True)
                    self.radar_size_slider.setValue(v)
                    self.radar_size_slider.blockSignals(False)
                    if hasattr(self, "radar_size_label"):
                        self.radar_size_label.setText(f"Size: {v} px")
                if hasattr(self, "radar_opacity_slider"):
                    a = int(getattr(CFG, "radar_alpha", 235))
                    self.radar_opacity_slider.blockSignals(True)
                    self.radar_opacity_slider.setValue(a)
                    self.radar_opacity_slider.blockSignals(False)
                    if hasattr(self, "radar_opacity_label"):
                        self.radar_opacity_label.setText(f"Opacity: {a}")
                if hasattr(self, "radar_fps_slider"):
                    fps = int(float(getattr(CFG, "radar_fps", 60.0)))
                    self.radar_fps_slider.blockSignals(True)
                    self.radar_fps_slider.setValue(fps)
                    self.radar_fps_slider.blockSignals(False)
                    if hasattr(self, "radar_fps_label"):
                        self.radar_fps_label.setText(f"Overlay FPS: {fps}")
                if hasattr(self, "radar_reader_fps_slider"):
                    rfps = int(float(getattr(CFG, "radar_reader_fps", 60.0)))
                    self.radar_reader_fps_slider.blockSignals(True)
                    self.radar_reader_fps_slider.setValue(rfps)
                    self.radar_reader_fps_slider.blockSignals(False)
                    if hasattr(self, "radar_reader_fps_label"):
                        self.radar_reader_fps_label.setText(f"Reader FPS: {rfps}")
                if hasattr(self, "radar_range_slider"):
                    r = int(float(getattr(CFG, "radar_range_units", 3000.0)))
                    self.radar_range_slider.blockSignals(True)
                    self.radar_range_slider.setValue(r)
                    self.radar_range_slider.blockSignals(False)
                    if hasattr(self, "radar_range_label"):
                        self.radar_range_label.setText(f"Range: {r}")
            except Exception:
                pass

            
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 600)
        self.learn_dir = LEARN_DIR
        self.weapon_ids = []
        self.all_data = {}
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
        except Exception:
            self._watching = False

    def _create_group_box(self, title: str):
        return SectionFrame(title)

    def _init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #14141a; border: none; }")

        content = QWidget(); content.setStyleSheet("background-color: #14141a;")
        root = QVBoxLayout(content)
        root.setSpacing(20); root.setContentsMargins(15, 15, 15, 15)

        # 1. Trace Map (Dominant at the TOP)
        plot_g = self._create_group_box("RECOIL PATTERN ANALYSIS")
        plot_l = QVBoxLayout(plot_g); plot_l.setContentsMargins(10, 40, 10, 10)
        self.canvas = FigureCanvas(Figure(facecolor="#14141a", figsize=(10, 6)))
        self.ax = self.canvas.figure.add_subplot(111); self._style_axes()
        plot_l.addWidget(self.canvas)
        
        btn_row = QHBoxLayout()
        export_btn = QPushButton("EXPORT PATTERN (.PNG)"); export_btn.setFixedHeight(35); export_btn.setFixedWidth(250)
        export_btn.setStyleSheet("font-weight: 800; background-color: #1c1c24; border: 1px solid #eb3c3c; color: #ffffff;")
        btn_row.addStretch(); btn_row.addWidget(export_btn); btn_row.addStretch()
        plot_l.addLayout(btn_row)
        root.addWidget(plot_g, 4)

        # 2. Controls (2-column layout below plot)
        cols = QHBoxLayout(); cols.setSpacing(20)
        col1 = QVBoxLayout(); col1.setSpacing(15)
        col2 = QVBoxLayout(); col2.setSpacing(15)

        src_g = self._create_group_box("DATA SOURCE")
        src_l = QVBoxLayout(src_g); src_l.setSpacing(12); src_l.setContentsMargins(15, 40, 15, 15)
        
        lbl_dir = QLabel("LEARNING DIRECTORY")
        lbl_dir.setStyleSheet("font-weight: 800; color: #8a8a90; font-size: 9pt;")
        src_l.addWidget(lbl_dir)
        
        row_dir = QHBoxLayout()
        self.dir_edit = QLineEdit(self.learn_dir); self.dir_edit.setReadOnly(True); self.dir_edit.setFixedHeight(30)
        browse_btn = QPushButton("..."); browse_btn.setFixedWidth(40); browse_btn.setFixedHeight(30)
        row_dir.addWidget(self.dir_edit, 1); row_dir.addWidget(browse_btn)
        src_l.addLayout(row_dir)

        lbl_wpn = QLabel("ACTIVE WEAPON")
        lbl_wpn.setStyleSheet("font-weight: 800; color: #8a8a90; font-size: 9pt;")
        src_l.addWidget(lbl_wpn)
        self.dropdown = QComboBox(); self.dropdown.setFixedHeight(35)
        src_l.addWidget(self.dropdown)

        row_acts = QHBoxLayout(); row_acts.setSpacing(10)
        self.watch_cb = CheatCheckBox("AUTO-REFRESH"); self.watch_cb.setChecked(getattr(self, "_watching", False))
        reload_btn = QPushButton("RELOAD"); reload_btn.setFixedHeight(30); reload_btn.setStyleSheet("font-weight: bold;")
        row_acts.addWidget(self.watch_cb); row_acts.addStretch(); row_acts.addWidget(reload_btn)
        src_l.addLayout(row_acts)
        col1.addWidget(src_g)

        dsp_g = self._create_group_box("RENDERER CONFIG")
        dsp_l = QVBoxLayout(dsp_g); dsp_l.setSpacing(10); dsp_l.setContentsMargins(15, 40, 15, 15)
        
        self.mode_checkbox = CheatCheckBox("RENDER SPRAY PATH"); self.mode_checkbox.setChecked(True)
        self.grid_cb = CheatCheckBox("ENABLE ALIGNMENT GRID"); self.grid_cb.setChecked(True)
        self.leg_cb = CheatCheckBox("DISPLAY DATA LEGEND"); self.leg_cb.setChecked(True)
        dsp_l.addWidget(self.mode_checkbox); dsp_l.addWidget(self.grid_cb); dsp_l.addWidget(self.leg_cb)
        
        dsp_l.addSpacing(5)
        row_line = QHBoxLayout()
        self.line_label = QLabel(f"LINE WIDTH: {self.line_width:.1f}"); self.line_label.setStyleSheet("color: #f0f0f0; font-weight: bold;")
        self.line_slider = NoScrollSlider(Qt.Horizontal); self.line_slider.setRange(1, 40); self.line_slider.setValue(int(self.line_width * 10))
        row_line.addWidget(self.line_label); row_line.addSpacing(10); row_line.addWidget(self.line_slider)
        dsp_l.addLayout(row_line)

        row_mark = QHBoxLayout()
        self.marker_label = QLabel(f"POINT SIZE: {self.marker_size:.1f}"); self.marker_label.setStyleSheet("color: #f0f0f0; font-weight: bold;")
        self.marker_slider = NoScrollSlider(Qt.Horizontal); self.marker_slider.setRange(1, 50); self.marker_slider.setValue(int(self.marker_size * 10))
        row_mark.addWidget(self.marker_label); row_mark.addSpacing(10); row_mark.addWidget(self.marker_slider)
        dsp_l.addLayout(row_mark)
        
        col2.addWidget(dsp_g)
        
        cols.addLayout(col1, 1); cols.addLayout(col2, 1)
        root.addLayout(cols)

        # 3. Analytics (Very bottom)
        stats_g = self._create_group_box("PATTERN METRICS")
        stats_l = QVBoxLayout(stats_g); stats_l.setContentsMargins(15, 40, 15, 15)
        self.stats_scroll = QScrollArea(); self.stats_scroll.setWidgetResizable(True); self.stats_scroll.setMinimumHeight(150)
        self.stats_scroll.setStyleSheet("QScrollArea { background-color: #0d0d12; border: 1px solid #2b2b3c; border-radius: 4px; }")
        self.stats_widget = QWidget(); self.stats_widget.setStyleSheet("background: transparent;")
        self.stats_layout = QVBoxLayout(self.stats_widget); self.stats_scroll.setWidget(self.stats_widget)
        stats_l.addWidget(self.stats_scroll)
        root.addWidget(stats_g, 2)

        scroll.setWidget(content)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(scroll)

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
        self.ax.set_facecolor("#14141a")
        self.ax.tick_params(axis="x", colors="#8a8a90", labelsize=8)
        self.ax.tick_params(axis="y", colors="#8a8a90", labelsize=8)
        self.ax.set_xlabel("Yaw Δ", color="#ebebeb")
        self.ax.set_ylabel("Pitch Δ", color="#ebebeb")
        for spine in self.ax.spines.values():
            spine.set_edgecolor("#37373c")

    def _on_data_updated(self):
        if getattr(self, "_watching", False): self.scan_aimbot_data()

    def _toggle_watch(self, st):
        self._watching = (st == Qt.Checked)

    def _toggle_mode(self, st):
        self.spray_mode = (st == Qt.Checked); self.update_view(self.dropdown.currentText())

    def _toggle_grid(self, st):
        self.show_grid = (st == Qt.Checked); self.update_view(self.dropdown.currentText())

    def _toggle_legend(self, st):
        self.show_legend = (st == Qt.Checked); self.update_view(self.dropdown.currentText())

    def _change_line(self, v):
        self.line_width = max(0.1, (v / 10.0)); self.line_label.setText(f"Line W: {self.line_width:.1f}"); self.update_view(self.dropdown.currentText())

    def _change_marker(self, v):
        self.marker_size = max(0.1, (v / 10.0)); self.marker_label.setText(f"Marker: {self.marker_size:.1f}"); self.update_view(self.dropdown.currentText())

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Data Folder", self.learn_dir or "")
        if path: self.learn_dir = path; self.dir_edit.setText(path); self.scan_aimbot_data()

    def _export_png(self):
        wid = self.dropdown.currentText() or "recoil"
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", f"{wid}.png", "PNG Image (*.png)")
        if path: self.canvas.figure.savefig(path, dpi=150, bbox_inches="tight")

    def scan_aimbot_data(self):
        path = self.learn_dir or LEARN_DIR
        if not os.path.exists(path): return
        cur = self.dropdown.currentText()
        files = [f for f in os.listdir(path) if f.endswith(".json")]
        merged = {}
        for fn in files:
            try:
                with open(os.path.join(path, fn), "r", encoding="utf-8") as f: data = json.load(f)
                wid = fn[:-5]
                if wid.startswith("raw_mouse_"): base = wid.replace("raw_mouse_", ""); merged.setdefault(base, {})["raw_mouse"] = data
                else: merged.setdefault(wid, {}).update(data if isinstance(data, dict) else {"raw_mouse": data})
            except: continue
        self.weapon_ids = sorted(merged.keys()); self.all_data = merged
        self.dropdown.blockSignals(True); self.dropdown.clear(); self.dropdown.addItems(self.weapon_ids); self.dropdown.blockSignals(False)
        if self.weapon_ids:
            idx = self.dropdown.findText(cur)
            self.dropdown.setCurrentIndex(idx if idx >= 0 else 0); self.update_view(self.dropdown.currentText())

    def update_view(self, weapon_id):
        self._style_axes()
        self.ax.set_title(f"Recoil Pattern: {weapon_id}", color="#ebebeb", fontsize=10)
        if self.show_grid: self.ax.grid(True, linestyle="--", color="#37373c", alpha=0.5)
        while self.stats_layout.count():
            w = self.stats_layout.takeAt(0).widget()
            if w: w.deleteLater()
        data = self.all_data.get(weapon_id, {})
        colors = ["#eb3c3c", "#3c88eb", "#3ceb88", "#ebeb3c", "#eb3ceb"]
        c_idx, drew = 0, False
        for key, vectors in data.items():
            if not vectors: continue
            x, y = [0.0], [0.0]
            for v in vectors:
                try: x.append(x[-1] + float(v[1])); y.append(y[-1] + float(v[0]))
                except: continue
            if len(x) > 1:
                col = colors[c_idx % len(colors)]
                self.ax.plot(x, y, linewidth=self.line_width, marker=".", markersize=self.marker_size, color=col, label=key)
                drew = True; self._add_stats_block(key, vectors)
            c_idx += 1
        if drew and self.show_legend: self.ax.legend(facecolor="#14141a", edgecolor="#37373c", labelcolor="#ebebeb")
        self.canvas.draw()

    def _add_stats_block(self, key, vectors):
        dp = [float(v[0]) for v in vectors if len(v) > 0]
        dy = [float(v[1]) for v in vectors if len(v) > 1]
        avg_p = sum(dp)/len(dp) if dp else 0; avg_y = sum(dy)/len(dy) if dy else 0
        container = QFrame(); container.setStyleSheet("background-color: #18181c; border: 1px solid #37373c; border-radius: 4px;")
        l = QVBoxLayout(container)
        header = QLabel(f"DATASET: {key.upper()}"); header.setStyleSheet("font-weight: bold; color: #eb3c3c; border: none; background: transparent;")
        info = QLabel(f"Samples: {len(vectors)}  |  Avg Pitch: {avg_p:.2f}  |  Avg Yaw: {avg_y:.2f}"); info.setStyleSheet("color: #8a8a90; border: none; background: transparent;")
        l.addWidget(header); l.addWidget(info); self.stats_layout.addWidget(container)


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

                                                               
    def create_group_box(self, title: str):
        return SectionFrame(title)

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
        # Scroll container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background-color: #14141a; border: none; }")

        content = QWidget(); content.setStyleSheet("background-color: #14141a;")
        layout = QVBoxLayout(content)
        layout.setSpacing(10); layout.setContentsMargins(10, 10, 10, 10)

        # 2-column layout
        cols = QHBoxLayout(); cols.setSpacing(10)
        col1 = QVBoxLayout(); col1.setSpacing(10)
        col2 = QVBoxLayout(); col2.setSpacing(10)

        # --- Column 1: Core ---
        main_g = self.create_group_box("Trigger Master")
        main_l = QVBoxLayout(main_g)
        self.add_checkbox(main_l, "Enable TriggerBot", "triggerbot_enabled",
                          on_toggle=self._toggle_triggerbot)
        self.add_checkbox(main_l, "Always On", "triggerbot_always_on")
        self.add_checkbox(main_l, "Team Check", "shoot_teammates")
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color: #8a8a90; font-style: italic;")
        main_l.addWidget(self.status_label)
        col1.addWidget(main_g)

        key_g = self.create_group_box("Activation")
        key_l = QVBoxLayout(key_g)
        self.trigger_key_label = QLabel(f"Hot Key: {getattr(self.CFG, 'trigger_key', 'mouse5')}")
        self.trigger_key_label.setStyleSheet("color: #f0eaea;")
        key_l.addWidget(self.trigger_key_label)
        self.set_key_btn = QPushButton("Change Key")
        self.set_key_btn.clicked.connect(self.set_trigger_key)
        key_l.addWidget(self.set_key_btn)
        col1.addWidget(key_g)
        col1.addStretch()

        # --- Column 2: Timing ---
        beh_g = self.create_group_box("Behavior & Timing")
        beh_l = QVBoxLayout(beh_g)
        self.add_float_slider(beh_l, "Cooldown (s)", "triggerbot_cooldown", 0.00, 1.00, 100, "s")
        self.add_float_slider(beh_l, "Delay Min (s)", "trigger_delay_min", 0.000, 0.150, 1000, "s")
        self.add_float_slider(beh_l, "Delay Max (s)", "trigger_delay_max", 0.000, 0.250, 1000, "s")
        col2.addWidget(beh_g)

        safe_g = self.create_group_box("Safety")
        safe_l = QVBoxLayout(safe_g)
        self.add_checkbox(safe_l, "Require VisCheck", "trigger_require_vischeck", default=True)
        col2.addWidget(safe_g)
        col2.addStretch()

        cols.addLayout(col1, 1)
        cols.addLayout(col2, 1)
        layout.addLayout(cols)

        scroll.setWidget(content)
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

                                      
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
        self.trigger_key_label.setText("Press any key…")
        self.trigger_key_label.setStyleSheet("color: #eb3c3c; font-weight: bold;")
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
            self.trigger_key_label.setText(f"Trigger Key: {getattr(self.CFG,'trigger_key','')}")
            self.trigger_key_label.setStyleSheet("color: #f0eaea; font-weight: normal;")
            self.set_key_btn.setEnabled(True)

    def key_set(self, key_name):
        setattr(self.CFG, "trigger_key", key_name)
        self.trigger_key_label.setText(f"Trigger Key: {key_name}")
        self.trigger_key_label.setStyleSheet("color: #ffffff; font-weight: bold;")
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

# ------------------------------------------------------------
# Radar defaults (safe; only sets missing attributes)
# ------------------------------------------------------------
def _ensure_attr(obj, key, default):
    try:
        if not hasattr(obj, key):
            setattr(obj, key, default)
    except Exception:
        pass

for _obj in (Config, cfg):
    _ensure_attr(_obj, "radar_enabled", False)
    _ensure_attr(_obj, "radar_stop", False)
    _ensure_attr(_obj, "radar_x", 40)
    _ensure_attr(_obj, "radar_y", 120)
    _ensure_attr(_obj, "radar_width", 280)
    _ensure_attr(_obj, "radar_height", 280)
    _ensure_attr(_obj, "radar_alpha", 235)
    _ensure_attr(_obj, "radar_fps", 60.0)
    _ensure_attr(_obj, "radar_reader_fps", 60.0)
    _ensure_attr(_obj, "radar_always_on_top", True)
    _ensure_attr(_obj, "radar_show_team", True)
    _ensure_attr(_obj, "radar_show_me_dir", True)
    _ensure_attr(_obj, "radar_show_enemy_dir", True)
    _ensure_attr(_obj, "radar_show_team_dir", False)
    _ensure_attr(_obj, "radar_fixed_range", False)
    _ensure_attr(_obj, "radar_range_units", 3000.0)

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

radar_thread = None
radar_app = None

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
