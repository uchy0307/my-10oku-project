# 📊 本日の進捗（2026-05-20）

> 自動生成レポート / 生成時刻: 2026-05-20 03:15 JST
> 注: 本レポートは 03:15 JST 時点のスナップショット。本日の主要cronスロット（朝7時台以降）はまだ到来していません。

---

## 【歴史YouTube（samurai / @japanese.samurai.channel）】

ワークフロー: `YouTube Auto Cycle` (youtube_auto.yml)
スケジュール: 07:50 / 13:50 / 19:50 JST

❌ 07:50 JST スロット: **未実行**（時刻未到来）
❌ 13:50 JST スロット: **未実行**（時刻未到来）
❌ 19:50 JST スロット: **未実行**（時刻未到来）

**直近の状況**: 連続失敗継続中
- ❌ #79 / Scheduled / 2026-05-20T01:39 JST / 失敗（スケジュール外の起動・所要1m30s）
- ❌ #78 / Scheduled / 2026-05-19T19:50 JST / 失敗（8m02s）
- ❌ #77 / Manual / 2026-05-19T18:45 JST / 失敗
- 動画URL: **取得なし**（全runが失敗）

---

## 【note.com（200の問いシリーズ / @happy_happy_4649）】

ワークフロー: `note Auto Post (B-plan / slow & safe)` (note_auto_post.yml)
スケジュール: 07:50 / 11:50 / 15:50 / 19:50 / 22:50 JST

**本日公開確認: 1本（#048）**

✅ #048 「会話のネタ帳AI」 / 公開: 2026-05-20T02:48:32+09:00 / ¥100 / status=published
   URL: https://note.com/happy_happy_4649/n/ncb9b20684ee1
   匿名API検証: ✅ `price=100` ・`status=published`

**ワークフロー実行状況**:
✅ note Auto Post #72 / 2026-05-20T02:30:07 JST / 成功（18m54s）→ #048 公開に対応
✅ note Auto Post #71 / 2026-05-19T22:57:12 JST / 成功（前日22:50枠）
✅ note Auto Post #70 / 2026-05-19T19:49:48 JST / 成功（前日19:50枠）

**本日の残スロット（時刻未到来）**:
- 07:50 / 11:50 / 15:50 / 19:50 / 22:50 JST: いずれも未実行

---

## 【新YouTube（大人の心理学 / @otona_no_psychology）】

該当ワークフロー候補:
- `new-youtube auto pipeline` (new_youtube_auto.yml) — cron 07:00-07:30 / 13:00-13:30 / 19:00-19:30 JST（多重スケジュール）
- `Otona YouTube Auto - Day (AI Images)` (otona_youtube_auto_day.yml) — 08:00 / 13:00 JST

❌ 07:00 JST スロット: **未実行**（時刻未到来）
❌ 13:00 JST スロット: **未実行**（時刻未到来）
❌ 19:00 JST スロット: **未実行**（時刻未到来）

**直近の状況** (new-youtube auto pipeline):
- 🔄 #48 / Scheduled / 2026-05-20T02:54:03 JST / **実行中**（レポート生成時点）
- 🔄 #47 / Scheduled / 2026-05-20T02:54:02 JST / **実行中**
- ❌ #46 / Scheduled / 2026-05-20T01:42:20 JST / **失敗**
- ⚠️ #45 / Scheduled / 2026-05-20T01:25:56 JST / **キャンセル**
- ✅ #44 / 2026-05-19 / 成功（参考）

**直近の状況** (Otona YouTube Auto - Day):
- ❌ #9 / 2026-05-19T23:12:28 JST / 失敗
- ❌ #8 / 2026-05-19T19:50:36 JST / 失敗
- ❌ #7 / 2026-05-19T01:35:32 JST / 失敗
- ✅ #6 / 2026-05-18T20:07:15 JST / 成功（参考）

- 動画URL: **取得なし**（最新の完了runが失敗のため）
- 朝昼A案クラウド / 夜B案ローカル（VOICEVOX 冥鳴ひまり）: **未検証**（本日の本スケジュール未到来）

---

## 【YouTubeショート（samurai切り出し）】

ワークフロー: `YouTube Shorts Auto` (youtube_shorts_auto.yml)

**本日投稿数: 0本**（全runが失敗）

- ❌ #11 / 2026-05-20T02:40:29 JST / 失敗（1m01s）
- ❌ #10 / 2026-05-19T21:29:30 JST / 失敗（1m09s）
- ❌ #9 / 2026-05-19T04:16:32 JST / 失敗
- ✅ #8 / 2026-05-19T01:15:19 JST / 成功（参考・最後の成功例）

---

## 【ブロッカー・要対応事項】

### 🔴 重大（うっちー様対応要）

1. **YouTube Auto Cycle（samurai）連続失敗**
   - 最新7run（#73〜#79）が全て失敗・成功率0%
   - #79 は所要1m30sで早期失敗 → 初期化エラーの可能性
   - [Actions](https://github.com/uchy0307/my-10oku-project/actions/workflows/youtube_auto.yml)

2. **YouTube Shorts Auto 連続失敗**
   - 最後の成功は #8（2026-05-19T01:15 JST）以降全失敗
   - 短時間（1分強）で終了 → 入力ファイル不在 or 認証切れの可能性
   - [Actions](https://github.com/uchy0307/my-10oku-project/actions/workflows/youtube_shorts_auto.yml)

3. **Otona YouTube Auto - Day 連続失敗**
   - #7〜#9 全失敗・成功は #6（2026-05-18T20:07 JST 手動）まで
   - YouTube API OAuth tokenの期限切れ疑惑（昨日からの継続課題）

4. **new-youtube auto pipeline 不安定**
   - #45 キャンセル（タイムアウト or 多重起動衝突）
   - #46 失敗
   - #47/#48 が同秒（02:54:02 と 02:54:03）に二重スタート → cron多重定義の影響

### ⚠️ 注意

- 本日 03:15 時点で確認できた成功発火は **note Auto Post #72 のみ**。映像系（YT・Shorts・Otona・new-YT）は今朝以降の cron が動くまで「失敗継続中」が続く想定。

### 🟢 ポジティブ

- note Auto Post は安定稼働中（#70・#71・#72 連続成功）。1本目（#048・¥100）公開済。

---

## 【明日（= 本日 07:00 以降）の予定】

- 07:00 / 07:50 cron 起動を監視 — 次回レポート（06:00 JST）以降で結果反映
- YouTube系3ワークフロー（samurai / Shorts / Otona）のエラーログを確認しスクリプト修正
  - 推奨: 一旦 workflow_dispatch で1本だけ走らせて exit code と stderr を採取
- new-youtube auto pipeline の cron 多重定義（07-07:30 を10分刻みで4個など）を1個に整理
- note Auto Post は現状維持で OK・残4スロット（11:50/15:50/19:50/22:50）の自動発火を待つ

---

## 【未確認 / 留意事項】

- 本日 07:00 以降のcron結果は本レポートには含まれない（時刻未到来）
- 失敗runのログ本文は未読（再確認には個別run画面アクセスが必要）
- new-youtube #47/#48 は実行中のため最終ステータス未確定
