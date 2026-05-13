# 現在のブロッカー

## 🔴 最優先: note.com 同期処理（200本フルマッチ未達）

### 症状
sync-drafts.mjs が note.com 上の下書きを14本しかマッチさせられず、残り186本の draftId が空のまま。
post.mjs は draftId が無い記事をスキップする実装になってるので、結果的に1本も自動投稿されない。

### 詳細
- `https://note.com/api/v2/notes/note_list/contents?page=N&status={draft|published}` がnote.comの内部API
- 直接 fetch すると HTML 404 が返る（CSRF/Referer/XSRF-token 検証で弾かれてる疑い）
- note.com 自身がそのAPIを叩くタイミングを Playwright の `response` イベントで捕捉してる
- スニッファでJSONは取得できているが、配列パースが失敗して0件抽出になっている疑い

### 仮説
1. レスポンスJSONの構造が `pickNoteArray()` で想定してる形と違う
2. 配列はあるが各要素のキー（id/title）が想定外（例: `key`, `name`）

### 次の一手（push済 / 次回Cronで判明）
sync-drafts.mjs に「最初3レスポンスを生ダンプ」と「再帰的配列探索」を追加。
次回Cron実行後に `[DUMP1] [DUMP2] [DUMP3]` ログを確認→該当キー名でparser修正。

## 🟡 中: YouTube 動画コンパイル
- ffmpeg + sharp の組み合わせで現状「黒背景＋字幕」のみ
- 完成品クオリティに届かないため未投稿
- 動的画像生成 or ストックフッテージ合成のレシピが必要

## 🟢 解消済み
- ~~ワークフロー全段エラー~~（5/13朝に初グリーン達成）
- ~~`SyntaxError: Unexpected end of input`~~（pageNumループ`}`不足を修正）
- ~~git push 衝突~~（rebase経由でフォールバック）
- ~~`?kind=draft` URL誤り~~（`?status=draft` に修正）
- ~~Gemini API モデル404/429~~（`gemini-2.5-flash` で安定）
