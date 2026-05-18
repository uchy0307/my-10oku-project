"""step3b_thumbnail.py
Imagen-generated 1280x720 thumbnail with title text overlay.
Falls back to gradient if Imagen API fails.
"""
import os, sys, json, base64
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
THUMB_W = 1280
THUMB_H = 720

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")

THUMB_MODELS = [
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-generate-001",
    "imagen-3.0-generate-001",
    "imagen-3.0-fast-generate-001",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp-image-generation",
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
]


def call_image_gen(prompt, model):
    if model.startswith("imagen"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={GEMINI_API_KEY}"
        body = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}}
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if "predictions" in data:
            preds = data.get("predictions", [])
            if not preds:
                raise RuntimeError("no predictions")
            b64 = preds[0].get("bytesBase64Encoded") or (preds[0].get("image") or {}).get("bytesBase64Encoded")
            if not b64:
                raise RuntimeError("no bytes")
            return base64.b64decode(b64)
        cands = data.get("candidates", [])
        if not cands:
            raise RuntimeError(f"no candidates: {json.dumps(data)[:200]}")
        parts = cands[0].get("content", {}).get("parts", [])
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
        raise RuntimeError("no inline_data in response")



def fetch_thumbnail_background(prompt, out_tmp_path):
    if not GEMINI_API_KEY:
        print("[step3b_thumb] GEMINI_API_KEY missing - falling back to gradient")
        return False
    for m in THUMB_MODELS:
        try:
            img_bytes = call_image_gen(prompt, m)
            out_tmp_path.write_bytes(img_bytes)
            print(f"[step3b_thumb] thumbnail bg OK using model={m}")
            return True
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")[:200]
            print(f"[step3b_thumb] {m} HTTP {e.code}: {msg}")
        except Exception as e:
            print(f"[step3b_thumb] {m} exc: {e}")
    return False


def fit_to_thumb_size(src_path):
    from PIL import Image
    with Image.open(src_path) as im:
        im = im.convert("RGB")
        sw, sh = im.size
        ta = THUMB_W / THUMB_H
        sa = sw / sh
        if abs(sa - ta) < 0.005:
            return im.resize((THUMB_W, THUMB_H), Image.LANCZOS)
        if sa > ta:
            new_w = THUMB_W
            new_h = int(THUMB_W / sa)
            res = im.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGB", (THUMB_W, THUMB_H), (0, 0, 0))
            canvas.paste(res, (0, (THUMB_H - new_h) // 2))
            return canvas
        else:
            new_h = THUMB_H
            new_w = int(THUMB_H * sa)
            res = im.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGB", (THUMB_W, THUMB_H), (0, 0, 0))
            canvas.paste(res, ((THUMB_W - new_w) // 2, 0))
            return canvas


def gradient_bg():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (THUMB_W, THUMB_H), (28, 30, 52))
    d = ImageDraw.Draw(img)
    for y in range(THUMB_H):
        ratio = y / THUMB_H
        r = int(28 + 20 * (1 - ratio))
        g = int(30 + 10 * (1 - ratio))
        b = int(52 - 30 * ratio)
        d.line([(0, y), (THUMB_W, y)], fill=(max(8, r), max(8, g), max(8, b)))
    return img



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
    cut_chars = "、。！？ ・「」"
    best = -1
    for i, ch in enumerate(title):
        if i >= mx - 2 and i <= mx + 4 and ch in cut_chars:
            best = i + 1
            break
    if best < 0:
        best = mx
    line1 = title[:best].rstrip("、。！？ ")
    line2 = title[best:].lstrip("、。！？ ")
    if len(line2) > mx + 4:
        line2 = line2[: mx + 2] + "…"
    return [line1, line2] if line2 else [line1]


def make_thumb_prompt(title, category):
    return (
        f"Wide 16:9 cinematic thumbnail background for a Japanese adult psychology channel. "
        f"Title theme: {title}. Category: {category}. "
        f"Moody dramatic atmosphere, low-key lighting, japanese urban night, soft bokeh, suggestive but tasteful, "
        f"no nudity, no minors, no visible text, plenty of negative space in upper-center for title overlay. "
        f"Color palette: deep navy, burgundy, gold accents."
    )



def main():
    from PIL import Image, ImageDraw
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    tid = cur["id"]
    title = cur["title"]
    category = cur.get("category", "")
    out_path = OUTPUT_DIR / f"{tid}_thumb.png"
    tmp_path = OUTPUT_DIR / f"{tid}_thumb_bg_raw.jpg"

    bg_img = None
    if fetch_thumbnail_background(make_thumb_prompt(title, category), tmp_path):
        try:
            bg_img = fit_to_thumb_size(tmp_path)
        except Exception as e:
            print(f"[step3b_thumb] fit failed: {e}")
            bg_img = None
        try:
            tmp_path.unlink()
        except Exception:
            pass
    if bg_img is None:
        print("[step3b_thumb] using gradient fallback")
        bg_img = gradient_bg()

    d = ImageDraw.Draw(bg_img)
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

    cat_font = find_font(36)
    cat_text = f"#{category}"
    cb = d.textbbox((0, 0), cat_text, font=cat_font)
    pad = 12
    d.rectangle([40, 40, 40 + (cb[2] - cb[0]) + pad * 2,
                 40 + (cb[3] - cb[1]) + pad * 2], fill=(180, 30, 60))
    d.text((40 + pad, 40 + pad), cat_text, font=cat_font, fill=(255, 255, 255))

    bg_img.save(out_path, format="PNG", optimize=True)
    sz = out_path.stat().st_size
    print(f"[step3b_thumb] wrote {out_path} ({sz/1024:.1f}KB)")
    if sz > 2 * 1024 * 1024:
        jp = out_path.with_suffix(".jpg")
        bg_img.save(jp, format="JPEG", quality=88, optimize=True)
        print(f"[step3b_thumb] PNG > 2MB, JPEG fallback: {jp}")
        try:
            out_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()

