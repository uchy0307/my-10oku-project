#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2026-05-30 X 自動投稿稼働を受けて、 全公開ファイルに X リンク一括 inject。

対象:
  1. articles/note_*.md (note 公開記事 200 本) - 末尾シグネチャ
  2. youtube/*/scripts/long_*.json (YT 台本) - description 末尾
重複防止: 既に "SoothingSoothin" or "x.com/" を含むファイルは skip。
"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')

X_HANDLE = '@SoothingSoothin'
X_URL = 'https://x.com/SoothingSoothin'

NOTE_FOOTER = '''

---

📌 **関連プラットフォーム / Follow me**

- **X (Twitter)**: [@SoothingSoothin](https://x.com/SoothingSoothin) ── 苦徹成珠 ─ 侍の美学
- **toi-suite**: [200の問い + 6軸自己診断](https://toi-suite.vercel.app/) ── 無料7問体験
- **YouTube (日本史)**: [@Japanese.Samurai.Channel](https://www.youtube.com/@Japanese.Samurai.Channel)
- **YouTube (大人の心理学)**: [@Otona_Psychology](https://www.youtube.com/@Otona_Psychology)
'''

YT_DESC_FOOTER = '''

━━━━━━━━━━━━━━━━━
📌 関連プラットフォーム / 苦徹成珠
X (Twitter): https://x.com/SoothingSoothin
toi-suite (200の問い): https://toi-suite.vercel.app/
note: https://note.com/happy_happy_4649
━━━━━━━━━━━━━━━━━'''


def inject_articles():
    art_dir = ROOT / 'articles'
    modified = []
    skipped = 0
    for p in sorted(art_dir.glob('note_*.md')):
        text = p.read_text(encoding='utf-8')
        if 'SoothingSoothin' in text or 'x.com/' in text.lower():
            skipped += 1
            continue
        new_text = text.rstrip() + NOTE_FOOTER + '\n'
        p.write_text(new_text, encoding='utf-8')
        modified.append(p.name)
    print(f'[articles] modified={len(modified)} skipped={skipped}')
    return len(modified)


def inject_yt_scripts():
    modified = 0
    skipped = 0
    targets = ['history_v2', 'psych_v2', 'history_shorts_v2', 'otona_shorts_v2',
               'shorts_v2', 'audio_drama', 'psych_shorts_v2']
    for sub in targets:
        d = ROOT / 'youtube' / sub / 'scripts'
        if not d.exists():
            continue
        for p in sorted(d.glob('*.json')):
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            desc = data.get('description', '')
            if not isinstance(desc, str):
                continue
            if 'SoothingSoothin' in desc or 'x.com/' in desc.lower():
                skipped += 1
                continue
            data['description'] = desc.rstrip() + YT_DESC_FOOTER
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            modified += 1
    print(f'[YT scripts] modified={modified} skipped={skipped}')
    return modified


if __name__ == '__main__':
    print('=' * 60)
    print('X link 一括 inject')
    print('=' * 60)
    a = inject_articles()
    y = inject_yt_scripts()
    print()
    print(f'計 {a + y} ファイル更新')
