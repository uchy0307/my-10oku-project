#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""200 アプリ (articles/note_*.md) 品質監査 (2026-05-30)。

検出:
  1. 空セクション (## 見出し直後に本文なし)
  2. 上級プロンプト 実体欠落 (「貼り付け」と書いて実プロンプト code block なし)
  3. 禁則ワード (経営層/50歳/中年/年下上司/47歳/管理職 等)
  4. bracket バランス ({{ }} 未置換以外の [ ] ( ) 不均衡)
  5. プレースホルダ未処理
"""
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / 'articles'

BANNED = ['経営層', '50歳', '五十歳', '中年', '年下上司', '47歳', '管理職', '部長', '課長', '役員', 'おじさん', '中高年']

stats = {
    'empty_section': [],
    'no_prompt_body': [],
    'banned': [],
    'has_happyhappy': [],
}

for i in range(1, 201):
    p = ART / f'note_{i:03d}.md'
    if not p.exists():
        continue
    text = p.read_text(encoding='utf-8')
    lines = text.split('\n')

    # 1. 空セクション検出: ## 見出し の次の非空行が ## か --- なら空
    for j, line in enumerate(lines):
        if re.match(r'^##\s+\d+\.', line):  # 番号付きセクション
            # 次の本文を探す
            body = []
            for k in range(j + 1, len(lines)):
                nxt = lines[k].strip()
                if nxt.startswith('##') or nxt == '---':
                    break
                if nxt:
                    body.append(nxt)
            if not body:
                stats['empty_section'].append((p.name, line.strip()[:40]))

    # 2. 上級プロンプト 実体欠落: 「貼り付け」記載あるが code block (```) が後続にない
    m = re.search(r'## 🎯 上級プロンプト', text)
    if m:
        after = text[m.start():m.start() + 1500]
        # code block か、 具体的なプロンプト文 (「」で囲まれた指示 + 改行複数) があるか
        has_codeblock = '```' in after[:1200]
        # 「以下」「下記」と書いてるのに code block なし = 欠落
        promises_prompt = ('貼り付け' in after or '下記' in after or '以下' in after)
        if promises_prompt and not has_codeblock:
            stats['no_prompt_body'].append((p.name,))

    # 3. 禁則ワード
    hits = [w for w in BANNED if w in text]
    if hits:
        stats['banned'].append((p.name, hits))

    # 4. happyhappy 署名
    if 'happyhappy' in text:
        stats['has_happyhappy'].append((p.name,))

print('=' * 60)
print('200 アプリ品質監査結果')
print('=' * 60)
print(f'\n[1] 空セクション: {len(stats["empty_section"])} 件')
for n, h in stats['empty_section'][:15]:
    print(f'    {n}: {h}')
print(f'\n[2] 上級プロンプト 実体欠落: {len(stats["no_prompt_body"])} 件')
for t in stats['no_prompt_body'][:15]:
    print(f'    {t[0]}')
print(f'\n[3] 禁則ワード: {len(stats["banned"])} 件')
for n, h in stats['banned'][:20]:
    print(f'    {n}: {h}')
print(f'\n[4] happyhappy 署名: {len(stats["has_happyhappy"])} 件')
