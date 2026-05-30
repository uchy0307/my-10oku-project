#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""image_urls 空の台本 JSON に Wikimedia Commons の File URL を自動投入 (Task #39)。

フロー:
  1. Gemini に「動画テーマ → Wikimedia 検索キーワード 12 個」リクエスト
  2. 各キーワードで Wikimedia Commons API search (file namespace)
  3. 取得した file URL を script JSON の image_urls に投入

使い方:
  python scripts/_fill_image_urls.py --kind history --idx-from 31 --idx-to 40
  python scripts/_fill_image_urls.py --kind history  # 全 history
"""
import argparse, json, sys, time, urllib.parse, urllib.request
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

# generate_stock_scripts.py の Gemini call を再利用
from generate_stock_scripts import call_gemini, load_env  # noqa: E402
load_env()

WIKI_UA = '10oku-history-bot/1.0 (https://github.com/uchy0307/my-10oku-project; uchiyamatakayuki0307@gmail.com)'


def search_wikimedia(keyword: str, limit: int = 2) -> list:
    """Wikimedia Commons File namespace (6) で検索 → Special:FilePath URL のリスト"""
    q = urllib.parse.quote(keyword)
    url = (f'https://commons.wikimedia.org/w/api.php'
           f'?action=query&format=json&list=search&srsearch={q}&srnamespace=6&srlimit={limit}')
    req = urllib.request.Request(url, headers={'User-Agent': WIKI_UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode('utf-8'))
        files = [h['title'].replace('File:', '') for h in data.get('query', {}).get('search', [])]
        urls = []
        for f in files:
            fname = f.replace(' ', '_')
            # 画像ファイル拡張子チェック (svg / pdf 除く)
            if not f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                continue
            urls.append(f'https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(fname)}')
        return urls
    except Exception as e:
        print(f'  [WARN] wikimedia search "{keyword}" failed: {e}', file=sys.stderr)
        return []


def ask_gemini_keywords(title: str, category: str = '') -> list:
    """Gemini に Wikimedia 検索キーワード生成依頼 (12 個)"""
    prompt = (
        f'動画テーマ「{title}」(カテゴリ: {category}) について、 '
        f'Wikimedia Commons で検索すべき画像キーワードを 12 個提案せよ。\n'
        f'人物名、 地名、 城/寺/施設名、 戦/事件名、 文化財名など、 '
        f'ジャンルに合った「実在の画像が Wikimedia にありそう」なキーワード。\n'
        f'出力形式: 1 行 1 キーワードで 12 行。 説明文/番号付け/記号 不要。'
    )
    text = call_gemini(prompt)
    lines = []
    for raw in text.split('\n'):
        s = raw.strip().lstrip('・*-#').strip()
        # 番号付き ("1. xxx" or "1) xxx") 除去
        s = s.lstrip('0123456789').lstrip('.)、 ')
        if s and 2 <= len(s) <= 50:
            lines.append(s)
    return lines[:15]


def fill_one(script_path: Path) -> bool:
    """script JSON 1 つを処理。 image_urls が空なら埋める。"""
    try:
        data = json.loads(script_path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'[SKIP] {script_path.name}: json parse fail: {e}')
        return False
    if not isinstance(data, dict):
        return False
    existing = data.get('image_urls') or []
    if isinstance(existing, list) and len(existing) >= 6:
        return False  # 既に十分あり、 skip
    title = data.get('title', '').strip()
    category = data.get('category', '').strip()
    if not title:
        print(f'[SKIP] {script_path.name}: empty title')
        return False
    print(f'[fill] {script_path.name}: "{title}"')
    try:
        keywords = ask_gemini_keywords(title, category)
    except Exception as e:
        print(f'  [FAIL] Gemini keyword: {e}', file=sys.stderr)
        return False
    print(f'  keywords ({len(keywords)}): {keywords[:5]}...')
    urls = []
    for kw in keywords:
        if len(urls) >= 12:
            break
        results = search_wikimedia(kw, limit=2)
        urls.extend(results)
        time.sleep(0.5)
    # 重複除外 + 上限 12
    seen = set()
    deduped = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
        if len(deduped) >= 12:
            break
    print(f'  → {len(deduped)} URLs found')
    if len(deduped) < 6:
        print(f'  [WARN] urls < 6 ({len(deduped)}), skip writing (動画化 fail 防止)')
        return False
    data['image_urls'] = deduped
    script_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', choices=['history', 'psych'], required=True)
    ap.add_argument('--idx-from', type=int, default=1)
    ap.add_argument('--idx-to', type=int, default=999)
    args = ap.parse_args()

    if args.kind == 'history':
        scripts_dir = ROOT / 'youtube' / 'history_v2' / 'scripts'
        prefix = 'long_'
    else:
        scripts_dir = ROOT / 'youtube' / 'psych_v2' / 'scripts'
        prefix = 'psych_'

    files = sorted(scripts_dir.glob(f'{prefix}*.json'))
    ok, skip, fail = 0, 0, 0
    for f in files:
        m = f.stem.replace(prefix, '')
        try:
            idx = int(m)
        except ValueError:
            continue
        if not (args.idx_from <= idx <= args.idx_to):
            continue
        try:
            if fill_one(f):
                ok += 1
            else:
                skip += 1
        except KeyboardInterrupt:
            print('\n[STOP] interrupted')
            break
        except Exception as e:
            fail += 1
            print(f'[FAIL] {f.name}: {e}', file=sys.stderr)
        time.sleep(5)  # Gemini rate limit (15 RPM)
    print(f'\n=== Done: ok={ok} skip={skip} fail={fail} ===')


if __name__ == '__main__':
    main()
