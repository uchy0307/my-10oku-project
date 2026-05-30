#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
youtube/history_v2/scripts/make_thumb.py

Generate a 1280x720 YouTube thumbnail jpg for the samurai history channel.
Design (per user spec 2026-05-21):
    - Yellow background (gold tone)
    - Bold RED title text, large, auto-wrapped to fit within 92% of frame width
    - Optional hero portrait on the right side (semi-transparent overlay if used)
    - Thick white outline + drop shadow under text for legibility

Usage:
    python3 make_thumb.py --title "<title>" --out <path.jpg> [--hero <hero.jpg>]

Exits 0 on success, nonzero on failure.
"""
from __future__ import annotations
import argparse
import os
import sys
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Canvas
W, H = 1280, 720
# Background (yellow / gold)
BG_COLOR = (245, 200, 70, 255)        # warm gold
# Optional washi-style noise tint
WASHI_TINT = (235, 185, 55, 255)
# Text color (deep red)
TEXT_COLOR = (200, 16, 46, 255)       # #C8102E
TEXT_OUTLINE_COLOR = (255, 255, 255, 255)
TEXT_SHADOW_COLOR = (60, 0, 0, 180)

# Maximum text width = 92% of canvas
MAX_TEXT_W = int(W * 0.92)

# Candidate Japanese-capable font paths, in priority order.
JP_FONT_CANDIDATES = [
    # Windows (2026-05-30 追加: CLAUDE.md 既知バグ「サムネフォント Linux 決め打ち」対策)
    r"C:\Windows\Fonts\YuGothB.ttc",      # 游ゴシック Bold
    r"C:\Windows\Fonts\YuGothM.ttc",      # 游ゴシック Medium
    r"C:\Windows\Fonts\meiryob.ttc",      # メイリオ Bold
    r"C:\Windows\Fonts\meiryo.ttc",       # メイリオ
    r"C:\Windows\Fonts\msgothic.ttc",     # MS ゴシック
    r"C:\Windows\Fonts\NotoSansCJKjp-Bold.otf",
    r"C:\Windows\Fonts\BIZ-UDGothicB.ttc",
    # GitHub Actions ubuntu-latest after `apt install fonts-noto-cjk`
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    # Common local install paths
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # latin fallback (renders boxes for kanji)
]


def find_jp_font() -> str:
    for p in JP_FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise RuntimeError(
        "no usable font found (need fonts-noto-cjk on the runner)"
    )


def load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    # .ttc collections: index 0 (Black/Bold for NotoSansCJK)
    try:
        return ImageFont.truetype(font_path, size=size, index=0)
    except (TypeError, OSError):
        return ImageFont.truetype(font_path, size=size)


def measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def wrap_japanese(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_w: int,
) -> List[str]:
    """Wrap Japanese text by character: split greedily so each line fits max_w.
    Prefers breaking on Japanese punctuation / common particles when possible.
    """
    if not text:
        return []
    # Preferred break characters (don't break, but if break happens AFTER these chars it's natural).
    soft_breaks = set("ããï¼ï¼ã»ï½ã â¦")

    lines: List[str] = []
    buf = ""
    for ch in text:
        candidate = buf + ch
        w, _ = measure(draw, candidate, font)
        if w <= max_w:
            buf = candidate
            continue
        # over the limit. Try to backtrack to the last soft-break in buf.
        bt_idx = -1
        for i in range(len(buf) - 1, max(0, len(buf) - 6), -1):
            if buf[i] in soft_breaks:
                bt_idx = i
                break
        if bt_idx > 0 and bt_idx >= len(buf) // 2:
            head, tail = buf[: bt_idx + 1], buf[bt_idx + 1 :]
            lines.append(head)
            buf = tail + ch
        else:
            lines.append(buf)
            buf = ch
    if buf:
        lines.append(buf)
    return lines


def pick_font_size(
    draw: ImageDraw.ImageDraw,
    font_path: str,
    text: str,
    max_w: int,
    canvas_h: int,
    max_lines: int = 3,
    start_size: int = 130,
    min_size: int = 56,
) -> tuple[ImageFont.FreeTypeFont, List[str], int]:
    """Pick the largest font size where the wrapped text fits within max_w & max_lines."""
    # We also want a soft preference: line length 8..12 chars-ish via max_w only.
    for size in range(start_size, min_size - 1, -2):
        font = load_font(font_path, size)
        lines = wrap_japanese(draw, text, font, max_w)
        if len(lines) <= max_lines:
            # Also check total height stays under 0.78 * canvas_h
            line_h = font.size + int(font.size * 0.15)
            total_h = line_h * len(lines)
            if total_h <= int(canvas_h * 0.78):
                return font, lines, size
    # Fallback: use min size and force-wrap (truncate to max_lines)
    font = load_font(font_path, min_size)
    lines = wrap_japanese(draw, text, font, max_w)
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [lines[max_lines - 1][: max(1, len(lines[max_lines - 1]) - 1)] + "â¦"]
    return font, lines, min_size


def add_washi_texture(img: Image.Image) -> Image.Image:
    """Light noise texture to suggest washi paper."""
    import random
    rng = random.Random(42)
    px = img.load()
    for _ in range(2200):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        r, g, b, a = px[x, y]
        d = rng.randint(-14, 14)
        px[x, y] = (
            max(0, min(255, r + d)),
            max(0, min(255, g + d)),
            max(0, min(255, b + d)),
            a,
        )
    return img


def composite_hero(canvas: Image.Image, hero_path: str) -> None:
    """Overlay hero portrait on the right ~38% of frame, semi-transparent so text overlays cleanly."""
    try:
        hero = Image.open(hero_path).convert("RGBA")
    except Exception as e:
        print(f"[make_thumb] hero load failed ({e}), skipping", file=sys.stderr)
        return
    target_w = 460
    target_h = H
    # Scale + center-crop
    src_w, src_h = hero.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    hero = hero.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    hero = hero.crop((left, top, left + target_w, top + target_h))
    # Soft fade on the LEFT edge so it blends into the yellow.
    fade = Image.new("L", (target_w, target_h), 255)
    fd = ImageDraw.Draw(fade)
    for x in range(120):
        fd.rectangle([(x, 0), (x + 1, target_h)], fill=int(255 * (x / 120)))
    hero.putalpha(fade)
    canvas.alpha_composite(hero, (W - target_w, 0))


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    lines: List[str],
    font: ImageFont.FreeTypeFont,
    canvas_h: int,
) -> None:
    line_h = font.size + int(font.size * 0.15)
    total_h = line_h * len(lines)
    start_y = (canvas_h - total_h) // 2
    for i, line in enumerate(lines):
        w, _ = measure(draw, line, font)
        x = (W - w) // 2
        y = start_y + i * line_h
        # drop shadow
        draw.text((x + 4, y + 5), line, font=font, fill=TEXT_SHADOW_COLOR)
        # white outline (stroked)
        draw.text(
            (x, y),
            line,
            font=font,
            fill=TEXT_COLOR,
            stroke_width=6,
            stroke_fill=TEXT_OUTLINE_COLOR,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True, help="Japanese title (full)")
    ap.add_argument("--out", required=True, help="output jpg path")
    ap.add_argument("--hero", default=None, help="optional hero portrait jpg")
    ap.add_argument("--no-washi", action="store_true", help="disable washi texture")
    args = ap.parse_args()

    title = args.title.strip()
    # Strip leading channel-name decorations the user doesn't want in thumb if any
    # (the title is rendered as-is by default)

    font_path = find_jp_font()

    canvas = Image.new("RGBA", (W, H), BG_COLOR)
    if not args.no_washi:
        canvas = add_washi_texture(canvas)

    if args.hero and os.path.exists(args.hero):
        composite_hero(canvas, args.hero)

    draw = ImageDraw.Draw(canvas)
    font, lines, picked = pick_font_size(
        draw,
        font_path,
        title,
        MAX_TEXT_W,
        H,
        max_lines=3,
        start_size=130,
        min_size=56,
    )
    print(f"[make_thumb] font={os.path.basename(font_path)} size={picked} lines={len(lines)}")
    for i, ln in enumerate(lines):
        print(f"[make_thumb]   line{i}: {ln}")

    draw_text_block(draw, lines, font, H)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    canvas.convert("RGB").save(args.out, "JPEG", quality=92, optimize=True)
    sz = os.path.getsize(args.out)
    print(f"[make_thumb] wrote {args.out} ({sz} bytes)")
    if sz < 10000:
        print("[make_thumb] WARNING: output suspiciously small", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
