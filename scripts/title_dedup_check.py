#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
title_dedup_check.py
====================
新規タイトル候補が、過去投稿/ストック中の既存タイトルと類似していないかチェック。

Usage:
  # exit 0 = OK, exit 1 = REJECT (類似タイトル発見)
  python scripts/title_dedup_check.py --title "新タイトル候補" --threshold 0.7

  # 既存タイトル DB 確認 (デバッグ用)
  python scripts/title_dedup_check.py --list

DB 構築元:
  - youtube/<kind>_v2/uploaded.json (投稿済タイトル)
  - youtube/<kind>_v2/scripts/*.json (ストック中タイトル)
  - youtube/<kind>_shorts_v2/uploaded.json (ショート投稿済)
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')

SOURCES = [
    ROOT / 'youtube' / 'history_v2',
    ROOT / 'youtube' / 'psych_v2',
    ROOT / 'youtube' / 'history_shorts_v2',
    ROOT / 'youtube' / 'psych_shorts_v2',
    ROOT / 'youtube' / 'shorts_v2',
    ROOT / 'youtube' / 'otona_shorts_v2',
]


def normalize_title(s):
    """記号・空白除去 + 小文字化"""
    s = (s or '').strip()
    s = re.sub(r'[「」『』【】（）\(\)\[\]、,。\.！\!？\?〜~ー\-—–　 \t\n#]', '', s)
    return s.lower()


def bigrams(s):
    """2-gram 集合 (Jaccard 用)"""
    s = normalize_title(s)
    if len(s) < 2:
        return set()
    return set(s[i:i + 2] for i in range(len(s) - 1))


def jaccard(a, b):
    sa, sb = bigrams(a), bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def collect_existing_titles():
    titles = []
    for ch in SOURCES:
        if not ch.exists():
            continue
        # uploaded.json
        up = ch / 'uploaded.json'
        if up.exists():
            try:
                data = json.loads(up.read_text(encoding='utf-8'))
                for v in data.values():
                    t = v.get('title', '')
                    if t:
                        titles.append({'title': t, 'source': f'{ch.name}/uploaded'})
            except Exception:
                pass
        # scripts/*.json (ストック)
        scripts_dir = ch / 'scripts'
        if scripts_dir.exists():
            for f in scripts_dir.glob('*.json'):
                try:
                    j = json.loads(f.read_text(encoding='utf-8'))
                    t = j.get('title', '')
                    if t:
                        titles.append({'title': t, 'source': f'{ch.name}/{f.name}'})
                except Exception:
                    pass
    return titles


def check(title, threshold):
    existing = collect_existing_titles()
    matches = []
    for e in existing:
        sim = jaccard(title, e['title'])
        if sim >= threshold:
            matches.append((sim, e))
    matches.sort(reverse=True, key=lambda x: x[0])
    return matches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--title')
    ap.add_argument('--threshold', type=float, default=0.7)
    ap.add_argument('--list', action='store_true', help='print all known titles and exit')
    args = ap.parse_args()

    if args.list:
        titles = collect_existing_titles()
        print(f'total known titles: {len(titles)}')
        for t in titles:
            print(f'  [{t["source"]}] {t["title"]}')
        sys.exit(0)

    if not args.title:
        print('--title required (or --list)', file=sys.stderr)
        sys.exit(2)

    matches = check(args.title, args.threshold)
    if matches:
        print(f'REJECT: similar titles found (threshold={args.threshold}):')
        for sim, e in matches[:5]:
            print(f'  [{sim:.2f}] [{e["source"]}] {e["title"]}')
        sys.exit(1)
    else:
        print(f'OK: no similar title (threshold={args.threshold})')
        sys.exit(0)


if __name__ == '__main__':
    main()
