#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HP 用 6 枚グリッド画像を 3x2 で分割 → 各パスにリサイズ保存 (2026-05-30)。

使い方:
  python scripts/_split_hp_grid.py --src "<グリッド画像パス>"
  # 行間/列間に余白がある場合は --margin で調整 (px、 デフォルト自動推定)
"""
import argparse, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets' / 'hp_landing'

# (row, col) → (filename, target_w, target_h)
LAYOUT = {
    (0, 0): ('logo.png', 400, 400),
    (0, 1): ('hero.png', 1920, 1080),
    (0, 2): ('pillar_shindan.png', 600, 400),
    (1, 0): ('pillar_toi.png', 600, 400),
    (1, 1): ('pillar_drama.png', 600, 400),
    (1, 2): ('pillar_otona.png', 600, 400),
}


def cover_resize(img, tw, th):
    """アスペクト維持で target を埋める crop+resize (歪み防止)"""
    w, h = img.size
    scale = max(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--cols', type=int, default=3)
    ap.add_argument('--rows', type=int, default=2)
    ap.add_argument('--inset', type=float, default=0.04,
                    help='各セル内側を inset 比率でトリム (枠/余白除去、 デフォルト 4%)')
    args = ap.parse_args()

    grid = Image.open(args.src).convert('RGB')
    W, H = grid.size
    cw, ch = W // args.cols, H // args.rows
    print(f'grid {W}x{H} → cell {cw}x{ch}')

    for (r, c), (fname, tw, th) in LAYOUT.items():
        x0, y0 = c * cw, r * ch
        # inset トリム (セル境界の白枠を除去)
        ix, iy = int(cw * args.inset), int(ch * args.inset)
        cell = grid.crop((x0 + ix, y0 + iy, x0 + cw - ix, y0 + ch - iy))
        out_img = cover_resize(cell, tw, th)
        dst = OUT / fname
        out_img.save(dst, 'PNG', optimize=True)
        print(f'  [{r},{c}] → {fname} ({tw}x{th}, {dst.stat().st_size//1024}KB)')

    print('\n=== Done: 6 images placed ===')


if __name__ == '__main__':
    main()
