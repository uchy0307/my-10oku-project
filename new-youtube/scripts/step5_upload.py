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
import subprocess
from pathlib import Path
from datetime import datetime, timezone
import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
THUMB_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"

# 2026-05-20: 本編=30分尺ナレ動画のみ、を強制するための duration gate.
# ffprobe で読み取った format.duration が MIN_DURATION_SEC 未満なら upload を拒否する.
# 環境変数 NEW_YOUTUBE_SKIP_DURATION_GATE=1 で一時的に bypass 可能 (本日特例の再 upload 等).
MIN_DURATION_SEC = 1800  # 30 min


def _probe_duration_sec(video_path: Path) -> float:
    """ffprobe で対象 mp4 の duration (秒) を取得.
    取得失敗時は RuntimeError を上げる (= upload 拒否扱い).
    """
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(video_path),
            ],
            stderr=subprocess.STDOUT,
            timeout=60,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"ffprobe not found on PATH: {e}") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ffprobe failed for {video_path}: rc={e.returncode} out={e.output!r}"
        ) from e
    txt = out.decode("utf-8", errors="replace").strip()
    if not txt:
        raise RuntimeError(f"ffprobe returned empty duration for {video_path}")
    try:
        return float(txt.splitlines()[0])
    except ValueError as e:
        raise RuntimeError(f"ffprobe duration parse failed: {txt!r}") from e


def _enforce_duration_gate(video_path: Path) -> float:
    """duration < MIN_DURATION_SEC なら SystemExit で upload を拒否.
    戻り値は秒数 (ログ用)."""
    if os.environ.get("NEW_YOUTUBE_SKIP_DURATION_GATE") == "1":
        print(f"[step5][gate] BYPASS via NEW_YOUTUBE_SKIP_DURATION_GATE=1 ({video_path})")
        # bypass でも一応取得を試みる (失敗しても続行)
        try:
            return _probe_duration_sec(video_path)
        except Exception as e:
            print(f"[step5][gate] WARN probe failed during bypass: {e}")
            return -1.0
    dur = _probe_duration_sec(video_path)
    mm = int(dur // 60)
    ss = int(dur % 60)
    if dur < MIN_DURATION_SEC:
        raise SystemExit(
            f"Duration <30min, abort upload "
            f"(actual={mm:02d}:{ss:02d} = {dur:.1f}s, "
            f"min={MIN_DURATION_SEC}s, path={video_path}). "
            "Set NEW_YOUTUBE_SKIP_DURATION_GATE=1 to bypass (special-case only)."
        )
    print(f"[step5][gate] OK duration={mm:02d}:{ss:02d} ({dur:.1f}s >= {MIN_DURATION_SEC}s)")
    return dur


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
    # 2026-05-20: duration gate (30min) を最優先で評価. 不合格なら SystemExit.
    _enforce_duration_gate(video_path)
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
