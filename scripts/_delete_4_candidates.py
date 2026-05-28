#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""うっちー様 OK 出た4候補を一括削除. VOICEVOX model は除外."""
import sys, shutil
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

targets = [
    Path(r'C:\Users\user\AppData\Roaming\Claude\vm_bundles\claudevm.bundle\rootfs.vhdx.zst'),
    Path(r'C:\Users\user\Downloads\voicevox-cpu-0.25.2-x64.nsis.7z'),
    Path(r'C:\Users\user\Documents\10oku-project\new-youtube-local\output'),
    Path(r'C:\Users\user\Documents\10oku-project\new-youtube\outputs'),
]

freed = 0
for t in targets:
    if not t.exists():
        print(f'SKIP (not exist): {t}')
        continue
    try:
        if t.is_file():
            sz = t.stat().st_size
            t.unlink()
            freed += sz
            print(f'FILE rm: {t}  {sz/1024/1024:.1f} MB')
        else:
            sz = sum(p.stat().st_size for p in t.rglob('*') if p.is_file())
            shutil.rmtree(t, ignore_errors=True)
            freed += sz
            print(f'DIR rm: {t}  {sz/1024/1024:.1f} MB')
    except Exception as e:
        print(f'FAIL: {t} ({e})')

print(f'\ntotal freed: {freed/1024/1024/1024:.2f} GB')
print(f'free now: {shutil.disk_usage("C:").free/1024/1024/1024:.2f} GB')
