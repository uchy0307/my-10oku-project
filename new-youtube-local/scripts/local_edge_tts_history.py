#!/usr/bin/env -S python3 -u
"""
local_edge_tts_history.py — ローカル PC 専用 edge-tts ナレーション生成 (history_v2)

GitHub Actions cloud runner は edge-tts endpoint から 403 で蹴られるため、
ローカル Windows PC 上で edge-tts ja-JP-NanamiNeural を実行し、
mp3 + word-level SRT を生成して history_v2/audio/ にコミットする。

CLI:
    python local_edge_tts_history.py <long_index>           # 例: 011
    python local_edge_tts_history.py <input_json> <out_mp3> <out_srt>   # 直叩き

仕様 (feedback_yt_pipeline_quality_v2.md, 2026-05-21):
    voice    = ja-JP-NanamiNeural
    rate     = +0%  (atempo 補正なし)
    pitch    = +0Hz
    output   = MP3 (cloud runner 側でそのまま narration として使用)
    subtitles = word-level SRT (cloud runner 側で ASS に変換し焼き込み)

無料・API キー不要・完全自動化。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

try:
    import edge_tts  # type: ignore
    from edge_tts import SubMaker  # type: ignore
except ImportError as e:  # pragma: no cover
    print(
        "[local_edge_tts_history][FATAL] edge-tts is required. "
        "Install with: pip install edge-tts",
        file=sys.stderr,
    )
    sys.exit(2)


VOICE = "ja-JP-NanamiNeural"
RATE = "+0%"   # atempo 補正禁止 (feedback_yt_pipeline_quality_v2.md)
PITCH = "+0Hz"

REPO_ROOT = Path(__file__).resolve().parents[2]
HISTORY_SCRIPTS_DIR = REPO_ROOT / "youtube" / "history_v2" / "scripts"
HISTORY_AUDIO_DIR = REPO_ROOT / "youtube" / "history_v2" / "audio"


def _load_chapters_text(json_path: Path) -> str:
    spec = json.loads(json_path.read_text(encoding="utf-8"))
    chapters = spec.get("chapters") or []
    if not chapters:
        raise ValueError(f"no chapters in {json_path}")
    # 章の区切りには長めの読点 + 改行を入れて自然な間を作る。
    parts: list[str] = []
    for ch in chapters:
        t = (ch.get("text") or "").strip()
        if not t:
            continue
        parts.append(t)
    if not parts:
        raise ValueError(f"all chapters empty in {json_path}")
    # 章間に短い無音相当のポーズ（句点 + 改行）。edge-tts は改行で軽く間を取る。
    return "\n\n".join(parts)


async def _synthesize(text: str, out_mp3: Path, out_srt: Path) -> None:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    out_srt.parent.mkdir(parents=True, exist_ok=True)

    communicate = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE, pitch=PITCH)
    submaker = SubMaker()

    audio_bytes = 0
    with open(out_mp3, "wb") as f:
        async for chunk in communicate.stream():
            ct = chunk.get("type")
            if ct == "audio":
                f.write(chunk["data"])
                audio_bytes += len(chunk["data"])
            elif ct == "WordBoundary":
                # edge-tts >=7.x: SubMaker.feed(chunk)
                # edge-tts <7.x:  submaker.create_sub((offset, duration), text)
                if hasattr(submaker, "feed"):
                    submaker.feed(chunk)
                else:
                    submaker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])

    if audio_bytes < 10_000:
        raise RuntimeError(
            f"audio too small ({audio_bytes}B). edge-tts may have been rate-limited."
        )

    # SRT 出力: 新 API は get_srt() 、旧 API は __str__() で VTT を返す。
    if hasattr(submaker, "get_srt"):
        srt_text = submaker.get_srt()
    elif hasattr(submaker, "generate_subs"):
        srt_text = submaker.generate_subs()
    else:
        # 旧 API: VTT を生成し SRT 風に変換 (Cloud 側で更にパース)
        srt_text = str(submaker)
    out_srt.write_text(srt_text, encoding="utf-8")


def run_for_long_index(long_index: str) -> tuple[Path, Path]:
    if not (long_index.isdigit() and len(long_index) == 3):
        raise ValueError(f"long_index must be 3-digit string, got: {long_index!r}")

    json_path = HISTORY_SCRIPTS_DIR / f"long_{long_index}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"script not found: {json_path}")

    out_mp3 = HISTORY_AUDIO_DIR / f"{long_index}.mp3"
    out_srt = HISTORY_AUDIO_DIR / f"{long_index}.srt"

    text = _load_chapters_text(json_path)
    print(f"[local_edge_tts_history] index={long_index} chars={len(text)} -> {out_mp3.name}")
    asyncio.run(_synthesize(text, out_mp3, out_srt))
    mp3_size = out_mp3.stat().st_size
    srt_size = out_srt.stat().st_size
    print(
        f"[local_edge_tts_history] OK index={long_index} "
        f"mp3={mp3_size}B srt={srt_size}B voice={VOICE} rate={RATE}"
    )
    return out_mp3, out_srt


def run_direct(input_json: Path, out_mp3: Path, out_srt: Path) -> None:
    text = _load_chapters_text(input_json)
    print(f"[local_edge_tts_history] direct chars={len(text)} -> {out_mp3}")
    asyncio.run(_synthesize(text, out_mp3, out_srt))


def main(argv: list[str]) -> int:
    if len(argv) == 2:
        long_index = argv[1].strip()
        run_for_long_index(long_index)
        return 0
    if len(argv) == 4:
        in_json = Path(argv[1])
        out_mp3 = Path(argv[2])
        out_srt = Path(argv[3])
        run_direct(in_json, out_mp3, out_srt)
        return 0
    print(
        "usage:\n"
        "  python local_edge_tts_history.py <long_index>\n"
        "  python local_edge_tts_history.py <input.json> <out.mp3> <out.srt>",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
