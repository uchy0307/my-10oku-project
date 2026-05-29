#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_dashboard.py
=============
全 4 チャンネル投稿状況 + プレースホルダー検知 + 在庫サマリを集約。
出力: scripts/logs/dashboard.json (pc.uchy0307.uk から閲覧可能、スマホ確認用)

実行:
  python scripts/_dashboard.py
"""
import json, sys, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
JST = timezone(timedelta(hours=9))
PLACEHOLDER_RE = __import__('re').compile(
    r'^(?:Shorts|history|psych|otona_shorts|history_shorts|psych_shorts)\s+\d{3}',
    __import__('re').IGNORECASE,
)

CHANNELS = [
    ('history_v2',       'long',  '@Japanese.Samurai.Channel'),
    ('psych_v2',         'long',  '@Otona_Psychology'),
    ('history_shorts_v2','short', '@Japanese.Samurai.Channel'),
    ('psych_shorts_v2',  'short', '@Otona_Psychology'),
    ('shorts_v2',        'short', '@Japanese.Samurai.Channel'),
    ('otona_shorts_v2',  'short', '@Otona_Psychology'),
]


def probe_oembed(vid):
    """oEmbed で公開状態確認"""
    url = f'https://www.youtube.com/oembed?url=https%3A//youtu.be/{vid}&format=json'
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            d = json.loads(r.read())
            return True, d.get('title', '')
    except urllib.error.HTTPError as e:
        return False, f'HTTP {e.code}'
    except Exception:
        return False, 'timeout'


def channel_report(dir_name, mode, handle):
    root = ROOT / 'youtube' / dir_name
    out = {
        'channel_dir':  dir_name,
        'youtube_handle': handle,
        'mode':         mode,
        'uploaded':     0,
        'placeholder':  [],
        'failed':       [],
        'titles':       {},
        'stock_built':  0,    # output.mp4 がある未投稿
        'stock_scripts':0,    # 台本 JSON 数
        'stock_audio':  0,
    }
    if not root.exists():
        return out

    up_path = root / 'uploaded.json'
    if up_path.exists():
        try:
            db = json.loads(up_path.read_text(encoding='utf-8'))
        except Exception:
            db = {}
        out['uploaded'] = len(db)
        for idx, meta in db.items():
            t = (meta.get('title') or '').strip()
            out['titles'][idx] = t
            if PLACEHOLDER_RE.match(t):
                out['placeholder'].append({'idx': idx, 'title': t, 'videoId': meta.get('videoId')})

    # script + audio 在庫
    scripts_dir = root / 'scripts'
    audio_dir = root / 'audio'
    if scripts_dir.exists():
        out['stock_scripts'] = len(list(scripts_dir.glob('*.json')))
    if audio_dir.exists():
        out['stock_audio'] = len(list(audio_dir.glob('*.mp3')))

    # 完成 MP4 (.work と .work_quarantine)
    work = root / '.work'
    quar = root / '.work_quarantine'
    built = set()
    for d in [work, quar]:
        if d.exists():
            for p in d.glob('*/output.mp4'):
                if p.stat().st_size > 100_000:
                    built.add(p.parent.name)
    uploaded_keys = set()
    if up_path.exists():
        try:
            uploaded_keys = set(json.loads(up_path.read_text(encoding='utf-8')).keys())
        except Exception:
            pass
    out['stock_built'] = len(built - uploaded_keys)
    return out


def main():
    reports = []
    for d, m, h in CHANNELS:
        reports.append(channel_report(d, m, h))

    total_uploaded = sum(r['uploaded'] for r in reports)
    total_placeholder = sum(len(r['placeholder']) for r in reports)
    total_built = sum(r['stock_built'] for r in reports)

    summary = {
        'generated_at': datetime.now(JST).isoformat(),
        'total_uploaded':    total_uploaded,
        'total_placeholder': total_placeholder,
        'total_built_unposted': total_built,
        'channels': reports,
    }

    out_path = ROOT / 'scripts' / 'logs' / 'dashboard.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    # コンソール出力
    print(f'=== dashboard {summary["generated_at"]} ===')
    print(f'total uploaded:    {total_uploaded}')
    print(f'total placeholder: {total_placeholder} ⚠️' if total_placeholder else f'total placeholder: 0 ✅')
    print(f'total built unposted: {total_built}')
    print()
    for r in reports:
        flag = '⚠️' if r['placeholder'] else '✅'
        print(f'{flag} {r["channel_dir"]:24s} uploaded={r["uploaded"]:3d}  placeholder={len(r["placeholder"]):2d}  built_unposted={r["stock_built"]:3d}  scripts={r["stock_scripts"]:3d}  audio={r["stock_audio"]:3d}')
        if r['placeholder']:
            for p in r['placeholder']:
                print(f'    ⚠️ {p["idx"]:8s} "{p["title"]}" → https://youtube.com/watch?v={p["videoId"]}')
    print()
    print(f'JSON written: {out_path}')


if __name__ == '__main__':
    main()
