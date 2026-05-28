# dispatch スタックパターン参照集

> supervisor cycle が観測した既知・新規のスタックパターンを記録する。
> 更新: 2026-05-23 14:25 JST (supervisor cycle auto-write)

---

## ■ 既知パターン（継承分）

| ID | ワークフロー | 症状 | 根本原因 | 解決策 |
|---|---|---|---|---|
| P-003 | any | dispatch fiber 不可視（is_child:true ゼロ継続） | Agent SDK 子窓が起動しない / クラッシュ | supervisor memory 経由間接伝達で次サイクルまで待機 |
| P-014 | psych_v2 | Spec-compliance gate 失敗 | audio MP3 未コミット | `youtube/psych_v2/audio/{INDEX}.mp3` pre-commit 必須 |
| P-022 | history_v2 | Spec-compliance gate 失敗 | audio MP3 未コミット | `youtube/history_v2/audio/{INDEX}.mp3` pre-commit 必須 |
| P-024 | shorts_v2 | Spec-compliance gate 失敗 | script JSON 未存在 | `youtube/shorts_v2/scripts/short_{INDEX}.json` pre-commit 必須 |
| P-029 | psych_v2 / history_v2 | edge-tts NanamiNeural 生成失敗 | GitHub Actions 環境での edge-tts 音質/可否問題 | pre-committed MP3 で回避 |
| P-035 | any | schedule cron 発火なし | workflow yml の schedule がコメントアウト停止 | schedule 行のコメント解除 + push |
| P-036 | any | workflow_dispatch 後も failure 継続 | gate を満たすアセットが不足している状態で dispatch | アセット補充→コミット→dispatch の順番遵守 |
| P-038 | shorts_v2 | Run#16 以降 schedule 停止 | 連続失敗制御で cron コメントアウト（31249eb） | コード修正完了後に schedule 再有効化 |

---

## ■ 新規パターン（2026-05-23 本サイクル確認）

### P-039: Shorts v2 Wikipedia 画像 URL が GitHub Actions からブロック

| 項目 | 内容 |
|---|---|
| ID | P-039 |
| ワークフロー | shorts_v2 |
| 発見日時 | 2026-05-23 14:20 JST |
| 症状 | `gh workflow run shorts_v2.yml` を発火しても upload に到達せず failure |
| 根本原因 | `youtube/shorts_v2/scripts/short_{INDEX}.json` の `image_urls` が Wikipedia CDN URL（`https://upload.wikimedia.org/...`）を参照 → GitHub Actions runner から fetch すると 403/タイムアウト → `pipeline.mjs` の全画像 fetch 失敗判定 → `exit code 7` で停止 |
| 証拠 | `youtube/shorts_v2/scripts/short_001.json` に `https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Odanobunaga.jpg/800px-...` 確認 / pipeline.mjs L103: `fail("all N images failed to fetch", 7)` |
| 影響 | schedule 再有効化だけでは回復不可。コード修正が前提 |
| 解決策（推奨） | Option A: `images/shorts/{INDEX}/` に画像を pre-commit し `image_urls` を `file://` ローカルパス参照に変更 / Option B: Wikimedia 以外の GitHub raw URL 等 Actions からアクセス可能な CDN を使用 |
| 状態 | 🔴 未解決（2026-05-23 14:25 JST 時点） |

---

### P-040: psych_v2 duration gate 過剰厳格（1800s 設定 vs 実動画 ~1620s）

| 項目 | 内容 |
|---|---|
| ID | P-040 |
| ワークフロー | psych_v2 |
| 発見日時 | 2026-05-23 本サイクル調査 |
| 症状 | psych_v2 が psych_001（~27分 = ~1620s）で duration gate 失敗 |
| 根本原因 | `psych_v2.yml` の min duration 閾値が 1800s（30分）に設定されていたため、27分動画が非準拠と判定 |
| 解決策 | commit `7c00439`（2026-05-23 14:12 JST）で 1800s → 1500s（25分）に緩和 ✅ 修正済 |
| 状態 | ✅ 解消済み（14:12 JST パッチ適用・コミット済） |

---

## ■ 継続監視中

| 観測事象 | 継続期間 | 備考 |
|---|---|---|
| is_child:true ゼロ（dispatch fiber 不可視） | 6h+ | P-003 相当。supervisor → memory 間接伝達で継続 |
| psych_v2 schedule 停止中 | 2026-05-23 全日 | aeb6928 コメントアウト。P-014+P-040 修正済のため再有効化可能状態 |
| Shorts v2 schedule 停止中 | Run#16 以降 | P-039 コード修正が先決。修正前の再有効化は無意味 |

---

更新: 2026-05-23 14:25 JST (supervisor auto-write / P-039 new / P-040 resolved)
