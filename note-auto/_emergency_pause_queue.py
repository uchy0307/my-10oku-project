#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""緊急: queue.json の publish=true && pending を全て false に"""
import sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

p = Path(__file__).parent / 'queue.json'
q = json.loads(p.read_text(encoding='utf-8'))
items = q.get('items', [])
count = 0
ids = []
for it in items:
    if it.get('publish') is True and it.get('status') in ('pending', None):
        it['publish'] = False
        it['_paused_by'] = 'claude_emergency_2026-05-27'
        count += 1
        ids.append(it.get('id'))
q['items'] = items
q['_emergency_pause'] = {
    'at': '2026-05-27T23:55+09:00',
    'reason': 'うっちー様指示: #109/#111/#112 違反 (金額表記NG・本文古い) のため、108件全停止・要精査',
    'paused_count': count,
}
p.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'publish=false 化: {count}件')
print(f'対象 id: {ids[:20]}{"...+" + str(len(ids)-20) + "件" if len(ids)>20 else ""}')
