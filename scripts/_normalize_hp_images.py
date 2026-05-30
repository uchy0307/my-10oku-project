#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""assets/hp_landing/raw/ に保存された画像を正規サイズにリサイズして配置 (2026-05-30)。

うっちー様が右クリック保存した画像を raw/ に置く → このスクリプトが
各ファイル名から用途を判定 → cover リサイズ → assets/hp_landing/ 直下に配置。

raw/ 内のファイル名 (部分一致、 大文字小文字無視) で振り分け:
  logo    → logo.png    (400x400)
  hero    → hero.png    (1920x1080)
  shindan → pillar_shindan.png (600x400)
  toi     → pillar_toi.png     (600x400)
  drama   → pillar_drama.png   (600x400)
  otona   → pillar_otona.png   (600x400)
"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
HP = ROOT / 'assets' / 'hp_landing'
RAW = HP / 'raw'

# (キーワード, 出力名, w, h)
MAP = [
    ('logo',    'logo.png',           400, 400),
    ('hero',    'hero.png',          1920, 1080),
    ('shindan', 'pillar_shindan.png', 600, 400),
    ('toi',     'pillar_toi.png',     600, 400),
    ('drama',   'pillar_drama.png',   600, 400),
    ('otona',   'pillar_otona.png',   600, 400),
]


def cover(img, tw, th):
    w, h = img.size
    s = max(tw / w, th / h)
    nw, nh = int(w * s), int(h * s)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def main():
    if not RAW.exists():
        print(f'[FATAL] {RAW} が無い。 raw/ フォルダを作って画像を保存して')
        return 1
    files = [p for p in RAW.iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
    print(f'raw images: {[f.name for f in files]}')
    done = 0
    for kw, out, tw, th in MAP:
        match = next((f for f in files if kw in f.stem.lower()), None)
        if not match:
            print(f'  [SKIP] {kw}: 該当ファイルなし (ファイル名に "{kw}" を含めて保存)')
            continue
        img = Image.open(match).convert('RGB')
        cover(img, tw, th).save(HP / out, 'PNG', optimize=True)
        print(f'  [OK] {match.name} ({img.size[0]}x{img.size[1]}) → {out} ({tw}x{th})')
        done += 1
    print(f'\n=== {done}/6 配置完了 ===')


if __name__ == '__main__':
    main()
