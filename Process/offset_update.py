import json
import os
import shutil
import subprocess
import sys
import urllib.request

# === Ensure correct working directory ===
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print(f"[DEBUG] Running in: {os.getcwd()}")

class Offsets:
    @classmethod
    def update_offsets_py(cls):
        try:
            dumper_url = "https://github.com/Cr0mb/CS2-GFusion-Python/releases/download/dumper/cs2-dumper.exe"
            dumper_path = "cs2-dumper.exe"

            if not os.path.exists(dumper_path):
                print("[INFO] Downloading cs2-dumper.exe...")
                urllib.request.urlretrieve(dumper_url, dumper_path)
                print("[INFO] Download complete.")

            # === Step 2: Run cs2-dumper.exe ===
            print("[INFO] Running cs2-dumper.exe...")
            subprocess.run([dumper_path], check=True)
            print("[INFO] cs2-dumper.exe finished.")

            output_dir = "output"
            for file_name in ["offsets.json", "client_dll.json"]:
                src = os.path.join(output_dir, file_name)
                dst = os.path.join(".", file_name)
                if os.path.exists(src):
                    shutil.move(src, dst)
                    print(f"[INFO] Moved {file_name} to current directory.")
                else:
                    raise FileNotFoundError(f"{file_name} not found in {output_dir}")

            with open("offsets.json", "r", encoding="utf-8") as f:
                offset = json.load(f)
            with open("client_dll.json", "r", encoding="utf-8") as f:
                client = json.load(f)

            manual_offsets = {
                "dwEntityList": offset["client.dll"]["dwEntityList"],
                "dwViewMatrix": offset["client.dll"]["dwViewMatrix"],
                "dwLocalPlayerPawn": offset["client.dll"]["dwLocalPlayerPawn"],

                "m_iTeamNum": client["client.dll"]["classes"]["C_BaseEntity"]["fields"]["m_iTeamNum"],
                "m_lifeState": client["client.dll"]["classes"]["C_BaseEntity"]["fields"]["m_lifeState"],
                "m_pGameSceneNode": client["client.dll"]["classes"]["C_BaseEntity"]["fields"]["m_pGameSceneNode"],
                "m_vecAbsOrigin": client["client.dll"]["classes"]["CGameSceneNode"]["fields"]["m_vecAbsOrigin"],

                "m_hPlayerPawn": client["client.dll"]["classes"]["CCSPlayerController"]["fields"]["m_hPlayerPawn"],
                "m_pClippingWeapon": client["client.dll"]["classes"]["C_CSPlayerPawnBase"]["fields"]["m_pClippingWeapon"],
                "m_AttributeManager": client["client.dll"]["classes"]["C_EconEntity"]["fields"]["m_AttributeManager"],
                "m_Item": client["client.dll"]["classes"]["C_AttributeContainer"]["fields"]["m_Item"],
                "m_iItemDefinitionIndex": client["client.dll"]["classes"]["C_EconItemView"]["fields"]["m_iItemDefinitionIndex"],
            }

            all_offsets = {}

            for module_name, offsets_dict in offset.items():
                for offset_name, offset_value in offsets_dict.items():
                    all_offsets[offset_name] = offset_value

            for module_name, module_data in client.items():
                if "classes" not in module_data:
                    continue
                for class_name, class_data in module_data["classes"].items():
                    if "fields" not in class_data:
                        continue
                    for field_name, field_value in class_data["fields"].items():
                        if field_name == "m_modelState" and class_name == "CSkeletonInstance":
                            field_name = "m_pBoneArray"
                            field_value += 128
                        all_offsets[field_name] = field_value

            all_offsets.update(manual_offsets)

            with open("offsets.py", "w", encoding="utf-8") as f:
                f.write("class Offsets:\n")
                if not all_offsets:
                    f.write("    pass\n")
                else:
                    for name in sorted(all_offsets):
                        f.write(f"    {name} = {all_offsets[name]}\n")

            print("[SUCCESS] offsets.py updated successfully.")

            files_to_delete = [
                "cs2-dumper.exe",
                "offsets.json",
                "client_dll.json",
                "cs2-dumper.log"
            ]
            for file in files_to_delete:
                if os.path.exists(file):
                    os.remove(file)
                    print(f"[CLEANUP] Deleted {file}")

            if os.path.exists(output_dir):
                shutil.rmtree(output_dir)
                print(f"[CLEANUP] Removed {output_dir} directory")

        except Exception as e:
            print(f"[ERROR] Failed to update offsets.py: {e}")
            sys.exit(1)


# Run the update
if __name__ == "__main__":
    Offsets.update_offsets_py()
