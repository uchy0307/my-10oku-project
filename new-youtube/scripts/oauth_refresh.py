#!/usr/bin/env -S python3 -u
"""
oauth_refresh.py — Google OAuth2 refresh_token -> access_token 取得 汎用モジュール

YouTube Data API / Drive / Gmail 等の任意の Google API で使える。
標準ライブラリ (urllib) のみで実装、追加依存無し。

Usage (import):
    from new_youtube.scripts.oauth_refresh import refresh_access_token
    tok = refresh_access_token(client_id, client_secret, refresh_token)
    # tok = {"access_token": "...", "expires_in": 3599, "scope": "...", "token_type": "Bearer"}

Usage (CLI):
    python oauth_refresh.py \\
        --client-id ID --client-secret SECRET --refresh-token TOKEN

    あるいは env 経由:
        GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN

Notes:
  - リトライ無し。失敗時は即例外
  - scope は refresh_token 発行時に紐付け済みのため body で送らない（OAuth2 仕様）
  - 標準的な Google token endpoint: https://oauth2.googleapis.com/token
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


TOKEN_URL = "https://oauth2.googleapis.com/token"


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    token_url: str = TOKEN_URL,
    timeout: float = 30.0,
) -> dict:
    """refresh_token から新しい access_token を取得する。

    Args:
        client_id:     OAuth クライアント ID
        client_secret: OAuth クライアントシークレット
        refresh_token: 事前取得済みのリフレッシュトークン
        token_url:     差し替え用（テスト時のみ）
        timeout:       秒

    Returns:
        Google token endpoint の JSON レスポンス dict
        典型例: {"access_token": "...", "expires_in": 3599,
                "scope": "...", "token_type": "Bearer"}

    Raises:
        ValueError: 引数欠落
        RuntimeError: HTTP エラー / JSON 不正 / access_token 欠落
    """
    for name, val in [
        ("client_id", client_id),
        ("client_secret", client_secret),
        ("refresh_token", refresh_token),
    ]:
        if not val:
            raise ValueError(f"refresh_access_token: {name} is empty")

    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")

    req = urllib.request.Request(
        token_url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")
        raise RuntimeError(
            f"refresh_access_token: HTTP {e.code} from {token_url}: {err_body[:400]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"refresh_access_token: network error to {token_url}: {e.reason}"
        ) from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"refresh_access_token: non-JSON response: {raw[:400]}"
        ) from e

    if not data.get("access_token"):
        raise RuntimeError(
            f"refresh_access_token: response missing access_token: {data}"
        )
    return data


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Google OAuth2 refresh_token -> access_token")
    ap.add_argument("--client-id", default=os.environ.get("GOOGLE_CLIENT_ID"))
    ap.add_argument("--client-secret", default=os.environ.get("GOOGLE_CLIENT_SECRET"))
    ap.add_argument("--refresh-token", default=os.environ.get("GOOGLE_REFRESH_TOKEN"))
    ap.add_argument("--token-url", default=TOKEN_URL)
    ap.add_argument("--json", action="store_true", help="emit full JSON response")
    args = ap.parse_args()

    if not (args.client_id and args.client_secret and args.refresh_token):
        ap.error(
            "client-id / client-secret / refresh-token が必須 "
            "(env GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN でも可)"
        )

    tok = refresh_access_token(
        args.client_id, args.client_secret, args.refresh_token,
        token_url=args.token_url,
    )
    if args.json:
        print(json.dumps(tok, ensure_ascii=False))
    else:
        at = tok["access_token"]
        masked = at[:12] + "..." + at[-6:] if len(at) > 24 else "***"
        print(
            f"[oauth_refresh] OK access_token={masked} "
            f"expires_in={tok.get('expires_in')} "
            f"scope={tok.get('scope','?')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
