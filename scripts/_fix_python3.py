#!/usr/bin/env python3
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for p in [Path('youtube/history_v2/pipeline.mjs'), Path('youtube/psych_v2/pipeline.mjs')]:
    c = p.read_text(encoding='utf-8')
    new = c.replace('python3 ', 'python ')
    p.write_text(new, encoding='utf-8')
    print(f'{p.name}: replaced (had {c.count("python3 ")})')
