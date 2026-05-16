"""Refresh ``Process.offsets.Offsets`` in-place from a live cs2.exe.

Drives :mod:`Process.dumper` to pattern-scan client.dll / inputsystem.dll /
matchmaking.dll and walk schemasystem.dll, then writes the resulting
RVAs/field offsets straight onto the static ``Offsets`` class so the rest of
the codebase (ESP, Aimbot, Glow, TriggerBot, etc.) picks them up without any
further changes.

ESP/Aimbot read ``Offsets.dwEntityList``/``Offsets.m_iHealth`` etc. directly
from the class. Mutating those class attributes is the lowest-disruption way
to plug fresh offsets in -- nothing else needs to import this module.
"""
from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Optional

from .dumper import CS2Dumper, find_module, run_dumper
from .offsets import Offsets


# Field name maps. Many fields live on multiple classes in the CS2 schema
# (e.g. m_iTeamNum is on C_BaseEntity AND on the player pawn), so we pick the
# canonical owner here -- matching what the C++ side does in Offsets.cpp.
SCHEMA_FIELD_OWNERS: list[tuple[str, str]] = [
    # (className, fieldName)
    ("C_BaseEntity",                "m_iHealth"),
    ("C_BaseEntity",                "m_iMaxHealth"),
    ("C_BaseEntity",                "m_iTeamNum"),
    ("C_BaseEntity",                "m_lifeState"),
    ("C_BaseEntity",                "m_fFlags"),
    ("C_BaseEntity",                "m_pGameSceneNode"),
    ("C_BaseEntity",                "m_vecAbsVelocity"),
    ("C_BaseEntity",                "m_vecVelocity"),
    ("C_BaseEntity",                "m_nSubclassID"),
    ("C_BasePlayerPawn",            "m_vOldOrigin"),
    ("C_BasePlayerPawn",            "m_pWeaponServices"),
    ("C_BasePlayerPawn",            "m_pObserverServices"),
    ("C_BasePlayerPawn",            "m_pCameraServices"),
    ("C_BasePlayerPawn",            "m_pItemServices"),
    ("C_BasePlayerPawn",            "m_hController"),
    ("C_CSPlayerPawnBase",          "m_flFlashDuration"),
    ("C_CSPlayerPawn",              "m_ArmorValue"),
    ("C_CSPlayerPawn",              "m_bIsScoped"),
    ("C_CSPlayerPawn",              "m_bIsDefusing"),
    ("C_CSPlayerPawn",              "m_angEyeAngles"),
    ("C_CSPlayerPawn",              "m_iShotsFired"),
    ("C_CSPlayerPawn",              "m_iIDEntIndex"),
    ("C_CSPlayerPawn",              "m_iFOVStart"),
    ("C_CSPlayerPawn",              "m_aimPunchAngle"),
    ("C_CSPlayerPawn",              "m_aimPunchCache"),
    ("C_CSPlayerPawn",              "m_pAimPunchServices"),
    ("C_CSPlayerPawn",              "m_pBulletServices"),
    ("C_CSPlayerPawn",              "m_pClippingWeapon"),
    ("C_CSPlayerPawn",              "m_bWaitForNoAttack"),
    ("C_CSPlayerPawn",              "m_flEmitSoundTime"),
    ("C_CSPlayerPawn",              "m_vecLastClipCameraPos"),
    ("C_CSPlayerPawn",              "m_entitySpottedState"),
    ("EntitySpottedState_t",        "m_bSpottedByMask"),
    ("CBasePlayerController",       "m_hPawn"),
    ("CBasePlayerController",       "m_iszPlayerName"),
    ("CBasePlayerController",       "m_steamID"),
    ("CBasePlayerController",       "m_nTickBase"),
    ("CBasePlayerController",       "m_iObserverMode"),
    ("CCSPlayerController",         "m_bPawnIsAlive"),
    ("CCSPlayerController",         "m_hPlayerPawn"),
    ("CCSPlayerController",         "m_iPawnArmor"),
    ("CCSPlayerController",         "m_bPawnHasDefuser"),
    ("CCSPlayerController",         "m_bPawnHasHelmet"),
    ("CCSPlayerController",         "m_pInGameMoneyServices"),
    ("CCSPlayerController_InGameMoneyServices", "m_iAccount"),
    ("CPlayer_ObserverServices",    "m_hObserverTarget"),
    ("CPlayer_WeaponServices",      "m_hActiveWeapon"),
    ("CPlayer_WeaponServices",      "m_hMyWeapons"),
    ("CCSPlayer_BulletServices",    "m_totalHitsOnServer"),
    ("CCSPlayer_AimPunchServices",  "m_predictableBaseAngle"),
    ("C_EconEntity",                "m_AttributeManager"),
    ("C_AttributeContainer",        "m_Item"),
    ("C_EconItemView",              "m_iItemDefinitionIndex"),
    ("C_BasePlayerWeapon",          "m_iClip1"),
    ("CBasePlayerWeaponVData",      "m_iMaxClip1"),
    ("CCSWeaponBaseVData",          "m_szName"),
    ("CSkeletonInstance",           "m_modelState"),
    ("CPlayer_MovementServices",    "m_vecVelocity"),
    ("C_PlantedC4",                 "m_bBeingDefused"),
    ("C_PlantedC4",                 "m_flDefuseCountDown"),
    ("C_PlantedC4",                 "m_nBombSite"),
]

# Pattern-scanned client.dll RVAs and similar friends.
MODULE_OFFSETS: list[tuple[str, str]] = [
    ("client.dll", "dwEntityList"),
    ("client.dll", "dwViewMatrix"),
    ("client.dll", "dwViewAngles"),
    ("client.dll", "dwLocalPlayerController"),
    ("client.dll", "dwLocalPlayerPawn"),
    ("client.dll", "dwGlobalVars"),
    ("client.dll", "dwPlantedC4"),
    ("client.dll", "dwPrediction"),
    ("client.dll", "dwSensitivity"),
    ("client.dll", "dwSensitivity_sensitivity"),
    ("client.dll", "dwCSGOInput"),
    ("inputsystem.dll", "dwInputSystem"),
    ("matchmaking.dll", "dwGameTypes"),
]


def _find_cs2_pid() -> Optional[int]:
    """Find cs2.exe by walking the process snapshot."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]
    TH32CS_SNAPPROCESS = 0x00000002

    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == ctypes.c_void_p(-1).value:
        return None
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(pe)
        if not k32.Process32FirstW(snap, ctypes.byref(pe)):
            return None
        while True:
            if pe.szExeFile.lower() == "cs2.exe":
                return int(pe.th32ProcessID)
            if not k32.Process32NextW(snap, ctypes.byref(pe)):
                break
    finally:
        k32.CloseHandle(snap)
    return None


def _open_cs2(pid: int) -> int:
    PROCESS_ACCESS = 0x0010 | 0x0400  # VM_READ | QUERY_INFORMATION
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k32.OpenProcess(PROCESS_ACCESS, False, pid)
    return int(h or 0)


def apply_to_offsets_class(dumper: CS2Dumper, log=print) -> int:
    """Set fresh dumper values on the static :class:`Offsets`. Returns count."""
    applied = 0
    skipped: list[str] = []

    # Module RVAs
    for mod, name in MODULE_OFFSETS:
        rva = dumper.offsets.get(mod, {}).get(name)
        if rva:
            setattr(Offsets, name, rva)
            applied += 1
        else:
            skipped.append(f"{mod}/{name}")

    # Schema fields
    for cls_name, field in SCHEMA_FIELD_OWNERS:
        cls_fields = dumper.schema_fields.get(cls_name, {})
        if field in cls_fields:
            setattr(Offsets, field, cls_fields[field])
            applied += 1
        else:
            skipped.append(f"{cls_name}.{field}")

    # Derived offsets that don't fall out of the dump directly.
    skel = dumper.schema_fields.get("CSkeletonInstance", {}).get("m_modelState")
    if skel is not None:
        Offsets.m_pBoneArray = skel + 0x80   # Pawn.BoneArray = m_modelState + 0x80
        applied += 1

    # vecAbsOrigin lives on CGameSceneNode; ESP reads it via m_vOldOrigin
    # (pawn-relative). Keep both populated.
    abs_origin = dumper.schema_fields.get("CGameSceneNode", {}).get("m_vecAbsOrigin")
    if abs_origin is not None:
        Offsets.m_vecAbsOrigin = abs_origin
        applied += 1

    if skipped:
        log(f"[Offsets] {applied} offsets refreshed; {len(skipped)} unchanged (using fallback)")
        # Only log the first few skips; the rest are usually optional/aliases.
        for s in skipped[:10]:
            log(f"[Offsets]   skip: {s}")
        if len(skipped) > 10:
            log(f"[Offsets]   ... and {len(skipped) - 10} more")
    else:
        log(f"[Offsets] {applied} offsets refreshed")
    return applied


_refresh_lock = threading.Lock()
_last_refresh_at: float = 0.0


def refresh_now(memory_interface=None, log=print, force: bool = False) -> bool:
    """Run the dumper end-to-end and patch :class:`Offsets`.

    Returns True if the dumper completed and at least one offset was applied.
    Re-entrant safe; cached for 60s unless ``force=True`` is passed.
    """
    global _last_refresh_at
    with _refresh_lock:
        now = time.time()
        if not force and (now - _last_refresh_at) < 60.0:
            return True
        pid = _find_cs2_pid()
        if not pid:
            log("[Offsets] cs2.exe not running -- skipping refresh, using static fallback")
            return False
        handle = _open_cs2(pid)
        if not handle:
            log("[Offsets] OpenProcess(cs2.exe) failed -- using static fallback")
            return False
        try:
            d = run_dumper(pid, handle, memory_interface=memory_interface, log=log)
            if not d:
                log("[Offsets] dumper failed -- using static fallback")
                return False
            applied = apply_to_offsets_class(d, log=log)
            if applied == 0:
                log("[Offsets] dumper produced 0 offsets -- using static fallback")
                return False
            _last_refresh_at = now
            return True
        finally:
            try:
                ctypes.WinDLL("kernel32").CloseHandle(handle)
            except Exception:
                pass


def refresh_in_background(memory_interface=None, log=print):
    """Kick off ``refresh_now`` on a daemon thread. Use for startup hooks
    where blocking the UI thread would be a bad idea."""
    t = threading.Thread(
        target=refresh_now,
        kwargs={"memory_interface": memory_interface, "log": log},
        name="OffsetRefreshThread",
        daemon=True,
    )
    t.start()
    return t
