#!/usr/bin/env python3
"""
NeacController Python Module Example

This example demonstrates basic usage of the NeacController Python bindings.
Run this script as administrator to test the functionality.
"""

import neac_controller
import sys
import time

def main():
    print("NeacController Python Module Example")
    print("=====================================")
    
    # Create driver manager instance
    driver = neac_controller.NeacDriverManager()
    
    try:
        # Step 1: Start the driver service
        print("\n[1] Starting NeacSafe64 driver service...")
        if driver.start_driver():
            print("✓ Driver service started successfully")
        else:
            print("✗ Failed to start driver service")
            print("   Make sure you're running as administrator and the driver is installed")
            return False
        
        # Step 2: Connect to the driver
        print("\n[2] Connecting to driver...")
        if driver.connect():
            print("✓ Connected to driver successfully")
        else:
            print("✗ Failed to connect to driver")
            return False
        
        # Step 3: Demonstrate functionality
        print("\n[3] Testing driver functionality...")
        
        # Get current process information
        import os
        current_pid = os.getpid()
        print(f"Current process PID: {current_pid}")
        
        # Get process base address
        base_addr = driver.get_process_base(current_pid)
        if base_addr:
            print(f"✓ Process base address: 0x{base_addr:X}")
            
            # Test memory reading
            print("\n[4] Testing memory operations...")
            try:
                # Read some memory from our own process
                data = driver.read_process_memory(current_pid, base_addr, 64)
                if data:
                    print(f"✓ Read {len(data)} bytes from process memory")
                    print(f"   First 16 bytes: {data[:16].hex().upper()}")
                
                # Test typed reads
                print("\n[5] Testing typed memory reads...")
                try:
                    # Read different data types (might not be meaningful data, but tests the API)
                    uint32_val = driver.read_uint32(current_pid, base_addr)
                    uint64_val = driver.read_uint64(current_pid, base_addr)
                    print(f"✓ Read uint32: {uint32_val}")
                    print(f"✓ Read uint64: {uint64_val}")
                except Exception as e:
                    print(f"✗ Typed read error: {e}")
                
            except Exception as e:
                print(f"✗ Memory read error: {e}")
        else:
            print("✗ Failed to get process base address")
        
        # Test SSDT access
        print("\n[6] Testing SSDT access...")
        try:
            ssdt_table = driver.get_ssdt_table()
            if ssdt_table:
                non_zero_entries = [addr for addr in ssdt_table if addr != 0]
                print(f"✓ Retrieved SSDT table with {len(non_zero_entries)} non-zero entries")
                if non_zero_entries:
                    print(f"   First few entries: {[hex(addr) for addr in non_zero_entries[:5]]}")
            else:
                print("✗ Failed to retrieve SSDT table")
        except Exception as e:
            print(f"✗ SSDT access error: {e}")
        
        print("\n[7] All tests completed!")
        return True
        
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
        
    finally:
        # Always cleanup
        print("\n[8] Cleaning up...")
        driver.disconnect()
        print("✓ Disconnected from driver")
        
        driver.stop_driver()
        print("✓ Driver service stopped")

def advanced_example():
    """Advanced example showing more complex operations"""
    print("\n" + "="*50)
    print("ADVANCED EXAMPLE - Process Memory Scanner")
    print("="*50)
    
    driver = neac_controller.NeacDriverManager()
    
    try:
        if not driver.start_driver() or not driver.connect():
            print("Failed to initialize driver")
            return
        
        # Example: Simple memory pattern scanner
        def scan_for_pattern(pid, start_addr, size, pattern):
            """Scan memory for a byte pattern"""
            chunk_size = 4096
            current_addr = start_addr
            end_addr = start_addr + size
            
            while current_addr < end_addr:
                try:
                    data = driver.read_process_memory(pid, current_addr, min(chunk_size, end_addr - current_addr))
                    if data and pattern in data:
                        offset = data.find(pattern)
                        return current_addr + offset
                    current_addr += chunk_size
                except:
                    current_addr += chunk_size
            return None
        
        # Scan for a simple pattern in our own process
        import os
        current_pid = os.getpid()
        base_addr = driver.get_process_base(current_pid)
        
        if base_addr:
            print(f"Scanning process {current_pid} for pattern...")
            # Look for a common pattern (DOS header signature)
            pattern = b"MZ"
            found_addr = scan_for_pattern(current_pid, base_addr, 0x1000, pattern)
            
            if found_addr:
                print(f"✓ Found pattern at address: 0x{found_addr:X}")
            else:
                print("✗ Pattern not found in scanned region")
    
    finally:
        driver.disconnect()
        driver.stop_driver()

if __name__ == "__main__":
    print("Make sure you're running this script as Administrator!")
    input("Press Enter to continue or Ctrl+C to exit...")
    
    try:
        success = main()
        
        if success:
            print("\nWould you like to run the advanced example? (y/n): ", end="")
            if input().lower().startswith('y'):
                advanced_example()
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    
    print("\nExample completed. Press Enter to exit...")
    input()
