#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
note 違反検知 v2 (正しいルール):

【削除対象】
- マスターキー TOI-MASTER-XXXX (全アプリ解錠)
- 全アプリ開示リンク・一覧 URL
- 金額表記 (500円/100円/¥/￥)

【残す】
- 各記事固有の TOI-NNN-XXXX (#109 のアクセスコード等) — 有料エリア内ならOK
- 各記事固有の toi-suite.vercel.app/page/NNN リンク
- 「## 🔑 アクセスコード」セクションと {{ACCESS_CODE}} プレースホルダ

【まず v1 で過剰削除した分を復元 → v2 で正しい違反のみ削除】
"""
import sys, re, json
from pathlib import Path
from datetime import datetime, timezone, timedelta

if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / 'articles'
QUEUE = ROOT / 'note-auto' / 'queue.json'
JST = timezone(timedelta(hours=9))

# ─── 削除対象 (絶対NG) ───
MASTER_KEY_PATTERN = re.compile(r'TOI-MASTER-[A-Z0-9]+', re.IGNORECASE)
MASTER_LINE = re.compile(r'^.*TOI-MASTER-[A-Z0-9]+.*$', re.MULTILINE | re.IGNORECASE)

# 全アプリ一覧 URL (全部解錠可能なリンク)
ALL_APPS_PATTERNS = [
    re.compile(r'toi-suite\.vercel\.app/?(?:\s|$|"|\))'),  # ルート (page なし)
    re.compile(r'toi-suite\.vercel\.app/list', re.IGNORECASE),
    re.compile(r'toi-suite\.vercel\.app/all', re.IGNORECASE),
    re.compile(r'toi-suite\.vercel\.app/master', re.IGNORECASE),
    re.compile(r'toi-suite\.vercel\.app/index', re.IGNORECASE),
]

# 金額表記 (NG)
PRICE_PATTERNS = [
    re.compile(r'1本\s*\d+\s*円'),
    re.compile(r'\d+\s*円で'),
    re.compile(r'価格\s*[：:]\s*\d+\s*円'),
    re.compile(r'¥\s*\d+'),
    re.compile(r'￥\s*\d+'),
    re.compile(r'(500|300|200)\s*円'),
]

def check(md_text, nid):
    violations = []
    if MASTER_KEY_PATTERN.search(md_text):
        violations.append('master_key_leak')
    for p in ALL_APPS_PATTERNS:
        if p.search(md_text):
            violations.append(f'all_apps_link:{p.pattern[:40]}')
    for p in PRICE_PATTERNS:
        if p.search(md_text):
            violations.append(f'price_leak:{p.pattern[:30]}')
    return violations

def fix(md_text):
    md_text = MASTER_LINE.sub('', md_text)
    for p in ALL_APPS_PATTERNS:
        md_text = p.sub('', md_text)
    for p in PRICE_PATTERNS:
        md_text = p.sub('', md_text)
    md_text = re.sub(r'\n{3,}', '\n\n', md_text)
    return md_text

def restore_all_from_v1_backup():
    """v1 で .md.bak_* を作ったので全部復元"""
    restored = 0
    for bak in ARTICLES.glob('note_*.md.bak_*'):
        orig = ARTICLES / bak.name.split('.bak_')[0]
        if orig.exists():
            orig.write_text(bak.read_text(encoding='utf-8'), encoding='utf-8')
            restored += 1
    return restored

def main():
    print('=== STEP 1: v1 過剰削除を全件復元 ===')
    restored = restore_all_from_v1_backup()
    print(f'  復元: {restored} 件')

    print('\n=== STEP 2: v2 で正しい違反のみ精緻削除 ===')
    files = sorted(ARTICLES.glob('note_*.md'))
    fixed = []
    clean = []
    for f in files:
        m = re.match(r'note_(\d+)\.md', f.name)
        if not m: continue
        nid = m.group(1)
        body = f.read_text(encoding='utf-8')
        vios = check(body, nid)
        if not vios:
            clean.append(nid)
            continue
        new_body = fix(body)
        bak = f.with_suffix('.md.v2bak_' + datetime.now(JST).strftime('%Y%m%d_%H%M%S'))
        if not bak.exists():
            bak.write_text(body, encoding='utf-8')
        f.write_text(new_body, encoding='utf-8')
        fixed.append({'id': nid, 'violations': vios})
        print(f'  FIXED #{nid}: {vios}')

    print(f'\n=== SUMMARY ===')
    print(f'  v1 backup から復元: {restored}件')
    print(f'  v2 違反検知で修正: {len(fixed)}件')
    print(f'  違反なし: {len(clean)}件 (固有アクセスコード/page URL はOK扱い)')

    if QUEUE.exists():
        try:
            q = json.loads(QUEUE.read_text(encoding='utf-8'))
            q.setdefault('_violation_fixes_v2', []).append({
                'at': datetime.now(JST).isoformat(),
                'restored_from_v1': restored,
                'v2_fixed': len(fixed),
                'v2_fixed_ids': [x['id'] for x in fixed],
            })
            QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'queue.json に v2 修正履歴記録済')
        except Exception as e:
            print(f'queue.json write failed: {e}')

if __name__ == '__main__':
    main()
