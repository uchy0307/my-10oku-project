# 📊 本日の進捗（2026-05-23）

> 取りまとめ: 2026-05-23 06:00 JST 時点（scheduled-task 自動実行 / 3時間ごと8回 cycle）
> 確認方法: note.com 匿名 API（v2 creators contents）/ YouTube watch ページの `uploadDate` メタデータ / GitHub Actions REST API (`/actions/runs`)
> 制約: 本タスク稼働時刻（06:13 JST 取得）は本日の cron 1本目（note 07:50）より前のため、note 早朝 catch-up 以外の本日新規発火はまだ無し。

---

## 【歴史YouTube（侍・戦国・幕末 / @japanese.samurai.channel）】

ワークフロー: `History v2 (samurai long-form 30min pipeline)`（旧 `youtube_auto.yml` は schedule コメントアウト維持）
本日のドキュメント上スケジュール: 07:50 / 13:50 / 19:50 JST（取りまとめ時点未到来）

- ❌ 07:50 JST: **時刻未到来**
- ❌ 13:50 JST: **時刻未到来**
- ❌ 19:50 JST: **時刻未到来**

**本日（00:00〜06:13 JST）にチャンネルに上がった本編: 0本（未確認なし・公開 0）**

直近 upload（参考）はすべて 2026-05-22 JST（本日分ではない）:
- 2026-05-22 18:00 JST：上杉謙信 関東出兵 完全版 https://www.youtube.com/watch?v=zoUFH0cKzq4
- 2026-05-22 15:57 JST：島津義弘 関ヶ原『敵中突破』完全版 https://www.youtube.com/watch?v=z9hajAYrEMw
- 2026-05-22 13:00 JST：豊臣秀吉 朝鮮出兵の真実 https://www.youtube.com/watch?v=9GDNJvVjqgU

GitHub Actions（06:00 JST 早朝 dispatch）:
- ❌ History v2 #20（workflow_dispatch / 06:00 JST）→ **failure**（Spec-compliance gate (pre-pipeline assets) で停止 / 後段の upload は実行されず）

---

## 【note.com（200の問いシリーズ / @happy_happy_4649）】

ワークフロー: `note Auto Post (B-plan / slow & safe)`（note_auto_post.yml）
ドキュメント上スケジュール: 07:50 / 11:50 / 15:50 / 19:50 / 22:50 JST

**本日（00:00〜06:13 JST）公開: 8本（#069 〜 #076）** ✅ **目標5本 大幅達成（+3）**

| # | タイトル | publishAt (JST) | price | status | URL |
|---|---|---|---|---|---|
| #069 | 📌 記憶定着パートナー | 2026-05-23 01:19:24 | ¥100 | published | https://note.com/happy_happy_4649/n/nee8d2b |
| #070 | ❓ 質問力向上コーチ | 2026-05-23 01:40:13 | ¥100 | published | https://note.com/happy_happy_4649/n/n2a4e6e |
| #071 | 📊 図解思考サポーター | 2026-05-23 01:46:27 | ¥100 | published | https://note.com/happy_happy_4649/n/n75f702 |
| #072 | ✍️ 執筆ブロック解除 | 2026-05-23 01:53:07 | ¥100 | published | https://note.com/happy_happy_4649/n/n6b17c9751410 |
| #073 | 🎓 資格試験戦略 | 2026-05-23 01:59:13 | ¥100 | published | https://note.com/happy_happy_4649/n/n50ea28173ba6 |
| #074 | ⚖️ 意思決定の重み付け | 2026-05-23 02:05:55 | ¥100 | published | https://note.com/happy_happy_4649/n/nde55cdab9b98 |
| #075 | 🎵 集中BGM提案 | 2026-05-23 02:45:54 | ¥100 | published | https://note.com/happy_happy_4649/n/n9d58181f219d |
| #076 | 💎 失敗の資産化 | 2026-05-23 04:25:39 | ¥100 | published | https://note.com/happy_happy_4649/n/n822b3ca0aec3 |

API（v2 creators contents）にて全件 `status=published` ・`price=100` ✅
URL は短縮表示（n069/n070/n071 は API key 後ろ6文字、それ以外はフルキー）。

GitHub Actions（本日該当 schedule 発火 run）:
- ✅ note Auto Post #92（schedule / 2026-05-23 02:28 JST）→ **success**（8 分弱）
- ✅ note Auto Post #93（schedule / 2026-05-23 04:17 JST）→ **success**（8 分強）
- ⏳ 07:50 / 11:50 / 15:50 / 19:50 / 22:50 JST スロットは時刻未到来

**観測**: 公開時刻が 01:19〜04:25 JST に集中（深夜 catch-up MAX 機構）。文書上スロット時刻（07:50〜22:50）に分散していないが、本数は既に超過達成。

---

## 【新YouTube（大人の心理学 / @Otona_Psychology）】

> ハンドル正は `@Otona_Psychology`（タスク指示文の `@otona_no_psychology` は 404）

ワークフロー: `Psych v2 (long-form clean pipeline)`
本日のドキュメント上スケジュール: 07:00 / 13:00 / 19:00 JST（取りまとめ時点未到来）

- ❌ 07:00 JST: **時刻未到来**
- ❌ 13:00 JST: **時刻未到来**
- ❌ 19:00 JST: **時刻未到来**

**本日（00:00〜06:13 JST）にチャンネルに上がった本編: 0本**

直近 upload（参考）はすべて 2026-05-22 JST:
- 2026-05-22 20:30 JST：30代女性が知っておきたい大人の恋愛心理学：幸せを育む8つの智慧 (37:40) https://www.youtube.com/watch?v=tlK2mzCBtZs
- 2026-05-22 15:09 JST：30代女性が知っておきたい大人の恋愛心理学 (32:10) https://www.youtube.com/watch?v=A_nIDUcAIb4
- 2026-05-22 10:26 JST：30代女性が知っておきたい大人の恋愛心理学 (37:43) https://www.youtube.com/watch?v=-mDkSwQDiMI

GitHub Actions（06:00 JST 早朝 dispatch + 過去 15 時間のリトライ）:
- ❌ Psych v2 #14（workflow_dispatch / 06:00 JST 2026-05-23）→ **failure**
- ❌ Psych v2 #10（workflow_dispatch / 2026-05-23 01:11 JST）→ **failure**
- ❌ Psych v2 #9 / #8 / #7（workflow_dispatch / 2026-05-23 00:11〜00:15 JST 集中）→ **すべて failure**
- 共通ステップ失敗: **Spec-compliance gate (pre-pipeline assets)**（pipeline 開始前のアセット検証で停止 → upload 段に到達せず）

---

## 【YouTubeショート（samurai 切出し / @japanese.samurai.channel Shorts）】

ワークフロー: `Shorts v2 (samurai clean pipeline)`（旧 `youtube_shorts_auto.yml` 系から v2 に移行）
ドキュメント上スケジュール: 10:30 / 16:30 / 22:30 JST（取りまとめ時点未到来）

**本日（00:00〜06:13 JST）投稿: 0本**

直近投稿（参考）はすべて 2026-05-22 JST:
- 2026-05-22 22:28 JST：織田信長 最期の言葉「是非に及ばず」｜本能寺の変（決定版） https://www.youtube.com/shorts/Opof7fxyk8g
- 2026-05-22 15:40 JST：織田信長 最期の言葉「是非に及ばず」｜本能寺の変 https://www.youtube.com/shorts/KfG1KpM5QjI
- 2026-05-22 14:20 JST：立花宗茂 不屈の名将 https://www.youtube.com/shorts/aG_A9FzUR4k
- 2026-05-22 14:19 JST：直江兼続『愛』の兜 https://www.youtube.com/shorts/_6FHrIXDniw

GitHub Actions:
- ❌ Shorts v2 #19（workflow_dispatch / 06:00 JST 2026-05-23）→ **failure**
- ❌ Shorts v2 #18（workflow_dispatch / 2026-05-23 01:11 JST）→ **failure**
- 同じく **Spec-compliance gate (pre-pipeline assets)** 失敗で停止

---

## 【ブロッカー・要対応事項】

### 🟢 良好

- **note**: 8本公開（目標5本 +3）/ 全件 ¥100 課金 ・published を API で再確認済
- 深夜 catch-up MAX 機構が想定通り動作（01:19〜04:25 JST に 8本連続消化）

### 🔴 重大（うっちー様アクション要）

1. **v2 pipeline 3本すべて連続 failure（Spec-compliance gate）**
   - 該当ワークフロー:
     - `History v2 (samurai long-form 30min pipeline)` #19, #20
     - `Shorts v2 (samurai clean pipeline)` #18, #19
     - `Psych v2 (long-form clean pipeline)` #7, #8, #9, #10, #14
   - 共通失敗ステップ: **Spec-compliance gate (pre-pipeline assets)**（履歴 v2 #20 のジョブ "upload" の事前検証ゲート）
   - 影響: 本日（5/23）の cron スロット（07:00 / 07:50 / 10:30 / 13:00 / 13:50 / 16:30 / 19:00 / 19:50 / 22:30）が同じゲートで全部止まる可能性が高い → **本日の新規 YouTube アップロード 0本のリスク**
   - 注: 直近のチャンネル上に見える「2026-05-22 の upload」は本日分ではなく、v1（旧 `youtube_auto.yml` / `new_youtube_auto.yml` / `youtube_shorts_auto.yml`）系の最終稼働分か、v2 移行直後の手動 dispatch 分

2. **必要なアセット欠落の特定が必要**
   - Spec-compliance gate は通常、`inputs/`, `assets/`, `samples/<id>/` 配下の必須ファイル（thumbnail, script, audio, narration spec, など）の存在チェック
   - 直近 commit `9b464c8 fix: @Otona_Psychology typo + remove bad prefix (otona_retro_thumbnai…)` 直後から failure が連続している → typo 修正で参照パスが変わり、必須アセットが新パスに置かれていない可能性
   - 推奨: `History v2 #20` のジョブログを開いて "Spec-compliance gate (pre-pipeline assets)" のエラーメッセージを確認し、欠落しているファイルパスを特定

### 🟡 注意

- 06:00 JST に v2 3本同時 dispatch（Psych #14・Shorts #19・History #20）は schedule ではなく `workflow_dispatch` 経由 → Self-Heal 系または 06:00 cron をどこかに新設している可能性。ただし全部失敗。
- `Self-Heal Auto-Retry on Failure` は本日 #245〜#247 が skipped（再試行ガード正常動作）

---

## 【明日の予定 / 本日中の推奨アクション】

### うっちー様 本日中（5/23）対応推奨

1. **🔴 v2 Spec-compliance gate 修復（最優先）**
   - 失敗 run のログ確認: https://github.com/uchy0307/my-10oku-project/actions/runs/26311738849 （History v2 #20）
   - 不足アセットを `inputs/`（または該当パス）に補充 → 一本 manual dispatch で通ることを確認 → 以降の cron に任せる
2. **🟡 cron の確認**
   - 06:00 JST に v2 が一斉 dispatch される設定があるか確認（schedule か外部 trigger か）
   - 文書（SKILL.md / 本タスク指示文）上の 07:00 / 07:50 / 10:30 / 13:00 / 13:50 / 16:30 / 19:00 / 19:50 / 22:30 / 22:50 と GitHub Actions 実 schedule の整合確認

### 通常運用継続項目

- 本日 11:50 / 15:50 / 19:50 / 22:50 JST: note Auto Post（5/5 達成は既に超過済 → 残りはボーナス）
- 本日 07:50 / 13:50 / 19:50 JST: History v2 ← Spec-gate 修復前は失敗継続見込み
- 本日 07:00 / 13:00 / 19:00 JST: Psych v2 ← 同上
- 本日 10:30 / 16:30 / 22:30 JST: Shorts v2 ← 同上

---

## 【今回未確認・留意事項】

- v2 ジョブ "upload" 内の失敗詳細メッセージ（gate がチェックしている具体的なファイル名）はジョブログ未開封のため未取得 → 次の取りまとめ（09:00 JST）で再確認予定
- 旧 `youtube_auto.yml` / `new_youtube_auto.yml` / `youtube_shorts_auto.yml` の本日稼働有無は GitHub Actions に該当 workflow_runs が見えないため schedule 無効維持と推定
- new-youtube-local の VOICEVOX 夜枠ローカル runner 稼働状況は本セッションから接触不可（ローカル PC 側プロセス確認は対象外）
