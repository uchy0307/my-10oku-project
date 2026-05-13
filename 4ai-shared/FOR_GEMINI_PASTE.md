# Gemini 共有用 全文ダンプ（最終更新: 2026/05/13）

うっちー様の年商10億プロジェクト現状把握用。これ全部読んでから回答してください。

---

## 1. プロジェクト全体像

- ゴール: 年商10億・完全自動化量産プロジェクト
- 主軸: toi-suite（200の問い）PWA + note.com 200本記事販売 + YouTube @Japanese.Samurai.Channel
- 4AI連携: Claude（実装・司令）/ Gemini（戦略・台本）/ NotebookLM（哲学）/ ElevenLabs（ナレーション）

---

## 2. 絶対遵守ルール

- 手動投稿は**完全禁止**。完全自動化のみ
- PC OFF前提・GitHub Actions Cron による 24/7 クラウド運転
- toi-suite水準が品質基準。既存記事の妥協版再デプロイ厳禁
- 価格: note 1本100円 / メンバーシップ 500円/月
- GitHub username: **uchy0307** （happyhappy0307 / 4649 は誤り）

---

## 3. シリーズ別ターゲットペルソナ

| シリーズ | 対象 |
|---|---|
| toi-suite（200の問い） | 47歳前後・管理職男女 |
| 恋愛 | 男女全世代 |
| 健康 | 40歳以上 |
| お笑い | 全世代 |
| 子育て | 子育て世代と祖父母世代 |

toiの「47歳管理職」を他シリーズに流用しない。

---

## 4. 戦略転換（2026/05/09）

- 残り10シリーズの新規開発は中止
- toi-suite単独に集中。アプリ付きnote販売
- API連携を基本、Bot UI操作は最小化

---

## 5. 技術スタック

- 自動化基盤: GitHub Actions
- note 投稿: Playwright + storageState（B-plan / slow & safe）
- YouTube: googleapis YouTube Data API v3 + OAuth refresh token
- TTS: ElevenLabs API
- 台本生成: Gemini API（モデル: `gemini-2.5-flash` で安定）
- Self-Heal 診断: Octokit + Gemini

---

## 6. 進捗ステータス（2026/05/13 朝時点）

- 原稿200本（v3）: ✅ `articles/` 完備
- note.com 出稿済: 14本（#001〜#014）
- note 自動投稿: ⚠️ 5/13朝 ワークフロー初グリーン達成。ただし draftId マッチ14件のみで実投稿ゼロ
- YouTube 自動化: ❌ 動画化未完了
- Self-Heal: ✅ 動作OK（失敗→Issue起票まで）
- 売上: 0円

---

## 7. 最優先ブロッカー: note.com 同期処理

### 症状
sync-drafts.mjs が note.com 上の下書きを14本しかマッチさせられず、残り186本の draftId が空。
post.mjs は draftId 無い記事をスキップする実装なので、1本も自動投稿されない。

### 詳細
- `https://note.com/api/v2/notes/note_list/contents?page=N&status={draft|published}` がnote.com内部API
- 直接 fetch すると HTML 404 が返る（CSRF / Referer / XSRF-token 検証で弾かれてる疑い）
- note.com 自身がそのAPIを叩くタイミングを Playwright の `response` イベントで捕捉
- スニッファでJSONは取得できているが、配列パースが失敗して0件抽出になっている疑い

### 仮説
1. レスポンスJSONの構造が想定形と違う
2. 配列要素のキー（id/title）が想定外（例: `key`, `name`）

### 次の一手（push済 / 次回Cronで判明）
sync-drafts.mjs に「最初3レスポンスを生ダンプ」と「再帰的配列探索」を追加。
次回Cron実行後に `[DUMP1] [DUMP2] [DUMP3]` ログを確認→該当キー名でparser修正。

---

## 8. Gemini への具体的な依頼

1. **note.com API `/api/v2/notes/note_list/contents` のCSRFトークン取得方法**
   （storageStateで保持してるCookieだけでは404になる原因の特定）

2. **レスポンスJSONのスキーマ予測**
   （公式ドキュメントor逆解析結果あれば。`note_list/contents` ってURL構造から推測も可）

3. **bot検知回避ヘッダー**
   特に `X-Note-XHR-Token`, `X-Requested-With`, `Referer` 等の必要性・最適値

4. **YouTube 動画コンパイル**
   現状 ffmpeg + sharp で「黒背景＋字幕」のみ。最低限見られる動画に仕上げる ffmpeg filter_complex の具体例

---

## 9. Cron スケジュール

- `note Auto Post`: 03:17 UTC（12:17 JST）/ 11:43 UTC（20:43 JST）
- `Self-Heal on Failure`: ワークフロー失敗時のみ自動発火

---

## 10. リポジトリ構成（主要ファイル）

```
my-10oku-project/
├─ articles/                       # 原稿200本（note_001.md 〜 note_200.md）
├─ note-auto/
│  ├─ sync-drafts.mjs              # 下書き一覧スクレイプ → queue.json再構築
│  ├─ post.mjs                     # queue.jsonを元に下書き編集・保存
│  ├─ queue.json                   # 投稿キュー（200件）
│  └─ capture-session.mjs          # storageState取得用
├─ youtube/scripts/
│  ├─ generate_script.mjs          # Gemini API台本生成
│  └─ upload_youtube.mjs           # YouTube Data API v3
├─ scripts/
│  └─ self_heal.mjs                # 失敗診断（Octokit + Gemini）
├─ .github/workflows/
│  ├─ note_auto_post.yml
│  └─ self-heal.yml
└─ 4ai-shared/                     # ★ このフォルダ（4AI共有ハブ）
   ├─ README.md
   ├─ status.md
   ├─ decisions.md
   ├─ blockers.md
   ├─ next_actions.md
   └─ FOR_GEMINI_PASTE.md          # ← 今読んでるやつ
```

---

以上、これが現状全体像です。回答時は上記制約を踏まえ、特に「手動投稿不可」「完全自動化のみ」を絶対に違反しないでください。
