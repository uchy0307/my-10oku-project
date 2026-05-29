#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.env の必須キーが揃っているか・長さが妥当か診断。
値は出力しない (長さと先頭3文字の prefix だけ)。
"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ENV_PATH = Path(r'C:\Users\user\Documents\10oku-project\.env')


def load_env():
    env = {}
    for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


EXPECTED = [
    # (key, expected_prefix, min_len, max_len, description)
    # 注: Gemini key は2025-2026年に新形式(AQ...)が登場。prefix チェックは廃止して長さのみ。
    ('GEMINI_API_KEY',                 '',       30, 120,  'Gemini #1'),
    ('GEMINI_API_KEY_FREE',            '',       30, 120,  'Gemini #2'),
    ('YOUTUBE_CLIENT_ID',              '',       40, 80,   'OAuth Client ID (.apps.googleusercontent.com で終わる)'),
    ('YOUTUBE_CLIENT_SECRET',          'GOCSPX', 30, 50,   'OAuth Client Secret'),
    ('YOUTUBE_REFRESH_TOKEN',          '1//',    60, 150,  'samurai refresh_token'),
    ('OTONA_YOUTUBE_REFRESH_TOKEN',    '1//',    60, 150,  'otona refresh_token'),
]


def main():
    env = load_env()
    all_ok = True
    for key, prefix, min_len, max_len, desc in EXPECTED:
        v = env.get(key, '')
        n = len(v)
        ok = True
        notes = []

        if n == 0:
            ok = False
            notes.append('EMPTY')
        else:
            if prefix and not v.startswith(prefix):
                ok = False
                notes.append(f'prefix mismatch (expected "{prefix}...")')
            if n < min_len:
                ok = False
                notes.append(f'too short (got {n}, min {min_len})')
            if n > max_len * 2:
                ok = False
                notes.append(f'too long (got {n}, max ~{max_len})')

        mark = 'OK  ' if ok else 'FAIL'
        # OAuth Client ID の特別チェック
        if key == 'YOUTUBE_CLIENT_ID' and v and not v.endswith('.apps.googleusercontent.com'):
            ok = False
            notes.append('does not end with .apps.googleusercontent.com')
            mark = 'FAIL'

        if not ok:
            all_ok = False

        notes_str = (' | ' + '; '.join(notes)) if notes else ''
        print(f'{mark}  {key:30s} len={n:4d}  ({desc}){notes_str}')

    print()
    if all_ok:
        print('--> ALL 6 KEYS VALID FORMAT (中身の有効性は _oauth_test.py で別途確認)')
    else:
        print('--> NEEDS FIX')


if __name__ == '__main__':
    main()
