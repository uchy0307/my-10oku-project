#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本日 5/29 投稿の 17 video を YouTube API で実機確認。
- 各 video の uploadStatus / privacyStatus / processingStatus
- 現在のタイトル
- ハルシネーションだった分の特定
"""
import sys, json, urllib.request, urllib.parse, urllib.error
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
CID = env['YOUTUBE_CLIENT_ID']
CSEC = env['YOUTUBE_CLIENT_SECRET']

def access_token(refresh):
    data = urllib.parse.urlencode({
        'client_id': CID, 'client_secret': CSEC,
        'refresh_token': refresh, 'grant_type': 'refresh_token',
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST')
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())['access_token']

def list_videos(access, ids):
    """video IDs (max 50) を list で取得"""
    params = urllib.parse.urlencode({
        'part': 'status,snippet,processingDetails,contentDetails',
        'id': ','.join(ids),
    })
    req = urllib.request.Request(
        f'https://www.googleapis.com/youtube/v3/videos?{params}',
        headers={'Authorization': f'Bearer {access}'},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f'HTTP {e.code}: {body[:500]}')
        return None

# 5/29 投稿リスト
SAMURAI_VIDS = {
    '009': 'fJSZD7HIlvM',  # 北条早雲
    '010': 'AXLpf9T3de4',  # 真田幸村
    '016': 'r7rDJLj2Mpk',  # 壇ノ浦
    '002_peak': 'q_OMGsFvO6w',  # short
    '003_peak': 'cR5px2ADqQc',
    '004_peak': 'qNab7CUsDHk',
    '005_peak': 'XdZ220-4Ekw',
    '006_peak': 'NQQqBpkiHPw',
}
OTONA_VIDS = {
    '004': 'LAVSg_jvnkY',  # 心理的安全性
    '006': 'CCgFjnDlxvM',  # 言葉にしない愛情
    '007': 'OdK_Z-qOWOY',  # psych 007 ← suspect
    '010_otona_short': 'RZq9llbHwdg',  # ← suspect
    '012_otona_short': 'xRwsoaLG9CQ',
    '014_otona_short': 'sFSwoJXuDWA',
    '015_otona_short': 'Fdura5dH4Qw',
    '016_otona_short': 'xtQde66p21M',
    '017_otona_short': 'uBb3WoHgb0E',
}


def report(label, refresh, mapping):
    print(f'\n=== {label} ===')
    token = access_token(refresh)
    data = list_videos(token, list(mapping.values()))
    if not data:
        print('FAIL: no data')
        return
    by_id = {it['id']: it for it in data.get('items', [])}
    for local_idx, vid in mapping.items():
        it = by_id.get(vid)
        if not it:
            print(f'{local_idx:24s} {vid} → NOT FOUND (deleted/private?)')
            continue
        s = it.get('status', {})
        sn = it.get('snippet', {})
        pd = it.get('processingDetails', {}) or {}
        title = sn.get('title', '')[:60]
        upload_status = s.get('uploadStatus', '?')
        privacy = s.get('privacyStatus', '?')
        proc = pd.get('processingStatus', '?')
        failure = s.get('failureReason', '')
        rejection = s.get('rejectionReason', '')
        cat = sn.get('categoryId', '?')
        flag = ''
        if upload_status != 'processed': flag += ' [UPLOAD-' + upload_status + ']'
        if privacy != 'public': flag += ' [' + privacy + ']'
        if failure: flag += ' [FAIL:' + failure + ']'
        if rejection: flag += ' [REJ:' + rejection + ']'
        print(f'{local_idx:24s} {vid} cat={cat} {upload_status}/{privacy} proc={proc}{flag}')
        print(f'  title: {title}')


report('SAMURAI (samurai refresh)', env['YOUTUBE_REFRESH_TOKEN'], SAMURAI_VIDS)
report('OTONA (otona refresh)', env['OTONA_YOUTUBE_REFRESH_TOKEN'], OTONA_VIDS)
