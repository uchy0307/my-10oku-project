#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
samurai_thumb_upload.py
@Japanese.Samurai.Channel の Shorts 4本にカスタムサムネを upload する自動スクリプト

実行: ダブルクリック samurai_thumb_upload.bat
出力: samurai_thumb_upload.log

env 設定 (samurai_thumb_upload.bat 内 or set コマンドで事前指定):
    SAMURAI_YOUTUBE_CLIENT_ID
    SAMURAI_YOUTUBE_CLIENT_SECRET
    SAMURAI_YOUTUBE_REFRESH_TOKEN

参考: note-auto/youtube_tokens.json から該当値を読んで上記環境変数に set してから実行。
secrets を source code に絶対に書かないこと (push protection / 漏洩防止)。
"""
from __future__ import annotations
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THUMB_DIR = ROOT / "outputs" / "samurai_thumbs"
LOG = Path(__file__).with_suffix(".log")

# === credentials (環境変数経由で読込) ===
CLIENT_ID = os.environ.get("SAMURAI_YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SAMURAI_YOUTUBE_CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("SAMURAI_YOUTUBE_REFRESH_TOKEN", "")

# === targets ===
MAPPING = [
    ("01_sakuradamon.jpg", "w-2WORvC3nQ", "桜田門外の変"),
    ("02_oseifukko.jpg",   "3w8bTCPetds", "王政復古の大号令"),
    ("03_edomoney.jpg",    "fgOW_DX3-No", "江戸時代のお金"),
    ("04_kinshinkon.jpg",  "-A0aEZGGnOA", "近親婚の歴史"),
]

OAUTH_URL = "https://oauth2.googleapis.com/token"
THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def ensure_credentials() -> None:
    missing = [
        name for name, val in (
            ("SAMURAI_YOUTUBE_CLIENT_ID", CLIENT_ID),
            ("SAMURAI_YOUTUBE_CLIENT_SECRET", CLIENT_SECRET),
            ("SAMURAI_YOUTUBE_REFRESH_TOKEN", REFRESH_TOKEN),
        ) if not val
    ]
    if missing:
        raise RuntimeError(
            "Missing env vars: " + ", ".join(missing) +
            ". samurai_thumb_upload.bat 内で set してから再実行してください。"
        )


def refresh_token() -> str:
    body = urllib.parse.urlencode({
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN, "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(OAUTH_URL, data=body, method="POST",
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    if not d.get("access_token"):
        raise RuntimeError(f"no access_token: {d}")
    log(f"OAuth refresh OK expires_in={d.get('expires_in')} scope={d.get('scope')}")
    return d["access_token"]


def set_thumb(token: str, video_id: str, path: Path) -> dict:
    data = path.read_bytes()
    qs = f"?videoId={urllib.parse.quote(video_id)}&uploadType=media"
    req = urllib.request.Request(
        THUMB_URL + qs, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "image/jpeg",
            "Content-Length": str(len(data)),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8")
            return {"status": r.status, "body": json.loads(body) if body else {}}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {err[:600]}") from e


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    log(f"=== samurai_thumb_upload start (root={ROOT}) ===")
    log(f"thumb_dir={THUMB_DIR}")

    ensure_credentials()

    missing = [n for n, _, _ in MAPPING if not (THUMB_DIR / n).is_file()]
    if missing:
        log(f"MISSING thumbnails: {missing}")
        return 2

    token = refresh_token()

    results = []
    for fn, vid, title in MAPPING:
        p = THUMB_DIR / fn
        size = p.stat().st_size
        try:
            res = set_thumb(token, vid, p)
            log(f"OK  {vid}  {title}  ({size}B)  HTTP={res['status']}")
            results.append({"vid": vid, "title": title, "ok": True, "status": res["status"], "body": res["body"]})
        except Exception as e:
            log(f"FAIL {vid}  {title}  ({size}B)  {type(e).__name__}: {e}")
            results.append({"vid": vid, "title": title, "ok": False, "err": str(e)})

    # summary
    ok = sum(1 for r in results if r["ok"])
    log(f"=== DONE  ok={ok}/{len(results)} ===")
    # write JSON result
    Path(__file__).with_name("samurai_thumb_upload.result.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"FATAL: {type(e).__name__}: {e}")
        sys.exit(99)
