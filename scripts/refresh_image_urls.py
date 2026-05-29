#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
refresh_image_urls.py
=====================
youtube/history_v2/scripts/long_*.json の image_urls を Wikipedia API で
自動再取得・置換する。失効した image_urls 問題の根本解決。

Strategy:
  1. 各 long_*.json の title から検索キーワード抽出 (例: 「島津義弘」「関ヶ原」)
  2. Wikipedia REST API でページの主要画像 (originalimage) を取得
  3. さらに Commons API で関連画像を取得 (8-12 枚目標)
  4. HTTP HEAD で URL 生存確認
  5. 全部 OK な image_urls 配列で long_*.json を上書き

Usage:
  python scripts/refresh_image_urls.py --kind history --all
  python scripts/refresh_image_urls.py --kind history --index 009
"""
import sys, json, urllib.request, urllib.parse, argparse, time, re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
UA = 'Mozilla/5.0 (10oku-refresh-bot/1.0; mailto:uchiyamatakayuki0307@gmail.com)'

def fetch_url(url, timeout=10):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def head_ok(url, timeout=8):
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ct = r.headers.get('Content-Type', '')
            return r.status == 200 and ('image' in ct or url.endswith(('.jpg','.png','.webp','.jpeg')))
    except Exception:
        return False

def extract_keywords(title):
    """title から検索キーワード候補を抽出"""
    # 「島津義弘 関ヶ原『敵中突破』完全版｜...」 → ['島津義弘', '関ヶ原']
    title_clean = re.sub(r'[｜「」『』【】\(\)（）]', ' ', title)
    parts = title_clean.split()
    return [p for p in parts if len(p) >= 2][:3]  # 上位3キーワード

def search_commons_images(keyword, limit=15):
    """Wikimedia Commons で画像検索 → URL list"""
    url = f'https://commons.wikimedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(keyword)}&srnamespace=6&format=json&srlimit={limit}'
    try:
        data = json.loads(fetch_url(url))
        titles = [it['title'] for it in data.get('query', {}).get('search', [])]
        urls = []
        for t in titles:
            if not t.startswith('File:'):
                continue
            filename = t[5:]
            # Special:FilePath URL (直接画像にリダイレクト)
            urls.append(f'https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(filename)}')
        return urls
    except Exception as e:
        print(f'  search fail "{keyword}": {e}')
        return []

def refresh_one(script_path):
    spec = json.loads(script_path.read_text(encoding='utf-8'))
    title = spec.get('title', '')
    old_urls = spec.get('image_urls', [])

    print(f'\n=== {script_path.name}: {title[:40]} ===')
    print(f'  old: {len(old_urls)} urls')

    keywords = extract_keywords(title)
    print(f'  keywords: {keywords}')

    new_urls = []
    seen = set()
    for kw in keywords:
        if len(new_urls) >= 12: break
        candidates = search_commons_images(kw, 15)
        time.sleep(0.5)  # API 礼儀
        for u in candidates:
            if len(new_urls) >= 12: break
            if u in seen: continue
            seen.add(u)
            if head_ok(u):
                new_urls.append(u)
                print(f'  OK: {u}')
            time.sleep(0.2)

    if len(new_urls) < 6:
        print(f'  WARN: only {len(new_urls)} urls found (need >=6) - keeping old + new')
        new_urls = list(set(new_urls + old_urls))

    spec['image_urls'] = new_urls
    backup = script_path.with_suffix(script_path.suffix + '.urls_bak')
    if not backup.exists():
        backup.write_text(json.dumps({'image_urls': old_urls}, ensure_ascii=False, indent=2), encoding='utf-8')
    script_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  new: {len(new_urls)} urls written')
    return len(new_urls)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', choices=['history', 'psych'], required=True)
    ap.add_argument('--index')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--start', help='start index (e.g. 009)')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    if args.kind == 'history':
        scripts_dir = ROOT / 'youtube' / 'history_v2' / 'scripts'
        prefix = 'long_'
    else:
        scripts_dir = ROOT / 'youtube' / 'psych_v2' / 'scripts'
        prefix = 'psych_'

    if args.index:
        target = scripts_dir / f'{prefix}{args.index}.json'
        if not target.exists():
            print(f'NOT FOUND: {target}')
            sys.exit(1)
        refresh_one(target)
    elif args.all:
        files = sorted(scripts_dir.glob(f'{prefix}*.json'))
        if args.start:
            files = [f for f in files if f.stem >= f'{prefix}{args.start}']
        if args.limit > 0:
            files = files[:args.limit]
        for f in files:
            try:
                refresh_one(f)
            except Exception as e:
                print(f'FAIL {f.name}: {e}')

if __name__ == '__main__':
    main()
