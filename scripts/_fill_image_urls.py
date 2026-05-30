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


# 2026-05-30: 現代写真を除外するための NG パターン (ファイル名ベース)
# 歴史動画に現代の建物/道路/人物写真が混入する事故 (046 町火消しに現代火の見やぐら) の対策
MODERN_NG = [
    '198', '199', '200', '201', '202',  # 1980-2029 年号 (ファイル名の年)
    'tower', 'station', 'building', 'road', 'highway', 'modern', 'street',
    'dsc', 'img_', 'p10', 'p11', 'p12', 'pxl_', 'photo', 'camera',
    'panorama', 'aerial', 'drone', 'satellite', 'google',
    # 現代の施設・建造物 (「Edo」等が現代名にマッチする事故対策)
    'library', 'computer', 'laborator', 'school', 'university', 'college',
    'campus', 'hall', 'hospital', 'airport', 'hotel', 'stadium', 'factory',
    'railway', 'railroad', 'subway', 'metro', 'expressway', 'apartment',
    'mansion', 'shopping', 'mall', 'park_2', 'bridge_2', 'interior',
    'restaurant', 'cafe', 'shinkansen', 'highway', 'monorail', 'terminal',
    # 現代イベント・芸能 (ローマ字単語が声優/俳優/祭事にマッチする事故対策)
    'festival', 'film', 'actor', 'actress', 'voice', 'cosplay', 'anime',
    'manga', 'game', 'concert', 'award', 'ceremony', 'premiere', 'expo',
    'conference', 'summit', 'olympic', 'world_cup', 'singer', 'idol',
    'cinema', 'movie', 'tv_', 'youtube', 'interview', 'press',
    # 海外の同名地名・施設 (ローマ字が米国地名等にマッチする事故対策)
    'nrhp', 'county', '_sd_', '_usa', '_us_', 'illinois', 'california',
    'texas', 'ohio', 'virginia', 'dakota', 'kansas', 'street_view',
    # 天体・地名collision (絵師名が水星クレーター等にマッチ)
    'crater', 'nasa', 'mercury', 'planet', 'm10', 'aom', 'asteroid',
    'lunar', 'satellite', 'spacecraft', 'messenger',
]
# 歴史画像を優先するための GOOD パターン
HIST_GOOD = [
    'ukiyo', '浮世絵', '絵図', '古地図', '屏風', 'byobu', 'emaki', '絵巻',
    'edo', '江戸', 'meiji', '明治', 'hiroshige', 'hokusai', 'utamaro',
    'kuniyoshi', 'museum', 'woodblock', 'print', 'scroll', 'painting',
    '錦絵', '版画', '掛軸', '史料',
]


def _hist_score(fname: str) -> int:
    low = fname.lower()
    score = 0
    for g in HIST_GOOD:
        if g.lower() in low:
            score += 3
    for n in MODERN_NG:
        if n in low:
            score -= 5
    return score


def search_wikimedia(keyword: str, limit: int = 2, historical: bool = False) -> list:
    """Wikimedia Commons 検索 → Special:FilePath URL。
    historical=True なら現代写真を除外 + 浮世絵/歴史画像を優先スコアリング。"""
    # 歴史なら検索語に時代修飾を足して古い画像をヒットさせる
    srch = keyword
    q = urllib.parse.quote(srch)
    fetch_n = max(limit * 4, 8) if historical else limit
    url = (f'https://commons.wikimedia.org/w/api.php'
           f'?action=query&format=json&list=search&srsearch={q}&srnamespace=6&srlimit={fetch_n}')
    req = urllib.request.Request(url, headers={'User-Agent': WIKI_UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode('utf-8'))
        files = [h['title'].replace('File:', '') for h in data.get('query', {}).get('search', [])]
        cands = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
        if historical:
            # 現代 NG を強く含むものを除外 → スコア順
            scored = [(f, _hist_score(f)) for f in cands]
            scored = [s for s in scored if s[1] > -5]  # 明確に現代なものは捨てる
            scored.sort(key=lambda x: x[1], reverse=True)
            cands = [f for f, _ in scored]
        urls = []
        for f in cands[:limit]:
            fname = f.replace(' ', '_')
            urls.append(f'https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(fname)}')
        return urls
    except Exception as e:
        print(f'  [WARN] wikimedia search "{keyword}" failed: {e}', file=sys.stderr)
        return []


def ask_gemini_keywords(title: str, category: str = '', historical: bool = False) -> list:
    """Gemini に Wikimedia 検索キーワード生成依頼 (12 個)"""
    if historical:
        prompt = (
            f'動画テーマ「{title}」(カテゴリ: {category}) は日本史の動画です。\n'
            f'Wikimedia Commons で画像検索する「単語」を 10 個。\n'
            f'【最重要】複合語・2語以上は禁止 (検索がヒットしない)。 必ず 1 つの固有名詞/単語。\n'
            f'【最重要】英語のローマ字表記を優先 (Wikimedia は英語が多い)。 例: Hiroshige, Hokusai, Kuniyoshi, Tokaido, Nihonbashi, Asakusa\n'
            f'狙い: 浮世絵の絵師名・有名な浮世絵シリーズ名・江戸の地名 (英語表記)・歴史人物名 (英語表記)。\n'
            f'現代写真が出る一般語 (tower, station, 現代地名) は避ける。\n'
            f'出力形式: 1 行 1 単語で 10 行。 説明/番号/記号 不要。'
        )
    else:
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


def fill_one(script_path: Path, historical: bool = False, force: bool = False) -> bool:
    """script JSON 1 つを処理。 image_urls が空なら埋める (force で上書き)。"""
    try:
        data = json.loads(script_path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'[SKIP] {script_path.name}: json parse fail: {e}')
        return False
    if not isinstance(data, dict):
        return False
    existing = data.get('image_urls') or []
    if isinstance(existing, list) and len(existing) >= 6 and not force:
        return False  # 既に十分あり、 skip (force 時は再取得)
    title = data.get('title', '').strip()
    category = data.get('category', '').strip()
    if not title:
        print(f'[SKIP] {script_path.name}: empty title')
        return False
    print(f'[fill] {script_path.name}: "{title}" (historical={historical})')
    try:
        keywords = ask_gemini_keywords(title, category, historical=historical)
    except Exception as e:
        print(f'  [FAIL] Gemini keyword: {e}', file=sys.stderr)
        return False
    print(f'  keywords ({len(keywords)}): {keywords[:5]}...')

    def collect(strict):
        out = []
        for kw in keywords:
            if len(out) >= 14:
                break
            out.extend(search_wikimedia(kw, limit=3, historical=strict))
            time.sleep(0.4)
        return out

    # 1st pass: トピック単語 (厳格フィルタ)
    urls = collect(historical)
    seen, deduped = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); deduped.append(u)
    # 2nd pass (歴史のみ): 確実に江戸浮世絵がヒットするプールで補充
    if len(deduped) < 12 and historical:
        EDO_POOL = [
            'Hiroshige', 'Hokusai', 'Kuniyoshi', 'Utamaro',
            'Hundred Famous Views of Edo', 'Tokaido', 'Ukiyo-e Edo',
            'Edo period painting', 'Kunisada', 'Edo castle ukiyo-e',
        ]
        for kw in EDO_POOL:
            if len(deduped) >= 12:
                break
            for u in search_wikimedia(kw, limit=2, historical=True):
                if u not in seen:
                    seen.add(u); deduped.append(u)
            time.sleep(0.4)
    deduped = deduped[:12]
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
    ap.add_argument('--force', action='store_true', help='既存 image_urls も上書き再取得')
    args = ap.parse_args()

    # history は歴史時代厳格モード (浮世絵/古地図優先、 現代写真除外)
    historical = (args.kind == 'history')
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
            if fill_one(f, historical=historical, force=args.force):
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
