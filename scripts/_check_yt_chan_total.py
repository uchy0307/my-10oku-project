#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""yt-dlp チャンネル全件取得テスト。local_button_server._fetch_yt_chan_total と同等。"""
import subprocess, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CHANS = [
    ('@Japanese.Samurai.Channel', 'samurai'),
    ('@Otona_Psychology', 'otona'),
]

for handle, label in CHANS:
    print(f'\n=== {label} {handle} ===')
    t0 = time.time()
    args = [
        sys.executable, '-m', 'yt_dlp',
        '--flat-playlist',
        '--print', '%(id)s',
        '--encoding', 'utf-8',
        '--no-warnings',
        f'https://www.youtube.com/{handle}/videos',
    ]
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    except subprocess.TimeoutExpired:
        print(f'TIMEOUT after {time.time()-t0:.1f}s')
        continue
    except Exception as e:
        print(f'EXCEPTION: {e}')
        continue
    elapsed = time.time() - t0
    count = sum(1 for line in (r.stdout or '').splitlines() if line.strip())
    print(f'elapsed: {elapsed:.1f}s')
    print(f'returncode: {r.returncode}')
    print(f'count: {count}')
    if r.returncode != 0 or count == 0:
        print(f'stderr_tail:\n{(r.stderr or "")[-1500:]}')
