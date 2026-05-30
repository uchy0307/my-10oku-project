#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""X (Twitter) プロフィール一括更新 (2026-05-30 案 A 漆黒+金箔)。

更新内容:
  1. 表示名: 「苦徹成珠 ─ 侍の美学」
  2. Bio (110字)
  3. ウェブサイト URL: toi-suite.vercel.app
  4. アバター画像 (assets/x_branding/avatar.png があれば)
  5. バナー画像 (assets/x_branding/banner.png があれば)
  6. ピン留めツイート投稿 (固定設定は X 管理画面で手動)

必要環境変数 (.env or GitHub Secrets 経由):
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET

使い方:
  python scripts/_x_profile_update.py            # 全部更新
  python scripts/_x_profile_update.py --dry-run  # 更新内容だけ表示
  python scripts/_x_profile_update.py --skip-pin # ピン留め投稿スキップ
"""
import argparse, os, sys
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r'C:\Users\user\Documents\10oku-project')

# .env load
env_path = ROOT / '.env'
if env_path.exists():
    for line in env_path.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


NEW_NAME = '苦徹成珠 ─ 侍の美学'

NEW_BIO = (
    '侍の美学で、現代の悩みを問い直す。\n'
    '心理学 × 古典 × 200の問い。\n'
    '6軸自己診断 + 音声ドラマ + 便利アプリ150本予定。\n'
    '無料で7問 → あなたの中の侍を可視化。\n'
    '#苦徹成珠 #自己診断'
)

NEW_URL = 'https://toi-suite.vercel.app/'

BANNER_PATH = ROOT / 'assets' / 'x_branding' / 'banner.png'
AVATAR_PATH = ROOT / 'assets' / 'x_branding' / 'avatar.png'

PINNED_TEXT = (
    'あなたの侍性、可視化してみませんか?\n\n'
    '7問の無料診断で「決断力・洞察力・大義・精神力・適応力・規律心・自己理解」の6軸を可視化。\n\n'
    '無料体験 → https://toi-suite.vercel.app/\n\n'
    '#200の問い #自己診断 #苦徹成珠'
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='更新内容のみ表示、実 API 叩かない')
    ap.add_argument('--skip-pin', action='store_true', help='ピン留めツイート投稿スキップ')
    ap.add_argument('--skip-image', action='store_true', help='画像 upload スキップ (テキストのみ)')
    args = ap.parse_args()

    if args.dry_run:
        print('=' * 60)
        print('DRY-RUN: 以下の内容で X プロフィール更新予定')
        print('=' * 60)
        print(f'\n[表示名] {NEW_NAME}')
        print(f'\n[Bio]\n{NEW_BIO}')
        print(f'\n[URL] {NEW_URL}')
        print(f'\n[アバター] {AVATAR_PATH} (exists={AVATAR_PATH.exists()})')
        print(f'\n[バナー] {BANNER_PATH} (exists={BANNER_PATH.exists()})')
        print(f'\n[ピン留め ツイート]\n{PINNED_TEXT}')
        return 0

    try:
        import tweepy
    except ImportError:
        print('[FATAL] tweepy 未導入。 pip install tweepy', file=sys.stderr)
        return 1

    keys = [os.environ.get(k, '') for k in ('X_API_KEY', 'X_API_SECRET', 'X_ACCESS_TOKEN', 'X_ACCESS_SECRET')]
    if not all(keys):
        missing = [n for n, v in zip(('X_API_KEY', 'X_API_SECRET', 'X_ACCESS_TOKEN', 'X_ACCESS_SECRET'), keys) if not v]
        print(f'[FATAL] env vars 不足: {missing}', file=sys.stderr)
        print('       → .env に X_API_KEY 等を追記 (4 つ)', file=sys.stderr)
        return 1
    api_key, api_secret, access_token, access_secret = keys

    # v1.1 OAuth (profile update 用)
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
    api_v1 = tweepy.API(auth)

    # v2 Client (tweet 投稿用)
    client_v2 = tweepy.Client(
        consumer_key=api_key, consumer_secret=api_secret,
        access_token=access_token, access_token_secret=access_secret,
    )

    # 1. Profile text update (Name + Bio + URL)
    print('[1/4] 表示名 + Bio + URL 更新中...')
    try:
        api_v1.update_profile(name=NEW_NAME, description=NEW_BIO, url=NEW_URL)
        print(f'      ✓ name={NEW_NAME!r}, bio={len(NEW_BIO)}字, url={NEW_URL}')
    except Exception as e:
        print(f'      ✗ FAIL: {type(e).__name__}: {e}', file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f'      response: {e.response.text[:500]}', file=sys.stderr)

    # 2. Avatar
    if args.skip_image:
        print('[2/4] アバター skip (--skip-image)')
    elif AVATAR_PATH.exists():
        print(f'[2/4] アバター upload: {AVATAR_PATH.name} ({AVATAR_PATH.stat().st_size // 1024}KB)')
        try:
            api_v1.update_profile_image(str(AVATAR_PATH))
            print('      ✓ 完了')
        except Exception as e:
            print(f'      ✗ FAIL: {type(e).__name__}: {e}', file=sys.stderr)
    else:
        print(f'[2/4] SKIP: アバター画像なし ({AVATAR_PATH})')

    # 3. Banner
    if args.skip_image:
        print('[3/4] バナー skip (--skip-image)')
    elif BANNER_PATH.exists():
        print(f'[3/4] バナー upload: {BANNER_PATH.name} ({BANNER_PATH.stat().st_size // 1024}KB)')
        try:
            api_v1.update_profile_banner(str(BANNER_PATH))
            print('      ✓ 完了')
        except Exception as e:
            print(f'      ✗ FAIL: {type(e).__name__}: {e}', file=sys.stderr)
    else:
        print(f'[3/4] SKIP: バナー画像なし ({BANNER_PATH})')

    # 4. Pinned tweet
    if args.skip_pin:
        print('[4/4] ピン留めツイート skip (--skip-pin)')
    else:
        print(f'[4/4] ピン留め用ツイート投稿中 ({len(PINNED_TEXT)} chars, $0.200 URL 含む)')
        try:
            res = client_v2.create_tweet(text=PINNED_TEXT, user_auth=True)
            tid = res.data.get('id') if hasattr(res, 'data') else '?'
            print(f'      ✓ Tweet ID: {tid}')
            print(f'      → https://x.com/SoothingSoothin/status/{tid}')
            print('      ⚠ X 管理画面で右上 ⋯ → 「プロフィールに固定表示する」 を手動クリック')
            print('         (API でピン留め設定は X 公式 endpoint 未提供)')
        except Exception as e:
            print(f'      ✗ FAIL: {type(e).__name__}: {e}', file=sys.stderr)

    print('\n=== Done ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())
