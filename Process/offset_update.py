import json
import sys
import os
import urllib.request

class Offsets:
    @classmethod
    def update_offsets_py(cls):
        try:
            # URLs for the JSON files
            urls = {
                "offsets.json": "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/offsets.json",
                "client_dll.json": "https://raw.githubusercontent.com/a2x/cs2-dumper/main/output/client_dll.json"
            }

            # Download the JSON files
            for filename, url in urls.items():
                print(f"[*] Downloading {filename}...")
                urllib.request.urlretrieve(url, filename)

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

            script_dir = os.path.dirname(os.path.abspath(__file__))
            offsets_path = os.path.join(script_dir, "offsets.py")

            with open(offsets_path, "w", encoding="utf-8") as f:
                f.write("class Offsets:\n")
                if not all_offsets:
                    f.write("    pass\n")
                else:
                    for name in sorted(all_offsets):
                        f.write(f"    {name} = {all_offsets[name]}\n")


            print("[*] offsets.py updated successfully.")

        except Exception as e:
            print(f"[!] Failed to update offsets.py: {e}")
            sys.exit(1)
        finally:
            for filename in ["offsets.json", "client_dll.json"]:
                if os.path.exists(filename):
                    try:
                        os.remove(filename)
                        print(f"[*] Deleted temporary file: {filename}")
                    except Exception as e:
                        print(f"[!] Failed to delete {filename}: {e}")

# Run the update
Offsets.update_offsets_py()
