#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""script JSON の chapter 合計 char 数を確認 (再生成進捗確認用)。"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent

for sub, prefix in [('history_v2', 'long_'), ('psych_v2', 'psych_')]:
    d = ROOT / 'youtube' / sub / 'scripts'
    if not d.exists():
        continue
    files = sorted(d.glob(f'{prefix}*.json'))
    counts = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            chs = data.get('chapters') or []
            total = sum(len(c.get('text', '')) for c in chs)
            counts.append((f.name, total))
        except Exception:
            pass
    print(f'\n=== {sub} ({len(counts)} files) ===')
    print('chars histogram:')
    print(f'  >= 11000: {sum(1 for _, c in counts if c >= 11000)} (新 char_max OK)')
    print(f'   8000-10999: {sum(1 for _, c in counts if 8000 <= c < 11000)}')
    print(f'   5000-7999: {sum(1 for _, c in counts if 5000 <= c < 8000)} (旧 char_max)')
    print(f'   < 5000: {sum(1 for _, c in counts if c < 5000)}')
