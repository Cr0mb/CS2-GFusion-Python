"""
Unified Memory Interface for CS2 Cheat System.

Supports two memory-access modes:
  * Usermode  - standard ReadProcessMemory / WriteProcessMemory
  * Kernel    - via a pluggable IKernelDriver backend (Process.drivers).

The default kernel backend is Binalyze IREC (KDU provider #41) which is
non-blacklisted by Microsoft.

Backend selection is driven by ``Config.kernel_driver`` (string).
"""

import ctypes
import struct
import time
import threading
from ctypes import wintypes
from abc import ABC, abstractmethod

# Import Config for tracking kernel instances
try:
    from .config import Config
except ImportError:
    from Process.config import Config

# Pluggable kernel-driver backends
try:
    from .drivers import load_driver as _load_kernel_driver
except Exception:
    try:
        from Process.drivers import load_driver as _load_kernel_driver  # type: ignore
    except Exception:
        _load_kernel_driver = None  # type: ignore

# Global variables
_kernel_driver = None  # IKernelDriver instance (process-wide singleton)
_kernel_driver_lock = threading.Lock()
_driver_initialization_attempted = False

class IMemoryReader(ABC):
    """Abstract base class for memory readers"""
    
    @abstractmethod
    def read_bytes(self, address: int, size: int) -> bytes:
        """Read raw bytes from memory"""
        pass
    
    @abstractmethod
    def write_bytes(self, address: int, data: bytes) -> bool:
        """Write raw bytes to memory"""
        pass
    
    @abstractmethod
    def read_int(self, address: int) -> int:
        """Read 32-bit signed integer"""
        pass
    
    @abstractmethod
    def read_uint32(self, address: int) -> int:
        """Read 32-bit unsigned integer"""
        pass
    
    @abstractmethod
    def read_uint64(self, address: int) -> int:
        """Read 64-bit unsigned integer"""
        pass
    
    @abstractmethod
    def read_float(self, address: int) -> float:
        """Read 32-bit float"""
        pass
    
    @abstractmethod
    def write_int(self, address: int, value: int) -> bool:
        """Write 32-bit signed integer"""
        pass
    
    @abstractmethod
    def write_uint32(self, address: int, value: int) -> bool:
        """Write 32-bit unsigned integer"""
        pass
    
    @abstractmethod
    def write_float(self, address: int, value: float) -> bool:
        """Write 32-bit float"""
        pass
    
    def read_vec3(self, address: int) -> list:
        """Read 3D vector (3 floats)"""
        data = self.read_bytes(address, 12)
        if data and len(data) == 12:
            return list(struct.unpack("fff", data))
        return [0.0, 0.0, 0.0]
    
    def read_string(self, address: int, max_length: int = 256) -> str:
        """Read null-terminated string"""
        data = self.read_bytes(address, max_length)
        if data:
            null_pos = data.find(b'\x00')
            if null_pos != -1:
                data = data[:null_pos]
            return data.decode('utf-8', errors='ignore')
        return ""

class UsermodeMemoryReader(IMemoryReader):
    """Standard usermode memory reader using ReadProcessMemory/WriteProcessMemory"""
    
    def __init__(self, process_handle: int):
        self.process_handle = process_handle
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    
    def read_bytes(self, address: int, size: int) -> bytes:
        if not address or address > 0x7FFFFFFFFFFF or size <= 0:
            return b"\x00" * size
        
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        
        success = self.kernel32.ReadProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read)
        )
        
        if not success or bytes_read.value != size:
            return b"\x00" * size
        
        return buffer.raw
    
    def write_bytes(self, address: int, data: bytes) -> bool:
        if not address or address > 0x7FFFFFFFFFFF:
            return False
        
        buffer = ctypes.create_string_buffer(data)
        bytes_written = ctypes.c_size_t(0)
        
        success = self.kernel32.WriteProcessMemory(
            self.process_handle,
            ctypes.c_void_p(address),
            buffer,
            len(data),
            ctypes.byref(bytes_written)
        )
        
        return success and bytes_written.value == len(data)
    
    def read_int(self, address: int) -> int:
        data = self.read_bytes(address, 4)
        return struct.unpack("i", data)[0] if data else 0
    
    def read_uint32(self, address: int) -> int:
        data = self.read_bytes(address, 4)
        return struct.unpack("I", data)[0] if data else 0
    
    def read_uint64(self, address: int) -> int:
        data = self.read_bytes(address, 8)
        return struct.unpack("Q", data)[0] if data else 0
    
    def read_float(self, address: int) -> float:
        data = self.read_bytes(address, 4)
        return struct.unpack("f", data)[0] if data else 0.0
    
    def write_int(self, address: int, value: int) -> bool:
        data = struct.pack("i", value)
        return self.write_bytes(address, data)
    
    def write_uint32(self, address: int, value: int) -> bool:
        data = struct.pack("I", value)
        return self.write_bytes(address, data)
    
    def write_float(self, address: int, value: float) -> bool:
        data = struct.pack("f", value)
        return self.write_bytes(address, data)

class KernelMemoryReader(IMemoryReader):
    """Kernel mode reader driven by a pluggable IKernelDriver backend.

    Two modes:
      1. Handle-based backends (e.g. Binalyze IREC) provide an elevated
         process HANDLE; we then use ReadProcessMemory on it. This is the
         preferred path because it keeps the hot R/W loop in usermode.
      2. R/W-providing backends supply ``read_bytes`` / ``write_bytes`` 
         directly; we forward to them.
    """

    def __init__(self, process_id: int):
        self.process_id = process_id
        self.driver = None
        self._elevated_handle: int = 0
        self._k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._initialize_driver()

    def _initialize_driver(self):
        global _kernel_driver, _kernel_driver_lock, _driver_initialization_attempted

        with _kernel_driver_lock:
            if _kernel_driver is not None:
                self.driver = _kernel_driver
            elif not _driver_initialization_attempted:
                _driver_initialization_attempted = True
                self.driver = self._load_backend()
                _kernel_driver = self.driver

        if not self.driver:
            return

        # Prefer an elevated handle if the backend supports it.
        try:
            self._elevated_handle = int(self.driver.open_process(self.process_id) or 0)
        except Exception as e:
            print(f"[Kernel] open_process failed: {e}")
            self._elevated_handle = 0

    @staticmethod
    def _load_backend():
        """Load the configured kernel backend, falling back through known names."""
        if _load_kernel_driver is None:
            print("[Kernel] drivers package unavailable")
            return None

        name = (getattr(Config, "kernel_driver", "binalyze_irec") or "").strip().lower()
        tried = []
        for candidate in [name, "binalyze_irec"]:
            if candidate in tried or not candidate:
                continue
            tried.append(candidate)
            drv = _load_kernel_driver(candidate)
            if drv is None:
                continue
            try:
                if drv.start():
                    print(f"[Kernel] Backend '{candidate}' started: {drv.status()}")
                    return drv
                print(f"[Kernel] Backend '{candidate}' refused to start: {drv.status()}")
            except Exception as e:
                print(f"[Kernel] Backend '{candidate}' raised: {e}")
        return None

    def _ensure_driver(self) -> bool:
        return self.driver is not None and (
            self._elevated_handle != 0 or hasattr(self.driver, "read_bytes")
        )

    # -------- handle-based primitives (preferred path) --------------------
    def _rpm(self, address: int, size: int) -> bytes:
        buf = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t(0)
        ok = self._k32.ReadProcessMemory(
            wintypes.HANDLE(self._elevated_handle),
            ctypes.c_void_p(address), buf, size, ctypes.byref(read),
        )
        return buf.raw if ok and read.value == size else b"\x00" * size

    def _wpm(self, address: int, data: bytes) -> bool:
        buf = ctypes.create_string_buffer(data)
        written = ctypes.c_size_t(0)
        ok = self._k32.WriteProcessMemory(
            wintypes.HANDLE(self._elevated_handle),
            ctypes.c_void_p(address), buf, len(data), ctypes.byref(written),
        )
        return bool(ok) and written.value == len(data)

    # -------- IMemoryReader API -------------------------------------------
    def read_bytes(self, address: int, size: int) -> bytes:
        if not self._ensure_driver():
            return b"\x00" * size
        if self._elevated_handle:
            return self._rpm(address, size)
        try:
            data = self.driver.read_bytes(self.process_id, address, size)
            return data if data else b"\x00" * size
        except Exception:
            return b"\x00" * size

    def write_bytes(self, address: int, data: bytes) -> bool:
        if not self._ensure_driver():
            return False
        if self._elevated_handle:
            return self._wpm(address, data)
        try:
            return bool(self.driver.write_bytes(self.process_id, address, data))
        except Exception:
            return False

    def read_int(self, address: int) -> int:
        d = self.read_bytes(address, 4)
        return struct.unpack("i", d)[0] if d else 0

    def read_uint32(self, address: int) -> int:
        d = self.read_bytes(address, 4)
        return struct.unpack("I", d)[0] if d else 0

    def read_uint64(self, address: int) -> int:
        d = self.read_bytes(address, 8)
        return struct.unpack("Q", d)[0] if d else 0

    def read_float(self, address: int) -> float:
        d = self.read_bytes(address, 4)
        return struct.unpack("f", d)[0] if d else 0.0

    def write_int(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("i", value))

    def write_uint32(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("I", value))

    def write_float(self, address: int, value: float) -> bool:
        return self.write_bytes(address, struct.pack("f", value))

class MemoryInterface:
    """Main memory interface that automatically chooses between kernel and usermode"""
    
    def __init__(self, process_id: int, process_handle: int, config=None):
        self.process_id = process_id
        self.process_handle = process_handle
        self.config = config
        self.kernel_reader = None
        self.usermode_reader = None
        self._current_reader = None
        self._kernel_mode_active = False
        
        # Initialize readers
        self._initialize_readers()
    
    def _initialize_readers(self):
        """Initialize both kernel and usermode readers"""
        print(f"[Memory] Initializing memory interface for PID {self.process_id}")
        
        # Always create usermode reader as fallback
        try:
            self.usermode_reader = UsermodeMemoryReader(self.process_handle)
            print("[Memory] ✓ Usermode reader initialized")
        except Exception as e:
            print(f"[Memory] ✗ Failed to initialize usermode reader: {e}")
        
        # Try to create kernel reader if enabled
        kernel_enabled = self.config and getattr(self.config, 'kernel_mode_enabled', False)
        print(f"[Memory] Kernel mode enabled in config: {kernel_enabled}")
        
        if kernel_enabled:
            try:
                print("[Memory] Attempting to initialize kernel reader...")
                self.kernel_reader = KernelMemoryReader(self.process_id)
                if self.kernel_reader._ensure_driver():
                    self._current_reader = self.kernel_reader
                    self._kernel_mode_active = True
                    drv_name = (getattr(self.config, "kernel_driver", "binalyze_irec") or "binalyze_irec")
                    print(f"[Memory] 🚀 KERNEL MODE ACTIVE - backend: {drv_name}")
                    
                    # Track active kernel instances for GUI status
                    if not hasattr(Config, '_kernel_active_instances'):
                        Config._kernel_active_instances = 0
                    Config._kernel_active_instances += 1
                else:
                    print("[Memory] ⚠️ Kernel driver not available, falling back to usermode")
                    if getattr(self.config, 'kernel_fallback_to_usermode', True):
                        self._current_reader = self.usermode_reader
                        print("[Memory] ✓ Fallback to usermode successful")
                    else:
                        raise Exception("Kernel mode required but driver unavailable")
            except Exception as e:
                print(f"[Memory] ✗ Failed to initialize kernel reader: {e}")
                if getattr(self.config, 'kernel_fallback_to_usermode', True):
                    print("[Memory] Falling back to usermode...")
                    self._current_reader = self.usermode_reader
                else:
                    raise Exception(f"Kernel mode required but failed: {e}")
        else:
            print("[Memory] Using usermode memory access (kernel mode disabled)")
            self._current_reader = self.usermode_reader
        
        if not self._current_reader:
            raise Exception("Failed to initialize any memory reader")
            
        # Final status report
        mode = "KERNEL MODE" if self._kernel_mode_active else "USERMODE"
        print(f"[Memory] Final Status: {mode} - Ready for operations")
    
    def is_kernel_mode_active(self) -> bool:
        """Check if kernel mode is currently active"""
        return self._kernel_mode_active
    
    def switch_to_kernel_mode(self) -> bool:
        """Switch to kernel mode if available"""
        if self.kernel_reader and self.kernel_reader._ensure_driver():
            self._current_reader = self.kernel_reader
            self._kernel_mode_active = True
            print("[Memory] Switched to kernel mode")
            return True
        return False
    
    def switch_to_usermode(self) -> bool:
        """Switch to usermode"""
        if self.usermode_reader:
            self._current_reader = self.usermode_reader
            self._kernel_mode_active = False
            print("[Memory] Switched to usermode")
            return True
        return False
    
    def get_process_base_address(self) -> int:
        """Get process base address (kernel mode only)"""
        if self.kernel_reader and self.kernel_reader._ensure_driver():
            try:
                return self.kernel_reader.driver.get_process_base(self.process_id)
            except Exception:
                pass
        return 0
    
    # Delegate all memory operations to current reader
    def read_bytes(self, address: int, size: int) -> bytes:
        return self._current_reader.read_bytes(address, size)
    
    def write_bytes(self, address: int, data: bytes) -> bool:
        return self._current_reader.write_bytes(address, data)
    
    def read_int(self, address: int) -> int:
        return self._current_reader.read_int(address)
    
    def read_uint32(self, address: int) -> int:
        return self._current_reader.read_uint32(address)
    
    def read_uint64(self, address: int) -> int:
        return self._current_reader.read_uint64(address)
    
    def read_float(self, address: int) -> float:
        return self._current_reader.read_float(address)
    
    def read_vec3(self, address: int) -> list:
        return self._current_reader.read_vec3(address)
    
    def read_string(self, address: int, max_length: int = 256) -> str:
        return self._current_reader.read_string(address, max_length)
    
    def write_int(self, address: int, value: int) -> bool:
        return self._current_reader.write_int(address, value)
    
    def write_uint32(self, address: int, value: int) -> bool:
        return self._current_reader.write_uint32(address, value)
    
    def write_float(self, address: int, value: float) -> bool:
        return self._current_reader.write_float(address, value)

def ensure_kernel_driver_started() -> bool:
    """Eagerly load + start the configured kernel backend.

    Idempotent. Populates the module-level ``_kernel_driver`` so subsequent
    ``MemoryInterface`` instances reuse it instead of re-loading. Returns
    True if a backend is live.
    """
    global _kernel_driver, _driver_initialization_attempted
    with _kernel_driver_lock:
        if _kernel_driver is not None:
            return True
        if _load_kernel_driver is None:
            return False
        _driver_initialization_attempted = True
        name = (getattr(Config, "kernel_driver", "binalyze_irec") or "binalyze_irec").strip().lower()
        for candidate in (name, "binalyze_irec"):
            if not candidate:
                continue
            drv = _load_kernel_driver(candidate)
            if drv is None:
                continue
            try:
                if drv.start():
                    _kernel_driver = drv
                    print(f"[Kernel] Auto-started backend '{candidate}': {drv.status()}")
                    return True
                print(f"[Kernel] Backend '{candidate}' refused to start: {drv.status()}")
            except Exception as e:
                print(f"[Kernel] Backend '{candidate}' raised: {e}")
        return False


def cleanup_kernel_driver():
    """Cleanup kernel driver on exit"""
    global _kernel_driver, _kernel_driver_lock

    with _kernel_driver_lock:
        if _kernel_driver:
            try:
                _kernel_driver.stop()
                print("[Kernel] Driver cleaned up successfully")
            except Exception as e:
                print(f"[Kernel] Error cleaning up driver: {e}")
            finally:
                _kernel_driver = None

# Register cleanup function
import atexit
atexit.register(cleanup_kernel_driver)
