# Shorts Pipeline 重複 upload バグ 修正レポート

session_id: `shorts-pipeline-fix-20260520-001`
日付: 2026-05-20

## 真因
- `youtube/scripts/shorts_pipeline.mjs` の旧 `pickSourceCandidates` は
  channel uploads を「新しい順」で並べて `processed` 集合に無い最初の videoId を選ぶだけだった。
- `CLIP_START` は env default `30` 固定 → 全 Short が秒位置 30〜88 で抽出される。
- 同 source の本編動画は冒頭が似ているため、秒位置 30 周辺は ナレ / 映像 / テロップ が酷似 → 4 連続「中身が全部同じ」Short がアップされた。

## 修正方針 (user 明示の最終確定)
1. source = 侍チャンネル `@japanese.samurai.channel` 既存 upload の長尺本編 (full archive)
2. `shorts_state.json#usedSegments[{sourceVideoId, startSec}]` で 全組合せを永続管理
3. **古い順 (oldest first)** で video を rotation
4. `START_GRID = [60, 300, 600, 900, 1500, 1800, 2400]` から未使用 (videoId, startSec) を選択
5. rotation 順: startSec 外 × videoId 内 (= まず別動画を優先)
6. download/upload 前に slot を予約 commit (失敗時の再選択ループ防止)
7. **duplicate gate**: 同 source + ±5s startSec を構造的に拒否

## 変更ファイル
| ファイル | 変更 |
|---|---|
| `youtube/scripts/shorts_pipeline.mjs` | 全面改訂 (133 → 552 行) |
| `youtube/scripts/shorts_pipeline.test.mjs` | 新規 (204 行, 20 テスト) |
| `.github/workflows/youtube_shorts_auto.yml` | `clip_start` default `''` (auto-pick) |

## commit SHA
- `eb4b091` — feat(shorts): rewrite source rotation (auto-sync 経由)
- `1b2e66a` — fix(shorts): final corrections + workflow yml (auto-sync 経由) ← HEAD

## ユニットテスト
```
20/20 pass
- isDuplicateSegment: 同/隣接/別 video の判定
- pickUnusedComboPure: rotation 順 / duration バリデーション / 全枯渇 / 旧バグ再現シナリオ
- backfillUsedSegments: 旧 records → usedSegments への移行
- 定数 sanity: START_GRID 単調増加 / CLIP_DURATION ≤ 59
```

## 旧バグ再現テスト
```
"既存 4 本 (重複バグ再現シナリオ) が同じ source/start を返さない"
→ 旧 default startSec=30 で 4 video が used 状態でも、新ロジックは startSec=60 から rotation
→ assert.notEqual(picked.startSec, 30) ← pass
```

## 動作デモ (実 state + 仮想 channel uploads)
既存 7 records を backfill すると 7 entries @ startSec=30 が usedSegments に入り、
次 10 Runs は すべて unique な (sourceVideoId, startSec) を選択：

```
Run 1: source=OLD_A      startSec=60s   ← 最古 video から
Run 2: source=OLD_B      startSec=60s
Run 3: source=OLD_C      startSec=60s
...
Run 10: source=HtcdgPGQz74 startSec=60s

全 10 pick が unique か: ✅ YES
```

## verify 状況
- ✅ ローカル unit test: 20/20 pass
- ✅ 動作 demo: 連続 10 Run で all unique
- ⏳ 実 workflow trigger: 次 cron `13:30 UTC` (= JST 22:30) に自動発火
- ⏳ Short URL 実視認: Chrome MCP に browser 未接続 (`list_connected_browsers` = `[]`)。
  cron 完了後 (約 13:45 UTC 頃) に `shorts_state.json` に新 record が追加されるため、
  そこから `shortsUrl` を取得して視認可能。

## 重複再発防止の構造保証
1. **usedSegments**: 全 (sourceVideoId, startSec) を永続記録
2. **pickUnusedComboPure**: used に含まれる combo を確実に skip
3. **duplicate gate** (main 内): 選択後にも `isDuplicateSegment` で再確認 → 衝突なら throw
4. **reserve before upload**: state を先に commit → 失敗しても次 Run で同 slot 再選択されない

これらが組み合わさり、同じ source + 近接 startSec の重複 upload は コードレベルで不可能 になっている。
