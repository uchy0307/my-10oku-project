#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""messages.json に新しい claude_to_user メッセージを先頭追加。"""
import json, time, datetime, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
p = ROOT / 'scripts' / 'messages.json'
data = json.loads(p.read_text(encoding='utf-8'))
jst = datetime.timezone(datetime.timedelta(hours=9))
ts_ms = int(time.time())

new_msg = {
    "id": f"msg_pipeline_fix_{ts_ms}",
    "ts": datetime.datetime.now(jst).isoformat(),
    "title": "✅ 動画品質根本対応 + スマホパネル正確化 + 45GB 解放",
    "text": (
        "今後 YT 全動画 字幕削除完了 (commit 3bf44ea)\n"
        "history_v2: silence padding 削除 + 動画 seg ループ削除 + 字幕削除\n"
        "psych_v2 + shorts_v2: 字幕削除\n"
        "アップロード済 3 本 (009/016/004) は放置 (うっちー様指示)\n\n"
        "スマホパネル: 歴史 155/74、大人 5/32 (long/shorts 分離)\n"
        "ディスク C: 3.87GB → 49.04GB (45GB 解放)\n\n"
        "次: 固有名詞ふりがな辞書 (今川氏親→いまがわうじちか)\n"
        "次: Gemini プロンプトで画像と chapter 内容一致"
    ),
    "type": "claude_to_user",
    "read": False
}
data.insert(0, new_msg)
p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'OK: messages.json 先頭に追加 (total {len(data)} msgs)')
