"""GFusion entry point.

Self-elevates via UAC if not already Administrator, then launches GFusion.py
in the same Python interpreter. Admin rights are required because the
Binalyze IREC kernel driver is loaded via NtLoadDriver, which needs
SeLoadDriverPrivilege.

Use:
    pythonw start.pyw          # silent (no console)
    python  start.pyw          # with stdout for live driver logs

Or simply double-click start.pyw — Python's default association handles it.
"""
import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "GFusion.py")


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _relaunch_elevated() -> None:
    """Re-launch this script through ShellExecuteW("runas") and exit."""
    params = f'"{os.path.abspath(__file__)}"'
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, HERE, 1,
    )
    # ShellExecuteW returns >32 on success.
    if int(rc) <= 32:
        ctypes.windll.user32.MessageBoxW(
            None,
            "GFusion needs Administrator rights to load the kernel driver.\n\n"
            "UAC prompt was cancelled or blocked.",
            "GFusion", 0x10,
        )
    sys.exit(0)


def main() -> int:
    if not _is_admin():
        _relaunch_elevated()  # does not return

    if not os.path.isfile(MAIN):
        ctypes.windll.user32.MessageBoxW(
            None, f"GFusion.py not found:\n{MAIN}", "GFusion", 0x10,
        )
        return 1

    os.chdir(HERE)
    # Hand off to GFusion.py in this same interpreter so we don't spawn an
    # extra process. Exit code propagates back to the OS.
    code = compile(open(MAIN, "rb").read(), MAIN, "exec")
    g = {"__name__": "__main__", "__file__": MAIN}
    exec(code, g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
