# YouTube 自動投稿パイプライン

「侍の美学」トーンで、**1000本ノック**を実現する自動投稿システム。

---

## パイプラインの全体像

```
[1] generate_script.mjs   ← Gemini APIで30分台本生成（侍の美学トーン）
        │
        ▼
[2] generate_voice.mjs    ← ElevenLabs APIでナレーション音声生成
        │
        ▼
[3] compile_video.mjs     ← 動画コンパイル（現状stub：メタデータのみ生成）
        │
        ▼
[4] upload_youtube.mjs    ← YouTube Data API v3でアップロード（現状stub：state記録のみ）
```

---

## 1サイクルの実行

```bash
npm run youtube:cycle
```

このコマンドが上記4ステップを順に実行します。

---

## 状態管理

`youtube/output/state.json` が「次に処理すべきテーマ」「投稿済みID」を管理します。
GitHub Actions が cron で実行するたびに state.json を更新 → commit & push して状態を継続。

---

## テーマソース

`youtube/topics.json` に雛形50本を収録。
将来的に toi-suite の Supabase DB から動的に取得する想定。

---

## 環境変数

`.env.example` を参照。ローカル実行時は `.env` を作成、GitHub Actions では Secrets を使用。

---

## stub について

- **compile_video.mjs**: 動画コンパイルは ffmpeg + asset library が必要なため後実装。現状は `<id>_meta.json`（タイトル・説明・タグ）のみ生成。
- **upload_youtube.mjs**: 動画ファイル未生成のため、現状は `state.json` に「投稿予約」記録のみ。実動画生成後にアップロード本体が動くロジックは既に実装済。
