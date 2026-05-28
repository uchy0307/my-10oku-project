# lp.uchy0307.uk を samurai-lab プロジェクトに移行する手順

samurai-lab は `https://2b22aa38.samurai-lab.pages.dev` に配信中。
これを `lp.uchy0307.uk` で開けるようにする。

## 所要時間
- ダッシュボード操作: 約 3 分
- SSL 証明書発行待ち: 2〜10 分

---

## STEP 1: 旧プロジェクト (uchy-lp) からドメインを外す

> 注意: 新UIでは「⋯」メニューに「Cloudflare DNS の管理」しか出ない。Remove は **ドメイン名そのものをクリック** した先の詳細ページにある。

### 方法A: ドメイン詳細ページから削除 (推奨)
1. https://dash.cloudflare.com を開く
2. 左メニュー **「Workers & Pages」** をクリック
3. プロジェクト一覧から **`uchy-lp`** をクリック
4. 上部タブの **「カスタムドメイン」** をクリック
5. **`lp.uchy0307.uk` のドメイン名 (テキスト部分) を直接クリック** ← ここがポイント
6. 詳細ページが開く → 右上 or 下部の **「Remove domain」** / **「ドメインを削除」** ボタンを押す
7. 確認ダイアログで **「Remove」** を押す

### 方法B: DNS レコード削除で間接的に外す
詳細ページの Remove ボタンも見つからない場合:
1. ダッシュボードのトップに戻る (ホーム)
2. ドメイン一覧から **`uchy0307.uk`** をクリック
3. 左メニュー **「DNS」** → **「レコード」**
4. `lp` の CNAME レコード (値が `uchy-lp.pages.dev` などのもの) を見つけ、右の **編集 → 削除**
5. これで Pages 側のカスタムドメインも自動で外れる (1〜2分)

### 方法C: wrangler CLI (PowerShell から)
```powershell
cd C:\Users\user\Documents\10oku-project
npx wrangler pages domain remove uchy-lp lp.uchy0307.uk
```
※ wrangler が `pages domain` サブコマンドを持たないバージョンの場合は方法A/Bへ。

> 旧サイトは数秒〜数十秒で 404 になる。同時に samurai-lab 側でも作業すれば実質ダウンタイムなし。

---

## STEP 2: 新プロジェクト (samurai-lab) にドメインを付ける

1. 「Workers & Pages」一覧に戻る
2. **`samurai-lab`** をクリック
3. 上部タブの **「カスタムドメイン」** をクリック
4. **「カスタムドメインを設定する」** (青ボタン) をクリック
5. ドメイン入力欄に **`lp.uchy0307.uk`** を入力 → **「続行」**
6. CNAME プレビュー画面で内容を確認 → **「ドメインを有効化」**

`uchy0307.uk` の DNS が Cloudflare に乗っているなら、CNAME は自動追加される。

CLI 派は:
```powershell
cd C:\Users\user\Documents\10oku-project
npx wrangler pages domain add samurai-lab lp.uchy0307.uk
```

---

## STEP 3: 動作確認

1. **「Custom domains」** に `lp.uchy0307.uk` が出たら、Status が **「Active」** になるまで待つ (2〜5 分)
2. ブラウザで `https://lp.uchy0307.uk` を開く → samurai-lab の中身が表示されればOK
3. もし `ERR_SSL_VERSION_OR_CIPHER_MISMATCH` などが出たら、SSL 証明書発行待ちなので 5〜10 分後に再アクセス

---

## トラブルシュート

### 「ドメインが既に他プロジェクトで使われています」エラーが出る
→ STEP 1 で削除されていない。再度 uchy-lp 側で Custom domains を確認。

### Status が `Pending` のまま動かない
→ 30 分待っても Active にならない場合、ダッシュボードで一度削除 → 再追加。
→ または `uchy0307.uk` の DNS で `lp` の CNAME レコードが正しく `samurai-lab.pages.dev` を指しているか確認。

### 旧 uchy-lp プロジェクトはどうする？
→ ドメイン外しただけなら残しても無害 (デフォルトの `*.pages.dev` URL は生きてる)。
完全に消したい場合: samurai-lab で 24h 稼働確認後、Workers & Pages → uchy-lp → Settings → 最下部 **「Delete project」**。
