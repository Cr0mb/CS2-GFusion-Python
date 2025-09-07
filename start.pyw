import os
import sys
import random
import string
import logging
import subprocess
import time
from cryptography.fernet import Fernet
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont

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
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(100, 100, 600, 500)
        self.drag_position = None

        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: white;
                font-family: Consolas;
                border: 1px solid #3ecf8e;
                border-radius: 10px;
            }
            QPushButton {
                background-color: #3c3f41;
                padding: 8px;
                border-radius: 6px;
                color: white;
            }
            QPushButton:hover {
                background-color: #505354;
            }
            QTextEdit {
                background-color: #2b2b2b;
                border: 1px solid #444;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        self.title_bar = QLabel(" GFusion AES Launcher")
        self.title_bar.setFont(QFont("Consolas", 14, QFont.Bold))
        self.title_bar.setStyleSheet("color: #3ecf8e;")
        self.title_bar.setFixedHeight(30)
        self.title_bar.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        layout.addWidget(self.title_bar)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.update_btn = QPushButton("Update Offsets")
        self.update_btn.clicked.connect(self.update_offsets)

        self.generate_btn = QPushButton("Generate Launcher")
        self.generate_btn.clicked.connect(self.generate_launcher)

        self.run_btn = QPushButton("Run Launcher")
        self.run_btn.clicked.connect(self.run_launcher)

        for btn in [self.update_btn, self.generate_btn, self.run_btn]:
            layout.addWidget(btn)

        self.setLayout(layout)

        # Setup GUI-only logging
        log_handler = QTextEditLogger(self.log_output)
        log_handler.setFormatter(logging.Formatter('[*] %(message)s'))
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        if logger.hasHandlers():
            logger.handlers.clear()
        logger.addHandler(log_handler)

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

