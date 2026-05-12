# 10oku-project 引き継ぎドキュメント

> スマホ・GitHub上でそのまま閲覧可能。緊急時はこれ1枚で全体把握可。

---

## プロジェクト概要

- **名称**: 年商10億・完全自動化量産プロジェクト
- **コア思想**: 苦徹成珠・侍の美学
- **ユーザー**: うっちー様（GitHub: [uchy0307](https://github.com/uchy0307)）
- **マスタリポジトリ**: `uchy0307/my-10oku-project`
- **連携プロダクト**: `uchy0307/toi-suite`（Vercel本番稼働中）

---

## 4脳連携

| 脳 | 役割 | 主な担当 |
|---|---|---|
| Claude Code / Dispatch | 実装 | コード生成・GitHub Actions・自動化スクリプト |
| NotebookLM | 思想・トーン | 文体・世界観の一貫性チェック |
| Gemini API | 戦略・分析 | 台本生成・市場分析・要約 |
| ElevenLabs | 音声 | ナレーション・キャラボイス |

---

## 現状

- **toi-suite**: Vercel稼働中、6軸レーダー実装push済
- **10oku-project**: GitHub Actions構築完了、Secrets設定済
- **note自動投稿**: B案・下書き編集型（storageState使用、bot検知回避）で実装完了
- **YouTube自動**: 毎日12:00 UTC cron稼働、compile_video / upload_youtube 本実装完了（ffmpeg + googleapis）
- **Self-Heal**: workflow失敗時に Gemini で原因推定→Issue自動起票（`.github/workflows/self-heal.yml`）

---

## アーキテクチャ

```
┌──────────────────────────────────────────────────┐
│              GitHub Actions (cron)               │
│   ┌──────────────┐        ┌──────────────────┐   │
│   │YouTube Cycle │        │note Auto Post (B)│   │
│   │ 12:00 UTC毎日 │        │ ランダム 1日2本以下│   │
│   └──────┬───────┘        └────────┬─────────┘   │
└──────────┼─────────────────────────┼─────────────┘
           │                         │
   ┌───────▼──────┐          ┌───────▼────────┐
   │ Gemini API   │          │ Playwright     │
   │ ElevenLabs   │          │ (Chromium)     │
   │ YouTube API  │          │ → note.com     │
   └──────┬───────┘          └────────────────┘
          │
   ┌──────▼──────────┐       ┌───────────────────┐
   │ Supabase (DB)   │◀──────│ toi-suite (Vercel)│
   │ + state.json    │       │  6軸レーダー本番  │
   └─────────────────┘       └───────────────────┘
```

---

## 今後の運用

- **cron 毎日12:00 UTC** で YouTube自動 + note低速自動が走る
- 失敗時は GitHub Issues 自動起票（要本実装、雛形は workflow 内に記載）
- スマホから [Actions タブ](https://github.com/uchy0307/my-10oku-project/actions) で状態確認可
- queue.json は workflow が自動 commit back（投稿ステータス更新）

---

## 連絡経路

- **GitHub失敗メール**: 自動配信（GitHubアカウント通知設定に依存）
- **緊急時**: ローカルPCで PowerShell から手動再開可
  ```powershell
  cd C:\Users\user\Documents\10oku-project
  npm run youtube:cycle    # YouTube手動実行
  npm run note:post        # note手動投稿
  ```

---

## 既知の制約

- **note自動投稿はnote規約グレーゾーン**（BANリスクあり、1日2本まで・ランダム遅延）
- 完全自動化が原則、人手介入は最終アクション（push実行・Actions 有効化）のみ
- Playwright on GitHub Actions は CAPTCHA で停止する可能性あり
- Supabase / Vercel / ElevenLabs はそれぞれ無料枠に上限あり、月次で要監視

---

## 残タスク

- [x] `compile_video.mjs` 本実装（ffmpeg + sharp、静止画+音声→mp4）
- [x] `upload_youtube.mjs` 本実装（googleapis + OAuth refresh token フロー）
- [x] GitHub Issues 自動起票（self-heal workflow、Gemini-2.5-flash診断付き）
- [x] note を下書き編集型に切り替え（Playwright storageState）
- [ ] ローカルで `npm run note:capture` 実行 → storageState 取得 → Secret 登録（**ユーザー作業**）
- [ ] note.com 上で記事の下書きを作成し draftId を queue.json に流し込み
- [ ] Playwright 実機テスト（ローカルで `npm run note:post` 動作確認）
- [ ] note `queue.json` への本番記事流し込み

---

## 重要な決定

- 残10シリーズ量産は中止、**toi-suite単独製品** に集約
- メンバーシップ **500円/月**、note **1本100円買取**
- 11シリーズ対象ペルソナ確定済（toiは47歳管理職、他は別ペルソナ）
- note自動化は B案（低速・人間操作シミュレート）採用、A案（API利用）はnote公式API未公開のため不採用

---

## ディレクトリ構造

```
10oku-project/
├── HANDOFF.md                    ← この文書
├── README.md                     ← プロジェクト全体README
├── package.json
├── _push_10oku.bat               ← Windows用 初回push ランチャー
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       ├── youtube_auto.yml      ← YouTube自動サイクル（毎日12:00 UTC）
│       ├── toi_suite_deploy.yml  ← Vercel deploy hook
│       ├── note_auto_post.yml    ← note B案 自動投稿（1日2回・下書き編集型）
│       └── self-heal.yml         ← 失敗検知→Gemini診断→Issue自動起票
├── scripts/
│   └── self_heal.mjs             ← self-heal 本体（Octokit + Gemini）
├── youtube/
│   ├── scripts/                  ← generate / compile / upload
│   └── output/                   ← state.json + 生成物（gitignore）
├── note-auto/                    ← B案 note自動投稿（下書き編集型）
│   ├── README.md                 ← 新方針・storageState取得手順
│   ├── post.mjs                  ← Playwright（storageState使用）
│   ├── capture-session.mjs       ← 手動ログイン→storageState保存
│   └── queue.json                ← 投稿待ち記事キュー（draftId必須）
└── apps/
    └── toi-suite-link.md         ← toi-suite repo へのリンク
```

---

## うっちー様の最終アクション

1. ローカルで `_push_self_heal_v2.bat` を実行（GITHUB_TOKEN 設定済の PowerShell から）
2. ローカルで storageState 取得:
   ```powershell
   cd C:\Users\user\Documents\10oku-project
   npm install
   npx playwright install chromium
   npm run note:capture
   ```
   → 起動した Chromium で手動ログイン → Enter → `note-auto/storageState.json` 生成
3. GitHub → Settings → Secrets and variables → Actions に
   `NOTE_STORAGE_STATE`（storageState.json の中身全文）を登録
4. note.com 上で下書きを1本作成し、URL から `draftId` を取得
5. `note-auto/queue.json` に `draftId` / `title` / `body` を埋めて push
6. https://github.com/uchy0307/my-10oku-project/actions を開く
7. `note_auto_post` / `YouTube Auto Cycle` workflow を有効化
8. 以降は cron で自動稼働 → **PC は OFF にしてOK**

storageState の cookie が失効した場合は手順 2-3 を再実施するだけでよい。
