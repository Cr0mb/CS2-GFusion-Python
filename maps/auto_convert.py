#!/usr/bin/env python3
"""
Auto Physics Converter Script
Runs PhysExtractor.exe then converts all .vphys files with VPhysToOpt.exe
"""

import os
import subprocess
import glob
import time
import sys
from pathlib import Path

def main():
    print("CS2 Auto Physics Converter")
    print("=" * 40)
    
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    
    # Define executable paths (look in current directory)
    phys_extractor_exe = script_dir / "PhysExtractor.exe"
    vphys_to_opt_exe = script_dir / "VPhysToOpt.exe"
    
    # Check if executables exist
    if not phys_extractor_exe.exists():
        print(f"ERROR: PhysExtractor.exe not found at: {phys_extractor_exe}")
        print("Please build the project first with: dotnet build")
        input("Press Enter to exit...")
        return
    
    if not vphys_to_opt_exe.exists():
        print(f"ERROR: VPhysToOpt.exe not found at: {vphys_to_opt_exe}")
        print("Please ensure VPhysToOpt.exe is in the bin directory")
        input("Press Enter to exit...")
        return
    
    print(f"PhysExtractor: {phys_extractor_exe}")
    print(f"VPhysToOpt: {vphys_to_opt_exe}")
    print(f"Working directory: {script_dir}")
    print()
    
    # Step 1: Run PhysExtractor.exe
    print("Step 1: Running PhysExtractor to extract .vphys files...")
    print("-" * 50)
    
    try:
        # Change to script directory so .vphys files are created here
        os.chdir(script_dir)
        
        # Run PhysExtractor.exe
        result = subprocess.run([str(phys_extractor_exe)], 
                              capture_output=False, 
                              text=True, 
                              cwd=str(script_dir))
        
        if result.returncode != 0:
            print(f"ERROR: PhysExtractor failed with return code: {result.returncode}")
            input("Press Enter to exit...")
            return
            
    except Exception as e:
        print(f"ERROR running PhysExtractor: {e}")
        input("Press Enter to exit...")
        return
    
    print("\nPhysExtractor completed!")
    
    # Step 2: Find all .vphys files in current directory
    print("\nStep 2: Finding .vphys files to convert...")
    print("-" * 50)
    
    vphys_files = list(Path(script_dir).glob("*.vphys"))
    
    if not vphys_files:
        print("No .vphys files found in the current directory.")
        input("Press Enter to exit...")
        return
    
    print(f"Found {len(vphys_files)} .vphys files to convert:")
    for i, file in enumerate(vphys_files, 1):
        print(f"  {i}. {file.name}")
    
    print()
    
    # Step 3: Convert each .vphys file with VPhysToOpt.exe
    print("Step 3: Converting .vphys files...")
    print("-" * 50)
    
    converted_count = 0
    failed_count = 0
    
    for i, vphys_file in enumerate(vphys_files, 1):
        print(f"Converting {i}/{len(vphys_files)}: {vphys_file.name}")
        
        try:
            # Run VPhysToOpt.exe with the directory path containing the .vphys file
            result = subprocess.run([str(vphys_to_opt_exe), str(script_dir)],
                                  capture_output=True,
                                  text=True,
                                  cwd=str(script_dir),
                                  timeout=60)  # 60 second timeout per file
            
            if result.returncode == 0:
                print(f"  ✓ Successfully converted: {vphys_file.name}")
                
                # Remove the original .vphys file after successful conversion
                try:
                    vphys_file.unlink()
                    print(f"  ✓ Removed original: {vphys_file.name}")
                    converted_count += 1
                except Exception as e:
                    print(f"  ⚠ Warning: Could not remove {vphys_file.name}: {e}")
                    converted_count += 1  # Still count as converted
                    
            else:
                print(f"  ✗ Failed to convert: {vphys_file.name}")
                print(f"    Return code: {result.returncode}")
                if result.stderr:
                    print(f"    Error: {result.stderr.strip()}")
                failed_count += 1
                
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout converting: {vphys_file.name}")
            failed_count += 1
            
        except Exception as e:
            print(f"  ✗ Error converting {vphys_file.name}: {e}")
            failed_count += 1
        
        # Small delay between conversions
        time.sleep(0.5)
    
    # Step 4: Summary
    print("\n" + "=" * 50)
    print("CONVERSION SUMMARY")
    print("=" * 50)
    print(f"Total files found: {len(vphys_files)}")
    print(f"Successfully converted: {converted_count}")
    print(f"Failed conversions: {failed_count}")
    
    if failed_count == 0:
        print("\n🎉 All files converted successfully!")
    else:
        print(f"\n⚠ {failed_count} files failed to convert.")
    
    # Check for any remaining .vphys files
    remaining_vphys = list(Path(script_dir).glob("*.vphys"))
    if remaining_vphys:
        print(f"\nRemaining .vphys files: {len(remaining_vphys)}")
        for file in remaining_vphys:
            print(f"  - {file.name}")
    else:
        print("\n✓ All .vphys files have been processed and removed.")
    
    print("\nConversion process completed!")
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
