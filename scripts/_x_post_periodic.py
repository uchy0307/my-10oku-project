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
# 2026-05-30: URL を本文から除去 (X API URL 付き $0.200 → URL なし $0.015)。
# 月 180 投稿: $36 → $2.70。 リンク誘導は bio + ピン留めで集約。
# URL 定数は将来用に残置 (Basic tier 移行 or 別 SNS 切替時に復活可)。
URL_TOI = 'https://toi-suite.vercel.app/'
URL_NOTE = 'https://note.com/happy_happy_4649'
URL_YT_SAMURAI = 'https://www.youtube.com/@Japanese.Samurai.Channel'
URL_YT_OTONA = 'https://www.youtube.com/@Otona_Psychology'

TEMPLATES = [
    # 自己診断系
    "あなたの侍性、可視化してみませんか?\n7問の無料診断で「決断力・洞察力・大義・精神力・適応力・規律心・自己理解」の6軸を可視化。\nプロフィール固定リンクから ▶\n#200の問い #自己診断",
    "死ぬ覚悟が生き残る道を開く──薩摩武士の哲学を、現代の問いに翻訳した自己分析。\nBio のリンクから無料体験可。\n#苦徹成珠 #侍の美学",
    "成熟した悩める大人へ。\n6軸レーダーで、自分の中の侍を見つける。\nプロフィールから無料で 7 問。\n#自己理解 #大人の学び",

    # 200の問い系
    "心理学・古典・現代思想を「侍の視座」で再編した、200の問い。\n1問100円から、気になる問いだけ深掘り。\nプロフィールから note へ。\n#200の問い",
    "1日1問、自分を問い直す。\n200の問いから、今日のあなたに必要な一問を。\nプロフィール固定リンクから ▶\n#習慣化 #自己対話",

    # 音声ドラマ系
    "【音声ドラマ】島津義弘 関ヶ原『捨て奸』の真相。\n薩摩武士の死生観が拓いた、敗戦の中の勝利。\nプロフィールから YouTube へ。\n#日本史 #戦国",
    "【音声ドラマ】直江兼続『愛』の兜が語る上杉家の哲学。\n義の上に重ねた一字の真意とは。\nプロフィールから視聴可。\n#日本史 #上杉",
    "【音声ドラマ】深夜のLINEが脳に焼き付く科学。\n睡眠導入期の感情記憶のメカニズム。\nプロフィール → 大人の心理学 ch。\n#心理学 #大人の心理学",

    # 物語・思想系
    "完璧な継続より、再開の早さが大事。\n問いとともに、また始める力を。\nプロフィール固定リンクから ▶\n#成長",
    "言葉にならない感覚も、AIと対話すれば形になる。\n200の問いで自己理解を深める。\nプロフィールから無料体験 ▶\n#AI対話",

    # アプリ系 (Phase 4 着手後に有効化)
    # "家計簿から自己診断まで。お役立ち PWA 150 本パック登場予定。\nプロフィール固定リンクから ▶\n#PWA #便利アプリ",
]


def post_to_x(text, dry_run=False):
    import traceback
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
        missing = [n for n, v in zip(('X_API_KEY', 'X_API_SECRET', 'X_ACCESS_TOKEN', 'X_ACCESS_SECRET'), keys) if not v]
        print(f'[x-post] ERR: missing env vars: {missing}', file=sys.stderr)
        return False
    api_key, api_secret, access_token, access_secret = keys
    # 長さ確認 (空白/typo 検出用)
    print(f'[x-post] key lengths: api_key={len(api_key)} api_secret={len(api_secret)} '
          f'access_token={len(access_token)} access_secret={len(access_secret)}')
    print(f'[x-post] tweepy version: {tweepy.__version__}')
    print(f'[x-post] api_key first/last 2: {api_key[:2]}...{api_key[-2:]}')
    print(f'[x-post] access_token first/last 2: {access_token[:2]}...{access_token[-2:]}')
    # 検証: token 内に「-」 (アクセストークンの ID 部区切り) が含まれるか
    if '-' not in access_token:
        print('[x-post] WARN: access_token に「-」がない (本物の Access Token は通常 数字-英数字_... 形式)', file=sys.stderr)
    try:
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        # 2026-05-30: user_auth=True 明示 (tweepy >= 4.10 で OAuth 1.0a User Context 確実化)
        res = client.create_tweet(text=text, user_auth=True)
        tid = res.data.get('id') if hasattr(res, 'data') else '?'
        print(f'[x-post] OK -> tweet id={tid}')
        return True
    except Exception as e:
        print(f'[x-post] FAIL: {type(e).__name__}: {e}', file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            try:
                print(f'[x-post] HTTP status: {e.response.status_code}', file=sys.stderr)
                print(f'[x-post] response body:\n{e.response.text[:3000]}', file=sys.stderr)
                print(f'[x-post] response headers (relevant):', file=sys.stderr)
                for h in ('x-rate-limit-limit', 'x-rate-limit-remaining', 'x-rate-limit-reset', 'www-authenticate'):
                    v = e.response.headers.get(h)
                    if v:
                        print(f'  {h}: {v}', file=sys.stderr)
            except Exception as inner:
                print(f'[x-post] (failed to extract response details: {inner})', file=sys.stderr)
        if hasattr(e, 'api_codes'):
            print(f'[x-post] api_codes: {e.api_codes}', file=sys.stderr)
        if hasattr(e, 'api_messages'):
            print(f'[x-post] api_messages: {e.api_messages}', file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
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
