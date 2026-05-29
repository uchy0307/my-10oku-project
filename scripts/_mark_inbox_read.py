#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""inbox.json 全件を read:true にマーク"""
import sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
p = Path(r'C:\Users\user\Documents\10oku-project\scripts\inbox.json')
data = json.loads(p.read_text(encoding='utf-8'))
n = 0
for m in data:
    if not m.get('read'):
        m['read'] = True
        n += 1
p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'marked: {n}')
