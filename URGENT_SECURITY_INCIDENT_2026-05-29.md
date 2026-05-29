# 🚨 緊急セキュリティインシデント 2026-05-29

## 何が起きたか

GitHub Secret Scanning が commit `9576708` (5/28 自走) で**全クレデンシャル漏洩**を検出。
Cloudflare が **CLOUDFLARE_API_TOKEN を自動で無効化** (失効通知メール)。

## 漏洩したクレデンシャル

ファイル: `.env.env.bak_token_update` (commit 9576708 で push 済)

| クレデンシャル | 状態 | 対応 |
|---|---|---|
| **CLOUDFLARE_API_TOKEN** (`cfut_85xMTDMLZQ...`) | ✅ Cloudflare 側で自動失効済 | Cloudflare Dashboard で**ロール or 削除** |
| **YOUTUBE_REFRESH_TOKEN** (samurai, `1//0eS6H0IrN...`) | ⚠️ **まだ有効** | Google Cloud で**取り消し → 再発行** |
| **OTONA_YOUTUBE_REFRESH_TOKEN** (otona, `1//0eA-mtaaT...`) | ⚠️ **まだ有効** | 同上 |
| **YOUTUBE_CLIENT_SECRET** (`GOCSPX-nz2Pgxlre...`) | ⚠️ **まだ有効** | Google Cloud で**再生成** |
| **GEMINI_API_KEY** (`AIzaSyDa36UmYQ...`) | ⚠️ **まだ有効** | Google AI Studio で**取り消し → 新規発行** |
| **GEMINI_API_KEY_FREE** (`AIzaSyAXW8SsGS...`) | ⚠️ **まだ有効** | 同上 |

## 既に実施した応急処置 (Claude 自走で)

1. ✅ `.env.env.bak_token_update` を working tree から削除 (`rm` 実行済)
2. ✅ `.gitignore` を強化: `.env.*`, `*.env.bak*`, `.env_backup*`, `.env.backup*` 全パターン追加
3. ✅ git status で「D `.env.env.bak_token_update`」(削除 staged) を確認
4. ✅ Cloudflare 失効通知メールの内容を読んで対処判断

## 未実施 (うっちー様判断が必要)

| 項目 | 判定基準 | コマンド |
|---|---|---|
| 削除 commit | 個別 commit にして他の変更と分離するか | `git add .gitignore .env.env.bak_token_update && git commit -m "fix(security): remove leaked .env backup + harden gitignore"` |
| git filter-repo で履歴から完全消去 | リポを clean にしたいか (destructive) | `git filter-repo --invert-paths --path .env.env.bak_token_update` |
| force push | history 書き換え後の同期 | `git push --force-with-lease origin sync/2026-05-29-auto` |

## ⚠️ 重要な注意

**GitHub に push 済の commit `9576708` に漏洩がある以上、誰かが既にコピーしている可能性ゼロではない。**
**全クレデンシャル「漏洩済み = ローテーション必須」前提で行動するのが安全。**

Cloudflare が自動失効したのは「Anthropic GitHub から signal が来た」ためで、GitHub 自体が public に公開している以上、他のスキャナーも見ている。

## 推奨手順 (うっちー様朝起きたら)

### Step 1: 全クレデンシャル取り消し (10分)
1. https://console.cloud.google.com/apis/credentials
   - YouTube OAuth 2.0 クライアント `898426588524-3l6tabtv...` を**削除**
   - 新規 OAuth クライアント作成
2. https://aistudio.google.com/app/apikey
   - 既存 Gemini API key 2本を**削除**
   - 新規 API key 2本作成
3. https://dash.cloudflare.com/profile/api-tokens
   - 失効済 CF token のロール or 削除
   - 必要なら新トークン作成 (Pages デプロイ用など)

### Step 2: refresh_token 再取得 (15分)
samurai と otona の両方:
- https://developers.google.com/oauthplayground/
- 新 CLIENT_ID / CLIENT_SECRET 入力
- `https://www.googleapis.com/auth/youtube.upload` で認証
- refresh_token コピー

### Step 3: .env 更新 + 動作確認 (5分)
```bash
# 新クレデンシャルで .env 更新後
python scripts/_oauth_test.py    # OAuth 動作確認
node note-auto/post.mjs --max=1  # 1本だけテスト投稿
```

### Step 4: GitHub から履歴消去 (15分、destructive)
```bash
# バックアップを取ってから
git clone --mirror . ../10oku-project-backup.git

# filter-repo で漏洩ファイルを全 commit から削除
pip install git-filter-repo
git filter-repo --invert-paths --path .env.env.bak_token_update --force

# remote を再追加 (filter-repo は origin を消す)
git remote add origin https://github.com/uchy0307/my-10oku-project.git
git push --force origin --all
```

## 漏洩元の特定 (再発防止)

`.env.env.bak_token_update` というファイル名は `_update_env_token.py` (5/28 作成) が作ったバックアップと推測。

`scripts/_update_env_token.py` の中身を見て、`.bak` パターンを正しく `.env.bak_*` (gitignore 一致) で作るよう修正必要。
