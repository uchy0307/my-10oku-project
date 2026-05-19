#!/usr/bin/env -S python3 -u
"""
tts_edge.py — edge-tts integration (完全無料・API キー不要)

Microsoft Edge の Read-Aloud TTS endpoint を叩く `edge-tts` パッケージを
使い、日本語ナレーション wav を生成する汎用モジュール。

Usage (import):
    from new_youtube.scripts.tts_edge import tts_edge
    tts_edge("こんにちは世界", Path("out.wav"))

Usage (CLI):
    python tts_edge.py "こんにちは世界" out.wav
    python tts_edge.py --text "..." --out out.wav [--voice ja-JP-NanamiNeural] [--rate -5%]

Notes:
  - edge-tts は MP3 で受信するため ffmpeg で wav 16-bit / 24kHz に変換する
  - rate は SSMLっぽい文字列 (`-5%` `+10%` 等)。デフォルト `-5%`
  - voice は ja-JP-NanamiNeural / ja-JP-KeitaNeural 等が使える
  - 失敗時はリトライ無し・例外を即座に投げる（呼び出し側で扱う）
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import edge_tts  # type: ignore
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "edge-tts is required. Install with: pip install edge-tts"
    ) from e


DEFAULT_VOICE = "ja-JP-NanamiNeural"
DEFAULT_RATE = "-5%"
DEFAULT_SR = 24000  # 16-bit PCM 24kHz wav


def _ffmpeg_bin() -> str:
    """ffmpeg バイナリの場所を解決。PATH 優先、無ければ imageio-ffmpeg。"""
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError(
            "ffmpeg not found on PATH and imageio-ffmpeg not installed. "
            "Install ffmpeg or `pip install imageio-ffmpeg`."
        ) from e


async def _synth_mp3(text: str, mp3_path: Path, voice: str, rate: str) -> None:
    """edge-tts で MP3 を生成。失敗時は AssertionError / NoAudioReceived 等を伝播。"""
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(str(mp3_path))


def tts_edge(
    text: str,
    output_path: str | Path,
    *,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    sample_rate: int = DEFAULT_SR,
) -> Path:
    """日本語テキストを wav に合成して output_path に書き出す。

    Args:
        text:        合成するテキスト（日本語想定）
        output_path: 出力 wav パス
        voice:       edge-tts voice 名（デフォルト ja-JP-NanamiNeural）
        rate:        速度 SSML 文字列（デフォルト -5%）
        sample_rate: wav サンプリングレート（デフォルト 24000）

    Returns:
        生成された wav の Path

    Raises:
        ValueError: text が空
        RuntimeError: ffmpeg 不在 / 変換失敗
        edge_tts 由来の例外: 合成失敗
    """
    if not text or not text.strip():
        raise ValueError("tts_edge: text is empty")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = _ffmpeg_bin()

    with tempfile.TemporaryDirectory(prefix="tts_edge_") as td:
        mp3 = Path(td) / "raw.mp3"
        asyncio.run(_synth_mp3(text, mp3, voice, rate))
        if not mp3.exists() or mp3.stat().st_size == 0:
            raise RuntimeError(
                f"tts_edge: edge-tts produced empty MP3 (voice={voice}, rate={rate})"
            )

        # MP3 -> wav (PCM s16le mono at sample_rate)
        cmd = [
            ffmpeg, "-y", "-loglevel", "error",
            "-i", str(mp3),
            "-ac", "1",
            "-ar", str(sample_rate),
            "-c:a", "pcm_s16le",
            str(out),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(
                f"tts_edge: ffmpeg failed (rc={res.returncode}): {res.stderr.strip()}"
            )

    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"tts_edge: output wav missing/empty: {out}")
    return out


def _cli() -> int:
    ap = argparse.ArgumentParser(description="edge-tts -> wav (JP)")
    ap.add_argument("text_pos", nargs="?", help="text to synthesize (positional)")
    ap.add_argument("out_pos", nargs="?", help="output wav path (positional)")
    ap.add_argument("--text", help="text to synthesize")
    ap.add_argument("--out", help="output wav path")
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--rate", default=DEFAULT_RATE)
    ap.add_argument("--sample-rate", type=int, default=DEFAULT_SR)
    args = ap.parse_args()

    text = args.text or args.text_pos
    out = args.out or args.out_pos
    if not text or not out:
        ap.error("text and output path are required")

    p = tts_edge(text, out, voice=args.voice, rate=args.rate, sample_rate=args.sample_rate)
    size = p.stat().st_size
    print(f"[tts_edge] OK voice={args.voice} rate={args.rate} bytes={size} path={p}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
