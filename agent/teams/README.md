# チーム編成 (2026-05-24 発足)

## 編成方針
- **総括班**（うっちー様 + Main Claude）が全体指揮・収益実態把握・最終意思決定
- 各班は**明確なKPI**を持ち、**自律的に提案・実装**を進める
- 班間連携は総括班経由で調整（特にA-B、C-D、E-Aは密接）
- subagent並列実行可能（Main Claude が dispatch）

## 班構成

| 班 | ミッション | KPI / ゴール | 連携 |
|---|---|---|---|
| **総括班** | 全体監督・収益実態日次把握・ヒトモノカネジョウホウ管理 | 月次収益、KPIダッシュボード | 全班 |
| **A班** | note収益化・記事内アプリ展開・200→500本拡張 | note月売上、購入転換率 | B班・E班 |
| **B班** | 200アプリ改善・PWA→ネイティブ化・HP連動 | 月額500円購読数、アクセス回数 | A班 |
| **C班** | 歴史YT（通常＋ショート）品質・本数 | **再収益化（あと1767時間）→3000時間** | E班 |
| **D班** | 大人YT（通常＋ショート）立ち上げ | **登録500人達成** | E班 |
| **E班** | HP進化・X/Instagram拡散・3本目YT検討・新規開拓 | 流入数、ブランド認知 | 全班 |
| **F班** | E班から派生する新規プロジェクト | 案件発生時に組成 | E班 |

## 班ファイル
- `agent/teams/A_note.md` — A班ミッション詳細
- `agent/teams/B_200apps.md`
- `agent/teams/C_history_yt.md`
- `agent/teams/D_otona_yt.md`
- `agent/teams/E_hp_diffusion.md`
- `agent/teams/dashboard.md` — 総括班 ダッシュボード仕様

## Main Claude による班 dispatch 方法

班に作業を委譲する場合:
```
Agent tool で subagent_type=Explore or general-purpose で起動
prompt:「[X班] あなたは○○班です。agent/teams/X_xxx.md を読んで、現在のKPIに対して最も効果的なアクションを1つ提案・実装してください」
```

並列実行例 (A班とC班同時):
```
1つのmessage内で複数Agent toolを呼ぶ → 並列実行
```

結果は Main Claude が集約 → 総括班（うっちー様）に報告。

## 永続化レイヤー
- `agent/teams/*.md` — 各班の永続ミッション・状態
- `agent/teams/dashboard.md` — 週次/月次KPI記録
- `HANDOFF.md` — プロジェクト全体状態
- `CLAUDE.md` — 規約 + 班編成サマリ
