# NeacController Python Module

This Python module provides bindings for the NeacController Windows kernel driver, enabling process memory manipulation and kernel-level operations from Python.

## Features

- **Driver Management**: Start/stop the NeacSafe64 kernel driver service
- **Process Memory Operations**: Read/write process memory with type safety
- **Kernel Memory Access**: Direct kernel memory read/write capabilities  
- **Memory Protection**: Change memory protection flags
- **Process Control**: Kill processes, get process base addresses
- **SSDT Access**: Access System Service Descriptor Table

## Requirements

- Windows operating system
- Python 3.6 or higher
- Administrator privileges (required for kernel driver operations)
- NeacSafe64 kernel driver installed
- Visual Studio Build Tools or Visual Studio (for compilation)

## Installation

### Option 1: Build from source

```bash
# Install requirements
pip install -r requirements.txt

# Build and install the module
python setup.py build_ext --inplace
python setup.py install
```

### Option 2: Development installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Quick Start

```python
import neac_controller

# Create driver manager
driver = neac_controller.NeacDriverManager()

try:
    # Start the kernel driver service
    if not driver.start_driver():
        print("Failed to start driver service")
        exit(1)
    
    # Connect to the driver
    if not driver.connect():
        print("Failed to connect to driver")
        exit(1)
    
    print("Successfully connected to NeacController driver!")
    
    # Example: Get process base address
    pid = 1234  # Replace with target process ID
    base_addr = driver.get_process_base(pid)
    if base_addr:
        print(f"Process {pid} base address: 0x{base_addr:X}")
        
        # Read different data types
        byte_val = driver.read_uint8(pid, base_addr)
        int_val = driver.read_uint32(pid, base_addr)
        float_val = driver.read_float(pid, base_addr + 0x10)
        
        print(f"Byte value: {byte_val}")
        print(f"Integer value: {int_val}")
        print(f"Float value: {float_val}")
        
        # Write values
        driver.write_uint32(pid, base_addr + 0x20, 12345)
        driver.write_float(pid, base_addr + 0x24, 3.14159)
        
        # Read raw memory
        raw_data = driver.read_process_memory(pid, base_addr, 64)
        print(f"Raw memory (first 16 bytes): {raw_data[:16].hex()}")

finally:
    # Always cleanup
    driver.disconnect()
    driver.stop_driver()
```

## API Reference

### NeacDriverManager Class

#### Driver Management
- `start_driver()` -> `bool`: Start the NeacSafe64 driver service
- `stop_driver()` -> `bool`: Stop the NeacSafe64 driver service  
- `connect()` -> `bool`: Connect to the driver communication port
- `disconnect()` -> `None`: Disconnect from the driver
- `is_connected()` -> `bool`: Check if connected to the driver

#### Process Operations
- `get_process_base(pid: int)` -> `int`: Get process base address
- `kill_process_by_pid(pid: int)` -> `bool`: Terminate a process

#### Memory Operations
- `read_process_memory(pid: int, address: int, size: int)` -> `bytes`: Read raw memory
- `write_process_memory(pid: int, address: int, data: bytes)` -> `bool`: Write raw memory
- `protect_process_memory(pid: int, address: int, size: int, new_protect: int)` -> `bool`: Change memory protection

#### Typed Read Operations
- `read_uint8(pid: int, address: int)` -> `int`: Read unsigned 8-bit integer
- `read_uint16(pid: int, address: int)` -> `int`: Read unsigned 16-bit integer
- `read_uint32(pid: int, address: int)` -> `int`: Read unsigned 32-bit integer
- `read_uint64(pid: int, address: int)` -> `int`: Read unsigned 64-bit integer
- `read_int8(pid: int, address: int)` -> `int`: Read signed 8-bit integer
- `read_int16(pid: int, address: int)` -> `int`: Read signed 16-bit integer
- `read_int32(pid: int, address: int)` -> `int`: Read signed 32-bit integer
- `read_int64(pid: int, address: int)` -> `int`: Read signed 64-bit integer
- `read_float(pid: int, address: int)` -> `float`: Read 32-bit float
- `read_double(pid: int, address: int)` -> `float`: Read 64-bit double

#### Typed Write Operations
- `write_uint8(pid: int, address: int, value: int)` -> `bool`
- `write_uint16(pid: int, address: int, value: int)` -> `bool`
- `write_uint32(pid: int, address: int, value: int)` -> `bool`
- `write_uint64(pid: int, address: int, value: int)` -> `bool`
- `write_int8(pid: int, address: int, value: int)` -> `bool`
- `write_int16(pid: int, address: int, value: int)` -> `bool`
- `write_int32(pid: int, address: int, value: int)` -> `bool`
- `write_int64(pid: int, address: int, value: int)` -> `bool`
- `write_float(pid: int, address: int, value: float)` -> `bool`
- `write_double(pid: int, address: int, value: float)` -> `bool`

#### Kernel Operations
- `read_kernel_memory(address: int, size: int)` -> `bytes`: Read kernel memory
- `write_kernel_memory(dst_address: int, data: bytes)` -> `bool`: Write kernel memory
- `get_ssdt_table()` -> `list`: Get SSDT entries

#### Driver State
- `update_driver_state(function_id: int, state: int)` -> `bool`: Update driver state

### Memory Protection Constants

```python
# Available as module attributes
neac_controller.PAGE_NOACCESS         # 0x01
neac_controller.PAGE_READONLY         # 0x02
neac_controller.PAGE_READWRITE        # 0x04
neac_controller.PAGE_WRITECOPY        # 0x08
neac_controller.PAGE_EXECUTE          # 0x10
neac_controller.PAGE_EXECUTE_READ     # 0x20
neac_controller.PAGE_EXECUTE_READWRITE # 0x40
neac_controller.PAGE_EXECUTE_WRITECOPY # 0x80
neac_controller.PAGE_GUARD            # 0x100
neac_controller.PAGE_NOCACHE          # 0x200
neac_controller.PAGE_WRITECOMBINE     # 0x400
```

## Advanced Examples

### Memory Scanning
```python
def scan_memory_pattern(driver, pid, start_addr, end_addr, pattern):
    """Scan memory for a specific byte pattern"""
    chunk_size = 4096
    current_addr = start_addr
    
    while current_addr < end_addr:
        try:
            data = driver.read_process_memory(pid, current_addr, chunk_size)
            if pattern in data:
                offset = data.find(pattern)
                return current_addr + offset
            current_addr += chunk_size
        except:
            current_addr += chunk_size
    
    return None
```

### Process Memory Dumper
```python
def dump_process_memory(driver, pid, output_file):
    """Dump process memory to file"""
    base_addr = driver.get_process_base(pid)
    if not base_addr:
        return False
    
    with open(output_file, 'wb') as f:
        addr = base_addr
        chunk_size = 4096
        
        while True:
            try:
                data = driver.read_process_memory(pid, addr, chunk_size)
                if not data:
                    break
                f.write(data)
                addr += chunk_size
            except:
                break
    return True
```

## Security Considerations

⚠️ **WARNING**: This module provides low-level system access and requires administrator privileges. Use with extreme caution.

- Always run with administrator privileges
- Ensure the NeacSafe64 driver is from a trusted source
- Be careful when writing to process/kernel memory
- Always disconnect and stop the driver when finished
- Test thoroughly in a safe environment before production use

## Troubleshooting

### Common Issues

1. **"Failed to start driver service"**
   - Ensure running as administrator
   - Check if NeacSafe64.sys is properly installed
   - Verify driver is not blocked by antivirus

2. **"Failed to connect to driver"**
   - Make sure driver service is started
   - Check Windows Event Log for driver errors
   - Verify driver communication port is available

3. **Compilation errors**
   - Install Visual Studio Build Tools
   - Ensure pybind11 is properly installed
   - Check that all required libraries are available

4. **Access denied errors**
   - Run Python as administrator
   - Check target process permissions
   - Verify driver is loaded and running

## License

This project is provided as-is for educational and research purposes. Use at your own risk.
