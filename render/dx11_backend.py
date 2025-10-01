# DX11 Backend Stub - Fallback for broken dx11_backend.py
# This module is currently abandoned/broken but kept for reference

# print("[DX11] Using stub DX11Backend (abandoned module)")

class DX11Backend:
    """Fallback stub for DX11Backend"""
    
    def __init__(self, *args, **kwargs):
        print("[DX11] DX11Backend stub initialized (non-functional)")
        
    def __getattr__(self, name):
        """Return a no-op function for any method call"""
        def noop(*args, **kwargs):
            return None
        return noop

# For compatibility
COMTYPES_AVAILABLE = False
