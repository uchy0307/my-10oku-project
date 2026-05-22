# 📊 本日の進捗（2026-05-20）

> 取りまとめ: 2026-05-20 18:15 JST（午後 cron 一部到来後）
> 前回スナップショット: 15:10 JST（daily_report_2026-05-20_1510JST.md）
> 確認方法: note.com 匿名API + GitHub Actions UI + YouTube チャンネル UI（Chrome MCP）

---

## 【歴史YouTube（samurai / @japanese.samurai.channel）】

ワークフロー: `YouTube Auto Cycle` (youtube_auto.yml)

**⚠ スケジュールは現在コメントアウト（quota 浪費防止のため一時停止中）**
- 旧スロット（07:50 / 13:50 / 19:50 JST）は **発火していない**（仕様通り）

- ❌ 07:50 JST: 未発火（スケジュール停止中）
- ❌ 13:50 JST: 未発火（スケジュール停止中）
- ❌ 19:50 JST: 未発火（時刻未到来 + スケジュール停止中）

**直近の手動 run（前回 15:10 以降）**:
- ❓ #83 / Manual / 18m 0s（要 status 個別確認・stress test 推定）
- ❓ #82 / Manual / 30s（短時間 → 失敗 or kill 推定）
- ❓ #81 / Manual / 4m 28s

**samurai 本編チャンネル**: 最新動画は **3日前**（「真田幸村 日本一の兵 1h25m」「石田三成 1h22m」「明智光秀 1h18m」）
→ 本日の本編 upload は **0本**（仕様通り、quota 待機中）

---

## 【note.com（200の問いシリーズ / @happy_happy_4649）】

ワークフロー: `note Auto Post (B-plan / slow & safe)` (note_auto_post.yml)
スケジュール: 07:50 / 11:50 / 15:50 / 19:50 / 22:50 JST

**本日公開: 5本（#048 / #049 / #050 / #051 / #052）** ✅ **5本目標達成**

| # | タイトル | publishAt | price | status | URL |
|---|---|---|---|---|---|
| #048 | 🗨️ 会話のネタ帳AI | 2026-05-20T02:48:32+09:00 | ¥100 | published | https://note.com/happy_happy_4649/n/ncb9b20684ee1 |
| #049 | 🚷 断り方の美学 | 2026-05-20T03:34:06+09:00 | ¥100 | published | https://note.com/happy_happy_4649/n/naede381b23e7 |
| #050 | 🪞 コミュ癍診断 | 2026-05-20T05:31:44+09:00 | ¥100 | published | https://note.com/happy_happy_4649/n/n358b065ca03b |
| #051 | 🏠 義実家・親戚対応 | 2026-05-20T16:50:11+09:00 | ¥100 | published | https://note.com/happy_happy_4649/n/nbe2466f54046 |
| #052 | 🤔 友人の整理・選別 | 2026-05-20T16:56:00+09:00 | ¥100 | published | https://note.com/happy_happy_4649/n/n046a8b2a0e3c |

**API検証** (`/api/v2/creators/happy_happy_4649/contents`): 全5本とも `price=100` ・`status=published` ✅

**ワークフロー実行（本日）**:
- ✅ #72 / 2026-05-20T02:30 JST / 18m54s → #048
- ✅ #73 / 2026-05-20T03:17 JST / 17m8s → #049
- ✅ #74 / 2026-05-20T05:16 JST / 16m0s → #050
- ✅ #75 / 2026-05-20T16:30 JST 頃 / 13m43s（Manual） → #051 + #052（同一 run で2本生成と推定）

**スロット整合**:
- 07:50 JST: cron 発火確認できず（早朝に 3本まとめて発火）
- 11:50 JST: cron 発火確認できず
- 15:50 JST: 16:30 頃に Manual run #75 で代替・2本生成
- 19:50 / 22:50 JST: 時刻未到来

---

## 【新YouTube（大人の心理学 / @otonano_Psychology）】

> ハンドル正は `@otonano_Psychology`（タスク指示文の `@@otonano_Psychology` は typo）

ワークフロー: `new-youtube auto pipeline` (new_youtube_auto.yml) + `Otona YouTube Auto - Day` (otona_youtube_auto_day.yml)

**本日のチャンネル upload: 4本**（前回 15:10 から増減なし）

| 投稿時刻 | タイトル | URL |
|---|---|---|
| ~15:00 JST（3 hours ago） | 30代女性が知っておきたい大人の恋愛心理学 (25:46) | https://www.youtube.com/watch?v=PGGowNn_PvM |
| ~04:00 JST（14 hours ago） | 30代女性のための大人の恋愛心理学 (26:30) | https://www.youtube.com/watch?v=rOrAwH6nHpQ |
| ~04:00 JST（14 hours ago） | 30代女性のための大人の恋愛心理学 (32:39) | https://www.youtube.com/watch?v=PAylYdXvsSk |
| ~04:00 JST（14 hours ago） | 30代女性が知っておきたい大人の恋愛心理学 (27:54) | https://www.youtube.com/watch?v=myXhMHwkqdI |

**対応 run（new-youtube auto pipeline）**:
- ✅ #47 / Scheduled / 02:54 JST / 57m15s → 朝枠1本目
- ✅ #48 / Scheduled / 02:54 JST / 46m20s → 朝枠2本目
- ✅ #49 / Scheduled / 03:14 JST / 44m27s → 朝枠3本目
- ⚠️ #50 / Scheduled / 03:15 JST / 1h0m33s → **キャンセル**（多重起動衝突）
- ✅ #51 / Manual / 14:04 JST / 45m53s → 昼枠（15:00 投稿）
- ❓ #52 / Manual / 2m6s（前回以降の新 run・短時間→失敗推定）
- ❓ #53 / Manual / 1m58s（短時間→失敗推定）

**Otona YouTube Auto - Day（朝昼 A案クラウド系）**: 本日 run **0件**（最新は前日 #9 / 2026-05-19T23:12 JST 失敗）

**スケジュール（07:00 / 13:00 / 19:00 JST）整合**:
- 07:00 スロット: 02:54〜03:14 にまとめて 3本生成（事実上の朝枠）
- 13:00 スロット: 14:04 Manual run #51 で代替（15:00 投稿）
- 19:00 スロット（B案ローカル / VOICEVOX 冥鳴ひまり）: **時刻未到来**
- 朝昼A案クラウド・夜B案ローカル の振り分けは run 履歴上は new-youtube auto pipeline 単独で動作・Otona-Day（A案）系は本日 0件

---

## 【YouTubeショート（samurai 切り出し）】

ワークフロー: `YouTube Shorts Auto` (youtube_shorts_auto.yml)

**本日投稿: 5本**（目標 3本に対し +2 = **目標超過達成** ✅）

| 投稿時刻（推定） | タイトル | views | URL |
|---|---|---|---|
| 08:59 JST | 【侍の美学】真田幸村 日本一の兵 #Shorts | 212 | https://www.youtube.com/shorts/PpNAROcK0H8 |
| 14:06 JST | 【侍の美学】明智光秀 謀反人の本心 #Shorts | 594 | https://www.youtube.com/shorts/xIyTSqqrM-4 |
| 15:10 以降 | 【侍の美学】上杉謙信 義に生きた軍神 #Shorts | 0 | https://www.youtube.com/shorts/HhiwetefdsU |
| 15:10 以降 | 【侍の美学】上杉謙信 義に生きた軍神 #Shorts | 2 | https://www.youtube.com/shorts/EuIGkOKjZ2E |
| 15:10 以降 | 【侍の美学】上杉謙信 義に生きた軍神 #Shorts | 4 | https://www.youtube.com/shorts/Vlofclq5Va0 |

**Run 履歴（本日 / 前回以降の新規分）**:
- ❓ #18 / Manual / 3m32s（上杉謙信 系・成功推定）
- ❓ #17 / Manual / 3m8s（上杉謙信 系・成功推定）
- ❓ #16 / Manual / 1m28s（上杉謙信 系・成功推定）
- ✅ #15 / Manual / 14:04 JST / 1m24s → 明智光秀
- ✅ #14 / Manual / 08:58 JST / 1m11s → 真田幸村
- ❌ #13 / Manual / 08:41 JST / 1m6s → #14 でリカバリ
- ❌ #12 / Scheduled / 05:09 JST / 59s

---

## 【ブロッカー・要対応事項】

### 🟡 注意（自動リカバリ済 or 軽微）

1. **note Auto Post の朝昼スロット未発火**
   - 07:50 / 11:50 JST スロット時刻に対応する run が見当たらない
   - 早朝（02:30〜05:16）に 3本、午後（16:30 頃）に Manual で 2本生成
   - **影響**: 5本目標 → **達成（5本公開済み）**

2. **Shorts 上杉謙信タイトル重複 3本（要原因究明）**
   - #16 / #17 / #18 の3run（1m28s〜3m32s）が連続実行され、同タイトルのShorts 3本投稿
   - 内容（動画ファイル）が同一かどうかは未検証
   - **要確認**: 同一動画ファイルの重複アップロードなら quota浪費・SNS規約リスク

3. **new-youtube auto pipeline #52/#53 早期終了**
   - 2m前後で完了 → 失敗 or skip と推定
   - チャンネルへの新規 upload なし（4本のまま）

4. **Otona YouTube Auto - Day（A案クラウド）本日 run 0件**
   - 朝昼=A案クラウドの想定だが本日 1件も発火していない
   - 新-YT pipeline が代替している状態
   - **要判断**: スケジュール再設計 or A案系の廃止

### 🟢 ポジティブ

- note: **5本目標達成**（¥100 × 5 = 期待売上 ¥500 base）
- 大人YT: 4本 upload（朝3 + 昼1）
- Shorts: 失敗からのリカバリ機能・**目標超過 5本投稿**
- samurai 本編: 仕様通り停止維持（quota 温存）

### 🔴 重大（うっちー様アクション）

- **現時点で要対応のクリティカル課題なし**

---

## 【明日の予定】

- 通常運用継続
- note: 残スロット（19:50 / 22:50 JST）でさらに発火するか観察（5本超え分はボーナス）
- 新YT: 19:00 JST スロット（B案ローカル / VOICEVOX 冥鳴ひまり）発火確認
- Shorts: 上杉謙信 3本重複の原因究明（cron 多重定義 / retry ロジック / 同一スクリプト連続実行 のどれか）
- A案クラウド（Otona-Day）系の再有効化 or 廃止判断
- samurai 本編 schedule の再有効化判断（bulk ストック化進捗次第）

---

## 【未確認 / 留意事項】

- 各 GitHub Actions run の success/failure ステータスは個別 run 画面を開かないと不明（duration ベースの推定）
- 19:00 / 19:50 / 22:50 JST スロットは時刻未到来のため未検証
- 上杉謙信 Shorts 3本の動画内容が同一か別バージョンかは未検証
- new-youtube #52/#53 の失敗ログ本文は未読
