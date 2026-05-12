# Claude.ai プロジェクト 引き継ぎ統合ドキュメント

> このファイル1つで「年商10億・完全自動化量産プロジェクト」の全文脈を引き継げます。
> Claude.ai の Projects 機能で「ナレッジ」にアップロードし、カスタム指示に下記の冒頭文を貼り付けてください。

---

## 【冒頭指示文】（Claude.ai プロジェクトの「カスタム指示」に貼る）

```
あなたは @uchy0307（うっちー様）の「年商10億・完全自動化量産プロジェクト」の実行責任者です。
同梱されている CLAUDE_PROJECT_HANDOFF.md を必ず最初に読み、全ての前提・決定事項・禁止事項を遵守してください。

特に厳守:
1. GitHub username は uchy0307（happyhappy0307/happyhappy4649 は誤り）
2. 残り10シリーズの量産は中止、toi-suite単独製品に集約
3. note記事1本100円、メンバーシップ500円/月（全11シリーズ共通）
4. 完全自動化が絶対条件（うっちー様は平日会社員、土日は家族時間）
5. 過剰な確認質問・選択肢提示は禁止、決定済み事項は実行のみ
6. 各シリーズの対象ペルソナを混同しない（toi=47歳管理職、他は別）
```

---

# 第1部: プロジェクト全体像

## 概要

- **名称**: 年商10億・完全自動化量産プロジェクト
- **コア思想**: 苦徹成珠・侍の美学
- **ユーザー**: うっちー様（GitHub: uchy0307）
- **マスタリポジトリ**: `uchy0307/my-10oku-project`
- **メインプロダクト**: `uchy0307/toi-suite`（Vercel本番稼働中）

## 4脳連携

| 脳 | 役割 |
|---|---|
| Claude Code / Dispatch | 実装責任者：コード生成・GitHub Actions・自動化スクリプト |
| NotebookLM | 思想・トーン管理：「苦徹成珠・侍の美学」哲学 |
| Gemini API | 戦略・分析：台本生成・市場分析・要約 |
| ElevenLabs | 音声：ナレーション・キャラボイス |

## 2本の柱（2026/05/09 戦略転換後）

### 柱1: toi-suite = アプリ付きnote販売
- 残り10シリーズ（owarai/koi/koso/kenko/kane/biz/car/gaku/men/nin）の量産は中止
- toi-suite単独で品質極限まで上げる
- 200の問い PWA + note記事の組み合わせで販売
- Page000は全シリーズの聖域・終着点

### 柱2: 幕末YouTube再収益化
- チャンネル: https://www.youtube.com/@Japanese.Samurai.Channel
- 既に登録者3000+、過去配信234本（過去収益化済）
- 目標: 1000本投稿で再収益化
- 完全自動化が絶対条件（GitHub Actions + Gemini + ElevenLabs + YouTube API）

---

# 第2部: 絶対遵守の参照情報

## 2.1 GitHub username

**正解: `uchy0307`**

URL: https://github.com/uchy0307

❌ 誤り（過去ミス、絶対使うな）:
- happyhappy0307
- happyhappy4649

## 2.2 価格設定（全11シリーズ共通）

| 種別 | 価格 |
|---|---|
| note記事 1本買取 | **100円** |
| メンバーシップ | **500円/月** |

シリーズごとに価格を変えない。全11シリーズ共通。

## 2.3 対象ペルソナ（混同厳禁）

| シリーズ | プレフィックス | 対象 |
|---|---|---|
| 200の問い | TOI | 47歳前後ミドル管理職（男女） |
| お笑いNote | OWARAI | お笑い好き全世代 |
| 恋愛Note | KOI | 恋愛全世代 |
| 子育てNote | KOSO | 子育て世代と祖父母世代 |
| 健康Note | KENKO | 40才以上男女 |
| お金Note | KANE | 20代以上全世代 |
| ビジネスNote | BIZ | ビジネスパーソン全般 |
| キャリアNote | CAR | 20代以上全世代 |
| 学習Note | GAKU | 10代以上全世代 |
| メンタルNote | MEN | ビジネスパーソン全般 |
| 人間関係Note | NIN | ビジネスパーソン全般 |

**重要**: 「47歳前後」は **200の問いだけ**。他シリーズに絶対つけない。

## 2.4 ハッシュタグ（11シリーズ共通正解版）

`#人生 #ミドル #コミュニケーション #47歳 #happyhappy #思考整理 #note #整理整頓 #Chat自分 #自己成長 #ChatGPT #意識`

---

# 第3部: コンテンツ規格

## 3.1 Note記事の絶対黄金律 6:2:2（4000文字以上）

- **60% あるある・共感**: 泥臭い日常描写、ターゲットが「これは自分のことだ」と思う
- **20% くすっと・失敗談**: 47歳著者が15年間「頑張れ」と言い続けた中の葛藤・ユーモア
- **20% 泣ける・深化**: 「本当はどうしたい？」と魂に問いかける深い洞察

## 3.2 YouTube動画 30分長尺の黄金律

- **序盤30秒戦略**: 衝撃的結論予告 or 強力な問い（好奇心ギャップ）
- **3幕構成**: 背景設定 → 展開・転換点 → 結末・現代教訓
- **情報密度**: 3-5秒ごとに視覚変化（テロップ・Bロール・ズーム）

## 3.3 Page000（聖域）の設計意図

- 全シリーズの**終着点**
- バラバラの回答（点）が1本の物語（線）になる感動体験
- 読者が「自分の人生を愛おしく思える」UI
- 独自ペルソナ設定・独自10問・独自レーダーは持たない（集計と分析のみ）

---

# 第4部: 自動化アーキテクチャ

## 4.1 インフラ構成

```
┌──────────────────────────────────────────────────┐
│              GitHub Actions (cron)               │
│   ┌──────────────┐        ┌──────────────────┐   │
│   │YouTube Cycle │        │note Auto Post (B)│   │
│   │ 12:00 UTC毎日 │        │ ランダム 1日2本以下│   │
│   └──────┬───────┘        └────────┬─────────┘   │
└──────────┼─────────────────────────┼─────────────┘
           │                         │
   ┌───────▼──────┐          ┌───────▼────────┐
   │ Gemini API   │          │ Playwright     │
   │ ElevenLabs   │          │ (Chromium)     │
   │ YouTube API  │          │ → note.com     │
   └──────┬───────┘          └────────────────┘
          │
   ┌──────▼──────────┐       ┌───────────────────┐
   │ Supabase (DB)   │◀──────│ toi-suite (Vercel)│
   │ + state.json    │       │  6軸レーダー本番  │
   └─────────────────┘       └───────────────────┘
```

## 4.2 Supabase

テーブル構築済（`gothqgwtucnyrsblzawo` プロジェクト、ap-northeast-1）:
- `profiles`: ユーザー属性・AI分析結果
- `questions`: 問いのストック（AI生成フラグ含む）
- `answers`: 回答 + 感情スコア + キーワード抽出
- `execution_logs`: 2時間おきのcron実行記録

## 4.3 GitHub Secrets（設定済）

- `GEMINI_API_KEY`
- `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID`
- `LEMON_SQUEEZY_API_KEY`
- `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_DB_PASSWORD`
- `YOUTUBE_API_KEY` / `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN`
- `NOTE_STORAGE_STATE`（B案 note自動投稿用 / Playwright storageState JSON。`NOTE_EMAIL`/`NOTE_PASSWORD` は廃止）

## 4.4 6軸分析システム（toi-suite に実装済）

ユーザーの10問回答を Gemini API に投げ、以下6軸を 0-100 でスコア化:

1. **決断力 (decision)** - 迷わず機を捉える力
2. **精神力 (mental)** - プレッシャーに屈しない芯の強さ
3. **適応力 (resilience)** - 逆境を好機に変える柔軟性
4. **洞察力 (insight)** - 本質を見抜き、先を読む力
5. **規律心 (discipline)** - 己を律し、継続する力
6. **大義 (vision)** - 己のためだけでなく、世のために動く志

UIフロー: **10問ラリー → 6軸レーダー（今の目安） → 分析プロンプト生成**

実装ファイル:
- `api/analyze.js` (Vercel Serverless Function)
- `src/lib/gemini.js` / `src/lib/supabase.js`
- `src/components/PageBase.jsx`
- `supabase/migrations/0001_init.sql`

---

# 第5部: 自律運用ルール

## 5.1 必須

- エラーは Gemini API と相談して自己修正（オーナーに毎回聞かない）
- 2時間おきに Supabase `execution_logs` へ書き込み
- スマホで読める3行要約（進捗率・収益見込み）を チャットに出す

## 5.2 禁止事項（過去の失敗から）

- ❌ 過剰な確認質問・選択肢提示（うっちー様の時間とトークンを浪費）
- ❌ 「私は担当外」発言（あなたは統括実行責任者）
- ❌ 残り10シリーズの新規開発
- ❌ 妥協版でのデプロイ（過去P42等で品質負債発生）
- ❌ Chrome MCP/computer-use での散漫な操作
- ❌ ペルソナ混同（toi=47歳管理職を他シリーズに流用）
- ❌ GitHub username の取り違え

## 5.3 完全自動化の絶対条件

うっちー様は:
- 平日: 会社員
- 土日: 家族時間・他のやりたいこと

→ PC OFF時もクラウドで全自動稼働させること。理想ではなく**ガチの絶対条件**。

---

# 第6部: 現状サマリ（2026/05/09 時点）

## 完了済み

- ✅ toi-suite Vercel稼働、6軸レーダー実装push済
- ✅ toi-suite Page000 集計機能修復push済
- ✅ 10oku-project リポジトリ構築（GitHub Actions 2本: YouTube + note）
- ✅ B案 note自動投稿 Playwright実装（1日2本・ランダム遅延）
- ✅ Supabase スキーマ + GitHub Secrets 設定済
- ✅ HANDOFF.md 配置

## 未完了

- [x] `compile_video.mjs` 本実装（ffmpeg + sharp 連携、静止画+音声→mp4）
- [x] `upload_youtube.mjs` 本実装（googleapis + OAuth refresh token フロー）
- [x] GitHub Issues 自動起票（self-heal workflow、Gemini-2.5-flash診断）
- [x] note 下書き編集型に切り替え（Playwright storageState 使用）
- [ ] ローカルで `npm run note:capture` → storageState 取得 → Secret `NOTE_STORAGE_STATE` 登録（**ユーザー作業**）
- [ ] note.com で下書きを作成し draftId を queue.json に流し込み
- [ ] Playwright 実機テスト（ローカルで `npm run note:post`）
- [ ] 2-hour-cycle 進捗報告システム

## 既知の制約

- note自動投稿は note 規約グレーゾーン（BANリスクあり）
- Playwright on GitHub Actions は CAPTCHA で停止する可能性あり
- Supabase / Vercel / ElevenLabs の無料枠上限を月次で要監視

---

# 第7部: note.com 既存資産

## 200の問い 反映状況

- ローカルv3原稿: #001-#200 完成（フェーズ1.5完了）
- note.com反映済: #007-#012 + #013-#014
- **未反映: #015-#200（186本）**
- ローカル原稿パス: `C:\Users\user\Documents\Claude\Projects\note 200本\note_articles_v2\note_NNN_*.md`

## 既存スコープ外（10シリーズPWA）

過去P20-P29で5本フル+195本スタブの妥協版をデプロイしたが品質負債として認識。
**今後の運用対象外**（戦略転換で中止）。

---

# 第8部: 連絡経路

## 失敗時

- **GitHub失敗メール**: 自動配信（GitHubアカウント通知設定に依存）
- **GitHub Issues**: 自動起票（`.github/workflows/self-heal.yml` + `scripts/self_heal.mjs` 実装済 / Gemini-2.5-flash で原因推定 + 修正案）
- **緊急時**: ローカルPCで PowerShell から手動再開可
  ```powershell
  cd C:\Users\user\Documents\10oku-project
  npm run youtube:cycle    # YouTube手動実行
  npm run note:post        # note手動投稿
  ```

## 状態確認

- スマホ → [GitHub Actions タブ](https://github.com/uchy0307/my-10oku-project/actions)
- `state.json` の commit ログでも進捗追跡可

---

# 第9部: 引き継ぎ・継続性

## このファイルの位置づけ

このファイルは Claude.ai プロジェクトで永続知識として参照される設計です。
新しい Claude セッションが立ち上がっても、このファイルを読めば即座に文脈復元可能。

## Cowork desktop での再開時

うっちー様がローカルPCで Cowork を起動すると、Dispatch Claude の memory ファイルが自動的に読み込まれます。継続作業可能。

memory ファイルの場所:
`C:\Users\user\AppData\Roaming\Claude\local-agent-mode-sessions\<session>\agent\memory\`

主要なメモリファイル:
- `MEMORY.md` （インデックス）
- `project_10oku_master_plan.md`
- `project_strategy_pivot_2026_05_09.md`
- `reference_series_target_personas.md`
- `reference_pricing.md`
- `reference_github_username.md`
- `project_pwa_quality_debt.md`
- `project_note_com_sync_plan.md`

---

**更新日**: 2026/05/09
**作成者**: Dispatch Claude (Cowork session)
**目的**: PC OFF後もプロジェクトを完全に自走させるための引き継ぎドキュメント
