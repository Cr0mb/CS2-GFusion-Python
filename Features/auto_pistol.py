import ctypes
import time
import threading
from ctypes import wintypes

from Process.config import Config

# --- Key mapping (human-readable to virtual key codes) ---
KEY_MAP = {
    "MOUSE2": 0x02,
    "MOUSE3": 0x04,
    "MOUSE4": 0x05,
    "MOUSE5": 0x06,
    "ALT": 0x12,
    "SHIFT": 0x10,
    "CTRL": 0x11,
    "SPACE": 0x20
}

cfg = Config()

# --- WinAPI Constants ---
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
INPUT_MOUSE = 0

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("ii",)
    _fields_ = [("type", ctypes.c_ulong), ("ii", _INPUT)]

SendInput = ctypes.windll.user32.SendInput
GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

def click_mouse1():
    inp_down = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, None))
    inp_up = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, None))
    SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(inp_down))
    SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(inp_up))

def is_cs2_focused():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return False

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    hProcess = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not hProcess:
        return False

    exe_path_buffer = ctypes.create_unicode_buffer(260)
    size = wintypes.DWORD(len(exe_path_buffer))

    if not kernel32.QueryFullProcessImageNameW(hProcess, 0, exe_path_buffer, ctypes.byref(size)):
        kernel32.CloseHandle(hProcess)
        return False

    kernel32.CloseHandle(hProcess)

    exe_name = exe_path_buffer.value.split("\\")[-1].lower()
    return exe_name == "cs2.exe"

def auto_pistol_loop():
    vk = KEY_MAP.get(cfg.activation_key.upper())
    if vk is None:
        print(f"[!] Invalid activation key: {cfg.activation_key}")
        return

    print(f"[+] Auto pistol active — hold {cfg.activation_key} to fire")

    try:
        while True:
            if GetAsyncKeyState(vk) & 0x8000:
                if is_cs2_focused():
                    click_mouse1()
                    time.sleep(cfg.fire_rate)
                else:
                    time.sleep(0.1)
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("[*] Auto pistol stopped.")

def run_auto_pistol(cfg):
    def auto_pistol_loop():
        print(f"[+] Auto pistol thread started")

        last_key = None
        vk = None

        try:
            while True:
                if not cfg.auto_pistol_enabled:
                    time.sleep(0.1)
                    continue

                # Update activation key if changed
                if cfg.activation_key != last_key:
                    last_key = cfg.activation_key
                    vk = KEY_MAP.get(last_key.upper())
                    if vk is None:
                        print(f"[AutoPistol] Invalid key: {last_key}")
                        time.sleep(0.2)
                        continue
                    else:
                        print(f"[AutoPistol] Key set to: {last_key.upper()}")

                if GetAsyncKeyState(vk) & 0x8000:
                    if is_cs2_focused():
                        click_mouse1()
                        time.sleep(cfg.fire_rate)
                    else:
                        time.sleep(0.1)
                else:
                    time.sleep(0.01)

        except KeyboardInterrupt:
            print("[*] Auto pistol stopped.")

    thread = threading.Thread(target=auto_pistol_loop, daemon=True)
    thread.start()

if __name__ == "__main__":
    t = threading.Thread(target=auto_pistol_loop, daemon=True)
    t.start()

    print("[*] Press CTRL+C to quit.")
    while t.is_alive():
        time.sleep(1)