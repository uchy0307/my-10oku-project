#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""manual_upload_existing.py
既に .work/{idx}/output.mp4 (+thumbnail.jpg) がある動画を YouTube にアップロードする。
title/description/tags は scripts/{idx}.json から読む。

Usage:
  python manual_upload_existing.py --kind psych --index 001
  python manual_upload_existing.py --kind history --index 015
"""
import argparse, json, os, sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
# Load .env
for line in (ROOT / ".env").read_text(encoding="utf-8-sig", errors="replace").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

ap = argparse.ArgumentParser()
ap.add_argument("--kind", required=True, choices=["history", "psych"])
ap.add_argument("--index", required=True)
args = ap.parse_args()

cfg = {
    "history": {
        "work": ROOT / "youtube" / "history_v2" / ".work" / args.index,
        "script": ROOT / "youtube" / "history_v2" / "scripts" / f"long_{args.index}.json",
        "token_env": "YOUTUBE_REFRESH_TOKEN",
        "category": "27",  # Education
    },
    "psych": {
        "work": ROOT / "youtube" / "psych_v2" / ".work" / args.index,
        "script": ROOT / "youtube" / "psych_v2" / "scripts" / f"psych_{args.index}.json",
        "token_env": "OTONA_YOUTUBE_REFRESH_TOKEN",
        "category": "27",
    },
}[args.kind]

mp4 = cfg["work"] / "output.mp4"
thumb = cfg["work"] / "thumbnail.jpg"
if not mp4.exists():
    print(f"FATAL: {mp4} not found", file=sys.stderr)
    sys.exit(2)

script_data = json.loads(cfg["script"].read_text(encoding="utf-8"))
title = (script_data.get("title") or "").strip()
description = (script_data.get("description") or "").strip()
tags = script_data.get("tags") or []
if not title:
    print("FATAL: title missing", file=sys.stderr)
    sys.exit(2)

# OAuth
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
except ImportError:
    print("FATAL: pip install google-auth google-api-python-client", file=sys.stderr)
    sys.exit(3)

cid = os.environ.get("YOUTUBE_CLIENT_ID")
csec = os.environ.get("YOUTUBE_CLIENT_SECRET")
rtoken = os.environ.get(cfg["token_env"])
if not (cid and csec and rtoken):
    print(f"FATAL: missing env (need YOUTUBE_CLIENT_ID/_SECRET/{cfg['token_env']})", file=sys.stderr)
    sys.exit(2)

creds = Credentials(
    None, refresh_token=rtoken,
    client_id=cid, client_secret=csec,
    token_uri="https://oauth2.googleapis.com/token",
)
creds.refresh(Request())
yt = build("youtube", "v3", credentials=creds)

# Check duplicate
ch = yt.channels().list(part="contentDetails", mine=True).execute()
uploads_pl = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
existing = set()
page = None
while True:
    res = yt.playlistItems().list(
        part="snippet", playlistId=uploads_pl, maxResults=50, pageToken=page
    ).execute()
    for it in res.get("items", []):
        existing.add(it["snippet"]["title"])
    page = res.get("nextPageToken")
    if not page or len(existing) > 200:
        break

upload_title = title
if title in existing:
    # 重複避けのためサフィックス付与
    from datetime import datetime, timezone, timedelta
    jst = datetime.now(timezone(timedelta(hours=9)))
    suffix = f" ({jst.strftime('%m/%d')}再)"
    upload_title = (title[:100 - len(suffix)] + suffix).strip()
    print(f"[manual_upload] title duplicate, using: {upload_title}")

print(f"[manual_upload] uploading {mp4} ({mp4.stat().st_size/1024/1024:.1f}MB)")
body = {
    "snippet": {
        "title": upload_title[:100],
        "description": description[:4500],
        "tags": tags[:15],
        "categoryId": cfg["category"],
    },
    "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
}
media = MediaFileUpload(str(mp4), mimetype="video/mp4", resumable=True)
req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
resp = None
while resp is None:
    status, resp = req.next_chunk()
    if status:
        print(f"  upload {int(status.progress()*100)}%")
video_id = resp["id"]
url = f"https://youtube.com/watch?v={video_id}"
print(f"video_url={url}")

if thumb.exists():
    try:
        yt.thumbnails().set(videoId=video_id, media_body=str(thumb)).execute()
        print("thumbnail set")
    except Exception as e:
        print(f"thumbnail set failed (non-fatal): {e}")

# Post to messages.json
from datetime import datetime, timezone, timedelta
import json as _j
jst = timezone(timedelta(hours=9))
mp = ROOT / "scripts" / "messages.json"
try:
    msgs = _j.loads(mp.read_text(encoding="utf-8"))
except Exception:
    msgs = []
emoji = "⚔️" if args.kind == "history" else "🧠"
msgs.append({
    "id": f"manual_upload_{args.kind}_{args.index}_{int(datetime.now(jst).timestamp())}",
    "ts": datetime.now(jst).isoformat(),
    "title": f"{emoji} {args.kind} #{args.index} 手動アップ完了",
    "body": f"{url}\n\nタイトル: {upload_title}",
    "read": False,
    "auto": True,
})
mp.write_text(_j.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")
print("done")
