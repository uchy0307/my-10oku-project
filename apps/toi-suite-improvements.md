# toi-suite 改善提案ドキュメント
> 2026-05-24 · Claude Code 監査
> 対象リポジトリ: `uchy0307/toi-suite` (Public)
> 対象URL: https://toi-suite.vercel.app/

## 1. 現状の構造把握

### スタック
- **フロント**: React 18 + Vite 5 + React Router 6
- **バックエンド**: Supabase (Row-Level Security付き)
- **可視化**: Recharts (6軸レーダー)
- **AI**: Gemini API（Vercel Edge Function経由）
- **共有**: html2canvas (スクショ) + QRCode

### 機能
- 200の自己理解アプリ（カタログ式）
- アクセスコード認証3層（CatalogGate / MasterOnlyGate / AppGate）
- 6軸分析（決断力・精神力・適応力・洞察力・規律心・大義）
- LocalStorageで履歴保持

### コア課題
**ユーザーが「価値を体験する前にゲートで弾かれる」構造**になっており、収益化を阻害している可能性大。

---

## 2. 高インパクト × 低工数の改善（優先順位順）

### 🥇 Priority 1: 公開ヒーロー＋無料お試し（収益直結）

**現状**:
```
visitor → サイト訪問 → いきなりCatalogGateで「マスターコード入力」プロンプト → 離脱
```

**改善後**:
```
visitor → ヒーロー画面（コンセプト説明＋3問お試しCTA）
       → 3問無料で6軸ミニ診断
       → 結果画面で「あなたの傾向は『〇〇型』」
       → 「もっと深く知るには? → note記事200円購入 → アクセスコード取得」
       → コード入力でフル機能解錠
```

**実装**:
- `src/pages/Landing.jsx` 新規作成（公開ページ）
- 既存`CatalogGate` を `/catalog` ルートに移動
- 3問サンプル `src/pages/QuickSample.jsx` 新規
- nostalgia/empathy 系コピーで「自分を理解したい大人」を捕まえる

**期待効果**: 訪問→note購入転換率 1% → 5-10%

---

### 🥈 Priority 2: モバイルファースト再設計

**現状の不明点**: モバイル最適化の程度（要実機確認）

**チェックリスト**:
- [ ] タップ領域: 全ボタン48x48px以上か
- [ ] フォントサイズ: 16px以上か
- [ ] 横スクロール発生していないか
- [ ] safe-area-inset 対応か（ノッチ端末）
- [ ] PWA対応（vite-plugin-pwa 導入）

**実装**:
- ダッシュボード側で導入済みの`vite-plugin-pwa`をtoi-suiteにも適用
- A2HS（Add to Home Screen）プロンプト
- Service Worker でアセットキャッシュ → 初回後の起動爆速化

---

### 🥉 Priority 3: 「日々戻ってくる」エンゲージメント

**現状**: 単発診断で終わり、リピート訪問の動機なし

**追加機能**:
1. **デイリー質問** - 毎日1問届く（PWA push or Web push）
2. **ストリーク**: 「7日連続回答中🔥」
3. **過去の自分との比較**: 「3ヶ月前のあなた vs 今のあなた」レーダー重ね表示
4. **結果シェア**: 既存`html2canvas`活用、QRコード付きで「やってみて」と友達誘導

**実装**:
- Supabase に `user_responses` 履歴テーブル（既存スキーマ確認）
- 比較ビュー: Recharts 2レーダー重ね描画
- 通知: 当面は Web Notifications API のみ（PWA push は後回し）

**期待効果**: DAU/WAU比 改善 → 月額継続率↑

---

### Priority 4: 6軸分析の信頼性アップ

**現状**: 10問→Gemini scoring → 6軸

**改善**:
- Gemini の出力を**JSON schema strict mode**に変更（不安定さ削減）
- スコアリングの根拠を結果画面に表示（透明性）
- スコアの統計的分布（「あなたの規律心は上位15%」）を匿名集計から算出

**実装**:
- Supabase: 6軸スコアの集計ビュー作成
- 結果画面に「分布グラフ」追加

---

### Priority 5: SEO / 流入導線

**現状不明**: meta tags, OGP, sitemap

**チェック必要**:
- [ ] index.html に description, OGP, twitter cards
- [ ] /sitemap.xml 自動生成
- [ ] 各app page (`/:id`) にユニークtitle/description

**実装**:
- `vite-plugin-sitemap` 導入
- public/robots.txt
- 各 app page に react-helmet で動的meta

**期待効果**: Google検索流入 → note記事購入導線

---

## 3. 「やってはいけない」改修

- ❌ **デザイン全とっかえ**: 既存warm earth tonesは差別化要素なので維持
- ❌ **アクセスコード認証の廃止**: 収益モデルの根幹（noteとの結びつき）
- ❌ **無料化**: noteの売上を毀損
- ❌ **Reactから別framework移行**: 既存資産を捨てることに

---

## 4. 段階的実装プラン（4週間想定）

### Week 1: P1（公開LP + 3問サンプル）
- Landing.jsx 実装
- QuickSample.jsx 実装  
- 既存ルーティング調整
- → **これだけで note購入転換率が大幅改善する可能性**

### Week 2: P2（モバイル最適化 + PWA）
- レスポンシブ点検
- PWA化
- safe-area対応

### Week 3: P3（エンゲージメント基盤）
- Supabase履歴テーブル設計
- 過去比較レーダー
- 共有強化

### Week 4: P4 + P5（信頼性 + SEO）
- Gemini strict JSON
- 分布ビュー
- meta tags / sitemap

---

## 5. すぐ着手できる「30分パッチ」

最小工数で可能な改善：

1. **`public/og-image.png` 作成** + `index.html` に OGP追加 (15分)
2. **「使い方ガイド」モーダル** をCatalogGate直前に表示 (15分)
3. **「note記事を見る」リンク** を CatalogGate に追加 (5分)
4. **エラー時のフォールバックUI** 改善 (15分)

→ 合計1時間で「初見訪問者の混乱」を大きく減らせる

---

## 6. 次セッション着手時の優先サイクル

1. ローカルでtoi-suite cloneして実機確認
2. モバイル/PCで全画面遷移を点検（スクショ撮りながら）
3. P1 (公開LP) を**プロトタイプ実装**してプレビュー
4. うっちー様確認 → OKなら本実装 → デプロイ

---

## 7. メモ

- repo Public化済み（2026-05-24 確認）
- マスターキー: `TOI-MASTER-P7S4KK`（運用機密、リポジトリには出さない）
- noteのアクセスコード `006-200` は `note-auto/access_codes.json` で管理（gitignore済）
- toi-suiteのコード認証ロジックは `src/codeHashes.js`（次回読込予定）
