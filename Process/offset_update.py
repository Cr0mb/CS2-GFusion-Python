import json
import os
import sys
import urllib.request
import urllib.error

# === Ensure correct working directory ===
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print(f"[DEBUG] Running in: {os.getcwd()}")


class Offsets:
    # Raw GitHub URLs for latest CS2 dumper output
    OFFSETS_URL = "https://raw.githubusercontent.com/a2x/cs2-dumper/refs/heads/main/output/offsets.json"
    CLIENT_DLL_URL = "https://raw.githubusercontent.com/a2x/cs2-dumper/refs/heads/main/output/client_dll.json"

    @classmethod
    def _download_json(cls, url: str, name: str) -> dict:
        """
        Download JSON from the given URL and return it as a Python dict.
        """
        print(f"[INFO] Downloading {name} from {url}")
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Python offsets-updater)"
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} while downloading {name}")
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error while downloading {name}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error while downloading {name}: {e}") from e

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse JSON for {name}: {e}") from e

        print(f"[INFO] Successfully downloaded and parsed {name}")
        return data

    @classmethod
    def update_offsets_py(cls):
        try:
            # 1) Download the latest JSON blobs directly from GitHub
            offset = cls._download_json(cls.OFFSETS_URL, "offsets.json")
            client = cls._download_json(cls.CLIENT_DLL_URL, "client_dll.json")

            # 2) Manual offsets you explicitly care about (stable names)
            manual_offsets = {
                "dwEntityList": offset["client.dll"]["dwEntityList"],
                "dwViewMatrix": offset["client.dll"]["dwViewMatrix"],
                "dwLocalPlayerPawn": offset["client.dll"]["dwLocalPlayerPawn"],

                "m_iTeamNum": client["client.dll"]["classes"]["C_BaseEntity"]["fields"]["m_iTeamNum"],
                "m_lifeState": client["client.dll"]["classes"]["C_BaseEntity"]["fields"]["m_lifeState"],
                "m_pGameSceneNode": client["client.dll"]["classes"]["C_BaseEntity"]["fields"]["m_pGameSceneNode"],
                "m_vecAbsOrigin": client["client.dll"]["classes"]["CGameSceneNode"]["fields"]["m_vecAbsOrigin"],

                "m_hPlayerPawn": client["client.dll"]["classes"]["CCSPlayerController"]["fields"]["m_hPlayerPawn"],
                "m_AttributeManager": client["client.dll"]["classes"]["C_EconEntity"]["fields"]["m_AttributeManager"],
                "m_Item": client["client.dll"]["classes"]["C_AttributeContainer"]["fields"]["m_Item"],
                "m_iItemDefinitionIndex": client["client.dll"]["classes"]["C_EconItemView"]["fields"]["m_iItemDefinitionIndex"],
            }

            # 3) Flatten everything into one big dict
            all_offsets = {}

            # 3a) From offsets.json (top-level is modules, e.g. "client.dll")
            for module_name, offsets_dict in offset.items():
                if not isinstance(offsets_dict, dict):
                    continue
                for offset_name, offset_value in offsets_dict.items():
                    all_offsets[offset_name] = offset_value

            # 3b) From client_dll.json (classes/fields)
            for module_name, module_data in client.items():
                if not isinstance(module_data, dict):
                    continue
                classes = module_data.get("classes")
                if not isinstance(classes, dict):
                    continue

                for class_name, class_data in classes.items():
                    fields = class_data.get("fields")
                    if not isinstance(fields, dict):
                        continue

                    for field_name, field_value in fields.items():
                        # Special-case: m_modelState in CSkeletonInstance -> m_pBoneArray + 128
                        if field_name == "m_modelState" and class_name == "CSkeletonInstance":
                            field_name = "m_pBoneArray"
                            field_value = field_value + 128

                        all_offsets[field_name] = field_value

            # 3c) Ensure manual offsets override anything else
            all_offsets.update(manual_offsets)

            # 4) Emit offsets.py
            output_path = os.path.join(script_dir, "offsets.py")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("class Offsets:\n")
                if not all_offsets:
                    f.write("    pass\n")
                else:
                    for name in sorted(all_offsets):
                        f.write(f"    {name} = {all_offsets[name]}\n")

            print(f"[SUCCESS] offsets.py updated successfully at {output_path}")

        except Exception as e:
            print(f"[ERROR] Failed to update offsets.py: {e}")
            sys.exit(1)


# Run the update
if __name__ == "__main__":
    Offsets.update_offsets_py()
