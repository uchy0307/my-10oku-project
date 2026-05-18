"""step3b_thumbnail.py
Pillow-only thumbnail generator (no AI model - Gemini Imagen access pending).
Generates a 1280x720 thumbnail with title text overlay on a moody gradient.
"""
import os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
THUMB_W = 1280
THUMB_H = 720


def find_font(size):
    from PIL import ImageFont
    for p in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/yugothb.ttc",
        "C:/Windows/Fonts/meiryob.ttc",
    ]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_title(title, mx=12):
    title = title.strip()
    if len(title) <= mx:
        return [title]
    cut_chars = "、。！？　・「」"
    best = -1
    for i, ch in enumerate(title):
        if i >= mx - 2 and i <= mx + 4 and ch in cut_chars:
            best = i + 1
            break
    if best < 0:
        best = mx
    line1 = title[:best].rstrip("、。！？　")
    line2 = title[best:].lstrip("、。！？　")
    if len(line2) > mx + 4:
        line2 = line2[: mx + 2] + "…"
    return [line1, line2] if line2 else [line1]


def main():
    from PIL import Image, ImageDraw
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    tid = cur["id"]
    title = cur["title"]
    category = cur.get("category", "")
    out_path = OUTPUT_DIR / f"{tid}_thumb.png"

    # Moody gradient: dark navy at top, deeper at bottom
    img = Image.new("RGB", (THUMB_W, THUMB_H), (28, 30, 52))
    d = ImageDraw.Draw(img)
    for y in range(THUMB_H):
        ratio = y / THUMB_H
        r = int(28 + 20 * (1 - ratio))
        g = int(30 + 10 * (1 - ratio))
        b = int(52 - 30 * ratio)
        d.line([(0, y), (THUMB_W, y)], fill=(max(8, r), max(8, g), max(8, b)))

    # Title text - center
    lines = wrap_title(title, mx=12)
    font_size = 96 if len(lines) == 1 else 84
    font = find_font(font_size)
    lws, lhs = [], []
    for ln in lines:
        bb = d.textbbox((0, 0), ln, font=font)
        lws.append(bb[2] - bb[0])
        lhs.append(bb[3] - bb[1])
    total_h = sum(lhs) + 12 * (len(lines) - 1)
    y0 = THUMB_H // 2 - total_h // 2
    for i, ln in enumerate(lines):
        x = (THUMB_W - lws[i]) // 2
        y = y0 + sum(lhs[:i]) + 12 * i
        for dx in (-3, -2, 0, 2, 3):
            for dy in (-3, -2, 0, 2, 3):
                if dx == 0 and dy == 0:
                    continue
                d.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0))
        d.text((x, y), ln, font=font, fill=(255, 255, 255))

    # Category label - top-left
    cat_font = find_font(36)
    cat_text = f"#{category}"
    cb = d.textbbox((0, 0), cat_text, font=cat_font)
    pad = 12
    d.rectangle([40, 40, 40 + (cb[2] - cb[0]) + pad * 2,
                 40 + (cb[3] - cb[1]) + pad * 2], fill=(180, 30, 60))
    d.text((40 + pad, 40 + pad), cat_text, font=cat_font, fill=(255, 255, 255))

    img.save(out_path, format="PNG", optimize=True)
    sz = out_path.stat().st_size
    print(f"[step3b_thumb] wrote {out_path} ({sz/1024:.1f}KB)")
    if sz > 2 * 1024 * 1024:
        jp = out_path.with_suffix(".jpg")
        img.save(jp, format="JPEG", quality=88, optimize=True)
        print(f"[step3b_thumb] PNG > 2MB, JPEG fallback: {jp}")
        try:
            out_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
