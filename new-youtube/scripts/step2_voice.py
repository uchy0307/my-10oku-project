#!/usr/bin/env -S python3 -u
"""
Step 2: narration voice generation
Provider : Google Cloud Text-to-Speech REST API (direct, GOOGLE_API_KEY auth)
Voice    : ja-JP-Neural2-B (same as samurai pipeline)

Notes:
- Per-chapter synth -> mp3 cached under work_dir/chapters/
- Concatenated via pydub -> work_dir/voice.mp3
- Returns (voice.mp3 path, [chapter_duration_sec, ...])
"""
from __future__ import annotations
import os
import sys
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from pydub import AudioSegment

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GCP_VOICE = "ja-JP-Neural2-B"
TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


def _tts_google(text: str, out_path: Path) -> None:
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY env var is not set")
    body = {
        "input": {"text": text},
        "voice": {
            "languageCode": "ja-JP",
            "name": GCP_VOICE,
            "ssmlGender": "FEMALE",
        },
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0},
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        TTS_URL + "?key=" + GOOGLE_API_KEY,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")
        raise RuntimeError("TTS HTTP " + str(e.code) + ": " + body_txt)
    audio_b64 = payload.get("audioContent")
    if not audio_b64:
        raise RuntimeError("TTS missing audioContent: " + json.dumps(payload)[:200])
    out_path.write_bytes(base64.b64decode(audio_b64))


def synth_chapter(text: str, out_path: Path) -> None:
    _tts_google(text, out_path)


def generate_voice(script: dict, work_dir: Path):
    work_dir.mkdir(parents=True, exist_ok=True)
    chap_dir = work_dir / "chapters"
    chap_dir.mkdir(exist_ok=True)

    durations = []
    combined = AudioSegment.silent(duration=0)
    pause = AudioSegment.silent(duration=600)

    for ch in script["chapters"]:
        cp = chap_dir / ("ch%02d.mp3" % ch["id"])
        if not cp.exists() or cp.stat().st_size < 1000:
            print("[step2] synth ch%02d (%d chars)" % (ch["id"], len(ch["narration"])), flush=True)
            synth_chapter(ch["narration"], cp)
        else:
            print("[step2] cache ch%02d (%d bytes)" % (ch["id"], cp.stat().st_size), flush=True)
        seg = AudioSegment.from_file(cp, format="mp3")
        durations.append(len(seg) / 1000.0)
        combined += seg + pause

    out = work_dir / "voice.mp3"
    combined.export(out, format="mp3", bitrate="128k")
    print("[step2] voice.mp3 written: " + str(out), flush=True)
    return out, durations


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script

    script = read_script(sys.argv[1] if len(sys.argv) > 1 else "inputs/script_001.json")
    out, durs = generate_voice(script, Path("outputs/voice_work"))
    print("voice : " + str(out), flush=True)
    print("durs  : " + str([round(d, 1) for d in durs]), flush=True)
    print("total : " + str(round(sum(durs), 1)) + "s", flush=True)
