#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""C ドライブ内の巨大ファイル/ディレクトリ Top をリスト化 (削除はしない)"""
import sys, os
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 検査範囲 (システムフォルダ除外)
TARGETS = [
    Path(r'C:\Users\user\Documents'),
    Path(r'C:\Users\user\Downloads'),
    Path(r'C:\Users\user\AppData\Local'),
    Path(r'C:\Users\user\AppData\Roaming'),
]

dir_sizes = {}
big_files = []

for root in TARGETS:
    if not root.exists():
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        total = 0
        for f in filenames:
            p = Path(dirpath) / f
            try:
                sz = p.stat().st_size
                total += sz
                if sz >= 100 * 1024 * 1024:  # 100MB以上
                    big_files.append((sz, str(p)))
            except: pass
        if total > 0:
            dir_sizes[dirpath] = total
        # 深い再帰防ぐ
        depth = len(Path(dirpath).relative_to(root).parts)
        if depth >= 4:
            dirnames.clear()

# Top 30 ディレクトリ
top_dirs = sorted(dir_sizes.items(), key=lambda x: -x[1])[:30]
print('=== Top 30 directories by size ===')
for d, sz in top_dirs:
    print(f'  {sz/1024/1024/1024:6.2f} GB  {d}')

# Top 30 個別大ファイル
big_files.sort(key=lambda x: -x[0])
print('\n=== Top 30 individual files (>=100MB) ===')
for sz, p in big_files[:30]:
    print(f'  {sz/1024/1024:7.1f} MB  {p}')
