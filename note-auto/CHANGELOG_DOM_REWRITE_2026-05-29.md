# post.mjs DOM 書換 changelog (2026-05-29 深夜)

## 背景
- CLAUDE.md 5/29 引き継ぎ書: 「post.mjs DOM 変更不適合 / editor.note.com → note.com 統合後の新 DOM」
- 旧 post.mjs はラスト稼働時 attach=0 / 境界線移動失敗 / 全文有料化 のいずれかが起きうる状態

## 実施 (自走モード)

### 1. DOM dump 取得 (note-auto/_dom_dump.json, _dom_dump_publish.json)
- `_dom_dump.mjs` を id 引数受付に変更 (#112 は draftId 空のため #150 で取得)
- 新規 `_dom_dump_publish.mjs` で /publish/ ページも取得

### 2. 確定した DOM 変化

| 機能 | 旧 selector | 新 selector / 構造 |
|---|---|---|
| 本文エディタ | `.ProseMirror` | **同じ** (変化なし) |
| 下書き保存ボタン | `button:has-text("下書き保存")` | **同じ** |
| プラス(+)メニュー開く | 8通り推測 OR 結合 | **`button[aria-label="メニューを開く"]`** (確定) |
| ファイル選択 | 複数推測 | `button:has-text("ファイル")` (plus menu 展開後表示) |
| **有料エリア設定** | `button:has-text("有料エリア設定")` on /publish/ | **廃止** → /edit/ plus menu の **「有料エリア指定」ブロック** に移行 |
| 公開に進む | (なし: /publish/ 直接遷移) | `button:has-text("公開に進む")` 追加 |
| 投稿する | `button:has-text("投稿する")` | **同じ** (/publish/ 上) |
| paid radio | `input[type="radio"][name="is_paid"]` | **同じ** (value=free/paid) |

### 3. post.mjs 変更内容

#### SELECTORS 整理 (確認済みのもののみ残す)
- `plusMenuOpen` を 1つに絞った (確定: `button[aria-label="メニューを開く"]`)
- `paidConfigBtn` を `paidConfigBtn_LEGACY` にリネーム (新UIで廃止)
- 新規 `paidAreaInsertBtn: 'button:has-text("有料エリア指定")'`
- 新規 `proceedToPublishBtn: 'button:has-text("公開に進む")'`

#### 新規関数: `insertPaidBoundary(page)`
- /edit/ で 🔑 H2 の直前にカーソル移動
- Enter で新ブロック作成
- プラスメニュー開く → 「有料エリア指定」クリック
- 戻り値: `{ ok: boolean, reason?: string }`

#### `editDraft` フロー変更
- body 入力 + 添付の後、`USE_NEW_BOUNDARY && runPaid` 時に `insertPaidBoundary()` 呼出
- その後の `/publish/` での「有料エリア設定」ボタン操作は `USE_NEW_BOUNDARY=true` なら skip
- legacy 動作も残してある (`NOTE_USE_NEW_BOUNDARY=false` で旧動作)

#### 環境変数
- `NOTE_USE_NEW_BOUNDARY` (default ON / `false` で旧動作) — 新 boundary 挿入フロー切替

## 未検証 (要うっちー様確認)

⚠️ 以下は実際に投稿してみないと判明しません:
1. `insertPaidBoundary()` で挿入された「有料エリア指定」ブロックが note の publish パイプライン的に正しく「境界線」として認識されるか
2. /publish/ の paid radio + 価格 + 「投稿する」フローは旧通り動くか (DOM dump からは動きそう)
3. プラスメニュー開く → 「ファイル」クリック で添付 docx upload が動くか (filechooser event 周りは未変更)

## 推奨テスト手順 (うっちー様朝起きたら)

```bash
# 1. ドライラン (ATTACH_ONLY モード = 公開せず添付のみ verify)
NOTE_TEST_ATTACH_ONLY=true node note-auto/post.mjs --ids=150 --max=1

# 2. 単独 publish テスト (#150 だけ実 publish — 注意: 本番に出る)
node note-auto/post.mjs --ids=150 --max=1
# → 失敗時は NOTE_USE_NEW_BOUNDARY=false で旧 flow リトライ
NOTE_USE_NEW_BOUNDARY=false node note-auto/post.mjs --ids=150 --max=1

# 3. 成功したら通常運用に戻す
node note-auto/post.mjs --max=3
```

## ロールバック方法

```bash
git diff note-auto/post.mjs   # 確認
git checkout note-auto/post.mjs  # 取消し
```

## ファイル

- `note-auto/post.mjs` — 本修正対象
- `note-auto/_dom_dump.mjs` — id 引数化に変更
- `note-auto/_dom_dump_publish.mjs` — 新規 (/publish/ DOM 取得)
- `note-auto/_dom_dump.json` — /edit/ DOM サンプル
- `note-auto/_dom_dump_publish.json` — /publish/ DOM サンプル
- `note-auto/_check_queue_112.py` — queue.json item チェッカー
