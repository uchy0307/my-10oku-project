"""step3_images_imagen.py
Google Gemini ネイティブ画像生成で章ごとの本編画像を生成。
- Pollinations / Stability 系は使用禁止（うっちー仕様）。
- Imagen predict 系は v1beta 公開なし / 権限なしで 404 が出るため
  Gemini API (generateContent + responseModalities=IMAGE) に切替。
- モデル: gemini-2.5-flash-image-preview (env GEMINI_IMG_MODEL で上書き可)
"""
import os, sys, json, time, base64
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
GEMINI_IMG_MODEL = os.environ.get("GEMINI_IMG_MODEL", "gemini-2.5-flash-image-preview")
IMG_PER_CHAPTER = int(os.environ.get("IMG_PER_CHAPTER", "2"))

BASE_STYLE = (
    "cinematic mood, dim ambient lighting, modern japanese urban night, "
    "soft bokeh, melancholic atmosphere, photorealistic 35mm, shallow depth of field, "
    "no text, no watermark, no logo, Aspect 16:9, wide horizontal composition."
)


def make_prompt(chapter_title, chapter_brief, video_title):
    return (
        f"Generate a wide 16:9 cinematic image for: "
        f"{video_title}. {chapter_title}. {chapter_brief[:140]}. "
        f"Adult psychology theme, suggestive but tasteful, no nudity, no minors. "
        f"{BASE_STYLE}"
    )


def call_gemini_image(prompt, attempt=1):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) env not set")
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_IMG_MODEL}:generateContent?key={GEMINI_API_KEY}")
    body = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}],
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="ignore")
        print(f"[step3_imagen] HTTPError {e.code}: {msg[:400]}")
        if attempt < 4 and e.code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            return call_gemini_image(prompt, attempt + 1)
        raise
    cands = data.get("candidates", [])
    if not cands:
        print(f"[step3_imagen] no candidates: {json.dumps(data)[:400]}")
        raise RuntimeError("no candidates returned")
    parts = cands[0].get("content", {}).get("parts", [])
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            if mime.startswith("image/"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("no image inline_data in response")


call_imagen = call_gemini_image

def main():
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    images = []
    for c in cur["chapters"]:
        base_prompt = make_prompt(c["title"], c.get("brief", ""), cur["title"])
        for k in range(IMG_PER_CHAPTER):
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
        json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8")
    if not images:
        print("[step3_imagen] FATAL: no images generated")
        sys.exit(1)


if __name__ == "__main__":
    main()
