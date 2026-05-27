#!/usr/bin/env python3
"""
3時間ごとの死活監視ループ (タイムスタンプ管理版)
監視ループから 20分ごとに呼ばれる。
前回チェックから 3時間(10800秒)以上経過していたら実際のチェックを実行して出力。
未到達なら無出力（Monitor がスリープせずに繰り返す）。
"""

import os
import time
import subprocess
import sys

STATE_FILE = "/tmp/uchy_health_last_check"
INTERVAL   = 10800  # 3時間

now  = time.time()
try:
    last = float(open(STATE_FILE).read().strip())
except Exception:
    last = 0.0

if now - last >= INTERVAL:
    result = subprocess.run(
        [sys.executable,
         "/home/user/my-10oku-project/scripts/health_check.py"],
        capture_output=True, text=True
    )
    output = result.stdout.strip()
    if output:
        print(output, flush=True)
    # エラー出力があれば表示
    if result.stderr.strip():
        print(f"[stderr] {result.stderr.strip()}", flush=True)
    # 次の基準時刻を保存（実行時刻で更新）
    with open(STATE_FILE, "w") as f:
        f.write(str(now))
# 未到達時は無出力で終了
