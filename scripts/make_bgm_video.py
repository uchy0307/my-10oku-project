#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
make_bgm_video.py
=================
2 時間 (7200s) の癒し BGM 動画を生成。
- 背景: 静止画 1 枚 (Wikipedia 時代写真 or 大人系イメージ)
- 動き: 微小 zoompan で「少し動く」エンドレス感
- 音声: フリー BGM mp3 を loop で 7200s 埋める

Usage:
  python scripts/make_bgm_video.py --kind history --image youtube/stock_images/wiki/cherry_001.jpg --bgm assets/bgm_koto.mp3 --title "侍と桜 2時間 癒しBGM" --out youtube/bgm/history_001.mp4
  python scripts/make_bgm_video.py --kind otona --image .../bar_night.jpg --bgm .../piano_ambient.mp3 --title "夜の静謐 2時間 癒しBGM" --out youtube/bgm/otona_001.mp4

依存: ffmpeg PATH
出力: 1920x1080 mp4, h264, aac, 2 時間
ファイルサイズ目安: 1-1.5 GB
"""
import argparse, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', choices=['history', 'otona'], required=True)
    ap.add_argument('--image', required=True, help='背景静止画')
    ap.add_argument('--bgm', required=True, help='BGM mp3 (loop 元)')
    ap.add_argument('--title', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--duration', type=int, default=7200, help='秒 (デフォルト 2時間)')
    args = ap.parse_args()

    img = Path(args.image)
    bgm = Path(args.bgm)
    out = Path(args.out)
    if not img.exists():
        print(f'[FATAL] image not found: {img}', file=sys.stderr)
        sys.exit(1)
    if not bgm.exists():
        print(f'[FATAL] bgm not found: {bgm}', file=sys.stderr)
        sys.exit(1)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 微小 zoompan: 0-7200s で 1.0 → 1.08 倍にゆっくり拡大 + 中心固定
    frames = args.duration * 30
    vf = (
        f"scale=2400:1400:force_original_aspect_ratio=increase,"
        f"crop=2304:1296,"
        f"zoompan=z='min(1+0.00001*on,1.08)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s=1920x1080:fps=30,"
        f"setsar=1,"
        f"drawtext=fontfile=C\\:/Windows/Fonts/YuGothB.ttc:"
        f"text='{args.title}':fontcolor=white@0.4:fontsize=24:"
        f"x=(w-text_w)/2:y=h-60:enable='between(t,0,15)'"
    )

    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-i', str(img),
        '-stream_loop', '-1', '-i', str(bgm),
        '-vf', vf,
        '-map', '0:v:0', '-map', '1:a:0',
        '-t', str(args.duration),
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '24',
        '-pix_fmt', 'yuv420p', '-r', '30',
        '-c:a', 'aac', '-b:a', '128k',
        '-shortest',
        str(out),
    ]
    print(f'[bgm] generating {args.duration}s ({args.duration/60:.0f}分) BGM video', flush=True)
    print(f'[bgm] image: {img.name}', flush=True)
    print(f'[bgm] bgm:   {bgm.name}', flush=True)
    print(f'[bgm] out:   {out}', flush=True)

    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f'[bgm] FFMPEG FAIL rc={r.returncode}')
        sys.exit(r.returncode)

    size_mb = out.stat().st_size / 1024 / 1024
    print(f'[bgm] DONE {out} ({size_mb:.1f}MB)')


if __name__ == '__main__':
    main()
