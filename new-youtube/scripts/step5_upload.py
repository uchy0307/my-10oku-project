"""
Step 5: YouTube 自動アップロード (新チャンネル専用)

samurai の既存 YOUTUBE_* とは別チャンネル運用のため、本ファイルは
NEW_YOUTUBE_* env のみを読む。既存 samurai 環境変数は触らない。

必須 env:
  NEW_YOUTUBE_CLIENT_ID
  NEW_YOUTUBE_CLIENT_SECRET
  NEW_YOUTUBE_REFRESH_TOKEN

任意 env:
  NEW_YOUTUBE_PLAYLIST_ID   指定すると公開後にプレイリストへ追加
  NEW_YOUTUBE_CHANNEL_ID    指定すると onBehalfOfContentOwnerChannel に渡す (Brand Account 用)

設計:
  - resumable upload (videos.insert)
  - publishAt 指定で予約公開可
  - playlist 追加は playlistItems.insert
"""
from __future__ import annotations
import sys as _flush_sys
try:
    _flush_sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
import builtins as _flush_b
if not hasattr(_flush_b, "_orig_print"):
    _flush_b._orig_print = _flush_b.print
    def _flush_print(*a, **k):
        k.setdefault("flush", True)
        return _flush_b._orig_print(*a, **k)
    _flush_b.print = _flush_print

import os
import json
from pathlib import Path
from datetime import datetime, timezone
import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
THUMB_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"


def _need(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"env {name} is required")
    return v


def _get_access_token() -> str:
    # 2026-05-20: 共通モジュール oauth_refresh.refresh_access_token に集約
    # (旧版は同梱の直書き requests.post 実装。挙動互換)
    try:
        from oauth_refresh import refresh_access_token  # type: ignore
    except ImportError:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from oauth_refresh import refresh_access_token  # type: ignore
    tok = refresh_access_token(
        _need("NEW_YOUTUBE_CLIENT_ID"),
        _need("NEW_YOUTUBE_CLIENT_SECRET"),
        _need("NEW_YOUTUBE_REFRESH_TOKEN"),
    )
    return tok["access_token"]


def upload_thumbnail(token: str, video_id: str, thumb_path: Path) -> None:
    """videos.thumbnails.set: upload custom thumbnail JPEG.
    Requires account verification (phone) on YouTube; will return 400 with
    'youtubeSignupRequired' if未認証. We log + swallow that case so the rest of
    the pipeline doesn't fail.
    """
    size = thumb_path.stat().st_size
    if size > 2 * 1024 * 1024:
        print(f"[step5] WARN thumbnail too large ({size} bytes, max 2MB), skipping")
        return
    with open(thumb_path, "rb") as f:
        r = requests.post(
            THUMB_UPLOAD_URL,
            params={"videoId": video_id, "uploadType": "media"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "image/jpeg",
            },
            data=f.read(),
            timeout=120,
        )
    if r.status_code >= 400:
        msg = r.text[:300]
        print(f"[step5] WARN thumbnails.set HTTP {r.status_code}: {msg}")
        r.raise_for_status()
    else:
        print(f"[step5] thumbnail set OK ({size} bytes)")


def upload_video(video_path: Path, script: dict,
                 schedule_at_jst: datetime | None = None,
                 privacy: str = "private",
                 thumbnail_path: Path | None = None) -> str:
    token = _get_access_token()
    metadata = {
        "snippet": {
            "title": script["title"][:100],
            "description": script.get("description", ""),
            "tags": script.get("tags", []),
            "categoryId": "22",
            "defaultLanguage": "ja",
            "defaultAudioLanguage": "ja",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    if schedule_at_jst:
        utc = schedule_at_jst.astimezone(timezone.utc)
        metadata["status"]["privacyStatus"] = "private"
        metadata["status"]["publishAt"] = utc.isoformat().replace("+00:00", "Z")

    size = video_path.stat().st_size
    init = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(size),
        },
        json=metadata, timeout=60,
    )
    init.raise_for_status()
    upload_url = init.headers["Location"]

    with open(video_path, "rb") as f:
        r = requests.put(
            upload_url,
            headers={"Content-Type": "video/mp4",
                     "Content-Length": str(size)},
            data=f, timeout=1800,
        )
    r.raise_for_status()
    vid = r.json()["id"]
    print(f"uploaded: https://youtu.be/{vid}")

    # 2026-05-20 fix: custom thumbnail upload (旧版未実装 → YouTube 自動生成の黒画面サムネだった)
    if thumbnail_path and thumbnail_path.exists() and thumbnail_path.stat().st_size > 1000:
        try:
            upload_thumbnail(token, vid, thumbnail_path)
        except Exception as e:
            print(f"[step5] WARN thumbnail set failed: {e}")
    else:
        print(f"[step5] no custom thumbnail provided (path={thumbnail_path})")

    # optional: add to playlist
    pl = os.environ.get("NEW_YOUTUBE_PLAYLIST_ID")
    if pl:
        try:
            _add_to_playlist(token, vid, pl)
            print(f"added to playlist: {pl}")
        except Exception as e:
            print(f"[WARN] playlist add failed: {e}")

    return vid


def _add_to_playlist(token: str, video_id: str, playlist_id: str) -> None:
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    r = requests.post(
        PLAYLIST_ITEMS_URL,
        params={"part": "snippet"},
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        json=body, timeout=30,
    )
    r.raise_for_status()


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script
    script = read_script(sys.argv[1])
    vp = Path(sys.argv[2])
    upload_video(vp, script, privacy="private")
