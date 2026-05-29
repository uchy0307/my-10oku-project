# X (Twitter) アカウント ブランディング セット

> 2026-05-30 作成。 苦徹成珠 ブランドの X 公式アカウント設計。

## ファイル構成

| ファイル | 内容 |
|---|---|
| `bio.md` | 表示名 / Bio (自己紹介) / ピン留めツイート / 設定手順 |
| `banner_prompt.md` | バナー画像 (1500×500) 生成プロンプト + デザイン案 4 種 |
| `avatar_prompt.md` | プロフィール画像 (400×400) 生成プロンプト + デザイン案 4 種 |

## うっちー様作業手順 (15 〜 30 分)

### Step 1: 画像生成 (10 分)
- アバター: Canva で `avatar_prompt.md` の **案A 篆書「苦徹成珠」** を作成 → PNG ダウンロード
- バナー: Bing Image Creator で `banner_prompt.md` の **推奨案A「月光と刀身」** を生成 → Canva で 1500×500 に整える + テキスト合成

### Step 2: X プロフィール設定 (5 分)
- https://x.com/settings/profile を開く
- `bio.md` の **「設定手順」セクション** に従う:
  1. 表示名: `苦徹成珠 ─ 侍の美学`
  2. Bio: 推奨案 (110 字)
  3. ウェブサイト: `https://toi-suite.vercel.app/`
  4. アバター: PNG アップロード
  5. ヘッダー: バナー PNG アップロード
- 保存

### Step 3: ピン留めツイート (5 分)
- `bio.md` の **「ピン留めツイート案 候補A 診断誘導型」** を投稿
- 投稿の右上 ⋯ → 「プロフィールに固定表示する」

### Step 4: 自動投稿の API key 設定 (15 分)
- `memory/hp-renewal-x-automation.md` または以下手順:
  1. https://developer.x.com/ で Free 開発者アカウント登録
  2. App 作成 → User authentication で "Read and Write"
  3. Keys and tokens で 4 つ取得
  4. GitHub Secrets に追加 (X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET)
  5. GitHub Actions で workflow_dispatch 手動テスト

## ブランド規約 (CLAUDE.md 準拠)

### 禁止
- ❌ 「うっちー」「UCHY」「Uchy」名乗り表記
- ❌ GitHub リンク (公開ページ全般)
- ❌ アクセスコード文字列の公開掲載
- ❌ 「47歳管理職」表現

### 推奨
- ✅ 「苦徹成珠」(くてつせいじゅ)
- ✅ 「侍の美学」「SAMURAI AESTHETICS」
- ✅ 「成熟した悩める大人」(年齢表記なし)
- ✅ toi-suite.vercel.app URL 明示

## 配色パレット

| 色 | HEX | 用途 |
|---|---|---|
| 漆黒 | #0A0A0F | 背景メイン |
| 黄金 | #D4AF37 | ブランド文字・装飾 |
| 朱赤 | #A52A2A | 印章・アクセント |
| 純白 | #FFFFFF | サブテキスト |
| 鈍色 | #4A4A52 | サブ装飾 |

## フォント

| 用途 | フォント | 色 |
|---|---|---|
| ブランド名「苦徹成珠」 | 篆書体 / 龍門石碑体 / Yuji Boku (Google Fonts) | #D4AF37 |
| サブコピー (日本語横書き) | 明朝体 / Yu Mincho / Noto Serif JP | #FFFFFF |
| URL / ハッシュタグ | サンセリフ / Inter / Noto Sans JP | #D4AF37 (薄め) |
