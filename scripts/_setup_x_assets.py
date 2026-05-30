#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""アップロード画像を assets/x_branding/banner.png + avatar.png にコピー + リサイズ。

使い方:
  python scripts/_setup_x_assets.py --banner <path> --avatar <path>
"""
import argparse, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    from PIL import Image
except ImportError:
    print('[FATAL] Pillow 未導入。 pip install pillow', file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'assets' / 'x_branding'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def resize_save(src, dst, target_size, label):
    img = Image.open(src).convert('RGB')
    w, h = img.size
    print(f'[{label}] src: {w}x{h}, target: {target_size[0]}x{target_size[1]}')
    img = img.resize(target_size, Image.LANCZOS)
    img.save(dst, 'PNG', optimize=True)
    size_kb = dst.stat().st_size // 1024
    print(f'[{label}] saved: {dst.name} ({size_kb}KB)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--banner', required=True, help='バナー画像 src path')
    ap.add_argument('--avatar', required=True, help='アバター画像 src path')
    args = ap.parse_args()

    resize_save(Path(args.banner), OUT_DIR / 'banner.png', (1500, 500), 'banner')
    resize_save(Path(args.avatar), OUT_DIR / 'avatar.png', (400, 400), 'avatar')
    print('\n=== Done ===')


if __name__ == '__main__':
    main()
