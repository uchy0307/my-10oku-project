"""step3_images_imagen.py
Robust image generation with model fallback chain + solid-color last resort.
"""
import os, sys, json, time, base64
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
IMG_PER_CHAPTER = int(os.environ.get("IMG_PER_CHAPTER", "2"))

CANDIDATE_MODELS = [
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp-image-generation",
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-generate-001",
    "imagen-3.0-generate-001",
    "imagen-3.0-fast-generate-001",
]

_working_model = None
_listed = False


def list_models():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [m.get("name", "").replace("models/", "") for m in data.get("models", [])]


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


def gen_fallback_image(prompt, out_path):
    """Solid-color image with text bake (no AI). Last resort."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1280, 720), (28, 30, 52))
    d = ImageDraw.Draw(img)
    # subtle gradient bottom-darker
    for y in range(360, 720):
        a = int(80 * (y - 360) / 360)
        d.line([(0, y), (1280, y)], fill=(28 - a // 4, 30 - a // 4, 52 - a // 4))
    img.save(out_path, format="JPEG", quality=85)


def generate(prompt, out_path):
    global _working_model, _listed
    if not _listed:
        try:
            models = list_models()
            img_capable = [m for m in models if "image" in m.lower() or "imagen" in m.lower()]
            print(f"[step3] available image-capable models: {img_capable[:20]}")
        except Exception as e:
            print(f"[step3] list_models failed: {e}")
        _listed = True
    if _working_model:
        try:
            img_bytes = call_image_gen(prompt, _working_model)
            out_path.write_bytes(img_bytes)
            return True
        except Exception as e:
            print(f"[step3] cached {_working_model} failed: {e}")
            _working_model = None
    for m in CANDIDATE_MODELS:
        try:
            img_bytes = call_image_gen(prompt, m)
            out_path.write_bytes(img_bytes)
            _working_model = m
            print(f"[step3] OK using model={m}")
            return True
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")[:200]
            print(f"[step3] {m} HTTP {e.code}: {msg}")
        except Exception as e:
            print(f"[step3] {m} exc: {e}")
    print(f"[step3] WARN: all image models failed, using solid-color fallback")
    gen_fallback_image(prompt, out_path)
    return False


def make_prompt(ct, cb, vt):
    return (
        f"Generate a wide 16:9 cinematic image for: {vt}. {ct}. {cb[:140]}. "
        f"Adult psychology theme, suggestive but tasteful, no nudity, no minors. "
        f"Cinematic dim ambient lighting, modern japanese urban night, soft bokeh."
    )


def main():
    if not GEMINI_API_KEY:
        print("[step3] FATAL: GEMINI_API_KEY not set")
        sys.exit(1)
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    images = []
    for c in cur["chapters"]:
        bp = make_prompt(c["title"], c.get("brief", ""), cur["title"])
        for k in range(IMG_PER_CHAPTER):
            varied = f"{bp} . variation {k+1}"
            out = OUTPUT_DIR / f"{cur['id']}_img_{c['index']:02d}_{k:02d}.jpg"
            ok = generate(varied, out)
            images.append({"chapter": c["index"], "path": str(out), "prompt": varied, "ai_ok": ok})
            print(f"[step3] wrote {out.name} (ai={ok})")
    (OUTPUT_DIR / f"{cur['id']}_images.json").write_text(
        json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8")
    if not images:
        sys.exit(1)


if __name__ == "__main__":
    main()
