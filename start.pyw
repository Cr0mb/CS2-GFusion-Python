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
        # Ensure module name is a string, not a set or other type
        if not isinstance(mod_name, str):
            logging.error(f"Module name is not a string: {mod_name} (type: {type(mod_name)})")
            mod_name = str(mod_name)
        enc = encrypt_file(f)
        modules_enc[mod_name] = enc
        logging.info(f"Processing module: '{mod_name}' from file: {f}")

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
            # Debug: Check the type of self.name
            name_value = {{self.name}}
            if not isinstance(name_value, str):
                print("WARNING: Module name is not a string: " + str(name_value) + " (type: " + str(type(name_value)) + ")")
                # Convert to string if it's somehow not a string
                if isinstance(name_value, set) and len(name_value) == 1:
                    name_value = next(iter(name_value))  # Get the single item from set
                else:
                    name_value = str(name_value).strip("{{}}").strip("''")  # Fallback conversion
            
            code_enc = modules[name_value]
            code = fernet.decrypt(code_enc.encode()).decode('utf-8')
            
            # Set essential module attributes that modules expect
            module.__name__ = name_value
            module.__package__ = None
            
            # Set __file__ to a fake path that makes sense for the module
            if name_value == "GFusion":
                module.__file__ = "GFusion.py"
            elif "." in name_value:
                # For modules like "Features.esp", set appropriate path
                parts = name_value.split(".")
                module.__file__ = "/".join(parts) + ".py"
            else:
                module.__file__ = name_value + ".py"
            
            print("Executing module: " + name_value)
            exec(code, module.__dict__)
            print("Successfully loaded module: " + name_value)
        except Exception as e:
            print("Error loading module " + str({{self.name}}) + ": " + str(e))
            print("Module name type: " + str(type({{self.name}})))
            print("Module name value: " + str({{self.name}}))
            traceback.print_exc()
            raise
    def get_code(self, fullname):
        source = fernet.decrypt(modules[fullname].encode()).decode('utf-8')
        return compile(source, '<encrypted_' + fullname + '>', 'exec')
    def get_source(self, fullname):
        return fernet.decrypt(modules[fullname].encode()).decode('utf-8')

class AESFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in modules:
            # Ensure fullname is a string
            module_name = str(fullname) if not isinstance(fullname, str) else fullname
            return importlib.util.spec_from_loader(module_name, AESLoader(module_name))
        return None

sys.meta_path.insert(0, AESFinder())

# Set up environment for encrypted modules
import os
# Ensure current directory is set correctly
if not os.getcwd().endswith('CS2'):
    # Try to find the CS2 directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if 'CS2' in script_dir:
        cs2_dir = script_dir[:script_dir.rfind('CS2') + 3]
        os.chdir(cs2_dir)
        print("Changed working directory to:", os.getcwd())

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
        
        # Fonts consistent with GFusion
        self.h1 = QFont("MS Sans Serif", 10, QFont.Bold)
        self.h2 = QFont("MS Sans Serif", 9, QFont.Bold)
        self.log_font = QFont("Consolas", 9)

        # Apply GFusion menu styling
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
                color: #000000;
                font-family: "MS Sans Serif","Tahoma",sans-serif;
                font-size: 9pt;
            }
            QLabel {
                color: #000000;
            }
            QCheckBox {
                color: #000000;
                spacing: 2px;
            }
            QCheckBox::indicator {
                width: 12px; height: 12px;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #000000;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #e6e6e6;
            }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #ffffff;
                border: 1px solid #000000;
            }
            QScrollArea {
                border: none;
            }
            QFrame {
                border: 1px solid #c0c0c0;
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

        # Check admin status for title
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
        
        admin_status = " - Administrator" if is_admin else " - User Mode"
        title_label = QLabel(f" GFusion AES Launcher{admin_status}")
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

        # Debug button (smaller)
        self.debug_btn = QPushButton("DEBUG LAUNCHER")
        self.debug_btn.setObjectName("btn-yellow")
        self.debug_btn.setProperty("class", "ms-btn")
        self.debug_btn.setFont(QFont("Comic Sans MS", 8, QFont.Bold))
        self.debug_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.debug_btn.clicked.connect(self.debug_launcher)
        self.debug_btn.setMaximumHeight(30)

        for btn in [self.update_btn, self.generate_btn, self.run_btn, self.auto_convert_btn]:
            btn.setStyleSheet("")  # let the parent stylesheet handle visuals
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn_layout.addWidget(btn)
        
        # Add debug button on a separate row
        debug_layout = QHBoxLayout()
        debug_layout.addStretch()
        debug_layout.addWidget(self.debug_btn)
        debug_layout.addStretch()

        btn_row.setLayout(btn_layout)
        main_layout.addWidget(btn_row)
        main_layout.addLayout(debug_layout)

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
        try:
            logging.info("Starting launcher generation...")
            generate_launcher()
            
            # Verify the launcher was created and is valid
            if os.path.exists(LAUNCHER_FILE):
                file_size = os.path.getsize(LAUNCHER_FILE)
                logging.info(f"✓ Launcher generated successfully: {LAUNCHER_FILE} ({file_size} bytes)")
                
                # Quick syntax check
                try:
                    with open(LAUNCHER_FILE, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    # Try to compile the code to check for syntax errors
                    compile(code, LAUNCHER_FILE, 'exec')
                    logging.info("✓ Launcher syntax validation passed")
                    
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Launcher generated successfully!\n\n"
                        f"File: {LAUNCHER_FILE}\n"
                        f"Size: {file_size} bytes\n\n"
                        f"You can now click 'RUN LAUNCHER' to start GFusion."
                    )
                    
                except SyntaxError as e:
                    logging.error(f"Launcher has syntax errors: {e}")
                    QMessageBox.critical(
                        self,
                        "Launcher Syntax Error",
                        f"The generated launcher has syntax errors:\n\n{e}"
                    )
                except Exception as e:
                    logging.error(f"Launcher validation error: {e}")
                    QMessageBox.warning(
                        self,
                        "Launcher Validation Warning",
                        f"Could not fully validate launcher:\n\n{e}"
                    )
            else:
                logging.error("Launcher file was not created!")
                QMessageBox.critical(
                    self,
                    "Generation Failed",
                    f"Launcher file '{LAUNCHER_FILE}' was not created.\n\n"
                    f"Check the log for errors."
                )
                
        except Exception as e:
            logging.error(f"Failed to generate launcher: {e}")
            QMessageBox.critical(
                self,
                "Generation Error", 
                f"Failed to generate launcher:\n\n{e}"
            )

    def run_launcher(self):
        if os.path.exists(LAUNCHER_FILE):
            logging.info(f"Launching launcher: {LAUNCHER_FILE}")
            
            # Check admin status (should already be admin from startup)
            import ctypes
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            except:
                is_admin = False
            
            if is_admin:
                logging.info("✓ Running as Administrator - Kernel mode available")
            else:
                logging.info("⚠ Running as User - Kernel mode unavailable")

            # Test the launcher file first
            logging.info("Testing launcher file before execution...")
            try:
                # First, try to run a simpler test
                test_code = f'''
import sys
import os
try:
    sys.path.insert(0, os.getcwd())
    print("Testing basic imports...")
    
    # Test cryptography first
    from cryptography.fernet import Fernet
    print("Cryptography import: OK")
    
    # Test launcher file parsing
    with open("{LAUNCHER_FILE}", "r", encoding="utf-8") as f:
        content = f.read()
    print("Launcher file read: OK")
    
    # Test compilation
    compile(content, "{LAUNCHER_FILE}", "exec")
    print("Launcher compilation: OK")
    
    print("Basic tests passed - trying full execution...")
    exec(content)
    
except Exception as e:
    print("Test failed:", str(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''
                
                result = subprocess.run(
                    [sys.executable, "-c", test_code],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    logging.error(f"Launcher test failed with return code: {result.returncode}")
                    if result.stderr:
                        logging.error(f"Error output: {result.stderr}")
                    if result.stdout:
                        logging.info(f"Standard output: {result.stdout}")
                    
                    QMessageBox.critical(
                        self, 
                        "Launcher Test Failed", 
                        f"The launcher file has errors and cannot run:\n\n"
                        f"Return code: {result.returncode}\n"
                        f"Error: {result.stderr[:500]}..."
                    )
                    return
                else:
                    logging.info("✓ Launcher test successful")
                    
            except subprocess.TimeoutExpired:
                logging.error("Launcher test timed out")
                QMessageBox.warning(
                    self, 
                    "Launcher Test Timeout", 
                    "The launcher test timed out. It may be working but took too long to start."
                )
            except Exception as e:
                logging.error(f"Launcher test error: {e}")
                QMessageBox.critical(
                    self, 
                    "Launcher Test Error", 
                    f"Could not test the launcher:\n\n{e}"
                )
                return

            # Random small delay to reduce detection pattern
            time.sleep(random.uniform(0.5, 1.5))

            # Now launch the actual program
            logging.info("Starting launcher in background...")
            
            try:
                # Launch with visible console for debugging (remove CREATE_NO_WINDOW for now)
                # CREATE_NO_WINDOW = 0x08000000
                
                process = subprocess.Popen(
                    [sys.executable, LAUNCHER_FILE],
                    # creationflags=CREATE_NO_WINDOW,  # Commented out for debugging
                    # stdout=subprocess.DEVNULL,      # Commented out for debugging  
                    # stderr=subprocess.DEVNULL,      # Commented out for debugging
                    # stdin=subprocess.DEVNULL        # Commented out for debugging
                )
                
                # Give it a moment to start
                time.sleep(2)
                
                # Check if process is still running
                if process.poll() is None:
                    logging.info("✓ Launcher started successfully and is running")
                    logging.info(f"Process ID: {process.pid}")
                    
                    # Ask user if they want to close the GUI
                    result = QMessageBox.question(
                        self,
                        "Launcher Started",
                        "Launcher started successfully!\n\n"
                        "Do you want to close this launcher GUI?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    
                    if result == QMessageBox.Yes:
                        QApplication.quit()
                else:
                    exit_code = process.poll()
                    logging.error(f"Launcher exited immediately with code: {exit_code}")
                    QMessageBox.critical(
                        self,
                        "Launcher Failed",
                        f"The launcher started but exited immediately.\n"
                        f"Exit code: {exit_code}\n\n"
                        f"Check the console window for error details."
                    )
                    
            except Exception as e:
                logging.error(f"Failed to start launcher: {e}")
                QMessageBox.critical(self, "Launch Error", f"Failed to start launcher:\n\n{e}")
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
    
    def debug_launcher(self):
        """Debug the launcher file and show detailed information"""
        if not os.path.exists(LAUNCHER_FILE):
            QMessageBox.warning(self, "Debug Error", f"{LAUNCHER_FILE} not found. Generate it first.")
            return
        
        try:
            # Get file info
            file_size = os.path.getsize(LAUNCHER_FILE)
            file_mtime = os.path.getmtime(LAUNCHER_FILE)
            
            logging.info(f"=== LAUNCHER DEBUG INFO ===")
            logging.info(f"File: {LAUNCHER_FILE}")
            logging.info(f"Size: {file_size} bytes")
            logging.info(f"Modified: {time.ctime(file_mtime)}")
            logging.info(f"Exists: {os.path.exists(LAUNCHER_FILE)}")
            logging.info(f"Readable: {os.access(LAUNCHER_FILE, os.R_OK)}")
            
            # Try to read and validate the file
            with open(LAUNCHER_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logging.info(f"Content length: {len(content)} characters")
            
            # Check for key components
            has_imports = "import" in content
            has_aes = "AESLoader" in content or "Fernet" in content
            has_main = "__main__" in content
            has_modules = "modules =" in content
            
            logging.info(f"Has imports: {has_imports}")
            logging.info(f"Has AES encryption: {has_aes}")
            logging.info(f"Has main execution: {has_main}")
            logging.info(f"Has modules data: {has_modules}")
            
            # Try to compile
            try:
                compile(content, LAUNCHER_FILE, 'exec')
                logging.info("✓ Syntax validation: PASSED")
            except SyntaxError as e:
                logging.error(f"✗ Syntax validation: FAILED - {e}")
            
            # Test import of required modules
            try:
                subprocess.run([sys.executable, "-c", "from cryptography.fernet import Fernet; print('Fernet OK')"], 
                             check=True, capture_output=True, text=True)
                logging.info("✓ Cryptography module: AVAILABLE")
            except:
                logging.error("✗ Cryptography module: MISSING")
            
            # Show first few lines for inspection
            lines = content.split('\n')[:10]
            logging.info("=== FIRST 10 LINES ===")
            for i, line in enumerate(lines, 1):
                logging.info(f"{i:2d}: {line[:80]}{'...' if len(line) > 80 else ''}")
            
            logging.info("=== DEBUG COMPLETE ===")
            
            QMessageBox.information(
                self,
                "Debug Complete",
                f"Debug information logged to console.\n\n"
                f"File size: {file_size} bytes\n"
                f"Syntax: {'✓ Valid' if 'PASSED' in str(logging) else '✗ Invalid'}\n"
                f"Components: {sum([has_imports, has_aes, has_main, has_modules])}/4 present"
            )
            
        except Exception as e:
            logging.error(f"Debug failed: {e}")
            QMessageBox.critical(self, "Debug Error", f"Failed to debug launcher:\n\n{e}")

# UAC elevation check and request
def check_admin_privileges():
    """Check if running as administrator and request elevation if not"""
    import ctypes
    
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except:
        is_admin = False
    
    if not is_admin:
        # Request UAC elevation
        try:
            # Show message about elevation
            print("Requesting Administrator privileges for kernel mode support...")
            
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

# Entry point
def main():
    # Check and request admin privileges first
    is_admin = check_admin_privileges()
    
    app = QApplication(sys.argv)
    window = LauncherGUI()
    
    # Set window icon to indicate admin status
    if is_admin:
        window.setWindowTitle("GFusion AES Launcher - Administrator")
    else:
        window.setWindowTitle("GFusion AES Launcher - User Mode")
    
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
