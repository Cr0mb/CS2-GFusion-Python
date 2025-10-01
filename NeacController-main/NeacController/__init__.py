"""
NeacController Python Module

Python bindings for the NeacController Windows kernel driver.
Provides process memory manipulation and kernel-level operations.

Example usage:
    import neac_controller
    
    driver = neac_controller.NeacDriverManager()
    if driver.start_driver() and driver.connect():
        # Use driver functionality
        base_addr = driver.get_process_base(pid)
        value = driver.read_uint32(pid, base_addr)
        driver.disconnect()
        driver.stop_driver()
"""

__version__ = "1.0.0"
__author__ = "CS2 Team"

try:
    from .neac_controller import NeacDriverManager
    from .neac_controller import (
        PAGE_NOACCESS, PAGE_READONLY, PAGE_READWRITE, PAGE_WRITECOPY,
        PAGE_EXECUTE, PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE, 
        PAGE_EXECUTE_WRITECOPY, PAGE_GUARD, PAGE_NOCACHE, PAGE_WRITECOMBINE
    )
except ImportError:
    # Module not built yet
    import warnings
    warnings.warn(
        "NeacController C++ extension not found. "
        "Please build the module using 'python setup.py build_ext --inplace' "
        "or run build.bat as administrator.",
        ImportWarning
    )

__all__ = [
    'NeacDriverManager',
    'PAGE_NOACCESS', 'PAGE_READONLY', 'PAGE_READWRITE', 'PAGE_WRITECOPY',
    'PAGE_EXECUTE', 'PAGE_EXECUTE_READ', 'PAGE_EXECUTE_READWRITE', 
    'PAGE_EXECUTE_WRITECOPY', 'PAGE_GUARD', 'PAGE_NOCACHE', 'PAGE_WRITECOMBINE'
]
