#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""scripts/logs/ 内の最新ログを探索 (powershell pipe回避)"""
import sys, argparse, glob, os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ap = argparse.ArgumentParser()
ap.add_argument('--pattern', required=True, help='filename prefix (例: action_build_history_3)')
ap.add_argument('--count', type=int, default=1)
args = ap.parse_args()

logs = Path(r'C:\Users\user\Documents\10oku-project\scripts\logs')
matches = sorted(
    logs.glob(f'{args.pattern}*.log'),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)[:args.count]
for m in matches:
    print(m)
