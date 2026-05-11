# 10oku-project ｜ 年商10億完全自動化マスタープロジェクト

うっちー様の**4脳連携体制（ChatGPT＝設計脳 / Gemini＝指揮脳 / Claude＝実装脳 / Manus＝拡張脳）**を、1つのGitリポジトリに統合した自動化基盤です。

---

## 3つの稼働ライン

| # | ライン名 | 役割 | 稼働形態 |
|---|---|---|---|
| 1 | **toi-suite 6軸分析システム** | Webアプリ本体（プロダクト本丸） | Vercel常時稼働（別repo: `uchy0307/toi-suite`） |
| 2 | **YouTube自動投稿パイプライン** | 台本生成 → ナレーション → 動画コンパイル → YouTubeアップロード | GitHub Actions cron（24h自律） |
| 3 | **GitHub Actions cron実行基盤** | PC OFF後もクラウドで稼働させる土台 | 毎日12:00 UTC自動 + 手動トリガー対応 |

---

## ディレクトリ構成

```
10oku-project/
├── README.md                     ← 本ファイル
├── .gitignore
├── .env.example                  ← APIキー雛形
├── package.json
├── _push_10oku.bat               ← うっちー様起動用（git init + push一括）
├── apps/
│   └── toi-suite-link.md         ← toi-suite（別repo）への参照ドキュメント
├── youtube/
│   ├── README.md
│   ├── scripts/
│   │   ├── generate_script.mjs   ← Gemini APIで台本生成
│   │   ├── generate_voice.mjs    ← ElevenLabs APIでナレーション
│   │   ├── compile_video.mjs     ← 動画コンパイル（stub）
│   │   └── upload_youtube.mjs    ← YouTube Data API v3アップロード（stub）
│   ├── topics.json               ← 1000本ノックの全テーマ（雛形50本）
│   └── output/                   ← 生成物（.gitignore）
└── .github/workflows/
    ├── youtube_auto.yml          ← YouTube自動投稿ワークフロー
    └── toi_suite_deploy.yml      ← toi-suite デプロイhook
```

---

## セットアップ手順

### 1. GitHub Secrets 確認

`https://github.com/uchy0307/my-10oku-project/settings/secrets/actions` で以下が設定されていることを確認:

- `GEMINI_API_KEY`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `YOUTUBE_API_KEY`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

### 2. ローカルからGitHubへ初回push

PowerShellで `_push_10oku.bat` を実行（または直接以下）:

```powershell
cd C:\Users\user\Documents\10oku-project
git init
git add -A
git commit -m "feat: 10oku-project初期構築"
git remote add origin https://uchy0307:$env:GITHUB_TOKEN@github.com/uchy0307/my-10oku-project.git
git branch -M main
git push -u origin main --force
```

### 3. GitHub Actions 有効化

- リポジトリの **Actions** タブを開く
- `Enable workflows` をクリック（初回のみ）
- `youtube_auto.yml` を選択 → **Run workflow** ボタンで手動初動確認

### 4. cron稼働開始

毎日 **12:00 UTC（日本時間21:00）** に自動実行されます。
PCをOFFにしても、クラウドで自律稼働を継続します。

---

## うっちー様の最終アクション

1. **`_push_10oku.bat` をダブルクリック** → GitHubへ初回push
2. **GitHub Secrets を確認**（上記8項目すべて）
3. **Actions タブで `Run workflow` を1回手動実行**（動作確認）
4. **以降はPC OFFのまま24h自律稼働**

---

## 4脳連携の役割分担

- **ChatGPT（設計脳）**: 全体アーキテクチャ・要件定義
- **Gemini（指揮脳）**: 詳細仕様・命令書発行
- **Claude（実装脳）**: コード生成・ファイル構築（本リポジトリ）
- **Manus（拡張脳）**: 外部リサーチ・データ収集

---

## 関連リポジトリ

- **toi-suite 本体**: `https://github.com/uchy0307/toi-suite`
- **本リポジトリ**: `https://github.com/uchy0307/my-10oku-project`

---

侍の美学を、最後の最後まで。
