#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
note 違反検知 & 自動修正 (articles/note_NNN.md)

ルール (CLAUDE.md):
  1. アクセスコード「TOI-NNN-XXXX」は本文に書かない
  2. 金額表記 (500円/100円/¥/￥) は書かない
  3. #001-#050 のテンプレに準拠

このスクリプトは: ローカル md ファイルを修正するだけ。
note.com 本番への反映は post.mjs (Playwright) 経由で別途実行。
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

# ─── 違反パターン ───
ACCESS_CODE_PATTERN = re.compile(r'アクセスコード\s*[：:]\s*TOI-\d+-[A-Z0-9]+', re.IGNORECASE)
ACCESS_CODE_LINE = re.compile(r'^.*アクセスコード\s*[：:].*TOI-\d+.*$', re.MULTILINE)
PRICE_PATTERNS = [
    re.compile(r'1本\s*\d+\s*円'),
    re.compile(r'\d+\s*円で'),
    re.compile(r'価格\s*[：:]\s*\d+\s*円'),
    re.compile(r'¥\s*\d+'),
    re.compile(r'￥\s*\d+'),
    re.compile(r'(500|300|200)\s*円'),
]

def check(md_text):
    violations = []
    if ACCESS_CODE_PATTERN.search(md_text):
        violations.append('access_code_leak')
    for p in PRICE_PATTERNS:
        if p.search(md_text):
            violations.append(f'price_leak:{p.pattern}')
    return violations

def fix(md_text):
    """違反箇所を削除/置換"""
    # 1. アクセスコード行を丸ごと削除
    md_text = ACCESS_CODE_LINE.sub('', md_text)
    # 2. 金額表記を削除 (文ごと消すと文脈崩れるので、該当部分のみマスク)
    for p in PRICE_PATTERNS:
        md_text = p.sub('', md_text)
    # 3. 連続空行を1つに圧縮
    md_text = re.sub(r'\n{3,}', '\n\n', md_text)
    return md_text

def main():
    if not ARTICLES.exists():
        print(f'articles dir not found: {ARTICLES}')
        return
    files = sorted(ARTICLES.glob('note_*.md'))
    print(f'対象: {len(files)} 件')

    fixed_ids = []
    no_violation_ids = []
    for f in files:
        m = re.match(r'note_(\d+)\.md', f.name)
        if not m: continue
        nid = m.group(1)
        body = f.read_text(encoding='utf-8')
        vios = check(body)
        if not vios:
            no_violation_ids.append(nid)
            continue
        new_body = fix(body)
        # バックアップ
        bak = f.with_suffix('.md.bak_' + datetime.now(JST).strftime('%Y%m%d_%H%M%S'))
        if not bak.exists():
            bak.write_text(body, encoding='utf-8')
        f.write_text(new_body, encoding='utf-8')
        fixed_ids.append({'id': nid, 'violations': vios, 'backup': bak.name})
        print(f'  FIXED #{nid}: {vios}')

    print(f'\n=== SUMMARY ===')
    print(f'  修正済: {len(fixed_ids)} 件')
    print(f'  違反なし: {len(no_violation_ids)} 件')

    # queue.json に修正履歴記録
    if QUEUE.exists() and fixed_ids:
        try:
            q = json.loads(QUEUE.read_text(encoding='utf-8'))
            q.setdefault('_violation_fixes', []).append({
                'at': datetime.now(JST).isoformat(),
                'fixed_count': len(fixed_ids),
                'fixed_ids': [x['id'] for x in fixed_ids[:50]],
            })
            QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'queue.json に修正履歴記録済')
        except Exception as e:
            print(f'queue.json write failed: {e}')

    return {'fixed': fixed_ids, 'clean': no_violation_ids}

if __name__ == '__main__':
    main()
