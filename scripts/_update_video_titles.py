#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_update_video_titles.py
=======================
既投稿動画のタイトル/説明を script JSON の正しい値に書き換える。
OAuth scope youtube.force-ssl が必要 (既存 youtube.upload のみでは不足)。

事前作業 (うっちー様):
  1. https://developers.google.com/oauthplayground/ で再 authorize
  2. scope: youtube.upload + youtube.force-ssl 両方チェック
  3. samurai (歴史) + otona (大人) 両アカウントで取得
  4. .env の YOUTUBE_REFRESH_TOKEN と OTONA_YOUTUBE_REFRESH_TOKEN を新値に置換
  5. python scripts/_oauth_test.py で動作確認

実行:
  python scripts/_update_video_titles.py            # dry-run
  python scripts/_update_video_titles.py --apply    # 実適用
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
        'client_id':     env['YOUTUBE_CLIENT_ID'],
        'client_secret': env['YOUTUBE_CLIENT_SECRET'],
        'refresh_token': refresh,
        'grant_type':    'refresh_token',
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST')
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())['access_token']


def get_video(token, vid):
    """videos.list で現在の snippet 取得 (categoryId 等 keeping needed)"""
    req = urllib.request.Request(
        f'https://www.googleapis.com/youtube/v3/videos?part=snippet,status&id={vid}',
        headers={'Authorization': f'Bearer {token}'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    items = d.get('items', [])
    return items[0] if items else None


def update_video(token, vid, new_title, new_description, tags, category_id):
    body = json.dumps({
        'id': vid,
        'snippet': {
            'title':       new_title[:95],
            'description': new_description[:4500],
            'tags':        tags[:15],
            'categoryId':  category_id,
            'defaultLanguage':      'ja',
            'defaultAudioLanguage': 'ja',
        },
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://www.googleapis.com/youtube/v3/videos?part=snippet',
        data=body, method='PUT',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type':  'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return False, e.read().decode('utf-8', errors='replace')[:500]


# 修正対象: 公開済 + プレースホルダータイトル
TARGETS = [
    # (channel, video_id, local_script_path, category_id, default_tags)
    ('otona', 'OdK_Z-qOWOY',
     'youtube/psych_v2/scripts/psych_007.json', '27', ['心理学', '大人', 'AI対話']),
    ('otona', 'RZq9llbHwdg',
     'youtube/otona_shorts_v2/scripts/short_010.json', '27', ['Shorts', '心理学']),
    ('otona', 'xRwsoaLG9CQ',
     'youtube/otona_shorts_v2/scripts/short_012.json', '27', ['Shorts', '心理学']),
    ('otona', 'sFSwoJXuDWA',
     'youtube/otona_shorts_v2/scripts/short_014.json', '27', ['Shorts', '心理学']),
    ('otona', 'Fdura5dH4Qw',
     'youtube/otona_shorts_v2/scripts/short_015.json', '27', ['Shorts', '心理学']),
    ('otona', 'xtQde66p21M',
     'youtube/otona_shorts_v2/scripts/short_016.json', '27', ['Shorts', '心理学']),
    ('otona', 'uBb3WoHgb0E',
     'youtube/otona_shorts_v2/scripts/short_017.json', '27', ['Shorts', '心理学']),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='実行 (なしは dry-run)')
    args = ap.parse_args()

    samurai_tok = access_token(env['YOUTUBE_REFRESH_TOKEN'])
    otona_tok   = access_token(env['OTONA_YOUTUBE_REFRESH_TOKEN'])

    print(f'=== {"APPLY" if args.apply else "DRY-RUN"} mode ===\n')

    for ch, vid, spec_rel, cat, default_tags in TARGETS:
        spec_path = ROOT / spec_rel
        if not spec_path.exists():
            print(f'SKIP {ch}/{vid}: spec missing {spec_rel}')
            continue
        try:
            spec = json.loads(spec_path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'SKIP {ch}/{vid}: spec parse fail: {e}')
            continue

        new_title = (spec.get('title') or '').strip()
        new_desc  = (spec.get('description') or '').strip()
        tags      = spec.get('tags', []) or default_tags
        if not new_title:
            print(f'SKIP {ch}/{vid}: empty new title')
            continue

        # Shorts なら description に #Shorts 付与
        if 'short' in spec_rel.lower():
            if '#Shorts' not in new_desc and '#shorts' not in new_desc:
                new_desc = (new_desc + '\n\n#Shorts').strip()

        token = samurai_tok if ch == 'samurai' else otona_tok
        cur = get_video(token, vid)
        cur_title = cur.get('snippet', {}).get('title', '?') if cur else '<not found>'

        print(f'{ch} {vid}')
        print(f'  before: {cur_title[:70]}')
        print(f'  after:  {new_title[:70]}')
        if not args.apply:
            print(f'  (dry-run skip)')
            continue

        ok, body = update_video(token, vid, new_title, new_desc, tags, cat)
        if ok:
            print(f'  -> OK')
        else:
            print(f'  -> FAIL: {body}')


if __name__ == '__main__':
    main()
