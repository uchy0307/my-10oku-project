#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_audio_for_scripts.py
========================
台本JSONから音声(.mp3) を edge-tts で一括生成。

使い方:
    python gen_audio_for_scripts.py --kind history
    python gen_audio_for_scripts.py --kind psych
    python gen_audio_for_scripts.py --kind history_shorts
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import edge_tts
except ImportError:
    print("[FATAL] edge-tts未導入。pip install edge-tts")
    sys.exit(2)

# 2026-05-30: 固有名詞ふりがな置換 (Task #35)
# edge-tts が「今川氏親→いまがしおや」と誤読する対策
try:
    from preprocess_yomi import apply_yomi  # type: ignore
except ImportError:
    def apply_yomi(text):  # フォールバック
        return text

ROOT = Path(__file__).resolve().parent.parent

VOICE = "ja-JP-NanamiNeural"
# 2026-05-30: RATE を -25% に変更。 +0% だと早口で 30min 動画化要件 (>=1500s) を満たせず、
# build_videos_seq.py で 600-880s しか出ず pipeline 「< 1500s で fail」になった。
# -25% で読み速度を落とし、 台本 7000-12000 chars で 1500s+ 確保。
RATE = "-25%"
PITCH = "+0Hz"

KIND_CONFIG = {
    "history": {
        "scripts_dir": ROOT / "youtube" / "history_v2" / "scripts",
        "audio_dir":   ROOT / "youtube" / "history_v2" / "audio",
    },
    "psych": {
        "scripts_dir": ROOT / "youtube" / "psych_v2" / "scripts",
        "audio_dir":   ROOT / "youtube" / "psych_v2" / "audio",
    },
    "history_shorts": {
        "scripts_dir": ROOT / "youtube" / "shorts_v2" / "scripts",
        "audio_dir":   ROOT / "youtube" / "shorts_v2" / "audio",
    },
    "otona_shorts": {
        "scripts_dir": ROOT / "youtube" / "otona_shorts_v2" / "scripts",
        "audio_dir":   ROOT / "youtube" / "otona_shorts_v2" / "audio",
    },
}


def extract_id(filename: str) -> str:
    """long_007.json -> 007"""
    stem = Path(filename).stem
    # take trailing digits
    digits = ""
    for ch in reversed(stem):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    return digits or stem


def script_to_text(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    chapters = data.get("chapters") or data.get("sections") or []
    parts = []
    for ch in chapters:
        if isinstance(ch, dict):
            t = (ch.get("text") or ch.get("narration") or "").strip()
            if t:
                parts.append(t)
        elif isinstance(ch, str):
            parts.append(ch.strip())
    if not parts and isinstance(data, dict) and data.get("text"):
        parts.append(str(data["text"]).strip())
    # shorts_v2 のスキーマ: narration_text フィールド
    if not parts and isinstance(data, dict) and data.get("narration_text"):
        parts.append(str(data["narration_text"]).strip())
    if not parts and isinstance(data, dict) and data.get("narration"):
        parts.append(str(data["narration"]).strip())
    return "\n\n".join(parts)


async def synth_one(text: str, out_mp3: Path) -> None:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    comm = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE, pitch=PITCH)
    audio_bytes = 0
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk.get("type") == "audio":
                f.write(chunk["data"])
                audio_bytes += len(chunk["data"])
    if audio_bytes < 5000:
        raise RuntimeError(f"audio too small ({audio_bytes}B)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(KIND_CONFIG.keys()))
    ap.add_argument("--force", action="store_true",
                    help="既存 mp3 を上書き再生成 (RATE 変更時等の再生成用)")
    ap.add_argument("--idx-from", type=int, default=1)
    ap.add_argument("--idx-to", type=int, default=999)
    args = ap.parse_args()
    cfg = KIND_CONFIG[args.kind]
    sdir = cfg["scripts_dir"]
    adir = cfg["audio_dir"]
    adir.mkdir(parents=True, exist_ok=True)

    if not sdir.exists():
        print(f"[FATAL] scripts dir not found: {sdir}")
        return 1
    scripts = sorted(sdir.glob("*.json"))
    print(f"[info] kind={args.kind} scripts={len(scripts)}")
    ok = 0
    skip = 0
    fail = 0
    for sp in scripts:
        idx = extract_id(sp.name)
        try:
            idx_n = int(idx)
            if not (args.idx_from <= idx_n <= args.idx_to):
                continue
        except ValueError:
            pass
        out = adir / f"{idx}.mp3"
        if out.exists() and out.stat().st_size > 5000 and not args.force:
            skip += 1
            continue
        if args.force and out.exists():
            print(f"[force] overwrite existing {out.name}")
        try:
            text = script_to_text(sp)
            if not text:
                print(f"[SKIP] {sp.name}: empty text")
                skip += 1
                continue
            # 2026-05-30: edge-tts 投入前にふりがな置換
            text_yomi = apply_yomi(text)
            yomi_diff = len(text_yomi) - len(text)
            print(f"[gen] {sp.name} ({len(text)} chars, yomi diff={yomi_diff:+d}) -> {out.name}")
            asyncio.run(synth_one(text_yomi, out))
            ok += 1
        except KeyboardInterrupt:
            print("[STOP] interrupted")
            break
        except Exception as e:
            fail += 1
            print(f"[FAIL] {sp.name}: {e}")
    print(f"\n=== Done: ok={ok} skip={skip} fail={fail} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
