#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_button_server.py
======================
うっちー様PCで常駐する小型HTTPサーバー。
スマホ / PWA のボタンを押すと対応する .bat / .py を起動する。

ホットリロード: ボタン定義は scripts/actions.json から毎リクエスト時に読み込み。
ボタン追加時はサーバー再起動不要・JSON更新のみで反映。

起動: python local_button_server.py  (port 7373)
"""

import json
import os
import socket
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

# pythonw.exe (no console) では stdout/stderr が None
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class DualStackServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6
    daemon_threads = True  # 親プロセス終了時にスレッドも終了
    allow_reuse_address = True  # 再起動時の TIME_WAIT 回避

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ACTIONS_JSON = SCRIPTS / "actions.json"
MESSAGES_JSON = SCRIPTS / "messages.json"   # Claude → User
INBOX_JSON    = SCRIPTS / "inbox.json"      # User → Claude


def _load_json_safe(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save_json_safe(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# プラットフォーム定義（進捗パネル用）
PLATFORMS = [
    {
        "id": "history",
        "label": "歴史",
        "icon": "⚔️",
        "quota": 3,
        "yt_channel_id": "UChsS2R5ao05wsptKmutSaoA",
        "yt_url": "https://www.youtube.com/@Japanese.Samurai.Channel",
        "is_shorts": False,
        "oauth_kind": "samurai",  # YOUTUBE_REFRESH_TOKEN
    },
    {
        "id": "history_shorts",
        "label": "歴史ショート",
        "icon": "⚡",
        "quota": 5,
        "yt_channel_id": "UChsS2R5ao05wsptKmutSaoA",
        "yt_url": "https://www.youtube.com/@Japanese.Samurai.Channel/shorts",
        "is_shorts": True,
        "oauth_kind": "samurai",
    },
    {
        "id": "otona",
        "label": "大人",
        "icon": "🧠",
        "quota": 3,
        "yt_channel_id": "UClMciBTt4e1QUV1q6l9qrWQ",
        "yt_url": "https://www.youtube.com/@Otona_Psychology",
        "is_shorts": False,
        "oauth_kind": "otona",  # OTONA_YOUTUBE_REFRESH_TOKEN
    },
    {
        "id": "otona_shorts",
        "label": "大人ショート",
        "icon": "✨",
        "quota": 5,
        "yt_channel_id": "UClMciBTt4e1QUV1q6l9qrWQ",
        "yt_url": "https://www.youtube.com/@Otona_Psychology/shorts",
        "is_shorts": True,
        "oauth_kind": "otona",
    },
    {
        "id": "note",
        "label": "note",
        "icon": "📝",
        "quota": 5,
        "yt_channel_id": None,
        "yt_url": "https://note.com/happy_happy_4649",
        "is_shorts": False,
        "is_note": True,
    },
]


def load_actions():
    try:
        with open(ACTIONS_JSON, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

    expanded = {}
    for aid, val in raw.items():
        if isinstance(val, dict):
            cmd_list = val.get("cmd", [])
        else:
            cmd_list = val
        expanded[aid] = {
            "cmd": [
                arg.replace("{ROOT}", str(ROOT)).replace("{SCRIPTS}", str(SCRIPTS))
                if isinstance(arg, str) else arg
                for arg in cmd_list
            ],
            "label": val.get("label", aid) if isinstance(val, dict) else aid,
            "icon": val.get("icon", "▶") if isinstance(val, dict) else "▶",
            "description": val.get("description", "") if isinstance(val, dict) else "",
            "category": val.get("category", "build") if isinstance(val, dict) else "build",
        }
    return expanded


# YouTube RSS から本日アップ動画数を集計
def jst_today_start():
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    return datetime(now.year, now.month, now.day, tzinfo=jst)


def _load_env_vars():
    """Read .env once and return dict (lazy / cached)"""
    if hasattr(_load_env_vars, "_cache"):
        return _load_env_vars._cache
    env = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        # utf-8-sig で BOM (PowerShell Set-Content -Encoding UTF8 の副産物) を除去
        for line in env_file.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip().lstrip("﻿")
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip().lstrip("﻿")] = v.strip()
    _load_env_vars._cache = env
    return env


# (oauth_kind -> {access_token, expires_at, uploads_playlist})
_oauth_cache: dict = {}


def _get_access_token(oauth_kind: str) -> tuple[str, str] | tuple[None, None]:
    """oauth_kind = 'samurai' or 'otona' -> (access_token, uploads_playlist_id)"""
    import time as _t
    cached = _oauth_cache.get(oauth_kind)
    if cached and cached["expires_at"] > _t.time() + 60:
        return cached["access_token"], cached["uploads_playlist"]
    env = _load_env_vars()
    cid = env.get("YOUTUBE_CLIENT_ID")
    csec = env.get("YOUTUBE_CLIENT_SECRET")
    if oauth_kind == "otona":
        rtoken = env.get("OTONA_YOUTUBE_REFRESH_TOKEN")
        # OTONA_YOUTUBE_CLIENT_ID/SECRET があれば優先
        cid = env.get("OTONA_YOUTUBE_CLIENT_ID") or cid
        csec = env.get("OTONA_YOUTUBE_CLIENT_SECRET") or csec
    else:
        rtoken = env.get("YOUTUBE_REFRESH_TOKEN")
    if not (cid and csec and rtoken):
        return None, None
    # POST to oauth2.googleapis.com/token
    body = urllib.parse.urlencode({
        "client_id": cid, "client_secret": csec,
        "refresh_token": rtoken, "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            tok = json.loads(res.read().decode("utf-8"))
    except Exception:
        return None, None
    access_token = tok.get("access_token")
    expires_in = tok.get("expires_in", 3600)
    if not access_token:
        return None, None
    # Get uploads playlist (cached forever since channel doesn't change)
    uploads_playlist = cached["uploads_playlist"] if cached else None
    if not uploads_playlist:
        ch_req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        try:
            with urllib.request.urlopen(ch_req, timeout=10) as res:
                ch = json.loads(res.read().decode("utf-8"))
            uploads_playlist = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        except Exception:
            uploads_playlist = None
    _oauth_cache[oauth_kind] = {
        "access_token": access_token,
        "expires_at": _t.time() + expires_in,
        "uploads_playlist": uploads_playlist,
    }
    return access_token, uploads_playlist


_ytdlp_cache: dict = {}   # handle -> (timestamp, entries)


def fetch_youtube_rss(channel_id, oauth_kind="samurai"):
    """2026-05-29: youtube.upload scope では channels.list / playlistItems.list が呼べない (insufficient).
    yt-dlp 経由でチャンネル最近動画を取得 (scope 不要)。
    返却: [{id, title, published(YYYYMMDD), link, is_shorts_url}]
    cache 5分。"""
    import time as _t
    import subprocess as _sp
    handle = "@Japanese.Samurai.Channel" if oauth_kind == "samurai" else "@Otona_Psychology"
    cached = _ytdlp_cache.get(handle)
    if cached and _t.time() - cached[0] < 300:
        return cached[1]
    args = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist", "--playlist-end", "20",
        "--print", "%(id)s|%(title)s|%(upload_date)s|%(duration)s",
        "--encoding", "utf-8",
        "--no-warnings",
        f"https://www.youtube.com/{handle}/videos",
    ]
    try:
        r = _sp.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    except Exception:
        return []
    if r.returncode != 0:
        return []
    entries = []
    seen = set()
    for line in (r.stdout or "").splitlines():
        parts = line.strip().split("|", 3)
        if len(parts) < 2:
            continue
        vid = parts[0]
        title = parts[1] if len(parts) > 1 else ""
        upload_date = parts[2] if len(parts) > 2 else ""
        try:
            dur = float(parts[3]) if len(parts) > 3 and parts[3] not in ("", "None") else 0
        except ValueError:
            dur = 0
        if not vid or vid in seen:
            continue
        seen.add(vid)
        # Shorts URL は yt-dlp で duration <= 60 + URL に /shorts/ を含む傾向 → duration で判定
        is_shorts_url = 0 < dur <= 65
        entries.append({
            "id": vid,
            "title": title,
            "published": upload_date,  # YYYYMMDD
            "link": f"https://youtube.com/shorts/{vid}" if is_shorts_url else f"https://youtu.be/{vid}",
            "_duration": dur,
        })
    _ytdlp_cache[handle] = (_t.time(), entries)
    return entries


def fetch_note_today_count():
    """note の本日投稿数 + 累計 を取得。本日は RSS、累計は queue.json (status=published) から。"""
    today_count = 0
    latest_link = "https://note.com/happy_happy_4649"
    # 今日分: RSS
    try:
        url = "https://note.com/happy_happy_4649/rss"
        req = urllib.request.Request(url, headers={"User-Agent": "uchy-button/1.0"})
        with urllib.request.urlopen(req, timeout=8) as res:
            xml = res.read().decode("utf-8", errors="replace")
        root = ET.fromstring(xml)
        cutoff = jst_today_start()
        for item in root.iter("item"):
            pub_el = item.find("pubDate")
            link_el = item.find("link")
            if pub_el is None or pub_el.text is None:
                continue
            try:
                from email.utils import parsedate_to_datetime
                pub = parsedate_to_datetime(pub_el.text)
                if pub >= cutoff:
                    today_count += 1
                    if link_el is not None and link_el.text:
                        latest_link = link_el.text
            except Exception:
                continue
    except Exception:
        pass
    # 累計: note-auto/queue.json の published 件数
    total_count = 0
    qp = ROOT / "note-auto" / "queue.json"
    if qp.exists():
        try:
            q = json.loads(qp.read_text(encoding="utf-8"))
            items = q if isinstance(q, list) else (q.get("items") or [])
            for it in items:
                st = (it.get("status") or "").lower() if isinstance(it, dict) else ""
                if st in ("published", "published_manual"):
                    total_count += 1
        except Exception:
            pass
    return today_count, latest_link, total_count


_PROGRESS_DIRS = {
    "history":        ["history_v2"],
    "history_shorts": ["history_shorts_v2", "shorts_v2"],
    "otona":          ["psych_v2"],
    "otona_shorts":   ["psych_shorts_v2", "otona_shorts_v2"],
}


def _fetch_yt_today_from_local(chan_id):
    """ローカル youtube/<dir>/uploaded.json から本日 JST 投稿 + 累計 を集計 (scope 不要・正確)。
    返却: (today_count, last_url, total_count)
    """
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).strftime("%Y-%m-%d")
    today_count = 0
    total_count = 0
    last_url = None
    last_ts = ""
    for d in _PROGRESS_DIRS.get(chan_id, []):
        # 通常の uploaded.json (history_v2 等)
        p = ROOT / "youtube" / d / "uploaded.json"
        if p.exists():
            try:
                db = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                db = {}
            total_count += len(db)
            for k, v in db.items():
                ts = v.get("uploadedAt", "")
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(jst)
                    if dt.strftime("%Y-%m-%d") == today:
                        today_count += 1
                        if ts > last_ts:
                            last_ts = ts
                            last_url = v.get("videoUrl", last_url)
                except Exception:
                    continue
    # audio_drama も該当 kind を含めて集計
    drama_p = ROOT / "youtube" / "audio_drama" / "uploaded.json"
    if drama_p.exists():
        try:
            db = json.loads(drama_p.read_text(encoding="utf-8"))
        except Exception:
            db = {}
        for k, v in db.items():
            drama_kind = v.get("kind", "")
            # history → samurai 系、psych/otona → otona 系
            if chan_id == "history" and drama_kind == "history":
                total_count += 1
                ts = v.get("uploadedAt", "")
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(jst)
                    if dt.strftime("%Y-%m-%d") == today:
                        today_count += 1
                        if ts > last_ts:
                            last_ts = ts
                            last_url = v.get("videoUrl", last_url)
                except Exception:
                    continue
            elif chan_id == "otona" and drama_kind == "otona":
                total_count += 1
                ts = v.get("uploadedAt", "")
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(jst)
                    if dt.strftime("%Y-%m-%d") == today:
                        today_count += 1
                        if ts > last_ts:
                            last_ts = ts
                            last_url = v.get("videoUrl", last_url)
                except Exception:
                    continue
    return today_count, last_url, total_count


def get_progress():
    """全プラットフォームの本日アップ数を返す (uploaded.json ベース、ローカル真実が正)"""
    result = []
    for p in PLATFORMS:
        if p.get("is_note"):
            count, link, total = fetch_note_today_count()
            result.append({
                "id": p["id"],
                "label": p["label"],
                "icon": p["icon"],
                "count": count,
                "quota": p["quota"],
                "total": total,                # 累計
                "url": link,
            })
            continue
        cnt, last_url, total = _fetch_yt_today_from_local(p["id"])
        result.append({
            "id": p["id"],
            "label": p["label"],
            "icon": p["icon"],
            "count": cnt,
            "quota": p["quota"],
            "total": total,                   # 累計
            "url": last_url or p["yt_url"],
        })
    return result


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#fefce8">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <title>PC操作</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    html, body { font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans JP", "Meiryo", sans-serif; }
    body {
      background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%);
      color: #1f2937;
      min-height: 100dvh;
      padding: env(safe-area-inset-top, 16px) 18px env(safe-area-inset-bottom, 24px);
      max-width: 520px;
      margin: 0 auto;
    }
    header {
      padding: 18px 0 14px;
      border-bottom: 2px solid #fcd34d;
      margin-bottom: 18px;
    }
    h1 { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.02em; color: #78350f; }
    .subtitle { font-size: 0.85rem; color: #92400e; margin-top: 4px; font-weight: 500; }

    /* Claude メッセージバナー */
    .messages-wrap { margin-bottom: 12px; }
    .message-card {
      background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
      border: 2px solid #f59e0b;
      border-radius: 16px;
      padding: 14px 16px;
      margin-bottom: 8px;
      display: flex;
      align-items: flex-start;
      gap: 12px;
      box-shadow: 0 4px 12px rgba(245,158,11,0.2);
      animation: slidein 0.4s;
    }
    @keyframes slidein {
      from { opacity: 0; transform: translateY(-8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .msg-icon { font-size: 1.5rem; flex-shrink: 0; }
    .msg-body { flex: 1; min-width: 0; }
    .msg-title { font-weight: 700; font-size: 0.95rem; color: #78350f; margin-bottom: 4px; }
    .msg-text { font-size: 0.85rem; color: #1f2937; line-height: 1.55; white-space: pre-wrap; }
    .msg-time { font-size: 0.7rem; color: #92400e; margin-top: 6px; }
    .msg-dismiss {
      flex-shrink: 0;
      background: rgba(0,0,0,0.08);
      border: none;
      border-radius: 50%;
      width: 28px;
      height: 28px;
      font-size: 1rem;
      cursor: pointer;
      color: #78350f;
    }

    /* 送信FAB */
    .fab {
      position: fixed;
      right: calc(max(0px, (100vw - 520px) / 2) + 20px);
      bottom: max(20px, env(safe-area-inset-bottom, 20px));
      background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
      color: #fff;
      border: none;
      border-radius: 999px;
      padding: 14px 22px;
      font-size: 0.95rem;
      font-weight: 700;
      box-shadow: 0 6px 24px rgba(245,158,11,0.5);
      cursor: pointer;
      z-index: 50;
      font-family: inherit;
    }
    .fab:active { transform: scale(0.95); }

    /* モーダル */
    .modal-bg {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(31,41,55,0.6);
      backdrop-filter: blur(4px);
      z-index: 200;
      justify-content: center;
      align-items: center;
      padding: 20px;
    }
    .modal-bg.open { display: flex; }
    .modal {
      background: #fff;
      border-radius: 24px;
      padding: 24px;
      width: 100%;
      max-width: 440px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    }
    .modal h3 { font-size: 1.2rem; font-weight: 800; color: #78350f; margin-bottom: 12px; }
    .modal-sub { font-size: 0.8rem; color: #6b7280; margin-bottom: 14px; }
    .modal textarea {
      width: 100%;
      min-height: 140px;
      border: 2px solid #fcd34d;
      border-radius: 14px;
      padding: 12px;
      font-family: inherit;
      font-size: 1rem;
      resize: vertical;
      outline: none;
    }
    .modal textarea:focus { border-color: #f59e0b; }
    .modal-actions { display: flex; gap: 10px; margin-top: 14px; justify-content: flex-end; }
    .modal-btn {
      padding: 10px 20px;
      border-radius: 999px;
      border: none;
      font-weight: 700;
      cursor: pointer;
      font-size: 0.9rem;
      font-family: inherit;
    }
    .modal-btn.cancel { background: #e5e7eb; color: #4b5563; }
    .modal-btn.send { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: #fff; }

    /* リンクチップ */
    .link-row {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 14px 0 4px;
      margin: -4px -4px 4px;
      scrollbar-width: none;
    }
    .link-row::-webkit-scrollbar { display: none; }
    .link-chip {
      flex-shrink: 0;
      background: #fff;
      border: 1.5px solid #fcd34d;
      border-radius: 999px;
      padding: 8px 14px;
      font-size: 0.85rem;
      font-weight: 600;
      color: #78350f;
      text-decoration: none;
      transition: transform 0.1s;
      white-space: nowrap;
    }
    .link-chip:active { transform: scale(0.95); }

    /* 進捗パネル */
    .progress-title {
      font-size: 1rem;
      font-weight: 700;
      color: #78350f;
      margin: 18px 0 10px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .progress-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 22px;
    }
    .progress-card {
      background: #fff;
      border: 2px solid #fcd34d;
      border-radius: 16px;
      padding: 14px 12px;
      text-decoration: none;
      color: inherit;
      display: flex;
      flex-direction: column;
      gap: 4px;
      box-shadow: 0 2px 6px rgba(180,83,9,0.08);
      transition: transform 0.1s, box-shadow 0.1s;
    }
    .progress-card:active { transform: scale(0.97); box-shadow: 0 1px 3px rgba(180,83,9,0.12); }
    .progress-card.done { background: #d1fae5; border-color: #10b981; }
    .progress-card.partial { background: #fef9c3; border-color: #f59e0b; }
    .progress-card .pc-head { display: flex; align-items: center; gap: 6px; font-size: 0.9rem; font-weight: 700; color: #78350f; }
    .progress-card .pc-count { font-size: 1.6rem; font-weight: 800; color: #1f2937; letter-spacing: -0.02em; }
    .progress-card .pc-count .target { font-size: 1rem; color: #6b7280; font-weight: 600; }
    .progress-card .pc-total { font-size: 0.7rem; color: #8a6030; margin-top: 4px; font-weight: 600; }
    .progress-card .pc-bar { height: 6px; background: #fef3c7; border-radius: 999px; overflow: hidden; margin-top: 4px; }
    .progress-card .pc-fill { height: 100%; background: #f59e0b; transition: width 0.3s; }
    .progress-card.done .pc-fill { background: #10b981; }

    /* ボタン */
    .actions-title {
      font-size: 1rem;
      font-weight: 700;
      color: #78350f;
      margin: 18px 0 10px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .btn-list { display: flex; flex-direction: column; gap: 12px; }
    .schedule-title { font-size: 1rem; font-weight: 700; color: #78350f; margin: 22px 0 10px; }
    .schedule { background: #fff; border: 1.5px solid #fcd34d; border-radius: 14px; padding: 12px 14px; box-shadow: 0 2px 6px rgba(180,83,9,0.06); }
    .sch-row { display: flex; gap: 12px; padding: 6px 0; font-size: 0.82rem; color: #1f2937; border-bottom: 1px solid #fef3c7; }
    .sch-row:last-child { border-bottom: none; }
    .sch-time { color: #d97706; font-weight: 700; min-width: 64px; }
    .btn {
      background: #fff;
      border: 2px solid #d1d5db;
      border-radius: 18px;
      padding: 16px 16px;
      text-align: left;
      cursor: pointer;
      color: #1f2937;
      font-family: inherit;
      transition: all 0.15s;
      width: 100%;
      box-shadow: 0 2px 6px rgba(0,0,0,0.04);
      display: flex;
      align-items: flex-start;
      gap: 14px;
    }
    .btn:active { transform: translateY(1px) scale(0.99); box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .btn:disabled { opacity: 0.55; cursor: not-allowed; }
    .btn { box-shadow: 0 3px 0 rgba(0,0,0,0.1), 0 6px 14px rgba(0,0,0,0.08); }
    .btn.build { border-color: #fbbf24; background: linear-gradient(180deg,#fffcf2,#fff5dc); }
    .btn.system { border-color: #94a3b8; background: linear-gradient(180deg,#fff,#f3f4f6); }
    .btn.util { border-color: #c4b5fd; background: linear-gradient(180deg,#faf5ff,#f3eaff); }
    /* チャンネル別 投稿ボタン色分け */
    .btn.build-history { border-color: #dc2626; background: linear-gradient(180deg,#fef2f2,#fee2e2); }
    .btn.build-history-shorts { border-color: #ea580c; background: linear-gradient(180deg,#fff7ed,#ffedd5); }
    .btn.build-otona { border-color: #9333ea; background: linear-gradient(180deg,#faf5ff,#f3e8ff); }
    .btn.build-otona-shorts { border-color: #db2777; background: linear-gradient(180deg,#fdf2f8,#fce7f3); }
    .btn.arm { border-color: #f59e0b !important; background: #fef3c7 !important; box-shadow: 0 6px 18px rgba(245,158,11,0.45); animation: pulse 1.2s infinite; }
    .btn.running { border-color: #f59e0b; background: #fef3c7; }
    .btn.ok { border-color: #10b981; background: linear-gradient(180deg,#ecfdf5,#d1fae5); }
    .btn.error { border-color: #ef4444; background: linear-gradient(180deg,#fef2f2,#fee2e2); }
    @keyframes pulse {
      0%, 100% { box-shadow: 0 4px 12px rgba(245,158,11,0.35); }
      50% { box-shadow: 0 4px 18px rgba(245,158,11,0.6); }
    }
    .btn-icon { font-size: 2.1rem; flex-shrink: 0; line-height: 1; }
    .btn-body { flex: 1; min-width: 0; }
    .btn-label { font-size: 1.05rem; font-weight: 700; line-height: 1.3; color: #1f2937; }
    .btn-desc  { font-size: 0.82rem; color: #6b7280; line-height: 1.45; margin-top: 6px; }
    .btn-msg   { font-size: 0.78rem; color: #059669; margin-top: 6px; font-weight: 600; }
    .btn-confirm {
      display: none;
      font-size: 0.9rem;
      color: #92400e;
      font-weight: 700;
      margin-top: 8px;
      padding: 6px 10px;
      background: #fde68a;
      border-radius: 8px;
    }
    .btn.arm .btn-confirm { display: block; }

    .toast {
      position: fixed;
      bottom: max(28px, env(safe-area-inset-bottom, 28px));
      left: 50%;
      transform: translateX(-50%);
      background: #1f2937;
      color: #fef3c7;
      border-radius: 999px;
      padding: 10px 22px;
      font-size: 0.9rem;
      font-weight: 600;
      box-shadow: 0 6px 24px rgba(0,0,0,0.25);
      z-index: 100;
      white-space: nowrap;
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.2s;
    }
    .toast.ok    { background: #059669; color: #fff; }
    .toast.error { background: #dc2626; color: #fff; }
    .toast.show  { opacity: 1; }
    footer { margin-top: 24px; font-size: 0.72rem; color: #92400e; line-height: 1.7; text-align: center; }
  </style>
</head>
<body>
  <header>
    <h1>⚙️ PC操作</h1>
    <div class="subtitle" id="status">読み込み中...</div>
  </header>

  <div class="messages-wrap" id="messages-wrap"></div>

  <div class="link-row">
    <a class="link-chip" href="https://lp.uchy0307.uk" target="_blank" rel="noopener">🌐 LP</a>
    <a class="link-chip" href="https://note.com/happy_happy_4649" target="_blank" rel="noopener">📝 Note</a>
    <a class="link-chip" href="https://toi-suite.vercel.app/" target="_blank" rel="noopener">🎯 toi</a>
    <a class="link-chip" href="https://github.com/uchy0307/my-10oku-project" target="_blank" rel="noopener">📦 github</a>
    <a class="link-chip" href="https://vercel.com/dashboard" target="_blank" rel="noopener">▲ vercel</a>
  </div>

  <div class="progress-title">📊 本日の進捗</div>
  <div class="progress-grid" id="progress"></div>

  <div class="actions-title">🎬 実行ボタン</div>
  <div class="btn-list" id="grid"></div>

  <div class="schedule-title">⏰ 日別タイムテーブル（実測ベース）</div>
  <div class="schedule">
    <div class="sch-row"><span class="sch-time">08:00</span><span>cron 起動：ストック確認→不足分生成→動画化→投稿</span></div>
    <div class="sch-row"><span class="sch-time">08-14時</span><span>動画生成＋投稿（1本約60分・順次最大6時間）</span></div>
    <div class="sch-row"><span class="sch-time">並行</span><span>note添付 20件追加（約20分）</span></div>
    <div class="sch-row"><span class="sch-time">毎5分</span><span>inbox 自動応答（受信確認）</span></div>
    <div class="sch-row"><span class="sch-time">完了時</span><span>各動画URL を本バナーへ自動通知</span></div>
    <div class="sch-row"><span class="sch-time">夜</span><span>日次レポート（成功/失敗/コスト）</span></div>
  </div>

  <footer>
    タップで構え → もう一度タップで実行
  </footer>
  <div class="toast" id="toast"></div>

  <button class="fab" id="compose-fab" onclick="openCompose()">💬 Claudeに送信</button>

  <div class="modal-bg" id="compose-modal">
    <div class="modal">
      <h3>💬 Claudeにメッセージ送信</h3>
      <div class="modal-sub">外出先からClaudeに質問・依頼・コメントを残せます。次セッション開始時に読まれます。</div>
      <textarea id="compose-text" placeholder="例: 大人台本の生成を100本に増やしてほしい"></textarea>
      <div class="modal-actions">
        <button class="modal-btn cancel" onclick="closeCompose()">キャンセル</button>
        <button class="modal-btn send" onclick="sendCompose()">送信</button>
      </div>
    </div>
  </div>

  <script>
    const BASE = '';
    let toastTimer = null;
    let armedId = null;

    function showToast(msg, tone) {
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.className = 'toast show' + (tone ? ' ' + tone : '');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => { t.className = 'toast'; }, 2800);
    }

    function escHtml(s) {
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    async function loadProgress() {
      try {
        const res = await fetch(BASE + '/progress');
        const data = await res.json();
        const grid = document.getElementById('progress');
        grid.innerHTML = '';
        for (const p of data.platforms) {
          const pct = Math.min(100, Math.round(p.count * 100 / p.quota));
          const cls = p.count >= p.quota ? 'done' : (p.count > 0 ? 'partial' : '');
          const card = document.createElement('a');
          card.className = 'progress-card ' + cls;
          card.href = p.url;
          card.target = '_blank';
          card.rel = 'noopener';
          const totalStr = (p.total != null) ? ('<div class="pc-total">累計 ' + p.total + ' 本</div>') : '';
          card.innerHTML =
            '<div class="pc-head">' + p.icon + ' ' + escHtml(p.label) + '</div>' +
            '<div class="pc-count">' + p.count + '<span class="target"> / ' + p.quota + ' 本</span></div>' +
            '<div class="pc-bar"><div class="pc-fill" style="width:' + pct + '%"></div></div>' +
            totalStr;
          grid.appendChild(card);
        }
      } catch(e) {
        document.getElementById('progress').innerHTML = '<div style="grid-column:1/-1;color:#92400e;font-size:0.85rem;">進捗取得失敗（YouTube RSS到達不可）</div>';
      }
    }

    function resetArm() {
      if (!armedId) return;
      const prev = document.querySelector('.btn[data-id="' + armedId + '"]');
      if (prev) prev.classList.remove('arm');
      armedId = null;
    }

    async function fire(id, btn, info) {
      btn.disabled = true;
      btn.classList.remove('arm');
      btn.className = 'btn ' + (info.category || 'build') + ' running';
      showToast('起動中...');
      try {
        const res = await fetch(BASE + '/run/' + id, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'HTTP ' + res.status);
        btn.className = 'btn ' + (info.category || 'build') + ' ok';
        const msgEl = btn.querySelector('.btn-msg');
        if (msgEl) msgEl.textContent = '✓ ' + (data.message || '起動済み');
        showToast('✓ ' + info.label + ' 起動成功', 'ok');
        setTimeout(loadProgress, 2000);
      } catch(e) {
        btn.className = 'btn ' + (info.category || 'build') + ' error';
        showToast('✗ ' + e.message, 'error');
      } finally {
        btn.disabled = false;
        armedId = null;
      }
    }

    function handleTap(id, btn, info) {
      if (armedId === id) {
        fire(id, btn, info);
      } else {
        resetArm();
        armedId = id;
        btn.classList.add('arm');
        showToast('もう一度タップで「' + info.label + '」を実行');
      }
    }

    async function loadActions() {
      try {
        const res = await fetch(BASE + '/actions');
        const data = await res.json();
        const grid = document.getElementById('grid');
        grid.innerHTML = '';
        const entries = Object.entries(data.actions);
        // category順: 投稿(歴史→大人→歴史ショート→大人ショート) → build(台本/音声) → util
        const order = {
          'build-history': 0, 'build-otona': 1,
          'build-history-shorts': 2, 'build-otona-shorts': 3,
          'build': 4, 'util': 5, 'system': 6
        };
        entries.sort((a, b) => (order[a[1].category] ?? 9) - (order[b[1].category] ?? 9));
        for (const [id, info] of entries) {
          const btn = document.createElement('button');
          btn.className = 'btn ' + (info.category || 'build');
          btn.dataset.id = id;
          btn.innerHTML =
            '<div class="btn-icon">' + (info.icon || '▶') + '</div>' +
            '<div class="btn-body">' +
              '<div class="btn-label">' + escHtml(info.label || id) + '</div>' +
              '<div class="btn-desc">' + escHtml(info.description || '') + '</div>' +
              '<div class="btn-confirm">▶ もう一度タップで実行</div>' +
              '<div class="btn-msg"></div>' +
            '</div>';
          btn.onclick = () => handleTap(id, btn, info);
          grid.appendChild(btn);
        }
        document.getElementById('status').textContent = 'ボタン ' + entries.length + ' 個 / ' + new Date().toLocaleTimeString('ja-JP');
      } catch(e) {
        document.getElementById('status').textContent = '読込失敗: ' + e.message;
        showToast('読込失敗: ' + e.message, 'error');
      }
    }

    document.body.addEventListener('click', (e) => {
      if (!e.target.closest('.btn')) resetArm();
    });

    // Claude→User メッセージ（最新5件まで表示・以降は折りたたみ）
    const MSG_LIMIT = 5;
    let msgExpanded = false;
    async function loadMessages() {
      try {
        const res = await fetch(BASE + '/messages');
        const data = await res.json();
        const wrap = document.getElementById('messages-wrap');
        wrap.innerHTML = '';
        const msgs = (data.messages || []).slice().reverse();  // 新しい順
        const visible = msgExpanded ? msgs : msgs.slice(0, MSG_LIMIT);
        for (const m of visible) {
          const card = document.createElement('div');
          card.className = 'message-card';
          const ts = m.ts ? new Date(m.ts).toLocaleString('ja-JP') : '';
          card.innerHTML =
            '<div class="msg-icon">📩</div>' +
            '<div class="msg-body">' +
              '<div class="msg-title">' + escHtml(m.title || 'Claudeから') + '</div>' +
              '<div class="msg-text">' + escHtml(m.body || '') + '</div>' +
              '<div class="msg-time">' + ts + '</div>' +
            '</div>' +
            '<button class="msg-dismiss" data-id="' + m.id + '">✕</button>';
          card.querySelector('.msg-dismiss').onclick = () => dismissMsg(m.id);
          wrap.appendChild(card);
        }
        if (msgs.length > MSG_LIMIT) {
          const more = document.createElement('button');
          more.className = 'link-chip';
          more.style.marginTop = '6px';
          more.textContent = msgExpanded ? '▲ 折りたたむ' : '▼ 残り ' + (msgs.length - MSG_LIMIT) + ' 件';
          more.onclick = () => { msgExpanded = !msgExpanded; loadMessages(); };
          wrap.appendChild(more);
        }
      } catch(e) { /* silent */ }
    }

    async function dismissMsg(id) {
      try {
        await fetch(BASE + '/messages/dismiss/' + id, { method: 'POST' });
        loadMessages();
      } catch(e) {}
    }

    function openCompose() { document.getElementById('compose-modal').classList.add('open'); }
    function closeCompose() { document.getElementById('compose-modal').classList.remove('open'); document.getElementById('compose-text').value = ''; }

    async function sendCompose() {
      const ta = document.getElementById('compose-text');
      const text = ta.value.trim();
      if (!text) { showToast('内容を入力してください', 'error'); return; }
      try {
        const res = await fetch(BASE + '/inbox', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'HTTP ' + res.status);
        showToast('✓ Claudeに送信しました', 'ok');
        closeCompose();
      } catch(e) {
        showToast('✗ ' + e.message, 'error');
      }
    }

    loadActions();
    loadProgress();
    loadMessages();
    setInterval(loadProgress, 60000);
    setInterval(loadMessages, 30000);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = HTML_TEMPLATE.encode("utf-8")
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/lp":
            # ランディングページ配信
            lp_path = SCRIPTS / "lp.html"
            try:
                body = lp_path.read_bytes()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._json(404, {"error": "lp.html not found"})

        elif self.path == "/actions":
            actions = load_actions()
            ui = {
                aid: {
                    "label": v["label"],
                    "icon": v["icon"],
                    "description": v["description"],
                    "category": v["category"],
                }
                for aid, v in actions.items()
            }
            self._json(200, {"actions": ui})

        elif self.path == "/progress":
            try:
                platforms = get_progress()
                self._json(200, {"platforms": platforms})
            except Exception as e:
                self._json(500, {"error": str(e)})

        elif self.path == "/messages":
            # Claude → User: 未読メッセージ取得
            msgs = _load_json_safe(MESSAGES_JSON, [])
            unread = [m for m in msgs if not m.get("read")]
            self._json(200, {"messages": unread, "total_unread": len(unread)})

        elif self.path == "/inbox":
            # User → Claude: 全送信履歴（Claudeが次セッション開始時に読む）
            inbox = _load_json_safe(INBOX_JSON, [])
            self._json(200, {"inbox": inbox})

        elif self.path == "/api":
            actions = load_actions()
            self._json(200, {"status": "ok", "actions": list(actions.keys()), "root": str(ROOT)})

        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)

        # メッセージ既読化
        if parsed.path.startswith("/messages/dismiss/"):
            msg_id = parsed.path.split("/messages/dismiss/", 1)[1]
            msgs = _load_json_safe(MESSAGES_JSON, [])
            changed = False
            for m in msgs:
                if m.get("id") == msg_id:
                    m["read"] = True
                    changed = True
            if changed:
                _save_json_safe(MESSAGES_JSON, msgs)
            self._json(200, {"status": "ok"})
            return

        # ユーザー → Claude 送信
        if parsed.path == "/inbox":
            try:
                clen = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(clen).decode("utf-8", errors="replace")
                payload = json.loads(raw) if raw else {}
                text = (payload.get("text") or "").strip()
            except Exception:
                text = ""
            if not text:
                self._json(400, {"error": "empty"})
                return
            inbox = _load_json_safe(INBOX_JSON, [])
            from datetime import datetime, timezone as _tz
            inbox.append({
                "id": f"in_{int(datetime.now(_tz.utc).timestamp())}",
                "ts": datetime.now(_tz.utc).isoformat(),
                "text": text,
                "read": False
            })
            _save_json_safe(INBOX_JSON, inbox)
            self._json(200, {"status": "ok", "message": "Claude に送信しました（次セッションで読まれます）"})
            return

        # アクション実行
        actions = load_actions()
        if not parsed.path.startswith("/run/"):
            self._json(404, {"error": "not found"})
            return

        aid = parsed.path.split("/run/", 1)[1]
        if aid not in actions:
            self._json(400, {"error": "unknown action", "id": aid})
            return

        cmd = actions[aid]["cmd"]
        try:
            # Windows: CREATE_NO_WINDOW でウィンドウを完全に隠す
            CREATE_NO_WINDOW = 0x08000000
            flags = CREATE_NO_WINDOW if sys.platform == "win32" else 0
            # cmd リストの先頭が 'cmd.exe /c start' の場合は、shellラッパー不要なので
            # 直接 .bat / .py を実行する形に変換
            actual_cmd = cmd
            if (len(cmd) >= 5 and cmd[0].lower().endswith("cmd.exe")
                and cmd[1] == "/c" and cmd[2] == "start"):
                # ['cmd.exe', '/c', 'start', '', 'path\\foo.bat']
                #  -> ['cmd.exe', '/c', 'path\\foo.bat']
                actual_cmd = ["cmd.exe", "/c", cmd[-1]]

            # ログ記録
            logs_dir = SCRIPTS / "logs"
            logs_dir.mkdir(exist_ok=True)
            from datetime import datetime
            log_line = f"[{datetime.now().isoformat()}] action={aid} cmd={actual_cmd}\n"
            with open(logs_dir / "actions.log", "a", encoding="utf-8") as lf:
                lf.write(log_line)

            # アクション固有ログ (stdout/stderr 統合)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            action_log = logs_dir / f"action_{aid}_{ts}.log"
            log_fp = open(action_log, "w", encoding="utf-8", errors="replace")

            # .env を Python 側で読んで子プロセスに渡す
            # (BAT 内の for /f .env パース構文エラーを回避する正攻法)
            child_env = dict(os.environ)
            for k, v in _load_env_vars().items():
                child_env[k] = v

            proc = subprocess.Popen(
                actual_cmd,
                env=child_env,
                cwd=str(ROOT),
                creationflags=flags,
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )

            # 終了監視スレッド: 異常終了なら messages.json に通知
            def _watch(p, aid_, label_, logpath, fp):
                try:
                    rc = p.wait()
                finally:
                    try: fp.close()
                    except Exception: pass
                if rc != 0:
                    try:
                        with open(logpath, "r", encoding="utf-8", errors="replace") as rf:
                            tail = rf.read()[-800:]
                    except Exception:
                        tail = "(log read failed)"
                    try:
                        msgs = json.loads(MESSAGES_JSON.read_text(encoding="utf-8"))
                    except Exception:
                        msgs = []
                    from datetime import timezone, timedelta
                    jst = timezone(timedelta(hours=9))
                    msgs.append({
                        "id": f"act_fail_{aid_}_{int(datetime.now(jst).timestamp())}",
                        "ts": datetime.now(jst).isoformat(),
                        "title": f"❌ {label_} 失敗 (exit={rc})",
                        "body": f"ログ末尾:\n{tail}\n\n全ログ: {logpath}",
                        "read": False,
                        "auto": True,
                    })
                    MESSAGES_JSON.write_text(
                        json.dumps(msgs, ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
            import threading
            label_for_msg = actions[aid].get("label", aid)
            threading.Thread(
                target=_watch,
                args=(proc, aid, label_for_msg, str(action_log), log_fp),
                daemon=True
            ).start()

            self._json(200, {
                "status": "started",
                "action": aid,
                "pid": proc.pid,
                "message": "実行中（PID " + str(proc.pid) + "）",
                "log": str(action_log)
            })
        except Exception as e:
            # エラーもログ
            try:
                logs_dir = SCRIPTS / "logs"
                logs_dir.mkdir(exist_ok=True)
                from datetime import datetime
                with open(logs_dir / "actions.log", "a", encoding="utf-8") as lf:
                    lf.write(f"[{datetime.now().isoformat()}] action={aid} ERROR: {e}\n")
            except Exception:
                pass
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        if sys.stderr:
            sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")


def _print(msg):
    if sys.stdout:
        print(msg)


def main():
    port = 7373
    actions = load_actions()
    _print(f"=== local button server ===")
    _print(f"Listening: http://localhost:{port}")
    _print(f"ROOT: {ROOT}")
    _print(f"Actions: {list(actions.keys())}")
    _print(f"Ctrl+C で停止")
    server = DualStackServer(("::", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _print("\n停止しました。")


if __name__ == "__main__":
    main()
