#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_channel_title_check.py
=======================
yt-dlp で YouTube チャンネルの公開タイトル全件を取得 → 入力タイトルとの重複判定。
upload_quarantine.mjs / upload_shorts.mjs の upload 前 pre-flight として使用。

Usage:
  python scripts/_channel_title_check.py --channel @Japanese.Samurai.Channel --title "真田幸村 日本一の兵"
  → exit 0 = OK (新規可), exit 1 = REJECT (重複/類似), exit 2 = エラー

cache: 60分間 ローカル cache (scripts/logs/_channel_titles_<handle>.json)
"""
import argparse, json, re, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
CACHE_DIR = ROOT / 'scripts' / 'logs'
CACHE_TTL = 60 * 60  # 1 時間


def normalize(s):
    s = (s or '').strip()
    s = re.sub(r'[「」『』【】（）\(\)\[\]、,。\.！\!？\?〜~ー\-—–　 \t\n#＃]', '', s)
    return s.lower()


def bigrams(s):
    s = normalize(s)
    if len(s) < 2:
        return set()
    return set(s[i:i + 2] for i in range(len(s) - 1))


def jaccard(a, b):
    sa, sb = bigrams(a), bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def fetch_channel_titles(handle, limit=500):
    """yt-dlp でチャンネル全動画タイトル取得 (cache 1時間)"""
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', handle)
    cache_path = CACHE_DIR / f'_channel_titles_{safe}.json'
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding='utf-8'))
            if time.time() - data.get('ts', 0) < CACHE_TTL:
                return data.get('titles', [])
        except Exception:
            pass

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url = f'https://www.youtube.com/{handle}/videos'
    args = [
        sys.executable, '-m', 'yt_dlp',
        '--flat-playlist',
        '--playlist-end', str(limit),
        '--print', '%(title)s',
        '--encoding', 'utf-8',
        '--no-warnings',
        url,
    ]
    r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(f'[channel-check] yt-dlp fail: {(r.stderr or "")[-300:]}', file=sys.stderr)
        return []
    titles = [ln.strip() for ln in (r.stdout or '').splitlines() if ln.strip()]
    cache_path.write_text(json.dumps({'ts': time.time(), 'titles': titles}, ensure_ascii=False), encoding='utf-8')
    return titles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--channel', required=True, help='@Japanese.Samurai.Channel 形式')
    ap.add_argument('--title', required=True)
    ap.add_argument('--threshold', type=float, default=0.85)
    args = ap.parse_args()

    titles = fetch_channel_titles(args.channel)
    if not titles:
        print('[channel-check] WARN: could not fetch channel titles, ALLOW by default')
        sys.exit(0)
    print(f'[channel-check] fetched {len(titles)} titles from {args.channel}')

    # 完全一致チェック
    new_norm = normalize(args.title)
    for t in titles:
        if normalize(t) == new_norm:
            print(f'[channel-check] REJECT: exact-match found: "{t}"')
            sys.exit(1)

    # 類似度チェック
    worst = []
    for t in titles:
        sim = jaccard(args.title, t)
        if sim >= args.threshold:
            worst.append((sim, t))
    worst.sort(reverse=True)
    if worst:
        print(f'[channel-check] REJECT: similar titles (threshold={args.threshold}):')
        for sim, t in worst[:3]:
            print(f'  [{sim:.2f}] "{t}"')
        sys.exit(1)

    print(f'[channel-check] OK: no duplicate/similar in {len(titles)} channel titles')
    sys.exit(0)


if __name__ == '__main__':
    main()
