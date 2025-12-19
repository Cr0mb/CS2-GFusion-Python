import ctypes
import time
from ctypes import wintypes

from Process.config import Config

# ============================================================
# WinAPI setup
# ============================================================

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SendInput = user32.SendInput

# Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001

VK_W = 0x57  # 'W'

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# ============================================================
# Structures
# ============================================================

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("mi", MOUSEINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]


# ============================================================
# Input helpers
# ============================================================

def press_key(vk: int, down: bool = True):
    flags = 0 if down else KEYEVENTF_KEYUP
    ki = KEYBDINPUT(
        wVk=vk,
        wScan=0,
        dwFlags=flags,
        time=0,
        dwExtraInfo=None,
    )
    inp = INPUT(type=INPUT_KEYBOARD, u=INPUT_UNION(ki=ki))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def move_mouse(dx: int, dy: int):
    mi = MOUSEINPUT(
        dx=dx,
        dy=dy,
        mouseData=0,
        dwFlags=MOUSEEVENTF_MOVE,
        time=0,
        dwExtraInfo=None,
    )
    inp = INPUT(type=INPUT_MOUSE, u=INPUT_UNION(mi=mi))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


# ============================================================
# Foreground process name (NO psutil)
# ============================================================

kernel32.OpenProcess.argtypes = [
    wintypes.DWORD,
    wintypes.BOOL,
    wintypes.DWORD,
]
kernel32.OpenProcess.restype = wintypes.HANDLE

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


def get_foreground_window_process_name() -> str | None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None

    hproc = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid.value,
    )
    if not hproc:
        return None

    try:
        buf_len = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(buf_len.value)

        if not kernel32.QueryFullProcessImageNameW(
            hproc, 0, buf, ctypes.byref(buf_len)
        ):
            return None

        # Extract exe name only
        path = buf.value
        exe = path.rsplit("\\", 1)[-1].lower()
        return exe
    finally:
        kernel32.CloseHandle(hproc)


# ============================================================
# Walkbot logic
# ============================================================

MOUSE_SPEED = 16
SLEEP_INTERVAL = 0.005


def walk_in_circle():
    key_pressed = False
    print("[+] WalkBot: Running circle loop...")

    try:
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

    finally:
        if key_pressed:
            press_key(VK_W, False)

        Config.walkbot_enabled = False
        print("[+] WalkBot: Circle loop stopped.")
