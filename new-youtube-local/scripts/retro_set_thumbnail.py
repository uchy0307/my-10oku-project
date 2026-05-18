"""retro_set_thumbnail.py
Standalone: set custom thumbnail on existing YouTube video (Otona channel).
Usage: python retro_set_thumbnail.py --video-id=XXX --thumb-path=path/to/thumb.png
"""
import os, sys, json, argparse
from pathlib import Path
import urllib.request, urllib.parse, urllib.error

CLIENT_ID = os.environ.get("NEW_YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NEW_YOUTUBE_CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("NEW_YOUTUBE_REFRESH_TOKEN", "")


def get_access_token():
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data, headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.loads(r.read().decode("utf-8"))
        return body["access_token"]


def set_thumbnail(access_token, video_id, thumb_path):
    p = Path(thumb_path)
    ctype = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    data = p.read_bytes()
    print(f"[retro_thumb] uploading {p.name} ({len(data)} bytes, {ctype}) for video {video_id}")
    url = f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}&uploadType=media"
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": ctype,
            "Content-Length": str(len(data)),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read().decode("utf-8")
            print(f"[retro_thumb] HTTP {r.status} response: {body[:600]}")
            return body
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="ignore")
        print(f"[retro_thumb] HTTPError {e.code}: {msg[:600]}")
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", required=True)
    ap.add_argument("--thumb-path", required=True)
    args = ap.parse_args()
    if not (CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN):
        print("[retro_thumb] ABORT: NEW_YOUTUBE_* env missing")
        sys.exit(1)
    if not Path(args.thumb_path).exists():
        print(f"[retro_thumb] ABORT: thumb file not found: {args.thumb_path}")
        sys.exit(1)
    token = get_access_token()
    print(f"[retro_thumb] access token obtained, setting thumb for {args.video_id}")
    set_thumbnail(token, args.video_id, args.thumb_path)
    print("[retro_thumb] DONE")


if __name__ == "__main__":
    main()

