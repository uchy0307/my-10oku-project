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


def generate_image(scene_prompt: str, cache_dir: Path,
                   seed: int | None = None) -> Path:
    _validate(scene_prompt)
    full = PROMPT_TEMPLATE.format(scene=scene_prompt)
    key = _cache_key(full, seed)
    out = cache_dir / f"{key}.jpg"
    if out.exists() and out.stat().st_size > 1000:
        return out

    url = f"{POLLINATIONS_BASE}{quote(full)}"
    params = {
        "width": WIDTH, "height": HEIGHT, "model": MODEL,
        "nologo": "true", "negative": NEGATIVE,
    }
    if seed is not None:
        params["seed"] = seed

    # retry (samurai fetch_portrait.mjs と同等)
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=180)
            r.raise_for_status()
            if len(r.content) < 1000:
                raise RuntimeError(f"response too small ({len(r.content)} bytes)")
            out.write_bytes(r.content)
            return out
        except Exception as e:
            last = e
            print(f"[WARN] image attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to generate image: {scene_prompt[:80]} ({last})")


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
