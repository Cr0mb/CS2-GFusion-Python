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
    OFFSETS_URL = "https://raw.githubusercontent.com/a2x/cs2-dumper/refs/heads/main/output/offsets.json"
    CLIENT_DLL_URL = "https://raw.githubusercontent.com/a2x/cs2-dumper/refs/heads/main/output/client_dll.json"

    OUTPUT_DIR = "output"   # where ExLoader may put fallback DBs

    @classmethod
    def _download_json(cls, url: str, name: str) -> dict:
        """
        Try downloading JSON from GitHub.
        Raise exception if not successful.
        """
        print(f"[INFO] Downloading {name} from {url}")
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Python offsets-updater)"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} while downloading {name}")
                raw = resp.read().decode("utf-8", errors="replace")

            data = json.loads(raw)
            print(f"[INFO] Successfully downloaded {name}")
            return data

        except Exception as e:
            print(f"[WARN] Could not download {name}: {e}")
            raise

    @classmethod
    def _load_local_json(cls, name: str) -> dict:
        """
        Load JSON file from local output/ folder as fallback.
        """
        path = os.path.join(cls.OUTPUT_DIR, name)
        print(f"[INFO] Trying fallback local file: {path}")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Fallback file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                print(f"[INFO] Loaded fallback {name} from disk")
                return data
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Invalid JSON in fallback {name}: {e}")

    @classmethod
    def _get_json_with_fallback(cls, url: str, filename: str) -> dict:
        """
        Try downloading from GitHub.
        If that fails, load from output/ directory.
        """
        try:
            return cls._download_json(url, filename)
        except Exception:
            print(f"[WARN] Download failed, switching to fallback local file for {filename}")

        try:
            return cls._load_local_json(filename)
        except Exception as e:
            print(f"[ERROR] Fallback also failed for {filename}: {e}")
            raise RuntimeError(f"Could not obtain {filename} from any source")

    @classmethod
    def update_offsets_py(cls):
        try:
            # === Core change: This now supports fallback ===
            offset = cls._get_json_with_fallback(cls.OFFSETS_URL, "offsets.json")
            client = cls._get_json_with_fallback(cls.CLIENT_DLL_URL, "client_dll.json")

            # Your existing flatten + output logic remains the same
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

            all_offsets = {}

            # flattening logic from your script
            for module_name, offsets_dict in offset.items():
                if isinstance(offsets_dict, dict):
                    for name, value in offsets_dict.items():
                        all_offsets[name] = value

            for module_name, module_data in client.items():
                if isinstance(module_data, dict):
                    classes = module_data.get("classes", {})
                    for class_name, class_data in classes.items():
                        fields = class_data.get("fields", {})
                        for field_name, field_value in fields.items():
                            if field_name == "m_modelState" and class_name == "CSkeletonInstance":
                                field_name = "m_pBoneArray"
                                field_value += 128
                            all_offsets[field_name] = field_value

            all_offsets.update(manual_offsets)

            # write the final offsets.py
            out_path = os.path.join(script_dir, "offsets.py")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("class Offsets:\n")
                for name in sorted(all_offsets.keys()):
                    f.write(f"    {name} = {all_offsets[name]}\n")

            print(f"[SUCCESS] offsets.py updated successfully at {out_path}")

        except Exception as e:
            print(f"[FATAL] Offsets update failed: {e}")
            sys.exit(1)


# Run updater
if __name__ == "__main__":
    Offsets.update_offsets_py()
