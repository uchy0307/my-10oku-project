#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
make_audio_drama.py
===================
5-10 分の音声ドラマを生成。
- edge-tts 多声化 (ナレーター + 登場人物 2-3 名)
- BGM/SE を ffmpeg で mix
- 静止画 1 枚 (時代背景) + 字幕で動画化
- 歴史系: samurai YouTube 用 → 時代物
- 大人系: otona YouTube 用 → 心理学・人間関係物
- 同 mp3 を toi-suite (自社HP) にも配置可能

入力 JSON:
  {
    "title": "ドラマタイトル",
    "kind": "history" | "otona",
    "image": "path/to/bg.jpg",
    "bgm":   "path/to/bgm.mp3",
    "scenes": [
      {"voice": "ja-JP-DaichiNeural", "text": "ナレーション..."},
      {"voice": "ja-JP-KeitaNeural",  "text": "登場人物A: ..."},
      {"voice": "ja-JP-NanamiNeural", "text": "登場人物B: ..."}
    ]
  }

Usage:
  python scripts/make_audio_drama.py --spec youtube/audio_drama/scripts/history_001.json --out youtube/audio_drama/.work/history_001/

依存: edge-tts (pip install edge-tts), ffmpeg
"""
import argparse, asyncio, json, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')


async def tts_one(text, voice, out_mp3):
    try:
        import edge_tts
    except ImportError:
        print('[FATAL] edge-tts not installed. pip install edge-tts', file=sys.stderr)
        sys.exit(2)
    comm = edge_tts.Communicate(text, voice)
    await comm.save(str(out_mp3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', required=True, help='出力ディレクトリ')
    args = ap.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f'[FATAL] spec not found: {spec_path}', file=sys.stderr)
        sys.exit(1)
    spec = json.loads(spec_path.read_text(encoding='utf-8'))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    title = spec.get('title', spec_path.stem)
    image = ROOT / spec['image'] if not Path(spec['image']).is_absolute() else Path(spec['image'])
    bgm_spec = spec.get('bgm', '')
    use_bgm = bool(bgm_spec)
    bgm = (ROOT / bgm_spec if not Path(bgm_spec).is_absolute() else Path(bgm_spec)) if use_bgm else None
    if use_bgm and not bgm.exists():
        print(f'[WARN] bgm not found: {bgm} → BGM 無しで続行')
        use_bgm = False
        bgm = None
    scenes = spec.get('scenes', [])
    if not scenes:
        print('[FATAL] no scenes')
        sys.exit(1)

    # 1) 各 scene を edge-tts で mp3 化
    print(f'[drama] generating {len(scenes)} scene voices', flush=True)
    scene_mp3s = []
    for i, sc in enumerate(scenes):
        mp3 = out_dir / f'scene_{i:03d}.mp3'
        asyncio.run(tts_one(sc['text'], sc.get('voice', 'ja-JP-DaichiNeural'), mp3))
        scene_mp3s.append(mp3)
        print(f'  scene_{i:03d}: {mp3.stat().st_size} bytes ({sc.get("voice", "?")})')

    # 2) シーン間に 0.4 秒の無音を挟みつつ binary 結合 (mp3 は単純 cat で OK)
    silence = out_dir / '_silence_400ms.mp3'
    subprocess.run([
        'ffmpeg', '-y', '-f', 'lavfi',
        '-i', 'anullsrc=channel_layout=mono:sample_rate=24000',
        '-t', '0.4', '-c:a', 'libmp3lame', '-b:a', '128k', str(silence)
    ], check=True, capture_output=True)

    voice_concat = out_dir / 'voice.mp3'
    silence_bytes = silence.read_bytes()
    with open(voice_concat, 'wb') as fout:
        for i, m in enumerate(scene_mp3s):
            fout.write(m.read_bytes())
            if i < len(scene_mp3s) - 1:
                fout.write(silence_bytes)
    print(f'[drama] voice.mp3 created: {voice_concat.stat().st_size:,} bytes (binary concat)', flush=True)

    # 3) BGM を -15 dB で mix (任意)
    voice_dur = float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(voice_concat)
    ]).decode().strip())
    print(f'[drama] voice duration: {voice_dur:.1f}s (use_bgm={use_bgm})')

    final_audio = out_dir / 'final_audio.mp3'
    if use_bgm:
        subprocess.run([
            'ffmpeg', '-y',
            '-i', str(voice_concat),
            '-stream_loop', '-1', '-i', str(bgm),
            '-filter_complex',
            f'[1:a]volume=0.18[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2',
            '-c:a', 'libmp3lame', '-b:a', '192k',
            '-t', str(voice_dur),
            str(final_audio),
        ], check=True, capture_output=True)
    else:
        # BGM 無し: voice そのまま流用 (再 encode)
        subprocess.run([
            'ffmpeg', '-y',
            '-i', str(voice_concat),
            '-c:a', 'libmp3lame', '-b:a', '192k',
            str(final_audio),
        ], check=True, capture_output=True)

    # 4) 静止画 + 音声で動画化 (1920x1080, ken-burns)
    out_mp4 = out_dir / 'output.mp4'
    frames = int(voice_dur * 30)
    vf = (
        f"scale=2400:1400:force_original_aspect_ratio=increase,crop=2304:1296,"
        f"zoompan=z='min(1+0.00005*on,1.05)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s=1920x1080:fps=30,"
        f"setsar=1"
    )
    subprocess.run([
        'ffmpeg', '-y',
        '-loop', '1', '-i', str(image),
        '-i', str(final_audio),
        '-vf', vf,
        '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        str(out_mp4),
    ], check=True)

    size_mb = out_mp4.stat().st_size / 1024 / 1024
    print(f'[drama] DONE {out_mp4} ({size_mb:.1f}MB, {voice_dur/60:.1f}分)')


if __name__ == '__main__':
    main()
