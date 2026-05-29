#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""docs/incidents/2026-05.md に 5/30 セクションを末尾追加。"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
p = ROOT / 'docs' / 'incidents' / '2026-05.md'

new_section = '''

---

## 2026-05-30 (土) 動画品質致命バグ + 字幕完全削除方針

### 緊急発覚
- ユーザー報告: https://youtu.be/fJSZD7HIlvM (009 北条早雲) 「学習していないのか?」
  - 音声 19 分で終わるのに動画 30.6 分 (差 11 分)
  - テロップ固定で音声と無関係
  - 画像とタイトル不一致
- 同時報告: https://youtu.be/LAVSg_jvnkY (004 心理的安全性、psych) 字幕ボロボロ
- 視聴者コメント: 「今川氏親をいまがしおやって、もうめちゃくちゃやん」 (edge-tts 固有名詞読み違え)

### 根本原因 3 点 (history_v2/pipeline.mjs)
1. **silence padding 残存**: audioDur < 1830s で無音 mp3 追加して水増し
   - CLAUDE.md 「2026-05-25 削除済」記載と実装が乖離 = **ハルシネーション認定**
2. **動画 seg ループ**: `while totalSec < audioDur+5` で seg を循環追加
   - concat_video.txt 末尾に seg_0 重複 → タイトル無関係画像が末尾 11 分間ループ
3. **ASS 字幕均等分散**: 全テキスト ÷ padding 後 audioDur で均等分割
   - whisper SRT (refine_srt.py 出力) を pipeline.mjs は完全に無視していた

### 修正 (commit 3bf44ea)
- 全 pipeline (history/psych/shorts) 字幕焼き込み完全削除
  - うっちー様指示: 「今後 YT 全部 (歴史/大人/両ショート) 字幕一切なし。音声と画像イメージは必ずタイトルに合わす」
- history silence padding 削除 + audioDur < 1500s で fail
- history 動画 seg ループ削除 (重複なし concat)
- スマホパネル: yt-dlp `/shorts` URL 別取得で long/shorts 精密分離
  - 歴史: 229 (混合) → 155/74 (long/shorts)
  - 大人: 37 (混合) → 5/32 (long/shorts)

### ディスク 45.19 GB 解放
- C: 3.87 GB → 49.04 GB (約 13 倍)
- 主犯: youtube/history_v2/.work 34GB、.work_broken 5GB、psych_v2/.work 5GB
- audio/*.mp3, .srt + stock_images/wiki も削除 (再生成可)
- scripts/_aggressive_cleanup.py (新規) で実行

### アップロード済 3 本 (009/016/004) は放置
- うっちー様指示「アップロード済みはもう放置でいい、今後の YT はマスト」
- 削除も再 build もしない

### 追加コミット
- `feat: スマホパネル累計 yt-dlp 統合 + X 自動投稿実装 + note ¥500 削除` (01bbd0b)
- `fix: 動画品質根本対応 字幕全削除 + history padding/ループ削除 + shorts 累計 + 45GB 解放` (3bf44ea)

### 残課題 (Task #35, #36)
- **edge-tts 固有名詞ふりがな辞書**: scripts/_yomi_dict.json + scripts/preprocess_yomi.py、gen_*_audio bat の STEP 1 直前に挿入
- **Gemini 画像マッピング**: generate_stock_scripts.py プロンプトに chapter_image_map を JSON で強制要求、pipeline.mjs が chapter 単位で画像配置

### 恒久ルール追加
- pipeline 修正記載は「実装確認」とセット (記載のみで実装漏れ = ハルシネーション)
- 全 uploaded 動画は `scripts/_check_video_audio_sync.py` で定期スキャン推奨
'''

with p.open('a', encoding='utf-8') as f:
    f.write(new_section)
print(f'OK: appended {len(new_section)} chars to {p.name}')
