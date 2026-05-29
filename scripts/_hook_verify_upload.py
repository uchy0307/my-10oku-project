#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_hook_verify_upload.py
======================
Claude Code の PostToolUse hook から呼ばれる。
直前の Bash command 文字列が upload_quarantine.mjs / upload_shorts.mjs を含む場合だけ、
_verify_uploads_oembed.py を実行して結果を stdout に出す。
それ以外は何もせず exit 0。

ハルシネーション再発防止用。
"""
import sys, json, subprocess
from pathlib import Path

# Claude Code hook は stdin で {tool_input, tool_response, ...} を渡してくる
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_input = data.get('tool_input', {})
cmd = (tool_input.get('command') or '').lower()

# upload 関連コマンドかどうか判定
if not any(k in cmd for k in ['upload_quarantine.mjs', 'upload_shorts.mjs']):
    sys.exit(0)

# 実行
script = Path(__file__).parent / '_verify_uploads_oembed.py'
if not script.exists():
    sys.exit(0)

print('---- [hook] upload 完了検知 → oEmbed 公開確認 ----', flush=True)
try:
    r = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=120,
    )
    print(r.stdout, flush=True)
    if r.returncode != 0:
        print(f'[hook] verify exit={r.returncode}', flush=True)
except Exception as e:
    print(f'[hook] verify failed: {e}', flush=True)
sys.exit(0)
