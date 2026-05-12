# note-auto ｜ B案 note自動投稿（下書き編集型・新方針）

> 苦徹成珠。手作業の積み重ねを、機械にも侍の所作で振る舞わせる。

---

## ⚠️ 重要なリスク表記

**note.com の利用規約上、自動投稿は明示的に禁止されています。**
本スクリプトはあくまで「人間の所作をシミュレート」して BAN リスクを下げる試みであり、
アカウント凍結のリスクは残ります。**利用者責任** で使用してください。

---

## なぜ「下書き編集型」に切り替えたか

完全自動ログイン（NOTE_EMAIL/NOTE_PASSWORD 入力）は note 側 bot 検知に
引っかかって失敗するケースが多発した。新方針:

1. **ログインは人間が手動で1回だけ実施**（CAPTCHA / 2FA 全部突破できる）
2. その時の認証情報を Playwright `storageState` として書き出す
3. 以降の自動実行は `storageState` を読み込んでログイン済状態で起動
4. note.com 上に**事前に作成しておいた下書き**（draftId）に本文を流し込む
5. 「下書き保存」or「公開」をクリック

これにより、自動化が触るのは「下書き編集」だけになり、bot 検知の最大の壁である
ログインフローを通過する必要がなくなる。

---

## 低速・安全ルール（B案として据え置き）

| 項目 | 値 |
|---|---|
| 1日の最大投稿数 | **2本** |
| 投稿間ランダム遅延 | 3〜7秒 |
| 起動時刻 | cron 2回 / 日（時刻はランダムにずらす） |
| エラー時動作 | 即時 abort、queue.json に `status: "error: ..."` 記録 |

---

## ファイル構成

```
note-auto/
├── README.md             ← この文書
├── post.mjs              ← Playwright スクリプト本体（下書き編集型）
├── capture-session.mjs   ← ローカル用：手動ログイン→storageState保存
├── queue.json            ← 投稿待ち記事キュー（draftId 必須）
└── storageState.json     ← ローカル取得用（.gitignore済・絶対commit禁止）
```

---

## セットアップ手順（初回 / cookie失効時）

### 1. ローカルで手動ログインして storageState を取得

```powershell
cd C:\Users\user\Documents\10oku-project
npm install
npx playwright install chromium
npm run note:capture
```

1. Chromium が起動する
2. 表示された note.com のログイン画面で**手動でログイン**（CAPTCHA / 2FA も人間で突破）
3. ログイン完了したら、ターミナルに戻って Enter キーを押す
4. `note-auto/storageState.json` が生成される（`.gitignore` 済）

### 2. GitHub Secret `NOTE_STORAGE_STATE` に登録

1. `note-auto/storageState.json` の中身（JSON全体）をクリップボードにコピー
2. GitHub → Settings → Secrets and variables → Actions → New repository secret
3. Name: `NOTE_STORAGE_STATE` / Value: 貼り付け
4. （旧 `NOTE_EMAIL` / `NOTE_PASSWORD` は不要なので削除してOK）

### 3. note.com で下書きを事前作成

note.com で記事を1本「下書き保存」しておき、URL から `draftId` を控える。
URL 例: `https://note.com/notes/n1234abcdef/edit` → draftId は `n1234abcdef`。

### 4. queue.json に draftId を埋める

```json
{
  "version": 2,
  "items": [
    {
      "id": "001",
      "draftId": "n1234abcdef",
      "title": "侍の美学・第一話",
      "body": "本文……改行は\\n",
      "publish": false,
      "status": "pending",
      "scheduled_at": null,
      "posted_at": null,
      "error": null
    }
  ]
}
```

---

## queue.json スキーマ（v2）

| フィールド | 説明 |
|---|---|
| `id` | 一意ID |
| `draftId` | note.com 側の下書きID（事前に作成して URL から取得） |
| `title` | タイトル（空文字なら変更しない） |
| `body` | 本文（改行 `\n` 区切り） |
| `publish` | `false`=下書き保存 / `true`=公開設定→公開 |
| `status` | `pending` / `draft_saved` / `published` / `error: ...` |
| `scheduled_at` | ISO8601（任意） |
| `posted_at` | 投稿成功時に自動記録 |
| `error` | エラー時メッセージ |

---

## ローカル実行

```powershell
$env:NOTE_STORAGE_STATE = Get-Content -Raw note-auto\storageState.json
$env:NOTE_HEADLESS = "false"   # ブラウザを表示したい場合
npm run note:post
```

`NOTE_HEADLESS=false` をつけると Chromium ウィンドウが表示され、動作を目視確認可能。

---

## GitHub Actions 運用

`.github/workflows/note_auto_post.yml` が 1日2回 cron で起動する。
失敗時は `self-heal` workflow が自動的にエラーを Gemini に診断させ
GitHub Issue を起票する（`.github/workflows/self-heal.yml` 参照）。

---

## 既知の停止条件

- **cookie 失効**: storageState の cookie が切れたら 401 でエラーになる → 再取得
- DOM セレクタ変更時 → `post.mjs` 内 `SELECTORS` 定数を一元更新
- ネットワーク不通 → リトライせず abort
- CAPTCHA 表示時 → 即 abort（突破しない方針は据え置き）
