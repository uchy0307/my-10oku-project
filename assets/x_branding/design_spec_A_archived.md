# 案 A 確定仕様: 漆黒 + 金箔 (toi-suite Web / X / 全媒体共通)

> 2026-05-30 採用決定。 ブランド統一スタイル。 全 web/SNS で同一パレット。

## カラーパレット (5 色のみ)

| 用途 | HEX | RGB | 用例 |
|---|---|---|---|
| 背景メイン | `#0A0A0F` | (10, 10, 15) | 全体背景、 ヘッダー |
| 金箔メイン | `#D4AF37` | (212, 175, 55) | ブランド文字、 アクセント線 |
| 金箔深 | `#9C7E1A` | (156, 126, 26) | ホバー、 グラデーション |
| 朱印 | `#A52A2A` | (165, 42, 42) | 印章、 強調 1 点のみ |
| 純白 | `#FFFFFF` | (255, 255, 255) | サブテキスト (透明度 80%) |

⚠ **5 色以上使用禁止**。 5/30 以前のサイトで混乱した教訓。

## タイポグラフィ

### 見出し (ブランド名「苦徹成珠」)
- フォント: **篆書体 / 龍門石碑体 / Tensho**
  - 無料: Google Fonts「[Yuji Boku](https://fonts.google.com/specimen/Yuji+Boku)」
  - 有料: Adobe Fonts「貂明朝」「源界明朝」
- 色: `#D4AF37` (金箔)
- 行間: 1.2
- 文字間: 0.05em

### サブヘッド (キャッチコピー)
- フォント: **明朝**
  - Google Fonts「[Noto Serif JP](https://fonts.google.com/noto/specimen/Noto+Serif+JP)」Weight 500-700
  - もしくは「Yu Mincho」「Hiragino Mincho ProN」
- 色: `#FFFFFF` (純白、 opacity 0.9)
- 行間: 1.5

### 本文
- フォント: **サンセリフ ja**
  - Google Fonts「[Noto Sans JP](https://fonts.google.com/noto/specimen/Noto+Sans+JP)」Weight 400
- 色: `#FFFFFF` (純白、 opacity 0.85)
- 行間: 1.7

### CTA ボタン / URL
- フォント: Noto Sans JP Bold
- 色: `#D4AF37` 文字 + `#0A0A0F` 背景 (線)
- ホバー: 反転 (`#0A0A0F` 文字 + `#D4AF37` 背景)

## レイアウト原則

1. **余白 70%、 コンテンツ 30%** (茶室の床の間ライン)
2. **画面中央寄せ** (左右対称、 完璧バランス)
3. **斜め線 1 本のみ** (刀身を象徴、 装飾は最小)
4. **朱印章 1 点のみ** (アクセント、 過剰禁止)
5. **アニメーション最小** (fade-in、 zoom 程度、 派手な動き禁止)

## コンポーネント例

### ヒーローセクション (Landing)

```jsx
<section className="hero">
  <div className="hero-bg" style={{background: '#0A0A0F'}} />
  <div className="hero-content">
    <h1 className="brand-name">苦徹成珠</h1>
    <div className="brand-line" />  {/* 細い金線 */}
    <p className="brand-tagline">侍の美学で、現代の悩みを問い直す。</p>
    <a className="cta-btn" href="/sample">7問の無料診断 ▶</a>
  </div>
  <div className="hero-seal" />  {/* 右下 朱印章 */}
</section>
```

```css
.hero {
  min-height: 100vh;
  background: #0A0A0F;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}
.brand-name {
  font-family: 'Yuji Boku', serif;
  font-size: clamp(4rem, 12vw, 10rem);
  color: #D4AF37;
  letter-spacing: 0.1em;
  text-align: center;
}
.brand-line {
  width: 120px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #D4AF37, transparent);
  margin: 2rem auto;
}
.brand-tagline {
  font-family: 'Noto Serif JP', serif;
  font-weight: 500;
  color: rgba(255,255,255,0.9);
  font-size: clamp(1rem, 2vw, 1.5rem);
  text-align: center;
  margin-bottom: 3rem;
}
.cta-btn {
  display: inline-block;
  padding: 1rem 3rem;
  border: 1px solid #D4AF37;
  color: #D4AF37;
  font-family: 'Noto Sans JP', sans-serif;
  font-weight: 700;
  text-decoration: none;
  transition: all 0.3s;
}
.cta-btn:hover {
  background: #D4AF37;
  color: #0A0A0F;
}
.hero-seal {
  position: absolute;
  bottom: 5%;
  right: 5%;
  width: 80px;
  height: 80px;
  background: #A52A2A;
  opacity: 0.8;
  clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%);
}
```

### ナビゲーション
- 背景: `#0A0A0F` (固定、 opacity 0.95、 backdrop-blur)
- リンク: `#D4AF37` 文字、 ホバー時 `#9C7E1A`
- アクティブ: 下線 1px `#D4AF37`

### カード
- 背景: `#0A0A0F` + border `1px solid rgba(212, 175, 55, 0.2)`
- ホバー: border opacity 0.6 + 微細な金光 shadow

### フッター
- 背景: `#0A0A0F`
- リンク: `#FFFFFF` opacity 0.7 / ホバー `#D4AF37`
- 中央に小さく「苦徹成珠 ─ 侍の美学」 篆書体 + URL

## アニメーション仕様

| イベント | 動き | 速度 |
|---|---|---|
| ヒーロー表示 | fade-in + 微 zoom (1.02→1.0) | 1.2s ease-out |
| ボタンホバー | 背景色反転 | 0.3s ease |
| ナビリンクホバー | 文字色 fade + 下線伸び | 0.25s ease |
| カードホバー | border opacity + 微浮き上がり (translateY -2px) | 0.3s ease |

## 禁止事項

- ❌ 派手なアニメーション (parallax、 video bg、 gradient animate)
- ❌ 5 色以上の使用
- ❌ 写真素材 (静物画 / 風景写真) の濫用
- ❌ 装飾文字 (草書、 隷書以外)
- ❌ 「うっちー」「UCHY」「Uchy」名乗り表記
- ❌ GitHub リンク
- ❌ 「47歳管理職」表現

## 適用範囲

| 媒体 | 適用 | 担当 |
|---|---|---|
| X バナー (1500x500) | 案 A | Bing 生成 + scripts/_x_profile_update.py で upload |
| X アバター (400x400) | 案 A (篆書) | Bing 生成 or Canva |
| toi-suite Web (Landing/Footer/全ページ) | 案 A | 別 repo `uchy0307/toi-suite` で適用 (本ファイル参照) |
| LP `uchy-lp` | 案 A | 別 repo or 別管理 |
| note 記事フッター | 案 A 配色は不要 (テキストのみ) | 既に inject 済 |
| YouTube サムネ | 別仕様 (現状黄背景 / 大人 黒帯維持) | 別 task |
| dashboard (内部用) | 適用任意 | 内部ツール |
