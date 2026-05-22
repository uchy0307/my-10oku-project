#!/usr/bin/env -S python3 -u
"""
local_edge_tts_history_poll.py — 自動ポーラー (Windows Task Scheduler 毎時起動想定)

Flow:
  1. git pull --ff-only origin main   (history_v2/scripts/ の最新化)
  2. youtube/history_v2/scripts/long_*.json を列挙
  3. youtube/history_v2/audio/{idx}.mp3 が無いものを対象に edge-tts 実行
  4. 生成された mp3 + srt を git add → commit → push (origin main 直接)

完全自動化・完全無料・ユーザー操作ゼロ。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "youtube" / "history_v2" / "scripts"
AUDIO_DIR = REPO_ROOT / "youtube" / "history_v2" / "audio"

# 起動時間ログ (デバッグ用)
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "local_edge_tts_history_poll.log"


def log(msg: str) -> None:
    line = f"[poll] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(REPO_ROOT), *args]
    log("$ " + " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.stdout.strip():
        log(res.stdout.strip())
    if res.stderr.strip():
        log("(stderr) " + res.stderr.strip())
    if check and res.returncode != 0:
        raise RuntimeError(f"git failed rc={res.returncode}: {' '.join(args)}")
    return res


def discover_pending() -> list[str]:
    """audio/{idx}.mp3 が存在しない long_*.json の index を返す"""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    pending: list[str] = []
    for jf in sorted(SCRIPTS_DIR.glob("long_*.json")):
        m = re.match(r"long_(\d{3})\.json$", jf.name)
        if not m:
            continue
        idx = m.group(1)
        if not (AUDIO_DIR / f"{idx}.mp3").exists():
            pending.append(idx)
    return pending


def synth_one(long_index: str) -> bool:
    """edge-tts で一本生成。成功時 True。"""
    from local_edge_tts_history import run_for_long_index  # type: ignore

    try:
        run_for_long_index(long_index)
        return True
    except Exception as e:
        log(f"synth_one FAILED idx={long_index}: {e!r}")
        return False


def main() -> int:
    log("=== run start ===")
    if not shutil.which("git"):
        log("FATAL: git not found on PATH")
        return 2

    # 1. pull (失敗してもローカルで処理続行)
    try:
        _git("fetch", "origin", check=False)
        _git("pull", "--ff-only", "origin", "main", check=False)
    except Exception as e:
        log(f"pull warning: {e}")

    # 2. discover
    pending = discover_pending()
    log(f"pending indexes: {pending}")
    if not pending:
        log("nothing to do.")
        log("=== run end ===")
        return 0

    # 3. synth (1 ジョブ 1 ファイル / cron 1 周回で複数 OK)
    succeeded: list[str] = []
    for idx in pending:
        if synth_one(idx):
            succeeded.append(idx)

    if not succeeded:
        log("no successful synth this round.")
        log("=== run end ===")
        return 0

    # 4. git commit & push
    # add は audio/{idx}.{mp3,srt} のみ
    to_add: list[str] = []
    for idx in succeeded:
        for ext in ("mp3", "srt"):
            p = AUDIO_DIR / f"{idx}.{ext}"
            if p.exists():
                to_add.append(str(p.relative_to(REPO_ROOT)).replace("\\", "/"))
    if not to_add:
        log("no new files to add (synth produced nothing).")
        return 0

    _git("add", *to_add)
    msg = f"chore(history-v2): add edge-tts narration audio for {','.join(succeeded)} [skip ci]"
    res = _git("commit", "-m", msg, check=False)
    if res.returncode != 0:
        log("commit had no changes (already committed?).")
    else:
        # push (失敗時はリトライ 1 回)
        push_res = _git("push", "origin", "HEAD:main", check=False)
        if push_res.returncode != 0:
            log("push retry after pull --rebase ...")
            _git("pull", "--rebase", "origin", "main", check=False)
            _git("push", "origin", "HEAD:main", check=False)

    log("=== run end ===")
    return 0


if __name__ == "__main__":
    # Allow `import local_edge_tts_history` from same dir
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
