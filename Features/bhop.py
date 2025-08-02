import time
import ctypes
import ctypes.wintypes as wintypes
import win32gui
import win32process
import keyboard

from Process.offsets import Offsets
from Process.config import Config


# Constants
PROCESS_ALL_ACCESS = 0x1F0FFF
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# Windows API functions
CreateToolhelp32Snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot
Process32First = ctypes.windll.kernel32.Process32First
Process32Next = ctypes.windll.kernel32.Process32Next
Module32First = ctypes.windll.kernel32.Module32First
Module32Next = ctypes.windll.kernel32.Module32Next
OpenProcess = ctypes.windll.kernel32.OpenProcess
CloseHandle = ctypes.windll.kernel32.CloseHandle
ReadProcessMemory = ctypes.windll.kernel32.ReadProcessMemory
GetLastError = ctypes.windll.kernel32.GetLastError
QueryFullProcessImageName = ctypes.windll.kernel32.QueryFullProcessImageNameW

# Structures
class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
        ('th32ModuleID', wintypes.DWORD),
        ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD),
        ('pcPriClassBase', ctypes.c_long),
        ('dwFlags', wintypes.DWORD),
        ('szExeFile', ctypes.c_char * 260),
    ]

class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]

def get_pid_by_name(process_name):
    """Get PID of the process matching process_name (case-insensitive)."""
    process_name = process_name.lower().encode('utf-8')
    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return None

    pe32 = PROCESSENTRY32()
    pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)

    if not Process32First(snapshot, ctypes.byref(pe32)):
        CloseHandle(snapshot)
        return None

    pid = None
    while True:
        if pe32.szExeFile.lower() == process_name:
            pid = pe32.th32ProcessID
            break
        if not Process32Next(snapshot, ctypes.byref(pe32)):
            break

    CloseHandle(snapshot)
    return pid

class CS2Process:
    def __init__(self, process_name="cs2.exe", module_name="client.dll", wait_timeout=30):
        self.process_name = process_name.lower()
        self.module_name = module_name.lower()
        self.wait_timeout = wait_timeout

        self.pid = None
        self.handle = None
        self.module_base = None

    def _wait_for_process(self):
        start_time = time.time()
        while True:
            self.pid = get_pid_by_name(self.process_name)
            if self.pid:
                return True
            if time.time() - start_time > self.wait_timeout:
                return False
            time.sleep(1)

    def wait_for_process(self):
        if not self._wait_for_process():
            raise RuntimeError(f"{self.process_name} not running after {self.wait_timeout} seconds")
        self.handle = OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        if not self.handle:
            raise RuntimeError(f"Failed to open process {self.process_name} (PID: {self.pid})")

    def get_module_base(self):
        if not self.pid or not self.handle:
            raise RuntimeError("Process not attached")

        snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, self.pid)
        if snapshot == INVALID_HANDLE_VALUE:
            raise RuntimeError("Failed to create module snapshot")

        me32 = MODULEENTRY32()
        me32.dwSize = ctypes.sizeof(MODULEENTRY32)

        found = False
        if Module32First(snapshot, ctypes.byref(me32)):
            while True:
                if me32.szModule.lower() == self.module_name.encode():
                    self.module_base = ctypes.addressof(me32.modBaseAddr.contents)
                    found = True
                    break
                if not Module32Next(snapshot, ctypes.byref(me32)):
                    break

        CloseHandle(snapshot)

        if not found:
            raise RuntimeError(f"Module {self.module_name} not found in process {self.process_name}")

    def initialize(self):
        self.wait_for_process()
        self.get_module_base()

    def __repr__(self):
        if self.module_base:
            return f"<CS2Process pid={self.pid} handle={self.handle} module_base=0x{self.module_base:x}>"
        return "<CS2Process uninitialized>"

def get_process_name(pid):
    """Get process executable name for given pid."""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    buffer_len = wintypes.DWORD(260)
    exe_name_buffer = ctypes.create_unicode_buffer(260)
    if QueryFullProcessImageName(handle, 0, exe_name_buffer, ctypes.byref(buffer_len)):
        full_path = exe_name_buffer.value
        exe_name = full_path.split('\\')[-1].lower()
        CloseHandle(handle)
        return exe_name
    CloseHandle(handle)
    return None

class BHopProcess:
    KEYEVENTF_KEYDOWN = 0x0000
    KEYEVENTF_KEYUP = 0x0002
    VK_SPACE = 0x20

    def __init__(self, process_name="cs2.exe", module_name="client.dll", jump_cooldown=0.1, foreground_check_interval=10):
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.process_name = process_name.lower()
        self.module_name = module_name
        self.jump_cooldown = jump_cooldown
        self.foreground_check_interval = foreground_check_interval

        self.cs2 = CS2Process(process_name=self.process_name, module_name=self.module_name)
        self.cs2.initialize()

        self.handle = self.cs2.handle
        self.base_addr = self.cs2.module_base

        self.cached_exe = None
        self.last_jump_time = 0
        self.iteration = 0

    def press_spacebar(self):
        self.user32.keybd_event(self.VK_SPACE, 0, self.KEYEVENTF_KEYDOWN, 0)
        time.sleep(0.001)
        self.user32.keybd_event(self.VK_SPACE, 0, self.KEYEVENTF_KEYUP, 0)

    def get_foreground_exe(self):
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid == 0:
            return None
        return get_process_name(pid)

    def read_memory(self, address, size):
        buffer = (ctypes.c_byte * size)()
        bytesRead = ctypes.c_size_t()
        if not ReadProcessMemory(self.handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytesRead)):
            raise ctypes.WinError()
        return bytes(buffer)

    def read_int(self, address):
        data = self.read_memory(address, 4)
        return int.from_bytes(data, byteorder='little')

    def read_longlong(self, address):
        data = self.read_memory(address, 8)
        return int.from_bytes(data, byteorder='little')

    def run(self):

        while True:
            try:
                if Config.bhop_stop:
                    break

                if self.iteration % self.foreground_check_interval == 0:
                    self.cached_exe = self.get_foreground_exe()
                self.iteration += 1

                if not Config.bhop_enabled:
                    time.sleep(0.01)
                    continue

                if self.cached_exe != self.process_name:
                    time.sleep(0.01)
                    continue

                if keyboard.is_pressed('space'):
                    pawn_ptr = self.read_longlong(self.base_addr + Offsets.dwLocalPlayerPawn)
                    if pawn_ptr == 0:
                        time.sleep(0.01)
                        continue

                    flags = self.read_int(pawn_ptr + Offsets.m_fFlags)
                    on_ground = (flags & 1) == 1

                    now = time.time()
                    if on_ground and now - self.last_jump_time > self.jump_cooldown:
                        self.press_spacebar()
                        self.last_jump_time = now

                time.sleep(0.0015)

            except KeyboardInterrupt:
                print("\n[BHop] Interrupted by user, stopping...")
                break
            except Exception as e:
                print(f"[BHop ERROR] Exception in main loop: {e}")
                time.sleep(0.01)

        print("[BHop] Stopped.")

def main():
    Config.bhop_enabled = True
    bhop = BHopProcess()
    bhop.run()

if __name__ == "__main__":
    main()
