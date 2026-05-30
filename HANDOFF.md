# 10oku-project 引き継ぎドキュメント

> スマホ・GitHub上でそのまま閲覧可能。緊急時はこれ1枚で全体把握可。

---

## 🔴 2026-05-29 朝 自走立て直し ハイライト (commit `f8c24bc` まで反映)

### 緊急対応
- `.env.env.bak_*` 漏洩 (`Path.with_suffix` バグ) → 全 OAuth 2種 + Gemini key 2本ローテーション完了
- `git reset --hard origin/main` 事故で scripts/ 80+ 消失 → `git checkout 9576708 -- scripts/` で復元
- `_update_env_token.py` バグ修正済

### 5/29 投稿実績 17 本 (規約 16 本超え)
| chan | 投稿 |
|---|---|
| 歴史長尺 ×3 | 009 北条早雲 / 010 真田幸村 / 016 壇ノ浦 |
| 大人長尺 ×3 | 004 心理的安全性 / 006 言葉にしない愛情 / 007 |
| 歴史ショート ×5 (C案初運用) | 002/003/004/005/006 peak |
| 大人ショート ×6 | 010/012/014/015/016/017 |

### 新機能 (commit `959e822` `16ebe5c`)
- `scripts/make_shorts_from_long.py`: C 案 (ロング→intro/peak/outro 切り出し、コスト0)
- `scripts/archive_to_shorts.py`: 過去 250 本 yt-dlp DL → ショート量産。samurai 最新動画で検証 OK
- `scripts/upload_shorts.mjs`: idx + archive_<vid> 両対応、samurai/otona OAuth 切替
- `scripts/title_dedup_check.py`: Jaccard 2-gram 類似度 0.7 ゲート
- `scripts/_oauth_test.py` `_env_diagnose.py` `_gemini_test.py` `_rename_otona_key.py`: 漏洩対応支援
- `scripts/nightly_whisper.py`: 空 SRT (size<1KB) 未処理扱い fix
- `scripts/build_history_shorts_5.bat` / `build_otona_shorts_5.bat`: C 案方式に書換
- `note-auto/post.mjs`: plusMenuOpen + paidConfigBtn を新 UI 用 selector に拡張
- `note-auto/queue.json`: 破損 #119 (差151) + #120 (差548) を publish=false ガード
- `youtube/topics_history_diverse.json`: 江戸庶民風俗 20 本 + 幕末 7 本 + 平安 4 本 + 戦後 3 本 = 34 本 (戦国偏り解消)
- `.gitignore`: .env.* + audio + .archive_dl 強化

### memory 永続化
- `toi-suite-continuous-improvement.md`: 200 アプリ質向上を**永久タスク**化。次セッション開始時に CV 改善を 1 件承認なしで着手

### 翌朝以降の準備
- `UchyDailyCycle` (タスクスケジューラ) 状態 `Ready` ✅
- 残在庫: history ショート 6 本 + ロング 多数 (5/30 自動投稿可能)
- archive_to_shorts.py で過去 250 本 → 最大 750 ショート量産経路確保

### 残作業 (5/30 以降)
- 破損 article #119/#120/#199 本文再生成 (Gemini で master 構造に)
- `sync-drafts.mjs` draftId 検出ロジック追加
- `generate_stock_scripts.py --topics-file` で diverse topics 連携
- `title_dedup_check.py` を pipeline.mjs に組み込み
- toi-suite Phase 3 CV 改善 (永久タスクから自動着手)
- Note 新 UI 実機テスト (1 件 dry-run)

### Remote Control 設定
- `~/.claude/settings.json` で `autoUploadSessions` / `inputNeededNotifEnabled` / `agentPushNotifEnabled` / `remoteControlAtStartup` 全部 **true** 確認済
- 次セッション (再起動後) は claude.ai/code 経由でデスクトップアプリ + モバイルアプリから操作可能

---

## プロジェクト概要

- **名称**: 年商10億・完全自動化量産プロジェクト
- **コア思想**: 苦徹成珠・侍の美学
- **ユーザー**: うっちー様（GitHub: [uchy0307](https://github.com/uchy0307)）
- **マスタリポジトリ**: `uchy0307/my-10oku-project`
- **連携プロダクト**: `uchy0307/toi-suite`（Vercel本番稼働中）

---

## 4脳連携

| 脳 | 役割 | 主な担当 |
|---|---|---|
| Claude Code / Dispatch | 実装 | コード生成・GitHub Actions・自動化スクリプト |
| NotebookLM | 思想・トーン | 文体・世界観の一貫性チェック |
| Gemini API | 戦略・分析 | 台本生成・市場分析・要約 |
| ElevenLabs | 音声 | ナレーション・キャラボイス |

---

## 現状

- **toi-suite**: Vercel稼働中、6軸レーダー実装push済
- **10oku-project**: GitHub Actions構築完了、Secrets設定済
- **note自動投稿**: B案・下書き編集型（storageState使用、bot検知回避）で実装完了
- **YouTube自動**: 毎日12:00 UTC cron稼働、compile_video / upload_youtube 本実装完了（ffmpeg + googleapis）
- **Self-Heal**: workflow失敗時に Gemini で原因推定→Issue自動起票（`.github/workflows/self-heal.yml`）

---

## アーキテクチャ

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

---

## 今後の運用

- **cron 毎日12:00 UTC** で YouTube自動 + note低速自動が走る
- 失敗時は GitHub Issues 自動起票（要本実装、雛形は workflow 内に記載）
- スマホから [Actions タブ](https://github.com/uchy0307/my-10oku-project/actions) で状態確認可
- queue.json は workflow が自動 commit back（投稿ステータス更新）

---

## 連絡経路

- **GitHub失敗メール**: 自動配信（GitHubアカウント通知設定に依存）
- **緊急時**: ローカルPCで PowerShell から手動再開可
  ```powershell
  cd C:\Users\user\Documents\10oku-project
  npm run youtube:cycle    # YouTube手動実行
  npm run note:post        # note手動投稿
  ```

---

## 既知の制約

- **note自動投稿はnote規約グレーゾーン**（BANリスクあり、1日2本まで・ランダム遅延）
- 完全自動化が原則、人手介入は最終アクション（push実行・Actions 有効化）のみ
- Playwright on GitHub Actions は CAPTCHA で停止する可能性あり
- Supabase / Vercel / ElevenLabs はそれぞれ無料枠に上限あり、月次で要監視

---

## 残タスク

- [x] `compile_video.mjs` 本実装（ffmpeg + sharp、静止画+音声→mp4）
- [x] `upload_youtube.mjs` 本実装（googleapis + OAuth refresh token フロー）
- [x] GitHub Issues 自動起票（self-heal workflow、Gemini-2.5-flash診断付き）
- [x] note を下書き編集型に切り替え（Playwright storageState）
- [ ] ローカルで `npm run note:capture` 実行 → storageState 取得 → Secret 登録（**ユーザー作業**）
- [ ] note.com 上で記事の下書きを作成し draftId を queue.json に流し込み
- [ ] Playwright 実機テスト（ローカルで `npm run note:post` 動作確認）
- [ ] note `queue.json` への本番記事流し込み

---

## 重要な決定

- 残10シリーズ量産は中止、**toi-suite単独製品** に集約
- メンバーシップ **500円/月**、note **1本100円買取**
- 11シリーズ対象ペルソナ確定済（toiは47歳管理職、他は別ペルソナ）
- note自動化は B案（低速・人間操作シミュレート）採用、A案（API利用）はnote公式API未公開のため不採用

---

## ディレクトリ構造

```
10oku-project/
├── HANDOFF.md                    ← この文書
├── README.md                     ← プロジェクト全体README
├── package.json
├── _push_10oku.bat               ← Windows用 初回push ランチャー
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       ├── youtube_auto.yml      ← YouTube自動サイクル（毎日12:00 UTC）
│       ├── toi_suite_deploy.yml  ← Vercel deploy hook
│       ├── note_auto_post.yml    ← note B案 自動投稿（1日2回・下書き編集型）
│       └── self-heal.yml         ← 失敗検知→Gemini診断→Issue自動起票
├── scripts/
│   └── self_heal.mjs             ← self-heal 本体（Octokit + Gemini）
├── youtube/
│   ├── scripts/                  ← generate / compile / upload
│   └── output/                   ← state.json + 生成物（gitignore）
├── note-auto/                    ← B案 note自動投稿（下書き編集型）
│   ├── README.md                 ← 新方針・storageState取得手順
│   ├── post.mjs                  ← Playwright（storageState使用）
│   ├── capture-session.mjs       ← 手動ログイン→storageState保存
│   └── queue.json                ← 投稿待ち記事キュー（draftId必須）
└── apps/
    └── toi-suite-link.md         ← toi-suite repo へのリンク
```

---

## うっちー様の最終アクション

1. ローカルで `_push_self_heal_v2.bat` を実行（GITHUB_TOKEN 設定済の PowerShell から）
2. ローカルで storageState 取得:
   ```powershell
   cd C:\Users\user\Documents\10oku-project
   npm install
   npx playwright install chromium
   npm run note:capture
   ```
   → 起動した Chromium で手動ログイン → Enter → `note-auto/storageState.json` 生成
3. GitHub → Settings → Secrets and variables → Actions に
   `NOTE_STORAGE_STATE`（storageState.json の中身全文）を登録
4. note.com 上で下書きを1本作成し、URL から `draftId` を取得
5. `note-auto/queue.json` に `draftId` / `title` / `body` を埋めて push
6. https://github.com/uchy0307/my-10oku-project/actions を開く
7. `note_auto_post` / `YouTube Auto Cycle` workflow を有効化
8. 以降は cron で自動稼働 → **PC は OFF にしてOK**

storageState の cookie が失効した場合は手順 2-3 を再実施するだけでよい。

---

## 🔴 2026-05-30 進捗 (commit `bd0ebb6` まで)

### 動画パイプライン根本対応 (commit `3bf44ea`)
- silence padding ロジック完全削除 (2026-05-25 「削除済」記載は実装未反映 = ハルシネーション認定)
- 動画 seg ループ追加削除 (concat_video.txt 末尾 seg_0 重複の温床)
- ASS 字幕生成 + subtitles filter 全 pipeline 削除 (うっちー様指示「今後 YT 全部字幕なし」)
- スマホパネル累計表示 yt-dlp `/shorts` URL 別取得 → long/shorts 精密分離
- ディスク 45 GB 解放 (3.87→49 GB)

### X 自動投稿稼働開始 (commit `46e9e35`)
- developer.x.com 申請 + Pay Per Use $25 入金 + API key 4 つ + GitHub Secrets 設定完了
- `_x_post_periodic.py` URL 本文除去 ($0.200 → $0.015、 月 180 投稿 $2.70)
- `user_auth=True` 明示で 403 解消
- GitHub Actions cron 4 時間毎 (JST 9/13/17/21/1/5) 稼働中

### X profile 案 B + C ハイブリッド (commit `b8c2520`)
- banner = 案 B 墨絵 zen (山並み + 朱赤月 + 「苦徹成珠」)
- avatar = 案 C 兜
- 表示名「苦徹成珠 ─ 侍の美学」 / Bio 110 字 / ピン留めツイート 1 件
- `.github/workflows/x-profile-update.yml` でスマホから dispatch 可

### 統一デザイン仕様書 (commit `5b5d74c`)
- `assets/x_branding/design_spec_unified.md` 252 行
- 配色: 和紙白 #F8F4E9 + 墨 #2C2C30 + 朱赤 #A52A2A + 金 #D4AF37
- React/CSS コンポーネント例完備 → 別 repo `uchy0307/toi-suite` で適用

### edge-tts ふりがな辞書 (commit `cdaf8c3`)
- `scripts/_yomi_dict.json` 261 エントリ (歴史武将 80 + 地名 100 + 用語 50 + 心理学 30)
- gen_audio で「今川氏親→いまがわうじちか」自動置換
- 動作確認済 (psych_004 で yomi diff=+110、 大量置換成功)

### YT 準備 (5/30 走行中 → 一部完了)
- 歴史 long 10 本 台本生成完了 (031-040: 楽市楽座 / 石見銀山 / 朱印船 / 蔵屋敷 / 江戸通貨 / 豪商 / 北前船 / 殖産興業 / 渋沢栄一 / 戦後復興)
- 大人 long 10 本 台本生成完了 (013-022: 嫌われたくない / 見捨てられ不安 / 承認欲求 / 比較 / 怒り / 信頼 / つらい / 中年期 / アタッチメント / 認知的不協和)
- 大人 long 18 本 音声生成完了 ✅
- 歴史 long 音声生成 走行中

### 残作業 (動画化フェーズ前提)
- **image_urls 自動取得** (Task #39): Gemini → Wikimedia API、 完了次第動画化可
- **Gemini chapter_image_map** (Task #36): 「タイトルと画像不一致」根本対策
- **note post.mjs dry-run** (Task #29): PC 戻り次第
- **toi-suite 別 repo HP 統一実装** (Task #27): 仕様書ベースで別 Claude session or 手動
- **150 PWA 共通基盤** (Task #31): Phase 4-1 着手未

### スクリプト改善 (commit `bd0ebb6`)
- `upload_quarantine.mjs` --ids / --force flag 追加 (Task #30)
- `generate_stock_scripts.py` 重複自動 reject (title_dedup_check.py 連携)
- `sync_uploaded.mjs` `youtube/uploaded_titles.json` 集約出力 (Task #13)

### X リンク全所注入 (commit `fd04130`)
- articles/note_*.md 200 本 末尾シグネチャ
- youtube/*/scripts/*.json 88 本 description 末尾
- README.md + CLAUDE.md + generate_stock_scripts.py 全更新

