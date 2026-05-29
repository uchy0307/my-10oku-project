#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Gemini API key の実動作確認。値は出力しない。
generativelanguage.googleapis.com の models endpoint を叩いて 200 が返るか確認。
"""
import sys, json, urllib.request, urllib.parse, urllib.error
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


def check_key(label, key):
    if not key:
        print(f'{label:18s}: SKIP (empty)')
        return False
    url = f'https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(key)}'
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            body = json.loads(r.read().decode('utf-8'))
        n_models = len(body.get('models', []))
        print(f'{label:18s}: OK ({n_models} models available)')
        return True
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode('utf-8'))
            msg = err.get('error', {}).get('message', '')[:120]
            code = err.get('error', {}).get('status', '')
        except Exception:
            msg, code = 'parse-fail', ''
        print(f'{label:18s}: FAIL HTTP {e.code} [{code}] {msg}')
        return False
    except Exception as e:
        print(f'{label:18s}: FAIL {type(e).__name__}: {e}')
        return False


def main():
    env = load_env()
    ok1 = check_key('GEMINI_API_KEY', env.get('GEMINI_API_KEY', ''))
    ok2 = check_key('GEMINI_API_KEY_FREE', env.get('GEMINI_API_KEY_FREE', ''))

    if ok1 and ok2:
        print('--> BOTH OK')
        sys.exit(0)
    else:
        print('--> ONE OR MORE FAILED')
        sys.exit(1)


if __name__ == '__main__':
    main()
