import ctypes
import time
import psutil

from Process.config import Config

SendInput = ctypes.windll.user32.SendInput
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants
INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001
VK_W = 0x57  # 'W' key

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT),
                ("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("u", INPUT_UNION)]

def press_key(vk, down=True):
    flags = 0 if down else KEYEVENTF_KEYUP
    ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None)
    inp = INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(ki=ki))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def move_mouse(dx, dy):
    mi = MOUSEINPUT(dx=dx, dy=dy, mouseData=0, dwFlags=MOUSEEVENTF_MOVE, time=0, dwExtraInfo=None)
    inp = INPUT(type=INPUT_MOUSE, u=INPUT_UNION(mi=mi))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def get_foreground_window_process_name():
    hwnd = user32.GetForegroundWindow()
    if hwnd == 0:
        return None
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == 0:
        return None
    try:
        proc = psutil.Process(pid.value)
        return proc.name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

# Configurable
MOUSE_SPEED = 16
SLEEP_INTERVAL = 0.005

def walk_in_circle():
    key_pressed = False
    print("[+] WalkBot: Running circle loop...")

    while Config.walkbot_enabled and not Config.walkbot_stop:
        proc_name = get_foreground_window_process_name()
        focused = (proc_name == "cs2.exe")

        if focused:
            if not key_pressed:
                press_key(VK_W, True)
                key_pressed = True
            move_mouse(MOUSE_SPEED, 0)
        else:
            if key_pressed:
                press_key(VK_W, False)
                key_pressed = False

        time.sleep(SLEEP_INTERVAL)

    if key_pressed:
        press_key(VK_W, False)
    print("[+] WalkBot: Circle loop stopped.")
    Config.walkbot_enabled = False
