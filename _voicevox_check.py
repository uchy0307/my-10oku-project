"""Quick VOICEVOX reachability check."""
import urllib.request, urllib.error, json
from pathlib import Path
OUT = Path(r"C:\Users\user\Documents\10oku-project") / "_voicevox_check.txt"
try:
    with urllib.request.urlopen("http://localhost:50021/version", timeout=5) as r:
        v = r.read().decode("utf-8")
    with urllib.request.urlopen("http://localhost:50021/speakers", timeout=10) as r:
        spk = json.loads(r.read().decode("utf-8"))
    names = [s.get("name") for s in spk]
    OUT.write_text(f"VOICEVOX OK: version={v.strip()} speakers={len(names)} names={names[:10]}\n", encoding="utf-8")
except Exception as e:
    OUT.write_text(f"VOICEVOX UNREACHABLE: {e}\n", encoding="utf-8")
