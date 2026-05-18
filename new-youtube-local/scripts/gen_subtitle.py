"""gen_subtitle.py
output/p001_voice.wav の duration と current.json body text から
等分配 SRT を生成。step4_compile_night.py が読む。

字幕は「画面 1/3 以下」要件のため、step4 側で FontSize=32 程度に焼込み。
"""
import os, sys, json, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Auto-load .env (when run standalone)
_ENV = ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _k = _k.strip(); _v = _v.strip()
        if _k and _k not in os.environ:
            os.environ[_k] = _v

OUTPUT_DIR = ROOT / "output"

CHARS_PER_LINE = int(os.environ.get("SUB_CHARS_PER_LINE", "20"))
MAX_CHARS_PER_SUB = int(os.environ.get("SUB_MAX_CHARS", "40"))


def split_text_balanced(body, max_chars=MAX_CHARS_PER_SUB):
    """body を句読点 / 改行で分割して max_chars 以下の subtitle chunks に。"""
    chunks = []
    # まず改行で分割
    paragraphs = [p.strip() for p in body.split("\n") if p.strip()]
    for para in paragraphs:
        # 句点 (。) で更に分割
        sentences = []
        cur = ""
        for ch in para:
            cur += ch
            if ch in "。！？":
                sentences.append(cur.strip())
                cur = ""
        if cur.strip():
            sentences.append(cur.strip())
        # 各 sentence を max_chars 以下に細分
        for sent in sentences:
            if len(sent) <= max_chars:
                chunks.append(sent)
            else:
                # 読点 (、) で切る
                parts = sent.split("、")
                buf = ""
                for p in parts:
                    if buf and len(buf) + len(p) + 1 > max_chars:
                        chunks.append(buf.strip("、"))
                        buf = p
                    else:
                        buf = buf + "、" + p if buf else p
                if buf:
                    chunks.append(buf.strip("、"))
    return [c for c in chunks if c]


def fmt_srt_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    tid = cur["id"]

    voice_path = OUTPUT_DIR / f"{tid}_voice.wav"
    if not voice_path.exists():
        print(f"[gen_subtitle] missing {voice_path}")
        sys.exit(1)

    w = wave.open(str(voice_path), "rb")
    total_sec = w.getnframes() / w.getframerate()
    w.close()
    print(f"[gen_subtitle] voice {total_sec:.1f}s")

    all_chunks = []
    chapter_offsets = []
    for c in cur["chapters"]:
        chunks = split_text_balanced(c["body"])
        chapter_offsets.append(len(all_chunks))
        all_chunks.extend(chunks)
    chapter_offsets.append(len(all_chunks))

    if not all_chunks:
        print("[gen_subtitle] FATAL: 0 chunks")
        sys.exit(2)
    print(f"[gen_subtitle] {len(all_chunks)} subtitle chunks")

    # 文字数比例で時間を割り振る
    total_chars = sum(len(c) for c in all_chunks)
    head_sec = 0.4  # step2 HEAD_MS と同じ
    per_char = (total_sec - head_sec) / total_chars
    print(f"[gen_subtitle] per_char={per_char*1000:.1f}ms")

    srt_lines = []
    cursor = head_sec
    for i, c in enumerate(all_chunks):
        dur = max(1.0, len(c) * per_char)
        start = cursor
        end = cursor + dur
        cursor = end
        srt_lines.append(str(i + 1))
        srt_lines.append(f"{fmt_srt_time(start)} --> {fmt_srt_time(end)}")
        srt_lines.append(c)
        srt_lines.append("")

    srt_text = "\n".join(srt_lines)
    out = OUTPUT_DIR / f"{tid}_subtitle.srt"
    out.write_text(srt_text, encoding="utf-8")
