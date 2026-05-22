# 📊 本日の進捗（2026-05-20）

> 取りまとめ: 2026-05-20 15:10 JST（午後の cron 一部到来後）
> 前回スナップショット: 03:15 JST（daily_report_2026-05-20.md）

---

## 【歴史YouTube（samurai / @japanese.samurai.channel）】

ワークフロー: `YouTube Auto Cycle` (youtube_auto.yml)

**⚠ 重要: スケジュールは現在コメントアウト（一時停止中）**
- yml 内: `# 2026-05-20: bulk ストック化が動くまで quota 浪費防止のため schedule を一時停止`
- 旧スロット（07:50 / 13:50 / 19:50 JST）はすべて **発火していない**（仕様通り）

- ❌ 07:50 JST: 未発火（スケジュール停止中）
- ❌ 13:50 JST: 未発火（スケジュール停止中）
- ❌ 19:50 JST: 未発火（時刻未到来 + スケジュール停止中）

**直近の手動 / 旧スケジュール run**:
- ❌ #80 / Scheduled / 2026-05-20T03:17 JST / 失敗（1m8s）
- ❌ #79 / Scheduled / 2026-05-20T01:39 JST / 失敗（1m30s）
- ❌ #78 / Scheduled / 2026-05-19T19:50 JST / 失敗（8m2s）

samurai 本編チャンネルの最新動画は「2日前」表記 → 本日の本編 upload は **0本**（仕様通り、quota 待機中）。

---

## 【note.com（200の問いシリーズ / @happy_happy_4649）】

ワークフロー: `note Auto Post (B-plan / slow & safe)` (note_auto_post.yml)
スケジュール: 07:50 / 11:50 / 15:50 / 19:50 / 22:50 JST

**本日公開: 3本（#048 / #049 / #050）**

✅ #048 「会話のネタ帳AI」 / publishAt: 2026-05-20T02:48:32+09:00 / ¥100 / status=published
   URL: https://note.com/happy_happy_4649/n/ncb9b20684ee1
✅ #049 「断り方の美学」 / publishAt: 2026-05-20T03:34:06+09:00 / ¥100 / status=published
   URL: https://note.com/happy_happy_4649/n/naede381b23e7
✅ #050 「コミュ癍診断」 / publishAt: 2026-05-20T05:31:44+09:00 / ¥100 / status=published
   URL: https://note.com/happy_happy_4649/n/n358b065ca03b

**API検証** (`/api/v2/creators/happy_happy_4649/contents`): 3本とも `price=100` ・`status=published` ✅

**ワークフロー実行（本日）**:
- ✅ #72 / 2026-05-20T02:30 JST / 成功（18m54s）→ #048
- ✅ #73 / 2026-05-20T03:17 JST / 成功（17m8s） → #049
- ✅ #74 / 2026-05-20T05:16 JST / 成功（16m0s） → #050

**残スロット**:
- ❌ 07:50 JST: 期待された cron 発火なし（GitHub Actions の遅延 or 不発）
- ❌ 11:50 JST: 期待された cron 発火なし
- ⏳ 15:50 JST / 19:50 JST / 22:50 JST: 時刻未到来 or 直前

---

## 【新YouTube（大人の心理学 / @Otona_Psychology）】

> **注意**: タスク指示文中の `@@Otona_Psychology` は typo。正しいハンドルは `@Otona_Psychology`（memory P-001 参照）。

ワークフロー: `new-youtube auto pipeline` (new_youtube_auto.yml) + `Otona YouTube Auto - Day` (otona_youtube_auto_day.yml)

**本日のチャンネル upload: 4本**（@Otona_Psychology の動画タブ調査結果）

- ✅ 「30代女性が知っておきたい大人の恋愛心理学」 / ~14:47 JST / https://www.youtube.com/watch?v=PGGowNn_PvM
- ✅ 「30代女性のための大人の恋愛心理学」 / ~04:10 JST / https://www.youtube.com/watch?v=rOrAwH6nHpQ
- ✅ 「30代女性のための大人の恋愛心理学」 / ~04:10 JST / https://www.youtube.com/watch?v=PAylYdXvsSk
- ✅ 「30代女性が知っておきたい大人の恋愛心理学」 / ~04:10 JST / https://www.youtube.com/watch?v=myXhMHwkqdI

**対応 run（new-youtube auto pipeline）**:
- ✅ #51 / Manual / 2026-05-20T14:04 JST / 成功（45m53s） → 14:47 投稿に対応
- ⚠️ #50 / Scheduled / 2026-05-20T03:15 JST / **キャンセル**（1h0m33s）
- ✅ #49 / Scheduled / 2026-05-20T03:14 JST / 成功（44m27s）
- ✅ #48 / Scheduled / 2026-05-20T02:54 JST / 成功（46m20s）
- ✅ #47 / Scheduled / 2026-05-20T02:54 JST / 成功（57m15s）

**Otona YouTube Auto - Day（朝昼A案クラウド）**: 本日新規 run **なし**（最新は #9 / 2026-05-19T23:12 JST 失敗）

**スケジュール（07:00 / 13:00 / 19:00 JST）整合**:
- 07:00 / 13:00 スロット名目では発火していないが、new-youtube pipeline が 02:54〜03:15 にまとめて 3 本生成・upload（事実上の朝枠）
- 14:04 の手動 run #51 が事実上の昼枠
- 19:00 スロット: 時刻未到来
- 朝昼A案クラウド・夜B案ローカル（VOICEVOX 冥鳴ひまり）の振り分けは **本日 run 履歴上は new-youtube auto pipeline 単独**。Otona-Day（A案）系は 0 件。

---

## 【YouTubeショート（samurai切り出し）】

ワークフロー: `YouTube Shorts Auto` (youtube_shorts_auto.yml)

**本日投稿: 2本**（目標 3本に対し -1）

- ✅ 「【侍の美学】真田幸村 日本一の兵 #Shorts」 / uploadDate: 2026-05-20T08:59:42 JST
   URL: https://www.youtube.com/shorts/PpNAROcK0H8 / 104 views
- ✅ 「【侍の美学】明智光秀 謀反人の本心 #Shorts」 / uploadDate: 2026-05-20T14:06:25 JST
   URL: https://www.youtube.com/shorts/xIyTSqqrM-4 / 16 views

**Run 履歴**:
- ✅ #15 / Manual / 2026-05-20T14:04 JST / 成功（1m24s） → 明智光秀
- ✅ #14 / Manual / 2026-05-20T08:58 JST / 成功（1m11s） → 真田幸村
- ❌ #13 / Manual / 2026-05-20T08:41 JST / 失敗（1m6s） → #14 でリカバリ
- ❌ #12 / Scheduled / 2026-05-20T05:09 JST / 失敗（59s）

---

## 【ブロッカー・要対応事項】

### 🟡 注意（自動リカバリ済 or 待機中）

1. **note Auto Post の朝昼スロット未発火**
   - 07:50 / 11:50 JST スロット時刻に対応する run が見当たらない
   - 早朝（02:30 / 03:17 / 05:16）に 3 本まとめて発火し成功
   - GitHub Actions cron の遅延 or schedule cluster と思われる
   - **影響**: 5本目標に対し現時点 3本。残スロット（15:50 / 19:50 / 22:50）で 2本追加発火すれば目標達成

2. **YouTube Shorts Auto の不安定さ**
   - #12 (cron 05:09) と #13 (manual 08:41) が失敗・1分強の早期終了
   - 手動 retry (#14 / #15) で 2本リカバリ済
   - **要確認**: 失敗 run の stderr で root cause 特定（入力動画不在 / OAuth 認証切れ / 何か）

3. **new-youtube auto pipeline #50 キャンセル**
   - 03:15 起動・1時間で cancel
   - 直前の #47 #48 #49（02:54〜03:14）と同一スロット内で 4 本目を試みた多重起動が原因と推測
   - 出力済 3本（#47 #48 #49）で本日朝枠分は確保

### 🟢 ポジティブ

- note: 3本連続成功・課金（¥100）正常
- 大人YT: 4本 upload・新-YT pipeline は安定稼働中
- Shorts: 失敗からの retry が機能・2本投稿達成
- samurai 本編: 仕様通り停止（quota 浪費防止のための schedule コメントアウト）

### 🔴 重大（うっちー様アクション）

- **現時点で要対応のクリティカル課題なし**。

---

## 【明日の予定】

- 通常運用継続
- note: 残スロット（15:50 / 19:50 / 22:50 JST）で 2 本追加発火を期待
- 新YT: 19:00 JST スロット（B案ローカル / VOICEVOX 冥鳴ひまり）発火確認
- Shorts: 残り 1本（夕方〜夜スロット）発火を期待
- 必要に応じ samurai 本編 schedule の再有効化判断（bulk ストック化進捗次第）

---

## 【未確認 / 留意事項】

- 19:00 / 19:50 / 22:50 JST スロットは時刻未到来のため未検証
- B案ローカル（VOICEVOX）と A案クラウドの振り分け実装は run ログから直接判定不可。
  - 本日は new-youtube auto pipeline 経由のみ発火しており、Otona-Day（A案）系 0 件
- YouTube Shorts の失敗ログ本文は未読
