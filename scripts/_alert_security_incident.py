"""
messages.json に緊急セキュリティアラートを追加 (スマホ pc.uchy0307.uk に黄色バナーで表示される)
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path('C:/Users/user/Documents/10oku-project')
MSG = ROOT / 'scripts' / 'messages.json'
JST = timezone(timedelta(hours=9))

def main():
    items = []
    if MSG.exists():
        try:
            items = json.loads(MSG.read_text(encoding='utf-8'))
        except Exception:
            items = []

    alert = {
        "id": f"msg_security_alert_{int(datetime.now().timestamp())}",
        "ts": datetime.now(JST).isoformat(),
        "title": "🚨 緊急: 全クレデンシャル漏洩 (GitHub 履歴に残存)",
        "body": (
            "Cloudflare から自動失効通知。原因は .env.env.bak_token_update が "
            "commit 9576708 で GitHub に push 済。\n\n"
            "漏洩クレデンシャル:\n"
            "- CLOUDFLARE_API_TOKEN (失効済)\n"
            "- YOUTUBE_REFRESH_TOKEN (samurai/otona 両方、まだ有効)\n"
            "- YOUTUBE_CLIENT_SECRET\n"
            "- GEMINI_API_KEY x2\n\n"
            "応急処置済 (Claude 自走):\n"
            "1. 漏洩ファイルを working tree から削除\n"
            "2. .gitignore を全 .env.* 派生にマッチするよう強化\n\n"
            "うっちー様が朝やる必要:\n"
            "1. Google Cloud で全 OAuth credentials 削除→再発行\n"
            "2. AI Studio で Gemini key 削除→再発行\n"
            "3. refresh_token を OAuth Playground で再取得\n"
            "4. .env 更新\n"
            "5. (任意) git filter-repo で履歴消去\n\n"
            "詳細: URGENT_SECURITY_INCIDENT_2026-05-29.md"
        ),
        "level": "critical",
        "read": False,
    }
    items.append(alert)
    MSG.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Alert added: {alert['id']}")

if __name__ == "__main__":
    main()
