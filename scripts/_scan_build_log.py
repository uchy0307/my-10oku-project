#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
p = Path(r'C:\Users\user\AppData\Local\Temp\claude\C--Users-user-Documents-10oku-project\cef4aaf5-aa48-4b5a-b433-ea53989ff64b\tasks\b30cohuxc.output')
t = p.read_text(encoding='utf-8', errors='replace')
keys = ['make_thumb', '[pipeline][FATAL]', 'Traceback', 'no CJK', 'SystemExit',
        'exited', '[build]', 'thumbnail', 'ModuleNotFound', 'Errno', 'python']
hits = []
for line in t.splitlines():
    low = line.lower()
    # ffmpeg banner / encode progress 除外
    if 'frame=' in line or '--enable' in line or 'libav' in low or 'configuration:' in low:
        continue
    if any(k.lower() in low for k in keys):
        hits.append(line.strip()[:160])
print(f'=== {len(hits)} 関連行 ===')
for h in hits[-40:]:
    print(h)
