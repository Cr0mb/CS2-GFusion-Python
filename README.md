# GFusion — Counter-Strike 2 Closet Cheat

The most advanced Counter-Strike closet cheat written in Python. Kernel-driver backed, fully self-contained, with no external loaders required at runtime.

[UC Forum](https://www.unknowncheats.me/forum/counter-strike-2-releases/711867-gfusion-closet-cheat.html) &nbsp;·&nbsp;
[YouTube](https://www.youtube.com/@cr0mble) &nbsp;·&nbsp;
[Install Walkthrough](https://www.youtube.com/watch?v=i3q_ryNTHww&lc=Ugz-S0AoR0fkkcZhfXZ4AaABAg)

<p align="center">
  <img src="https://github.com/user-attachments/assets/b25d707d-16bd-4897-8f27-b983e8657148" width="850" alt="GFusion menu">
</p>

---

## Quick Start

### 1. Install Python dependencies

```
pip install PyQt5 keyboard matplotlib requests pywin32
```

Python **3.14** is recommended — `vischeck.pyd` ships precompiled for that version. For other Python versions, rebuild it from `VisCheckCS2/`.

### 2. Confirm the kernel driver is in place

`drivers\IREC.sys` ships with the repo. If it's missing, restore it before launching.

### 3. Launch

Double-click **`start.pyw`** — it self-elevates via UAC and brings up the menu.

For live driver / memory logs, launch from a console:

```
python start.pyw
```

### 4. Open in-game

Start CS2, join a match, and press **`Insert`** to toggle the menu.

---

## Default Hotkeys

| Key | Action |
|---|---|
| `Insert` | Toggle menu |
| `Delete` | Panic key — instantly hides everything |
| `Mouse 1` | Aimbot activation |
| `Alt` | TriggerBot / Auto-Pistol activation |

All hotkeys are remappable in the **Configs** tab.

---

## Features

### Aimbot
- Multi-bone targeting (head, neck, chest, pelvis, hands, legs)
- Closest-to-crosshair or fixed-bone modes
- Recoil Control System (RCS) with learned recoil corrections
- Humanization — jitter, reaction delay, overshoot, smooth randomization
- Per-target aim profiles for unique smoothing per enemy
- Velocity prediction for moving targets
- Visibility-gated aiming (only fires at players you can see)
- Live "Kernel Mode" status indicator (driver loaded / kernel mode active / waiting)

### Player ESP
- Box ESP — normal, rounded, and corner styles
- Skeleton, head, bone-dot, line, trace overlays
- Health bar, armor bar, name, distance, weapon, money, scope, flashed status
- Visible / not-visible color separation
- Spectator list, team list, bomb ESP
- Lingering ESP for dead players (skeleton follows the ragdoll)
- Velocity, speed, and coordinates overlays
- Configurable colors and shapes per element

### World ESP
- Bomb sites, dropped weapons, grenade prediction

### Radar
- External draggable radar overlay (independent window)
- Resizable, alpha-adjustable, configurable FPS
- Fixed-range or dynamic-range modes
- Direction indicators for self, enemies, and team
- OBS-protected — invisible to OBS Studio captures

### Glow ESP
- Per-team glow colors (enemies / teammates)
- Live color picker

### Other Combat Modules
- **TriggerBot** — vischeck-gated, configurable delay / jitter / burst
- **Auto Pistol** — converts semi-auto pistols to full-auto
- **BHop** — frame-perfect bunny hop
- **Walk Bot** — pure-`ctypes` movement automation, no `psutil` dependency
- **FOV Changer** — overrides client FOV

### Safety / Stealth
- OBS Protection — overlay window excluded from screen captures
- Panic key (Delete) kills all overlays instantly
- Auto-cleanup on exit — driver unloaded, registry key wiped, no forensic traces
- No external dependencies at runtime — no `kdmapper.exe`, no `KDU.exe`

### Quality of Life
- Modern dark/red Qt UI with hover animations and a startup loader
- Resizable, font-customizable menu
- Console tab with text command system for every toggle
- Multiple config slots — atomic save with `.bak` backup, autosave every N minutes
- Live offset updates pulled from `cs2-dumper-main` with local fallback
- Crash-prevention layer with a rotating debug log (`gfusion_debug.log`, 10MB × 3)

---

## How It Works

GFusion talks to CS2 through a kernel driver — **Binalyze IREC** (CVE-2023-41444, KDU provider #41, **not** on the Microsoft driver blocklist) — for stealthy memory access.

The loader is **100% Python**:

1. Acquires `SeLoadDriverPrivilege` via `ctypes`.
2. Installs `IREC.sys` as kernel service `GFusionIREC`.
3. Loads it with `NtLoadDriver` and opens `\\.\IREC`.
4. Hands the device handle to a single shared `MemoryInterface` reused by ESP, Aimbot, FOV, Glow, and every other thread.

On clean exit, both `aboutToQuit` (Qt) and `atexit` hooks run:

1. Close the device handle.
2. Call `NtUnloadDriver`.
3. Wipe `HKLM\SYSTEM\CurrentControlSet\Services\GFusionIREC`.

No `kdmapper.exe`, no `KDU.exe`, no leftover service keys.

---

## Project Layout

```
CS2-GFusion-Python-main/
├── start.pyw                 UAC self-elevating launcher (recommended entry point)
├── GFusion.py                Main app — Qt UI, feature orchestration, logging
├── vischeck.pyd              Precompiled visibility-check module (Python 3.14)
├── Features/
│   ├── aimbot.py             Multi-bone aimbot + RCS + humanization
│   ├── esp.py                Player ESP renderer
│   ├── worldesp.py           World object ESP
│   ├── radar.py              External radar overlay
│   ├── glow.py               Glow ESP
│   ├── triggerbot.py         TriggerBot
│   ├── auto_pistol.py        Auto-pistol
│   ├── bhop.py               Bunny hop
│   ├── walk_bot.py           Movement automation
│   ├── fov.py                FOV changer
│   └── show.py               Overlay drawing primitives
├── Performance/
│   └── vischeck_optimizer.py BSP visibility optimizations
├── Process/
│   ├── memory_interface.py   Kernel/usermode memory abstraction
│   ├── offset_manager.py     Offset hot-reload
│   ├── offset_update.py      Pulls latest offsets from cs2-dumper
│   ├── offsets.py            Cached offsets
│   ├── config.py             Persistent config (atomic JSON + schema)
│   └── drivers/              Driver wrappers (IKernelDriver implementations)
├── VisCheckCS2/              Visibility-check source (rebuild target)
├── maps/                     Pre-baked .opt visibility maps
└── drivers/
    └── IREC.sys              Binalyze IREC kernel driver
```

---

## Requirements

- **OS:** Windows 10 / 11 (x64)
- **Python:** 3.14 (or rebuild `vischeck.pyd` from `VisCheckCS2/` for a different version)
- **Privileges:** Administrator (required to load the kernel driver)
- **Game:** Counter-Strike 2 (latest build)

Third-party Python packages: `PyQt5`, `keyboard`, `matplotlib`, `requests`, `pywin32`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| UAC prompt cancelled | Re-launch `start.pyw` and accept the prompt — admin is required for `NtLoadDriver` |
| `IREC.sys` not found | Restore the file to `.\drivers\IREC.sys` |
| `vischeck` import error | You are not on Python 3.14 — rebuild from `VisCheckCS2/` or update Python |
| Emoji crash on startup | Already fixed in v3.7 (stdio reconfigured to UTF-8 before any imports) |
| Aimbot misses heads after a CS2 update | Bone indices may have shifted — check the `BONES` table in `Process/config.py` |
| Map status / recoil broken after a CS2 update | Update offsets via the in-app updater (or check `cs2-dumper-main`) |

For live logs, see `gfusion_debug.log` in the repo root (rotating, 10MB with 3 backups).

---

## Disclaimer

This project is provided **for educational and research purposes only**. Using cheats in online competitive games may violate the game's Terms of Service and result in account bans, hardware bans, or VAC bans. You assume all risk for any use of this software. The authors are not responsible for any consequences arising from its use.

---

## Changelog

### v3.7 — 2026-05-02
- **Replaced backend with Binalyze IREC** (CVE-2023-41444).
- Pure-Python kernel driver loader. `SeLoadDriverPrivilege` + `NtLoadDriver` via `ctypes`.
- Auto-start on launch: `GFusion.py` installs the IREC service, loads the driver, and opens `\\.\IREC` before the Qt event loop starts.
- Auto-cleanup on exit: `aboutToQuit` + `atexit` close the device handle, `NtUnloadDriver`, and wipe `HKLM\...\Services\GFusionIREC` — no forensic traces.
- `MemoryInterface` now reuses a single shared driver instance across ESP / Aimbot / FOV / Glow threads instead of racing to load it per-feature.
- Aimbot tab "Kernel Mode" status reflects live driver state (Driver loaded / Kernel mode active / Waiting), polling every 2s.
- Added new entry point `start.pyw` — self-elevates via UAC and launches `GFusion.py` in the same interpreter.
- Reconfigured stdio to UTF-8 at startup so emoji log lines no longer crash `MemoryInterface` init on cp1252 consoles.
- **Fix:** CS2 build 14154 skeleton breakage — bone indices renumbered (head 6→7, pelvis 0→1, leg cluster shifted), per-bone 12-byte reads.
- **Fix:** Broken map-status pointer — `dwGameTypes` corrected to `0x1B0F80` from cs2-dumper-main (build 14158).
- **Fix:** Recoil control — `m_aimPunchAngle` was removed in 14154; rewired to read `AimPunchServices → m_predictableBaseAngle` chain with legacy fallback.
- **Cleanup:** Removed `GFusion_Launcher.pyw` (downloaded external kdmapper from a placeholder URL), the AES-encrypted `launcher.py` artifact, stale `kernel_config.json`, and four redundant test scripts.

### v3.6.5 — 2025-12-19
- Added external radar (compatibility with OBS protection added 2025-12-20).
- Added visibility color settings.
- Integrated FOV overlay color change for aimbot.
- Reorganized colors layout in menu.
- Added "Update Scripts" to GFusion Launcher for quick transfers between updates.
- Cleaned up GFusion repo source.
- **Note:** `vischeck` module updated for Python 3.14 — use old src, rebuild the module, or update Python.

### v3.6.4 — 2025-12-18
- Added more target bone selection options to the menu.

### v3.6.3 — 2025-12-18
- Added multiple bones to aimbot (closest-crosshair only for now). [Demo](https://www.youtube.com/watch?v=NPphc77LTcg)

### v3.6.2 — 2025-12-15
- Walk bot rewritten on pure `ctypes`, removed `psutil` dependency.

### v3.6.1 — 2025-12-14
- Added font changer to Configs tab.
- Made menu resizable.

### v3.6 — 2025-12-12
- Refactored ESP to reuse cached entities, batch-read bones, apply TTL-based memory refresh (~144 fps drawing).
- **Fix:** Aimbot — `aim_jitter_enabled` is now the single master toggle that cleanly enables/disables all jitter behavior without breaking existing logic.

### v3.5.4 — 2025-12-11
- New modern dark/red UI for all tabs.
- Added hover animations and a startup loading animation.
- Updated Console tab layout and log display.
- Added fallback offsets loading from local files if GitHub download fails.
- **Fix:** Indentation errors and menu crashes.
- Improved overall stability, performance, and responsiveness.

### v3.5.3 — 2025-12-02
- **Fix:** Error Code 1 — forced `win32api` global scope to resolve `UnboundLocalError` and prevent ESP crashes during panic-key checks.
- **Fix:** Error Code 1 in `start.pyw` — removed invalid CS2 directory switching, added full crash handling with traceback + error logging.
- Added full read-write process permissions in ESP to fix NoFlash not applying (`WriteProcessMemory` access).
- **Fix:** Crash from undefined `ui_refresher` during menu setting changes — added safe global refresher and protected UI updates.
- Added thread-safe menu toggle via Qt signal bridge — fixes cursor focus issues so the menu reliably opens/closes (previously required a click on the cheat window first).
- **Fix:** Aimbot vischeck.

### v3.5.2 — 2025-10-06
- Crash prevention and expanded logging.

### v3.5.1 — 2025-10-03
- Integrated Team List.
- Moved drawing FPS and map status box to Misc tab.

### v3.5 — 2025-10-01
- Standardized on `RPMReader` (removed duplicate `MemoryReader`, consolidated fallback logic).
- Added logging/error handling for `SendInput` and memory reads (invalid offsets warn instead of silent returns).
- Made process/module names configurable via `Config`.
- Optimized view-angle reads (batched pitch & yaw).
- Added idle timeout reset for recoil control (>2s pause).
- Added GUI + config toggle for mouse recording (default `True`).
- Introduced per-target aiming profiles (`get_target_profile`) for unique smoothing/jitter per enemy.
- Blended learned recoil corrections with human mouse data.
- **Fix:** Learning crash/unpack issues; updated schema to `(dp, dy, distance, bone, velocity)`.
- Rebuilt `RecoilViewer` with new schema + bone/distance/velocity stats and scatter plots.
- Patched `AimbotRCS.run` smoothing & max move (default 25, clamp before rounding).
- **Fix:** Circular jitter bug — switched sin/cos jitter → small random jitter, reduced smoothing cap, added snap-to-target.
- Integrated Visible-Only ESP.
- Upgraded menu styling (inspired by Artificial Aiming's Helios Framework).
- Added console tab/command system to control all toggles via text.
- Reorganized `GFusion.py` config tabs & menu.
- Check if CS2 is running before starting.
- Added lingering ESP for dead players (skeleton follows ragdoll).
- Implemented Visible-Only ESP optimizations (VisCheck).
- Restyled spectator list (dragging bug pending).
- Humanization features added to Aimbot (jitter / micro-move).
- **Fix:** Multiple menu/config crashing issues — stability improved.
- Optimized memory read structure, reduced code size.
- Added Draw Dead Entities toggle plus Dead Color CT and Dead Color T.
