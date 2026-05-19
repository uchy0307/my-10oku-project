#!/usr/bin/env -S python3 -u
"""
burn_subtitles.py — SRT 字幕を mp4 に焼き込む汎用モジュール

ffmpeg の `subtitles` filter (libass) を使い、SRT を映像にハードコード焼き付ける。
Windows パスの `C:\\...\\...srt` は filtergraph parser を壊すため、
コロンと区切り文字を所定の形でエスケープする。

Usage (import):
    from new_youtube.scripts.burn_subtitles import burn_subtitles
    burn_subtitles("in.mp4", "subs.srt", "out.mp4")

Usage (CLI):
    python burn_subtitles.py in.mp4 subs.srt out.mp4
    python burn_subtitles.py --video in.mp4 --srt subs.srt --out out.mp4 [--force-style "..."]

Notes:
  - 音声は無変換コピー (-c:a copy)、映像のみ再エンコード (libx264)
  - subtitles filter は absolute path 推奨。Windows でも動くようエスケープ処理あり
  - --force-style を渡せば ASS スタイル上書きが可能（例: "FontName=Yu Gothic,FontSize=28"）
  - 失敗時はリトライ無し・例外を即座に投げる
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _ffmpeg_bin() -> str:
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError(
            "ffmpeg not found on PATH and imageio-ffmpeg not installed."
        ) from e


def _escape_subtitles_path(path: str) -> str:
    """ffmpeg subtitles filter 用にパスをエスケープする。

    filtergraph parser:
      - `:` はフィルタ引数区切り → `\\:` に
      - `\\` は filter エスケープ文字 → `/` に正規化（Windows パス）
      - `'` は引用符 → `\\'` に
      - `,` はフィルタ区切り → `\\,` に
    """
    # Windows 区切り → POSIX 風に正規化
    p = path.replace("\\", "/")
    # コロンエスケープ（ドライブレター含むあらゆる `:`）
    p = p.replace(":", "\\:")
    # シングルクオート
    p = p.replace("'", "\\'")
    # カンマ
    p = p.replace(",", "\\,")
    return p


def burn_subtitles(
    video_path: str | Path,
    srt_path: str | Path,
    output_path: str | Path,
    *,
    force_style: str | None = None,
    crf: int = 20,
    preset: str = "medium",
) -> Path:
    """SRT を mp4 に焼き込んで output_path に書き出す。

    Args:
        video_path:  入力 mp4
        srt_path:    入力 SRT
        output_path: 出力 mp4
        force_style: 任意。subtitles filter の force_style 文字列
                     例: "FontName=Yu Gothic,FontSize=28,OutlineColour=&H00000000"
        crf:         libx264 CRF（小さいほど高画質、デフォルト 20）
        preset:      libx264 preset（デフォルト medium）

    Returns:
        生成された mp4 の Path

    Raises:
        FileNotFoundError: 入力 mp4 / SRT が存在しない
        RuntimeError: ffmpeg 失敗
    """
    video = Path(video_path)
    srt = Path(srt_path)
    out = Path(output_path)

    if not video.is_file():
        raise FileNotFoundError(f"burn_subtitles: video not found: {video}")
    if not srt.is_file():
        raise FileNotFoundError(f"burn_subtitles: srt not found: {srt}")

    out.parent.mkdir(parents=True, exist_ok=True)

    # 絶対パスに正規化（filter 内では現在ディレクトリ依存にしたくない）
    srt_abs = os.path.abspath(str(srt))
    escaped = _escape_subtitles_path(srt_abs)

    if force_style:
        # force_style は filter 引数の一部。値中の `:` `,` `'` も再度エスケープが必要
        fs = force_style.replace("\\", "\\\\").replace(":", "\\:").replace(
            ",", "\\,").replace("'", "\\'")
        sub_filter = f"subtitles='{escaped}':force_style='{fs}'"
    else:
        sub_filter = f"subtitles='{escaped}'"

    ffmpeg = _ffmpeg_bin()
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(video),
        "-vf", sub_filter,
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(out),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"burn_subtitles: ffmpeg failed (rc={res.returncode}):\n"
            f"  filter: {sub_filter}\n"
            f"  stderr: {res.stderr.strip()}"
        )
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"burn_subtitles: output mp4 missing/empty: {out}")
    return out


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Burn SRT into mp4 via ffmpeg/libass")
    ap.add_argument("video_pos", nargs="?")
    ap.add_argument("srt_pos", nargs="?")
    ap.add_argument("out_pos", nargs="?")
    ap.add_argument("--video")
    ap.add_argument("--srt")
    ap.add_argument("--out")
    ap.add_argument("--force-style", default=None)
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--preset", default="medium")
    args = ap.parse_args()

    video = args.video or args.video_pos
    srt = args.srt or args.srt_pos
    out = args.out or args.out_pos
    if not (video and srt and out):
        ap.error("video, srt, and out paths are required")

    p = burn_subtitles(
        video, srt, out,
        force_style=args.force_style, crf=args.crf, preset=args.preset,
    )
    print(f"[burn_subtitles] OK bytes={p.stat().st_size} path={p}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
