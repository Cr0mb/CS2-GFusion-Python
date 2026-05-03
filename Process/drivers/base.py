"""Abstract kernel-driver backend interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class IKernelDriver(ABC):
    """All backends must produce an elevated process handle for cs2.exe.

    Lifecycle:
        d = load_driver(name)
        d.start()                # install/start the driver service
        h = d.open_process(pid)  # returns elevated HANDLE or 0
        ...
        d.stop()                 # uninstall/stop on shutdown
    """

    name: str = "base"

    @abstractmethod
    def start(self) -> bool:
        """Install + start the driver. Return True if the driver is now usable."""

    @abstractmethod
    def open_process(self, pid: int) -> int:
        """Return an elevated HANDLE to ``pid`` (0 on failure)."""

    @abstractmethod
    def stop(self) -> None:
        """Stop and remove the driver service. Best-effort; do not raise."""

    def is_ready(self) -> bool:
        """Optional: report whether the backend is currently usable."""
        return False

    def status(self) -> str:
        """Human-readable status string for the GUI."""
        return "ready" if self.is_ready() else "not ready"

    # Optional R/W primitives. Backends that only provide an elevated handle
    # (e.g. Binalyze IREC) leave these as the default no-op so that the
    # caller falls back to ReadProcessMemory on the elevated handle.
    def read_bytes(self, pid: int, addr: int, size: int) -> Optional[bytes]:
        return None

    def write_bytes(self, pid: int, addr: int, data: bytes) -> bool:
        return False
