# SCHEDULE.md - Claude の仕事スケジュール

> このファイルは「私の永続的な仕事スケジュール」です。
> セッション開始時に CLAUDE.md と一緒に必ず読みます。
> 変更があれば編集して push。

---

## 🕗 毎日のリズム (Cron 自動実行)

| 時刻 | タスク | 担当 | 場所 |
|------|--------|------|------|
| **08:00** | UchyDailyCycle 起動 | scheduled task | `daily_cycle.py` |
| 08:00-08:30 | ① ストック確認・台本補充 (歴史/大人/歴史S/大人S 各30本維持) | Gemini | `step_scripts` |
| 08:30-09:00 | ② 音声生成 (足りない分のみ edge-tts) | edge-tts | `step_audio` |
| 09:00-09:30 | ③ whisper SRT + refine_srt (原稿テキスト合成) | whisper | `step_whisper` |
| 09:30-14:00 | ④ 動画化＋投稿 (歴史3本 + 歴史S5本 + 大人3本 + 大人S5本 = 16本) | ffmpeg + YouTube API | `step_upload` |
| 14:00-14:30 | ⑤ note 添付 20件 | Playwright | `step_note_attachments` |
| 14:30 | 日次レポート完了通知 → messages.json | - | - |

| 時刻 | サブシステム | 内容 |
|------|--------------|------|
| 毎5分 | inbox_auto_responder | スマホ → Claude の受信確認返信 |
| 常時 | UchyButtonServer | pc.uchy0307.uk バックエンド (pythonw) |

---

## 📊 週次ゴール

| KPI | 目標 | 担当ファイル |
|-----|------|--------------|
| 歴史侍YT 再生時間 | +1700h (再収益化トリガー) | `youtube/history_v2/` |
| 歴史侍YT 投稿 | 3本/日 × 7 = 21本/週 | `build_history_3.bat` |
| 歴史ショート | 5本/日 × 7 = 35本/週 | `build_history_shorts_5.bat` |
| 大人心理学YT | 3本/日 × 7 = 21本/週 | `build_otona_3.bat` |
| 大人ショート | 5本/日 × 7 = 35本/週 | `build_otona_shorts_5.bat` |
| note 公開 | 5本/日 × 7 = 35本/週 | `note-auto/` |

---

## 📅 月次マイルストーン

### Phase 1 (現在進行中): 既存アセットの収益化
- [ ] 歴史侍YT 再収益化 (+1700h)
- [ ] 大人心理学YT 1000登録
- [ ] toi-suite UI/UX 改善 (転換率 ↑)
- [ ] note → toi-suite 動線強化

### Phase 2 (Phase1進捗安定後):
- [ ] LP 動線改善 (noteからLP / LPからnote)

### Phase 3 (Phase2完了後):
- [ ] 3本目チャンネル「うっちー問答室」設計→立ち上げ

---

## 🎯 今セッションで対応中の課題 (動的)

`TaskList` ツールで管理。スクリプトの実態:
- `scripts/inbox.json` 未読チェック
- `messages.json` 既送通知ログ
- 各 BAT 実行状況 (`scripts/logs/`)

---

## 🚨 トラブル時の手動切替

| 症状 | 対処 |
|------|------|
| pc.uchy0307.uk が 502 | エクスプローラで `scripts/restart_button_server.bat` ダブルクリック |
| daily_cycle 走らない | 管理者PowerShellで `Start-ScheduledTask -TaskName 'UchyDailyCycle'` |
| 大人系が歴史チャンネルに誤投稿 | OTONA_YOUTUBE_REFRESH_TOKEN 未設定 → `scripts/setup_otona_token.ps1` |
| 字幕が誤認識 (採隔/大ら等) | `scripts/refine_srt.py --kind history --all` |
| 画像ストック不足 (<1000枚) | スマホで「🖼️ Wiki画像 補充」ボタン |

---

## 📝 セッション開始時の私のチェックリスト

1. `scripts/inbox.json` 未読を最優先で読む
2. `HANDOFF.md` 最新状態確認
3. `messages.json` 直近応答履歴
4. **`SCHEDULE.md` (本ファイル) で当日の予定確認**
5. `agent/memory/MEMORY.md` 嗜好リフレッシュ
6. ボタンサーバー稼働確認: `curl http://localhost:7373/api`

---

## ✏️ 編集ルール
- うっちー様が直接書き込んでOK (私は次セッションで読む)
- 大きな変更時は `HANDOFF.md` 「直近の重要決定」にも反映
- Cron 時刻変更時は `scripts/register_daily_cycle.ps1` も同期更新
