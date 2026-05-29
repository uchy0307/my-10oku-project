#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_cycle.py
==============
日次量産サイクル オーケストレータ。
タスクスケジューラから毎日1回実行 → 全自動でコンテンツ生成・投稿。

ステップ:
  1. 台本ストック確認 → 不足なら Gemini で補充（歴史/大人/ショート）
  2. 未音声化の台本を edge-tts で音声生成
  3. 音声に対して whisper で SRT 字幕生成
  4. 各チャンネルで未投稿の次の本数を pipeline.mjs で動画化＋YT投稿
  5. note 添付処理（未添付なら追加）
  6. messages.json に日次レポート書き込み

冪等: 既存ファイルがあるステップはスキップ。
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
JST = timezone(timedelta(hours=9))


# ======== EMERGENCY STOP (2026-05-27) ========
# 設置理由: note #109/#111/#112 違反 (1本500円表記・本文古い) で削除
# 解除方法: rm C:\Users\user\Documents\10oku-project\.EMERGENCY_STOP_DAILY_CYCLE
_EMERGENCY = ROOT / ".EMERGENCY_STOP_DAILY_CYCLE"
if _EMERGENCY.exists():
    print(f"[EMERGENCY_STOP] daily_cycle halted by {_EMERGENCY}")
    try:
        print(_EMERGENCY.read_text(encoding='utf-8', errors='replace')[:500])
    except Exception:
        pass
    sys.exit(0)
# =============================================


def now_str():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print(f"[{now_str()}] {msg}")


def env_load():
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def run(cmd, timeout=3600):
    """Run subprocess, return (returncode, stdout_tail)"""
    log(f"$ {' '.join(str(c) for c in cmd[:6])}{'...' if len(cmd)>6 else ''}")
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(ROOT),
        )
        tail = (r.stdout or "")[-300:] + (r.stderr or "")[-200:]
        return r.returncode, tail
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -2, str(e)


def count_files(kind):
    """Return (scripts_count, audio_count, srt_count) for a pipeline kind."""
    d = ROOT / "youtube" / f"{kind}_v2"
    s = len(list((d / "scripts").glob("*.json"))) if (d / "scripts").exists() else 0
    a = len(list((d / "audio").glob("*.mp3"))) if (d / "audio").exists() else 0
    srt = len(list((d / "audio").glob("*.srt"))) if (d / "audio").exists() else 0
    return s, a, srt


def append_message(title, body):
    p = SCRIPTS / "messages.json"
    try:
        msgs = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except Exception:
        msgs = []
    msgs.append({
        "id": f"daily_{int(datetime.now(JST).timestamp())}",
        "ts": datetime.now(JST).isoformat(),
        "title": title,
        "body": body,
        "read": False,
        "auto": True,
    })
    p.write_text(json.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")


# =========================================================================
# Steps
# =========================================================================

def step_scripts():
    """1. 台本ストック確保（既に30本以上ならスキップ）"""
    report = []
    for kind, target in [("history", 30), ("psych", 30), ("history_shorts", 30), ("otona_shorts", 30)]:
        s_dir_kind = {
            "history": "history_v2",
            "psych": "psych_v2",
            "history_shorts": "shorts_v2",
            "otona_shorts": "otona_shorts_v2",
        }[kind]
        s_count = len(list((ROOT / "youtube" / s_dir_kind / "scripts").glob("*.json")))
        if s_count >= target:
            report.append(f"  {kind}: {s_count} (sufficient)")
            continue
        need = target - s_count
        log(f"need {need} more {kind} scripts")
        rc, tail = run([sys.executable, str(SCRIPTS / "generate_stock_scripts.py"),
                        "--kind", kind, "--count", str(need)], timeout=7200)
        after = len(list((ROOT / "youtube" / s_dir_kind / "scripts").glob("*.json")))
        report.append(f"  {kind}: {s_count} → {after} (rc={rc})")
    return "\n".join(report)


def step_audio():
    """2. 未音声化を edge-tts で生成 (長尺+ショート 全4種)"""
    report = []
    kinds = [
        ("history",       "history_v2"),
        ("psych",         "psych_v2"),
        ("history_shorts", "shorts_v2"),
        ("otona_shorts",  "otona_shorts_v2"),
    ]
    for kind, s_dir in kinds:
        scripts_dir = ROOT / "youtube" / s_dir / "scripts"
        audio_dir   = ROOT / "youtube" / s_dir / "audio"
        s_count = len(list(scripts_dir.glob("*.json"))) if scripts_dir.exists() else 0
        a_count = len(list(audio_dir.glob("*.mp3"))) if audio_dir.exists() else 0
        if a_count >= s_count:
            report.append(f"  {kind}: audio {a_count}/{s_count} (sufficient)")
            continue
        log(f"generating {kind} audio")
        rc, _ = run([sys.executable, str(SCRIPTS / "gen_audio_for_scripts.py"),
                     "--kind", kind], timeout=7200)
        after = len(list(audio_dir.glob("*.mp3"))) if audio_dir.exists() else 0
        report.append(f"  {kind}: audio {a_count} → {after} (rc={rc})")
    return "\n".join(report)


def step_whisper():
    """3. 朝Cron では「本日 upload する分だけ」whisper をやる。
    残りは別 cron (UchyNightlyWhisper, 23:00) が tiny モデルで一括処理する。
    本日 upload 想定: 歴史3本 + 大人3本 = 上限6本だけ"""
    report = []
    UPLOAD_TARGETS_PER_KIND = 4  # 安全マージン込み
    for kind, sub in [("history", "history_v2"), ("psych", "psych_v2")]:
        audio_dir = ROOT / "youtube" / sub / "audio"
        if not audio_dir.exists():
            continue
        # SRT 無しの mp3 を上位N件だけ抽出 (index 昇順)
        mp3s = sorted(audio_dir.glob("*.mp3"))
        missing = [m for m in mp3s if not (audio_dir / f"{m.stem}.srt").exists()]
        targets = missing[:UPLOAD_TARGETS_PER_KIND]
        if not targets:
            report.append(f"  {kind}: whisper sufficient ({len(mp3s)-len(missing)}/{len(mp3s)} SRT exists)")
        else:
            log(f"running whisper for {kind} ({len(targets)} files: {[t.name for t in targets]})")
            for t in targets:
                rc, _ = run([sys.executable, str(SCRIPTS / "whisper_subtitle_gen.py"),
                             "--audio", str(t)], timeout=1200)
                report.append(f"  {kind} {t.name}: rc={rc}")
        # refine: 原稿テキスト + whisper タイミング合成 (誤認識補正)
        log(f"refining SRT for {kind}")
        rc2, _ = run([sys.executable, str(SCRIPTS / "refine_srt.py"),
                      "--kind", kind, "--all"], timeout=600)
        report.append(f"  {kind}: refine_srt rc={rc2}")
    return "\n".join(report)


def step_upload(daily_count_history=3, daily_count_psych=3, daily_count_shorts=5):
    """4. 動画化＋投稿（pipeline.mjs 呼び出し）
    現状は build_*_3.bat 等を呼ぶ簡易版。各 BAT 内で『次の未投稿』を選ぶ。"""
    report = []
    # 大人系 (psych, otona_shorts) は OTONA_YOUTUBE_REFRESH_TOKEN 必須に変更したため、
    # トークン未設定の現状では除外。設定後に再有効化のこと。
    bats = [
        ("history", "build_history_3.bat"),
        ("history_shorts", "build_history_shorts_5.bat"),
    ]
    if os.environ.get("OTONA_YOUTUBE_REFRESH_TOKEN"):
        bats.append(("psych", "build_otona_3.bat"))
        bats.append(("otona_shorts", "build_otona_shorts_5.bat"))
    else:
        report.append("  psych/otona_shorts: skipped (OTONA_YOUTUBE_REFRESH_TOKEN not set, prevents history-channel mis-upload)")
    for label, bat in bats:
        bp = SCRIPTS / bat
        if not bp.exists():
            report.append(f"  {label}: {bat} not found")
            continue
        # Daily cron は visible window 不要 → cmd /c 直接実行
        rc, tail = run(["cmd.exe", "/c", str(bp)], timeout=10800)
        report.append(f"  {label}: rc={rc}")
    return "\n".join(report)


def step_note_attachments(max_items=20):
    """5. note 添付未済の20件追加（短時間で完了）"""
    log(f"running note add-attachments (max={max_items})")
    rc, _ = run(["node", str(ROOT / "note-auto" / "add-attachments-only.mjs"),
                 f"--max={max_items}"], timeout=3600)
    # Count attached after
    try:
        q = json.loads((ROOT / "note-auto" / "queue.json").read_text(encoding="utf-8"))
        att = sum(1 for it in q.get("items", []) if it.get("attachmentCount", 0) >= 3)
        return f"  note attached: {att}/200 (rc={rc})"
    except Exception as e:
        return f"  note attach error: {e}"


# =========================================================================
# Main
# =========================================================================

def step_restart_button_server():
    """0. button server を最新コードで再起動（admin権限の本cronでなら kill 可）"""
    try:
        # Find PID listening on 7373
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-NetTCPConnection -LocalPort 7373 -State Listen -EA SilentlyContinue).OwningProcess"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        pid = (r.stdout or "").strip().split("\n")[0].strip()
        if pid and pid.isdigit():
            subprocess.run(["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force -EA Continue"], timeout=10)
        # Restart via scheduled task
        subprocess.run(["schtasks", "/Run", "/TN", "UchyButtonServer"], timeout=10)
        time.sleep(3)
        return f"  button server restarted (killed PID {pid or 'none'})"
    except Exception as e:
        return f"  restart failed: {e}"


def step_disk_cleanup():
    """毎日 daily_cycle 開始時に必ず自動掃除. ディスク Free 確保."""
    import shutil as _sh
    before = _sh.disk_usage("C:").free / 1024 / 1024 / 1024
    rc, _ = run([sys.executable, str(SCRIPTS / "auto_disk_cleanup.py")], timeout=180)
    after = _sh.disk_usage("C:").free / 1024 / 1024 / 1024
    return f"  before={before:.2f}GB → after={after:.2f}GB (rc={rc})"


def main():
    env_load()
    log("=== Daily Cycle START ===")
    report_lines = [f"# 日次サイクル {now_str()}"]

    steps = [
        ("-1. ディスク自動掃除", step_disk_cleanup),
        ("0. button server 再起動", step_restart_button_server),
        ("1. 台本ストック確保", step_scripts),
        ("2. 音声生成", step_audio),
        ("3. 字幕同期(whisper)", step_whisper),
        ("4. 動画化＋YT投稿", step_upload),
        ("5. note添付(20件)", step_note_attachments),
    ]

    for name, fn in steps:
        log(f"--- {name} ---")
        try:
            result = fn()
            report_lines.append(f"\n## {name}\n{result}")
        except Exception as e:
            tb = traceback.format_exc()[-500:]
            log(f"ERROR in {name}: {e}")
            report_lines.append(f"\n## {name}\nERROR: {e}\n```\n{tb}\n```")

    # 最終状態スナップショット
    h = count_files("history")
    p = count_files("psych")
    s = count_files("shorts")
    snapshot = (
        f"\n## 終了時刻 {now_str()}\n"
        f"- 歴史: scripts={h[0]} audio={h[1]} srt={h[2]}\n"
        f"- 大人: scripts={p[0]} audio={p[1]} srt={p[2]}\n"
        f"- ショート: scripts={s[0]} audio={s[1]} srt={s[2]}\n"
    )
    report_lines.append(snapshot)

    full_report = "\n".join(report_lines)
    # ファイルにも残す
    log_dir = SCRIPTS / "logs"
    log_dir.mkdir(exist_ok=True)
    today = datetime.now(JST).strftime("%Y%m%d")
    (log_dir / f"daily_{today}.log").write_text(full_report, encoding="utf-8")

    # スマホアプリ用通知
    append_message(
        f"📅 日次サイクル完了 {now_str()[:10]}",
        full_report[:1500]
    )

    log("=== Daily Cycle END ===")


if __name__ == "__main__":
    main()
