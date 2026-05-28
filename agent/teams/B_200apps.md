---
team: B
name: 200アプリ改善班
manager: Main Claude
escalation_to: 総括班
---

# B班 ミッション

## 目的
toi-suite (200の問い AI対話アプリ統合スイート) の品質向上と購読転換率改善。

## 現状 (2026-05-24)
- **URL**: https://toi-suite.vercel.app/
- **構造**: React 18 + Vite 5 + Supabase + Recharts
- **収益モデル**: 月額500円購読 + note記事ごとのアクセスコード
- **改善案ドキュメント**: `apps/toi-suite-improvements.md`
- **Phase 1実装ファイル**: `apps/toi-suite-changes/`（公開LP + 3問サンプル）

## KPI

| 指標 | 現状 | 目標 (3ヶ月) |
|---|---|---|
| 月額500円購読数 | 未公開 | **50人** |
| 訪問→note購入転換率 | 推定1% | **5-10%** |
| MAU | 未測定 | 計測開始 |
| アプリ完了率 | 未測定 | 30%↑ |

## 即着手タスク (P0)

### B-1. Phase 1 デプロイ
`apps/toi-suite-changes/INSTALL.md` 手順で公開LP + 3問サンプルをデプロイ。
**期待効果**: 訪問→note購入転換率 1% → 5-10%

### B-2. モバイル最適化 (Phase 2)
- タップ領域48x48px以上確認
- PWA対応（vite-plugin-pwa）
- safe-area対応

### B-3. アプリ品質バラツキ調査
200本のうちどれが完了率高い/低いか統計。
低い10本を改善（プロンプト見直し、UI調整）。

## 中長期タスク (P1-P2)

### B-4. ネイティブアプリ化検討
- Capacitor or React Native への移行コスト/リターン
- iOS/Android App Store配信
- 月額課金（StoreKit / Play Billing）対応

### B-5. エンゲージメント機能
- デイリー質問（PWA push）
- ストリーク
- 過去履歴比較

### B-6. 6軸分析の信頼性アップ
- Gemini strict JSON mode
- 分布グラフ追加（「あなたは上位XX%」）

## 連携
- **A班**: アクセスコード仕様統一、note誘導テキスト
- **E班**: HP→toi-suite誘導動線

## エスカレーション基準
- 月額購読 30人未達（3ヶ月時点）
- Vercel無料枠超過
- Supabase無料枠超過
