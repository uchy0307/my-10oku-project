"""step2_voice_gtts.py
Google Cloud TTS (REST API key) による音声合成。
- 既存 step2_voice_voicevox.py と同じ I/O:
  入力:  output/current.json
  出力:  output/<id>_voice.wav            （pydub で連結した全編）
  追加:  output/<id>_voice_timings.json   （Phase C: chunk 毎の duration 実測）
         output/<id>_voice_meta.json
- chunk = 段落（body を改行で split）。voicevox 版と同じ粒度。
- API key: 環境変数 GOOGLE_API_KEY を使用（GHA secrets で注入）。
- voice: ja-JP-Neural2-B（女性）デフォルト。環境変数 GTTS_VOICE_NAME で上書き可。

cloud (GitHub Actions runner) で voicevox 無しに動かすための差し替え。
"""
import os, sys, json, time, base64, subprocess
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
TMP_DIR = OUTPUT_DIR / "tmp_voice_gtts"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GTTS_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"

VOICE_NAME = os.environ.get("GTTS_VOICE_NAME", "ja-JP-Neural2-B")
VOICE_LANG = os.environ.get("GTTS_VOICE_LANG", "ja-JP")
VOICE_GENDER = os.environ.get("GTTS_VOICE_GENDER", "FEMALE")
SPEAKING_RATE = float(os.environ.get("GTTS_SPEAKING_RATE", "1.0"))
PITCH = float(os.environ.get("GTTS_PITCH", "0.0"))
SAMPLE_RATE = int(os.environ.get("GTTS_SAMPLE_RATE", "24000"))

PARA_BREAK_MS = int(os.environ.get("PARA_BREAK_MS", "300"))
CHAPTER_BREAK_MS = int(os.environ.get("CHAPTER_BREAK_MS", "900"))
HEAD_SILENCE_MS = int(os.environ.get("HEAD_SILENCE_MS", "400"))

MAX_BYTES_PER_REQ = 4500


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def split_for_tts(text: str):
    if len(text.encode("utf-8")) <= MAX_BYTES_PER_REQ:
        return [text]
    seps = ["。", "！", "？", "\n"]
    parts = [text]
    for sep in seps:
        new_parts = []
        for p in parts:
            if len(p.encode("utf-8")) <= MAX_BYTES_PER_REQ:
                new_parts.append(p)
                continue
            tokens = p.split(sep)
            buf = ""
            for i, tk in enumerate(tokens):
                piece = tk + (sep if i < len(tokens) - 1 else "")
                if len((buf + piece).encode("utf-8")) > MAX_BYTES_PER_REQ and buf:
                    new_parts.append(buf)
                    buf = piece
                else:
                    buf += piece
            if buf:
                new_parts.append(buf)
        parts = new_parts
    final = []
    for p in parts:
        b = p.encode("utf-8")
        if len(b) <= MAX_BYTES_PER_REQ:
            final.append(p)
            continue
        i = 0
        while i < len(b):
            j = min(i + MAX_BYTES_PER_REQ, len(b))
            while j > i and (b[j - 1] & 0xC0) == 0x80:
                j -= 1
            final.append(b[i:j].decode("utf-8", errors="ignore"))
            i = j
    return [s for s in final if s.strip()]


def synth_one(text: str, out_mp3: Path, attempt: int = 1) -> None:
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY env not set")
    url = f"{GTTS_ENDPOINT}?key={GOOGLE_API_KEY}"
    body = {
        "input": {"text": text},
        "voice": {"languageCode": VOICE_LANG, "name": VOICE_NAME, "ssmlGender": VOICE_GENDER},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": SPEAKING_RATE, "pitch": PITCH, "sampleRateHertz": SAMPLE_RATE},
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        audio_b64 = data.get("audioContent")
        if not audio_b64:
            raise RuntimeError(f"no audioContent: {data}")
        out_mp3.write_bytes(base64.b64decode(audio_b64))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="ignore")
        print(f"[step2_gtts] HTTPError {e.code}: {msg[:300]}")
        if attempt < 4:
            time.sleep(2 ** attempt)
            return synth_one(text, out_mp3, attempt + 1)
        raise


def ffprobe_duration(p: Path) -> float:
    try:
        r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(p)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        s = r.stdout.strip()
        if s:
            return float(s)
    except Exception as e:
        print(f"[step2_gtts] ffprobe failed: {e}")
    from pydub import AudioSegment
    seg = AudioSegment.from_file(str(p))
    return len(seg) / 1000.0


def _srt_time(sec: float) -> str:
    if sec < 0: sec = 0.0
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000: ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _wrap_sub(text: str, width: int = 32) -> str:
    text = text.replace("\n", " ").strip()
    if not text: return ""
    lines = []
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= width and ch in "。、！？…":
            lines.append(buf); buf = ""
    if buf: lines.append(buf)
    if not lines: return text
    if len(lines) > 2:
        joined = "".join(lines)
        half = (len(joined) + 1) // 2
        lines = [joined[:half], joined[half:]]
    return "\n".join(lines)


def main():
    ensure_dir(OUTPUT_DIR)
    ensure_dir(TMP_DIR)
    cur_path = OUTPUT_DIR / "current.json"
    if not cur_path.exists():
        print(f"[step2_gtts] missing {cur_path}"); sys.exit(1)
    cur = json.loads(cur_path.read_text(encoding="utf-8"))
    chapters = cur["chapters"]
    tid = cur["id"]
    if not GOOGLE_API_KEY:
        print("[step2_gtts] FATAL: GOOGLE_API_KEY env not set"); sys.exit(2)
    from pydub import AudioSegment
    timings = []
    head_silence = AudioSegment.silent(duration=HEAD_SILENCE_MS)
    para_silence = AudioSegment.silent(duration=PARA_BREAK_MS)
    chap_silence = AudioSegment.silent(duration=CHAPTER_BREAK_MS)
    full = head_silence
    cursor_sec = HEAD_SILENCE_MS / 1000.0
    for c in chapters:
        body = c.get("body", "")
        paras = [p.strip() for p in body.split("\n") if p.strip()]
        print(f"[step2_gtts] chapter {c['index']}: {len(paras)} paragraphs")
        for pi, para in enumerate(paras):
            sub_chunks = split_for_tts(para)
            for si, sub in enumerate(sub_chunks):
                mp3_path = TMP_DIR / f"ch{c['index']:02d}_p{pi:03d}_s{si:02d}.mp3"
                for attempt in range(3):
                    try:
                        synth_one(sub, mp3_path); break
                    except Exception as e:
                        print(f"[step2_gtts] retry: {e}"); time.sleep(2 ** attempt)
                else:
                    print(f"[step2_gtts] FAIL"); sys.exit(3)
                dur = ffprobe_duration(mp3_path)
                start = cursor_sec; end = start + dur
                timings.append({"chapter": c["index"], "paragraph_index": pi, "sub_index": si,
                    "file": mp3_path.name, "duration_sec": round(dur, 3),
                    "start_sec": round(start, 3), "end_sec": round(end, 3), "text": sub})
                seg = AudioSegment.from_file(str(mp3_path))
                full = full + seg
                cursor_sec = end
                print(f"[step2_gtts]   ch{c['index']} p{pi} s{si}: {dur:.2f}s")
            full = full + para_silence
            cursor_sec += PARA_BREAK_MS / 1000.0
        full = full + chap_silence
        cursor_sec += CHAPTER_BREAK_MS / 1000.0
    out_wav = OUTPUT_DIR / f"{tid}_voice.wav"
    full.export(str(out_wav), format="wav", parameters=["-ar", str(SAMPLE_RATE)])
    total_sec = len(full) / 1000.0
    print(f"[step2_gtts] wrote {out_wav} ({total_sec:.1f}s)")
    timings_obj = {"id": tid, "voice_name": VOICE_NAME, "language": VOICE_LANG,
        "sample_rate": SAMPLE_RATE, "speaking_rate": SPEAKING_RATE, "pitch": PITCH,
        "head_silence_ms": HEAD_SILENCE_MS, "para_break_ms": PARA_BREAK_MS,
        "chapter_break_ms": CHAPTER_BREAK_MS, "total_duration_sec": round(total_sec, 3), "chunks": timings}
    (OUTPUT_DIR / f"{tid}_voice_timings.json").write_text(
        json.dumps(timings_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {"engine": "google-cloud-tts", "voice": VOICE_NAME, "duration_sec": round(total_sec, 3), "chunk_count": len(timings)}
    (OUTPUT_DIR / f"{tid}_voice_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    srt_path = OUTPUT_DIR / f"{tid}_subtitle.srt"
    srt_lines = []
    for i, t in enumerate(timings, 1):
        srt_lines.append(str(i))
        srt_lines.append(f"{_srt_time(t['start_sec'])} --> {_srt_time(t['end_sec'])}")
        srt_lines.append(_wrap_sub(t["text"], width=32))
        srt_lines.append("")
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    print(f"[step2_gtts] wrote {srt_path} ({len(timings)} cues)")


if __name__ == "__main__":
    main()
