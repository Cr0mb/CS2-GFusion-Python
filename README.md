GFusion is a fully external Python-based cheat framework for Counter-Strike 2. It is built using ctypes, win32api, and PyQt5. It does not rely on any common cheat libraries like pymem or pyMeow.


<img width="1169" height="711" alt="image" src="https://github.com/user-attachments/assets/23a2e07d-5be0-4e09-b749-3458e048dd68" />

For active support & community join the discord: https://discord.gg/qKfmaA7FFJ

**Donate:** https://paypal.me/GHaxLegit?country.x=US&locale.x=en_US

**Videos**  
[**GFusion V1**](https://www.youtube.com/watch?v=vk7iz4ZaDlY)  
[**GFusion V1.2**](https://www.youtube.com/watch?v=qhYLK4H8oOQ)  
[**GFusion V1.5**](https://www.youtube.com/watch?v=nFDo0aIdPoE)  
[**GFusion V2**](https://www.youtube.com/watch?v=e3C_HtMf_DY)  
[**GFusion V2.1**](https://www.youtube.com/watch?v=YCy9dLPZ3qg)  
[**GFusion V2.1**](https://www.youtube.com/watch?v=YCy9dLPZ3qg)  
[**GFusion V2.2**](https://www.youtube.com/watch?v=JXbsdEL282s)  
[**GFusion V2.3**](https://www.youtube.com/watch?v=Bz0EKTYXF2k)<br>
[**GFusion V2.5**](https://www.youtube.com/watch?v=ZjwLNJX-leY)


```markdown
V2.2 8/4/2025
- Added OBS Proof for Screen Capture
```

```markdown
V2.3 8/4/2025
- Made menu OBS Proof for Screen Capture
```

```markdown
V2.4 8/6/2025
- Added walkbot
- Update offset_update.py to use https://www.unknowncheats.me/forum/counter-strike-2-a/711462-updated-cs2-dumper.html
```

```markdown
V2.5 8/8/2025
- Tried to make some performance improvements to ESP overlay
- Tried to make some performance improvements to Aimbot
- Added player info box (shows all players info in match)
- Added show drawing FPS for overlay

- Changed GDI Windows Overlay to be DirectX11 instead (Huge performance boost in visuals!)
```


# GFusion Feature List

<details>
<summary><strong>Watermark</strong></summary>

- Watermark Toggle

</details>

<details>
<summary><strong>ESP Features</strong></summary>

- OBS Proof - only works on Windows 10 build 1903+ (2019 or later)  
- Box ESP  
- Healthbar ESP  
- Armorbar ESP  
- Health Text ESP  
- Armor Text ESP  
- Flash Effect ESP  
- Scope Effect ESP  
- Skeleton ESP  
- Head ESP  
- Bone Dot ESP  
- Line ESP  
- Distance ESP  
- Name ESP  
- Weapon ESP  
- Bomb ESP  
- Money ESP  
- Spectator List  
- Velocity ESP  
- Speed ESP  
- Velocity Text ESP  
- Coordinates ESP  
- Trace ESP (with max point limit)  
- Team Filter (Enemies Only / Team Only)

</details>

<details>
<summary><strong>Local Info Box</strong></summary>

- Local Info Box Toggle  
- Background Color  
- Border Color  
- Velocity Text Color  
- Speed Text Color  
- Coordinate Text Color

</details>

<details>
<summary><strong>Aimbot & Recoil Control System (RCS)</strong></summary>

- Aimbot Enabled  
- Aim Key  
- Target Bone (name or list of bone indices)  
- Closest to Crosshair Targeting  
- Entity Cap  
- FOV Angle  
- Max Delta Angle  
- Target Switch Delay  
- Aim Start Delay  
- Downward Offset  
- DeathMatch Mode  

- Learning Mode  
- Learn Directory  
- Velocity Prediction Toggle  
- Velocity Prediction Factor  

- Smooth Base & Variation  
- Sensitivity  
- Invert Y-Axis  
- Max Mouse Move Limit  

- RCS Toggle  
- RCS Scale  
- RCS Smooth Base & Variation

</details>

<details>
<summary><strong>FOV Overlay</strong></summary>

- FOV Circle Toggle  
- Crosshair Toggle

</details>

<details>
<summary><strong>Misc Visuals</strong></summary>

- Grenade Prediction  
- NoFlash Effect Toggle

</details>

<details>
<summary><strong>Glow ESP</strong></summary>

- Glow Toggle  
- Show Enemies / Team  
- Enemy / Team Glow Colors

</details>

<details>
<summary><strong>TriggerBot</strong></summary>

- TriggerBot Enabled  
- Trigger Key  
- Cooldown  
- Shoot Teammates  
- Always On Toggle

</details>

<details>
<summary><strong>Auto Pistol</strong></summary>

- Auto Pistol Toggle  
- Activation Key  
- Fire Rate

</details>

<details>
<summary><strong>FOV Changer</strong></summary>

- FOV Changer Toggle  
- Custom Game FOV

</details>

<details>
<summary><strong>Bunny Hop (BHop)</strong></summary>

- Bunny Hop Toggle  
- AutoStrafe

</details>

<details>
<summary><strong>WalkBot</strong></summary>

- WalkBot Toggle  

</details>

<details>
<summary><strong>Menu GUI</strong></summary>

- Toggle Key: Insert

</details>

<details>
<summary><strong>ESP Customization & Color Settings</strong></summary>

- Crosshair Size & Color  
- Head ESP Size, Shape & Color  
- Bone Dot Size, Shape & Color  
- Line ESP Position & Color  
- Box ESP Color (T / CT)  
- Bone Lines Color  
- Healthbar / Armorbar Colors  
- Health / Armor Text Colors  
- Name ESP Text & Effects Color  
- Distance ESP Text Color  
- Flash / Scope Effect Colors  
- Spectator List Color  
- Weapon ESP Text Color  
- FOV Overlay Color  
- Trace ESP Color  
- Velocity ESP & Text Colors  
- Speed ESP Text Color  
- Coordinates ESP Text Color  
- Money ESP Text Color

</details>






## Installation

**How to Install:** https://www.youtube.com/watch?v=YJKS5BE3d5c

1. Install required dependencies:
```
pip install pillow PyQt5 comtypes cryptography keyboard matplotlib psutil requests pywin32
````

2. Run the launcher:

```
python start.pyw
```

3. Press `Insert` to open or close the GUI while CS2 is running.

This script must be run with administrator rights. The game must be running before you start the script.
If menu doesn't show you may need to disable anti-virus.

---

## Security and Optimization

* No third-party memory libraries
* External overlay rendering
* Designed for USB-bound execution (not necessary)
