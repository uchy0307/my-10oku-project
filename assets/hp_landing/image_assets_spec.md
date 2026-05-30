# HP / アプリ 画像アセット仕様 (2026-05-30 色味整合 再設計)

> 指摘: HP が侍一色で「人生色 (アプリ)」「恋愛色 (大人)」と不整合。
> 解決: ブランド「苦徹成珠」は umbrella 維持、 各コンテンツ柱に色味別イメージを付与。

## 色味 × 画像方針

| 領域 | 色味 | ビジュアル方向 |
|---|---|---|
| ブランド全体 (hero/logo) | 哲学 (中立) | 墨絵 zen・抽象・苦徹成珠。 どの層も拒絶しない |
| 6軸自己診断 | 人生色 | 羅針盤 / 六角レーダー / 道 |
| 200の問い (アプリ) | 人生色 | 本・問い・対話・光 |
| 音声ドラマ | 歴史色 | 侍シルエット・月・刀 |
| 大人の心理学 | 恋愛色 | やわらかい光・距離・ддва人影 |

---

## 生成プロンプト (Gemini / Bing Image Creator)

### 1. HP hero 背景 (1920x1080) — 既存 banner.png 流用可、 作り直すなら↓
```
A serene zen ink-wash (sumi-e) hero background image, 1920x1080. Soft washi paper warm off-white background hex F8F4E9. Distant misty mountains in gentle black ink gradients across the lower third. A single small vermilion red full moon hex A52A2A in the upper right. Vast empty negative space in the center for text overlay. Wabi-sabi, philosophical calm, universal and timeless (not specifically historical). No people, no text, no logos. 8k, hand-painted feel.
```

### 2. ロゴ/アバター (400x400) — 篆書版 (中立、 全色味対応) ⭐推奨切替
```
Square 400x400 logo. Warm off-white washi background hex F8F4E9. Center: four kanji 苦徹成珠 in elegant black tensho seal script, 2x2 grid layout. A single small vermilion red seal stamp hex A52A2A in the bottom right corner. Ultra-minimal, refined, works as a universal brand mark. No helmet, no people. 8k.
```
→ 兜版 (avatar.png) は「音声ドラマ (歴史色)」の柱アイコンに格下げ転用

### 3. 柱① 6軸自己診断 (人生色, 600x400)
```
Minimalist illustration 600x400, warm off-white background. A subtle hexagonal radar chart shape overlaid with a delicate brass compass, thin gold lines hex D4AF37. Calm, introspective, "finding your direction in life" mood. Sumi-e accent. No text. 8k.
```

### 4. 柱② 200の問い (人生色, 600x400)
```
Minimalist illustration 600x400, warm off-white background. An open traditional Japanese book with a single beam of soft light rising from its pages, suggesting questions and self-dialogue. Black ink and vermilion accent. Contemplative, warm. No text. 8k.
```

### 5. 柱③ 音声ドラマ (歴史色, 600x400)
```
Minimalist illustration 600x400, dark ink background. A lone samurai silhouette under a large moon, katana at side, sumi-e ink style. Historical, dramatic, "tales of the warriors" mood. Gold moon accent hex D4AF37. No text. 8k.
```

### 6. 柱④ 大人の心理学 (恋愛色, 600x400)
```
Minimalist illustration 600x400, soft warm gradient background (cream to dusty rose). Two abstract human silhouettes at a meaningful distance, soft bokeh light between them, suggesting adult relationships and emotional psychology. Tender, slightly melancholic, late-night mood. Subtle vermilion accent. No faces, no text. 8k.
```

---

## 保存先

`C:\Users\user\Documents\10oku-project\assets\hp_landing\` に:
- `hero.png` (1920x1080、 任意。 無ければ banner.png 流用)
- `logo.png` (400x400、 篆書版。 nav/footer ロゴ用)
- `pillar_shindan.png` (600x400)
- `pillar_toi.png` (600x400)
- `pillar_drama.png` (600x400)
- `pillar_otona.png` (600x400)

→ 保存後「画像できた」と伝えれば Claude が HP HTML に組込 + 再 commit

---

## タイトル整合チェック (色味別)

| 媒体 | 現タイトル傾向 | 色味整合 | 対応 |
|---|---|---|---|
| 200アプリ (note) | 「1on1マスターAI」等 人生ツール名 | ✅ 人生色 OK | 維持 |
| 歴史 YT | 武将名・合戦・江戸庶民 | ✅ 歴史色 OK | バズ枠追加済 |
| 大人 YT | 心理学用語系 (旧) | ⚠ 学術寄り | 恋愛色 topics に切替済 (topics_psych_diverse.json) |
| HP コピー | 「死ぬ覚悟が生き残る道」 | ⚠ 歴史色のみ | hero は哲学コピー、 各柱で色味別コピー追加 |
