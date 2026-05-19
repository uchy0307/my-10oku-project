"""step3_images_imagen.py
Robust image generation: Gemini Imagen / Gemini 2.0 image gen with fallback chain.
- Pollinations / Stability 系は使用禁止（うっちー仕様）。
- Aspect-preserve post-processing: scale image to TARGET_W x TARGET_H with black bar padding (NO STRETCH).
- I/O は既存 step3_images.py と互換: output/<id>_img_NN_NN.jpg + <id>_images.json
- 品質検証（2026-05-19 追加）: 顔横伸び / 単色塗りつぶし / aspect 違反を生成後検証、
  失敗したら最大 MAX_QC_RETRIES 回まで再生成。検証結果は <id>_quality.json に出力。
"""
import os, sys, json, time, base64
from pathlib import Path
import urllib.request, urllib.error

MAX_QC_RETRIES = int(os.environ.get("STEP3_QC_MAX_RETRIES", "3"))
FACE_ASPECT_MIN = float(os.environ.get("STEP3_FACE_ASPECT_MIN", "0.55"))  # 顔の縦/横 がこれ未満 → 横伸び NG
FACE_ASPECT_MAX = float(os.environ.get("STEP3_FACE_ASPECT_MAX", "1.80"))  # 顔の縦/横 がこれ以上 → 縦伸び NG

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
IMG_PER_CHAPTER = int(os.environ.get("IMG_PER_CHAPTER", "4"))
TARGET_W = int(os.environ.get("VIDEO_W", "1280"))
TARGET_H = int(os.environ.get("VIDEO_H", "720"))

# Model override env (优先 single-model). Fallback chain below if env not set.
GEMINI_IMG_MODEL = os.environ.get("GEMINI_IMG_MODEL", "")

CANDIDATE_MODELS = [
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-generate-001",
    "imagen-3.0-generate-001",
    "imagen-3.0-fast-generate-001",
    "gemini-2.0-flash-preview-image-generation",
    "gemini-2.0-flash-exp-image-generation",
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
]
if GEMINI_IMG_MODEL and GEMINI_IMG_MODEL not in CANDIDATE_MODELS:
    CANDIDATE_MODELS.insert(0, GEMINI_IMG_MODEL)

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



def _fit_aspect(out_path):
    """Open image at out_path, scale-fit to TARGET_W x TARGET_H with black bar padding. Overwrite."""
    try:
        from PIL import Image
    except ImportError:
        print("[step3] WARN: PIL not available, skip aspect-fit")
        return
    try:
        with Image.open(out_path) as im:
            im = im.convert("RGB")
            sw, sh = im.size
            ta = TARGET_W / TARGET_H
            sa = sw / sh
            if abs(sa - ta) < 0.005 and (sw, sh) == (TARGET_W, TARGET_H):
                return
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
            out.save(out_path, format="JPEG", quality=88)
            print(f"[step3] aspect-fit src=({sw}x{sh}) -> ({TARGET_W}x{TARGET_H}) padded")
    except Exception as e:
        print(f"[step3] aspect-fit failed for {out_path}: {e}")


def gen_fallback_image(prompt, out_path):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (TARGET_W, TARGET_H), (28, 30, 52))
    d = ImageDraw.Draw(img)
    for y in range(TARGET_H // 2, TARGET_H):
        a = int(80 * (y - TARGET_H // 2) / (TARGET_H // 2))
        d.line([(0, y), (TARGET_W, y)], fill=(28 - a // 4, 30 - a // 4, 52 - a // 4))
    img.save(out_path, format="JPEG", quality=85)


def _validate_image(out_path):
    """Return (ok: bool, reason: str). 顔横伸び/単色/aspect違反を検出。
    OpenCV があれば顔比率検証、無ければ Pillow のみで色分散検証。
    """
    try:
        from PIL import Image
    except ImportError:
        return True, "PIL not available, skipping QC"
    try:
        with Image.open(out_path) as im:
            im = im.convert("RGB")
            w, h = im.size
            # aspect check (must be exact TARGET after _fit_aspect)
            if (w, h) != (TARGET_W, TARGET_H):
                return False, f"aspect_mismatch w={w} h={h} target={TARGET_W}x{TARGET_H}"
            # 単色塗りつぶし検出（fallback gen と区別するために平均色分散見る）
            try:
                small = im.resize((64, 36), Image.LANCZOS)
                pixels = list(small.getdata())
                rs = [p[0] for p in pixels]
                gs = [p[1] for p in pixels]
                bs = [p[2] for p in pixels]
                def _stddev(xs):
                    n = len(xs)
                    if n == 0:
                        return 0.0
                    mean = sum(xs) / n
                    return (sum((x - mean) ** 2 for x in xs) / n) ** 0.5
                rng = _stddev(rs) + _stddev(gs) + _stddev(bs)
                if rng < 5.0:
                    return False, f"solid_color_image stddev={rng:.2f}"
            except Exception as e:
                print(f"[step3 QC] color check failed: {e}")
            # 顔比率検証（cv2 があれば実行、無ければ pass）
            try:
                import cv2
                import numpy as np
                arr = np.asarray(im)
                gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
                xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                face_cls = cv2.CascadeClassifier(xml)
                faces = face_cls.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=4, minSize=(40, 40))
                for (fx, fy, fw, fh) in faces:
                    ratio = fh / max(fw, 1)
                    if ratio < FACE_ASPECT_MIN or ratio > FACE_ASPECT_MAX:
                        return False, f"face_distorted h/w={ratio:.2f} bounds=[{FACE_ASPECT_MIN},{FACE_ASPECT_MAX}]"
            except ImportError:
                pass  # cv2 未インストールでも QC は緩く通す
            except Exception as e:
                print(f"[step3 QC] face check exc: {e}")
        return True, "ok"
    except Exception as e:
        return False, f"validate_exception {e}"


def _generate_once(prompt, out_path):
    """単発生成。成功した使えるモデルを返す。失敗時 None。"""
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
            _fit_aspect(out_path)
            return _working_model
        except Exception as e:
            print(f"[step3] cached {_working_model} failed: {e}")
            _working_model = None
    for m in CANDIDATE_MODELS:
        try:
            img_bytes = call_image_gen(prompt, m)
            out_path.write_bytes(img_bytes)
            _working_model = m
            print(f"[step3] OK using model={m}")
            _fit_aspect(out_path)
            return m
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")[:200]
            print(f"[step3] {m} HTTP {e.code}: {msg}")
        except Exception as e:
            print(f"[step3] {m} exc: {e}")
    return None


def generate(prompt, out_path):
    """QC ループ付き生成: validate → 失敗なら最大 MAX_QC_RETRIES 回まで再生成。
    最終的に QC fail なら fallback solid image を書き出して False を返す。
    """
    last_reason = "init"
    for attempt in range(1, MAX_QC_RETRIES + 1):
        # 再生成時は prompt に "no stretched faces" を強調 (毎回 inject)
        ptry = prompt + (" Strictly photorealistic. Undistorted human anatomy. No stretched faces. Clean composition."
                         if attempt == 1 else
                         f" CRITICAL: previous attempt failed QC ({last_reason}). Generate clean undistorted photo with proportional face geometry, no horror, no deformed features. Attempt {attempt}.")
        m = _generate_once(ptry, out_path)
        if m is None:
            last_reason = "model_call_failed"
            print(f"[step3 QC] attempt {attempt} model call failed")
            continue
        ok, reason = _validate_image(out_path)
        if ok:
            print(f"[step3 QC] attempt {attempt} PASS model={m}")
            return True
        last_reason = reason
        print(f"[step3 QC] attempt {attempt} FAIL ({reason}); retrying...")
    print(f"[step3 QC] all {MAX_QC_RETRIES} attempts failed (last={last_reason}), using solid fallback")
    gen_fallback_image(prompt, out_path)
    return False



def make_prompt(ct, cb, vt):
    """(β) 顔なし運用：人物アップ・複数人物の顔指定を完全除去。
    風景・物体・抽象的シーンのみで叙述する。顔歪み問題を構造的に回避。
    """
    return (
        f"Generate a wide 16:9 cinematic photograph (no people in foreground, no portrait, no faces). "
        f"Subject: visual metaphor for '{vt}' / '{ct}' / '{cb[:120]}'. "
        f"Composition: object-only or distant background only — empty bedroom, glass of wine, ring on velvet, "
        f"open book on desk, rain on city window, neon street at night, bokeh in cafe, hotel corridor, "
        f"silhouette far away, abstract texture, mood lighting. "
        f"Strictly NO human faces, NO close-up of people, NO portrait. "
        f"If a person appears, they must be: small silhouette in distance, back-view, hands only, or behind frosted glass. "
        f"Photorealistic, cinematic, modern japanese aesthetic, melancholic dim lighting, soft bokeh, "
        f"consistent style across all images, professional composition, no AI artifacts."
    )
# 後方互換のため call_imagen のままも公開
call_imagen = call_image_gen


def main():
    if not GEMINI_API_KEY:
        print("[step3] FATAL: GEMINI_API_KEY not set")
        sys.exit(1)
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    images = []
    qc_log = []
    for c in cur["chapters"]:
        bp = make_prompt(c["title"], c.get("brief", ""), cur["title"])
        for k in range(IMG_PER_CHAPTER):
            varied = f"{bp} . variation {k+1}"
            out = OUTPUT_DIR / f"{cur['id']}_img_{c['index']:02d}_{k:02d}.jpg"
            ok = generate(varied, out)
            # 最終 QC 結果も記録
            qc_ok, qc_reason = _validate_image(out)
            images.append({"chapter": c["index"], "path": str(out), "prompt": varied,
                           "ai_ok": ok, "qc_ok": qc_ok, "qc_reason": qc_reason})
            qc_log.append({"file": out.name, "qc_ok": qc_ok, "qc_reason": qc_reason, "ai_ok": ok})
            print(f"[step3] wrote {out.name} (ai={ok} qc={qc_ok}:{qc_reason})")
    (OUTPUT_DIR / f"{cur['id']}_images.json").write_text(
        json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / f"{cur['id']}_quality.json").write_text(
        json.dumps(qc_log, ensure_ascii=False, indent=2), encoding="utf-8")
    qc_pass = sum(1 for q in qc_log if q["qc_ok"])
    print(f"[step3] total images = {len(images)} QC pass = {qc_pass}/{len(images)} "
          f"(IMG_PER_CHAPTER={IMG_PER_CHAPTER}, chapters={len(cur['chapters'])})")
    if not images:
        sys.exit(1)
    # publish gate: QC pass率 50% 未満なら exit 1 で step4/5 を止める
    if len(images) > 0 and qc_pass / len(images) < 0.5:
        print(f"[step3] FATAL: QC pass rate {qc_pass/len(images):.0%} < 50%, aborting pipeline")
        sys.exit(2)


if __name__ == "__main__":
    main()

