"""
_interrupted_mp4_report.json の破損 mp4 を .work_broken/ に退避。
削除せず移動なので後で分析・復旧可能。
"""
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("C:/Users/user/Documents/10oku-project")
REPORT = ROOT / "scripts/logs/_interrupted_mp4_report.json"

PIPELINE_DIRS = {
    "history_v2":      ROOT / "youtube/history_v2",
    "psych_v2":        ROOT / "youtube/psych_v2",
    "shorts_v2":       ROOT / "youtube/shorts_v2",
    "otona_shorts_v2": ROOT / "youtube/otona_shorts_v2",
}

def main():
    if not REPORT.exists():
        print(f"Report not found: {REPORT}")
        sys.exit(1)
    with open(REPORT, encoding="utf-8") as f:
        data = json.load(f)
    interrupted = data.get("interrupted", [])
    print(f"Quarantining {len(interrupted)} broken mp4 dirs...")

    for item in interrupted:
        pname = item["pipeline"]
        idx = item["idx"]
        base = PIPELINE_DIRS[pname]
        src = base / ".work" / idx
        dst_root = base / ".work_broken"
        dst_root.mkdir(parents=True, exist_ok=True)
        dst = dst_root / idx
        if dst.exists():
            print(f"  SKIP (dst exists): {pname}/{idx}")
            continue
        if not src.exists():
            print(f"  SKIP (src missing): {pname}/{idx}")
            continue
        try:
            shutil.move(str(src), str(dst))
            print(f"  MOVED: {pname}/.work/{idx} -> .work_broken/{idx} (reason={item['reason']}, size={item.get('size_mb','?')}MB)")
        except Exception as e:
            print(f"  ERROR: {pname}/{idx}: {e}")

    print("\nDone.")

if __name__ == "__main__":
    main()
