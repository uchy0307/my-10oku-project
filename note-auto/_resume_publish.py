#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import argparse
ap = argparse.ArgumentParser()
ap.add_argument('--ids', nargs='+', required=True)
args = ap.parse_args()
p = Path(__file__).parent / 'queue.json'
q = json.loads(p.read_text(encoding='utf-8'))
items = q.get('items', [])
n = 0
for it in items:
    if it.get('id') in args.ids:
        it['publish'] = True
        it.pop('_paused_by', None)
        it['_violation_fixed_resume'] = '2026-05-28T01:08+09:00 by claude'
        n += 1
        print(f"  #{it['id']}: publish -> True")
p.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'戻し完了: {n}件')
