"""
Step 4: 動画合成・出力

入力 : voice.mp3 / 画像 N枚 (章ごとに分割) / BGM / script (ナレ全文)
処理 :
  - 章ごと: 画像を音声タイミングに合わせ均等切替 (Ken Burns 微ズーム)
  - 全体: ナレ全文を SRT 化（章持続時間に文字数比例で時刻割当）
  - ffmpeg subtitles filter (libass) で字幕焼き込み (Noto Sans CJK JP)
  - BGM を -20dB でループ mix

2026-05-20 fix:
  - 旧版は章見出しの TextClip オーバーレイのみ → ナレ字幕一切なし。
  - SRT 生成 + ffmpeg burn-in を追加 (new-youtube-local/step4_compile_day.py と同等)。
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

import os
import re
import shutil
import subprocess
from pathlib import Path

from moviepy.editor import (
    AudioFileClip, ImageClip,
    concatenate_videoclips,
)

W, H, FPS = 1280, 720, 24
SUB_FONT = os.environ.get("SUB_FONT", "Noto Sans CJK JP")
SUB_FONT_SIZE = int(os.environ.get("SUB_FONT_SIZE", "36"))


def _ken_burns(img_path: Path, duration: float, zoom_in: bool) -> ImageClip:
    clip = ImageClip(str(img_path)).set_duration(duration).resize((W, H))
    if zoom_in:
        clip = clip.resize(lambda t: 1.0 + 0.04 * (t / max(duration, 0.1)))
    else:
        clip = clip.resize(lambda t: 1.04 - 0.04 * (t / max(duration, 0.1)))
    return clip.set_position("center")


def _compile_chapter(images: list[Path], audio_path: Path,
                     out_path: Path) -> None:
    """章単体 mp4 を書き出す。字幕は後段の ffmpeg burn-in で乗せるため、
    moviepy 段階では入れない (TextClip ImageMagick 依存を完全に切る)。"""
    audio = AudioFileClip(str(audio_path))
    total = audio.duration
    n = max(1, len(images))
    per = total / n

    clips = [_ken_burns(p, per, zoom_in=(i % 2 == 0)) for i, p in enumerate(images)]
    base = concatenate_videoclips(clips, method="compose")
    final = base.set_audio(audio)
    final.write_videofile(
        str(out_path), fps=FPS, codec="libx264", audio_codec="aac",
        threads=2, preset="medium", verbose=False, logger=None,
    )
    final.close(); base.close(); audio.close()
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


# -------- Subtitle (SRT) generation + burn-in --------

_SENT_SPLIT = re.compile(r"(?<=[。．！？!?])\s*")


def _split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENT_SPLIT.split(text) if s and s.strip()]
    # 長すぎる文は読点で再分割（字幕1枚あたり最大40文字目安）
    out: list[str] = []
    for s in parts:
        if len(s) <= 40:
            out.append(s)
            continue
        sub = re.split(r"(?<=[、,])\s*", s)
        buf = ""
        for piece in sub:
            if not piece:
                continue
            if len(buf) + len(piece) <= 40:
                buf += piece
            else:
                if buf:
                    out.append(buf)
                buf = piece
        if buf:
            out.append(buf)
    return out


def _format_srt_time(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(script: dict, chapter_durations: list[float],
              chapter_audio_dir: Path | None = None) -> str:
    """ナレ全文を SRT に変換。章ごとの真の duration（audio file長さ）を
    引数 chapter_durations から受け取り、その内側で文字数比例で各文に時間を割当てる。
    実音声ファイルが存在する場合はそちらの長さを優先（より正確）。
    """
    lines: list[str] = []
    idx = 1
    cursor = 0.0
    for ci, ch in enumerate(script["chapters"]):
        ch_dur = chapter_durations[ci] if ci < len(chapter_durations) else 0.0
        if chapter_audio_dir is not None:
            cp = chapter_audio_dir / f"ch{ch['id']:02d}.mp3"
            if cp.exists():
                try:
                    from pydub import AudioSegment
                    ch_dur = len(AudioSegment.from_file(cp)) / 1000.0
                except Exception:
                    pass
        # chapter 間に 0.6s pause (step2_voice generate_voice の pause と合わせる)
        sentences = _split_sentences(ch["narration"])
        if not sentences:
            cursor += ch_dur + 0.6
            continue
        total_chars = sum(len(s) for s in sentences) or 1
        ch_start = cursor
        # 0.6s pause は次の章頭に置く (前章末では字幕なし)
        for sent in sentences:
            dur = ch_dur * (len(sent) / total_chars)
            start = cursor
            end = cursor + dur
            lines.append(str(idx))
            lines.append(f"{_format_srt_time(start)} --> {_format_srt_time(end)}")
            lines.append(sent)
            lines.append("")
            idx += 1
            cursor = end
        # ensure cursor advances at least to ch_start + ch_dur
        cursor = ch_start + ch_dur + 0.6
    return "\n".join(lines)


def _burn_subtitles(pre_path: Path, srt_path: Path, out_path: Path) -> None:
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
    # Linux のパスは ':' を含まないが Windows で実行された場合のため両対応
    srt_arg = str(srt_path).replace("\\", "/").replace(":", r"\:")
    vf = f"subtitles={srt_arg}:force_style='{force_style}'"
    cmd = [
        "ffmpeg", "-y", "-i", str(pre_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "copy",
        str(out_path),
    ]
    print("[step4] ffmpeg burn:", " ".join(cmd))
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True)
    print(r.stdout[-3000:])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg subtitles burn failed rc={r.returncode}")


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
            _compile_chapter(images_by_chapter[ci], ap, part)
        parts.append(part)

    concatenated = out_dir / "video_concat.mp4"
    _ffmpeg_concat(parts, concatenated)

    # BGM mix → pre-subtitle video
    pre_path = out_dir / "video_pre_subs.mp4"
    if bgm_path and bgm_path.exists():
        _mix_bgm(concatenated, bgm_path, pre_path)
        concatenated.unlink(missing_ok=True)
    else:
        if pre_path.exists():
            pre_path.unlink()
        concatenated.rename(pre_path)

    # SRT 生成
    srt_path = out_dir / "subtitle.srt"
    srt_text = build_srt(script, chapter_durations,
                         chapter_audio_dir=chapter_audio_dir)
    srt_path.write_text(srt_text, encoding="utf-8")
    cue_count = srt_text.count(" --> ")
    print(f"[step4] wrote SRT: {srt_path} ({cue_count} cues)")

    # ffmpeg subtitles filter で burn-in
    final_out = out_dir / "final.mp4"
    if cue_count > 0:
        try:
            _burn_subtitles(pre_path, srt_path, final_out)
            pre_path.unlink(missing_ok=True)
        except Exception as e:
            print(f"[step4] WARN subtitle burn failed ({e}); using pre-subs video")
            if final_out.exists():
                final_out.unlink()
            pre_path.rename(final_out)
    else:
        print("[step4] WARN no cues, skip subtitle burn")
        if final_out.exists():
            final_out.unlink()
        pre_path.rename(final_out)
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
