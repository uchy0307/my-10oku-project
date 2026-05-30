# 案 A 確定版 - X アバター (400x400) Bing / Canva 用

## オプション 1: Bing Image Creator (画像生成版)

```
Square 400x400 profile picture image, pure matte black void background hex 0A0A0F. Center: four Japanese kanji 苦徹成珠 in traditional tensho seal script style arranged in 2x2 grid layout (top row 苦 徹, bottom row 成 珠), elegant deep antique gold color hex D4AF37 with subtle metallic gold leaf texture, bold thick strokes. Thin gold border outline around the kanji block. No human face, no logo, no other text, ultra-minimal premium Japanese calligraphy art piece. Cinematic depth.
```

→ 生成後 **1024x1024 → 400x400 にリサイズ** (Canva or オンラインリサイザー [imageresizer.com](https://imageresizer.com/))

## オプション 2: Canva (推奨、 確実、 5 分) ⭐

Bing は漢字を崩しがち → **Canva で直接作成が確実**:

1. https://www.canva.com/ → 「カスタムサイズ」 → **400 × 400 px**
2. 背景色: `#0A0A0F` (漆黒)
3. テキスト追加: **「苦徹成珠」**
   - フォント検索: **「Yuji Boku」** (Google Fonts、 篆書系)
     - もしくは「BIZ UDPMincho」「源界明朝」「貂明朝」等
   - サイズ: 約 100-130pt
   - 色: `#D4AF37` (金色)
   - 配置: 2x2 グリッド (苦 徹 / 成 珠) もしくは縦書き 1 列
4. 装飾: 上下左右に細い金線 (任意、 装飾過多に注意)
5. **PNG エクスポート** → ファイル名 **`avatar.png`**

## 保存先 (必須)

**`C:\Users\user\Documents\10oku-project\assets\x_branding\avatar.png`**

## サイズ要件

- 400 × 400 px (正方形)
- **円形に切り抜き表示**される → 四隅 50px 圏内は描かない (見切れる)
- ファイル形式: PNG or JPG
- ファイルサイズ: 1MB 以下推奨

## 文字レイアウト例

### 案 A-1: 2x2 グリッド
```
┌───────────┐
│  苦   徹  │
│           │
│  成   珠  │
└───────────┘
```

### 案 A-2: 縦書き 1 列
```
┌───────┐
│   苦  │
│   徹  │
│   成  │
│   珠  │
└───────┘
```

### 案 A-3: 朱印章スタイル「苦」一文字
```
┌───────────┐
│           │
│    苦    │  ← 太い篆書、 朱赤 (#A52A2A) で印章風
│           │
└───────────┘
```

→ **2x2 グリッド (案 A-1)** が一番ブランド明示で覚えやすい、 推奨。

## 確認方法

ファイル保存後:
```
python scripts/_x_profile_update.py --dry-run
```
→ `[アバター] ...avatar.png (exists=True)` と出れば OK
