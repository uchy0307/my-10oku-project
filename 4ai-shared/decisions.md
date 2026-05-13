# 確定方針（絶対遵守）

## プロジェクト原則
- **手動投稿は完全禁止**。完全自動化のみ。日中サラリーマン・週末家族時間が前提
- **PC OFF前提**。GitHub Actions cron による 24/7 クラウド運転
- **既存記事を妥協版で再デプロイしない**。toi-suite水準が基準
- 売上ゼロのままダラダラやらず、詰まったら自動化の別アプローチに即切り替え

## 価格設定
- note 記事: **1本100円**（買い切り）
- メンバーシップ: **500円/月**
- 全11シリーズ共通

## シリーズ別ターゲットペルソナ
- toi-suite（200の問い）: 47歳前後・管理職男女
- 恋愛: 男女全世代
- 健康: 40歳以上
- お笑い: 全世代
- 子育て: 子育て世代と祖父母世代
- ※toiの「47歳管理職」を他シリーズに流用しない

## 戦略転換（2026/05/09）
- 残り10シリーズの新規開発は中止
- toi-suite単独に集中。アプリ付きnote販売
- API連携を基本とし、Bot UI操作は最小化

## GitHub
- username: **uchy0307**（happyhappy0307 / happyhappy4649 は誤り）
- リポジトリ: `my-10oku-project`

## Cron スケジュール
- `note Auto Post`: 03:17 UTC（12:17 JST） / 11:43 UTC（20:43 JST）
- `Self-Heal on Failure`: ワークフロー失敗時のみ自動発火

## 採用済み技術スタック
- 自動化基盤: GitHub Actions
- note 投稿: Playwright + storageState（B-plan / slow & safe）
- YouTube: googleapis YouTube Data API v3 + OAuth refresh token
- TTS: ElevenLabs API
- 台本生成: Gemini API（モデル: `gemini-2.5-flash` で安定）
- Self-Heal 診断: Octokit + Gemini
