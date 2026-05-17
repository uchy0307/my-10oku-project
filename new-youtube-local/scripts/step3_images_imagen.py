"""step3_images_imagen.py
Google Gemini Imagen API で章ごとの本編画像を生成。
- Pollinations / Stability 系は使用禁止（うっちー仕様）。
- Endpoint: generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict
- 1280x720 (16:9) - YouTube 動画用
- I/O は既存 step3_images.py と互換: output/<id>_img_NN_NN.jpg + <id>_images.json
"""
import os, sys, json, time, base64, hashlib
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
IMAGEN_MODEL = os.environ.get("IMAGEN_MODEL", "imagen-3.0-generate-002")
IMAGEN_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN_MODEL}:predict"

IMG_PER_CHAPTER = int(os.environ.get("IMG_PER_CHAPTER", "2"))
ASPECT_RATIO = os.environ.get("IMAGEN_ASPECT_RATIO", "16:9")
PERSON_GENERATION = os.environ.get("IMAGEN_PERSON_GENERATION", "allow_adult")  # allow_adult / dont_allow

BASE_STYLE = (
    "cinematic mood, dim ambient lighting, modern japanese urban night, "
    "soft bokeh, melancholic atmosphere, photorealistic 35mm, shallow depth of field, "
    "no text, no watermark, no logo, no caption, no UI elements"
)


def make_prompt(chapter_title: str, chapter_brief: str, video_title: str) -> str:
    return (
        f"{video_title}. {chapter_title}. {chapter_brief[:140]}. "
        f"adult psychology theme, suggestive but tasteful, no nudity, no minors. "
        f"{BASE_STYLE}"
    )


def call_imagen(prompt: str, attempt: int = 1) -> bytes:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) env not set")
    url = f"{IMAGEN_ENDPOINT}?key={GEMINI_API_KEY}"
    body = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": ASPECT_RATIO,
            "personGeneration": PERSON_GENERATION,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="ignore")
        print(f"[step3_imagen] HTTPError {e.code}: {msg[:400]}")
        if attempt < 4 and e.code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            return call_imagen(prompt, attempt + 1)
        raise

    preds = data.get("predictions", [])
    if not preds:
        # 安全性によって blocked される場合がある
        print(f"[step3_imagen] no predictions: {json.dumps(data)[:400]}")
        raise RuntimeError("no predictions returned")
    b64 = preds[0].get("bytesBase64Encoded") or preds[0].get("image", {}).get("bytesBase64Encoded")
    if not b64:
        print(f"[step3_imagen] no bytesBase64Encoded: {json.dumps(preds[0])[:300]}")
        raise RuntimeError("no image bytes")
    return base64.b64decode(b64)


def main():
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    images = []
    for c in cur["chapters"]:
        base_prompt = make_prompt(c["title"], c.get("brief", ""), cur["title"])
        for k in range(IMG_PER_CHAPTER):
            # シード安定のためプロンプト末尾に variation tag を付与
            varied = f"{base_prompt} . variation {k+1} of {IMG_PER_CHAPTER}"
            out = OUTPUT_DIR / f"{cur['id']}_img_{c['index']:02d}_{k:02d}.jpg"
            for attempt in range(3):
                try:
                    img_bytes = call_imagen(varied)
                    out.write_bytes(img_bytes)
                    break
                except Exception as e:
                    print(f"[step3_imagen] retry ch{c['index']} k{k}: {e}")
                    time.sleep(2 ** attempt)
            else:
                print(f"[step3_imagen] FAIL ch{c['index']} k{k}")
                continue
            images.append({"chapter": c["index"], "path": str(out), "prompt": varied})
            print(f"[step3_imagen] wrote {out.name}")

    (OUTPUT_DIR / f"{cur['id']}_images.json").write_text(
        json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not images:
        print("[step3_imagen] FATAL: no images generated")
        sys.exit(1)


if __name__ == "__main__":
    main()
