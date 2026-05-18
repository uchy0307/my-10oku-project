"""step2_voice_voicevox.py
VOICEVOX API (http://localhost:50021) で 冥鳴ひまり voice 生成
- /speakers から「冥鳴ひまり」style_id を解決（環境変数 VOICEVOX_STYLE_ID で上書き可）
- 章ごとに /audio_query → /synthesis でWAV取得
- pydub で連結 → output/<id>_voice.wav
"""
import os, sys, json, time
from pathlib import Path
import urllib.request, urllib.parse, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
TMP_DIR = OUTPUT_DIR / "tmp_voice"

VOICEVOX_URL = os.environ.get("VOICEVOX_URL", "http://localhost:50021")
SPEAKER_NAME = os.environ.get("VOICEVOX_SPEAKER_NAME", "冥鳴ひまり")
STYLE_NAME = os.environ.get("VOICEVOX_STYLE_NAME", "ノーマル")
FORCE_STYLE_ID = os.environ.get("VOICEVOX_STYLE_ID", "")
SPEED = float(os.environ.get("VOICEVOX_SPEED", "1.0"))
PITCH = float(os.environ.get("VOICEVOX_PITCH", "0.0"))
INTONATION = float(os.environ.get("VOICEVOX_INTONATION", "1.0"))

def http_get(path):
    req = urllib.request.Request(f"{VOICEVOX_URL}{path}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def http_post(path, data=None, params=None, headers=None):
    q = ""
    if params:
        q = "?" + urllib.parse.urlencode(params)
    h = {"Content-Type": "application/json"} if data is not None else {}
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(f"{VOICEVOX_URL}{path}{q}", data=body, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()

def resolve_style_id():
    if FORCE_STYLE_ID:
        print(f"[step2] using forced style_id={FORCE_STYLE_ID}")
        return int(FORCE_STYLE_ID)
    speakers = json.loads(http_get("/speakers").decode("utf-8"))
    for sp in speakers:
        if sp.get("name") == SPEAKER_NAME:
            styles = sp.get("styles", [])
            # まず STYLE_NAME 一致を試す
            for st in styles:
                if st.get("name") == STYLE_NAME:
                    print(f"[step2] resolved {SPEAKER_NAME}/{STYLE_NAME} -> style_id={st['id']}")
                    return int(st["id"])
            # 無ければ最初のスタイル
            if styles:
                print(f"[step2] fallback {SPEAKER_NAME}/{styles[0]['name']} -> style_id={styles[0]['id']}")
                return int(styles[0]["id"])
    raise RuntimeError(f"speaker not found: {SPEAKER_NAME}. Available: {[s.get('name') for s in speakers]}")

def synth_chapter(text: str, style_id: int, out_path: Path):
    q = http_post("/audio_query", data=b"", params={"text": text, "speaker": style_id})
    query = json.loads(q.decode("utf-8"))
    query["speedScale"] = SPEED
    query["pitchScale"] = PITCH
    query["intonationScale"] = INTONATION
    query["outputSamplingRate"] = 24000
    wav = http_post("/synthesis", data=query, params={"speaker": style_id})
    out_path.write_bytes(wav)

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    chapters = cur["chapters"]

    # 接続テスト
    try:
        http_get("/version")
    except Exception as e:
        print(f"[step2] FATAL: VOICEVOX not reachable at {VOICEVOX_URL}: {e}")
        sys.exit(2)

    style_id = resolve_style_id()

    # 章ごとに合成し、各 chunk の text/path を持って timings を組み立て
    chapter_data = []  # [(chapter_idx, [(path, text)])]
    for c in chapters:
        body = c["body"]
        chunks = [p.strip() for p in body.split("\n") if p.strip()]
        merged = []
        for i, chunk in enumerate(chunks):
            wav_path = TMP_DIR / f"ch{c['index']:02d}_p{i:03d}.wav"
            for attempt in range(3):
                try:
                    synth_chapter(chunk, style_id, wav_path)
                    break
                except Exception as e:
                    print(f"[step2] retry ch{c['index']} p{i}: {e}")
                    time.sleep(2 ** attempt)
            merged.append((wav_path, chunk))
        chapter_data.append((c["index"], merged))
        print(f"[step2] chapter {c['index']}: {len(merged)} segments")

    # pydub で連結 + timings 採取
    from pydub import AudioSegment
    HEAD_MS = 400
    PARA_MS = 300
    CHAP_MS = 900
    full = AudioSegment.silent(duration=HEAD_MS)
    cursor_sec = HEAD_MS / 1000.0
    timings = []
    for ch_idx, seg_list in chapter_data:
        for pi, (sp, text) in enumerate(seg_list):
            seg = AudioSegment.from_wav(str(sp))
            dur = len(seg) / 1000.0
            start = cursor_sec
            end = start + dur
            timings.append({
                "chapter": ch_idx,
                "paragraph_index": pi,
                "sub_index": 0,
                "file": sp.name,
                "duration_sec": round(dur, 3),
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "text": text,
            })
            full = full + seg + AudioSegment.silent(duration=PARA_MS)
            cursor_sec = end + PARA_MS / 1000.0
        full = full + AudioSegment.silent(duration=CHAP_MS)
        cursor_sec += CHAP_MS / 1000.0

    out = OUTPUT_DIR / f"{cur['id']}_voice.wav"
    full.export(str(out), format="wav")
    total_sec = len(full) / 1000.0
    print(f"[step2] wrote {out} ({total_sec:.1f}s)")

    # meta
    meta = {
        "engine": "voicevox",
        "style_id": style_id,
        "speaker": SPEAKER_NAME,
        "duration_sec": round(total_sec, 3),
        "chunk_count": len(timings),
    }
    (OUTPUT_DIR / f"{cur['id']}_voice_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # timings JSON
    timings_obj = {
        "id": cur["id"],
        "engine": "voicevox",
        "speaker": SPEAKER_NAME,
        "head_silence_ms": HEAD_MS,
        "para_break_ms": PARA_MS,
        "chapter_break_ms": CHAP_MS,
        "total_duration_sec": round(total_sec, 3),
        "chunks": timings,
    }
    (OUTPUT_DIR / f"{cur['id']}_voice_timings.json").write_text(
        json.dumps(timings_obj, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # SRT 生成（字幕焼込み用）
    srt_lines = []
    for i, t in enumerate(timings, 1):
        srt_lines.append(str(i))
        srt_lines.append(f"{_srt_time(t['start_sec'])} --> {_srt_time(t['end_sec'])}")
        srt_lines.append(_wrap_sub(t["text"], width=32))
        srt_lines.append("")
    (OUTPUT_DIR / f"{cur['id']}_subtitle.srt").write_text("\n".join(srt_lines), encoding="utf-8")
    print(f"[step2] wrote subtitle.srt ({len(timings)} cues)")


def _srt_time(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _wrap_sub(text: str, width: int = 32) -> str:
    text = text.replace("\n", " ").strip()
    if not text:
        return ""
    lines = []
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= width and ch in "。、！？…":
            lines.append(buf)
            buf = ""
    if buf:
        lines.append(buf)
    if not lines:
        return text
    if len(lines) > 2:
        joined = "".join(lines)
        half = (len(joined) + 1) // 2
        lines = [joined[:half], joined[half:]]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
