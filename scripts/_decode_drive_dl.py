#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MCP download_file_content の永続化 JSON ファイルを復号して PNG 保存。

使い方:
  python _decode_drive_dl.py <persisted_json_path> <out_png_path>
"""
import base64, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

src = Path(sys.argv[1])
out = Path(sys.argv[2])
raw = src.read_text(encoding='utf-8', errors='replace')
# JSON parse (content フィールドに base64)
try:
    data = json.loads(raw)
    b64 = data.get('content', '')
except Exception:
    # JSON でなければ全体を base64 とみなす
    b64 = raw.strip()
# data URI prefix 除去
if ',' in b64[:64] and b64[:5] in ('data:', 'iVBOR'):
    if b64.startswith('data:'):
        b64 = b64.split(',', 1)[1]
img = base64.b64decode(b64)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(img)
sig = img[:8]
is_png = sig == b'\x89PNG\r\n\x1a\n'
print(f'wrote {out.name}: {len(img)//1024}KB, PNG={is_png}')
