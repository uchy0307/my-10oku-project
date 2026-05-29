#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble_video.py
=================
audio + multiple images -> mp4 video.
ローカル ffmpeg を使ってチャンク方式で長尺動画を作る（タイムアウト回避）。

使い方:
    python assemble_video.py --kind history --audio path.mp3 --out output.mp4 --duration 900

kind:
    history  -> 1280x720 横長、wiki_hist_*.jpg から自動選択
    psych    -> 1280x720 横長、wiki_cafe_/library_/bedroom_ から選択
    shorts   -> 1080x1920 縦長、wiki_tokyo_/cafe_ から選択
"""

import argparse
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

# Windows で stdout/stderr を UTF-8 に統一（文字化け防止）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent  # 10oku-project/
STOCK_DIR = ROOT / "youtube" / "stock_images" / "wiki"


def pick_images(kind: str, n: int = 9):
    if kind == "history":
        prefixes = ["wiki_hist_sengoku_", "wiki_hist_armor_", "wiki_hist_edo_", "wiki_hist_kabuki_", "wiki_hist_meiji_", "wiki_hist_bakumatsu_"]
    elif kind == "psych":
        prefixes = ["wiki_cafe_", "wiki_library_", "wiki_bedroom_", "wiki_balcony_", "wiki_sunset_", "wiki_stars_"]
    elif kind == "shorts":
        prefixes = ["wiki_tokyo_", "wiki_kyoto_", "wiki_rainy_", "wiki_station_"]
    else:
        raise ValueError(f"unknown kind: {kind}")

    candidates = []
    for p in prefixes:
        candidates += sorted(STOCK_DIR.glob(p + "*.jpg"))
    random.shuffle(candidates)
    return candidates[:n] or [next(STOCK_DIR.glob("wiki_*.jpg"))]


def run_ffmpeg(args, label=""):
    print(f"[ffmpeg] {label}")
    result = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args,
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        print("STDERR:", result.stderr[-500:])
        raise RuntimeError(f"ffmpeg failed: {label}")


def assemble(kind: str, audio: Path, out: Path, duration: int):
    if kind == "shorts":
        w, h = 1080, 1920
        scale = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    else:
        w, h = 1280, 720
        scale = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"

    n_images = 9
    per_chunk = duration / n_images

    images = pick_images(kind, n_images)
    if len(images) < n_images:
        images = (images * (n_images // len(images) + 1))[:n_images]

    print(f"images: {[i.name for i in images]}")
    print(f"per chunk: {per_chunk:.1f}s, output: {out}")

    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        chunks = []

        # Chunk video (no audio yet)
        for i, img in enumerate(images):
            chunk_out = tmp / f"chunk_{i:02d}.mp4"
            run_ffmpeg([
                "-loop", "1", "-t", f"{per_chunk:.2f}", "-i", str(img),
                "-vf", scale,
                "-r", "15", "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", "30", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                "-an", str(chunk_out)
            ], label=f"chunk {i+1}/{n_images}")
            chunks.append(chunk_out)

        # Concat list
        concat_list = tmp / "list.txt"
        concat_list.write_text("\n".join(f"file '{c}'" for c in chunks))

        # Concat video-only
        video_only = tmp / "video_only.mp4"
        run_ffmpeg([
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", str(video_only)
        ], label="concat video")

        # Mux with audio
        run_ffmpeg([
            "-i", str(video_only), "-i", str(audio),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
            "-shortest", "-movflags", "+faststart", str(out)
        ], label="mux audio")

    print(f"DONE: {out} ({out.stat().st_size / 1024 / 1024:.1f} MB)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kind", required=True, choices=["history", "psych", "shorts"])
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--duration", type=int, default=900)
    args = p.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    assemble(args.kind, args.audio, args.out, args.duration)


if __name__ == "__main__":
    main()
