# note-auto ｜ B案 note自動投稿

> 苦徹成珠。手作業の積み重ねを、機械にも侍の所作で振る舞わせる。

---

## ⚠️ 重要なリスク表記

**note.com の利用規約上、自動投稿は明示的に禁止されています。**
本スクリプトはあくまで「人間の所作をシミュレート」して BAN リスクを下げる試みであり、
アカウント凍結のリスクは残ります。**利用者責任** で使用してください。

---

## B案の方針

A案（公式API利用）は note 側に公開API が無いため不採用。
B案として、Playwright で Chromium をヘッドレス起動し、人間操作をエミュレートします。

### 低速・安全ルール

| 項目 | 値 |
|---|---|
| 1日の最大投稿数 | **2本** |
| 投稿間ランダム遅延 | 3〜7秒 |
| 起動時刻 | cron 2回 / 日（時刻はランダムにずらす） |
| ログイン頻度 | 必要時のみ（セッション保持を試行） |
| エラー時動作 | 即時 abort、queue.json に `status: "error"` 記録 |

---

## ファイル構成

```
note-auto/
├── README.md       ← この文書
├── post.mjs        ← Playwright スクリプト本体（ESM）
└── queue.json      ← 投稿待ち記事キュー
```

---

## 環境変数

| 変数名 | 用途 |
|---|---|
| `NOTE_EMAIL` | note ログインメール |
| `NOTE_PASSWORD` | note ログインパスワード |

GitHub Actions では Secrets として設定してください。
ローカルでは `.env` に記入（gitignore 済）。

---

## queue.json スキーマ

```json
{
  "version": 1,
  "items": [
    {
      "id": "001",                      // 一意ID
      "title": "（記事タイトル）",
      "body": "（本文 Markdown または平文）",
      "publish": false,                 // false=下書き保存 / true=公開
      "status": "pending",              // pending | posted | error
      "scheduled_at": null,             // ISO8601 文字列（任意）
      "posted_at": null,                // 投稿成功時に自動記録
      "error": null                     // エラー時メッセージ
    }
  ]
}
```

---

## ローカル実行

```powershell
# 初回のみ
npm install
npx playwright install chromium

# 実行（1本だけ投稿）
$env:NOTE_EMAIL="your@example.com"
$env:NOTE_PASSWORD="xxxxxxxx"
npm run note:post
```

---

## GitHub Actions 運用

`.github/workflows/note_auto_post.yml` が 1日2回、ランダム時刻 cron で起動します。
失敗時は GitHub Issue が自動起票（gh CLI 経由）。
成功時は queue.json の差分が main に commit back されます。

---

## 既知の停止条件

- note 側 CAPTCHA 表示時 → 即 abort（Playwright で突破しない方針）
- DOM セレクタ変更時 → セレクタを post.mjs 内 `SELECTORS` 定数で一元管理、要更新
- ネットワーク不通 → リトライせず abort
