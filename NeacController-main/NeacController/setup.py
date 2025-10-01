import pybind11
from pybind11.setup_helpers import Pybind11Extension, build_ext, Pybind11Extension
from setuptools import setup, Extension
import pybind11.setup_helpers

__version__ = "1.0.0"

# Define the extension module
ext_modules = [
    Pybind11Extension(
        "neac_controller",
        [
            "python_bindings.cpp",
            "controller.cpp", 
            "service.cpp"
        ],
        include_dirs=[
            pybind11.get_cmake_dir() + "/../../../include",
        ],
        libraries=["fltlib", "advapi32", "kernel32"],
        language='c++'
    ),
]

setup(
    name="neac_controller",
    version=__version__,
    author="CS2 Team",
    author_email="",
    url="",
    description="Python bindings for NeacController - Windows Kernel Driver Controller",
    long_description="""
NeacController Python Module

This module provides Python bindings for the NeacController Windows kernel driver,
enabling process memory manipulation, kernel memory access, and driver management
from Python applications.

Features:
- Driver service management (start/stop)
- Process memory read/write operations
- Kernel memory access
- Memory protection management
- Process control (kill processes)
- SSDT (System Service Descriptor Table) access

Requirements:
- Windows operating system
- Administrator privileges
- NeacSafe64 driver installed

Usage:
    import neac_controller
    
    # Create driver manager instance
    driver = neac_controller.NeacDriverManager()
    
    # Start the driver service
    if driver.start_driver():
        print("Driver started successfully")
    
    # Connect to the driver
    if driver.connect():
        print("Connected to driver")
        
        # Example: Read process memory
        pid = 1234  # target process ID
        base_addr = driver.get_process_base(pid)
        if base_addr:
            value = driver.read_uint32(pid, base_addr)
            print(f"Read value: {value}")
        
        # Disconnect when done
        driver.disconnect()
    
    # Stop the driver service
    driver.stop_driver()

Warning:
This module provides low-level system access and should be used with caution.
Improper use may cause system instability or security issues.
    """,
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.6",
    install_requires=[
        "pybind11>=2.6.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8", 
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: C++",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration",
    ],
)
