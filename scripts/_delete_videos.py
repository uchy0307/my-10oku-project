#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_delete_videos.py
=================
重複タイトルで自動 reject された歴史 010/016 を削除し、uploaded.json から
該当 idx を消す。直後に upload_quarantine.mjs --kind history --count 2 で
新タイトル (long_010/016.json の更新済 title) で再アップロード可能。

要件: OAuth scope youtube.force-ssl (再 authorize 後)

実行:
  python scripts/_delete_videos.py            # dry-run
  python scripts/_delete_videos.py --apply    # 実適用
"""
import argparse, json, sys, urllib.request, urllib.parse, urllib.error
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')

def load_env():
    env = {}
    for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

env = load_env()

def access_token(refresh):
    data = urllib.parse.urlencode({
        'client_id': env['YOUTUBE_CLIENT_ID'],
        'client_secret': env['YOUTUBE_CLIENT_SECRET'],
        'refresh_token': refresh,
        'grant_type': 'refresh_token',
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST')
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())['access_token']


def delete_video(token, vid):
    req = urllib.request.Request(
        f'https://www.googleapis.com/youtube/v3/videos?id={vid}',
        method='DELETE',
        headers={'Authorization': f'Bearer {token}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:400]
        return False, f'HTTP {e.code}: {body}'


# 削除対象: 重複タイトルで YouTube 自動 reject された/欲しくない動画
TARGETS = [
    # (channel, video_id, local_idx, channel_dir)
    ('samurai', 'AXLpf9T3de4', '010', 'history_v2'),  # 真田幸村 (重複 → 新タイトルで再投稿予定)
    ('samurai', 'r7rDJLj2Mpk', '016', 'history_v2'),  # 壇ノ浦 (同上)
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    samurai_tok = access_token(env['YOUTUBE_REFRESH_TOKEN'])
    otona_tok   = access_token(env['OTONA_YOUTUBE_REFRESH_TOKEN'])

    print(f'=== {"APPLY" if args.apply else "DRY-RUN"} mode ===\n')

    for ch, vid, idx, ch_dir in TARGETS:
        token = samurai_tok if ch == 'samurai' else otona_tok
        print(f'{ch} {vid} (idx={idx}, dir={ch_dir})')
        if not args.apply:
            print('  (dry-run skip)')
            continue

        ok, info = delete_video(token, vid)
        print(f'  delete: {"OK" if ok else "FAIL"} {info if not ok else ""}')

        if ok:
            up_path = ROOT / 'youtube' / ch_dir / 'uploaded.json'
            if up_path.exists():
                db = json.loads(up_path.read_text(encoding='utf-8'))
                if idx in db:
                    del db[idx]
                    up_path.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')
                    print(f'  uploaded.json: removed {idx}')


if __name__ == '__main__':
    main()
