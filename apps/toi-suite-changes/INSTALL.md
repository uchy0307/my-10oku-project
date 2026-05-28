# toi-suite Phase 1 改修 インストール手順

> 2026-05-24 · Claude Code 実装
> 内容: 公開LP + 3問無料診断追加（ゲートで弾く前に価値体験を提供）

---

## 変更内容まとめ

### 新規ファイル（2つ）
1. `src/pages/Landing.jsx` — トップ公開ヒーロー画面
2. `src/pages/QuickSample.jsx` — 3問無料診断

### 修正ファイル（1つ）
3. `src/App.jsx` — ルート構成変更

### 新しいルート構成

| URL | 中身 | アクセス制限 |
|---|---|---|
| `/` | **新規** Landing | 🌐 公開 |
| `/sample` | **新規** QuickSample（3問診断） | 🌐 公開 |
| `/catalog` | 既存Catalog | 🔒 マスターコード |
| `/:id` | 既存アプリ個別ページ | 🔒 個別コード |

---

## インストール方法

### Option A: ローカルでtoi-suiteクローンして反映

```powershell
# 1. toi-suite をクローン（既にあるならスキップ）
cd C:\Users\user\Documents
git clone https://github.com/uchy0307/toi-suite.git toi-suite-local
cd toi-suite-local

# 2. ブランチを切る
git checkout -b feat/public-landing

# 3. ファイル3点をコピー
copy ..\10oku-project\apps\toi-suite-changes\src\pages\Landing.jsx     src\pages\Landing.jsx
copy ..\10oku-project\apps\toi-suite-changes\src\pages\QuickSample.jsx src\pages\QuickSample.jsx
copy ..\10oku-project\apps\toi-suite-changes\src\App.jsx               src\App.jsx -Force

# 4. ローカル動作確認
npm install
npm run dev
# → http://localhost:5173/ で Landing が表示されるか確認
# → / → /sample 押下で診断が動くか
# → /catalog がマスターコード要求するか

# 5. 問題なければコミット&プッシュ
git add src/pages/Landing.jsx src/pages/QuickSample.jsx src/App.jsx
git commit -m "feat: 公開LP + 3問無料診断追加（収益化導線改善）"
git push -u origin feat/public-landing

# 6. GitHub上で main にPR作成 → Vercel が自動デプロイ
```

### Option B: GitHub Web UI でブラウザから反映

1. https://github.com/uchy0307/toi-suite を開く
2. `src/pages/Landing.jsx` を新規作成 → 内容をペースト
3. `src/pages/QuickSample.jsx` を新規作成 → 内容をペースト
4. `src/App.jsx` を編集 → 内容を上書きペースト
5. コミット → Vercel自動デプロイ

---

## 動作確認チェックリスト

デプロイ後、 `https://toi-suite.vercel.app/` で確認：

- [ ] トップにLandingが表示される（紫っぽいゴールド配色のヒーロー）
- [ ] 「🌀 3問で自分を診断（無料）」ボタンで `/sample` に遷移
- [ ] 3問選択完了後、診断結果（侍型/求道型/彷徨型/兆し型）が表示される
- [ ] 結果画面の「📝 note記事を見る」が新タブで `note.com/happy_happy_4649` を開く
- [ ] 結果画面の「既にコードを持っている →」で `/catalog` に遷移
- [ ] `/catalog` で従来通りマスターコード入力フォームが出る
- [ ] マスターコード `TOI-MASTER-P7S4KK` で従来通り200アプリカタログが開く
- [ ] 個別アプリ（例 `/003`）への直接アクセスは従来通り動く
- [ ] `/000` メタアプリのMasterOnlyGateも従来通り動く

---

## 期待効果（推定）

- 初見訪問者の離脱率: 大幅減（コンセプト理解→診断体験→課金検討の自然な流れ）
- note記事への流入: 増（QuickSample結果画面に明確な誘導CTA）
- 訪問→note購入転換率: 推定 1% → 5-10%

---

## Phase 2 以降（次セッション以降）

`apps/toi-suite-improvements.md` 参照。次の優先順位:
- P2: PWA対応 + モバイル最適化
- P3: エンゲージメント（デイリー質問・ストリーク・履歴比較）
- P4: 6軸信頼性アップ（Gemini strict JSON）
- P5: SEO/OGP

---

## トラブルシューティング

### Landingが表示されず白画面
- ブラウザのキャッシュ削除 (Ctrl+Shift+R)
- localStorage の `toi_master_v1` を削除して再アクセス
- Vercelデプロイログでビルドエラー確認

### `/sample` で「Cannot find module」エラー
- `src/pages/QuickSample.jsx` が正しい場所にあるか確認
- ファイル名のtypo確認（QuickSample.jsx）

### 既存ユーザーが `/` でカタログに辿り着けない
- localStorage `toi_master_v1=1` の人は自動でCatalogGateバイパス
- それでもLandingが優先表示される → 新仕様、`/catalog` をブックマーク誘導

### CatalogのBackBarで「カタログに戻る」リンクが404
- BackBar内 `navigate("/")` を `navigate("/catalog")` に変更済み（修正版App.jsxに反映済み）
