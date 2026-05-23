#!/usr/bin/env python3
"""gen_stage_images.py

GitHub Actions 上で psych_v2 用の staging 画像を Gemini Imagen で生成する。
p001 はストック流用 (workflow 側で cp 済み) のため対象外、
ここでは p002〜p006 の 5 本 x 10 枚 = 50 枚を生成する。

2026-05-23 改訂 (rate-limit対策):
  - Gemini free tier daily quota が日中に切れるので、429 を検出したら
    その時点で全モデルを quota-out 扱いにして残りの画像を skip → 即終了。
    既に保存済みの画像は次回 schedule run で skip して残りを継続生成。
  - 404 / 400 で失敗するモデルは次回以降も試行しない (memoize)。
  - 一枚あたりの試行は 1 モデル 1 回、429 以外の失敗時のみ他モデルに fallback。

仕様 (うっちー mandate):
  - 純愛 / 対人関係心理学路線 (下ネタ / 性的表現 NG)
  - 30 代日本人女性 / アニメ風セルシェーディング
  - 夜景バー・ラウンジ等の上品な雰囲気
  - Pollinations / Stability 系は使用禁止 (Gemini Imagen のみ)
  - aspect 維持 / 伸ばし禁止 (足りない部分は黒帯 padding 可)
  - 出力: youtube/psych_v2/images/{002..006}/img_NN.jpg (1920x1080)
"""
import os
import sys
import json
import time
import base64
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGES_ROOT = ROOT / "images"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
TARGET_W = 1920
TARGET_H = 1080
IMAGES_PER_TOPIC = 10
PER_REQUEST_SLEEP_SEC = float(os.environ.get("STAGE_SLEEP_SEC", "7"))

CANDIDATE_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp-image-generation",
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-generate-001",
    "imagen-3.0-generate-001",
    "imagen-3.0-fast-generate-001",
]
_dead_models = set()  # 404/400 で恒久失敗したモデル
_quota_exhausted = False  # 429 を 1 回でも見たら True

STYLE_SUFFIX = (
    "Style: anime cel-shading illustration, soft pastel colors, "
    "clean lineart, modern Japanese aesthetic, cinematic 16:9 framing, "
    "warm amber bokeh, atmospheric lighting. "
    "Subject: a calm Japanese woman in her early 30s (or distant silhouette / "
    "back view / hands only), refined evening attire, elegant posture. "
    "Setting: upscale night bar lounge, quiet cafe, hotel lobby window, "
    "softly lit living room, or contemplative city night background. "
    "Mood: pure-love and interpersonal-psychology theme, tender, "
    "respectful, contemplative, no eroticism. "
    "Strict: tasteful and SFW, no sexual content, no nudity, no cleavage, "
    "no suggestive pose, no minors, no text overlay, no watermark, "
    "no logos, no exaggerated anatomy, undistorted faces."
)

SCENES = {
    "002": {
        "title": "Long-lasting partnership habits",
        "scenes": [
            "Two adults walking side by side on a quiet evening boulevard, distant view",
            "A couple's hands almost touching across a small cafe table at dawn",
            "Empty bedside table with two warm tea cups and a folded letter, soft lamp",
            "A woman gazing out a rain-streaked window at city lights, back view",
            "Two armchairs facing each other by a fireplace, no people, warm lighting",
            "Steaming kettle and two cups in a quiet morning kitchen, soft sunlight",
            "Hand of a Japanese woman writing a small note of gratitude at a desk",
            "Empty park bench in early morning fog, two coffee cups left side by side",
            "A garden path at dusk with paper lanterns, contemplative atmosphere",
            "Home entrance with two pairs of shoes neatly aligned, soft amber light",
        ],
    },
    "003": {
        "title": "Drawing out true feelings through listening",
        "scenes": [
            "A Japanese woman in her 30s listening attentively in a softly lit lounge",
            "Close-up of two empty armchairs facing each other in a quiet study",
            "Two cups of warm tea on a low wooden table, steam rising, soft lamp",
            "A woman by a rain-streaked window, head slightly tilted, back view",
            "Close-up of gentle eyes reflecting candlelight, calm expression",
            "Quiet reading nook with a single floor lamp and bookshelf, no people",
            "Warm amber bokeh in a hotel lounge corner, two seats angled toward each other",
            "A round cafe table with an open notebook and a single coffee, evening light",
            "Dawn light entering a quiet living room through linen curtains",
            "A garden path with stepping stones and lanterns at twilight",
        ],
    },
    "004": {
        "title": "Psychological safety in close relationships",
        "scenes": [
            "A Japanese woman smiling gently while greeting someone at a bar entrance",
            "Empty meeting room with circle of chairs at dusk, warm window light",
            "Silhouettes of teammates leaning in over a small round table",
            "An open journal and pen on a clean desk under a soft reading lamp",
            "Hand raised politely to ask a question in a softly lit lounge, side view",
            "Two cups of tea and a small dessert plate on a quiet bar counter",
            "Morning sunlight through linen curtains over a tidy living room",
            "Warm yellow window glow of a small home seen from a quiet street",
            "Dawn over a calm river with a small wooden bridge, contemplative mood",
            "Garden lantern path winding toward a softly lit door, evening",
        ],
    },
    "005": {
        "title": "Long-lasting love and preventing breakups",
        "scenes": [
            "A Japanese woman waiting at a wooden front door with a soft welcoming smile",
            "Closed apartment door with a small note pinned, soft hallway light",
            "Dawn light spreading across a quiet bedroom, single curtain swaying",
            "A peaceful river under early morning mist, lone wooden bridge",
            "Bedside table lamp glowing softly beside two books and a folded letter",
            "Quiet kitchen at night with a single cup of tea cooling on the counter",
            "A woman looking out a tall window at city night lights, back view",
            "Warm cozy living room with knit blanket on a sofa, no people, lamp on",
            "Two adults walking side by side along an evening canal, distant view",
            "Empty dining table set for two with a small handwritten thank-you card",
        ],
    },
    "006": {
        "title": "Unspoken love and quiet affection",
        "scenes": [
            "A Japanese woman in her 30s standing at a doorway smiling softly, half-turned",
            "Tall window with sheer curtains glowing in late-afternoon light, no people",
            "Two ceramic tea cups on a low wooden tray with steam rising gently",
            "Close-up of two hands almost touching on a wooden cafe table",
            "Two adults walking together at dusk along a tree-lined street, distant",
            "A quiet reading chair under a warm floor lamp with an open book",
            "Dawn breaking over a calm city skyline through a quiet bedroom window",
            "Dusk sky over a wooden terrace with a single lit paper lantern",
            "A small empty study with a fountain pen, notebook, and folded note",
            "Soft warm glow of a small home window seen from a quiet rainy street",
        ],
    },
}


def fail(msg, code=1):
    print(f"[stage][FATAL] {msg}", file=sys.stderr)
    sys.exit(code)


def call_image_gen(prompt, model):
    if model.startswith("imagen"):
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:predict?key={GEMINI_API_KEY}"
        )
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
        }
    else:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_API_KEY}"
        )
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "predictions" in data:
        preds = data.get("predictions", [])
        if not preds:
            raise RuntimeError("no predictions returned")
        b64 = preds[0].get("bytesBase64Encoded") or (
            preds[0].get("image") or {}
        ).get("bytesBase64Encoded")
        if not b64:
            raise RuntimeError("no bytes in predictions")
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


def fit_aspect(out_path):
    from PIL import Image
    with Image.open(out_path) as im:
        im = im.convert("RGB")
        sw, sh = im.size
        if (sw, sh) == (TARGET_W, TARGET_H):
            return
        ta = TARGET_W / TARGET_H
        sa = sw / sh
        if abs(sa - ta) < 0.005:
            out = im.resize((TARGET_W, TARGET_H), Image.LANCZOS)
        elif sa > ta:
            new_w = TARGET_W
            new_h = int(TARGET_W / sa)
            res = im.resize((new_w, new_h), Image.LANCZOS)
            out = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))
            out.paste(res, (0, (TARGET_H - new_h) // 2))
        else:
            new_h = TARGET_H
            new_w = int(TARGET_H * sa)
            res = im.resize((new_w, new_h), Image.LANCZOS)
            out = Image.new("RGB", (TARGET_W, TARGET_H), (0, 0, 0))
            out.paste(res, ((TARGET_W - new_w) // 2, 0))
        out.save(out_path, format="JPEG", quality=90)
        print(f"  aspect-fit {out_path.name}: {sw}x{sh} -> {TARGET_W}x{TARGET_H}")


def generate_one(prompt, out_path):
    """Try each non-dead model once. Returns True on success, False otherwise.
    On HTTP 429 sets global _quota_exhausted = True so caller can stop early.
    """
    global _quota_exhausted
    for m in CANDIDATE_MODELS:
        if m in _dead_models:
            continue
        try:
            img_bytes = call_image_gen(prompt, m)
            if not img_bytes or len(img_bytes) < 4000:
                raise RuntimeError(f"image too small ({len(img_bytes) if img_bytes else 0} bytes)")
            out_path.write_bytes(img_bytes)
            print(f"  OK model={m} bytes={len(img_bytes)}")
            fit_aspect(out_path)
            return True
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")[:180]
            print(f"  {m} HTTP {e.code}: {msg}")
            if e.code == 429:
                _quota_exhausted = True
                return False
            if e.code in (400, 404):
                _dead_models.add(m)
        except Exception as e:
            print(f"  {m} exc {e!r}")
            _dead_models.add(m)
    return False


def make_prompt(topic_title, scene_desc, idx):
    return (
        f"Topic: {topic_title}. "
        f"Scene {idx + 1}: {scene_desc}. "
        f"{STYLE_SUFFIX} "
        f"Variation {idx + 1}, slight composition shift, fresh framing."
    )


def main():
    if not GEMINI_API_KEY:
        fail("GEMINI_API_KEY not set (expected from GitHub Secrets)")
    print(f"[stage] starting. target={TARGET_W}x{TARGET_H} per-topic={IMAGES_PER_TOPIC} sleep={PER_REQUEST_SLEEP_SEC}s")
    total_ok = 0
    total_skip = 0
    total_fail = 0
    for topic_id, spec in SCENES.items():
        out_dir = IMAGES_ROOT / topic_id
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== topic {topic_id}: {spec['title']} ===")
        for i, scene in enumerate(spec["scenes"][:IMAGES_PER_TOPIC]):
            out_path = out_dir / f"img_{i:02d}.jpg"
            if out_path.exists() and out_path.stat().st_size > 4000:
                print(f"  skip (already exists): {out_path.name}")
                total_skip += 1
                continue
            if _quota_exhausted:
                print(f"  skip (quota exhausted): {out_path.name}")
                total_fail += 1
                continue
            prompt = make_prompt(spec["title"], scene, i)
            ok = generate_one(prompt, out_path)
            if ok:
                total_ok += 1
            else:
                total_fail += 1
                print(f"  failed: {out_path.name} (will retry in next scheduled run)")
            time.sleep(PER_REQUEST_SLEEP_SEC)
    print(f"\n[stage] done. new={total_ok} preexisting={total_skip} pending={total_fail}")
    print(f"[stage] dead_models={sorted(_dead_models)} quota_exhausted={_quota_exhausted}")
    for topic_id in SCENES.keys():
        d = IMAGES_ROOT / topic_id
        c = sum(
            1
            for p in d.glob("*")
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        )
        print(f"  {topic_id}: {c}/{IMAGES_PER_TOPIC} images")


if __name__ == "__main__":
    main()
