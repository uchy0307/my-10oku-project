#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inbox_auto_responder.py
=======================
PC側で常駐し、スマホからの inbox 送信を検知して messages.json に自動返信を書き戻す。
これにより「Claude が今オフラインか応答中か」がスマホでわかる。

使い方:
    python inbox_auto_responder.py  # 60秒間隔で監視ループ
    python inbox_auto_responder.py --once  # 1回だけチェック

タスクスケジューラ登録（5分ごと実行）:
    register_inbox_responder_service.ps1 で実行
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Windows UTF-8
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
INBOX = SCRIPTS / "inbox.json"
MESSAGES = SCRIPTS / "messages.json"
STATE = SCRIPTS / "inbox_responder_state.json"

JST = timezone(timedelta(hours=9))


def load_json(p, default):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_offline_reply(inbox_msg):
    """ユーザー送信に対する自動オフライン返信を生成（強化版）"""
    ts_now = datetime.now(JST)
    sent_ts = inbox_msg.get("ts", "")
    text = inbox_msg.get("text", "")[:120]
    # キーワード判定で個別応答
    text_lower = text.lower()
    if any(k in text for k in ["URL", "url", "リンク", "結果", "動画"]):
        hint = "📺 動画URLは投稿完了次第このバナーに自動表示されます（pipeline実行中なら ffmpeg+upload で約60分）。"
    elif any(k in text for k in ["失敗", "エラー", "fail", "止ま", "動か"]):
        hint = "❗ 失敗・エラーの場合は scripts/logs/ にログ残ってます。Claude次セッションで原因＋改善セットで報告予定。"
    elif any(k in text for k in ["進捗", "状況", "確認"]):
        hint = "📊 messages.json と inbox.json を私が次セッション開始時に必ず読みます。手動進捗確認なら『歴史投稿（次の3本）』ボタン押下で実行ログがバナーへ。"
    elif any(k in text for k in ["停止", "止め", "中止", "キャンセル"]):
        hint = "⏸ 緊急停止が必要なら管理者PowerShellで: taskkill /F /IM ffmpeg.exe /IM python.exe /IM node.exe"
    else:
        hint = "✉ 通常質問・指示は私が次セッション開始時にまとめて返答します。"
    return {
        "id": f"auto_reply_{inbox_msg['id']}",
        "ts": ts_now.isoformat(),
        "title": "🤖 自動応答（Claude オフライン）",
        "body": f"受信: 「{text}」({sent_ts[:19]})\n\n{hint}\n\nClaude本体は session 内のみ稼働。次回チャット時に読み込み済。",
        "read": False,
        "auto": True,
    }


def tick():
    """1回分のチェック・応答"""
    inbox = load_json(INBOX, [])
    messages = load_json(MESSAGES, [])
    state = load_json(STATE, {"replied_ids": []})
    replied = set(state.get("replied_ids", []))

    # Find unread inbox messages that we haven't auto-replied to yet
    new_messages_added = 0
    for m in inbox:
        mid = m.get("id")
        if not mid or mid in replied:
            continue
        # Only auto-reply to user messages (not those marked read by Claude)
        if m.get("read"):
            replied.add(mid)
            continue
        # Generate offline reply
        reply = make_offline_reply(m)
        messages.append(reply)
        replied.add(mid)
        new_messages_added += 1
        print(f"[auto-reply] sent for {mid}: {m.get('text','')[:50]}")

    if new_messages_added > 0:
        save_json(MESSAGES, messages)

    state["replied_ids"] = list(replied)[-500:]  # keep last 500
    state["last_check"] = datetime.now(JST).isoformat()
    save_json(STATE, state)

    return new_messages_added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="1回だけチェック")
    ap.add_argument("--interval", type=int, default=60, help="ループ間隔秒")
    args = ap.parse_args()

    if args.once:
        n = tick()
        print(f"[done] {n} auto-replies sent")
        return

    print(f"[auto-responder] loop start (interval={args.interval}s)")
    while True:
        try:
            n = tick()
            if n > 0:
                print(f"[{datetime.now(JST).isoformat()[:19]}] +{n} replies")
        except KeyboardInterrupt:
            print("[auto-responder] stopped")
            break
        except Exception as e:
            print(f"[error] {e}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
