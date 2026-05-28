#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""samurai / otona の refresh token を実機テスト"""
import sys, json, urllib.request, urllib.parse, urllib.error
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
env = {}
for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

print('=== presence ===')
for k in ['YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN',
          'OTONA_YOUTUBE_CLIENT_ID', 'OTONA_YOUTUBE_CLIENT_SECRET', 'OTONA_YOUTUBE_REFRESH_TOKEN']:
    print(f'  {k}: {"present" if env.get(k) else "MISSING"} (len={len(env.get(k,""))})')

def test_token(label, cid, csec, rtok):
    print(f'\n=== {label} ===')
    if not (cid and csec and rtok):
        print('  SKIP missing')
        return
    data = urllib.parse.urlencode({
        'client_id': cid, 'client_secret': csec,
        'refresh_token': rtok, 'grant_type': 'refresh_token',
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode())
            print(f'  OK len(access_token)={len(d.get("access_token",""))} expires_in={d.get("expires_in")}')
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f'  HTTP {e.code}: {body[:200]}')
    except Exception as e:
        print(f'  ERR: {e}')

test_token('samurai (YOUTUBE_*)',
           env.get('YOUTUBE_CLIENT_ID'),
           env.get('YOUTUBE_CLIENT_SECRET'),
           env.get('YOUTUBE_REFRESH_TOKEN'))
test_token('otona (OTONA_* or fallback)',
           env.get('OTONA_YOUTUBE_CLIENT_ID') or env.get('YOUTUBE_CLIENT_ID'),
           env.get('OTONA_YOUTUBE_CLIENT_SECRET') or env.get('YOUTUBE_CLIENT_SECRET'),
           env.get('OTONA_YOUTUBE_REFRESH_TOKEN'))
