import os
import sys
import random
import string
import logging
import subprocess
import time
from cryptography.fernet import Fernet
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox, QHBoxLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QCursor, QIcon

MAIN_SCRIPT = "GFusion.py"
LAUNCHER_FILE = "launcher.py"
FOLDERS_TO_OBFUSCATE = ["Features", "Process"]
FERNET_KEY = Fernet.generate_key()
fernet = Fernet(FERNET_KEY)

# QTextEdit Logger
class QTextEditLogger(QObject, logging.Handler):
    new_log = pyqtSignal(str)

    def __init__(self, text_edit):
        QObject.__init__(self)
        logging.Handler.__init__(self)
        self.widget = text_edit
        self.new_log.connect(self.widget.append)

    def emit(self, record):
        msg = self.format(record)
        self.new_log.emit(msg)

# File helpers
def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def get_py_files():
    files = [MAIN_SCRIPT]
    for folder in FOLDERS_TO_OBFUSCATE:
        for root, _, filenames in os.walk(folder):
            for f in filenames:
                if f.endswith(".py"):
                    files.append(os.path.join(root, f))
    logging.info(f"Collected {len(files)} Python files for obfuscation.")
    return files

def encrypt_file(path):
    with open(path, "rb") as f:
        return fernet.encrypt(f.read()).decode("utf-8")

def module_name_from_path(path):
    path = os.path.splitext(path)[0]
    parts = path.replace("\\", "/").split("/")
    return ".".join(parts)

def generate_launcher():
    logging.info("Generating AES-encrypted launcher...")
    py_files = get_py_files()
    modules_enc = {}
    for f in py_files:
        mod_name = module_name_from_path(f)
        enc = encrypt_file(f)
        modules_enc[mod_name] = enc

    launcher_code = f'''import sys
import importlib.abc
import importlib.util
from cryptography.fernet import Fernet
import traceback

key = {FERNET_KEY!r}
fernet = Fernet(key)
modules = {modules_enc!r}

class AESLoader(importlib.abc.Loader):
    def __init__(self, name):
        self.name = name
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        try:
            code_enc = modules[self.name]
            code = fernet.decrypt(code_enc.encode()).decode('utf-8')
            exec(code, module.__dict__)
        except Exception as e:
            print(f"Error loading module {{self.name}}: {{e}}")
            traceback.print_exc()
            raise
    def get_code(self, fullname):
        source = fernet.decrypt(modules[fullname].encode()).decode('utf-8')
        return compile(source, '<string>', 'exec')
    def get_source(self, fullname):
        return fernet.decrypt(modules[fullname].encode()).decode('utf-8')

class AESFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in modules:
            return importlib.util.spec_from_loader(fullname, AESLoader(fullname))
        return None

sys.meta_path.insert(0, AESFinder())

if __name__ == '__main__':
    import runpy
    runpy.run_module('{module_name_from_path(MAIN_SCRIPT)}', run_name='__main__')
    import sys
    sys.exit()
'''

    with open(LAUNCHER_FILE, "w", encoding="utf-8") as f:
        f.write(launcher_code)

    logging.info(f"Launcher generated: {LAUNCHER_FILE} with {len(modules_enc)} modules.")

# Offset update thread
class OffsetUpdater(QThread):
    finished = pyqtSignal()

    def run(self):
        if not os.path.isdir("Process"):
            logging.error("Process directory does not exist!")
        else:
            logging.info("Updating offsets by running Process/offset_update.py...")
            os.system(f'"{sys.executable}" Process/offset_update.py')
        self.finished.emit()

# GUI
class LauncherGUI(QWidget):
    def __init__(self):
        super().__init__()
        # Classic window (not translucent) for MS Paint feel
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setGeometry(150, 120, 760, 540)
        self.setMinimumSize(640, 420)
        self.drag_position = None

        # Fonts
        self.h1 = QFont("Comic Sans MS", 14, QFont.Bold)
        self.h2 = QFont("Comic Sans MS", 10, QFont.Bold)
        self.log_font = QFont("Consolas", 10)

        # Main style: light gray background, chunky black border, hand-drawn vibes
        self.setStyleSheet("""
            QWidget#root {
                background-color: #e9e9e9;   /* light paper-like background */
                border: 6px solid #000000;   /* thick black border like MS Paint window */
            }
            QLabel#title {
                color: white;
                padding-left: 10px;
            }
            #titlebar {
                background-color: #2b5797;   /* classic blue titlebar */
                border-bottom: 3px solid #000;
            }
            QPushButton.ms-btn {
                border: 3px solid #000;
                border-radius: 4px;
                padding: 12px 18px;
                font-family: "Comic Sans MS";
                font-weight: 700;
                min-height: 44px;
                min-width: 160px;
                box-sizing: border-box;
            }
            QPushButton.ms-btn:hover { cursor: pointer; }
            QPushButton#btn-yellow { background: #ffeb3b; }
            QPushButton#btn-red    { background: #f44336; color: #fff; }
            QPushButton#btn-blue   { background: #2196f3; color: #fff; }
            QPushButton#btn-green  { background: #4caf50; color: #fff; }

            QPushButton#closeBtn {
                background-color: #ff3b3b;
                color: white;
                border: 3px solid #000;
                min-width: 36px;
                min-height: 28px;
                font-weight: bold;
            }

            QTextEdit#log {
                background-color: #ffffff;
                border: 3px solid #000;
                padding: 8px;
            }

            QWidget#palette {
                background-color: transparent;
                border-bottom: 3px solid #000;
                padding: 6px;
            }

            QLabel.section-title {
                font-family: "Comic Sans MS";
                font-weight: 700;
                padding: 6px 0;
            }
        """)

        # Root container so we can target it with stylesheet
        root = QWidget(self)
        root.setObjectName("root")
        root.setGeometry(0, 0, self.width(), self.height())

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 6, 8, 8)
        main_layout.setSpacing(10)

        # Title bar (drag & close)
        titlebar = QWidget()
        titlebar.setObjectName("titlebar")
        titlebar_layout = QHBoxLayout()
        titlebar_layout.setContentsMargins(6, 2, 6, 2)

        title_label = QLabel(" GFusion AES Launcher")
        title_label.setObjectName("title")
        title_label.setFont(self.h1)
        title_label.setFixedHeight(36)
        title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        close_btn = QPushButton("X")
        close_btn.setObjectName("closeBtn")
        close_btn.setFont(QFont("Comic Sans MS", 10, QFont.Bold))
        close_btn.clicked.connect(self.close)
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))

        titlebar_layout.addWidget(title_label)
        titlebar_layout.addStretch()
        titlebar_layout.addWidget(close_btn)
        titlebar.setLayout(titlebar_layout)
        titlebar.setFixedHeight(44)
        titlebar.mousePressEvent = self.title_mouse_press
        titlebar.mouseMoveEvent = self.title_mouse_move

        main_layout.addWidget(titlebar)

        # Paint-like color palette (purely visual)
        palette = QWidget()
        palette.setObjectName("palette")
        pal_layout = QHBoxLayout()
        pal_layout.setContentsMargins(4, 2, 4, 2)

        for color_name, w in [("#ffeb3b", "Yellow"), ("#f44336", "Red"), ("#2196f3", "Blue"), ("#4caf50", "Green")]:
            sw = QLabel()
            sw.setFixedSize(44, 28)
            sw.setStyleSheet(f"background:{color_name}; border:3px solid #000;")
            pal_layout.addWidget(sw)
            pal_layout.addSpacing(6)

        pal_layout.addStretch()
        palette.setLayout(pal_layout)
        palette.setFixedHeight(44)
        main_layout.addWidget(palette)

        # Log output area (like the drawing/canvas area but used for logs)
        self.log_output = QTextEdit()
        self.log_output.setObjectName("log")
        self.log_output.setReadOnly(True)
        self.log_output.setFont(self.log_font)
        self.log_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.log_output)

        # Buttons row (large chunky MS Paint style)
        btn_row = QWidget()
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(12)

        self.update_btn = QPushButton("UPDATE OFFSETS")
        self.update_btn.setObjectName("btn-blue")
        self.update_btn.setProperty("class", "ms-btn")
        self.update_btn.setFont(self.h2)
        self.update_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.update_btn.clicked.connect(self.update_offsets)

        self.generate_btn = QPushButton("GENERATE LAUNCHER")
        self.generate_btn.setObjectName("btn-yellow")
        self.generate_btn.setProperty("class", "ms-btn")
        self.generate_btn.setFont(self.h2)
        self.generate_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.generate_btn.clicked.connect(self.generate_launcher)

        self.run_btn = QPushButton("RUN LAUNCHER")
        self.run_btn.setObjectName("btn-green")
        self.run_btn.setProperty("class", "ms-btn")
        self.run_btn.setFont(self.h2)
        self.run_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.run_btn.clicked.connect(self.run_launcher)

        for btn in [self.update_btn, self.generate_btn, self.run_btn]:
            btn.setStyleSheet("")  # let the parent stylesheet handle visuals
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn_layout.addWidget(btn)

        btn_row.setLayout(btn_layout)
        main_layout.addWidget(btn_row)

        root.setLayout(main_layout)
        self.root = root

        # Setup GUI-only logging
        log_handler = QTextEditLogger(self.log_output)
        log_handler.setFormatter(logging.Formatter('[*] %(message)s'))
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        if logger.hasHandlers():
            logger.handlers.clear()
        logger.addHandler(log_handler)

    # Titlebar dragging handlers
    def title_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def title_mouse_move(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    # Fallback drag when clicking anywhere on the window
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def update_offsets(self):
        self.update_btn.setEnabled(False)
        self.thread = OffsetUpdater()
        self.thread.finished.connect(lambda: self.update_btn.setEnabled(True))
        self.thread.start()

    def generate_launcher(self):
        generate_launcher()

    def run_launcher(self):
        if os.path.exists(LAUNCHER_FILE):
            logging.info(f"Launching launcher: {LAUNCHER_FILE}")

            # Random small delay to reduce detection pattern
            time.sleep(random.uniform(0.5, 1.5))

            # Windows specific flag to hide console window
            CREATE_NO_WINDOW = 0x08000000

            try:
                subprocess.Popen(
                    [sys.executable, LAUNCHER_FILE],
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
                logging.info("Launcher started stealthily, exiting GUI.")
                QApplication.quit()
            except Exception as e:
                logging.error(f"Failed to start launcher stealthily: {e}")
        else:
            QMessageBox.warning(self, "Error", f"{LAUNCHER_FILE} not found. Please generate it first.")

# Entry point
def main():
    app = QApplication(sys.argv)
    window = LauncherGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
