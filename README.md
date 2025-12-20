## GFusion V3.6.5

The most advanced Counter-Strike closet cheats ever made in Python. Kernel driver included.

[UC Forum](https://www.unknowncheats.me/forum/counter-strike-2-releases/711867-gfusion-closet-cheat.html)
[YouTube](https://www.youtube.com/@cr0mble)

[How to Download and Install GFusion V3.6](https://www.youtube.com/watch?v=i3q_ryNTHww&lc=Ugz-S0AoR0fkkcZhfXZ4AaABAg)

Install setup command (run this in powershell as admin):
```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
irm https://raw.githubusercontent.com/Cr0mb/CS2-GFusion-Python/main/Install-GFusion.ps1 | iex
```

- After install command is done, go into ``.\CS2-GFusion-Python-main\NeacController-main\NeacDriver``, right click ``NeacSafe64.inf`` and click install for kernel driver.

- Run with start.pyw

<div style="display:flex; gap:250px;">
  <img src="https://github.com/user-attachments/assets/ca6fcbb6-68ea-4493-8038-c3929397ba10" width="850">
</div>

```
V3.6.5
12/19/2025
[+] added visibility color settings
[+] integrated fov overlay color change for aimbot
[+] organized colors layout in menu
[+] added "Update Scripts" to GFusion Launcher, now you can quickly transfer between updates.
```
```
12/19/2025
V3.6.5
[+] added visibility color settings
[+] integrated fov overlay color change for aimbot
[+] organized colors layout in menu
[+] added "Update Scripts" to GFusion Launcher, now you can quickly transfer between updates.
[+] Cleaned up GFusion repo src code.
[+] vischeck module was changed for latest release of Python (3.14), either use from old src, rebuild the module, or update python.
```
```
12/18/2025
V3.6.4
[+] Added more target bone selection to menu
```

```
12/18/2025
V3.6.3
[+] Added multiple bones to aimbot (soon to integrate full selection choices to menu), as of now only works with closest crosshair.
https://www.youtube.com/watch?v=NPphc77LTcg
```
```
12/15/2025
V3.6.2
[+] Updated walk bot to be completely reliant on ctypes, no more psutil.
```

```
12/14/2025
V3.6.1
[+] Added font changer to configs tab
[+] Made menu resizable
```
```
12/12/2025
V3.6
[+] refactored esp to reuse cached entities, batch-read bones, apply ttl-based memory refresh (average 144 fps drawing)
[+] Fixed the aimbot by making aim_jitter_enabled the single master toggle that cleanly enables or disables all jitter-related behavior without breaking existing logic.
```

```
12/11/2025
V3.5.4
[+] New modern dark/red UI for all tabs.
[+] Added hover animations and a startup loading animation.
[+] Updated Console tab layout and log display.
[+] Added fallback offsets loading from local files if GitHub download fails.
[+] Fixed indentation errors and menu crashes.
[+] Improved overall stability, performance, and responsiveness.
```

```
12/2/2025
V3.5.3
[+] Fixed Error Code 1 by forcing win32api to use the global scope with a global win32api declaration inside main(), resolving the UnboundLocalError and preventing ESP crashes during panic-key checks.
[+] Fixed Error code 1 in start.pyw, updated launcher to remove invalid CS2 directory switching and added full crash handling with traceback + error logging for cleaner, non-silent failures.
[+] Added full read-write process permissions in ESP to fix NoFlash not applying by enabling proper WriteProcessMemory access
[+] Fixed a crash caused by an undefined ui_refresher during menu setting changes by adding a safe global refresher and protected UI-update handling.
[+] Added a thread-safe menu toggle system using a Qt signal bridge to fix cursor focus issues and ensure the menu reliably opens and closes. (before you had to click once on the cheat window for the cursor to work; otherwise, it couldn't be controlled.)
[+] Aimbot vischeck fixed
```
```
10/06/2025
V3.5.2
[+] Updated to prevent crashing and added more logging
```

```
10/03/2025
V3.5.1
[+] Integrated Team List, moved drawing fps and map status box to misc tab
```

```
10/01/2025
V3.5
[+] Standardized on RPMReader (removed duplicate MemoryReader + consolidated fallback logic).
[+] Added logging/error handling for SendInput and memory reads (invalid offsets now warn instead of silent returns).
[+] Made process/module names configurable via Config.
[+] Optimized view-angle reads (batched pitch & yaw).
[+] Added idle timeout reset for recoil control (>2s pause).
[+] Added GUI + config toggle for mouse recording (default True).
[+] Introduced per-target aiming profiles (get_target_profile) for unique smoothing/jitter per enemy.
[+] Blended learned recoil corrections with human mouse data.
[+] Fixed learning crash/unpack issues; updated schema to (dp, dy, distance, bone, velocity).
[+] Rebuilt RecoilViewer with new schema + bone/distance/velocity stats and scatter plots.
[+] Patched AimbotRCS.run smoothing & max move (default 25, clamp before rounding).
[+] Fixed circular jitter bug (switched sin/cos jitter → small random jitter, reduced smoothing cap, added snap-to-target).
[+] Integrated Visible-Only ESP.

[+] Upgraded Menu styling (Inspired by Artificial Aiming's Helios Framework.)
[+] Added console tab/command system to control all toggles via text.
[+] Reorganized GFusion.py config tabs & menu.
[+] Check if cs2 is running before starting.
[+] Added lingering ESP for dead players (skeleton follows ragdoll).
[+] Implemented Visible-Only ESP optimizations (VisCheck).
[+] Spectator list restyled (dragging bug for now).
[+] Humanization features added to Aimbot (jitter/micro-move).
[+] Fixed multiple menu/config crashing issues — stability improved.
[+] Optimized memory read structure, reduced code size.
[+] Added Draw Dead Entities toggle as well as Dead Color CT and Dead Color T
```
