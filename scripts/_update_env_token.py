#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""新しい refresh_token で .env の YOUTUBE_REFRESH_TOKEN= 行を更新"""
import sys, argparse
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ap = argparse.ArgumentParser()
ap.add_argument('--kind', choices=['samurai', 'otona'], required=True)
ap.add_argument('--token', required=True)
args = ap.parse_args()

key = 'YOUTUBE_REFRESH_TOKEN' if args.kind == 'samurai' else 'OTONA_YOUTUBE_REFRESH_TOKEN'
env_path = Path(r'C:\Users\user\Documents\10oku-project\.env')
lines = env_path.read_text(encoding='utf-8').splitlines()

found = False
for i, line in enumerate(lines):
    if line.startswith(f'{key}='):
        lines[i] = f'{key}={args.token}'
        found = True
        break
if not found:
    lines.append(f'{key}={args.token}')

backup = env_path.with_suffix('.env.bak_token_update')
backup.write_text(env_path.read_text(encoding='utf-8'), encoding='utf-8')

env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'updated {key} in .env (backup: {backup.name})')
