"""GFusion kernel-driver backend.

A "kernel driver backend" supplies an elevated process HANDLE that bypasses
user-mode access restrictions on cs2.exe. Once we have the handle, the rest
of GFusion uses standard ``ReadProcessMemory`` / ``WriteProcessMemory`` —
the driver only needs to be invoked once at startup.

The single supported backend is **Binalyze IREC** (KDU provider #41,
CVE-2023-41444, NOT on the Microsoft driver blocklist as of KDU's published
provider table). Loading is implemented entirely in Python via NtLoadDriver
— no kdmapper, no KDU.exe, no other external binaries.
"""
from __future__ import annotations

from typing import Optional

from .base import IKernelDriver


def load_driver(name: str = "binalyze_irec") -> Optional[IKernelDriver]:
    """Return a Binalyze IREC backend instance.

    The ``name`` argument is accepted for back-compat with older callers but
    only ``binalyze_irec`` (and its aliases) is supported.
    """
    name = (name or "binalyze_irec").strip().lower()
    if name not in ("binalyze_irec", "irec", "binalyze"):
        # Refuse silently — the caller's fallback path will handle it.
        return None
    try:
        from .binalyze_irec import BinalyzeIRECDriver
        return BinalyzeIRECDriver()
    except Exception:
        return None


__all__ = ["IKernelDriver", "load_driver"]
