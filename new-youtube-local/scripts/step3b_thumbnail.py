"""step3b_thumbnail.py
Gemini Imagen でサムネ用ベース画像を生成 → Pillow でタイトル文字焼込み。
- 入力: output/current.json
- 出力: output/<id>_thumb.png  (1280x720, YouTube カスタムサムネ用 < 2MB)
- フォント: DejaVuSans-Bold + Noto Sans CJK JP (Linux GHA) / Yu Gothic (Windows)
"""
import os, sys, json, base64, textwrap
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
IMAGEN_MODEL = os.environ.get("IMAGEN_MODEL", "imagen-3.0-generate-002")
IMAGEN_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN_MODEL}:predict"

THUMB_W = 1280
THUMB_H = 720


def call_imagen(prompt: str) -> bytes:
    url = f"{IMAGEN_ENDPOINT}?key={GEMINI_API_KEY}"
    body = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9",
            "personGeneration": "allow_adult",
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    preds = data.get("predictions", [])
    if not preds:
        raise RuntimeError(f"no predictions: {data}")
    b64 = preds[0].get("bytesBase64Encoded") or preds[0].get("image", {}).get("bytesBase64Encoded")
    if not b64:
        raise RuntimeError("no image bytes")
    return base64.b64decode(b64)


def find_font(size: int):
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/yugothb.ttc",
        "C:/Windows/Fonts/meiryob.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_title(title: str, max_chars_per_line: int = 12):
    title = title.strip()
    if len(title) <= max_chars_per_line:
        return [title]
    cut_chars = "、。！？　・「」"
    best = -1
    for i, ch in enumerate(title):
        if i >= max_chars_per_line - 2 and i <= max_chars_per_line + 4 and ch in cut_chars:
            best = i + 1
            break
    if best < 0:
        best = max_chars_per_line
    line1 = title[:best].rstrip("、。！？　")
    line2 = title[best:].lstrip("、。！？　")
    if len(line2) > max_chars_per_line + 4:
        line2 = line2[: max_chars_per_line + 2] + "…"
    return [line1, line2] if line2 else [line1]


def overlay_title(img_bytes: bytes, title: str, category: str, out_path: Path):
    from PIL import Image, ImageDraw, ImageFilter
    from io import BytesIO

    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    if img.size != (THUMB_W, THUMB_H):
        img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    for y in range(THUMB_H // 2, THUMB_H):
        ratio = (y - THUMB_H // 2) / (THUMB_H // 2)
        alpha = int(180 * ratio)
        draw_ov.rectangle([0, y, THUMB_W, y + 1], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    lines = wrap_title(title, max_chars_per_line=12)
    font_size = 96 if len(lines) <= 1 else 84
    font = find_font(font_size)

    line_heights = []
    line_widths = []
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])
    total_h = sum(line_heights) + 12 * (len(lines) - 1)

    y0 = THUMB_H - total_h - 60
    for i, ln in enumerate(lines):
        x = (THUMB_W - line_widths[i]) // 2
        y = y0 + sum(line_heights[:i]) + 12 * i
        for dx in (-3, -2, 0, 2, 3):
            for dy in (-3, -2, 0, 2, 3):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0))
        draw.text((x, y), ln, font=font, fill=(255, 255, 255))

    cat_font = find_font(36)
    cat_text = f"#{category}"
    cat_bbox = draw.textbbox((0, 0), cat_text, font=cat_font)
    pad = 12
    draw.rectangle(
        [40, 40, 40 + (cat_bbox[2] - cat_bbox[0]) + pad * 2, 40 + (cat_bbox[3] - cat_bbox[1]) + pad * 2],
        fill=(180, 30, 60),
    )
    draw.text((40 + pad, 40 + pad), cat_text, font=cat_font, fill=(255, 255, 255))

    img.save(out_path, format="PNG", optimize=True)
    sz = out_path.stat().st_size
    print(f"[step3b_thumb] wrote {out_path} ({sz/1024:.1f}KB, {THUMB_W}x{THUMB_H})")
    if sz > 2 * 1024 * 1024:
        jpeg_path = out_path.with_suffix(".jpg")
        img.save(jpeg_path, format="JPEG", quality=88, optimize=True)
        print(f"[step3b_thumb] PNG > 2MB, fallback JPEG: {jpeg_path} ({jpeg_path.stat().st_size/1024:.1f}KB)")
        try:
            out_path.unlink()
        except Exception:
            pass


def main():
    if not GEMINI_API_KEY:
        print("[step3b_thumb] FATAL: GEMINI_API_KEY (or GOOGLE_API_KEY) not set")
        sys.exit(1)

    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    tid = cur["id"]
    title = cur["title"]
    category = cur.get("category", "")
    print(f"[step3b_thumb] generate thumb for {tid}: {title}")

    prompt = (
        f"YouTube thumbnail base image for adult psychology channel. "
        f"Theme: {title}. Category: {category}. "
        f"Cinematic dark moody portrait composition, dramatic rim lighting, "
        f"sensual but tasteful, modern Japan night scene, photorealistic 35mm, "
        f"strong visual focal point in the upper half of frame, "
        f"bottom half slightly darker to leave space for overlay text, "
        f"no text, no watermark, no logo, no minors, no nudity."
    )
    img_bytes = None
    last_err = None
    for attempt in range(3):
        try:
            img_bytes = call_imagen(prompt)
            break
        except Exception as e:
            last_err = e
            print(f"[step3b_thumb] retry {attempt}: {e}")
    if img_bytes is None:
        print(f"[step3b_thumb] FATAL: Imagen failed: {last_err}")
        sys.exit(2)

    out_path = OUTPUT_DIR / f"{tid}_thumb.png"
    overlay_title(img_bytes, title, category, out_path)


if __name__ == "__main__":
    main()
