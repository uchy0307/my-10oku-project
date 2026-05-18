"""set_thumb_for_video.py
既存 YouTube 動画 (video_id) に Gemini 生成サムネを後追い set する。

usage:
  python scripts/set_thumb_for_video.py <video_id>

手順:
 1. YouTube Data API v3 videos.list で snippet (title, description, channelId) 取得
 2. step3b_thumbnail のロジックで Gemini Imagen + Pillow タイトル焼込みで PNG 生成
 3. step5_upload.set_thumbnail で thumbnails.set
"""
import os, sys, json, time
from pathlib import Path
import urllib.request, urllib.parse, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
sys.path.insert(0, str(ROOT / "scripts"))

# .env loader
ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() and k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip()

CLIENT_ID = os.environ.get("NEW_YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NEW_YOUTUBE_CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("NEW_YOUTUBE_REFRESH_TOKEN", "")


def get_access_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))["access_token"]


def fetch_video_snippet(access_token: str, video_id: str) -> dict:
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    items = d.get("items", [])
    if not items:
        raise RuntimeError(f"video not found: {video_id}")
    sn = items[0]["snippet"]
    return {
        "id": video_id,
        "title": sn.get("title", ""),
        "channelId": sn.get("channelId", ""),
        "channelTitle": sn.get("channelTitle", ""),
        "description": sn.get("description", ""),
        "tags": sn.get("tags", []),
    }


def infer_category(title: str, tags: list) -> str:
    txt = (title + " " + " ".join(tags)).lower()
    if any(w in title for w in ["既婚", "恋愛", "恋人", "ロマンス"]):
        return "恋愛心理"
    if any(w in title for w in ["性", "セックス", "セクシュアル"]):
        return "性愛心理"
    if any(w in title for w in ["暗黒", "闇", "ダーク"]):
        return "暗黒心理"
    return "恋愛心理"


def main():
    if len(sys.argv) < 2:
        print("usage: python set_thumb_for_video.py <video_id>")
        sys.exit(2)
    video_id = sys.argv[1].strip()
    print(f"[set_thumb] video_id={video_id}")

    if not (CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN):
        print("[set_thumb] FATAL: NEW_YOUTUBE_* env not set")
        sys.exit(1)

    print("[set_thumb] get_access_token …")
    token = get_access_token()

    print("[set_thumb] fetch video snippet …")
    sn = fetch_video_snippet(token, video_id)
    title = sn["title"]
    # ナレ用に「【大人の心理学】」prefix を剥がす
    clean_title = title
    for pfx in ("【大人の心理学】", "[大人の心理学]", "【大人心理学】"):
        if clean_title.startswith(pfx):
            clean_title = clean_title[len(pfx):]
            break
    category = infer_category(clean_title, sn.get("tags", []))
    print(f"[set_thumb] title='{title}' category='{category}' channel='{sn['channelTitle']}'")

    # ---- step3b_thumbnail.py のロジック呼出 ----
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 一時的に current.json をスタブ生成（step3b 側が読む）
    stub_id = f"post_{video_id}"
    stub_cur = {
        "id": stub_id,
        "title": clean_title,
        "category": category,
        "chapters": [{"index": 1, "title": "後追サムネ", "brief": "", "body": ""}],
    }
    cur_path = OUTPUT_DIR / "current.json"
    cur_backup = None
    if cur_path.exists():
        cur_backup = cur_path.read_bytes()
    cur_path.write_text(json.dumps(stub_cur, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        # step3b_thumbnail.main() 呼出（同プロセス内）
        import step3b_thumbnail
        step3b_thumbnail.main()
    finally:
        if cur_backup is not None:
            cur_path.write_bytes(cur_backup)

    # サムネファイル探す
    thumb_path = None
    for ext in ("png", "jpg"):
        p = OUTPUT_DIR / f"{stub_id}_thumb.{ext}"
        if p.exists():
            thumb_path = p
            break
    if not thumb_path:
        print("[set_thumb] FATAL: thumbnail file not found after step3b run")
        sys.exit(1)

    print(f"[set_thumb] using thumb: {thumb_path} ({thumb_path.stat().st_size/1024:.1f}KB)")

    # ---- step5_upload.set_thumbnail 呼出 ----
    import step5_upload
    ok = step5_upload.set_thumbnail(token, video_id, thumb_path)
    if not ok:
        print("[set_thumb] FAILED")
        sys.exit(3)

    print(f"[set_thumb] OK https://www.youtube.com/watch?v={video_id}")


if __name__ == "__main__":
    main()
