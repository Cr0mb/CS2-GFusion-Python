r"""Binalyze IREC kernel-driver backend (KDU provider #41, CVE-2023-41444).

Pure-Python loader. No external binaries (no kdmapper, no KDU.exe). The flow
mirrors what NeacSafe64 used to do, but for the Binalyze IREC.sys driver:

    1. enable SeLoadDriverPrivilege on the current process
    2. write HKLM\System\CurrentControlSet\Services\<svc> registry key
    3. NtLoadDriver() to load IREC.sys into the kernel
    4. CreateFileW("\\\\.\\IREC") to open the device
    5. DeviceIoControl(IOCTL_IREC_OPEN_PROCESS, &pid, &handle) to get an
       elevated HANDLE to cs2.exe
    6. on shutdown: close handle, NtUnloadDriver(), wipe registry key

Protocol cross-checked against KDU-master/Source/Hamakaze/idrv/binalyze.{h,cpp}:

    #define IOCTL_IREC_OPEN_PROCESS 0x80012028   // METHOD_BUFFERED
    DWORD data = HandleToUlong(ProcessId);
    supCallDriver(hDev, IOCTL, &data, sizeof(data), &data, sizeof(data));
    *ProcessHandle = UlongToHandle(data);

    -> in/out buffers are both DWORD (4 bytes). Driver overwrites the input.
"""
from __future__ import annotations

import ctypes
import logging
import os
from ctypes import wintypes
from typing import Optional

logger = logging.getLogger(__name__)

# --- Windows / driver constants ---
SERVICE_KERNEL_DRIVER = 0x00000001
SERVICE_DEMAND_START  = 0x00000003
SERVICE_ERROR_NORMAL  = 0x00000001

REG_DWORD     = 4
REG_EXPAND_SZ = 2
HKEY_LOCAL_MACHINE = 0x80000002
KEY_ALL_ACCESS     = 0xF003F

GENERIC_READ_WRITE = 0xC0000000
OPEN_EXISTING      = 3
FILE_ATTR_NORMAL   = 0x80
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY             = 0x0008
SE_PRIVILEGE_ENABLED    = 0x00000002

STATUS_SUCCESS                = 0x00000000
STATUS_IMAGE_ALREADY_LOADED   = 0xC000010E

IOCTL_IREC_OPEN_PROCESS = 0x80012028  # CTL_CODE(0x8001, 0x80A, METHOD_BUFFERED, FILE_ANY_ACCESS)

DEFAULT_SERVICE_NAME    = "GFusionIREC"
DEFAULT_DRIVER_FILENAME = "IREC.sys"
DEVICE_PATH             = "\\\\.\\IREC"


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _LUID_AND_ATTR(ctypes.Structure):
    _fields_ = [("Luid", _LUID), ("Attributes", wintypes.DWORD)]


class _TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD),
                ("Privileges", _LUID_AND_ATTR * 1)]


class _UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT),
                ("MaximumLength", wintypes.USHORT),
                ("Buffer", wintypes.LPWSTR)]


class BinalyzeIRECDriver:
    """Loads IREC.sys, hands out elevated process handles, then unloads."""

    def __init__(self, service_name: str = DEFAULT_SERVICE_NAME):
        self.service_name: str = service_name
        self.driver_path: Optional[str] = None
        self.device_handle: int = 0
        self._ready = False

        self._ntdll = ctypes.WinDLL("ntdll",    use_last_error=True)
        self._k32   = ctypes.WinDLL("kernel32", use_last_error=True)
        self._adv   = ctypes.WinDLL("advapi32", use_last_error=True)

        self._setup_prototypes()

    # ------------------------------------------------------------------
    # ctypes prototype setup (avoids 32/64-bit truncation surprises)
    # ------------------------------------------------------------------
    def _setup_prototypes(self) -> None:
        k32, adv, ntdll = self._k32, self._adv, self._ntdll

        k32.GetCurrentProcess.restype  = wintypes.HANDLE
        k32.CloseHandle.argtypes       = [wintypes.HANDLE]
        k32.CloseHandle.restype        = wintypes.BOOL

        k32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p,  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        k32.CreateFileW.restype = wintypes.HANDLE

        k32.DeviceIoControl.argtypes = [
            wintypes.HANDLE, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        k32.DeviceIoControl.restype = wintypes.BOOL

        adv.OpenProcessToken.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
        ]
        adv.OpenProcessToken.restype = wintypes.BOOL

        adv.LookupPrivilegeValueW.argtypes = [
            wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(_LUID),
        ]
        adv.LookupPrivilegeValueW.restype = wintypes.BOOL

        adv.AdjustTokenPrivileges.argtypes = [
            wintypes.HANDLE, wintypes.BOOL,
            ctypes.POINTER(_TOKEN_PRIVILEGES), wintypes.DWORD,
            ctypes.POINTER(_TOKEN_PRIVILEGES), ctypes.POINTER(wintypes.DWORD),
        ]
        adv.AdjustTokenPrivileges.restype = wintypes.BOOL

        adv.RegCreateKeyExW.argtypes = [
            wintypes.HKEY, wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPCWSTR,
            wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            ctypes.POINTER(wintypes.HKEY), ctypes.POINTER(wintypes.DWORD),
        ]
        adv.RegCreateKeyExW.restype = wintypes.LONG

        adv.RegSetValueExW.argtypes = [
            wintypes.HKEY, wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD,
        ]
        adv.RegSetValueExW.restype = wintypes.LONG

        adv.RegCloseKey.argtypes = [wintypes.HKEY]
        adv.RegCloseKey.restype  = wintypes.LONG
        adv.RegDeleteKeyW.argtypes = [wintypes.HKEY, wintypes.LPCWSTR]
        adv.RegDeleteKeyW.restype  = wintypes.LONG

        ntdll.NtLoadDriver.argtypes   = [ctypes.POINTER(_UNICODE_STRING)]
        ntdll.NtLoadDriver.restype    = ctypes.c_long
        ntdll.NtUnloadDriver.argtypes = [ctypes.POINTER(_UNICODE_STRING)]
        ntdll.NtUnloadDriver.restype  = ctypes.c_long

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_driver_path(self) -> Optional[str]:
        if self.driver_path and os.path.exists(self.driver_path):
            return self.driver_path

        process_dir  = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(process_dir))
        parent       = os.path.dirname(project_root)

        for base in (
            os.path.join(project_root, "drivers"),
            os.path.join(parent,       "drivers"),
            process_dir,
            project_root,
        ):
            for name in (DEFAULT_DRIVER_FILENAME, "irec.sys", "Irec.sys"):
                p = os.path.join(base, name)
                if os.path.exists(p):
                    self.driver_path = os.path.abspath(p)
                    return self.driver_path
        return None

    def _enable_load_driver_privilege(self) -> bool:
        h_token = wintypes.HANDLE()
        if not self._adv.OpenProcessToken(
            self._k32.GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(h_token),
        ):
            logger.error("[IREC] OpenProcessToken failed: %d", ctypes.get_last_error())
            return False
        try:
            luid = _LUID()
            if not self._adv.LookupPrivilegeValueW(None, "SeLoadDriverPrivilege",
                                                   ctypes.byref(luid)):
                logger.error("[IREC] LookupPrivilegeValueW failed: %d",
                             ctypes.get_last_error())
                return False
            tp = _TOKEN_PRIVILEGES()
            tp.PrivilegeCount = 1
            tp.Privileges[0].Luid = luid
            tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
            ok = self._adv.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp),
                                                 0, None, None)
            err = ctypes.get_last_error()
            if not ok or err != 0:
                logger.error("[IREC] AdjustTokenPrivileges failed: ok=%s err=%d",
                             bool(ok), err)
                return False
            return True
        finally:
            self._k32.CloseHandle(h_token)

    def _registry_path(self) -> str:
        return f"System\\CurrentControlSet\\Services\\{self.service_name}"

    def _nt_registry_path(self) -> str:
        return (f"\\Registry\\Machine\\System\\CurrentControlSet\\Services\\"
                f"{self.service_name}")

    def _write_service_key(self) -> bool:
        h_key = wintypes.HKEY()
        res = self._adv.RegCreateKeyExW(
            HKEY_LOCAL_MACHINE, self._registry_path(), 0, None, 0,
            KEY_ALL_ACCESS, None, ctypes.byref(h_key), None,
        )
        if res != 0:
            logger.error("[IREC] RegCreateKeyExW failed: %d", res)
            return False
        try:
            img = ctypes.create_unicode_buffer(f"\\??\\{self.driver_path}")
            self._adv.RegSetValueExW(h_key, "ImagePath", 0, REG_EXPAND_SZ,
                                     img, ctypes.sizeof(img))

            for name, value in (
                ("Type",         SERVICE_KERNEL_DRIVER),
                ("ErrorControl", SERVICE_ERROR_NORMAL),
                ("Start",        SERVICE_DEMAND_START),
            ):
                d = wintypes.DWORD(value)
                self._adv.RegSetValueExW(h_key, name, 0, REG_DWORD,
                                         ctypes.byref(d), ctypes.sizeof(d))
            return True
        finally:
            self._adv.RegCloseKey(h_key)

    def _delete_service_key(self) -> None:
        # ERROR_FILE_NOT_FOUND (2) is fine — already gone.
        res = self._adv.RegDeleteKeyW(HKEY_LOCAL_MACHINE, self._registry_path())
        if res not in (0, 2):
            logger.warning("[IREC] RegDeleteKeyW failed: %d", res)

    def _make_unicode_string(self, text: str):
        # IMPORTANT: keep `buf` alive — UNICODE_STRING.Buffer is a raw pointer.
        buf = ctypes.create_unicode_buffer(text)
        u = _UNICODE_STRING()
        u.Buffer        = ctypes.cast(buf, wintypes.LPWSTR)
        u.Length        = len(text) * 2
        u.MaximumLength = u.Length + 2
        return u, buf

    # ------------------------------------------------------------------
    # IKernelDriver interface
    # ------------------------------------------------------------------
    def start(self) -> bool:
        if self._ready:
            return True

        if not self._get_driver_path():
            logger.error("[IREC] %s not found in drivers/. Refusing to start.",
                         DEFAULT_DRIVER_FILENAME)
            return False

        if not self._enable_load_driver_privilege():
            logger.error("[IREC] SeLoadDriverPrivilege required (run as admin).")
            return False

        if not self._write_service_key():
            return False

        u_str, _hold = self._make_unicode_string(self._nt_registry_path())
        status = self._ntdll.NtLoadDriver(ctypes.byref(u_str)) & 0xFFFFFFFF
        if status not in (STATUS_SUCCESS, STATUS_IMAGE_ALREADY_LOADED):
            logger.error("[IREC] NtLoadDriver failed: 0x%08X", status)
            self._delete_service_key()
            return False
        if status == STATUS_IMAGE_ALREADY_LOADED:
            logger.info("[IREC] driver was already loaded; reusing")

        self.device_handle = self._k32.CreateFileW(
            DEVICE_PATH, GENERIC_READ_WRITE, 0, None,
            OPEN_EXISTING, FILE_ATTR_NORMAL, None,
        )
        if not self.device_handle or self.device_handle == INVALID_HANDLE_VALUE:
            err = ctypes.get_last_error()
            logger.error("[IREC] CreateFileW(%s) failed: %d", DEVICE_PATH, err)
            self.device_handle = 0
            self._unload_driver()
            return False

        self._ready = True
        logger.info("[IREC] driver loaded; device handle ready")
        return True

    def stop(self) -> bool:
        ok = True
        if self.device_handle:
            self._k32.CloseHandle(self.device_handle)
            self.device_handle = 0

        if not self._enable_load_driver_privilege():
            ok = False

        if not self._unload_driver():
            ok = False

        self._delete_service_key()
        self._ready = False
        return ok

    def _unload_driver(self) -> bool:
        u_str, _hold = self._make_unicode_string(self._nt_registry_path())
        status = self._ntdll.NtUnloadDriver(ctypes.byref(u_str)) & 0xFFFFFFFF
        if status != STATUS_SUCCESS:
            logger.warning("[IREC] NtUnloadDriver returned 0x%08X", status)
            return False
        return True

    def open_process(self, pid: int) -> Optional[int]:
        if not self._ready or not self.device_handle:
            return None

        # KDU passes one DWORD in, expects the driver to overwrite it with
        # the elevated handle (also 32 bits — UlongToHandle on the way out).
        buf = ctypes.c_uint32(int(pid))
        bytes_returned = wintypes.DWORD(0)

        ok = self._k32.DeviceIoControl(
            self.device_handle,
            IOCTL_IREC_OPEN_PROCESS,
            ctypes.byref(buf), ctypes.sizeof(buf),
            ctypes.byref(buf), ctypes.sizeof(buf),
            ctypes.byref(bytes_returned), None,
        )
        if not ok:
            logger.error("[IREC] DeviceIoControl(OPEN_PROCESS pid=%d) failed: %d",
                         pid, ctypes.get_last_error())
            return None

        handle = int(buf.value)
        if not handle:
            logger.error("[IREC] driver returned NULL handle for pid=%d", pid)
            return None
        return handle

    def is_ready(self) -> bool:
        return self._ready

    def status(self) -> str:
        if self._ready:
            return f"IREC ready ({self.driver_path})"
        if not self.driver_path:
            return f"IREC.sys not found"
        return "IREC not started"
