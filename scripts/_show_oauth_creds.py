#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OAuth playground 入力用に CLIENT_ID/SECRET を表示 (秘匿だがうっちー様自身の認証のため)"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

env = {}
for line in (Path(r'C:\Users\user\Documents\10oku-project') / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

print('=== OAuth playground 入力値 (samurai 再認証用) ===')
print(f'CLIENT_ID:     {env.get("YOUTUBE_CLIENT_ID", "(missing)")}')
print(f'CLIENT_SECRET: {env.get("YOUTUBE_CLIENT_SECRET", "(missing)")}')
print()
print('Scope: https://www.googleapis.com/auth/youtube.upload')
print('ログインアカウント: @Japanese.Samurai.Channel のもの')
