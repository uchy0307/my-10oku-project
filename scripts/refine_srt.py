#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""refine_srt.py
原稿(JSON chapters)の正確なテキストと whisper の単語タイミングを合成し、
読みやすい SRT を生成する。

問題:
- whisper の日本語 base モデルは誤認識が多い (采配→採隔、大乱→大ら、終止符→修士夫)
- 5文字×1.26秒の早すぎcue で読めない
- 途中切れの chunk が見苦しい

解決:
- テキストは原稿 JSON (chapters[].text) からそのまま使用
- タイミングは whisper words の比例マッピングで近似
- 句点(。)で必ず切る、target 12-13字、最低 1.5秒/cue
- 助詞始まりは前にマージ
- 13字超過は \\N で改行

Usage:
  python scripts/refine_srt.py --script youtube/history_v2/scripts/long_014.json \\
                                --words  youtube/history_v2/audio/014_words.json \\
                                --out    youtube/history_v2/audio/014.srt

  python scripts/refine_srt.py --kind history --index 014   # ショートカット
"""
import argparse, json, sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

PARTICLE_STARTS = ("の", "を", "は", "が", "に", "で", "と", "や", "へ", "も",
                   "から", "まで", "より", "って", "けど", "ので", "のに",
                   "けれど", "けれども", "なので", "だから", "ね", "よ", "た")

HARD_BREAK = set("。！？!?")
SOFT_BREAK = set("、,")
TARGET_CHARS = 12
MAX_CHARS = 14
MIN_DUR = 1.5


def srt_ts(sec: float) -> str:
    ms = int(round(max(0, sec) * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def load_script_text(script_json: Path) -> str:
    """chapters[].text を結合し原稿全文を返す。
    余計な空白・改行は除去するが句読点は残す。
    """
    data = json.loads(script_json.read_text(encoding="utf-8"))
    chapters = data.get("chapters") or []
    if not chapters:
        # short_*.json の場合 narration / text フィールド
        return (data.get("narration") or data.get("text") or "").strip()
    return "".join((ch.get("text") or "").strip() for ch in chapters)


def map_time(orig_idx: int, T: int, words: list) -> float:
    """原稿 idx → whisper word の start time を比例マッピング"""
    W = len(words)
    if W == 0 or T == 0:
        return 0.0
    w_idx = min(W - 1, max(0, int(round(orig_idx * W / T))))
    return float(words[w_idx]["start"])


def chunk_text(text: str):
    """原稿テキストを (start_char_idx, end_char_idx, displayed_text) リストに分割"""
    chunks = []
    buf_start = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        buf_len = i - buf_start + 1

        # 句点 → 強制切断 (短すぎ chunk は次に持ち越し)
        if c in HARD_BREAK and buf_len >= 5:
            chunks.append((buf_start, i + 1, text[buf_start:i + 1]))
            buf_start = i + 1
            i += 1
            continue

        # 読点 → target 近傍で切断
        if c in SOFT_BREAK and buf_len >= TARGET_CHARS - 3:
            chunks.append((buf_start, i + 1, text[buf_start:i + 1]))
            buf_start = i + 1
            i += 1
            continue

        # max 到達で強制カット
        if buf_len >= MAX_CHARS:
            chunks.append((buf_start, i + 1, text[buf_start:i + 1]))
            buf_start = i + 1
            i += 1
            continue

        # target 到達 → 助詞でない次の良い切れ目を探す
        if buf_len >= TARGET_CHARS:
            chunks.append((buf_start, i + 1, text[buf_start:i + 1]))
            buf_start = i + 1
            i += 1
            continue

        i += 1
    if buf_start < n:
        chunks.append((buf_start, n, text[buf_start:n]))

    # 助詞始まりは前 chunk にマージ
    merged = []
    for s, e, t in chunks:
        t_strip = t.strip()
        if (merged and t_strip
                and any(t_strip.startswith(p) for p in PARTICLE_STARTS)):
            ps, pe, pt = merged[-1]
            if len(pt) + len(t) <= MAX_CHARS + 2:
                merged[-1] = (ps, e, pt + t)
                continue
        merged.append((s, e, t))
    return merged


def refine(script_json: Path, words_json: Path, srt_out: Path) -> tuple[int, float]:
    text = load_script_text(script_json)
    text = text.replace("\r", "").replace("\n", "").strip()
    if not text:
        print(f"[refine] empty script: {script_json}")
        return 0, 0.0

    words = json.loads(words_json.read_text(encoding="utf-8"))
    if not words:
        print(f"[refine] empty words: {words_json}")
        return 0, 0.0

    T = len(text)
    chunks = chunk_text(text)
    lines = []
    for i, (s, e, t) in enumerate(chunks, 1):
        if not t.strip():
            continue
        start = map_time(s, T, words)
        end = map_time(e, T, words)
        # 最低 cue 持続
        end = max(end, start + MIN_DUR)
        # 次 cue とぶつからないように
        if i < len(chunks):
            next_start = map_time(chunks[i][0], T, words)
            end = min(end, next_start - 0.05)
        if end <= start:
            end = start + MIN_DUR
        # 13字超過 → \N で 2行表示
        display = t.replace("\\", "").replace("{", "").replace("}", "")
        if len(display) > 13:
            half = (len(display) + 1) // 2
            display = display[:half] + r"\N" + display[half:]
        lines.append(f"{i}\n{srt_ts(start)} --> {srt_ts(end)}\n{display}\n")

    srt_out.write_text("\n".join(lines), encoding="utf-8")
    total_dur = float(words[-1]["end"]) - float(words[0]["start"])
    return len(chunks), total_dur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", type=Path, help="台本 JSON (chapters[].text)")
    ap.add_argument("--words", type=Path, help="whisper _words.json")
    ap.add_argument("--out", type=Path, help="出力 SRT")
    ap.add_argument("--kind", choices=["history", "psych", "shorts", "otona_shorts"],
                    help="ショートカット用")
    ap.add_argument("--index", help="ショートカット用 3桁 index")
    ap.add_argument("--all", action="store_true",
                    help="--kind 指定下の audio フォルダ内の全 _words.json を一括再生成")
    args = ap.parse_args()

    KIND_PATHS = {
        "history": ("youtube/history_v2/scripts/long_{i}.json",
                    "youtube/history_v2/audio/{i}_words.json",
                    "youtube/history_v2/audio/{i}.srt"),
        "psych":   ("youtube/psych_v2/scripts/long_{i}.json",
                    "youtube/psych_v2/audio/{i}_words.json",
                    "youtube/psych_v2/audio/{i}.srt"),
        "shorts":  ("youtube/shorts_v2/scripts/short_{i}.json",
                    "youtube/shorts_v2/audio/{i}_words.json",
                    "youtube/shorts_v2/audio/{i}.srt"),
        "otona_shorts": ("youtube/otona_shorts_v2/scripts/short_{i}.json",
                         "youtube/otona_shorts_v2/audio/{i}_words.json",
                         "youtube/otona_shorts_v2/audio/{i}.srt"),
    }

    if args.all and args.kind:
        sp_tpl, wp_tpl, op_tpl = KIND_PATHS[args.kind]
        audio_dir = ROOT / sp_tpl.split("/scripts/")[0] / "audio"
        words = sorted(audio_dir.glob("*_words.json"))
        for wj in words:
            idx = wj.stem.replace("_words", "")
            sp = ROOT / sp_tpl.format(i=idx)
            op = ROOT / op_tpl.format(i=idx)
            if not sp.exists():
                print(f"  skip {idx}: no script")
                continue
            n, dur = refine(sp, wj, op)
            avg = dur / n if n else 0
            print(f"  {args.kind} {idx}: {n} cues, avg {avg:.2f}s/cue")
        return 0

    if args.kind and args.index:
        sp_tpl, wp_tpl, op_tpl = KIND_PATHS[args.kind]
        sp = ROOT / sp_tpl.format(i=args.index)
        wp = ROOT / wp_tpl.format(i=args.index)
        op = ROOT / op_tpl.format(i=args.index)
    elif args.script and args.words and args.out:
        sp, wp, op = args.script, args.words, args.out
    else:
        ap.print_help()
        return 1

    n, dur = refine(sp, wp, op)
    avg = dur / n if n else 0
    print(f"  {op.name}: {n} cues, avg {avg:.2f}s/cue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
