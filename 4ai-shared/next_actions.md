# 次のアクション

## 翌日対応（2026/05/15以降）
1. **1日2本配信** cron を 23:00 UTC（JST 08:00）と 11:00 UTC（JST 20:00）に設定 → `.github/workflows/youtube_auto.yml`
2. **説明文修正**: `compile_video.mjs` の `generateMeta` から `― 侍の美学 ―\n10oku-project｜年商10億完全自動化プロジェクト` を削除
3. **「ALL」再生リスト自動追加**: `upload_youtube.mjs` に `youtube.playlistItems.insert` 実装。プレイリストIDはうっちー様がStudioで作成後に Secrets `YOUTUBE_PLAYLIST_ALL_ID` で渡す
4. note.com 同期処理の `[DUMP]` ログ確認 → APIレスポンス構造特定 → parser修正

## note.com 関連（凍結中、12:17/20:43 JST cron実行後に再開）
- DUMP ログから note.com API レスポンス構造を確定
- `pickNoteArray()` / item key 抽出ロジックを正しい形に修正
- 200件マッチを達成
- post.mjs で実際の投稿動作テスト（max=1 でまず1本）

## YouTube 改善ロードマップ（中期）
- サムネに人物肖像合成（信長/秀吉等）
- 字幕デザイン強化（章タイトル大表示・効果音同期）
- 動的BGM追加（章ごと雰囲気変化）
- 画像生成プロンプトの精緻化（人物再現性向上）

## Gemini に依頼したい確認事項（凍結中）
- note.com API `/api/v2/notes/note_list/contents` の CSRF token 取得方法
- bot検知回避のための追加ヘッダー
