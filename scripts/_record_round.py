#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""自走ラウンド進捗を messages.json に記録するヘルパ (依頼表現禁止徹底)"""
import sys, json, argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ap = argparse.ArgumentParser()
ap.add_argument('--round', required=True)
ap.add_argument('--title', required=True)
ap.add_argument('--body', required=True)
args = ap.parse_args()

p = Path(r'C:\Users\user\Documents\10oku-project\scripts\messages.json')
msgs = json.loads(p.read_text(encoding='utf-8'))
JST = timezone(timedelta(hours=9))
new_msg = {
    'id': f'msg_round{args.round}_{int(datetime.now(JST).timestamp())}',
    'ts': datetime.now(JST).isoformat(),
    'title': args.title,
    'text': args.body,
    'type': 'claude_to_user',
    'read': False,
}
msgs.insert(0, new_msg)
p.write_text(json.dumps(msgs, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'written: {new_msg["id"]}')
