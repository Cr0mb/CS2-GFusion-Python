
<img width="967" height="719" alt="image" src="https://github.com/user-attachments/assets/c6802529-8909-431a-b3ef-a35535f2597e" />

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
