"""step5_upload.py
YouTube Data API v3 で動画アップロード
- refresh_token 方式（OAuth2）
- NEW_YOUTUBE_CLIENT_ID / _SECRET / _REFRESH_TOKEN を流用
- title / description / tags は current.json から組立
- --test 時は upload せず情報のみ表示
"""
import os, sys, json, time
from pathlib import Path
import urllib.request, urllib.parse, urllib.error

ROOT = Path(__file__).resolve().parent.parent

# Auto-load .env (when run standalone)
_ENV = ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _k = _k.strip(); _v = _v.strip()
        if _k and _k not in os.environ:
            os.environ[_k] = _v

OUTPUT_DIR = ROOT / "output"

CLIENT_ID = os.environ.get("NEW_YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NEW_YOUTUBE_CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("NEW_YOUTUBE_REFRESH_TOKEN", "")
CATEGORY_ID = os.environ.get("YOUTUBE_CATEGORY_ID", "22")
PRIVACY = os.environ.get("YOUTUBE_PRIVACY", "public")

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

def build_metadata(cur):
    title = f"【大人の心理学】{cur['title']}"
    if len(title) > 95:
        title = title[:95]
    desc_lines = [
        f"テーマ: {cur['title']}",
        f"カテゴリ: {cur['category']}",
        "",
        "本動画は心理学的視点から大人の恋愛・対人関係・性愛心理を考察します。",
        "視聴は18歳以上を推奨。",
        "",
        "■章立て",
    ]
    for c in cur["chapters"]:
        desc_lines.append(f"  {c['title']}")
    desc_lines += [
        "",
        "#大人の心理学 #恋愛心理 #otona_no_psychology",
    ]
    description = "\n".join(desc_lines)
    tags = ["大人の心理学", "心理学", "恋愛心理", "otona_no_psychology", cur["category"]]
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_ID,
            "defaultLanguage": "ja",
            "defaultAudioLanguage": "ja",
        },
        "status": {
            "privacyStatus": PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }

def resumable_upload(access_token, video_path, metadata):
    init_req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(metadata).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
        },
        method="POST",
    )
    with urllib.request.urlopen(init_req, timeout=60) as r:
        upload_url = r.headers.get("Location")
    if not upload_url:
        raise RuntimeError("no upload URL")
    with open(video_path, "rb") as f:
        body = f.read()
    put_req = urllib.request.Request(
        upload_url, data=body,
        headers={"Content-Type": "video/mp4", "Content-Length": str(len(body))},
        method="PUT",
    )
    with urllib.request.urlopen(put_req, timeout=1800) as r:
        result = json.loads(r.read().decode("utf-8"))
    vid = result.get("id", "")
    ch_id = (result.get("snippet") or {}).get("channelId", "")
    return vid, ch_id


def fetch_channel_id(access_token):
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=id&mine=true",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        items = data.get("items", [])
        if items:
            return items[0].get("id", "")
    except Exception as e:
        print(f"[step5] fetch_channel_id failed: {e}")
    return ""


def set_thumbnail(access_token, video_id, thumb_path):
    ctype = "image/png" if thumb_path.suffix.lower() == ".png" else "image/jpeg"
    data = thumb_path.read_bytes()
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
            res = json.loads(r.read().decode("utf-8"))
        print(f"[step5] thumbnail set: {json.dumps(res)[:200]}"