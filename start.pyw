import os
import sys
import random
import string
import logging
import subprocess
import time
from pathlib import Path
from cryptography.fernet import Fernet
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox, QHBoxLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
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

# Auto conversion thread with integrated functionality
class AutoConvertThread(QThread):
    log_message = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()

    def run(self):
        """Run the complete auto conversion process with logging"""
        try:
            self.log_message.emit("CS2 Auto Physics Converter")
            self.log_message.emit("=" * 40)
            
            # Get the maps directory
            script_dir = Path("maps").absolute()
            
            # Define executable paths (look in maps directory)
            phys_extractor_exe = script_dir / "PhysExtractor.exe"
            vphys_to_opt_exe = script_dir / "VPhysToOpt.exe"
            
            # Check if executables exist
            if not phys_extractor_exe.exists():
                self.log_message.emit(f"ERROR: PhysExtractor.exe not found at: {phys_extractor_exe}")
                self.log_message.emit("Please ensure PhysExtractor.exe is in the maps directory")
                return
            
            if not vphys_to_opt_exe.exists():
                self.log_message.emit(f"ERROR: VPhysToOpt.exe not found at: {vphys_to_opt_exe}")
                self.log_message.emit("Please ensure VPhysToOpt.exe is in the maps directory")
                return
            
            self.log_message.emit(f"PhysExtractor: {phys_extractor_exe}")
            self.log_message.emit(f"VPhysToOpt: {vphys_to_opt_exe}")
            self.log_message.emit(f"Working directory: {script_dir}")
            self.log_message.emit("")
            
            # Step 1: Run PhysExtractor.exe
            self.log_message.emit("Step 1: Running PhysExtractor to extract .vphys files...")
            self.log_message.emit("-" * 50)
            
            try:
                # Run PhysExtractor.exe
                result = subprocess.run([str(phys_extractor_exe)], 
                                      capture_output=False, 
                                      text=True, 
                                      cwd=str(script_dir))
                
                if result.returncode != 0:
                    self.log_message.emit(f"ERROR: PhysExtractor failed with return code: {result.returncode}")
                    return
                    
            except Exception as e:
                self.log_message.emit(f"ERROR running PhysExtractor: {e}")
                return
            
            self.log_message.emit("PhysExtractor completed!")
            
            # Step 2: Find all .vphys files in current directory
            self.log_message.emit("")
            self.log_message.emit("Step 2: Finding .vphys files to convert...")
            self.log_message.emit("-" * 50)
            
            vphys_files = list(Path(script_dir).glob("*.vphys"))
            
            if not vphys_files:
                self.log_message.emit("No .vphys files found in the directory.")
                return
            
            self.log_message.emit(f"Found {len(vphys_files)} .vphys files to convert:")
            for i, file in enumerate(vphys_files, 1):
                self.log_message.emit(f"  {i}. {file.name}")
            
            self.log_message.emit("")
            
            # Step 3: Convert each .vphys file with VPhysToOpt.exe
            self.log_message.emit("Step 3: Converting .vphys files...")
            self.log_message.emit("-" * 50)
            
            converted_count = 0
            failed_count = 0
            
            for i, vphys_file in enumerate(vphys_files, 1):
                self.log_message.emit(f"Converting {i}/{len(vphys_files)}: {vphys_file.name}")
                
                try:
                    # Run VPhysToOpt.exe with the directory path containing the .vphys file
                    result = subprocess.run([str(vphys_to_opt_exe), str(script_dir)],
                                          capture_output=True,
                                          text=True,
                                          cwd=str(script_dir),
                                          timeout=60)  # 60 second timeout per file
                    
                    if result.returncode == 0:
                        self.log_message.emit(f"  ✓ Successfully converted: {vphys_file.name}")
                        
                        # Remove the original .vphys file after successful conversion
                        try:
                            vphys_file.unlink()
                            self.log_message.emit(f"  ✓ Removed original: {vphys_file.name}")
                            converted_count += 1
                        except Exception as e:
                            self.log_message.emit(f"  ⚠ Warning: Could not remove {vphys_file.name}: {e}")
                            converted_count += 1  # Still count as converted
                            
                    else:
                        self.log_message.emit(f"  ✗ Failed to convert: {vphys_file.name}")
                        self.log_message.emit(f"    Return code: {result.returncode}")
                        if result.stderr:
                            self.log_message.emit(f"    Error: {result.stderr.strip()}")
                        failed_count += 1
                        
                except subprocess.TimeoutExpired:
                    self.log_message.emit(f"  ✗ Timeout converting: {vphys_file.name}")
                    failed_count += 1
                    
                except Exception as e:
                    self.log_message.emit(f"  ✗ Error converting {vphys_file.name}: {e}")
                    failed_count += 1
                
                # Small delay between conversions
                time.sleep(0.5)
            
            # Step 4: Summary
            self.log_message.emit("")
            self.log_message.emit("=" * 50)
            self.log_message.emit("CONVERSION SUMMARY")
            self.log_message.emit("=" * 50)
            self.log_message.emit(f"Total files found: {len(vphys_files)}")
            self.log_message.emit(f"Successfully converted: {converted_count}")
            self.log_message.emit(f"Failed conversions: {failed_count}")
            
            if failed_count == 0:
                self.log_message.emit("")
                self.log_message.emit("🎉 All files converted successfully!")
            else:
                self.log_message.emit("")
                self.log_message.emit(f"⚠ {failed_count} files failed to convert.")
            
            # Check for any remaining .vphys files
            remaining_vphys = list(Path(script_dir).glob("*.vphys"))
            if remaining_vphys:
                self.log_message.emit(f"Remaining .vphys files: {len(remaining_vphys)}")
                for file in remaining_vphys:
                    self.log_message.emit(f"  - {file.name}")
            else:
                self.log_message.emit("✓ All .vphys files have been processed and removed.")
            
            self.log_message.emit("")
            self.log_message.emit("Conversion process completed!")
            
        except Exception as e:
            self.log_message.emit(f"CRITICAL ERROR: {e}")
        finally:
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

        self.auto_convert_btn = QPushButton("AUTO CONVERT MAPS")
        self.auto_convert_btn.setObjectName("btn-red")
        self.auto_convert_btn.setProperty("class", "ms-btn")
        self.auto_convert_btn.setFont(self.h2)
        self.auto_convert_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.auto_convert_btn.clicked.connect(self.run_auto_convert)

        for btn in [self.update_btn, self.generate_btn, self.run_btn, self.auto_convert_btn]:
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

    def run_auto_convert(self):
        """Run the auto conversion process with integrated logging"""
        if not os.path.exists("maps"):
            logging.error("Maps folder not found!")
            QMessageBox.warning(self, "Error", "Maps folder not found! Please create the maps folder first.")
            return

        try:
            logging.info("Starting auto conversion process...")
            
            # Disable button during execution
            self.auto_convert_btn.setEnabled(False)
            self.auto_convert_btn.setText("CONVERTING...")
            
            # Start the conversion thread
            self.auto_convert_thread = AutoConvertThread()
            self.auto_convert_thread.log_message.connect(self.log_conversion_message)
            self.auto_convert_thread.finished.connect(self.on_conversion_finished)
            self.auto_convert_thread.start()
            
        except Exception as e:
            logging.error(f"Failed to start auto convert: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start auto convert process:\n\n{e}")
            
            # Re-enable button on error
            self.auto_convert_btn.setEnabled(True)
            self.auto_convert_btn.setText("AUTO CONVERT MAPS")
    
    def log_conversion_message(self, message):
        """Log a message from the conversion thread"""
        logging.info(message)
    
    def on_conversion_finished(self):
        """Called when conversion process finishes"""
        logging.info("Auto conversion process completed!")
        self.auto_convert_btn.setEnabled(True)
        self.auto_convert_btn.setText("AUTO CONVERT MAPS")

# Entry point
def main():
    app = QApplication(sys.argv)
    window = LauncherGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
