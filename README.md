## GFusion V3.5
[Discord](https://discord.gg/qKfmaA7FFJ)
[UC Forum](https://www.unknowncheats.me/forum/counter-strike-2-releases/711867-gfusion-closet-cheat.html)
[YouTube](https://www.youtube.com/@cr0mble)

[How to Download and Install GFusion V3.5](https://www.youtube.com/watch?v=HJDb8FdCeRc)

Install setup command (run this in powershell as admin):
```
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
irm https://raw.githubusercontent.com/Cr0mb/CS2-GFusion-Python/main/Install-GFusion.ps1 | iex
```

<div style="display:flex; gap:250px;">
  <img src="https://github.com/user-attachments/assets/26e1cd67-c1d9-4c3a-8c1a-97f980a3164b" width="850">
  <img src="https://github.com/user-attachments/assets/c5287c42-4d42-497f-8add-707a9b0a9bd7" width="400">
  <img src="https://github.com/user-attachments/assets/5422206b-5e99-4497-8284-06e0964a9578" width="400">
  <img src="https://github.com/user-attachments/assets/620b5cc3-7fec-4b8b-b059-0c7dc340b583" width="300">
  <img src="https://github.com/user-attachments/assets/50c77cf5-43c9-4b74-9b13-95f07ab8dc59" width="300">
  <img src="https://github.com/user-attachments/assets/1dc3afb2-6134-4f37-bc8b-2b41de7f6844" width="300">
  <img src="https://github.com/user-attachments/assets/ccf09df8-0b85-46f3-bdc9-d33a1461ebac" width="300">
</div>


```
2025-09-30
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
