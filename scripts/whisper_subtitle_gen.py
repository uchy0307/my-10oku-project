#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
whisper_subtitle_gen.py
=======================
Whisper を使って音声ファイル（.mp3）から「単語ごとに発話タイミング」付きの SRT 字幕を生成する。

使い方:
    # 1本だけ処理
    python whisper_subtitle_gen.py --audio path/to/001.mp3

    # フォルダ内の全mp3を処理
    python whisper_subtitle_gen.py --dir path/to/audio_folder

    # 全シリーズ一括（psych_v2 + history_v2 + shorts_v2）
    python whisper_subtitle_gen.py --all

依存:
    openai-whisper （pip install openai-whisper）
    ffmpeg （PATH に通っていること、Windows 標準 or scoop install ffmpeg）

出力:
    入力 mp3 と同じ場所に「{元名前}.srt」と「{元名前}_words.json」を生成。
    SRT は ffmpeg で動画に焼き込める形式。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# ---- 設定 ----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent  # 10oku-project/

# Whisper モデル: tiny, base, small, medium, large
# - tiny: 高速、精度低い、約 75MB
# - base: 速い、まあまあ精度、約 150MB（推奨）
# - small: 中速、高精度、約 500MB
# - medium: 遅い、より高精度、約 1.5GB
# - large: 最高精度、約 3GB
DEFAULT_MODEL = "tiny"  # base → tiny に変更 (3倍速。テキスト精度は refine_srt.py が原稿で補正、timingだけ重要)

# 字幕の言語（日本語ナレーション固定）
LANG = "ja"

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def format_timestamp(seconds: float) -> str:
    """秒数を SRT 形式の HH:MM:SS,mmm に変換"""
    millis = int(round(seconds * 1000))
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def process_one(mp3_path: Path, model_name: str = DEFAULT_MODEL) -> bool:
    """1本の mp3 を処理して .srt と .words.json を出力"""
    try:
        import whisper
    except ImportError:
        logging.error(
            "openai-whisper が入っていません。"
            "先に setup_whisper.bat を実行してください。"
        )
        return False

    if not mp3_path.exists():
        logging.error(f"音声ファイルが見つかりません: {mp3_path}")
        return False

    srt_out = mp3_path.with_suffix(".srt")
    json_out = mp3_path.with_name(mp3_path.stem + "_words.json")

    if srt_out.exists():
        logging.info(f"既に存在するためスキップ: {srt_out}")
        return True

    logging.info(f"処理開始: {mp3_path.name} (Whisper モデル: {model_name})")
    model = whisper.load_model(model_name)
    result = model.transcribe(
        str(mp3_path),
        language=LANG,
        word_timestamps=True,
        verbose=False,
    )

    # 単語レベル JSON
    words_data = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            words_data.append(
                {
                    "word": w.get("word", "").strip(),
                    "start": round(w.get("start", 0), 3),
                    "end": round(w.get("end", 0), 3),
                }
            )

    with json_out.open("w", encoding="utf-8") as f:
        json.dump(words_data, f, ensure_ascii=False, indent=2)
    logging.info(f"  単語タイミング保存: {json_out.name} ({len(words_data)} 個)")

    # SRT 生成（短いフレーズ単位で区切る、3〜5単語ずつ）
    srt_lines = []
    idx = 1
    chunk_size = 5  # 1字幕あたり最大単語数
    chunks = [
        words_data[i : i + chunk_size] for i in range(0, len(words_data), chunk_size)
    ]
    for chunk in chunks:
        if not chunk:
            continue
        start = chunk[0]["start"]
        end = chunk[-1]["end"]
        text = "".join(w["word"] for w in chunk).strip()
        if not text:
            continue
        srt_lines.append(
            f"{idx}\n{format_timestamp(start)} --> {format_timestamp(end)}\n{text}\n"
        )
        idx += 1

    srt_text = "\n".join(srt_lines)
    with srt_out.open("w", encoding="utf-8") as f:
        f.write(srt_text)
    logging.info(f"  SRT 字幕保存: {srt_out.name} ({idx - 1} 字幕)")

    return True


def process_dir(dir_path: Path, model_name: str = DEFAULT_MODEL) -> int:
    """フォルダ内の全 mp3 を処理"""
    if not dir_path.exists() or not dir_path.is_dir():
        logging.error(f"フォルダが見つかりません: {dir_path}")
        return 0

    mp3_files = sorted(dir_path.rglob("*.mp3"))
    logging.info(f"対象 mp3: {len(mp3_files)} 本（フォルダ: {dir_path}）")

    ok = 0
    for mp3 in mp3_files:
        if process_one(mp3, model_name):
            ok += 1
    return ok


def process_all(model_name: str = DEFAULT_MODEL) -> dict:
    """psych_v2 + history_v2 + shorts_v2 の全 mp3 を処理"""
    targets = [
        ROOT / "youtube" / "psych_v2" / ".work",
        ROOT / "youtube" / "history_v2" / "audio",
        ROOT / "youtube" / "shorts_v2",
    ]
    results = {}
    for tgt in targets:
        if tgt.exists():
            count = process_dir(tgt, model_name)
            results[str(tgt.relative_to(ROOT))] = count
        else:
            results[str(tgt.relative_to(ROOT))] = "（フォルダなし）"
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Whisper で mp3 から単語タイミング付き SRT を生成"
    )
    parser.add_argument("--audio", type=Path, help="単一の mp3 ファイル")
    parser.add_argument("--dir", type=Path, help="mp3 を含むフォルダ")
    parser.add_argument(
        "--all", action="store_true", help="psych_v2 + history_v2 + shorts_v2 全部"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper モデル（推奨: base）",
    )

    args = parser.parse_args()

    if args.audio:
        ok = process_one(args.audio, args.model)
        sys.exit(0 if ok else 1)
    elif args.dir:
        count = process_dir(args.dir, args.model)
        logging.info(f"完了: {count} 本処理")
        sys.exit(0)
    elif args.all:
        results = process_all(args.model)
        logging.info("=== 全体結果 ===")
        for k, v in results.items():
            logging.info(f"  {k}: {v}")
        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
