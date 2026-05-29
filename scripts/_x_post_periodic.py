#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_x_post_periodic.py
===================
X (Twitter) に toi-suite/note/YouTube リンクを定期投稿。
GitHub Actions cron / Vercel Cron / Windows ScheduledTask から呼べる。

依存:
  pip install tweepy

環境変数:
  X_API_KEY
  X_API_SECRET
  X_ACCESS_TOKEN
  X_ACCESS_SECRET

使い方:
  python scripts/_x_post_periodic.py            # ランダム1件投稿
  python scripts/_x_post_periodic.py --dry-run  # 投稿せず内容だけ表示
  python scripts/_x_post_periodic.py --template 5  # テンプレ idx 指定
"""
import argparse, os, random, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')

# .env load (ローカル実行用、GitHub Actions では Secrets から渡る)
env_path = ROOT / '.env'
if env_path.exists():
    for line in env_path.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# テンプレート (URL は末尾固定)
URL_TOI = 'https://toi-suite.vercel.app/'
URL_NOTE = 'https://note.com/happy_happy_4649'
URL_YT_SAMURAI = 'https://www.youtube.com/@Japanese.Samurai.Channel'
URL_YT_OTONA = 'https://www.youtube.com/@Otona_Psychology'

TEMPLATES = [
    # 自己診断系
    f"あなたの侍性、可視化してみませんか?\n7問の無料診断で「決断力・洞察力・大義・精神力・適応力・規律心・自己理解」の6軸を可視化。\n{URL_TOI}#sample\n#200の問い #自己診断",
    f"死ぬ覚悟が生き残る道を開く──薩摩武士の哲学を、現代の問いに翻訳した自己分析。\n{URL_TOI}\n#苦徹成珠 #侍の美学",
    f"成熟した悩める大人へ。\n6軸レーダーで、自分の中の侍を見つける。\n{URL_TOI}\n#自己理解 #大人の学び",

    # 200の問い系
    f"心理学・古典・現代思想を「侍の視座」で再編した、200の問い。\n1問100円から、気になる問いだけ深掘りできる。\n{URL_NOTE}\n#200の問い",
    f"1日1問、自分を問い直す。\n200の問いから、今日のあなたに必要な一問を。\n{URL_TOI}\n#習慣化 #自己対話",

    # 音声ドラマ系
    f"【音声ドラマ】島津義弘 関ヶ原『捨て奸』の真相。\n薩摩武士の死生観が拓いた、敗戦の中の勝利。\n{URL_YT_SAMURAI}\n#日本史 #戦国",
    f"【音声ドラマ】直江兼続『愛』の兜が語る上杉家の哲学。\n義の上に重ねた一字の真意とは。\n{URL_YT_SAMURAI}\n#日本史 #上杉",
    f"【音声ドラマ】深夜のLINEが脳に焼き付く科学。\n睡眠導入期の感情記憶のメカニズム。\n{URL_YT_OTONA}\n#心理学 #大人の心理学",

    # 物語・思想系
    f"完璧な継続より、再開の早さが大事。\n問いとともに、また始める力を。\n{URL_TOI}\n#成長",
    f"言葉にならない感覚も、AIと対話すれば形になる。\n200の問いで自己理解を深める。\n{URL_NOTE}\n#AI対話",

    # アプリ系 (Phase 4 着手後に有効化)
    # f"家計簿から自己診断まで。お役立ち PWA 150 本パック登場予定。\n{URL_TOI}apps\n#PWA #便利アプリ",
]


def post_to_x(text, dry_run=False):
    print(f'[x-post] text ({len(text)} chars):\n{text}\n')
    if dry_run:
        print('[x-post] DRY-RUN (not posted)')
        return True
    try:
        import tweepy
    except ImportError:
        print('[x-post] ERR: tweepy not installed. pip install tweepy', file=sys.stderr)
        return False
    keys = [os.environ.get(k, '') for k in ('X_API_KEY', 'X_API_SECRET', 'X_ACCESS_TOKEN', 'X_ACCESS_SECRET')]
    if not all(keys):
        print('[x-post] ERR: X_API_KEY/SECRET/ACCESS_TOKEN/SECRET not set in env', file=sys.stderr)
        return False
    api_key, api_secret, access_token, access_secret = keys
    try:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        res = client.create_tweet(text=text)
        tid = res.data.get('id') if hasattr(res, 'data') else '?'
        print(f'[x-post] OK -> tweet id={tid}')
        return True
    except Exception as e:
        print(f'[x-post] FAIL: {e}', file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--template', type=int, help='テンプレ idx (0-based)')
    args = ap.parse_args()

    if args.template is not None:
        idx = args.template % len(TEMPLATES)
    else:
        idx = random.randint(0, len(TEMPLATES) - 1)

    text = TEMPLATES[idx]
    ok = post_to_x(text, dry_run=args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
