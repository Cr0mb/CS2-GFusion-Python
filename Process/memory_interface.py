"""
Unified Memory Interface for CS2 Cheat System
Supports both usermode (ReadProcessMemory) and kernel mode (NeacController) memory access
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

# Global variables
_kernel_driver = None
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
    """Kernel mode memory reader using NeacController driver"""
    
    def __init__(self, process_id: int):
        self.process_id = process_id
        self.driver = None
        self._initialize_driver()
    
    def _initialize_driver(self):
        """Initialize the kernel driver"""
        global _kernel_driver, _kernel_driver_lock, _driver_initialization_attempted
        
        with _kernel_driver_lock:
            if _kernel_driver is not None:
                self.driver = _kernel_driver
                return
            
            if _driver_initialization_attempted:
                return
            
            _driver_initialization_attempted = True
            
            try:
                # Import the NeacController module
                import sys
                import os
                
                # Add the NeacController directory to path
                controller_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                             'NeacController-main', 'NeacController')
                if controller_path not in sys.path:
                    sys.path.insert(0, controller_path)
                
                import neac_controller
                
                # Create driver manager instance
                driver_manager = neac_controller.NeacDriverManager()
                
                # Try to start and connect to driver
                if driver_manager.start_driver():
                    print("[Kernel] NeacSafe64 driver started successfully")
                    
                    if driver_manager.connect():
                        print("[Kernel] Connected to NeacController driver")
                        _kernel_driver = driver_manager
                        self.driver = _kernel_driver
                    else:
                        print("[Kernel] Failed to connect to driver")
                        driver_manager.stop_driver()
                else:
                    print("[Kernel] Failed to start NeacSafe64 driver")
                    
            except ImportError as e:
                print(f"[Kernel] NeacController module not found: {e}")
                print("[Kernel] Make sure to build the Python module first")
            except Exception as e:
                print(f"[Kernel] Failed to initialize kernel driver: {e}")
    
    def _ensure_driver(self) -> bool:
        """Ensure driver is available and connected"""
        return self.driver is not None and self.driver.is_connected()
    
    def read_bytes(self, address: int, size: int) -> bytes:
        if not self._ensure_driver():
            return b"\x00" * size
        
        try:
            data = self.driver.read_process_memory(self.process_id, address, size)
            return data if data else b"\x00" * size
        except Exception:
            return b"\x00" * size
    
    def write_bytes(self, address: int, data: bytes) -> bool:
        if not self._ensure_driver():
            return False
        
        try:
            return self.driver.write_process_memory(self.process_id, address, data)
        except Exception:
            return False
    
    def read_int(self, address: int) -> int:
        if not self._ensure_driver():
            return 0
        
        try:
            return self.driver.read_int32(self.process_id, address)
        except Exception:
            return 0
    
    def read_uint32(self, address: int) -> int:
        if not self._ensure_driver():
            return 0
        
        try:
            return self.driver.read_uint32(self.process_id, address)
        except Exception:
            return 0
    
    def read_uint64(self, address: int) -> int:
        if not self._ensure_driver():
            return 0
        
        try:
            return self.driver.read_uint64(self.process_id, address)
        except Exception:
            return 0
    
    def read_float(self, address: int) -> float:
        if not self._ensure_driver():
            return 0.0
        
        try:
            return self.driver.read_float(self.process_id, address)
        except Exception:
            return 0.0
    
    def write_int(self, address: int, value: int) -> bool:
        if not self._ensure_driver():
            return False
        
        try:
            return self.driver.write_int32(self.process_id, address, value)
        except Exception:
            return False
    
    def write_uint32(self, address: int, value: int) -> bool:
        if not self._ensure_driver():
            return False
        
        try:
            return self.driver.write_uint32(self.process_id, address, value)
        except Exception:
            return False
    
    def write_float(self, address: int, value: float) -> bool:
        if not self._ensure_driver():
            return False
        
        try:
            return self.driver.write_float(self.process_id, address, value)
        except Exception:
            return False

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
                    print("[Memory] 🚀 KERNEL MODE ACTIVE - Using NeacController driver")
                    
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
                    print("[Memory] 🔄 Falling back to usermode...")
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
        print(f"[Memory] 📊 Final Status: {mode} - Ready for operations")
    
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

def cleanup_kernel_driver():
    """Cleanup kernel driver on exit"""
    global _kernel_driver, _kernel_driver_lock
    
    with _kernel_driver_lock:
        if _kernel_driver:
            try:
                _kernel_driver.disconnect()
                _kernel_driver.stop_driver()
                print("[Kernel] Driver cleaned up successfully")
            except Exception as e:
                print(f"[Kernel] Error cleaning up driver: {e}")
            finally:
                _kernel_driver = None

# Register cleanup function
import atexit
atexit.register(cleanup_kernel_driver)
