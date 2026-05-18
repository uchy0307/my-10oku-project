"""step3b_thumbnail.py
Gemini Imagen サムネ + Pillow タイトル焼込み
"""
import os, sys, json, base64
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent

# .env loader
_ENV = ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _k = _k.strip(); _v = _v.strip()
        if _k and _k not in os.environ:
            os.environ[_k] = _v

OUTPUT_DIR = ROOT / "output"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
GEMINI_IMG_MODEL = os.environ.get("GEMINI_IMG_MODEL", "gemini-3.1-flash-image-preview")
GEMINI_IMG_FALLBACK = [m.strip() for m in os.environ.get(
    "GEMINI_IMG_FALLBACK",
    "gemini-2.5-flash-image,gemini-3-pro-image-preview,imagen-4.0-generate-001",
).split(",") if m.strip()]

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
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    cands = data.get("candidates", [])
    if not cands:
        raise RuntimeError("no candidates from " + model)
    parts = cands[0].get("content", {}).get("parts", [])
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            if mime.startswith("image/"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("no image from " + model)


def _call_imagen_predict(model, prompt):
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           + model + ":predict?key=" + GEMINI_API_KEY)
    body = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for p in data.get("predictions", []):
        b64 = p.get("bytesBase64Encoded")
        if b64:
            return base64.b64decode(b64)
    raise RuntimeError("no predictions from " + model)


def call_imagen(prompt):
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
            print("[step3b_thumb] " + m + " HTTP " + str(e.code) + ": " + body)
            last_err = e
            if e.code != 404:
                raise
        except Exception as e:
            print("[step3b_thumb] " + m + " error: " + str(e))
            last_err = e
    raise RuntimeError("all image models failed: " + str(last_err))


def find_font(size):
    from PIL import ImageFont
    for p in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/yugothb.ttc",
        "C:/Windows/Fonts/meiryob.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def wrap_title(title, max_chars=12):
    t = title.strip()
    if len(t) <= max_chars:
        return [t]
    cut = "、。！？　・「」"
    best = -1
    for i, ch in enumerate(t):
        if i >= max_chars - 2 and i <= max_chars + 4 and ch in cut:
            best = i + 1
            break
    if best < 0:
        best = max_chars
    l1 = t[:best].rstrip("、。！？　")
    l2 = t[best:].lstrip("、。！？　")
    if len(l2) > max_chars + 4:
        l2 = l2[:max_chars + 2] + "…"
    return [l1, l2] if l2 else [l1]


def overlay_title(img_bytes, title, category, out_path):
    from PIL import Image, ImageDraw
    from io import BytesIO

    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    if img.size != (THUMB_W, THUMB_H):
        img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dov = ImageDraw.Draw(overlay)
    for y in range(THUMB_H // 2, THUMB_H):
        a = int(180 * (y - THUMB_H // 2) / (THUMB_H // 2))
        dov.rectangle([0, y, THUMB_W, y + 1], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    lines = wrap_title(title, 12)
    font = find_font(96 if len(lines) <= 1 else 84)

    lh, lw = [], []
    for ln in lines:
        bb = draw.textbbox((0, 0), ln, font=font)
        lw.append(bb[2] - bb[0])
        lh.append(bb[3] - bb[1])
    total_h = sum(lh) + 12 * (len(lines) - 1)
    y0 = THUMB_H - total_h - 60
    for i, ln in enumerate(lines):
        x = (THUMB_W - lw[i]) // 2
        y = y0 + sum(lh[:i]) + 12 * i
        for dx in (-3, -2, 0, 2, 3):
            for dy in (-3, -2, 0, 2, 3):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0))
        draw.text((x, y), ln, font=font, fill=(255, 255, 255))

    cf = find_font(36)
    ct = "#" + category
    cb = draw.textbbox((0, 0), ct, font=cf)
    pad = 12
    draw.rectangle([40, 40, 40 + (cb[2] - cb[0]) + pad * 2, 40 + (cb[3] - cb[1]) + pad * 2], fill=(180, 30, 60))
    draw.text((40 + pad, 40 + pad), ct, font=cf, fill=(255, 255, 255))

    img.save(out_path, format="PNG", optimize=True)
    sz = out_path.stat().st_size
    print("[step3b_thumb] wrote " + str(out_path) + " (" + str(sz // 1024) + "KB)")
    if sz > 2 * 1024 * 1024:
        jpeg = out_path.with_suffix(".jpg")
        img.save(jpeg, format="JPEG", quality=88, optimize=True)
        print("[step3b_thumb] >2MB, jpeg fallback")


def main():
    if not GEMINI_API_KEY:
        print("[step3b_thumb] FATAL: GEMINI_API_KEY not set")
        sys.exit(1)
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    tid = cur["id"]
    title = cur["title"]
    category = cur.get("category", "")
    print("[step3b_thumb] " + tid + ": " + title + " (" + category + ")")

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
            print("[step3b_thumb] attempt " + str(attempt) + ": " + str(e))
    if img_bytes is None:
        print("[step3b_thumb] FATAL: " + str(last_err))
        sys.exit(2)
    out = OUTPUT_DIR / (tid + "_thumb.png")
    overlay_title(img_bytes, title, category, out)


if __name__ == "__main__":
    main()
