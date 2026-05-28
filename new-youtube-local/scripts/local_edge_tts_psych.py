#!/usr/bin/env -S python3 -u
"""local_edge_tts_psych.py - generate edge-tts mp3+srt for psych_v2."""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

try:
    import edge_tts
    from edge_tts import SubMaker
except ImportError:
    print("[FATAL] edge-tts not installed. Run: pip install edge-tts", file=sys.stderr)
    sys.exit(2)

VOICE = "ja-JP-NanamiNeural"
RATE = "+0%"
PITCH = "+0Hz"

REPO_ROOT = Path(__file__).resolve().parents[2]
PSYCH_SCRIPTS_DIR = REPO_ROOT / "youtube" / "psych_v2" / "scripts"
PSYCH_AUDIO_DIR = REPO_ROOT / "youtube" / "psych_v2" / "audio"


def _load_text(json_path: Path) -> str:
    spec = json.loads(json_path.read_text(encoding="utf-8"))
    chapters = spec.get("chapters") or spec.get("sections") or []
    if not chapters:
        if isinstance(spec, dict) and spec.get("text"):
            return str(spec["text"]).strip()
        raise ValueError(f"no chapters/sections in {json_path}")
    parts = []
    for ch in chapters:
        t = (ch.get("text") or ch.get("narration") or "").strip()
        if t:
            parts.append(t)
    if not parts:
        raise ValueError(f"all chapters empty in {json_path}")
    return "\n\n".join(parts)


async def _synthesize(text: str, out_mp3: Path, out_srt: Path) -> None:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
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
                if hasattr(submaker, "feed"):
                    submaker.feed(chunk)
                else:
                    submaker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])
    if audio_bytes < 10_000:
        raise RuntimeError(f"audio too small ({audio_bytes}B)")
    if hasattr(submaker, "get_srt"):
        srt_text = submaker.get_srt()
    elif hasattr(submaker, "generate_subs"):
        srt_text = submaker.generate_subs()
    else:
        srt_text = str(submaker)
    out_srt.write_text(srt_text, encoding="utf-8")


def run_for_index(idx: str) -> None:
    if not (idx.isdigit() and len(idx) == 3):
        raise ValueError(f"index must be 3-digit string, got: {idx!r}")
    json_path = PSYCH_SCRIPTS_DIR / f"psych_{idx}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"script not found: {json_path}")
    out_mp3 = PSYCH_AUDIO_DIR / f"{idx}.mp3"
    out_srt = PSYCH_AUDIO_DIR / f"{idx}.srt"
    text = _load_text(json_path)
    print(f"[local_edge_tts_psych] index={idx} chars={len(text)} -> {out_mp3.name}")
    asyncio.run(_synthesize(text, out_mp3, out_srt))
    print(f"[local_edge_tts_psych] OK index={idx} voice={VOICE}")


def main(argv):
    if len(argv) == 2:
        run_for_index(argv[1].strip())
        return 0
    print("usage: python local_edge_tts_psych.py <index>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
