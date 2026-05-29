#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
note articles/note_NNN.md を「正解 #116 構造」に揃える検査+自動補正.

正解構造 (#116 ベース):
  - リード文: 「このアプリは『TEMA』のためのAI対話プロンプト集です。」で始まる
  - 本文 H2:
    * 4セクション程度の具体的内容 H2
    * 「体験談:」H2
    * 「✅ X項目セルフチェック」H2
    * 「🤔 5つの問い」H2 (中核)
    * 「✅ アプリURL」H2 ← toi-suite/page/NNN リンク
  - 「## 🔑 アクセスコード」セクション (有料境界マーカー)
  - 末尾「ここから先は **有料エリア** です。」
  - 末尾ハッシュタグ群

このスクリプト:
  1. 各 md の構造を分析
  2. 不備があれば検出 + レポート出力
  3. --fix で自動修正 (アクセスコードセクション追加、アプリURL補完、有料境界追加)

Usage:
  python scripts/note_structure_check.py            # チェックのみ
  python scripts/note_structure_check.py --fix      # 自動修正
  python scripts/note_structure_check.py --idx 119  # 特定idのみ
"""
import sys, re, argparse, json
from pathlib import Path
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
ARTICLES = ROOT / 'articles'
QUEUE = ROOT / 'note-auto' / 'queue.json'
ACCESS_CODES = ROOT / 'note-auto' / 'access_codes.json'
JST = timezone(timedelta(hours=9))

PATTERNS = {
    'lead': re.compile(r'このアプリは[「『][^」』]+[」』]のためのAI対話プロンプト集です'),
    'access_h2': re.compile(r'^## 🔑 アクセスコード\s*$', re.MULTILINE),
    'access_placeholder': re.compile(r'\{\{ACCESS_CODE\}\}'),
    'questions_h2': re.compile(r'^## 🤔 5つの問い', re.MULTILINE),
    'checklist_h2': re.compile(r'^## ✅ \d+項目セルフチェック', re.MULTILINE),
    'experience_h2': re.compile(r'^## 体験談[:：]', re.MULTILINE),
    'app_url_h2': re.compile(r'^## ✅ アプリURL', re.MULTILINE),
    'paid_boundary': re.compile(r'ここから先は\s*\*\*?\s*有料エリア'),
    'page_url': re.compile(r'toi-suite\.vercel\.app/page/(\d+)'),
    'hashtags': re.compile(r'(?:^|\n)(#\S+(?:\s+#\S+)+)', re.MULTILINE),
    'leak_master': re.compile(r'TOI-MASTER-[A-Z0-9]+', re.IGNORECASE),
    'leak_price_500': re.compile(r'500\s*円'),
}

def analyze(md_text, idx):
    issues = []
    if not PATTERNS['lead'].search(md_text):
        issues.append('NO_LEAD')
    if not PATTERNS['access_h2'].search(md_text):
        issues.append('NO_ACCESS_H2')
    if not PATTERNS['access_placeholder'].search(md_text) and not re.search(rf'TOI-{idx}-[A-Z0-9]+', md_text):
        issues.append('NO_ACCESS_TOKEN')
    if not PATTERNS['questions_h2'].search(md_text):
        issues.append('NO_QUESTIONS_H2')
    if not PATTERNS['checklist_h2'].search(md_text):
        issues.append('NO_CHECKLIST_H2')
    if not PATTERNS['experience_h2'].search(md_text):
        issues.append('NO_EXPERIENCE_H2')
    if not PATTERNS['app_url_h2'].search(md_text):
        issues.append('NO_APP_URL_H2')
    if not PATTERNS['paid_boundary'].search(md_text):
        issues.append('NO_PAID_BOUNDARY')
    m = PATTERNS['page_url'].search(md_text)
    if m and m.group(1) != idx:
        issues.append(f'PAGE_URL_MISMATCH(got={m.group(1)})')
    if not m:
        issues.append('NO_PAGE_URL')
    if PATTERNS['leak_master'].search(md_text):
        issues.append('LEAK_MASTER_KEY')
    if PATTERNS['leak_price_500'].search(md_text):
        issues.append('LEAK_PRICE_500')
    return issues

def apply_fix(md_text, idx):
    """軽微な補完 (構造を壊さない範囲)"""
    fixed = md_text
    # 1) マスターキー / 500円 漏洩を即削除
    fixed = PATTERNS['leak_master'].sub('', fixed)
    fixed = re.sub(r'^.*TOI-MASTER-[A-Z0-9]+.*$\n?', '', fixed, flags=re.MULTILINE)
    fixed = PATTERNS['leak_price_500'].sub('', fixed)
    # 2) page URL のずれ修正
    fixed = re.sub(r'toi-suite\.vercel\.app/page/\d+', f'toi-suite.vercel.app/page/{idx}', fixed)

    # 3) 有料境界 (「ここから先は有料エリア」) 追加: ## 🔑 アクセスコード の直前
    if not PATTERNS['paid_boundary'].search(fixed):
        boundary_text = '\n---\n\nここから先は **有料エリア** です。アクセスコード・上級プロンプト・ワークブックを掲載しています。\n\n'
        m = PATTERNS['access_h2'].search(fixed)
        if m:
            fixed = fixed[:m.start()] + boundary_text + fixed[m.start():]
        else:
            # access_h2 もない場合は末尾近くに挿入
            fixed = fixed + boundary_text + '## 🔑 アクセスコード\n\n```\n{{ACCESS_CODE}}\n```\n'

    # 4) アプリURL セクション追加: 「🤔 5つの問い」の直後に
    if not PATTERNS['app_url_h2'].search(fixed):
        app_url_section = f'\n\n## ✅ アプリURL\n\nURL: https://toi-suite.vercel.app/page/{idx}\n'
        m = PATTERNS['questions_h2'].search(fixed)
        if m:
            # questions セクション本体の終わり (次の H2 まで) を探す
            after = fixed[m.end():]
            next_h2 = re.search(r'\n## ', after)
            if next_h2:
                insert_pos = m.end() + next_h2.start()
                fixed = fixed[:insert_pos] + app_url_section + fixed[insert_pos:]
            else:
                # 次の H2 がなければ paid_boundary の直前
                pb = PATTERNS['paid_boundary'].search(fixed)
                if pb:
                    fixed = fixed[:pb.start()] + app_url_section + '\n' + fixed[pb.start():]
                else:
                    fixed = fixed + app_url_section

    # 5) 連続改行圧縮
    fixed = re.sub(r'\n{3,}', '\n\n', fixed)
    return fixed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fix', action='store_true', help='auto-fix safe issues')
    ap.add_argument('--idx', help='only one idx (e.g. 119)')
    ap.add_argument('--pending-only', action='store_true', help='only those status=pending in queue.json')
    args = ap.parse_args()

    # pending-only mode
    pending_ids = None
    if args.pending_only and QUEUE.exists():
        q = json.loads(QUEUE.read_text(encoding='utf-8'))
        pending_ids = {it.get('id') for it in q.get('items', []) if it.get('status') == 'pending'}
        print(f'[pending-only] target {len(pending_ids)} items')

    files = sorted(ARTICLES.glob('note_*.md'))
    if args.idx:
        files = [f for f in files if f.stem == f'note_{args.idx}']

    summary = {'OK': 0, 'ISSUES': 0, 'FIXED': 0}
    issue_counts = {}

    for f in files:
        m = re.match(r'note_(\d+)\.md', f.name)
        if not m: continue
        idx = m.group(1)
        if pending_ids is not None and idx not in pending_ids:
            continue
        body = f.read_text(encoding='utf-8')
        issues = analyze(body, idx)
        if not issues:
            summary['OK'] += 1
            continue
        summary['ISSUES'] += 1
        for it in issues:
            issue_counts[it] = issue_counts.get(it, 0) + 1
        print(f'#{idx}: {", ".join(issues)}')

        if args.fix:
            fixed = apply_fix(body, idx)
            if fixed != body:
                bak = f.with_suffix(f.suffix + '.v3bak_' + datetime.now(JST).strftime('%Y%m%d_%H%M%S'))
                if not bak.exists():
                    bak.write_text(body, encoding='utf-8')
                f.write_text(fixed, encoding='utf-8')
                summary['FIXED'] += 1

    print(f'\n=== SUMMARY ===')
    for k, v in summary.items():
        print(f'  {k}: {v}')
    print(f'\n=== Issue counts ===')
    for k, v in sorted(issue_counts.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')

if __name__ == '__main__':
    main()
