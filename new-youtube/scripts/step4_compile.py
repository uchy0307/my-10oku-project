"""
Step 4: 動画合成・出力

入力 : voice.mp3 / 画像40-60枚 / BGM
処理 :
  - 画像を音声タイミングに合わせ均等切替 (10-15秒/枚)
  - 各画像に Ken Burns (微ズーム)
  - 章見出しを字幕として焼き込み (白文字+黒縁)
  - BGM を -20dB でループ mix
  - 1280x720 / H.264 / 24fps mp4

メモリ管理:
  - 章ごとに中間 mp4 を生成 → ffmpeg concat (-c copy)
  - 巨大 clip オブジェクトを保持しない
  - clip.close() を必ず呼ぶ
  - moviepy threads=2
"""
from __future__ import annotations
import sys as _flush_sys
try:
    _flush_sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
import builtins as _flush_b
if not hasattr(_flush_b, "_orig_print"):
    _flush_b._orig_print = _flush_b.print
    def _flush_print(*a, **k):
        k.setdefault("flush", True)
        return _flush_b._orig_print(*a, **k)
    _flush_b.print = _flush_print

import subprocess
from pathlib import Path

from moviepy.editor import (
    AudioFileClip, ImageClip, CompositeVideoClip,
    concatenate_videoclips, TextClip,
)

W, H, FPS = 1280, 720, 24


def _ken_burns(img_path: Path, duration: float, zoom_in: bool) -> ImageClip:
    clip = ImageClip(str(img_path)).set_duration(duration).resize((W, H))
    if zoom_in:
        clip = clip.resize(lambda t: 1.0 + 0.04 * (t / max(duration, 0.1)))
    else:
        clip = clip.resize(lambda t: 1.04 - 0.04 * (t / max(duration, 0.1)))
    return clip.set_position("center")


def _subtitle(text: str, duration: float) -> TextClip:
    return (
        TextClip(
            text, fontsize=44, color="white",
            stroke_color="black", stroke_width=2,
            method="caption", size=(W - 120, None),
        )
        .set_duration(duration)
        .set_position(("center", H - 140))
    )


def _compile_chapter(images: list[Path], audio_path: Path,
                     heading: str, out_path: Path) -> None:
    audio = AudioFileClip(str(audio_path))
    total = audio.duration
    n = max(1, len(images))
    per = total / n

    clips = [_ken_burns(p, per, zoom_in=(i % 2 == 0)) for i, p in enumerate(images)]
    base = concatenate_videoclips(clips, method="compose")
    sub = _subtitle(heading, total)
    final = CompositeVideoClip([base, sub], size=(W, H)).set_audio(audio)
    final.write_videofile(
        str(out_path), fps=FPS, codec="libx264", audio_codec="aac",
        threads=2, preset="medium", verbose=False, logger=None,
    )
    final.close(); base.close(); sub.close(); audio.close()
    for c in clips:
        c.close()


def _ffmpeg_concat(parts: list[Path], out_path: Path) -> None:
    list_file = out_path.parent / "_concat.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in parts), encoding="utf-8"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c", "copy", str(out_path)],
        check=True,
    )
    list_file.unlink(missing_ok=True)


def _mix_bgm(video: Path, bgm: Path, out: Path) -> None:
    """ナレ音声に BGM を -20dB でループ mix."""
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video),
        "-stream_loop", "-1", "-i", str(bgm),
        "-filter_complex",
        "[1:a]volume=-20dB[bgm];"
        "[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest", str(out),
    ], check=True)


def compile_video(script: dict,
                  voice_path: Path,
                  chapter_durations: list[float],
                  images_by_chapter: list[list[Path]],
                  chapter_audio_dir: Path,
                  bgm_path: Path | None,
                  out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    parts: list[Path] = []
    for ci, ch in enumerate(script["chapters"]):
        ap = chapter_audio_dir / f"ch{ch['id']:02d}.mp3"
        part = out_dir / f"part_ch{ch['id']:02d}.mp4"
        if not part.exists():
            _compile_chapter(images_by_chapter[ci], ap, ch["heading"], part)
        parts.append(part)

    concatenated = out_dir / "video_concat.mp4"
    _ffmpeg_concat(parts, concatenated)

    final_out = out_dir / "final.mp4"
    if bgm_path and bgm_path.exists():
        _mix_bgm(concatenated, bgm_path, final_out)
        concatenated.unlink(missing_ok=True)
    else:
        if final_out.exists():
            final_out.unlink()
        concatenated.rename(final_out)
    return final_out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script
    from step2_voice import generate_voice
    from step3_images import generate_all_images

    script_path = sys.argv[1] if len(sys.argv) > 1 else "inputs/script_001.json"
    script = read_script(script_path)

    voice_work = Path("outputs/voice_work")
    voice_mp3, durs = generate_voice(script, voice_work)

    imgs = generate_all_images(script, Path("cache/images"), target_per_chapter=5)

    bgm = Path("assets") / script["bgm"]
    final = compile_video(
        script, voice_mp3, durs, imgs,
        chapter_audio_dir=voice_work / "chapters",
        bgm_path=bgm,
        out_dir=Path("outputs/compile_work"),
    )
    print(f"FINAL: {final}")
