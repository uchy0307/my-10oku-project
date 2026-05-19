#!/usr/bin/env -S python3 -u
"""
youtube_thumb.py — YouTube Data API v3 `thumbnails.set` 汎用モジュール

カスタムサムネイル JPEG をアップロードする。OAuth access_token は外部で取得する
（oauth_refresh.py を参照）ため、本モジュールはトークン文字列のみ受け取る。

Usage (import):
    from new_youtube.scripts.youtube_thumb import set_thumbnail
    res = set_thumbnail(access_token, video_id, Path("thumb.jpg"))

Usage (CLI):
    python youtube_thumb.py --access-token TOK --video-id VID --thumb thumb.jpg

API ref:
    https://developers.google.com/youtube/v3/docs/thumbnails/set
    Endpoint: POST https://www.googleapis.com/upload/youtube/v3/thumbnails/set
              ?videoId={VID}&uploadType=media
    Body:     raw JPEG/PNG bytes
    Headers:  Authorization: Bearer {access_token}
              Content-Type:  image/jpeg

制限:
  - JPEG / PNG / GIF / BMP のいずれか（実用上は JPEG 1280x720 推奨）
  - ファイルサイズ <= 2 MiB
  - アカウントの電話番号認証必須（未認証だと 400 youtubeSignupRequired を返す）

Notes:
  - リトライ無し。失敗時は具体的なエラーメッセージで例外を投げる
  - access_token の取得は呼び出し側責任
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
MAX_BYTES = 2 * 1024 * 1024  # YouTube 公称 2MB


def _detect_mime(path: Path) -> str:
    """先頭バイトで JPEG/PNG/GIF/BMP を判定。"""
    with open(path, "rb") as f:
        head = f.read(12)
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "image/gif"
    if head.startswith(b"BM"):
        return "image/bmp"
    raise ValueError(
        f"set_thumbnail: unsupported image format (head bytes: {head[:8].hex()})"
    )


def set_thumbnail(
    access_token: str,
    video_id: str,
    thumbnail_path: str | Path,
    *,
    timeout: float = 60.0,
    upload_url: str = UPLOAD_URL,
) -> dict:
    """YouTube videos の custom thumbnail を差し替える。

    Args:
        access_token:   有効な OAuth2 access_token (Bearer)
        video_id:       対象動画 ID
        thumbnail_path: 1280x720 推奨の JPEG/PNG ファイル（<= 2MB）
        timeout:        秒
        upload_url:     差し替え用（テスト時のみ）

    Returns:
        YouTube API レスポンスの dict（typically thumbnails.set#resource）

    Raises:
        FileNotFoundError: thumbnail_path が無い
        ValueError:        2MB 超過 / 未対応フォーマット / 引数欠落
        RuntimeError:      HTTP エラー（status + Google エラー JSON 込み）
    """
    if not access_token:
        raise ValueError("set_thumbnail: access_token is empty")
    if not video_id:
        raise ValueError("set_thumbnail: video_id is empty")
    p = Path(thumbnail_path)
    if not p.is_file():
        raise FileNotFoundError(f"set_thumbnail: thumbnail not found: {p}")

    size = p.stat().st_size
    if size > MAX_BYTES:
        raise ValueError(
            f"set_thumbnail: thumbnail too large ({size} bytes > {MAX_BYTES} max)"
        )
    if size == 0:
        raise ValueError(f"set_thumbnail: thumbnail is empty: {p}")

    mime = _detect_mime(p)
    data = p.read_bytes()

    qs = f"?videoId={urllib.parse.quote(video_id)}&uploadType=media"
    req = urllib.request.Request(
        upload_url + qs,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": mime,
            "Content-Length": str(len(data)),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"raw": body}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")
        raise RuntimeError(
            f"set_thumbnail: HTTP {e.code} from YouTube thumbnails.set "
            f"(videoId={video_id}): {err_body[:600]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"set_thumbnail: network error: {e.reason}"
        ) from e


def _cli() -> int:
    ap = argparse.ArgumentParser(description="YouTube thumbnails.set uploader")
    ap.add_argument("--access-token", default=os.environ.get("YT_ACCESS_TOKEN"))
    ap.add_argument("--video-id", required=False)
    ap.add_argument("--thumb", required=False, help="path to thumbnail JPEG/PNG")
    args = ap.parse_args()
    if not (args.access_token and args.video_id and args.thumb):
        ap.error("--access-token / --video-id / --thumb は必須 (token は env YT_ACCESS_TOKEN でも可)")

    res = set_thumbnail(args.access_token, args.video_id, args.thumb)
    print(f"[youtube_thumb] OK videoId={args.video_id}")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
