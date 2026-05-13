# 次のアクション

## うっちー様
1. 帰宅後 `_push_dump.bat` を実行（push）
2. または12:17 JST or 20:43 JSTのCron自動実行を待つ
3. ワークフロー実行後、Sync drafts ステップの **`[DUMP1] [DUMP2] [DUMP3]`** ログをClaudeに共有

## Claude
1. DUMP ログから note.com API レスポンス構造を確定
2. `pickNoteArray()` / item key 抽出ロジックを正しい形に修正
3. 200件マッチを達成
4. post.mjs で実際の投稿動作テスト（max=1 でまず1本）

## Gemini に依頼したい確認事項
- note.com API `/api/v2/notes/note_list/contents` の **CSRF token 取得方法**（必要なら）
- レスポンス JSON のスキーマ（公式ドキュメント or 解析結果あれば）
- bot検知回避のための追加ヘッダー（特に `X-Requested-With`、`X-Note-XHR-Token` 等の必要性）

## NotebookLM
- このフェーズでは依頼なし

## ElevenLabs
- このフェーズでは依頼なし
