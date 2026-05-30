#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""指定 idx の pipeline.mjs を順次実行する wrapper (Bash 動的構文禁止回避用)。

使い方:
  python scripts/_build_videos_seq.py --kind history --idxs 031,032,033
  python scripts/_build_videos_seq.py --kind psych --idxs 013,014
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent


def build_one(kind: str, idx: str) -> bool:
    if kind == 'history':
        pipeline = ROOT / 'youtube' / 'history_v2' / 'pipeline.mjs'
        env_name = 'LONG_INDEX'
    elif kind == 'psych':
        pipeline = ROOT / 'youtube' / 'psych_v2' / 'pipeline.mjs'
        env_name = 'PSYCH_INDEX'
    else:
        raise ValueError(f'unknown kind: {kind}')
    env = os.environ.copy()
    env[env_name] = idx
    print(f'\n[build] {kind}/{idx} start (ffmpeg encode 30-60min)')
    t0 = time.time()
    try:
        proc = subprocess.run(['node', str(pipeline)], env=env, cwd=str(ROOT),
                              capture_output=False, timeout=4200)  # 70min timeout
    except subprocess.TimeoutExpired:
        print(f'[build] {kind}/{idx} TIMEOUT after 70min')
        return False
    dt = time.time() - t0
    success = (proc.returncode == 0)
    print(f'[build] {kind}/{idx} {"OK" if success else "FAIL"}: rc={proc.returncode} ({dt/60:.1f}min)')
    return success


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', choices=['history', 'psych'], required=True)
    ap.add_argument('--idxs', required=True, help='comma-separated idx list (e.g. 031,032)')
    args = ap.parse_args()
    idxs = [s.strip() for s in args.idxs.split(',') if s.strip()]
    print(f'[build_seq] kind={args.kind} count={len(idxs)} idxs={idxs}')
    ok, fail = 0, 0
    for idx in idxs:
        try:
            if build_one(args.kind, idx):
                ok += 1
            else:
                fail += 1
        except KeyboardInterrupt:
            print('\n[STOP] interrupted')
            break
        except Exception as e:
            fail += 1
            print(f'[FAIL] {idx}: {e}')
    print(f'\n=== Done: ok={ok} fail={fail} ===')


if __name__ == '__main__':
    main()
