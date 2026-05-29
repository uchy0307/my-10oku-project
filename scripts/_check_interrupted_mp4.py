"""
.work/<idx>/output.mp4 の duration と整合性を一括検査。
中断 mp4 (< 期待値 or 破損) を検出して quarantine 候補リスト出力。

期待 duration:
- history_v2: >= 1800s (30分以上)
- psych_v2:   >= 1100s (約18分以上, 5/29引き継ぎ書で制限緩和)
- shorts_v2:  60s 前後 (ショート)
- otona_shorts_v2: 60s 前後
"""
import sys
import json
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("C:/Users/user/Documents/10oku-project")
PIPELINES = {
    "history_v2":       {"work": ROOT / "youtube/history_v2/.work",       "min_dur": 1800, "kind": "long"},
    "psych_v2":         {"work": ROOT / "youtube/psych_v2/.work",         "min_dur": 1100, "kind": "long"},
    "shorts_v2":        {"work": ROOT / "youtube/shorts_v2/.work",        "min_dur":   30, "kind": "short"},
    "otona_shorts_v2":  {"work": ROOT / "youtube/otona_shorts_v2/.work",  "min_dur":   30, "kind": "short"},
}

def get_duration(mp4_path: Path) -> float | None:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(mp4_path)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            return None
        return float(r.stdout.strip())
    except Exception:
        return None

def main():
    summary = {}
    interrupted = []  # candidates to quarantine
    for pname, cfg in PIPELINES.items():
        work = cfg["work"]
        min_dur = cfg["min_dur"]
        if not work.exists():
            continue
        rows = []
        for idx_dir in sorted(work.iterdir()):
            if not idx_dir.is_dir():
                continue
            mp4 = idx_dir / "output.mp4"
            if not mp4.exists():
                rows.append({"idx": idx_dir.name, "status": "NO_MP4"})
                continue
            size_mb = mp4.stat().st_size / (1024 * 1024)
            dur = get_duration(mp4)
            if dur is None:
                rows.append({"idx": idx_dir.name, "status": "CORRUPT", "size_mb": round(size_mb, 1)})
                interrupted.append({"pipeline": pname, "idx": idx_dir.name, "reason": "ffprobe_fail", "size_mb": round(size_mb, 1)})
            elif dur < min_dur:
                rows.append({"idx": idx_dir.name, "status": "SHORT", "size_mb": round(size_mb, 1), "dur_s": round(dur, 1), "min": min_dur})
                interrupted.append({"pipeline": pname, "idx": idx_dir.name, "reason": "under_min_duration", "dur_s": round(dur, 1), "min": min_dur, "size_mb": round(size_mb, 1)})
            else:
                rows.append({"idx": idx_dir.name, "status": "OK", "size_mb": round(size_mb, 1), "dur_s": round(dur, 1)})
        summary[pname] = {
            "total": len(rows),
            "ok":      len([r for r in rows if r["status"] == "OK"]),
            "no_mp4":  len([r for r in rows if r["status"] == "NO_MP4"]),
            "short":   len([r for r in rows if r["status"] == "SHORT"]),
            "corrupt": len([r for r in rows if r["status"] == "CORRUPT"]),
            "rows": rows,
        }

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for pname, s in summary.items():
        print(f"\n[{pname}] total={s['total']} ok={s['ok']} no_mp4={s['no_mp4']} short={s['short']} corrupt={s['corrupt']}")

    print("\n" + "=" * 60)
    print(f"INTERRUPTED CANDIDATES ({len(interrupted)})")
    print("=" * 60)
    for item in interrupted:
        print(json.dumps(item, ensure_ascii=False))

    # Save detailed report
    out_path = ROOT / "scripts/logs/_interrupted_mp4_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "interrupted": interrupted}, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved: {out_path}")

if __name__ == "__main__":
    main()
