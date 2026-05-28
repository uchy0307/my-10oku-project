# Cloudflare 固定URL 設定手順

## ゴール
固定URLを取得し、cmdを閉じてもPC再起動してもスマホPWAからボタン操作が継続できる状態にする。

## 必要なもの
- Cloudflareアカウント（無料・既存があればそれを使用）
- クレジットカード（ドメイン購入用）
- 所要時間：60分

## 費用
- ドメイン代：$8〜$12/年（.com）または $1〜$5/年（.xyz, .me等）
- Cloudflare Tunnel自体：無料（永久）

---

## 手順

### ステップ1：Cloudflareアカウント作成（10分）

1. https://dash.cloudflare.com/sign-up を開く
2. メール・パスワード登録
3. メール認証完了

### ステップ2：ドメイン購入（15分）

1. Cloudflareダッシュボード左メニュー「Domain Registration」→「Register Domains」
2. 短くて覚えやすいドメインを検索（例：`uchy.xyz` $1/年）
3. 購入手続き（クレジットカード入力）
4. 数分でドメインがアカウントに紐付く

### ステップ3：cloudflaredログイン（5分）

1. PC で `start_button_server.bat` のサーバーは動いたまま、別の **PowerShell** を開く
2. 以下を実行：
```powershell
cloudflared tunnel login
```
3. ブラウザが開く → 購入したドメインを選択 → Authorize クリック
4. cmd に `successfully authenticated` 表示で完了

### ステップ4：トンネル作成（5分）

```powershell
cloudflared tunnel create uchy-pc
```

→ `Created tunnel uchy-pc with id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` と表示される。
このトンネル ID をメモ。

### ステップ5：DNS設定（5分）

```powershell
cloudflared tunnel route dns uchy-pc pc.uchy.xyz
```

（`pc.uchy.xyz` の部分は購入ドメインに合わせて変更）

### ステップ6：設定ファイル作成（5分）

ファイルパス：`C:\Users\user\.cloudflared\config.yml`

内容（テキストエディタで作成）：
```yaml
tunnel: uchy-pc
credentials-file: C:\Users\user\.cloudflared\<TUNNEL_ID>.json

ingress:
  - hostname: pc.uchy.xyz
    service: http://127.0.0.1:7373
  - service: http_status:404
```

※ `<TUNNEL_ID>` をステップ4のIDに、`pc.uchy.xyz` をご自身のドメインに置き換え。

### ステップ7：Windowsサービスとして登録（5分・要管理者権限）

PowerShellを **管理者として実行** で開いて：
```powershell
cloudflared service install
```

→ 自動起動するWindowsサービスに登録される。これで cmd を閉じてもPC再起動でも自動で動く。

### ステップ8：PWA設定更新（1分）

スマホPWAの「サーバー設定」を開いて、URLを以下に変更：
```
https://pc.uchy.xyz
```

これで永続URL運用開始。

---

## 困ったら

- ドメイン名は自由（短い方が打ちやすい）
- DNSの伝搬に数分かかる場合あり
- サービス起動確認：`Get-Service cloudflared`

---

## 私（Claude）の代行可能範囲

- 設定ファイル作成（config.yml）：私が書きます
- bat化したセットアップ：書きます
- アカウント作成・購入・login認証：うっちー様の手作業必須

ステップ3まで進んだらお知らせください。残りは私側で代行＋スクリプト化します。
