#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""toi-suite 用 OG image (1200x630) を生成"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print('Pillow 未インストール'); sys.exit(2)

OUT = Path(r'C:\Users\user\Documents\toi-suite-local\public\og.png')

W, H = 1200, 630
img = Image.new('RGB', (W, H), '#8a6030')
draw = ImageDraw.Draw(img)

# グラデ風 (簡易版: 縦に色変化)
for y in range(H):
    ratio = y / H
    r = int(0x8a + (0x5a - 0x8a) * ratio)
    g = int(0x60 + (0x3a - 0x60) * ratio)
    b = int(0x30 + (0x10 - 0x30) * ratio)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# Font 探索
fonts_dir = [
    r'C:\Windows\Fonts\YuGothB.ttc',
    r'C:\Windows\Fonts\meiryob.ttc',
    r'C:\Windows\Fonts\msmincho.ttc',
    r'C:\Windows\Fonts\YuMincho.ttf',
    r'C:\Windows\Fonts\msgothic.ttc',
]
def font(size):
    for f in fonts_dir:
        if Path(f).exists():
            try: return ImageFont.truetype(f, size)
            except: pass
    return ImageFont.load_default()

# Title
title_font = font(110)
draw.text((W/2, H/2 - 90), '200の問い', font=title_font, fill='#ffffff', anchor='mm')

# Subtitle (English)
sub_font = font(40)
draw.text((W/2, H/2 + 40), 'SAMURAI AESTHETICS', font=sub_font, fill='#f5e8d0', anchor='mm')

# Tagline
tag_font = font(28)
draw.text((W/2, H/2 + 120), '自己理解を深める200本のAI対話アプリ', font=tag_font, fill='#e8d5b5', anchor='mm')

# Bottom URL
url_font = font(24)
draw.text((W/2, H - 50), 'toi-suite.vercel.app', font=url_font, fill='#d4bd95', anchor='mm')

# Top decoration (左右に絵文字代わりに crest 風シンプル marks)
deco_font = font(60)
draw.text((100, 80), '⚔', font=font(80), fill='#f5e8d0')
draw.text((W - 130, 80), '🏯', font=font(80), fill='#f5e8d0')

# 苦徹成珠 (right top small)
draw.text((W/2, 90), '苦 徹 成 珠', font=font(36), fill='#f5e8d0', anchor='mm')

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT, 'PNG', optimize=True)
print(f'WROTE: {OUT}')
print(f'size: {OUT.stat().st_size/1024:.1f} KB')
