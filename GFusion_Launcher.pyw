import os
import sys
import random
import string
import logging
import subprocess
from datetime import datetime
import time
import zipfile
import requests
import shutil
from pathlib import Path
from cryptography.fernet import Fernet
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox,
    QHBoxLayout, QSizePolicy, QProgressBar
)

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QPropertyAnimation
from PyQt5.QtGui import QFont, QCursor, QIcon

MAIN_SCRIPT = "GFusion.py"
LAUNCHER_FILE = "launcher.py"
FOLDERS_TO_OBFUSCATE = ["Features", "Process"]
FERNET_KEY = Fernet.generate_key()
fernet = Fernet(FERNET_KEY)

GITHUB_OWNER = "Cr0mb"
GITHUB_REPO = "CS2-GFusion-Python"
GITHUB_BRANCH = "main"

RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}"
API_TREE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees/{GITHUB_BRANCH}?recursive=1"
API_COMMIT = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"

IGNORED_PATHS = (
    ".git/",
    ".github/",
    ".vscode/",
    "dist/",
    "build/",
)

ALLOWED_EXTENSIONS = (
    ".py", ".json", ".txt",
    ".opt",
    ".exe", ".dll", ".pyd",
    ".bat",
    ".vcxproj", ".filters", ".sln",
    ".ps1", ".inf", ".sys", ".64", ".sys.i64", ".cpp",
    ".h"
)



# ===============================
# UPDATE RULES (PATCH)
# ===============================

FORCE_INCLUDE_DIRS = (
    "Features",
    "Process",
    "Performance",
    "render",
    "config",
    "aimbot_data",
    "maps",
    "VisCheckCS2",
    "NeacController-main",
)

EXCLUDE_DIRS = (
    "/.vs/",
    "/__pycache__/",
    "/x64/Debug/",
    "/x64/Release/",
    "/build/",        # directory ONLY now
)


EXCLUDE_EXTENSIONS = (
    ".pyc", ".pdb", ".obj", ".lib", ".exp",
    ".tlog", ".iobj", ".ipdb", ".recipe",
    ".lastbuildstate", ".log", ".vc.db",
)

# Files we do NOT diff or hash – existence only
OPAQUE_EXTENSIONS = (
    ".dll", ".exe", ".opt", ".pyd", ".sys",
    ".so", ".dylib",
)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "GFusion-Updater",
    "Accept": "application/vnd.github.v3.raw",
})

ALLOWLIST_FILES = {
    "NeacController-main/NeacController/build.bat",
}


def should_skip_path(path: str) -> bool:
    p = path.replace("\\", "/")

    # --- ALLOWLIST OVERRIDE (FIRST) ---
    if p in ALLOWLIST_FILES:
        return False

    # --- HARD SKIP: IDE / BUILD OUTPUT DIRS ---
    if (
        "/.vs/" in p
        or "/__pycache__/" in p
        or "/x64/Debug/" in p
        or "/x64/Release/" in p
        or p.endswith("/build")          # directory
        or "/build/" in p                # directory contents
    ):
        return True

    # --- EXTENSION-BASED SKIP ---
    if p.endswith(EXCLUDE_EXTENSIONS):
        return True

    # --- RUNTIME NARROWING ---
    if p.startswith("maps/runtimes/"):
        return not p.startswith("maps/runtimes/win-x64/native")

    return False

def is_valid_repo_file(path: str) -> bool:
    if any(path.startswith(x) for x in IGNORED_PATHS):
        return False
    return path.endswith(ALLOWED_EXTENSIONS)

def is_special_root_file(path: str) -> bool:
    return path in (
        "vischeck.pyd",
    )

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
def mirror_directory(tree_items, prefix: str, log_cb):
    import hashlib

    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    files = [
        f["path"]
        for f in tree_items
        if f["type"] == "blob"
        and (
            is_valid_repo_file(f["path"])
            or is_special_root_file(f["path"])
        )
        and not should_skip_path(f["path"])
    ]


    for path in files:
        if should_skip_path(path):
            continue

        local = Path(path)

        # ⚡ FAST PATH: opaque binaries
        if path.endswith(OPAQUE_EXTENSIONS):
            if local.exists():
                continue  # ⬅ NO NETWORK, NO DELAY
            # missing → download
            try:
                url = f"{RAW_BASE}/{path}"
                r = SESSION.get(url, timeout=30)
                r.raise_for_status()
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(r.content)
                log_cb(f"Added: {path}")
            except Exception as e:
                log_cb(f"ERROR downloading {path}: {e}")
            continue

        # ------------------------
        # Text / code files only
        # ------------------------
        try:
            url = f"{RAW_BASE}/{path}"
            remote = conditional_get(path)
            if remote is None:
                continue  # unchanged, skip


            needs_update = True
            if local.exists():
                needs_update = sha256_file(local) != sha256_bytes(remote)

            if not needs_update:
                continue

            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(remote)
            log_cb(f"Updated: {path}")

        except Exception as e:
            log_cb(f"ERROR syncing {path}: {e}")

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

def download_extract_run_gfusion(log, progress_cb=None):
    from pathlib import Path

    GFUSION_ZIP_URL = "https://github.com/Cr0mb/CS2-GFusion-Python/releases/download/GFusion/GFusion.zip"
    GFUSION_EXE_DIR = Path("GFusion_Exe")
    GFUSION_ZIP_PATH = Path("GFusion.zip")

    def set_progress(pct: int):
        if progress_cb:
            progress_cb(max(0, min(100, int(pct))))

    try:
        GFUSION_EXE_DIR.mkdir(exist_ok=True)
        set_progress(0)

        # -------------------------
        # Download (streamed)
        # -------------------------
        if not GFUSION_ZIP_PATH.exists():
            log.info("Downloading GFusion.zip...")
            with SESSION.get(GFUSION_ZIP_URL, stream=True, timeout=60) as r:
                r.raise_for_status()

                total = int(r.headers.get("Content-Length", "0") or "0")
                if total > 0:
                    log.info(f"Download size: {total / (1024*1024):.2f} MB")
                else:
                    log.info("Download size: (unknown)")

                downloaded = 0
                chunk_size = 1024 * 256  # 256 KB

                tmp_path = GFUSION_ZIP_PATH.with_suffix(".zip.part")
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            set_progress(pct)
                            # log occasionally so console isn't spammed
                            if pct % 5 == 0:
                                log.info(f"Downloading... {pct}% ({downloaded}/{total} bytes)")
                        else:
                            # unknown total: show “activity”
                            if downloaded % (1024 * 1024 * 2) < chunk_size:
                                log.info(f"Downloading... {downloaded / (1024*1024):.2f} MB")

                tmp_path.replace(GFUSION_ZIP_PATH)
            log.info("✓ Download complete")
        else:
            log.info("GFusion.zip already exists, skipping download")
            set_progress(100)

        # -------------------------
        # Extract
        # -------------------------
        log.info("Extracting GFusion.zip...")
        set_progress(0)

        with zipfile.ZipFile(GFUSION_ZIP_PATH, "r") as zip_ref:
            members = zip_ref.infolist()
            total_members = max(1, len(members))
            for i, member in enumerate(members, 1):
                zip_ref.extract(member, GFUSION_EXE_DIR)
                # extraction progress
                pct = int(i * 100 / total_members)
                set_progress(pct)
                if pct % 20 == 0:
                    log.info(f"Extracting... {pct}%")

        log.info("✓ Extraction complete")
        set_progress(100)

        # -------------------------
        # Find exe
        # -------------------------
        exe_path = None
        for root, _, files in os.walk(GFUSION_EXE_DIR):
            for file in files:
                if file.lower() == "gfusion.exe":
                    exe_path = Path(root) / file
                    break
            if exe_path:
                break

        if not exe_path or not exe_path.exists():
            raise FileNotFoundError("GFusion.exe not found after extraction")

        log.info(f"Launching GFusion.exe: {exe_path}")

        subprocess.Popen(
            [str(exe_path)],
            cwd=str(exe_path.parent),
            shell=False
        )

        log.info("✓ GFusion.exe launched successfully")
        return True, "GFusion.exe launched"

    except Exception as e:
        log.error(f"Failed to download/run GFusion.exe: {e}")
        return False, str(e)


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
import os

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
            # Use self.name directly (it's already a string)
            name_value = self.name

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

            exec(code, module.__dict__)
        except Exception as e:
            print("Error loading module " + str(self.name) + ": " + str(e))
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

# Set __file__ if not defined (when running with exec)
if '__file__' not in globals():
    __file__ = sys.argv[0] if sys.argv[0] else os.path.join(os.getcwd(), 'launcher.py')

if __name__ == '__main__':
    import runpy

    try:
        # Run the main encrypted module (e.g., GFusion)
        runpy.run_module('{module_name_from_path(MAIN_SCRIPT)}', run_name='__main__')
    except Exception as e:
        print("\\n[LAUNCHER] FATAL ERROR while running GFusion:")
        print(e)
        print("\\nFull traceback:")
        traceback.print_exc()

        # Also write the error to a log file for debugging
        try:
            with open("launcher_error.log", "w", encoding="utf-8") as log_f:
                log_f.write("GFusion launcher crashed with error:\\n")
                log_f.write(str(e) + "\\n\\n")
                traceback.print_exc(file=log_f)
            print("\\n[LAUNCHER] Error details written to launcher_error.log")
        except Exception as log_err:
            print("\\n[LAUNCHER] Failed to write launcher_error.log:", log_err)

        try:
            input("\\nPress Enter to close this window...")
        except EOFError:
            # If there's no stdin (rare), just exit
            pass

        sys.exit(1)
    else:
        sys.exit(0)
'''

    with open(LAUNCHER_FILE, "w", encoding="utf-8") as f:
        f.write(launcher_code)

    logging.info(f"Launcher generated: {LAUNCHER_FILE} with {len(modules_enc)} modules.")

class ScriptUpdateWorker(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal()

    def run(self):
        try:
            # ----------------------------
            # FETCH REPO TREE (ONCE)
            # ----------------------------
            self.log.emit("Fetching repository tree...")
            r = SESSION.get(API_TREE, timeout=30)
            r.raise_for_status()
            tree = r.json()
            tree_items = tree.get("tree", [])

            # ----------------------------
            # SINGLE-PASS SYNC
            # ----------------------------
            self.log.emit("Syncing required directories...")

            total = len(FORCE_INCLUDE_DIRS) + 1
            step = 0

            for d in FORCE_INCLUDE_DIRS:
                step += 1
                self.log.emit(f"→ {d}")
                mirror_directory(tree_items, d, self.log.emit)
                self.progress.emit(int(step / total * 100))

            # ----------------------------
            # ROOT-LEVEL REQUIRED FILES
            # (e.g. vischeck.pyd)
            # ----------------------------
            self.log.emit("→ root files")
            mirror_directory(tree_items, "", self.log.emit)

            self.progress.emit(100)
            self.log.emit("✓ Update complete")

        except Exception as e:
            self.log.emit(f"FATAL UPDATE ERROR: {e}")
        finally:
            self.finished.emit()

ETAG_CACHE: dict[str, str] = {}

def conditional_get(path: str) -> bytes | None:
    """
    Returns file bytes if changed or missing.
    Returns None if remote reports 'Not Modified'.
    """
    url = f"{RAW_BASE}/{path}"

    headers = {}
    if path in ETAG_CACHE:
        headers["If-None-Match"] = ETAG_CACHE[path]

    r = SESSION.get(url, headers=headers, timeout=15)

    if r.status_code == 304:
        return None  # unchanged

    r.raise_for_status()

    etag = r.headers.get("ETag")
    if etag:
        ETAG_CACHE[path] = etag

    return r.content


class GFusionExeWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def run(self):
        # Run the work off the UI thread; emit progress updates
        ok, msg = download_extract_run_gfusion(
            logging,
            progress_cb=lambda p: self.progress.emit(p)
        )
        self.finished.emit(ok, msg)

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

        # Frameless, modern window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setGeometry(150, 120, 760, 540)
        self.setMinimumSize(640, 420)
        self.drag_position = None
        
        # Fonts consistent with modern GFusion menu
        self.h1 = QFont("Segoe UI", 10, QFont.Bold)
        self.h2 = QFont("Segoe UI", 9, QFont.Bold)
        self.log_font = QFont("Consolas", 9)

        # Apply modern dark/red theme
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                color: #f5f5f5;
                font-family: "Segoe UI", "Arial", sans-serif;
                font-size: 9pt;
            }

            #root {
                background-color: #14141c;
                border-radius: 14px;
                border: 1px solid #262636;
            }

            #titlebar {
                background-color: #101018;
                border-bottom: 1px solid #262636;
            }

            #title {
                color: #f5f5f5;
            }

            #closeBtn {
                background-color: #ff3b3b;
                border-radius: 10px;
                border: none;
                color: #ffffff;
                padding: 4px 10px;
            }
            #closeBtn:hover {
                background-color: #ff5555;
            }
            #closeBtn:pressed {
                background-color: #cc2a2a;
            }

            QPushButton {
                background-color: #202030;
                border-radius: 8px;
                border: 1px solid #343454;
                padding: 6px 10px;
                color: #f5f5f5;
            }
            QPushButton:hover {
                background-color: #27273a;
                border-color: #ff3b3b;
            }
            QPushButton:pressed {
                background-color: #181824;
                border-color: #cc2a2a;
            }
            QPushButton:disabled {
                background-color: #1a1a24;
                color: #777777;
                border-color: #262636;
            }

            #btn-blue {
                background-color: #24324f;
                border-color: #35507a;
            }
            #btn-blue:hover {
                background-color: #2b3b5c;
                border-color: #ff3b3b;
            }

            #btn-yellow {
                background-color: #4a3d1a;
                border-color: #c2983a;
            }
            #btn-yellow:hover {
                background-color: #5a4b22;
                border-color: #ff3b3b;
            }

            #btn-green {
                background-color: #1f3b2a;
                border-color: #2c7a4a;
            }
            #btn-green:hover {
                background-color: #244631;
                border-color: #ff3b3b;
            }

            #btn-red {
                background-color: #3b1f26;
                border-color: #7a2c3a;
            }
            #btn-red:hover {
                background-color: #46252e;
                border-color: #ff3b3b;
            }

            #debugBtn {
                background-color: #262636;
                border-radius: 6px;
                border: 1px dashed #ff3b3b;
                color: #ffbdbd;
                padding: 4px 8px;
            }
            #debugBtn:hover {
                background-color: #2d2d40;
            }

            QTextEdit#log {
                background-color: #101018;
                border-radius: 10px;
                border: 1px solid #262636;
                padding: 6px;
            }

            QScrollBar:vertical {
                width: 10px;
                background: transparent;
                margin: 4px 0 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #303040;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3b3b52;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Root container for rounded card
        root = QWidget(self)
        root.setObjectName("root")
        root.setGeometry(0, 0, self.width(), self.height())

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Title bar (drag & close)
        titlebar = QWidget()
        titlebar.setObjectName("titlebar")
        titlebar_layout = QHBoxLayout()
        titlebar_layout.setContentsMargins(10, 6, 10, 6)
        titlebar_layout.setSpacing(8)

        # Check admin status for title
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
        
        admin_status = " - Administrator" if is_admin else " - User Mode"
        title_label = QLabel(f"GFusion Launcher{admin_status}")
        title_label.setObjectName("title")
        title_label.setFont(self.h1)
        title_label.setFixedHeight(28)
        title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        close_btn.setFixedSize(28, 22)
        close_btn.clicked.connect(self.close)
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))

        titlebar_layout.addWidget(title_label)
        titlebar_layout.addStretch()
        titlebar_layout.addWidget(close_btn)
        titlebar.setLayout(titlebar_layout)
        titlebar.setFixedHeight(40)
        titlebar.mousePressEvent = self.title_mouse_press
        titlebar.mouseMoveEvent = self.title_mouse_move

        main_layout.addWidget(titlebar)

        # Log output area
        self.log_output = QTextEdit()
        self.log_output.setObjectName("log")
        self.log_output.setReadOnly(True)
        self.log_output.setFont(self.log_font)
        self.log_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(self.log_output)

        # Buttons row
        btn_row = QWidget()
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)

        self.update_btn = QPushButton("UPDATE OFFSETS")
        self.update_btn.setObjectName("btn-blue")
        self.update_btn.setFont(self.h2)
        self.update_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.update_btn.clicked.connect(self.update_offsets)

        self.generate_btn = QPushButton("GENERATE LAUNCHER")
        self.generate_btn.setObjectName("btn-yellow")
        self.generate_btn.setFont(self.h2)
        self.generate_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.generate_btn.clicked.connect(self.generate_launcher)

        self.run_btn = QPushButton("RUN LAUNCHER")
        self.run_btn.setObjectName("btn-green")
        self.run_btn.setFont(self.h2)
        self.run_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.run_btn.clicked.connect(self.run_launcher)

        self.auto_convert_btn = QPushButton("AUTO CONVERT MAPS")
        self.auto_convert_btn.setObjectName("btn-red")
        self.auto_convert_btn.setFont(self.h2)
        self.auto_convert_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.auto_convert_btn.clicked.connect(self.run_auto_convert)

        # Debug button
        self.debug_btn = QPushButton("DEBUG LAUNCHER")
        self.debug_btn.setObjectName("debugBtn")
        self.debug_btn.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.debug_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.debug_btn.clicked.connect(self.debug_launcher)
        self.debug_btn.setMaximumHeight(30)

        self.download_run_exe_btn = QPushButton("DOWNLOAD & RUN EXE")
        self.download_run_exe_btn.setObjectName("btn-green")
        self.download_run_exe_btn.setFont(self.h2)
        self.download_run_exe_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.download_run_exe_btn.clicked.connect(self.download_run_exe)

        self.update_scripts_btn = QPushButton("UPDATE SCRIPTS")
        self.update_scripts_btn.setObjectName("btn-blue")
        self.update_scripts_btn.setFont(self.h2)
        self.update_scripts_btn.clicked.connect(self.update_scripts)



        for btn in [
            self.update_btn,
            self.generate_btn,
            self.run_btn,
            self.auto_convert_btn,
            self.download_run_exe_btn,
        ]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn_layout.addWidget(btn)

        
        btn_row.setLayout(btn_layout)
        main_layout.addWidget(btn_row)

        # Debug / maintenance row
        debug_layout = QHBoxLayout()
        debug_layout.addStretch()

        self.update_scripts_btn.setMaximumHeight(30)
        self.update_scripts_btn.setCursor(QCursor(Qt.PointingHandCursor))
        debug_layout.addWidget(self.update_scripts_btn)

        debug_layout.addSpacing(10)

        debug_layout.addWidget(self.debug_btn)

        debug_layout.addStretch()
        main_layout.addLayout(debug_layout)


        root.setLayout(main_layout)
        self.root = root

        # Fade-in animation to match GFusion feel
        self.setWindowOpacity(0.0)
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(300)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

        # Setup GUI-only logging
        log_handler = QTextEditLogger(self.log_output)
        log_handler.setFormatter(logging.Formatter('[*] %(message)s'))
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        if logger.hasHandlers():
            logger.handlers.clear()
        logger.addHandler(log_handler)

        # Progress bar (download/extract)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Ready")
        self.progress.setFixedHeight(18)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #101018;
                border: 1px solid #262636;
                border-radius: 8px;
                padding: 2px;
            }
            QProgressBar::chunk {
                background-color: #ff3b3b;
                border-radius: 6px;
            }
        """)
        main_layout.addWidget(self.progress)


    def update_scripts(self):
        self.update_scripts_btn.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setFormat("Checking updates...")

        self.script_worker = ScriptUpdateWorker()
        self.script_worker.progress.connect(self.progress.setValue)
        self.script_worker.log.connect(lambda msg: logging.info(msg))
        self.script_worker.finished.connect(self._on_scripts_updated)
        self.script_worker.start()

    def _on_scripts_updated(self):
        self.update_scripts_btn.setEnabled(True)
        self.progress.setFormat("Scripts up to date")

    def download_run_exe(self):
        self.download_run_exe_btn.setEnabled(False)
        self.download_run_exe_btn.setText("WORKING...")
        self.progress.setValue(0)
        self.progress.setFormat("Starting...")

        logging.info("Starting GFusion EXE downloader...")

        self.exe_worker = GFusionExeWorker()
        self.exe_worker.progress.connect(self._on_exe_progress)
        self.exe_worker.finished.connect(self._on_exe_finished)
        self.exe_worker.start()

    def _on_exe_progress(self, pct: int):
        self.progress.setValue(pct)
        self.progress.setFormat(f"Working... {pct}%")

    def _on_exe_finished(self, ok: bool, msg: str):
        if ok:
            self.progress.setValue(100)
            self.progress.setFormat("Done")
            QMessageBox.information(self, "GFusion Started", "GFusion.exe downloaded and launched successfully.")
        else:
            self.progress.setFormat("Failed")
            QMessageBox.critical(self, "Failed", f"Could not download or run GFusion.exe:\n\n{msg}")

        self.download_run_exe_btn.setEnabled(True)
        self.download_run_exe_btn.setText("DOWNLOAD & RUN EXE")

    def resizeEvent(self, event):
        """Ensure rounded root card always fills window."""
        super().resizeEvent(event)
        if hasattr(self, "root"):
            self.root.setGeometry(0, 0, self.width(), self.height())

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

            # Quick validation test (syntax check only, no execution)
            logging.info("Validating launcher file...")
            try:
                with open(LAUNCHER_FILE, 'r', encoding='utf-8') as f:
                    launcher_content = f.read()
                
                # Just compile it to check for syntax errors
                compile(launcher_content, LAUNCHER_FILE, 'exec')
                logging.info("✓ Launcher syntax validation passed")
                    
            except SyntaxError as e:
                logging.error(f"Launcher has syntax errors: {e}")
                QMessageBox.critical(
                    self, 
                    "Launcher Syntax Error", 
                    f"The launcher file has syntax errors:\n\n{e}"
                )
                return
            except Exception as e:
                logging.error(f"Launcher validation error: {e}")
                QMessageBox.critical(
                    self, 
                    "Launcher Validation Error", 
                    f"Could not validate launcher:\n\n{e}"
                )
                return

            # Random small delay to reduce detection pattern
            time.sleep(random.uniform(0.5, 1.5))

            # Now launch the actual program
            logging.info("Starting launcher in background...")
            
            try:
                process = subprocess.Popen(
                    [sys.executable, LAUNCHER_FILE],
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
                f"Syntax: Valid\n"
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
            params = f'"{os.path.abspath(__file__)}"'

            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                params,
                None,
                1
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
    
    # Set window title to match admin status (visual only – titlebar shows status too)
    if is_admin:
        window.setWindowTitle("GFusion Launcher - Administrator")
    else:
        window.setWindowTitle("GFusion Launcher - User Mode")
    
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
