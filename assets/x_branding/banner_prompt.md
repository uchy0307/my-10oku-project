# X (Twitter) バナー画像生成プロンプト

## サイズ仕様
- **解像度**: 1500 × 500 px (横長 3:1)
- **フォーマット**: PNG または高品質 JPG
- **重要**: スマホ表示時は中央 1500×300 のみ表示。上下 100px 圏内は装飾のみで重要情報を置かない

## デザインコンセプト
**「侍の美学を、現代に転生させる」**
- 漆黒 × 金色 × 朱赤の「凛とした和」
- 抽象モダン (具体的な侍イラストは避ける、シルエット程度)
- 余白を活かした品格

---

## 推奨案A: 「月光と刀身」 (Bing Image Creator / Midjourney 用)

```
A premium minimalist Twitter banner at 1500x500 horizontal aspect ratio,
deep matte black background (#0A0A0F),
subtle traditional Japanese seigaiha (wave pattern) faintly visible in the background,
a single elegant samurai katana blade silhouette in muted gold (#D4AF37) running diagonally across the lower third,
soft moon glow halo behind the blade,
sparse falling sakura petals (abstract, very faint),
empty negative space in upper area for text overlay,
ultra-modern Japanese aesthetic,
dark academia meets samurai philosophy,
cinematic depth of field,
8k quality, masterpiece,
serene yet powerful atmosphere,
no humans, no faces, no logos, no text in the image
```

→ 画像生成後、別途 Canva / Photoshop / Figma で以下のテキスト合成:
- **左 1/3**: 縦書きで「苦徹成珠」(篆書体、 大きく、 金色 #D4AF37)
- **中央**: 「侍の美学で、現代の悩みを問い直す」(白色、明朝体、 中サイズ)
- **右下**: `toi-suite.vercel.app` (薄い白、 小サイズ)
- **下端中央**: 「200の問い ─ 自己診断 ─ 音声ドラマ ─ お役立ちアプリ集」(細い金線で区切り)

---

## 推奨案B: 「霧と山並み」 (より静謐)

```
A premium minimalist Twitter banner at 1500x500,
matte black to dark indigo gradient background,
silhouettes of distant Japanese mountains (Mount Fuji style) in the lower third,
mist and fog rolling between the peaks,
single full moon in upper right with subtle golden glow,
a tiny silhouette of a lone samurai figure on a far mountaintop (very small, far away),
zen aesthetic, wabi-sabi, sumi-e ink wash painting style,
8k cinematic quality,
empty negative space for text overlay,
no text, no logos in the image
```

テキスト合成 (案 A と同様):
- 「苦徹成珠」中央寄せ
- サブコピー: 「死ぬ覚悟が、生き残る道を開く」

---

## 推奨案C: 「無地 + 印章」 (最もシンプル、ブランド強調)

無地黒背景 + 中央に「苦徹成珠」(朱印スタイル) + 下に小さく「SAMURAI AESTHETICS」のみ。
画像生成不要、Canva / Figma 等で直接作成可。

レイアウト:
```
[1500x500 漆黒背景 #0A0A0F]

         ┌────────────────┐
         │                │
         │   苦 徹       │ ← 縦書き篆書体、 金色
         │   成 珠       │
         │                │
         │  ▭ ▭ (朱印章) │
         │                │
         └────────────────┘

  SAMURAI AESTHETICS  ─  toi-suite.vercel.app
```

---

## 生成手順 (うっちー様作業)

### 方法 A: Bing Image Creator (無料、推奨)
1. https://www.bing.com/images/create を開く
2. Microsoft アカウントでログイン
3. 上記「推奨案A」のプロンプト全文を貼り付け → Create
4. 4 枚生成される → 最も良いものをダウンロード
5. **アスペクト比に注意**: Bing は 1024×1024 出力なので、Photoshop / Canva で 1500×500 にトリミング + テキスト合成

### 方法 B: Midjourney (有料、月 $10)
1. Discord で Midjourney bot に `/imagine` → プロンプト末尾に `--ar 3:1` 追加
2. 例: `... --ar 3:1 --v 6`

### 方法 C: Canva (無料、テンプレ豊富)
1. https://www.canva.com/
2. 「Twitter ヘッダー」テンプレ選択
3. 上記レイアウト案 C を再現 (黒背景 + 篆書体「苦徹成珠」+ URL)
4. ダウンロード PNG

### 方法 D: Stable Diffusion ローカル (時間あれば)
- AUTOMATIC1111 等で生成、 ControlNet で構図固定

---

## 注意事項
- **画像内に「うっちー」「UCHY」表記禁止** (CLAUDE.md 規約)
- **GitHub リンク掲載禁止**
- **toi-suite URL は明示**するが、 大きく書かない (主役はブランドコンセプト)
- **配色**: 黒 / 金 / 朱赤の 3 色以内に絞る (5 色以上はノイズ)
- **フォント**: 縦書き「苦徹成珠」は篆書体 or 隷書体、 横書き本文は明朝体 (Yu Mincho / Noto Serif JP)
