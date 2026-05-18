"""step3b_thumbnail.py
Gemini ネイティブ画像生成でサムネ用ベース画像を生成 → Pillow でタイトル文字焼込み。
- 出力: output/<id>_thumb.png  (1280x720, YouTube カスタムサムネ用 < 2MB)
- フォント: Noto Sans CJK JP (Linux GHA) / Yu Gothic (Windows)
- model: gemini-2.5-flash-image-preview (env GEMINI_IMG_MODEL)
"""
import os, sys, json, base64
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
GEMINI_IMG_MODEL = os.environ.get("GEMINI_IMG_MODEL", "gemini-2.5-flash-image-preview")

THUMB_W = 1280
THUMB_H = 720


def call_imagen(prompt):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_IMG_MODEL}:generateContent?key={GEMINI_API_KEY}")
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
        raise RuntimeError(f"no candidates: {data}")
    parts = cands[0].get("content", {}).get("parts", [])
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError("no image inline_data in response")


def find_font(size):
    from PIL import ImageFont
    for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
              "C:/Windows/Fonts/YuGothB.ttc",
              "C:/Windows/Fonts/yugothb.ttc",
              "C:/Windows/Fonts/meiryob.ttc"]:
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


def overlay_title(img_bytes, title, category, out_path):
    from PIL import Image, ImageDraw
    from io import BytesIO

    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    if img.size != (THUMB_W, THUMB_H):
        img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    drv = ImageDraw.Draw(overlay)
    for y in range(THUMB_H // 2, THUMB_H):
        r = (y - THUMB_H // 2) / (THUMB_H // 2)
        a = int(180 * r)
        drv.rectangle([0, y, THUMB_W, y + 1], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    lines = wrap_title(title, mx=12)
    font_size = 96 if len(lines) <= 1 else 84
    font = find_font(font_size)
    lws, lhs = [], []
    for ln in lines:
        b = draw.textbbox((0, 0), ln, font=font)
        lws.append(b[2] - b[0])
        lhs.append(b[3] - b[1])
    total_h = sum(lhs) + 12 * (len(lines) - 1)
    y0 = THUMB_H - total_h - 60
    for i, ln in enumerate(lines):
        x = (THUMB_W - lws[i]) // 2
        y = y0 + sum(lhs[:i]) + 12 * i
        for dx in (-3, -2, 0, 2, 3):
            for dy in (-3, -2, 0, 2, 3):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0))
        draw.text((x, y), ln, font=font, fill=(255, 255, 255))

    cat_font = find_font(36)
    cat_text = f"#{category}"
    cb = draw.textbbox((0, 0), cat_text, font=cat_font)
    pad = 12
    draw.rectangle([40, 40, 40 + (cb[2] - cb[0]) + pad * 2,
                    40 + (cb[3] - cb[1]) + pad * 2], fill=(180, 30, 60))
    draw.text((40 + pad, 40 + pad), cat_text, font=cat_font, fill=(255, 255, 255))

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
        f"strong visual focal point in upper half of frame, "
        f"bottom half slightly darker to leave space for overlay text, "
        f"no text, no watermark, no logo, no minors, no nudity. Aspect 16:9."
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
        print(f"[step3b_thumb] FATAL: Gemini image gen failed: {last_err}")
        sys.exit(2)
    out_path = OUTPUT_DIR / f"{tid}_thumb.png"
    overlay_title(img_bytes, title, category, out_path)


if __name__ == "__main__":
    main()
