"""
Step 3: 大人アニメ調 画像自動生成

Service : Pollinations.ai flux (samurai と同じ)
Style   : 25-40代女性 / OL/キャリア/主婦 / オフィスカジュアル
NG      : 制服/学生/性的示唆 系プロンプトは validate で reject

固定テンプレートでプロンプトを構築し、シーン記述のみ差し替える。
キャッシュ: SHA256(full_prompt) → cache/images/<key>.jpg
"""
from __future__ import annotations
import sys as _flush_sys
try:
    _flush_sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
import builtins as _flush_b
if not hasattr(_flush_b, "_orig_print"):
    _flush_b._orig_print = _flush_b.print
    def _flush_print(*a, **k):
        k.setdefault("flush", True)
        return _flush_b._orig_print(*a, **k)
    _flush_b.print = _flush_print

import hashlib
import time
import json
import base64
from pathlib import Path
from urllib.parse import quote
import requests
import os
import io
from PIL import Image, ImageDraw, ImageFont

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/"
MODEL = "flux"
WIDTH, HEIGHT = 1280, 720

# --- Gemini (Nano Banana / Imagen) primary backend (2026-05-20 fix) ---
# Free tier: gemini-2.5-flash-image (Nano Banana) ~200 req/day, no billing required.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
GEMINI_IMG_MODELS = [
    # 無料 tier (Nano Banana). 動けばこれだけで通る。
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp-image-generation",
    # billing 有効プロジェクトでは Imagen に fall through (free tier では 403 → 次へ)
    "imagen-4.0-fast-generate-001",
    "imagen-3.0-fast-generate-001",
    "imagen-3.0-generate-001",
]
_gemini_working_model = None

PROMPT_TEMPLATE = (
    "cinematic photograph, 16:9 aspect, 1280x720, NO PEOPLE in foreground, "
    "NO PORTRAIT, NO FACES, OBJECT-ONLY composition, "
    "modern japanese aesthetic, soft pastel or melancholic dim lighting, "
    "professional clean composition, no AI artifacts, no horror, no deformed features, "
    "subject: {scene}"
)

NEGATIVE = (
    "human face, portrait, close-up of person, multiple people, group shot, "
    "stretched face, distorted face, horror, deformed, "
    "nude, naked, topless, sexual, suggestive, school, uniform, "
    "child, minor, underage, schoolgirl, loli"
)

# 拒否するトークン (含まれていたら ValueError)
NG_TOKENS = [
    # 性表現
    "nude", "naked", "topless", "nipple", "breast cleavage", "cleavage",
    "sex", "erotic", "nsfw", "porn", "lingerie", "panties", "underwear",
    # 性的示唆 (前回スコープで除外)
    "sultry", "bedroom eyes", "parted lips", "seductive",
    "bedroom", "body-conscious", "body conscious",
    "tight knit", "highlighting body", "fitted body", "elegant curves",
    # 未成幸連想
    "school", "uniform", "schoolgirl", "student", "child", "minor",
    "underage", "young girl", "loli",
    # 日本語
    "制服", "学生", "セーラー", "JK", "JC", "少女",
    "裸", "ヌード", "露出", "性的", "下着", "ランジェリー",
]



# --- Fallback backends ---
HF_API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_TOKEN") or ""
TOGETHER_API_URL = "https://api.together.xyz/v1/images/generations"
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
POLLINATIONS_MAX_ATTEMPTS = 2  # 2 consecutive failures -> next backend
PER_CALL_DELAY_SEC = 5  # spacing between image calls to reduce 500s

def _validate(scene_prompt: str) -> None:
    low = scene_prompt.lower()
    for tok in NG_TOKENS:
        if tok.lower() in low:
            raise ValueError(
                f"Rejected prompt fragment '{tok}' in: {scene_prompt[:80]}"
            )


def _cache_key(full_prompt: str, seed: int | None) -> str:
    base = full_prompt + (f"|seed={seed}" if seed is not None else "")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _gemini_call(prompt: str, model: str) -> bytes:
    """Single Gemini image API call. Raises on failure. Returns image bytes."""
    if model.startswith("imagen"):
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
            f":predict?key={GEMINI_API_KEY}"
        )
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
        }
    else:
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
    if "predictions" in data:
        preds = data.get("predictions") or []
        if not preds:
            raise RuntimeError(f"empty predictions: {json.dumps(data)[:200]}")
        first = preds[0]
        b64 = first.get("bytesBase64Encoded") or (first.get("image") or {}).get("bytesBase64Encoded")
        if not b64:
            raise RuntimeError(f"no bytes in predictions: {json.dumps(data)[:200]}")
        return base64.b64decode(b64)
    cands = data.get("candidates") or []
    if not cands:
        raise RuntimeError(f"no candidates: {json.dumps(data)[:200]}")
    parts = cands[0].get("content", {}).get("parts", [])
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError(f"no inline_data: {json.dumps(data)[:200]}")


def _try_gemini(full: str, seed, out: Path) -> bool:
    """Try Gemini Image (Nano Banana) / Imagen cascade. Free tier first."""
    global _gemini_working_model
    if not GEMINI_API_KEY:
        print("[gemini] GEMINI_API_KEY/GOOGLE_API_KEY not set, skipping")
        return False
    candidates = list(GEMINI_IMG_MODELS)
    if _gemini_working_model and _gemini_working_model in candidates:
        # try the previously-working one first
        candidates.remove(_gemini_working_model)
        candidates.insert(0, _gemini_working_model)
    for model in candidates:
        try:
            img_bytes = _gemini_call(full, model)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            # aspect-fit with black bar padding (no stretch)
            sw, sh = img.size
            ta = WIDTH / HEIGHT
            sa = sw / sh
            if abs(sa - ta) < 0.01:
                img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
            elif sa > ta:
                nw = WIDTH; nh = int(WIDTH / sa)
                res = img.resize((nw, nh), Image.LANCZOS)
                canvas = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
                canvas.paste(res, (0, (HEIGHT - nh) // 2))
                img = canvas
            else:
                nh = HEIGHT; nw = int(HEIGHT * sa)
                res = img.resize((nw, nh), Image.LANCZOS)
                canvas = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
                canvas.paste(res, ((WIDTH - nw) // 2, 0))
                img = canvas
            img.save(out, "JPEG", quality=88)
            _gemini_working_model = model
            print(f"[gemini] OK model={model}: {out.name}")
            return True
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            body_txt = (e.response.text[:200] if e.response is not None else "")
            print(f"[gemini] {model} HTTP {code}: {body_txt}")
        except Exception as e:
            print(f"[gemini] {model} exc: {e}")
    return False


def _try_pollinations(full: str, seed, out: Path) -> bool:
    url = f"{POLLINATIONS_BASE}{quote(full)}"
    params = {
        "width": WIDTH, "height": HEIGHT, "model": MODEL,
        "nologo": "true", "negative": NEGATIVE,
    }
    if seed is not None:
        params["seed"] = seed
    last = None
    for attempt in range(POLLINATIONS_MAX_ATTEMPTS):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            if len(r.content) < 1000:
                raise RuntimeError(f"response too small ({len(r.content)} bytes)")
            out.write_bytes(r.content)
            return True
        except Exception as e:
            last = e
            print(f"[pollinations] attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    print(f"[pollinations] giving up after {POLLINATIONS_MAX_ATTEMPTS}: {last}")
    return False


def _try_huggingface(full: str, seed, out: Path) -> bool:
    headers = {"Accept": "image/png"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
    body = {"inputs": full}
    if seed is not None:
        body["parameters"] = {"seed": int(seed)}
    try:
        r = requests.post(HF_API_URL, headers=headers, json=body, timeout=30)
        if r.status_code == 503:
            # model loading -> wait then retry once
            print(f"[huggingface] 503 model loading, waiting 15s")
            time.sleep(15)
            r = requests.post(HF_API_URL, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "image" not in ct and len(r.content) < 1000:
            raise RuntimeError(f"non-image response ({ct}, {len(r.content)} bytes)")
        # Convert PNG to JPG to keep filename ext consistent
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img = img.resize((WIDTH, HEIGHT))
        img.save(out, "JPEG", quality=88)
        return True
    except Exception as e:
        print(f"[huggingface] failed: {e}")
        return False


def _try_together(full: str, seed, out: Path) -> bool:
    if not TOGETHER_API_KEY:
        return False
    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "black-forest-labs/FLUX.1-schnell-Free",
        "prompt": full,
        "width": WIDTH,
        "height": HEIGHT,
        "steps": 4,
        "n": 1,
        "response_format": "b64_json",
    }
    if seed is not None:
        body["seed"] = int(seed)
    try:
        r = requests.post(TOGETHER_API_URL, headers=headers, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        import base64
        b64 = data["data"][0]["b64_json"]
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        img = img.resize((WIDTH, HEIGHT))
        img.save(out, "JPEG", quality=88)
        return True
    except Exception as e:
        print(f"[together] failed: {e}")
        return False


def _try_pillow_fallback(scene_prompt: str, out: Path) -> bool:
    """Last-resort: abstract gradient + bokeh dots. NO TEXT (was rendering AI prompt as visible text on YouTube thumbs).
    2026-05-19: user 怒「サムネが AI プロンプトのテキストそのまま」→ テキスト描画を完全除去・抽象 gradient のみ。
    """
    try:
        import random
        random.seed(hash(scene_prompt) & 0xFFFFFFFF)
        img = Image.new("RGB", (WIDTH, HEIGHT), (12, 12, 16))
        draw = ImageDraw.Draw(img)
        # vertical gradient bottom-half: 暗い青〜紫
        for y in range(HEIGHT):
            r = int(12 + (y / HEIGHT) * 18)
            g = int(12 + (y / HEIGHT) * 14)
            b = int(16 + (y / HEIGHT) * 38)
            draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
        # bokeh dots (random soft circles)
        for _ in range(28):
            cx = random.randint(0, WIDTH)
            cy = random.randint(0, HEIGHT)
            radius = random.randint(15, 80)
            alpha = random.randint(20, 90)
            color_choices = [(220, 200, 180), (200, 220, 240), (220, 180, 200), (180, 200, 220)]
            color = random.choice(color_choices)
            overlay = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.ellipse([0, 0, radius * 2, radius * 2], fill=(color[0], color[1], color[2], alpha))
            img.paste(overlay, (cx - radius, cy - radius), overlay)
        img.save(out, "JPEG", quality=88)
        print(f"[pillow-fallback] wrote abstract placeholder (NO TEXT): {out.name}")
        return True
    except Exception as e:
        print(f"[pillow-fallback] failed unexpectedly: {e}")
        return False


def generate_image(scene_prompt: str, cache_dir: Path,
                   seed: int | None = None) -> Path:
    _validate(scene_prompt)
    full = PROMPT_TEMPLATE.format(scene=scene_prompt)
    key = _cache_key(full, seed)
    out = cache_dir / f"{key}.jpg"
    if out.exists() and out.stat().st_size > 1000:
        return out

    # Cascade: Gemini (Nano Banana, free tier) -> pollinations -> HF -> Together -> Pillow placeholder
    # 2026-05-20 fix: Gemini を primary に昇格 (workflow に GEMINI_API_KEY が通っているのに従来未使用だった)
    backends = [
        ("gemini",       lambda: _try_gemini(full, seed, out)),
        ("pollinations", lambda: _try_pollinations(full, seed, out)),
        ("huggingface",  lambda: _try_huggingface(full, seed, out)),
        ("together",     lambda: _try_together(full, seed, out)),
        ("pillow",       lambda: _try_pillow_fallback(scene_prompt, out)),
    ]
    for name, fn in backends:
        ok = fn()
        if ok and out.exists() and out.stat().st_size > 1000:
            print(f"[image] OK via {name}: {out.name}")
            time.sleep(PER_CALL_DELAY_SEC)
            return out
    # Should be unreachable because Pillow always succeeds
    raise RuntimeError(f"All backends failed (incl. Pillow placeholder): {scene_prompt[:80]}")


def generate_all_images(script: dict, cache_dir: Path,
                        target_per_chapter: int = 5) -> list[list[Path]]:
    """
    Returns: chapters x images (Path)
    10 分動画想定: 10章 x 5枚 = 50枚 (画像切替 ~12秒/枚)
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    result: list[list[Path]] = []
    for ci, ch in enumerate(script["chapters"]):
        prompts = ch["image_prompts"]
        chapter_imgs: list[Path] = []
        for i in range(target_per_chapter):
            scene = prompts[i % len(prompts)]
            img = generate_image(scene, cache_dir, seed=ci * 100 + i)
            chapter_imgs.append(img)
        result.append(chapter_imgs)
        print(f"  ch{ci+1:02d}: {len(chapter_imgs)} images ok")
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script

    script = read_script(sys.argv[1] if len(sys.argv) > 1 else "inputs/script_001.json")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    imgs = generate_all_images(script, Path("cache/images"), target_per_chapter=n)
    print(f"total: {sum(len(c) for c in imgs)} images")
