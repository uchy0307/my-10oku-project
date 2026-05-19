# Gemini API 完全無料化（Free Tier）切替 手順書

**作成日**: 2026-05-19 深夜（dispatch自動準備）
**所要時間**: 5〜10 分
**コスト**: ¥0
**user 操作**: ブラウザ web 操作のみ・cmd 不要

## 背景

現状：既存 `GEMINI_API_KEY` (Cloud project = 547717022137 / 898426588524) で **prepayment credits 枯渇 = 429 RESOURCE_EXHAUSTED**。YouTube auto pipeline 全停止中。

解決：**billing なしの新 Google Cloud project** で API key を作り、Free Tier（gemini-2.5-flash 1500req/day 無料）に乗り換え。

---

## 手順

### Step 1: 新 Google Cloud project 作成（2分）

1. https://console.cloud.google.com を Chrome で開く（既存 Google アカウントでログイン）
2. 画面上部のプロジェクトドロップダウン → 「**新しいプロジェクト**」
3. プロジェクト名: `claude-free-gemini`（任意）
4. **組織なし** / **billing アカウント割当て なし**（重要・billing 付けると有料枠が優先される）
5. 「作成」クリック → 1分待つ
6. 上部ドロップダウンで新プロジェクトを選択

### Step 2: Generative Language API 有効化（1分）

1. URL を開く：https://console.cloud.google.com/apis/library/generativelanguage.googleapis.com
2. 上部のプロジェクト選択が `claude-free-gemini` になっているか確認
3. 「**有効にする**」ボタンクリック
4. 1分待つ

### Step 3: API key 生成（1分）

1. URL を開く：https://console.cloud.google.com/apis/credentials
2. 「**+ 認証情報を作成**」→「**API キー**」
3. 表示された key 文字列（`AIza...` で始まる40文字程度）を**コピー**
4. （任意）「キーを制限」で「Generative Language API」のみに制限

### Step 4: GitHub Secrets 更新（2分）

1. URL を開く：https://github.com/uchy0307/my-10oku-project/settings/secrets/actions
2. リスト中の `GEMINI_API_KEY` を探す
3. 「**Update**」→ 新 key をペースト → 保存
4. 同じく `GOOGLE_API_KEY` も同じ key で Update（互換性のため両方更新）

### Step 5: 動作確認（任意・3分）

1. https://github.com/uchy0307/my-10oku-project/actions/workflows/youtube_auto.yml
2. 「Run workflow」→ default 設定で起動
3. 1〜3分後に最新 run を開いて Generate script step を見る
4. `[generate_script] attempt=1 finishReason=STOP ... totalTokens=...` のような成功ログが出れば OK
5. もし `429 RESOURCE_EXHAUSTED` が継続するなら API key が反映されていない・Step 4 で正しい secret 更新したか確認

---

## 完了後の状態

- 月 ¥0 で運用継続
- gemini-2.5-flash の Free Tier 1500req/day = 1日6本動画 (42req/day) に余裕
- 既存の prepayment 枠は手付かず（緊急時のフォールバック用に保持）
- 旧 API key（旧 project）は revoke せず温存して OK

## 失敗時のフォールバック

もし Step 2 で「billing が必要」というメッセージが出た場合：
- 「**スキップ**」or 「**今はしない**」で進める
- ある場合は新規 Google アカウントで別 project を作ると確実に free tier

## このファイルについて

- `_FREE_GEMINI_API_SETUP.md` という名前で repo 直下に置いてあります
- 手順完了後はこのファイルは削除して OK
