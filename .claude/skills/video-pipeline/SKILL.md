---
name: video-pipeline
description: |
  10oku-project 動画パイプライン専用スキル。歴史/大人 YouTube チャンネル向けの台本生成・音声生成・字幕修正・動画化・投稿の自動化と、その障害切り分けを担当する。
  使うタイミング:
  - pipeline.mjs (history_v2/psych_v2/shorts_v2/otona_shorts_v2) を触る時
  - 字幕 (refine_srt.py / whisper_subtitle_gen.py) の問題対応
  - 投稿ボタン (build_*_3.bat / build_*_5.bat) の失敗解析
  - YouTube API quota / OAuth トラブル
  - daily_cycle.py / nightly_whisper.py の Cron 関連
---

# Video Pipeline Skill

## 哲学
- うっちー様の年商10億プロジェクトの肝はYouTubeチャンネルでの再生時間獲得。**1本でも欠けたら被害大**
- pipeline.mjs を触る時は**先に動作確認、勝手に修正しない**
- 失敗は**「原因＋改善案セット」**で報告
- BAT は no-window モード前提 (pause/timeout /nobreak 強制)

## 構造マップ

```
youtube/
  history_v2/         長尺 30分 歴史侍チャンネル
    pipeline.mjs      → 投稿ロジック
    scripts/*.json    → Gemini 生成台本 (chapters[].text + image_urls)
    audio/*.mp3       → edge-tts 生成
    audio/*.srt       → whisper + refine_srt 字幕
    .work/{idx}/      → 一時 (output.mp4, thumbnail.jpg)
  psych_v2/           長尺 大人心理学チャンネル (OTONA_YOUTUBE_REFRESH_TOKEN必須)
  shorts_v2/          ショート 歴史 (narration_text フィールド)
  otona_shorts_v2/    ショート 大人 (chapters[].text)

scripts/
  build_description.mjs   → YouTube リッチ説明文ビルダー (目次+参考文献+BGM+ハッシュタグ)
  refine_srt.py            → whisper誤認識を原稿テキストで補正
  manual_upload.mjs        → 既ビルド output.mp4 を YouTube に手動アップ
  daily_cycle.py           → 朝 8:00 自動実行 (UchyDailyCycle)
  nightly_whisper.py       → 夜 23:00 自動実行 (UchyNightlyWhisper、tiny model)
  local_button_server.py   → pc.uchy0307.uk バックエンド (pythonw, no-window)
```

## 即解決チートシート

### 「動画ビルドエラー」
1. `scripts/logs/action_build_*_$(date +%Y%m%d)_*.log` の Tail 20行確認
2. よくある原因:
   - **image_urls 不足**: pipeline 側 stock fallback で補填 (history は ≥4 でOK)
   - **duplicate title**: 既投稿との重複。TITLE_SUFFIX env で "(MM/DD再)" 付与
   - **audio missing**: shorts_v2 の場合 narration_text フィールドが正しく読まれてるか確認
   - **duration < 900s**: 台本短い。expand chapter text

### 「字幕が大きすぎる/見切れる」
- ASS: Fontsize=56 + MarginL/R=200 + MarginV=80 が標準 (long-form 1920x1080)
- ASS: Fontsize=60 + MarginL/R=120 (shorts 1080x1920)
- SRT → libass の場合 PlayResY=288 デフォルトに注意 → SRT を ASS変換 (PlayResY=1080 明示) する srtToAss() 関数を使う

### 「YouTube アップ失敗」
- "Quota exceeded" → 1日6本/プロジェクト上限。100k 増枠申請 (B案)
- "duplicate title" → manual_upload.mjs が自動で suffix 付与
- "image_urls 0/8" → stockImagesUsed フォールバック確認
- OAuth エラー → .env の YOUTUBE_REFRESH_TOKEN / OTONA_YOUTUBE_REFRESH_TOKEN 別管理 (誤投稿防止)

### 「whisper 詰まり」
- daily_cycle 朝Cron では「本日upload分の4本だけ」whisper (`step_whisper` 仕様)
- 残りは UchyNightlyWhisper (23:00) で tiny モデル一括処理
- 既存 SRT があれば whisper スキップ

### 「button-server 落ちた」
- pc.uchy0307.uk が 502 → `Start-Process pythonw scripts/local_button_server.py -WindowStyle Hidden` で再起動
- 自動起動タスク `UchyButtonServer` が再ログオン時に立ち上げる
- ポート 7373 占有プロセスは `Get-NetTCPConnection -LocalPort 7373` で確認

## 絶対やってはいけない
- ❌ 大人系を `YOUTUBE_REFRESH_TOKEN` (歴史) で投稿 (チャンネル混入事故)
- ❌ pause / set /p / timeout 無 /nobreak を BAT に入れる (no-window で hang)
- ❌ pipeline.mjs の不要な書き換え (動いてるものを壊す)
- ❌ Fontsize を ASS Style と force_style で別値設定 (整合性確認)
- ❌ pythonw 起動した button-server を kill (admin必要、止めるなら restart_button_server.bat 経由)

## 強制ワークフロー (pipeline 変更時)
1. **diff を ultrareview (or 慎重に目視)**
2. **テスト index で 1本ビルド**して output.mp4 サイズ / 字幕位置 / 音声長 確認
3. 異常なし → daily_cycle が次回拾うように commit & 走らせる
4. 異常あり → ロールバック (`git restore`) して原因究明

## 参考リンク
- HANDOFF.md (プロジェクト現状)
- SCHEDULE.md (Claude の永続スケジュール)
- agent/memory/MEMORY.md (嗜好・累積記録)
