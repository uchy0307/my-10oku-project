#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.env の 2つ目の YOUTUBE_REFRESH_TOKEN= 行を
OTONA_YOUTUBE_REFRESH_TOKEN= に書き換える (値はそのまま保持・出力しない)
"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ENV = Path(r'C:\Users\user\Documents\10oku-project\.env')
lines = ENV.read_text(encoding='utf-8').splitlines()

# 既に OTONA キーが存在するか
if any(ln.startswith('OTONA_YOUTUBE_REFRESH_TOKEN=') for ln in lines):
    print('SKIP: OTONA_YOUTUBE_REFRESH_TOKEN already present')
    sys.exit(0)

count = 0
target_idx = -1
for i, ln in enumerate(lines):
    if ln.startswith('YOUTUBE_REFRESH_TOKEN='):
        count += 1
        if count == 2:
            target_idx = i
            break

if target_idx < 0:
    print(f'FAIL: only {count} YOUTUBE_REFRESH_TOKEN= lines found, expected 2')
    sys.exit(1)

# 値はそのまま、キー名だけ置換
original = lines[target_idx]
new_line = 'OTONA_YOUTUBE_REFRESH_TOKEN=' + original.split('=', 1)[1]
lines[target_idx] = new_line

ENV.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'OK: renamed line {target_idx+1} to OTONA_YOUTUBE_REFRESH_TOKEN=')
