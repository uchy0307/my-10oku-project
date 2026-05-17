"""step1_load.py
output/<id>_script.json を読込・検証して current.json にコピー
"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
STATE_FILE = OUTPUT_DIR / "state.json"

def main():
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    tid = state.get("currentTopic")
    if not tid:
        print("[step1] no currentTopic in state")
        sys.exit(1)
    src = OUTPUT_DIR / f"{tid}_script.json"
    if not src.exists():
        print(f"[step1] missing {src}")
        sys.exit(1)
    data = json.loads(src.read_text(encoding="utf-8"))
    chapters = data.get("chapters", [])
    if len(chapters) < 5:
        print(f"[step1] WARN: only {len(chapters)} chapters")
    total = sum(len(c.get("body", "")) for c in chapters)
    print(f"[step1] {tid}: {len(chapters)} chapters, total {total} chars")
    cur = OUTPUT_DIR / "current.json"
    cur.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[step1] wrote {cur}")

if __name__ == "__main__":
    main()
