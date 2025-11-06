import time
import ctypes
import keyboard
import winsound
from ctypes import *
from ctypes.wintypes import *
from win32gui import GetWindowText, GetForegroundWindow

from Process.offsets import Offsets
from Process.config import Config

# Windows constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
MAX_PATH = 260
ULONG_PTR = c_ulonglong if sizeof(c_void_p) == 8 else c_ulong

# Mouse input constants
INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# Struct definitions for process/module snapshots
class PROCESSENTRY32(Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("cntUsage", DWORD),
        ("th32ProcessID", DWORD),
        ("th32DefaultHeapID", ULONG_PTR),
        ("th32ModuleID", DWORD),
        ("cntThreads", DWORD),
        ("th32ParentProcessID", DWORD),
        ("pcPriClassBase", LONG),
        ("dwFlags", DWORD),
        ("szExeFile", c_char * MAX_PATH)
    ]

class MODULEENTRY32(Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("th32ModuleID", DWORD),
        ("th32ProcessID", DWORD),
        ("GlblcntUsage", DWORD),
        ("ProccntUsage", DWORD),
        ("modBaseAddr", LPBYTE),
        ("modBaseSize", DWORD),
        ("hModule", HMODULE),
        ("szModule", c_char * 256),
        ("szExePath", c_char * 260)
    ]

# Mouse input structures for SendInput
class MOUSEINPUT(Structure):
    _fields_ = [
        ("dx", LONG),
        ("dy", LONG),
        ("mouseData", DWORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR)
    ]

class INPUT_union(Union):
    _fields_ = [("mi", MOUSEINPUT)]

class INPUT(Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", DWORD),
        ("u", INPUT_union)
    ]

# Get function pointer for SendInput
SendInput = ctypes.windll.user32.SendInput

def send_mouse_event(flags):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi = MOUSEINPUT(0, 0, 0, flags, 0, 0)
    SendInput(1, byref(inp), sizeof(inp))


class Memory:
    def __init__(self, process_name):
        self.kernel32 = windll.kernel32
        self.process_name = process_name.encode()
        self.pid = self.get_pid_by_name()
        self.handle = self.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, self.pid)
        self.client_base = self.get_module_base(b"client.dll")

    def get_pid_by_name(self):
        hSnapshot = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        entry = PROCESSENTRY32()
        entry.dwSize = sizeof(PROCESSENTRY32)

        if not self.kernel32.Process32First(hSnapshot, byref(entry)):
            self.kernel32.CloseHandle(hSnapshot)
            raise Exception("Process32First failed")

        while True:
            if entry.szExeFile == self.process_name:
                pid = entry.th32ProcessID
                self.kernel32.CloseHandle(hSnapshot)
                return pid
            if not self.kernel32.Process32Next(hSnapshot, byref(entry)):
                break

        self.kernel32.CloseHandle(hSnapshot)
        raise Exception(f"Process '{self.process_name.decode()}' not found")

    def get_module_base(self, module_name):
        hSnapshot = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, self.pid)
        modEntry = MODULEENTRY32()
        modEntry.dwSize = sizeof(MODULEENTRY32)

        if not self.kernel32.Module32First(hSnapshot, byref(modEntry)):
            self.kernel32.CloseHandle(hSnapshot)
            raise Exception("Module32First failed")

        while True:
            if modEntry.szModule == module_name:
                base_addr = cast(modEntry.modBaseAddr, c_void_p).value
                self.kernel32.CloseHandle(hSnapshot)
                return base_addr
            if not self.kernel32.Module32Next(hSnapshot, byref(modEntry)):
                break

        self.kernel32.CloseHandle(hSnapshot)
        raise Exception(f"Module '{module_name.decode()}' not found")

    def read_bytes(self, address, size):
        buffer = create_string_buffer(size)
        bytes_read = c_size_t()
        success = self.kernel32.ReadProcessMemory(self.handle, c_void_p(address), buffer, size, byref(bytes_read))
        if not success or bytes_read.value != size:
            return None
        return buffer.raw

    def read_int(self, address):
        data = self.read_bytes(address, 4)
        if data is None:
            return 0
        return int.from_bytes(data, 'little')

    def read_longlong(self, address):
        data = self.read_bytes(address, 8)
        if data is None:
            return 0
        return int.from_bytes(data, 'little')


class TriggerBot:
    def __init__(self, shared_config=None):
        self.shared_config = shared_config if shared_config else Config()
        self.shootTeammates = getattr(self.shared_config, "shoot_teammates", False)

        self.memory = Memory("cs2.exe")
        self.client = self.memory.client_base
        self.offsets_manager = Offsets()
        self.last_shot_time = 0

    def shoot(self):
        send_mouse_event(MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.005)
        send_mouse_event(MOUSEEVENTF_LEFTUP)

    def enable(self):
        try:
            if GetWindowText(GetForegroundWindow()) != "Counter-Strike 2":
                return

            if not getattr(self.shared_config, "triggerbot_always_on", False):
                if not keyboard.is_pressed(getattr(self.shared_config, "trigger_key", "shift")):
                    return

            player = self.memory.read_longlong(self.client + self.offsets_manager.dwLocalPlayerPawn)
            if not player:
                return

            entityId = self.memory.read_int(player + self.offsets_manager.m_iIDEntIndex)
            if entityId <= 0:
                return

            entList = self.memory.read_longlong(self.client + self.offsets_manager.dwEntityList)
            if not entList:
                return

            entEntry = self.memory.read_longlong(entList + 0x8 * (entityId >> 9) + 0x10)
            entity = self.memory.read_longlong(entEntry + 112 * (entityId & 0x1FF))  # CS2 update: stride 120->112
            if not entity:
                return

            entityTeam = self.memory.read_int(entity + self.offsets_manager.m_iTeamNum)
            entityHp = self.memory.read_int(entity + self.offsets_manager.m_iHealth)
            playerTeam = self.memory.read_int(player + self.offsets_manager.m_iTeamNum)

            cooldown = getattr(self.shared_config, "triggerbot_cooldown", 0.8)
            allow_team = getattr(self.shared_config, "shoot_teammates", False)

            if entityTeam != 0 and entityHp > 0:
                if allow_team or (entityTeam != playerTeam):
                    current_time = time.time()
                    if current_time - self.last_shot_time >= cooldown:
                        self.shoot()
                        self.last_shot_time = current_time

        except Exception as e:
            print(f"[TriggerBot] Exception: {e}")

    def run(self):
        try:
            while not getattr(self.shared_config, "triggerbot_stop", False):
                if getattr(self.shared_config, "triggerbot_enabled", False):
                    self.enable()
                else:
                    print("[TriggerBot] Not enabled yet")
                time.sleep(0.005)
        except KeyboardInterrupt:
            print("[*] TriggerBot interrupted by user.")
        finally:
            print(" ")


if __name__ == "__main__":
    config = Config()
    bot = TriggerBot(shared_config=config)
    bot.run()
