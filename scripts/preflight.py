#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight.py — 動画化前の必須条件を30秒で全チェック。
1つでも fail なら即終了。60分 ffmpeg 後の発覚を防ぐ。

Usage:
  python preflight.py --kind history --index 010
  python preflight.py --kind psych --index 005
"""
import argparse, os, sys, json, subprocess, shutil
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# .env load
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

ap = argparse.ArgumentParser()
ap.add_argument("--kind", required=True, choices=["history", "psych", "shorts", "otona_shorts"])
ap.add_argument("--index", required=True)
args = ap.parse_args()

errors = []
warns = []

def check(name, fn):
    try:
        msg = fn()
        if msg is True or msg is None:
            print(f"  ✓ {name}")
        elif isinstance(msg, str) and msg.startswith("WARN"):
            warns.append(f"{name}: {msg}")
            print(f"  ⚠ {name}: {msg}")
        else:
            errors.append(f"{name}: {msg}")
            print(f"  ✗ {name}: {msg}")
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"  ✗ {name}: {e}")

# 1. ffmpeg/ffprobe
def chk_ffmpeg():
    r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=30)
    if r.returncode != 0: return "ffmpeg not found"
    r = subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=30)
    if r.returncode != 0: return "ffprobe not found"
    return True

# 2. Python + Pillow + 日本語フォント（実際にダミー画像生成して検証）
def chk_thumb():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return "Pillow not installed"
    font_candidates = [
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ]
    fp = next((p for p in font_candidates if Path(p).exists()), None)
    if not fp: return "no Japanese font found"
    img = Image.new("RGB", (400, 200), (255, 200, 70))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(fp, 40, index=0)
    d.text((20, 80), "テスト", font=f, fill=(0, 0, 0))
    out = ROOT / "scripts" / "_preflight_thumb_test.jpg"
    img.save(out, "JPEG")
    sz = out.stat().st_size
    out.unlink()
    if sz < 3000: return f"thumb gen too small ({sz}B)"
    return True

# 3. 音声ファイル
def chk_audio():
    audio_dir = {
        "history":      ROOT / "youtube" / "history_v2" / "audio",
        "psych":        ROOT / "youtube" / "psych_v2" / "audio",
        "shorts":       ROOT / "youtube" / "shorts_v2" / "audio",
        "otona_shorts": ROOT / "youtube" / "otona_shorts_v2" / "audio",
    }[args.kind]
    f = audio_dir / f"{args.index}.mp3"
    if not f.exists(): return f"audio missing: {f}"
    if f.stat().st_size < 5000: return f"audio too small: {f.stat().st_size}B"
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(f)],
        capture_output=True, text=True, timeout=30
    )
    try:
        dur = float(r.stdout.strip())
    except ValueError:
        return "audio duration probe failed"
    target = 1500 if args.kind == "psych" else 1800
    if args.kind in ("shorts", "otona_shorts"): target = 15
    if dur < target:
        return f"audio {dur:.0f}s < required {target}s ({args.kind})"
    print(f"     (audio: {dur/60:.1f}min)")
    return True

# 4. 台本JSON
def chk_script():
    spec_path = {
        "history":      ROOT / "youtube" / "history_v2" / "scripts" / f"long_{args.index}.json",
        "psych":        ROOT / "youtube" / "psych_v2" / "scripts" / f"psych_{args.index}.json",
        "shorts":       ROOT / "youtube" / "shorts_v2" / "scripts" / f"short_{args.index}.json",
        "otona_shorts": ROOT / "youtube" / "otona_shorts_v2" / "scripts" / f"short_{args.index}.json",
    }[args.kind]
    if not spec_path.exists(): return f"script missing: {spec_path.name}"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not spec.get("title"): return "script title missing"
    chapters = spec.get("chapters", [])
    if len(chapters) < 1: return f"chapters empty"
    return True

# 5. 画像（URL or stock）
def chk_images():
    spec_path = {
        "history":      ROOT / "youtube" / "history_v2" / "scripts" / f"long_{args.index}.json",
        "psych":        ROOT / "youtube" / "psych_v2" / "scripts" / f"psych_{args.index}.json",
        "shorts":       ROOT / "youtube" / "shorts_v2" / "scripts" / f"short_{args.index}.json",
        "otona_shorts": ROOT / "youtube" / "otona_shorts_v2" / "scripts" / f"short_{args.index}.json",
    }[args.kind]
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    iu = spec.get("image_urls", [])
    if len(iu) >= 6:
        print(f"     (image_urls: {len(iu)} entries)")
        return True
    # stock fallback
    stock = ROOT / "youtube" / "stock_images" / "wiki"
    if not stock.exists():
        return f"image_urls={len(iu)} (<6) AND stock_images/wiki missing"
    import re
    if args.kind == "history":
        pat = re.compile(r"^wiki_(hist|sengoku|edo|meiji|bakumatsu|armor|kabuki)_.*\.(jpe?g|png)$", re.I)
    elif args.kind == "psych":
        pat = re.compile(r"^wiki_(cafe|library|bedroom|balcony|sunset|stars)_.*\.(jpe?g|png)$", re.I)
    else:
        pat = re.compile(r"^wiki_.*\.(jpe?g|png)$", re.I)
    matches = [f for f in stock.iterdir() if pat.match(f.name)]
    if len(matches) < 8:
        return f"image_urls={len(iu)} AND only {len(matches)} matching stock"
    print(f"     (image_urls={len(iu)}, stock fallback {len(matches)} available)")
    return True

# 6. YouTube credentials
def chk_yt():
    if not os.environ.get("YOUTUBE_CLIENT_ID") and not os.environ.get("NEW_YOUTUBE_CLIENT_ID"):
        return "YOUTUBE_CLIENT_ID missing"
    if not os.environ.get("YOUTUBE_CLIENT_SECRET"):
        return "YOUTUBE_CLIENT_SECRET missing"
    if not os.environ.get("YOUTUBE_REFRESH_TOKEN"):
        return "YOUTUBE_REFRESH_TOKEN missing"
    return True

# 7. ディスク容量
def chk_disk():
    total, used, free = shutil.disk_usage(str(ROOT))
    free_gb = free / 1024**3
    if free_gb < 1.0:
        return f"only {free_gb:.1f}GB free, need >=1GB"
    print(f"     (free disk: {free_gb:.1f}GB)")
    return True

# 8. node + googleapis
def chk_node():
    r = subprocess.run(["node", "--version"], capture_output=True, timeout=30)
    if r.returncode != 0: return "node not found"
    r = subprocess.run(["node", "-e", "import('googleapis').then(()=>console.log('ok')).catch(e=>{console.error(e.message);process.exit(1)})"],
                       capture_output=True, text=True, timeout=15, cwd=str(ROOT))
    if r.returncode != 0: return f"googleapis fail: {r.stderr[:100]}"
    return True

print(f"=== PREFLIGHT: {args.kind} #{args.index} ===")
check("1. ffmpeg/ffprobe", chk_ffmpeg)
check("2. Python+Pillow+JPフォント+ダミー生成", chk_thumb)
check("3. 音声ファイル(長さ含む)", chk_audio)
check("4. 台本JSON", chk_script)
check("5. 画像 image_urls or stock fallback", chk_images)
check("6. YouTube認証情報", chk_yt)
check("7. ディスク容量", chk_disk)
check("8. node + googleapis", chk_node)

print()
if errors:
    print(f"❌ {len(errors)} fail. ABORTING (no 60min ffmpeg waste).")
    for e in errors: print(f"  - {e}")
    sys.exit(1)
if warns:
    print(f"⚠ {len(warns)} warnings, but proceeding")
print(f"✅ all green, proceed to encode")
sys.exit(0)
