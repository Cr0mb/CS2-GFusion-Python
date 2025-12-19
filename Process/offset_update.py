import json
import sys
import subprocess
import urllib.request
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================
CS2_DUMPER_URL = (
    "https://github.com/a2x/cs2-dumper/releases/download/0.1.3/cs2-dumper.exe"
)
DUMPER_NAME = "cs2-dumper.exe"

# ============================================================
# PATHS (MATCHES YOUR LAYOUT)
# ============================================================
PROCESS_DIR = Path(__file__).resolve().parent           # Process/
OUTPUT_DIR  = PROCESS_DIR / "output"                    # Process/output/
DUMPER_PATH = PROCESS_DIR / DUMPER_NAME                 # Process/cs2-dumper.exe
OFFSETS_PY  = PROCESS_DIR / "offsets.py"

print(f"[DEBUG] Process dir : {PROCESS_DIR}")
print(f"[DEBUG] Output dir  : {OUTPUT_DIR}")

# ============================================================
# HELPERS
# ============================================================
def download_dumper():
    if DUMPER_PATH.exists():
        print("[INFO] cs2-dumper.exe already exists")
        return

    print("[INFO] Downloading cs2-dumper.exe...")
    try:
        with urllib.request.urlopen(CS2_DUMPER_URL, timeout=30) as r:
            data = r.read()
        with open(DUMPER_PATH, "wb") as f:
            f.write(data)
        print("[SUCCESS] cs2-dumper.exe downloaded")
    except Exception as e:
        print(f"[FATAL] Failed to download dumper: {e}")
        sys.exit(1)


def run_dumper():
    print("[INFO] Running cs2-dumper.exe...")
    try:
        subprocess.run(
            [str(DUMPER_PATH)],
            cwd=str(PROCESS_DIR),   # CRITICAL: output goes to Process/output
            check=True,
            timeout=120
        )
    except subprocess.TimeoutExpired:
        print("[FATAL] cs2-dumper.exe timed out")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[FATAL] cs2-dumper.exe failed: {e}")
        sys.exit(1)


def load_json(name: str) -> dict:
    path = OUTPUT_DIR / name
    if not path.exists():
        print(f"[FATAL] Missing {path}")
        sys.exit(1)

    print(f"[INFO] Loading {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ============================================================
# MAIN LOGIC
# ============================================================
def update_offsets():
    OUTPUT_DIR.mkdir(exist_ok=True)

    download_dumper()
    run_dumper()

    offsets = load_json("offsets.json")
    client  = load_json("client_dll.json")

    # ---- manual mappings (UNCHANGED) ----
    manual_offsets = {
        "dwEntityList": offsets["client.dll"]["dwEntityList"],
        "dwViewMatrix": offsets["client.dll"]["dwViewMatrix"],
        "dwLocalPlayerPawn": offsets["client.dll"]["dwLocalPlayerPawn"],

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

    # ---- flatten offsets.json ----
    for _, block in offsets.items():
        if isinstance(block, dict):
            for name, value in block.items():
                all_offsets[name] = value

    # ---- flatten client_dll.json ----
    for module_data in client.values():
        classes = module_data.get("classes", {})
        for class_name, class_data in classes.items():
            fields = class_data.get("fields", {})
            for field_name, field_value in fields.items():
                # Skeleton fix (same logic you already use)
                if field_name == "m_modelState" and class_name == "CSkeletonInstance":
                    field_name = "m_pBoneArray"
                    field_value += 128
                all_offsets[field_name] = field_value

    all_offsets.update(manual_offsets)

    # ---- write offsets.py ----
    with open(OFFSETS_PY, "w", encoding="utf-8") as f:
        f.write("class Offsets:\n")
        for name in sorted(all_offsets):
            f.write(f"    {name} = {all_offsets[name]}\n")

    print(f"[SUCCESS] offsets.py written to {OFFSETS_PY}")

# ============================================================
# ENTRYPOINT
# ============================================================
if __name__ == "__main__":
    update_offsets()
