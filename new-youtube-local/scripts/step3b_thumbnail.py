"""step3b_thumbnail.py
Gemini Imagen でサムネ用ベース画像を生成 → Pillow でタイトル文字焼込み。
- 入力: output/current.json
- 出力: output/<id>_thumb.png  (1280x720, YouTube カスタムサムネ用 < 2MB)
"""
import os, sys, json, base64
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
# Default = Gemini 3.1 Flash Image (Nano Banana 2), available since 2026-02-26.
# Older 2.5-flash-image returns 404 on this account.
GEMINI_IMG_MODEL = os.environ.get("GEMINI_IMG_MODEL", "gemini-3.1-flash-image-preview")
# Optional comma-separated fallback chain of model names tried in order on 404.
GEMINI_IMG_FALLBACK = [
    m.strip() for m in os.environ.get(
        "GEMINI_IMG_FALLBACK",
        "gemini-2.5-flash-image,gemini-3-pro-image-preview,imagen-4.0-generate-001",
    ).split(",") if m.strip()
]

THUMB_W = 1280
THUMB_H = 720


def _call_generate_content(model, prompt):
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           + model + ":generateContent?key=" + GEMINI_API_KEY)
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    cands = data.get("candidates", [])
    if not cands:
        raise RuntimeError("no candidates from " + model + ": " + json.dumps(data)[:300])
    parts = cands[0].get("content", {}).get("parts", [])
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            if mime.startswith("image/"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("no image inline_data from " + model + " in response")


def _call_imagen_predict(model, prompt):
    """Imagen 4 dedicated endpoint (predict). Used when model name starts with 'imagen-'."""
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           + model + ":predict?key=" + GEMINI_API_KEY)
    body = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    preds = data.get("predictions", [])
    for p in preds:
        b64 = p.get("bytesBase64Encoded")
        if b64:
            return base64.b64decode(b64)
    raise RuntimeError("no predictions image from " + model + ": " + json.dumps(data)[:300])


def call_imagen(prompt):
    """Try primary model, fall back through chain on 404/error."""
    models = [GEMINI_IMG_MODEL] + GEMINI_IMG_FALLBACK
    last_err = None
    for m in models:
        try:
            if m.startswith("imagen-"):
                return _call_imagen_predict(m, prompt)
            return _call_generate_content(m, prompt)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="ignore")[:200]
            except Exception:
                pass
            print("[step3b_thumb] model " + m + " HTTP " + str(e.code) + ": " + body)
            last_err = e
            if e.code != 404:
                # non-404 — abort fallback (likely safety/quota)
                raise
        except Exception as e:
            print("[step3b_thumb] model " + m + " error: " + str(e))
            last_err = e
    raise RuntimeError("all image models failed: " + str(last_err))


def find_font(size):
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
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


def wrap_title(title, max_chars_per_line=12):
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


def overlay_title(img_bytes, title, category, out_path):
    from PIL import Image, ImageDraw
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

    line_heights, line_widths = [], []
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
    cat_text = "#" + category
    cat_bbox = draw.textbbox((0, 0), cat_text, font=cat_font)
    pad = 12
    draw.rectangle(
        [40, 40, 40 + (cat_bbox[2] - cat_bbox[0]) + pad * 2, 40 + (cat_bbox[3] - cat_bbox[1]) + pad * 2],
        fill=(180, 30, 60),
    )
    draw.text((40 + pad, 40 + pad), cat_text, font=cat_font, fill=(255, 255, 255))

    img.save(out_path, format="PNG", optimize=True)
    sz = out_path.stat().st_size
    print("[step3b_thumb] wrote " + str(out_path) + " (" + str(sz//1024) + "KB)")
    if sz > 2 * 1024 * 1024:
        jpeg_path = out_path.with_suffix(".jpg")
        img.save(jpeg_path, format="JPEG", quality=88, optimize=True)
        print("[step3b_thumb] >2MB, JPEG fallback")


def main():
    if not GEMINI_API_KEY:
        print("[step3b_thumb] FATAL: GEMINI_API_KEY not set")
        sys.exit(1)
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    tid = cur["id"]
    title = cur["title"]
    category = cur.get("category", "")
    print("[step3b_thumb] generate thumb for " + tid + ": " + title)

    prompt = (
        "YouTube thumbnail for adult psychology channel. "
        "Theme: " + title + ". Category: " + category + ". "
        "Cinematic dark moody portrait, dramatic rim lighting, "
        "sensual but tasteful, modern Japan night scene, photorealistic 35mm, "
        "focal point in upper half, bottom half darker for text overlay, "
        "no text, no watermark, no logo, no minors, no nudity."
    )
    img_bytes = None
    last_err = None
    for attempt in range(3):
        try:
            img_bytes = call_imagen(prompt)
            break
        except Exception as e:
            last_err = e
            print("[step3b_thumb] retry " + str(attempt) + ": " + str(e))
    if img_bytes is None:
        print("[step3b_thumb] FATAL: Imagen failed: " + str(last_err))
        sys.exit(2)
    out_path = OUTPUT_DIR / (tid + "_thumb.png")
    overlay_title(img_bytes, title, category, out_path)


if __name__ == "__main__":
    main()
