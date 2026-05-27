#!/usr/bin/env python3
"""
うっちー様プラットフォーム 死活監視スクリプト
3時間ごとに実行。異常時のみ詳細出力。
"""

import urllib.request
import urllib.error
import socket
import json
import datetime
import sys

# JST (UTC+9)
def now_jst():
    utc = datetime.datetime.utcnow()
    jst = utc + datetime.timedelta(hours=9)
    return jst.strftime('%H:%M')

def check_http(url, timeout=10):
    """HTTP GETでステータスコードを返す。DNS失敗は -1, タイムアウトは -2, その他エラーは -3"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; UchyMonitor/1.0)'
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), None
    except urllib.error.HTTPError as e:
        return e.code, None
    except socket.gaierror as e:
        return -1, f"DNS失敗: {e}"
    except socket.timeout:
        return -2, "タイムアウト (10s)"
    except Exception as e:
        return -3, str(e)

def check_api_with_actions(url, timeout=10):
    """pc.uchy0307.uk/api: ステータスコードとactions数を返す"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; UchyMonitor/1.0)'
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = r.getcode()
            body = r.read().decode('utf-8', errors='replace')
            try:
                data = json.loads(body)
                actions = data.get('actions', {})
                count = len(actions) if isinstance(actions, dict) else (len(actions) if isinstance(actions, list) else 0)
                return code, count, None
            except json.JSONDecodeError:
                return code, 0, "JSONパース失敗"
    except urllib.error.HTTPError as e:
        return e.code, 0, None
    except socket.gaierror as e:
        return -1, 0, f"DNS失敗: {e}"
    except socket.timeout:
        return -2, 0, "タイムアウト (10s)"
    except Exception as e:
        return -3, 0, str(e)

def is_ok_code(code):
    """200-299 or 301/302 (リダイレクト) は正常とみなす"""
    return 200 <= code < 300 or code in (301, 302, 303, 307, 308)

def main():
    time_str = now_jst()
    errors = []

    # --- 1. pc.uchy0307.uk/api ---
    api_code, actions_count, api_err = check_api_with_actions("https://pc.uchy0307.uk/api")
    if api_code != 200 or actions_count < 10:
        if api_code == -1:
            errors.append(f"- pc.uchy0307.uk/api: DNS解決失敗 → Cloudflare Tunnel/ドメイン障害")
        elif api_code == -2:
            errors.append(f"- pc.uchy0307.uk/api: タイムアウト → ローカルPC OFF または cloudflared 落ち")
        elif api_code == 403:
            errors.append(f"- pc.uchy0307.uk/api: HTTP 403 → Cloudflare アクセス拒否 (IPブロック or 設定変更)")
        elif api_code >= 500:
            errors.append(f"- pc.uchy0307.uk/api: HTTP {api_code} → ローカルPC OFF または cloudflared 落ち")
        elif is_ok_code(api_code) and actions_count < 10:
            errors.append(f"- pc.uchy0307.uk/api: HTTP {api_code} だが actions={actions_count}個 (10個未満) → ボタン設定要確認")
        else:
            errors.append(f"- pc.uchy0307.uk/api: HTTP {api_code}{(' / ' + api_err) if api_err else ''}")

    # --- 2-6. 各Webサービス ---
    services = [
        ("YouTube @Japanese.Samurai.Channel", "https://www.youtube.com/@Japanese.Samurai.Channel"),
        ("YouTube @Otona_Psychology",         "https://www.youtube.com/@Otona_Psychology"),
        ("note.com/happy_happy_4649",          "https://note.com/happy_happy_4649"),
        ("toi-suite.vercel.app",               "https://toi-suite.vercel.app/"),
        ("LP (uchy-lp.pages.dev)",             "https://main.uchy-lp.pages.dev"),
    ]

    for name, url in services:
        code, err = check_http(url)
        if code == -1:
            errors.append(f"- {name}: DNS解決失敗 → ドメイン消滅 or DNS障害")
        elif code == -2:
            errors.append(f"- {name}: タイムアウト → サービス無応答")
        elif code == 403:
            # YouTube/Note は bot 検出で 403 を返すことがある → DNS解決できていれば警告のみ
            try:
                socket.gethostbyname(url.split('/')[2])
                # DNS OK なら bot検出の可能性が高い → 警告なし (正常扱い)
                pass
            except socket.gaierror:
                errors.append(f"- {name}: DNS解決失敗 (403+DNS FAIL)")
        elif not is_ok_code(code) and code > 0:
            errors.append(f"- {name}: HTTP {code}{(' / ' + err) if err else ''}")
        elif code < 0:
            errors.append(f"- {name}: 接続エラー {code}{(' / ' + err) if err else ''}")

    # --- 出力 ---
    if not errors:
        print(f"✅ 全6サービス稼働中 ({time_str} JST チェック)")
    else:
        print(f"⚠ 異常検知 ({time_str} JST)")
        for e in errors:
            print(e)

    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
