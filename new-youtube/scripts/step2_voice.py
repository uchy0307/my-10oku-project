"""
Step 2: ナレーション音声生成

Primary  : ElevenLabs Multilingual v2 (日本語女性ボイス)
Fallback : Google Cloud TTS Neural2-B (samurai と同設定)

設計:
- 章ごとに synth → 中間 mp3 を chapters/ に保存（再実行時キャッシュ）
- 全章を pydub で結合し voice.mp3 を出力
- 各章の duration (秒) を返す → Step 4 で使う
"""
from __future__ import annotations
import os
from pathlib import Path
from pydub import AudioSegment

ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
GCP_VOICE = "ja-JP-Neural2-B"  # samurai と同等


def _tts_elevenlabs(text: str, out_path: Path) -> None:
    import requests
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"}
    body = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    r = requests.post(url, json=body, headers=headers, timeout=180)
    r.raise_for_status()
    out_path.write_bytes(r.content)


def _tts_gcp(text: str, out_path: Path) -> None:
    from google.cloud import texttospeech as tts
    client = tts.TextToSpeechClient()
    inp = tts.SynthesisInput(text=text)
    voice = tts.VoiceSelectionParams(
        language_code="ja-JP",
        name=GCP_VOICE,
        ssml_gender=tts.SsmlVoiceGender.FEMALE,
    )
    cfg = tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3, speaking_rate=1.0)
    res = client.synthesize_speech(input=inp, voice=voice, audio_config=cfg)
    out_path.write_bytes(res.audio_content)


def synth_chapter(text: str, out_path: Path) -> None:
    """章単位 TTS。ElevenLabs 優先・失敗時 GCP fallback。"""
    if ELEVENLABS_KEY:
        try:
            _tts_elevenlabs(text, out_path)
            return
        except Exception as e:
            print(f"[WARN] ElevenLabs failed ({e}); fallback to GCP")
    _tts_gcp(text, out_path)


def generate_voice(script: dict, work_dir: Path) -> tuple[Path, list[float]]:
    """
    Returns: (voice.mp3 path, [chapter_duration_sec, ...])
    streaming: chapter mp3 -> AudioSegment 結合 -> export
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    chap_dir = work_dir / "chapters"
    chap_dir.mkdir(exist_ok=True)

    durations: list[float] = []
    combined = AudioSegment.silent(duration=0)
    pause = AudioSegment.silent(duration=600)  # 章間ポーズ 0.6s

    for ch in script["chapters"]:
        cp = chap_dir / f"ch{ch['id']:02d}.mp3"
        if not cp.exists() or cp.stat().st_size < 1000:
            synth_chapter(ch["narration"], cp)
        seg = AudioSegment.from_file(cp, format="mp3")
        durations.append(len(seg) / 1000.0)
        combined += seg + pause

    out = work_dir / "voice.mp3"
    combined.export(out, format="mp3", bitrate="128k")
    return out, durations


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script

    script = read_script(sys.argv[1] if len(sys.argv) > 1 else "inputs/script_001.json")
    out, durs = generate_voice(script, Path("outputs/voice_work"))
    print(f"voice : {out}")
    print(f"durs  : {[round(d, 1) for d in durs]}")
    print(f"total : {round(sum(durs), 1)}s")
