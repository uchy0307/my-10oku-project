"""
Step 3b: サムネ画像生成 (2026-05-20 fix)

旧版にはサムネ生成も youtube.thumbnails.set 呼び出しも一切無く、
YouTube 自動生成（動画フレーム抜き出し）に頼っていた。
本ファイルで明示的にサムネ JPEG を作成し step5 で API 経由でアップロードする。

戦略:
  1. Gemini 2.5 Flash Image でサムネ用画像を 1枚生成 (タイトル文の視覚メタファ)
  2. 取れたら Pillow で半透明オーバーレイ + 大型タイトル文字を焼く
  3. 取れなかったら 1章目の既存生成画像をベースに同様に文字を焼く
  4. それも無理なら抽象グラデにタイトル文字を焼く (最後の砦, ただしテキストはサムネには必須)

完全無料軸: Gemini Nano Banana (free tier 200req/day) のみ使用。
"""
from __future__ import annotations
import os
import io
import re
import sys
import base64
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
GEMINI_IMG_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp-image-generation",
]

# Linux runner で必ず存在する Noto CJK
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    # Windows ローカルテスト用
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
]


def _find_font(size: int) -> ImageFont.ImageFont:
    for fp in FONT_CANDIDATES:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _gen_background_via_gemini(prompt: str, out: Path) -> bool:
    """Try Gemini image cascade. Same as step3 but extracted here to avoid
    coupling step3b on step3 internals."""
    if not GEMINI_API_KEY:
        return False
    for model in GEMINI_IMG_MODELS:
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
                f":generateContent?key={GEMINI_API_KEY}"
            )
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
            }
            r = requests.post(url, json=body, timeout=180,
                              headers={"Content-Type": "application/json"})
            r.raise_for_status()
            data = r.json()
            cands = data.get("candidates") or []
            if not cands:
                continue
            for p in cands[0].get("content", {}).get("parts", []):
                inline = p.get("inlineData") or p.get("inline_data")
                if inline and inline.get("data"):
                    img = Image.open(io.BytesIO(base64.b64decode(inline["data"]))).convert("RGB")
                    img = img.resize((W, H), Image.LANCZOS)
                    img.save(out, "JPEG", quality=92)
                    print(f"[step3b] background OK model={model}")
                    return True
        except Exception as e:
            print(f"[step3b] {model} failed: {e}")
    return False


def _gen_background_abstract(out: Path) -> None:
    import random
    random.seed(42)
    img = Image.new("RGB", (W, H), (12, 12, 24))
    d = ImageDraw.Draw(img)
    for y in range(H):
        r = int(20 + (y / H) * 30)
        g = int(15 + (y / H) * 20)
        b = int(60 + (y / H) * 80)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    img.save(out, "JPEG", quality=88)


def _wrap_jp(text: str, max_chars_per_line: int) -> list[str]:
    """日本語タイトルを max_chars_per_line で機械的に折り返す。"""
    text = re.sub(r"\s+", "", text)
    return [text[i:i+max_chars_per_line]
            for i in range(0, len(text), max_chars_per_line)]


def _overlay_title(base_path: Path, title: str, out_path: Path) -> None:
    img = Image.open(base_path).convert("RGB")
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
    # 下部に半透明ブラックバー
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    bar_top = int(H * 0.45)
    od.rectangle([(0, bar_top), (W, H)], fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    d = ImageDraw.Draw(img)
    font_big = _find_font(86)
    font_sub = _find_font(40)
    # タイトルを 1-2 行に折り返し（最大 12 文字/行）
    lines = _wrap_jp(title, 12)[:2]
    total_h = sum(font_big.getbbox(ln)[3] - font_big.getbbox(ln)[1] for ln in lines) + 30
    y = bar_top + (H - bar_top - total_h) // 2
    for ln in lines:
        bbox = font_big.getbbox(ln)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        # 黒縁取り（5方向シャドウ）
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (3, 3)):
            d.text((x + dx, y + dy), ln, font=font_big, fill=(0, 0, 0))
        d.text((x, y), ln, font=font_big, fill=(255, 230, 110))  # 山吹色
        y += (bbox[3] - bbox[1]) + 18
    # 右下角に「大人の心理学」サブ
    sub = "大人の心理学"
    sb = font_sub.getbbox(sub)
    sx = W - (sb[2] - sb[0]) - 30
    sy = H - (sb[3] - sb[1]) - 22
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        d.text((sx + dx, sy + dy), sub, font=font_sub, fill=(0, 0, 0))
    d.text((sx, sy), sub, font=font_sub, fill=(255, 255, 255))

    img.save(out_path, "JPEG", quality=88)
    print(f"[step3b] thumbnail written: {out_path} ({out_path.stat().st_size} bytes)")


def generate_thumbnail(script: dict, fallback_image: Path | None,
                       out_path: Path) -> Path:
    """Build thumbnail JPEG. Returns out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg_path = out_path.parent / "_thumb_bg.jpg"

    # Prompt: タイトルの視覚メタファ
    title = script["title"]
    thumb_prompt = (
        f"Cinematic 16:9 thumbnail background photo, dramatic mood lighting, "
        f"empty composition with negative space at bottom half for text overlay. "
        f"Visual metaphor for the topic: '{title}'. "
        f"NO PEOPLE in foreground, NO faces, NO text in image, NO writing. "
        f"Object-only or abstract composition: empty cafe interior, window light, "
        f"books on desk, rain on glass, neon street at night, soft bokeh. "
        f"Modern japanese aesthetic, dim warm or melancholic blue lighting, "
        f"professional cinematography, no AI artifacts."
    )

    bg_ready = _gen_background_via_gemini(thumb_prompt, bg_path)
    if not bg_ready:
        if fallback_image and fallback_image.exists():
            try:
                Image.open(fallback_image).convert("RGB").resize((W, H), Image.LANCZOS).save(bg_path, "JPEG", quality=88)
                bg_ready = True
                print(f"[step3b] using fallback image: {fallback_image}")
            except Exception as e:
                print(f"[step3b] fallback image load failed: {e}")
    if not bg_ready:
        _gen_background_abstract(bg_path)
        print("[step3b] abstract background fallback")

    _overlay_title(bg_path, title, out_path)
    try:
        bg_path.unlink()
    except Exception:
        pass
    return out_path


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script
    sp = sys.argv[1] if len(sys.argv) > 1 else "inputs/script_001.json"
    script = read_script(sp)
    out = Path("outputs/thumb.jpg")
    generate_thumbnail(script, None, out)
    print(f"thumbnail: {out}")
