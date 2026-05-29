#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""preprocess_yomi 動作確認テスト。"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent))

from preprocess_yomi import apply_yomi, load_dict

print('=== 辞書ロード ===')
d = load_dict()
print(f'辞書エントリ数: {len(d)}')
print()

samples = [
    "北条早雲の今川氏親への手紙が伊勢宗瑞によって書かれた",
    "壇ノ浦の戦いで平清盛の孫である安徳天皇が源義経と平知盛に追われた",
    "島津義弘が関ヶ原で捨て奸を敢行",
    "直江兼続の愛の兜は上杉謙信の遺志を継ぐ",
    "豊臣秀吉の太閤検地と織田信長の楽市楽座が江戸時代の基礎を作った",
    "心理的安全性は組織開発の基礎で、 自己効力感と承認欲求の両立が重要",
    "西郷隆盛、大久保利通、坂本龍馬が明治維新を成し遂げた",
]

print('=== ふりがな置換テスト ===')
for s in samples:
    out = apply_yomi(s)
    print(f'IN : {s}')
    print(f'OUT: {out}')
    print()
