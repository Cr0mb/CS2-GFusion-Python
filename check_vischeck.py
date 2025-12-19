#!/usr/bin/env python3
"""
Check VisCheck module compatibility
"""
import sys
import os
import platform
from pathlib import Path

def check_vischeck():
    print("🔍 VisCheck Module Checker")
    print("=" * 35)
    
    print(f"Python: {sys.version}")
    print(f"Architecture: {platform.architecture()}")
    print(f"Platform: {platform.platform()}")
    print(f"Machine: {platform.machine()}")
    print("")
    
    # Check for vischeck.pyd file
    vischeck_files = [
        "vischeck.pyd",
        "VisCheckCS2-main/VisCheckCS2/vischeck.pyd",
        "VisCheckCS2/vischeck.pyd"
    ]
    
    found_vischeck = None
    for vf in vischeck_files:
        if os.path.exists(vf):
            found_vischeck = vf
            size = os.path.getsize(vf)
            print(f"✅ Found: {vf} ({size:,} bytes)")
            break
    
    if not found_vischeck:
        print("❌ No vischeck.pyd file found!")
        print("   Looked for:")
        for vf in vischeck_files:
            print(f"   - {vf}")
        return False
    
    # Try to import vischeck
    print("\n🔄 Testing VisCheck import...")
    try:
        # Add to path if needed
        vischeck_dir = os.path.dirname(found_vischeck)
        if vischeck_dir and vischeck_dir not in sys.path:
            sys.path.insert(0, vischeck_dir)
        
        import vischeck
        print("✅ VisCheck import: SUCCESS")
        
        # Test basic functionality
        print("🔄 Testing VisCheck initialization...")
        checker = vischeck.VisCheck()
        print("✅ VisCheck initialization: SUCCESS")
        
        # Check if we can call basic methods
        try:
            checker.set_cache_enabled(True)
            print("✅ Cache methods: SUCCESS")
        except Exception as e:
            print(f"⚠️  Cache methods: {e}")
        
        return True
        
    except ImportError as e:
        print(f"❌ VisCheck import FAILED: {e}")
        print("\n💡 Possible solutions:")
        print("   1. Rebuild vischeck.pyd for this system")
        print("   2. Check if Visual C++ Redistributable is installed")
        print("   3. Verify Python architecture matches vischeck.pyd")
        return False
        
    except Exception as e:
        print(f"❌ VisCheck test FAILED: {e}")
        return False

if __name__ == "__main__":
    check_vischeck()
    input("\nPress Enter to exit...")
