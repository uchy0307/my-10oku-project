# toi-suite ｜ 6軸分析システム（別repo参照）

本ファイルは「10oku-project マスタリポジトリ」から **toi-suite 本体リポジトリ** への参照ドキュメントです。
コード本体は toi-suite repo に既存（P45で実装済）のため、ここには **コードを置きません**。

---

## リポジトリ

- **本体repo**: `https://github.com/uchy0307/toi-suite`
- **Vercel本番URL**: （Vercel ダッシュボードにて確認）

---

## 6軸分析システム概要

toi-suite は「歴史×ビジネス」を**6軸**で多次元分析するWebアプリ:

| 軸 | 内容 |
|---|---|
| 1. 人物軸 | 武将・思想家・経営者の人物像分析 |
| 2. 合戦軸 | 戦略・戦術・勝因敗因の構造分解 |
| 3. 文化軸 | 茶道・武士道・美学の系譜 |
| 4. 経済軸 | 楽市楽座・通貨改革・産業の生成 |
| 5. 思想軸 | 朱子学・陽明学・国学の影響 |
| 6. 地理軸 | 街道・港・城下町のネットワーク |

---

## 連携ポイント

10oku-project（本repo）の YouTube自動投稿パイプラインは、toi-suite の分析結果（DB: Supabase）から
**「次に動画化すべきテーマ」** を取得する設計です（フェーズ2で実装）。

現状は `youtube/topics.json` の手動キュレーションで稼働。

---

## デプロイフロー

1. toi-suite repo に push
2. Vercel が自動検知 → ビルド → デプロイ
3. 本repo の `.github/workflows/toi_suite_deploy.yml` は補助的なdeploy hookのみ

---

## 開発者向け

詳細仕様・APIエンドポイント・コンポーネント設計は toi-suite repo の `README.md` を参照してください。
