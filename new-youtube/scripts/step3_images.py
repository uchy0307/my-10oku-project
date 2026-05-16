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
from pathlib import Path
from urllib.parse import quote
import requests
import os
import io
from PIL import Image, ImageDraw, ImageFont

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/"
MODEL = "flux"
WIDTH, HEIGHT = 1280, 720

PROMPT_TEMPLATE = (
    "anime style, cel-shading, adult anime, professional Japanese woman in her 30s, "
    "office attire, casual wear, calm composition, soft pastel background, "
    "warm lighting, high detail, 16:9 aspect, 1280x720, {scene}"
)

NEGATIVE = (
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
            r = requests.get(url, params=params, timeout=180)
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
        r = requests.post(HF_API_URL, headers=headers, json=body, timeout=180)
        if r.status_code == 503:
            # model loading -> wait then retry once
            print(f"[huggingface] 503 model loading, waiting 15s")
            time.sleep(15)
            r = requests.post(HF_API_URL, headers=headers, json=body, timeout=180)
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
        r = requests.post(TOGETHER_API_URL, headers=headers, json=body, timeout=180)
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
    """Last-resort: black background + scene text. Never fails."""
    try:
        img = Image.new("RGB", (WIDTH, HEIGHT), (12, 12, 16))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 36)
        except Exception:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
            except Exception:
                font = ImageFont.load_default()
        # word-wrap roughly 40 chars per line
        text = scene_prompt
        words = text.split(" ")
        line = ""
        lines_out: list[str] = []
        for w in words:
            tentative = (line + " " + w).strip()
            if len(tentative) > 40:
                lines_out.append(line)
                line = w
            else:
                line = tentative
        if line:
            lines_out.append(line)
        y = HEIGHT // 2 - (len(lines_out) * 50) // 2
        for ln in lines_out[:8]:
            try:
                bbox = draw.textbbox((0, 0), ln, font=font)
                tw = bbox[2] - bbox[0]
            except Exception:
                tw = len(ln) * 18
            x = (WIDTH - tw) // 2
            draw.text((x, y), ln, font=font, fill=(220, 220, 220))
            y += 50
        img.save(out, "JPEG", quality=88)
        print(f"[pillow-fallback] wrote placeholder: {out.name}")
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

    # Cascade: pollinations -> HF -> Together -> Pillow placeholder
    backends = [
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
