<img width="1169" height="711" alt="image" src="https://github.com/user-attachments/assets/041e5b72-3454-4b4b-851c-cf8a6e9eb0c8" />


# GFusion-CS2-Cheat

GFusion is a fully external Python-based cheat framework for Counter-Strike 2. It is built using ctypes, win32api, and PyQt5. It does not rely on any common cheat libraries like pymem or pyMeow.

---

# GFusion Feature List

<details>
<summary><strong>Watermark</strong></summary>

- Watermark Toggle

</details>

<details>
<summary><strong>ESP Features</strong></summary>

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
<summary><strong>ESP Customization</strong></summary>

- Crosshair Size  
- Head ESP Size & Shape  
- Bone Dot Size & Shape  
- Line ESP Position

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
<summary><strong>Aimbot</strong></summary>

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

</details>

<details>
<summary><strong>Aimbot Prediction</strong></summary>

- Learning Mode  
- Learn Directory  
- Velocity Prediction Toggle  
- Velocity Prediction Factor

</details>

<details>
<summary><strong>Aimbot Smooth & Sensitivity</strong></summary>

- Smooth Base & Variation  
- Sensitivity  
- Invert Y-Axis  
- Max Mouse Move Limit

</details>

<details>
<summary><strong>Recoil Control System (RCS)</strong></summary>

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
<summary><strong>Menu GUI</strong></summary>

- Toggle Key: Insert

</details>

<details>
<summary><strong>Color Settings</strong></summary>

- Box (T / CT)  
- Bone Lines  
- Head ESP  
- Bone Dots  
- Healthbar / Armorbar  
- Health / Armor Text  
- Name ESP Text / Effects  
- Distance Text  
- Flash / Scope Effects  
- Spectator List  
- Weapon Text  
- FOV Overlay  
- Crosshair  
- Trace ESP  
- Velocity ESP / Text  
- Speed ESP  
- Coordinates ESP  
- Money Text

</details>



## Installation

1. Install required dependencies:
```
pip install pyqt5 matplotlib pywin32 keyboard requests
````

2. Run the launcher:

```
python start.pyw
```

3. Press `Insert` to open or close the GUI while CS2 is running.

This script must be run with administrator rights. The game must be running before you start the script.

---

## Security and Optimization

* No third-party memory libraries
* External overlay rendering with PyQt5
* Designed for USB-bound execution
* HWID and IP validation supported
* Supports anti-debug and basic auth logic

---

## Disclaimer

This software is provided for research and educational purposes only. Using it on protected servers may result in bans. The author is not responsible for misuse.

---

## Author

Created by cr0mb
GitHub: [github.com/cr0mb](https://github.com/cr0mb)
