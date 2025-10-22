import time
import ctypes
from ctypes import *
from ctypes.wintypes import *

from Process.offsets import Offsets
from Process.config import Config
from Process.memory_interface import MemoryInterface

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
MAX_PATH = 260
ULONG_PTR = c_ulonglong if sizeof(c_void_p) == 8 else c_ulong

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

class Memory:
    def __init__(self, process_name, shared_config=None):
        self.kernel32 = windll.kernel32
        self.process_name = process_name.encode()
        self.pid = self.get_pid_by_name()
        self.handle = self.kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION,
            False, self.pid)
        
        # Initialize unified memory interface
        try:
            self.memory_interface = MemoryInterface(self.pid, self.handle, shared_config)
            if self.memory_interface.is_kernel_mode_active():
                print("[FOV] Using kernel mode memory access")
            else:
                print("[FOV] Using usermode memory access")
        except Exception as e:
            print(f"[FOV] Failed to initialize memory interface: {e}")
            # Fallback to usermode-only
            self.memory_interface = None
        
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

    def read_longlong(self, address):
        if self.memory_interface:
            return self.memory_interface.read_uint64(address)
        
        # Fallback
        buffer = c_longlong()
        bytesRead = c_size_t()
        if self.kernel32.ReadProcessMemory(self.handle, c_void_p(address), byref(buffer), sizeof(buffer), byref(bytesRead)):
            return buffer.value
        return 0

    def read_int(self, address):
        if self.memory_interface:
            return self.memory_interface.read_int(address)
        
        # Fallback
        buffer = c_int()
        bytesRead = c_size_t()
        if self.kernel32.ReadProcessMemory(self.handle, c_void_p(address), byref(buffer), sizeof(buffer), byref(bytesRead)):
            return buffer.value
        return 0

    def write_int(self, address, value):
        if self.memory_interface:
            return self.memory_interface.write_int(address, value)
        
        # Fallback
        buffer = c_int(value)
        bytesWritten = c_size_t()
        return self.kernel32.WriteProcessMemory(self.handle, c_void_p(address), byref(buffer), sizeof(buffer), byref(bytesWritten))


class FOVChanger:
    def __init__(self, shared_config):
        self.shared_config = shared_config
        self.memory = Memory("cs2.exe", shared_config)  # Pass config for kernel mode
        self.client = self.memory.client_base
        self.controller = None
        self.last_applied_fov = None
        self.offsets = Offsets()
        self.resolve_controller()

    def resolve_controller(self):
        self.controller = self.memory.read_longlong(self.client + self.offsets.dwLocalPlayerController)
        if not self.controller:
            print("[FOVChanger] Controller not found.")

    def set_fov(self, value):
        if not self.controller:
            self.resolve_controller()
            if not self.controller:
                return

        current_fov = self.memory.read_int(self.controller + self.offsets.m_iDesiredFOV)
        if current_fov != value:
            if self.memory.write_int(self.controller + self.offsets.m_iDesiredFOV, value):
                self.last_applied_fov = value
            else:
                print("[FOVChanger] Failed to write FOV.")

    def run(self):
        while self.shared_config.fov_changer_enabled:
            try:
                # Re-resolve controller if lost
                if not self.controller:
                    self.resolve_controller()

                if not self.controller:
                    time.sleep(0.5)
                    continue

                desired_fov = getattr(self.shared_config, "game_fov", None)

                if desired_fov is not None and desired_fov != self.last_applied_fov:
                    self.set_fov(desired_fov)

            except Exception as e:
                print(f"[FOVChanger] Runtime error: {e}")

            time.sleep(0.1)  # fast enough to feel real-time but not CPU heavy

        print("[*] FOVChanger stopped.")



if __name__ == "__main__":
    cfg = Config()
    cfg.fov_changer_enabled = True
    cfg.game_fov = 90

    changer = FOVChanger(cfg)
    changer.run()
