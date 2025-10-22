# show_velocity.py
# Requires: esp.py (same folder). Reads the first entity returned by esp.get_entities()
# and prints its velocity (x,y,z) and speed in u/s continuously.

import time
import math
import ctypes
from ctypes import wintypes, byref

import esp  # your esp.py (must be in same folder)

def main(poll_hz=5.0):
    # find CS2 window
    hwnd = ctypes.windll.user32.FindWindowW(None, "Counter-Strike 2")
    if not hwnd:
        print("[!] Counter-Strike 2 window not found. Start the game and try again.")
        return

    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, byref(pid))
    if not pid.value:
        print("[!] Couldn't get PID from window.")
        return

    # open process (read-only)
    PROCESS_PERMISSIONS = getattr(esp, "PROCESS_PERMISSIONS", 0x0010)
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_PERMISSIONS, False, pid.value)
    if not handle:
        print(f"[!] OpenProcess failed for PID {pid.value}.")
        return

    # get client.dll base (uses Overlay's helper which exists in esp)
    try:
        overlay = esp.Overlay("tmp_show_velocity", fps=1)
        base = overlay.get_module_base(pid.value, "client.dll")
    except Exception as e:
        print("[!] Failed to get module base:", e)
        base = None

    if not base:
        print("[!] client.dll base not found. Exiting.")
        return

    print(f"[+] Attached to PID {pid.value}, client.dll base = 0x{base:x}")
    poll_interval = 1.0 / max(0.1, poll_hz)

    try:
        while True:
            # Use your esp.get_entities() to enumerate entities (it returns Entity objects)
            ents = esp.get_entities(handle, base)
            if not ents:
                print("[*] No entities found (or not in-game). Retrying...")
            else:
                first = ents[0]  # first entity returned by your function
                # Make sure data is fresh
                first.read_data()

                # Safe read velocity vector from pawn + offset
                try:
                    vel = esp.read_vec3(handle, first.pawn + esp.Offsets.m_vecVelocity)
                except Exception as e:
                    print("[!] read_vec3 failed:", e)
                    vel = esp.Vec3(0.0, 0.0, 0.0)

                speed = math.sqrt(vel.x * vel.x + vel.y * vel.y + vel.z * vel.z)
                print(f"[{time.strftime('%H:%M:%S')}] Entity pawn=0x{first.pawn:x} | "
                      f"V = ({vel.x:.2f}, {vel.y:.2f}, {vel.z:.2f}) u/s | Speed = {speed:.2f} u/s | Name='{getattr(first, 'name', 'unknown')}'")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[+] Stopped by user.")
    finally:
        try:
            ctypes.windll.kernel32.CloseHandle(handle)
        except:
            pass

if __name__ == "__main__":
    main(poll_hz=5.0)
