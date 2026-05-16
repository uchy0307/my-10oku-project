"""
Pipeline runner: Step 0 → 1 → 2 → 3 → 4 [→ 5]

Usage:
  python scripts/run_pipeline.py                # topics.json から取り出し
  python scripts/run_pipeline.py --topic "..."  # トピック直指定
  python scripts/run_pipeline.py --script inputs/script_001.json  # 既存JSON使用
  python scripts/run_pipeline.py --no-upload    # Step 5 をスキップ
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from step1_load import read_script
from step2_voice import generate_voice
from step3_images import generate_all_images
from step4_compile import compile_video


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", help="既存 script JSON を使う")
    ap.add_argument("--topic")
    ap.add_argument("--no-upload", action="store_true")
    args = ap.parse_args()

    repo = ROOT.parent  # new-youtube/
    inputs = repo / "inputs"
    outputs = repo / "outputs"
    cache = repo / "cache" / "images"
    assets = repo / "assets"

    if args.script:
        script_path = Path(args.script)
    else:
        from step0_gemini_generate import generate_script, pick_topic
        topic = args.topic or pick_topic(inputs / "topics.json")
        script_path = generate_script(topic, inputs)

    script = read_script(script_path)
    print(f"[1/4] script OK: {script_path.name}")

    voice_work = outputs / script_path.stem / "voice_work"
    voice_mp3, durs = generate_voice(script, voice_work)
    print(f"[2/4] voice OK: {voice_mp3} (sum {sum(durs):.1f}s)")

    imgs = generate_all_images(script, cache, target_per_chapter=5)
    print(f"[3/4] images OK: {sum(len(c) for c in imgs)} files")

    compile_work = outputs / script_path.stem / "compile_work"
    bgm = assets / script["bgm"]
    final = compile_video(
        script, voice_mp3, durs, imgs,
        chapter_audio_dir=voice_work / "chapters",
        bgm_path=bgm if bgm.exists() else None,
        out_dir=compile_work,
    )
    print(f"[4/4] video OK: {final}")

    if not args.no_upload:
        from step5_upload import upload_video
        vid = upload_video(final, script, privacy="private")
        print(f"[5/5] uploaded: {vid}")


if __name__ == "__main__":
    main()
