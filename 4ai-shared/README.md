# 4AI 共有ハブ（うっちー様の年商10億プロジェクト）

このフォルダは Claude / Gemini / NotebookLM / ElevenLabs の4AIが情報共有するための固定ファイル置き場。
うっちー様はこのフォルダを各AIに「読んで・書いて」と渡すだけで状況が同期される。

## ファイル構成

- `status.md` — 現在進行中の作業・直近の成功/失敗ログ
- `decisions.md` — 確定した方針・価格・ペルソナ・絶対ルール
- `blockers.md` — 詰まってる問題と仮説
- `next_actions.md` — 次にやるべきこと（誰が何を）

## 各AIへの渡し方（重要）

- **Claude**: ファイル直接読める。パス指定でOK
- **NotebookLM**: 「ソース」として `4ai-shared/` 配下を全部アップロード。更新時だけ差し替え
- **Gemini Web**: ファイル読めない。`FOR_GEMINI_PASTE.md` の中身を**全文コピペ**で渡す
- **ElevenLabs**: 文字列(SSML/プレーンテキスト)入力のみ。`FOR_GEMINI_PASTE.md` ではなく台本本文を直接渡す

## 更新ルール

- 各AIは作業完了・新事実判明のたびに該当ファイルを更新提案
- うっちー様が確認してから commit & push
- 主導は Claude（私）。Gemini/NotebookLM への共有はうっちー様がコピペで実施
