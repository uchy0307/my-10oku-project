# 案 A 確定版 - X バナー (1500x500) Bing Image Creator プロンプト

## 推奨プロンプト (英語、 そのままコピペ)

```
Ultra-luxurious minimalist Twitter banner at 1500x500 horizontal aspect ratio. Pure matte black void background hex 0A0A0F. Center-left area: vertical Japanese calligraphy kanji 苦徹成珠 in elegant tensho seal script style, deep antique gold color hex D4AF37 with subtle metallic gold leaf texture, large bold strokes. Center-right area: single thin gold leaf diagonal brushstroke representing katana blade edge, very subtle. Far right bottom corner: tiny vermilion red hanko japanese seal stamp accent. Massive negative space, refined wabi-sabi elegance, Ginza high-end bar interior aesthetic crossed with traditional tea ceremony tokonoma. No human figures, no logos. Cinematic depth, ultra-detailed gold leaf texture, 8k masterpiece, photorealistic.
```

## バックアップ案 (Bing で kanji 生成が崩れた場合用、 漢字なし版)

```
Ultra-luxurious minimalist Twitter banner 1500x500, pure matte black void background hex 0A0A0F. Single delicate vertical gold leaf brushstroke representing a katana blade in center-left, deep antique gold hex D4AF37 with metallic texture. Massive negative space on the right. Tiny vermilion red hanko seal stamp accent at far right bottom. Wabi-sabi minimalism, Ginza high-end bar aesthetic. No text, no humans, no logos, refined elegance, cinematic 8k.
```
→ 生成後、 Canva / Photoshop で「苦徹成珠」(篆書、 金色) を追加合成

## 生成手順 (うっちー様 5 分)

1. https://www.bing.com/images/create を開く (Microsoft 無料アカウント)
2. 上記プロンプト全文コピペ
3. **「作成」** クリック → 4 枚生成
4. 一番気に入った 1 枚を **ダウンロード** (.jpg or .png)

## サイズ整形 (必須)

Bing 出力は **1024x1024 正方形** → X バナー 1500x500 に整形必要:

### 方法 A: Canva (推奨、 無料、 5 分)
1. https://www.canva.com/ → カスタムサイズ 1500x500
2. Bing 画像をアップロード → 中央配置 + 上下をマット黒で埋める
3. テキスト「苦徹成珠」が崩れていれば、 ここで上書き (フォント: Yuji Boku、 色 #D4AF37)
4. **エクスポート** PNG → 1500x500 確認 → ファイル名 **`banner.png`**
5. **`C:\Users\user\Documents\10oku-project\assets\x_branding\banner.png`** に保存

### 方法 B: Photoshop / Figma
- 1500x500 のキャンバスで同様

## 保存先 (必須)

**`C:\Users\user\Documents\10oku-project\assets\x_branding\banner.png`**

このパスに保存されていれば、 私 (Claude) が `_x_profile_update.py` で自動 upload します。

## 確認方法

ファイル保存後、 ターミナルで:
```
python scripts/_x_profile_update.py --dry-run
```
→ `[バナー] ...banner.png (exists=True)` と出れば OK
