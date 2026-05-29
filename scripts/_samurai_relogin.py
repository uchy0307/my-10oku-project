#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""samurai (歴史侍) refresh_token の再取得
   既存の YOUTUBE_CLIENT_ID/SECRET (デスクトップ型) で
   InstalledAppFlow を使ってローカルブラウザで認証 → refresh_token 表示
"""
import sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
env_path = ROOT / '.env'
env = {}
for line in env_path.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

client_id = env.get('YOUTUBE_CLIENT_ID')
client_secret = env.get('YOUTUBE_CLIENT_SECRET')
if not (client_id and client_secret):
    print('ERROR: YOUTUBE_CLIENT_ID/SECRET が .env に無い')
    sys.exit(1)

# google-auth-oauthlib インストール確認
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print('google-auth-oauthlib が未インストール')
    print('  pip install google-auth-oauthlib')
    print('または py -m pip install google-auth-oauthlib')
    sys.exit(2)

# Desktop型 OAuth flow
client_config = {
    "installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

print('=== samurai 再認証フロー ===')
print('1. ブラウザが自動で開きます')
print('2. @Japanese.Samurai.Channel のアカウントを選択してログイン')
print('3. 権限許可')
print('4. 自動でこの画面に refresh_token が表示されます')
print()

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
creds = flow.run_local_server(port=0, prompt='consent', access_type='offline')

print()
print('=== SUCCESS ===')
print(f'access_token   len={len(creds.token)} (一時)')
print(f'refresh_token: {creds.refresh_token}')
print()
print('→ この refresh_token を チャットに貼るか、または下記コマンドで .env を自動更新:')
print(f'   python "C:/Users/user/Documents/10oku-project/scripts/_update_env_token.py" --kind samurai --token "{creds.refresh_token}"')
