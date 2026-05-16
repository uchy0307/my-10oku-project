# new-youtube

30代-40代女性向け 大人のライフスタイル・心理学チャンネル用 YouTube 自動化パイプライン。
10分長尺・横16:9・1日2本・アニメ調・健全範囲 (YouTube TOS 準拠)。

**samurai チャンネルとは完全に独立した別チャンネル**で運用します (env / state / playlist すべて分離)。

## ディレクトリ構成

```
new-youtube/
├── scripts/
│   ├── step0_gemini_generate.py   Gemini で台本JSON生成
│   ├── step1_load.py              JSON 読込・スキーマ検証・NG単語拒否
│   ├── step2_voice.py             ElevenLabs / GCP Neural2-B でナレ生成
│   ├── step3_images.py            Pollinations.ai flux で画像生成 + キャッシュ
│   ├── step4_compile.py           MoviePy + ffmpeg concat で動画合成
│   ├── step5_upload.py            YouTube Data API (新チャンネル専用 NEW_YOUTUBE_*)
│   └── run_pipeline.py            Step 0→1→2→3→4(→5) 一括実行
├── inputs/
│   ├── script_001.json            ダミー台本 (動作確認用・8章)
│   ├── topics.json                Gemini に渡すテーマ一覧 (15件)
│   └── state.json                 topic_idx 進捗 (samurai と独立)
├── outputs/                       実行時生成物 (.gitignore)
├── cache/images/                  画像キャッシュ (.gitignore)
├── assets/                        BGM 等 (calm_lounge.mp3 を配置)
├── .github/workflows/
│   └── new_youtube_auto.yml       JST 06:00 / 18:00 cron
├── requirements.txt
├── README.md  (本ファイル)
└── SAMURAI_DIFF.md
```

## ユーザー側で必須の準備 (チェックリスト)

### 1. 新 YouTube チャンネル

- [ ] 新 YouTube チャンネルを作成済か確認 (samurai と別アカウント or 同アカウント別Brand)
- [ ] チャンネルID をメモ
- [ ] 動画を流す Playlist を作成し ID をメモ (任意)

### 2. Google Cloud Console (新 OAuth Client)

- [ ] 新規 OAuth 2.0 Client ID 発行 (Web アプリ or Desktop)
- [ ] YouTube Data API v3 を有効化
- [ ] OAuth Playground 等で `https://www.googleapis.com/auth/youtube.upload` のスコープで **新チャンネル** にログインし refresh token を取得

### 3. GitHub Secrets (4 つ + α 登録)

リポジトリ Settings → Secrets and variables → Actions に以下を登録:

| Secret name                  | 用途                                     | 必須/任意 |
| ---------------------------- | ----------------------------------------- | --------- |
| `NEW_YOUTUBE_CLIENT_ID`      | 新 OAuth Client ID                       | **必須**  |
| `NEW_YOUTUBE_CLIENT_SECRET`  | 新新 OAuth Client Secret                   | **必須**  |
| `NEW_YOUTUBE_REFRESH_TOKEN`  | 新チャンネル用 refresh token             | **必須**  |
| `NEW_YOUTUBE_PLAYLIST_ID`    | 公開後に追加する Playlist ID             | 任意      |
| `GEMINI_API_KEY`             | Step 0 台本生成                          | **必須**  |
| `ELEVENLABS_API_KEY`        | Step 2 ナレ (推奨)                       | 任意      |
| `ELEVENLABS_VOICE_ID`        | 日本語女声 voice id                      | 任意      |
| `GCP_SA_JSON_B64`            | GCP TTS Neural2-B 用 SA キー (base64)    | 任意      |

ElevenLabs と GCP TTS は **どちらか片方**があれば音声生成は通る (ElevenLabs 優先・失敗時 GCP fallback)。

既存 samurai 用の `YOUTUBE_REFRESH_TOKEN` 等は **温存** (本パイプラインからは参照しません)。

## ローカル動作確認

```bash
# 0. requirements
pip install -r requirements.txt
sudo apt-get install -y ffmpeg fonts-noto-cjk imagemagick

# 1. Step 1 のみ (ダミー台本でスキーマ検証)
python scripts/step1_load.py inputs/script_001.json
#   期待: OK title=..., chapters=8, total narration chars: 1522

# 2. Step 3 のみ (Pollinations.ai は無料)
python scripts/step3_images.py inputs/script_001.json 2

# 3. Step 2-4 通し (要 ElevenLabs or GCP TTS)
python scripts/run_pipeline.py --script inputs/script_001.json --no-upload
#   outputs/script_001/compile_work/final.mp4 が生成されれば OK

# 4. Gemini で新規台本→動画 (要 GEMINI_API_KEY)
export GEMINI_API_KEY=xxx
python scripts/run_pipeline.py --no-upload

# 5. 新チャンネルへアップロードまで (要 NEW_YOUTUBE_*)
export NEW_YOUTUBE_CLIENT_ID=xxx
export NEW_YOUTUBE_CLIENT_SECRET=xxx
export NEW_YOUTUBE_REFRESH_TOKEN=xxx
python scripts/run_pipeline.py --script inputs/script_001.json
```

## GitHub へのコミット手順

PAT はリポジトリの `.git/config` (origin URL) 経由で push してください。チャット・コード内に直貼りしない方針です。

```bash
cd /path/to/my-10oku-project
git pull
mkdir -p new-youtube
cp -r /path/to/this/new-youtube/* new-youtube/
git add new-youtube/ .github/workflows/new_youtube_auto.yml
git commit -m "feat(new-youtube): step0-5 prototype + Gemini auto pipeline (new channel)"
git push
```

`.gitignore` 推奨:
```
new-youtube/outputs/
new-youtube/cache/
new-youtube/assets/*.mp3
new-youtube/gcp_sa.json
```

## GitHub Actions cron

`.github/workflows/new_youtube_auto.yml` は JST 06:00 / 18:00 で日 2 本実行。samurai 既存 cron と衝突する時刻があれば調整してください。

`workflow_dispatch` から手動実行も可。inputs:
- `topic` : トピック直指定
- `no_upload` : `true` でアップロードスキップ

## コンテンツポリシー

- 性表現・性的示唆・身体強調・euphemism 置換は **実装しない**
- 学生 / 制服 / 未成年 連想は全面禁止 (`step1_load.NG_WORDS` / `step3_images.NG_TOKENS` で 2 重チェック)
- Gemini プロンプトにも「健全な語彙のみ」「示唆的言い換えも使わない」を明示
- 異常時は自動置換せず `ValueError` で停止

YouTube 規約に違反するコンテンツは生成しない方針です。
