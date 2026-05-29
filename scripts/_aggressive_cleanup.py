#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2026-05-30 ディスク容量確保: youtube/*/.work* + stock_images/wiki + .archive_dl を一括削除。
ユーザー指示「字幕なし新ロジックで再 build」のため、古いビルド残骸は全削除して問題なし。
"""
import shutil, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')


def dir_size(p):
    try:
        return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
    except Exception:
        return 0


# 削除対象
targets = []
SUBS = ['history_v2', 'psych_v2', 'history_shorts_v2', 'otona_shorts_v2',
        'shorts_v2', 'audio_drama', 'psych_shorts_v2', 'otona_psych_v2',
        'otona']
KINDS = ['.work', '.work_quarantine', '.work_broken']
for sub in SUBS:
    for kind in KINDS:
        p = ROOT / 'youtube' / sub / kind
        if p.exists() and p.is_dir():
            targets.append(p)

# 大物単独
extras = [
    ROOT / '.archive_dl',
    ROOT / 'youtube' / 'stock_images' / 'wiki',
]
for p in extras:
    if p.exists() and p.is_dir():
        targets.append(p)

# audio mp3/srt も大物 (gitignore 済、再生成可能、削除 OK)
audio_dirs = []
for sub in ['history_v2', 'psych_v2', 'history_shorts_v2', 'otona_shorts_v2',
            'shorts_v2', 'psych_shorts_v2']:
    p = ROOT / 'youtube' / sub / 'audio'
    if p.exists() and p.is_dir():
        audio_dirs.append(p)

print('=' * 70)
print('削除対象 - work/quarantine/broken')
print('=' * 70)
freed_total = 0
for p in targets:
    size = dir_size(p)
    print(f'  {p.relative_to(ROOT)}: {size/(1024**3):.3f} GB')
    if size > 0:
        shutil.rmtree(p, ignore_errors=True)
        freed_total += size

print()
print('=' * 70)
print('削除対象 - audio mp3/srt (再生成可能)')
print('=' * 70)
for p in audio_dirs:
    # mp3/srt のみ削除、 .json 等は残す
    deleted = 0
    for f in p.rglob('*'):
        if f.is_file() and f.suffix.lower() in ('.mp3', '.srt', '.wav', '.json'):
            try:
                s = f.stat().st_size
                if f.suffix.lower() == '.json' and 'words' in f.name:
                    f.unlink()
                    deleted += s
                elif f.suffix.lower() in ('.mp3', '.srt', '.wav'):
                    f.unlink()
                    deleted += s
            except Exception:
                pass
    print(f'  {p.relative_to(ROOT)}: {deleted/(1024**3):.3f} GB 削除')
    freed_total += deleted

print()
print(f'=== Total freed: {freed_total/(1024**3):.2f} GB ===')

# 残量確認
import shutil as _sh
total, used, free = _sh.disk_usage('C:\\')
print(f'\nC: drive: free={free/(1024**3):.2f} GB / total={total/(1024**3):.2f} GB')
