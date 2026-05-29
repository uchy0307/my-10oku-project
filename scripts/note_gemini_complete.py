#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
note articles/note_NNN.md で NO_LEAD / NO_EXPERIENCE_H2 の不備を Gemini で補完.

Usage:
  python scripts/note_gemini_complete.py --pending-only
  python scripts/note_gemini_complete.py --idx 121
"""
import sys, os, re, json, time, argparse, urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
ARTICLES = ROOT / 'articles'
QUEUE = ROOT / 'note-auto' / 'queue.json'
JST = timezone(timedelta(hours=9))

# env load (GEMINI_API_KEY)
for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_KEY:
    print('GEMINI_API_KEY missing')
    sys.exit(2)

MODEL = 'gemini-2.5-flash'
URL = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_KEY}'

LEAD_TEMPLATE_RE = re.compile(r'^.+\n+(.*?(?=\n## ))', re.DOTALL)

def gemini_call(prompt, timeout=60):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1200},
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(URL, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode('utf-8'))
        return body['candidates'][0]['content']['parts'][0]['text'].strip()

def get_title_and_theme(md_text, idx):
    # 「【AI対話アプリ】... #NNN『テーマ』」からテーマ抽出
    m = re.search(r'#\s*' + idx + r'\s*[「『]([^」』]+)[」』]', md_text)
    if m:
        return m.group(1)
    # fallback: first H1
    h1 = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
    return h1.group(1) if h1 else f'200の問い #{idx}'

def add_lead(md_text, idx, theme):
    """リード文 (正解 #116 構造): 「このアプリは『XXX』のためのAI対話プロンプト集です。...」"""
    # H1 直後にリード追加
    prompt = f"""以下のテーマで note 記事のリード文を1段落 (180-220字) で書いてください。
出力ルール:
- 必ず冒頭は「このアプリは『{theme}』のためのAI対話プロンプト集です。」で始める
- 上記文に続けて、このテーマで何ができるか/どんな悩みに効くか/どう深掘りするかを具体的に2文程度
- 改行なし、1段落のみ
- 「成熟した悩める大人」が読み手
- 文章のみ出力、解説不要
"""
    try:
        new_lead = gemini_call(prompt)
    except Exception as e:
        print(f'  Gemini lead fail: {e}')
        return md_text
    # H1 行を見つけて、その直後の段落を新リードに置換 or 挿入
    h1_match = re.search(r'^(#\s+.+?)$', md_text, re.MULTILINE)
    if not h1_match:
        return md_text
    h1_end = h1_match.end()
    rest = md_text[h1_end:]
    # 既存のリード段落 (H2 までの空行+段落) を新リードに置換
    after_match = re.search(r'\n+([^\n#]+?)\n+(?=##|\Z)', rest, re.DOTALL)
    if after_match:
        new_md = md_text[:h1_end] + '\n\n' + new_lead + rest[after_match.end():]
    else:
        new_md = md_text[:h1_end] + '\n\n' + new_lead + '\n' + rest
    return new_md

def add_experience(md_text, idx, theme):
    """体験談セクション: 「## 体験談: ...」を生成"""
    prompt = f"""以下のテーマで note 記事の「体験談」セクションを書いてください。
出力ルール:
- 1行目: ## 体験談: 「適切なサブタイトル」
- 続けて 400-500字の体験談本文 (経営者・40-50代男性視点、具体的な状況→気付き→行動→結果の流れ)
- テーマ: {theme}
- 必ず1人称、リアリティある具体描写
- マークダウンの ## と本文のみ、解説不要
"""
    try:
        new_exp = gemini_call(prompt)
    except Exception as e:
        print(f'  Gemini exp fail: {e}')
        return md_text
    # ✅ X項目セルフチェック の直前に挿入
    insert_marker = re.search(r'\n## ✅ \d+項目セルフチェック', md_text)
    if insert_marker:
        pos = insert_marker.start()
        return md_text[:pos] + '\n\n' + new_exp + '\n' + md_text[pos:]
    # fallback: 末尾
    return md_text + '\n\n' + new_exp + '\n'

def needs_lead(md_text):
    return not re.search(r'このアプリは「[^」]+」のためのAI対話プロンプト集です', md_text)

def needs_experience(md_text):
    return not re.search(r'^## 体験談[:：]', md_text, re.MULTILINE)

def process_one(path, idx):
    body = path.read_text(encoding='utf-8')
    theme = get_title_and_theme(body, idx)
    print(f'\n#{idx}: theme="{theme}"')
    changed = False
    if needs_lead(body):
        body = add_lead(body, idx, theme)
        changed = True
        time.sleep(2)
    if needs_experience(body):
        body = add_experience(body, idx, theme)
        changed = True
        time.sleep(2)
    if changed:
        bak = path.with_suffix(path.suffix + '.gem_bak_' + datetime.now(JST).strftime('%Y%m%d_%H%M%S'))
        if not bak.exists():
            bak.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
        path.write_text(body, encoding='utf-8')
        print(f'  WRITTEN')
    return changed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pending-only', action='store_true')
    ap.add_argument('--idx')
    ap.add_argument('--limit', type=int, default=20)
    args = ap.parse_args()

    pending_ids = None
    if args.pending_only:
        q = json.loads(QUEUE.read_text(encoding='utf-8'))
        pending_ids = {it.get('id') for it in q.get('items', []) if it.get('status') == 'pending'}

    files = sorted(ARTICLES.glob('note_*.md'))
    if args.idx:
        files = [f for f in files if f.stem == f'note_{args.idx}']

    processed = 0
    for f in files:
        m = re.match(r'note_(\d+)\.md', f.name)
        if not m: continue
        idx = m.group(1)
        if pending_ids is not None and idx not in pending_ids:
            continue
        body = f.read_text(encoding='utf-8')
        if needs_lead(body) or needs_experience(body):
            try:
                if process_one(f, idx):
                    processed += 1
            except Exception as e:
                print(f'  ERR: {e}')
        if processed >= args.limit:
            print(f'  reached limit={args.limit}')
            break
    print(f'\nprocessed: {processed}')

if __name__ == '__main__':
    main()
