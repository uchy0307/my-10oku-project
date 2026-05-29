# X (Twitter) プロフィール画像 (アバター) 生成プロンプト

## サイズ仕様
- **解像度**: 400 × 400 px (正方形)
- **円形にクロップ**される → 四隅 50px 圏内は描かない (見切れる)
- **フォーマット**: PNG (透明背景なし、 JPG 可)

---

## 推奨案A: 篆書体「苦徹成珠」(最もブランド明示、推奨)

無地黒背景 + 中央に「苦徹成珠」4 文字を篆書体で配置。

レイアウト (テキスト合成、 画像生成不要):
```
[400x400 漆黒 #0A0A0F]

      苦 徹
      成 珠     ← 縦書き 2 列 × 2 段、 金色 #D4AF37、 篆書体
```

または 1 列縦書き:
```
[400x400]
   苦
   徹
   成
   珠      ← 1 列縦書き、 大きく
```

**作り方 (Canva / Figma)**:
1. 新規 400×400 px キャンバス
2. 背景: 漆黒 #0A0A0F
3. テキスト「苦徹成珠」を追加
4. フォント: **「龍門石碑体」「篆書体」「Tensho」**等
   - 無料: Google Fonts に「Yuji Boku」「Yuji Hentaigana」(古典書体)
   - 有料: Adobe Fonts「貂明朝」「源界明朝」
5. 色: 金色 #D4AF37 + 微細グラデーション
6. ふちに細い朱赤 (#A52A2A) の枠線 (任意)
7. PNG エクスポート

---

## 推奨案B: 月夜の刀身先端 (抽象、神秘的)

```
A circular profile picture, 400x400 px,
deep black background with subtle indigo gradient at edges,
center: a polished katana blade tip pointing upward,
moonlight reflection on the steel,
faint single sakura petal floating beside,
zen minimalism,
no text, no logos,
ultra-detailed metallic surface,
cinematic lighting,
8k quality, professional aesthetic
```

→ Bing Image Creator で生成 → 400×400 に円形クロップ

---

## 推奨案C: 朱印 + 「苦」一文字

最小構成、 シンプル極致。
- 漆黒背景
- 中央に **朱印章スタイル**で「苦」一文字 (篆書体)
- 周囲に篆書「徹成珠」をうっすら配置 (or 装飾のみ)

「苦徹成珠」のうち最も核となる「苦」を強調 → 「苦しみの中で輝く」哲学を強調。

---

## 推奨案D: 兜の正面シルエット (武家らしさ)

```
A circular profile picture, 400x400 px,
matte black background,
center: silhouette of a kabuto (samurai helmet) front view,
crescent moon ornament (maedate) on the helmet,
silhouette in dark gold (#D4AF37) on black,
minimal flat design,
no face beneath the helmet (empty inside),
modern Japanese aesthetic,
no text, no humans
```

→ Bing で生成 → 円形クロップ

---

## 推奨順位

| 順位 | 案 | 理由 |
|---|---|---|
| 1 | **案A 篆書「苦徹成珠」** | ブランド名直接表示 = 検索/記憶優位 |
| 2 | 案D 兜シルエット | 武家らしさ + シンプル + 覚えやすい |
| 3 | 案C 「苦」朱印 | 最も尖った哲学訴求 |
| 4 | 案B 刀身月光 | 美しいが抽象すぎてブランド連想弱い |

→ **案A を推奨** (1 ヶ月運用後、 効果で他案に変更可)

---

## 生成手順

### 案A の場合 (Canva 推奨)
1. https://www.canva.com/ ログイン
2. 「カスタムサイズ」400 × 400
3. 背景色 #0A0A0F
4. テキスト「苦徹成珠」追加
5. フォント検索で「篆書」「Tensho」「Seal Script」
6. 色 #D4AF37 (金)
7. PNG ダウンロード

### 案B/D の場合 (Bing Image Creator)
1. https://www.bing.com/images/create
2. プロンプト貼り付け → 生成
3. ダウンロード後、円形クロップアプリ (https://crop-circle.imageonline.co/ 等)

---

## 注意事項
- **円形にクロップされる** → 四隅 (約 50px) は表示されない
- **小さく表示される** (タイムラインで 40×40 px 程度) → 細かい線/文字は不可
- **シンプル + 高コントラスト** が鉄則
- **「うっちー」「UCHY」表記禁止** (CLAUDE.md 規約)
