"""step4_compile_day.py
朝昼版（A案）コンパイル: 静止画 Ken Burns ＋ ナレ ＋ 字幕焼込み。
- 入力: output/<id>_voice.wav, output/<id>_img_*.jpg, output/<id>_subtitle.srt
- 出力: output/<id>_video.mp4
- moviepy で画像 + 音声を合成 → ffmpeg で SRT 焼込み (libass/subtitles filter)
"""
import os, sys, json, glob, shutil, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

FPS = int(os.environ.get("VIDEO_FPS", "24"))
W = int(os.environ.get("VIDEO_W", "1280"))
H = int(os.environ.get("VIDEO_H", "720"))
CROSSFADE = float(os.environ.get("CROSSFADE_SEC", "0.8"))
SUB_FONT = os.environ.get("SUB_FONT", "Noto Sans CJK JP")
SUB_FONT_SIZE = int(os.environ.get("SUB_FONT_SIZE", "32"))

# === 15-min cap for unverified YouTube account (auto-applied) ===
MAX_DURATION_SEC = float(os.environ.get("MAX_DURATION_SEC", "870"))

def compile_silent_video(tid: str) -> Path:
    from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
    from moviepy.video.fx.all import resize as fx_resize

    voice_path = OUTPUT_DIR / f"{tid}_voice.wav"
    if not voice_path.exists():
        print(f"[step4_day] missing voice: {voice_path}")
        sys.exit(1)
    audio = AudioFileClip(str(voice_path))
    total_dur = audio.duration
    print(f"[step4_day] audio duration: {total_dur:.1f}s")

    if total_dur > MAX_DURATION_SEC:
        print(f"[step4_day] truncating audio {total_dur:.1f}s -> {MAX_DURATION_SEC:.1f}s (15-min cap)")
        audio = audio.subclip(0, MAX_DURATION_SEC)
        total_dur = MAX_DURATION_SEC

    img_files = sorted(glob.glob(str(OUTPUT_DIR / f"{tid}_img_*.jpg")))
    if not img_files:
        print("[step4_day] no images")
        sys.exit(1)
    print(f"[step4_day] {len(img_files)} images")

    per_clip = total_dur / len(img_files)
    clips = []
    for i, p in enumerate(img_files):
        c = ImageClip(p).set_duration(per_clip + CROSSFADE)
        c = c.resize(lambda t, c=c: 1.0 + 0.06 * (t / max(c.duration, 0.001)))
        c = c.set_position(("center", "center"))
        if i > 0:
            c = c.crossfadein(CROSSFADE)
        clips.append(c)

    video = concatenate_videoclips(clips, method="compose", padding=-CROSSFADE)
    video = video.set_audio(audio).set_duration(total_dur)
    video = fx_resize(video, newsize=(W, H))

    pre_path = OUTPUT_DIR / f"{tid}_video_nosubs.mp4"
    video.write_videofile(
        str(pre_path), fps=FPS, codec="libx264", audio_codec="aac",
        threads=4, preset="medium", bitrate="2500k",
        temp_audiofile=str(OUTPUT_DIR / f"{tid}_tmp_audio.m4a"),
        remove_temp=True,
    )
    print(f"[step4_day] wrote silent-sub video: {pre_path}")
    return pre_path

def burn_subtitles(pre_path: Path, srt_path: Path, out_path: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")

    force_style = (
        f"FontName={SUB_FONT},"
        f"FontSize={SUB_FONT_SIZE},"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2,"
        "MarginV=40"
    )
    srt_arg = str(srt_path).replace("\\", "/").replace(":", r"\:")
    vf = f"subtitles={srt_arg}:force_style='{force_style}'"

    cmd = [
        "ffmpeg", "-y", "-i", str(pre_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "copy",
        str(out_path),
    ]
    print("[step4_day] ffmpeg:", " ".join(cmd))
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout[-3000:])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg subtitles burn failed rc={r.returncode}")

def main():
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    tid = cur["id"]

    out_path = OUTPUT_DIR / f"{tid}_video.mp4"
    srt_path = OUTPUT_DIR / f"{tid}_subtitle.srt"

    pre_path = compile_silent_video(tid)

    if srt_path.exists():
        try:
            burn_subtitles(pre_path, srt_path, out_path)
            try:
                pre_path.unlink()
            except Exception:
                pass
        except Exception as e:
            print(f"[step4_day] WARN: subtitle burn failed ({e}); fall back to no-subs video")
            shutil.move(str(pre_path), str(out_path))
    else:
        print(f"[step4_day] WARN: {srt_path} not found, skip subtitle burn")
        shutil.move(str(pre_path), str(out_path))

    print(f"[step4_day] FINAL: {out_path} ({out_path.stat().st_size/1024/1024:.1f}MB)")

if __name__ == "__main__":
    main()
