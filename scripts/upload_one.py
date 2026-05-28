#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upload_one.py — 単一エピソードを動画化＋YouTube投稿
Usage: python upload_one.py --kind history --index 001
       python upload_one.py --kind psych --index 001
"""
import argparse, os, subprocess, sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# Load .env
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

ap = argparse.ArgumentParser()
ap.add_argument("--kind", required=True, choices=["history", "psych", "shorts", "otona_shorts"])
ap.add_argument("--index", required=True)
args = ap.parse_args()

cfg = {
    "history":      ("youtube/history_v2/pipeline.mjs",      "LONG_INDEX"),
    "psych":        ("youtube/psych_v2/pipeline.mjs",        "PSYCH_INDEX"),
    "shorts":       ("youtube/shorts_v2/pipeline.mjs",       "SHORT_INDEX"),
    "otona_shorts": ("youtube/otona_shorts_v2/pipeline.mjs", "OTONA_SHORT_INDEX"),
}[args.kind]

# Map YOUTUBE_CLIENT_ID to NEW_YOUTUBE_CLIENT_ID if pipeline uses that
if not os.environ.get("YOUTUBE_CLIENT_ID") and os.environ.get("NEW_YOUTUBE_CLIENT_ID"):
    os.environ["YOUTUBE_CLIENT_ID"] = os.environ["NEW_YOUTUBE_CLIENT_ID"]

os.environ[cfg[1]] = args.index
print(f"[upload_one] kind={args.kind} index={args.index} env={cfg[1]}={args.index}")

# Preflight 必須通過
preflight = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "preflight.py"),
     "--kind", args.kind, "--index", args.index],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
)
print(preflight.stdout)
if preflight.returncode != 0:
    print("[upload_one] PREFLIGHT FAIL - aborting before ffmpeg")
    print(preflight.stderr)
    # 失敗を messages.json に送信
    import json as _j
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    mp = ROOT / "scripts" / "messages.json"
    try:
        msgs = _j.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        msgs = []
    msgs.append({
        "id": f"preflight_fail_{args.kind}_{args.index}_{int(datetime.now(JST).timestamp())}",
        "ts": datetime.now(JST).isoformat(),
        "title": f"❌ {args.kind} #{args.index} preflight失敗",
        "body": preflight.stdout[-500:] + "\n" + preflight.stderr[-300:],
        "read": False,
        "auto": True,
    })
    mp.write_text(_j.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(2)

r = subprocess.run(["node", cfg[0]], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout[-2000:] if r.stdout else "")
print(r.stderr[-1000:] if r.stderr else "")

# 完了通知を messages.json に書き込む（スマホ表示用）
import json
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))
mp = ROOT / "scripts" / "messages.json"
try:
    msgs = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else []
except Exception:
    msgs = []
# Extract video_url if present
import re
combined = (r.stdout or "") + (r.stderr or "")
m = re.search(r'video_url[=:]\s*(https?://[^\s\n"]+)', combined)
if not m:
    m = re.search(r'(?:^|[\s:])url=(https?://[^\s\n"]+)', combined)
if not m:
    m = re.search(r'(https?://(?:www\.)?youtu(?:be\.com|\.be)/[^\s\n"]+)', combined)
url = m.group(1) if m else None
title_emoji = {"history": "⚔️", "psych": "🧠", "shorts": "⚡", "otona_shorts": "✨"}[args.kind]
if r.returncode == 0 and url:
    msgs.append({
        "id": f"upload_{args.kind}_{args.index}_{int(datetime.now(JST).timestamp())}",
        "ts": datetime.now(JST).isoformat(),
        "title": f"{title_emoji} {args.kind} #{args.index} アップ完了",
        "body": f"視聴確認お願いします:\n{url}\n\n品質チェック観点:\n・音声が最後まで途切れない\n・字幕が音声と合ってる\n・画像が震えない\n・テロップが画面内に収まる\n・サムネ表示OK",
        "read": False,
        "auto": True,
    })
else:
    err_excerpt = (r.stderr or r.stdout or "")[-400:]
    msgs.append({
        "id": f"upload_{args.kind}_{args.index}_fail_{int(datetime.now(JST).timestamp())}",
        "ts": datetime.now(JST).isoformat(),
        "title": f"❌ {args.kind} #{args.index} 失敗",
        "body": f"exit={r.returncode}\n\n{err_excerpt}",
        "read": False,
        "auto": True,
    })
mp.write_text(json.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")
sys.exit(r.returncode)
