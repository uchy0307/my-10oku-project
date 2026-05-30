#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""200 アプリ 禁則ワード一括置換 (Phase 1、 2026-05-30)。

CLAUDE.md 規約: 「47歳管理職」表現禁止 → 「成熟した悩める大人」全般。
年齢・役職ペルソナを汎用表現に置換 (全成熟した大人が対象)。
"""
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / 'articles'

# 長い語から先に置換 (部分マッチ防止)
REPLACEMENTS = [
    (r'年下上司', '立場が逆転した相手'),
    (r'五十歳目前', '人生の後半'),
    (r'50歳目前', '人生の後半'),
    (r'五十歳', '人生の後半'),
    (r'50歳', '人生の節目'),
    (r'47歳', ''),
    (r'中高年', '成熟した大人'),
    (r'中年の疲れ', 'ただの疲れ'),
    (r'中年期', '人生の後半'),
    (r'中年', '成熟した大人'),
    (r'経営層では', '責任ある立場では'),
    (r'経営層', '責任ある立場'),
    (r'経営の数字', '組織の数字'),
    (r'管理職として', '責任ある立場として'),
    (r'管理職', '責任ある立場'),
    (r'おじさん', '大人'),
    (r'部長や課長', '上司'),
    (r'部長・課長', '上司'),
    (r'部長', '上司'),
    (r'課長', '上司'),
    (r'役員会', '経営会議'),
    (r'役員', '上層部'),
]

modified = []
for i in range(1, 201):
    p = ART / f'note_{i:03d}.md'
    if not p.exists():
        continue
    text = p.read_text(encoding='utf-8')
    orig = text
    for pat, rep in REPLACEMENTS:
        text = re.sub(pat, rep, text)
    # 二重空白・句読点の整形 (置換で空文字化した箇所)
    text = re.sub(r'、\s*、', '、', text)
    text = re.sub(r'  +', ' ', text)
    if text != orig:
        p.write_text(text, encoding='utf-8')
        modified.append(p.name)

print(f'modified {len(modified)} files')
for n in modified:
    print(f'  {n}')
