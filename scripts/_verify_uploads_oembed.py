#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
oEmbed (匿名公開 API) で各 video の公開状態 + 実タイトルを取得。
- 200 + title 取得 = 公開済
- 401/403/404 = 未公開 (= upload 失敗 or private)
"""
import sys, json, urllib.request, urllib.parse, urllib.error
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

VIDS = {
    'samurai 長尺 009 北条早雲':       'fJSZD7HIlvM',
    'samurai 長尺 010 真田幸村':       'AXLpf9T3de4',
    'samurai 長尺 016 壇ノ浦':         'r7rDJLj2Mpk',
    'samurai short 002_peak':         'q_OMGsFvO6w',
    'samurai short 003_peak':         'cR5px2ADqQc',
    'samurai short 004_peak':         'qNab7CUsDHk',
    'samurai short 005_peak':         'XdZ220-4Ekw',
    'samurai short 006_peak':         'NQQqBpkiHPw',
    'otona 長尺 004 心理的安全性':     'LAVSg_jvnkY',
    'otona 長尺 006 言葉にしない愛情': 'CCgFjnDlxvM',
    'otona 長尺 007 psych 007':        'OdK_Z-qOWOY',
    'otona short 010 (otona_shorts 010)': 'RZq9llbHwdg',
    'otona short 012':                'xRwsoaLG9CQ',
    'otona short 014':                'sFSwoJXuDWA',
    'otona short 015':                'Fdura5dH4Qw',
    'otona short 016':                'xtQde66p21M',
    'otona short 017':                'uBb3WoHgb0E',
}

def probe(vid):
    url = f'https://www.youtube.com/oembed?url=https%3A//youtu.be/{vid}&format=json'
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read())
            return True, d.get('title', ''), d.get('type', ''), d.get('author_name', '')
    except urllib.error.HTTPError as e:
        return False, f'HTTP {e.code}', '', ''
    except Exception as e:
        return False, str(e), '', ''

print(f'{"label":40s} {"vid":13s}  status  title')
print('-' * 110)
for label, vid in VIDS.items():
    ok, info, typ, author = probe(vid)
    status = 'PUBLIC' if ok else 'FAIL'
    title = info[:60] if ok else info[:60]
    print(f'{label:40s} {vid:13s}  {status:6s}  {title}')
    if ok:
        print(f'{"":40s} {"":13s}          author={author}')
