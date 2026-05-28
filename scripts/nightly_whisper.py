#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nightly_whisper.py
夜間に whisper SRT を全 mp3 に対し生成し、refine_srt で原稿テキスト合成まで実行。

daily_cycle (朝Cron) は upload 最優先のため whisper は最低数本しかやらない。
本スクリプトが寝てる間に追いつかせる。

Usage (Task Scheduler 経由):
  python scripts/nightly_whisper.py
"""
import subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
JST = timezone(timedelta(hours=9))


def log(msg):
    print(f"[{datetime.now(JST).strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    log("=== Nightly Whisper START ===")
    targets = [
        ("history",        ROOT / "youtube" / "history_v2" / "audio"),
        ("psych",          ROOT / "youtube" / "psych_v2" / "audio"),
        ("history_shorts", ROOT / "youtube" / "shorts_v2" / "audio"),
        ("otona_shorts",   ROOT / "youtube" / "otona_shorts_v2" / "audio"),
    ]
    for kind, audio_dir in targets:
        if not audio_dir.exists():
            log(f"  {kind}: dir not found, skip")
            continue
        mp3s = list(audio_dir.glob("*.mp3"))
        srts = list(audio_dir.glob("*.srt"))
        missing = len(mp3s) - len(srts)
        log(f"  {kind}: {missing} files need whisper ({len(srts)}/{len(mp3s)} done)")
        if missing == 0:
            continue
        # whisper_subtitle_gen.py が既存スキップするので --dir で一括 OK
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "whisper_subtitle_gen.py"),
             "--dir", str(audio_dir), "--model", "tiny"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        log(f"  {kind} whisper rc={r.returncode}")
    # refine_srt も走らせる (long-form のみ。shorts は ASS 直接)
    for kind in ["history", "psych"]:
        log(f"  refine_srt {kind}")
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "refine_srt.py"), "--kind", kind, "--all"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        log(f"  refine_srt {kind} rc={r.returncode}")
    log("=== Nightly Whisper END ===")


if __name__ == "__main__":
    main()
