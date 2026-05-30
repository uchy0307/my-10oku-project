# 統一デザイン仕様書 (2026-05-30 確定): HP / X / 全媒体共通

> **採用案**: 案 B 墨絵 zen (世界観 / 背景) + 案 C 兜 (ロゴ / アクセント)
> ハイブリッドにより「静謐な大人の凄み」を体現

## 採用画像 (本 repo `assets/x_branding/`)

| ファイル | 用途 | 内容 |
|---|---|---|
| `banner.png` (1500x500) | X / HP ヒーロー背景 | 墨絵 zen: 山並み + 朱赤の月 + 篆書「苦徹成珠」|
| `avatar.png` (400x400) | X / HP ロゴ / favicon | 兜シルエット + 金縁 + 赤グロー |

→ HP (toi-suite) でもこの 2 枚を ヒーロー / ロゴに流用可能 (別 repo に同ファイルを配置)

## カラーパレット (5 色のみ)

| 用途 | HEX | RGB | 用例 |
|---|---|---|---|
| 背景メイン | `#F8F4E9` | (248, 244, 233) | 和紙白、 全体背景 |
| 墨色 | `#2C2C30` | (44, 44, 48) | 本文、 見出し |
| 朱赤 | `#A52A2A` | (165, 42, 42) | アクセント、 月、 印章、 CTA |
| 金 | `#D4AF37` | (212, 175, 55) | 兜縁、 高級感アクセント (使用最小限) |
| 純白 | `#FFFFFF` | (255, 255, 255) | カード背景 |

⚠ **5 色以上使用禁止**

## タイポグラフィ

### 見出し (ブランド名 / セクション titel)
- フォント: **Yuji Boku** (Google Fonts、 篆書系) or **Noto Serif JP Bold**
- 色: `#2C2C30` (墨色)
- 行間: 1.3
- 文字間: 0.05em

### サブヘッド / 本文
- フォント: **Noto Serif JP** (明朝)
- 色: `#2C2C30` opacity 0.85
- 行間: 1.7

### CTA ボタン
- フォント: Noto Sans JP Bold
- 色: 白文字 `#FFFFFF` + 朱赤背景 `#A52A2A`
- ホバー: 反転 (`#A52A2A` 文字 + 透明背景 + 朱赤 1px 線)

### ナビ / フッター
- フォント: Noto Sans JP Regular
- 色: `#2C2C30`、 ホバー時 `#A52A2A`

## レイアウト原則

1. **余白 70%、 コンテンツ 30%** (茶室の床の間ライン)
2. **画面中央寄せ** (左右対称)
3. **山並み画像 (banner.png 流用) をヒーロー背景**
4. **兜シルエット (avatar.png) を右上 nav ロゴ + フッター中央**
5. **朱赤アクセント 1 点のみ** (月 / 印章 / CTA)
6. **アニメーション最小** (fade-in、 zoom 程度)

## ヒーローセクション 実装例 (React/CSS)

```jsx
<section className="hero">
  <div className="hero-bg">
    <img src="/banner.png" alt="" className="hero-bg-img" />
    <div className="hero-overlay" />
  </div>
  <div className="hero-content">
    <h1 className="brand-name">苦徹成珠</h1>
    <p className="brand-tagline">侍の美学で、現代の悩みを問い直す。</p>
    <a className="cta-btn" href="/sample">7問の無料診断 ▶</a>
  </div>
</section>
```

```css
.hero {
  min-height: 100vh;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
.hero-bg { position: absolute; inset: 0; overflow: hidden; }
.hero-bg-img { width: 100%; height: 100%; object-fit: cover; opacity: 0.5; }
.hero-overlay {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(248,244,233,0.4) 0%, rgba(248,244,233,0.95) 100%);
}
.hero-content {
  position: relative;
  text-align: center;
  z-index: 2;
}
.brand-name {
  font-family: 'Yuji Boku', 'Noto Serif JP', serif;
  font-size: clamp(4rem, 12vw, 10rem);
  color: #2C2C30;
  letter-spacing: 0.1em;
}
.brand-tagline {
  font-family: 'Noto Serif JP', serif;
  font-weight: 500;
  color: rgba(44,44,48,0.85);
  font-size: clamp(1rem, 2vw, 1.5rem);
  margin: 2rem 0 3rem;
}
.cta-btn {
  display: inline-block;
  padding: 1rem 3rem;
  background: #A52A2A;
  color: #FFFFFF;
  font-family: 'Noto Sans JP', sans-serif;
  font-weight: 700;
  text-decoration: none;
  transition: all 0.3s;
}
.cta-btn:hover {
  background: transparent;
  color: #A52A2A;
  border: 1px solid #A52A2A;
}
```

## ナビゲーション

```jsx
<nav className="nav">
  <a href="/" className="nav-logo">
    <img src="/avatar.png" alt="苦徹成珠" />  {/* 兜ロゴ */}
    <span>苦徹成珠</span>
  </a>
  <ul className="nav-links">
    <li><a href="/sample">6軸自己診断</a></li>
    <li><a href="/apps/200">200の問い</a></li>
    <li><a href="/drama">音声ドラマ</a></li>
    <li><a href="/apps">便利アプリ</a></li>
  </ul>
</nav>
```

```css
.nav {
  background: rgba(248,244,233,0.95);
  backdrop-filter: blur(10px);
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky; top: 0; z-index: 100;
  border-bottom: 1px solid rgba(44,44,48,0.1);
}
.nav-logo { display: flex; align-items: center; gap: 0.5rem; text-decoration: none; }
.nav-logo img { width: 40px; height: 40px; border-radius: 50%; }
.nav-logo span { font-family: 'Yuji Boku', serif; color: #2C2C30; font-size: 1.2rem; }
.nav-links a {
  color: #2C2C30;
  text-decoration: none;
  font-family: 'Noto Sans JP', sans-serif;
  transition: color 0.25s;
}
.nav-links a:hover { color: #A52A2A; }
```

## フッター

```jsx
<footer className="footer">
  <img src="/avatar.png" alt="苦徹成珠" className="footer-logo" />
  <p className="footer-brand">苦徹成珠 ─ 侍の美学</p>
  <p className="footer-tagline">痛みを徹し、珠を成す。</p>
  <div className="footer-links">
    <a href="https://x.com/SoothingSoothin">X</a>
    <a href="https://note.com/happy_happy_4649">note</a>
    <a href="https://youtube.com/@Japanese.Samurai.Channel">日本史</a>
    <a href="https://youtube.com/@Otona_Psychology">大人の心理学</a>
  </div>
</footer>
```

```css
.footer {
  background: #F8F4E9;
  padding: 3rem 2rem;
  text-align: center;
  border-top: 1px solid rgba(44,44,48,0.1);
}
.footer-logo { width: 60px; height: 60px; border-radius: 50%; margin-bottom: 1rem; }
.footer-brand {
  font-family: 'Yuji Boku', serif;
  font-size: 1.5rem;
  color: #2C2C30;
}
.footer-tagline {
  font-family: 'Noto Serif JP', serif;
  color: rgba(44,44,48,0.7);
  font-style: italic;
  margin: 0.5rem 0 2rem;
}
.footer-links {
  display: flex;
  gap: 2rem;
  justify-content: center;
}
.footer-links a {
  color: #A52A2A;
  text-decoration: none;
  font-size: 0.9rem;
  transition: opacity 0.25s;
}
.footer-links a:hover { opacity: 0.6; }
```

## アニメーション

| イベント | 動き | 速度 |
|---|---|---|
| ヒーロー表示 | fade-in + 山並み微 zoom (1.05→1.0) | 1.5s ease-out |
| ボタンホバー | 色反転 (背景→線のみ) | 0.3s ease |
| ナビホバー | 色 fade | 0.25s ease |
| カードホバー | 微浮き (translateY -2px) + shadow 強化 | 0.3s ease |

## 禁止事項

- ❌ 派手アニメ (parallax video / gradient animate)
- ❌ 5 色以上
- ❌ 写真素材 (banner.png / avatar.png 以外の風景写真濫用)
- ❌ 装飾文字 (草書、 隷書以外)
- ❌ 「うっちー」「UCHY」「Uchy」名乗り
- ❌ GitHub リンク
- ❌ 「47歳管理職」表現
- ❌ 「漆黒 + 金箔」(旧案 A 配色) - 新方針では使わない

## 適用範囲

| 媒体 | 適用 | 担当 |
|---|---|---|
| X バナー (1500x500) | banner.png (案 B) | 既に upload (b8c2520 + workflow) |
| X アバター (400x400) | avatar.png (案 C) | 同上 |
| toi-suite Web (Landing/全ページ) | 本仕様書 + banner.png/avatar.png | **別 repo `uchy0307/toi-suite` で実装必要** |
| LP `uchy-lp` | 本仕様書同上 | 別 repo or 別管理 |
| note 記事フッター | テキストのみ X リンク (case B 配色は不要) | 既に inject 済 |
| YouTube サムネ | 別仕様 (現状黄背景維持) | 別 task |
| dashboard (内部用) | 任意統一 | 後回し |

## toi-suite 別 repo 適用 手順 (うっちー様 or 別 Claude)

1. `uchy0307/toi-suite` repo に `public/banner.png` + `public/avatar.png` を追加 (本 repo からコピー)
2. 本仕様書を `docs/design_unified.md` としてコピー
3. `src/pages/Landing.jsx` を上記 React コードに置換
4. `src/index.css` でグローバルカラーパレット + フォント変数定義
5. Vercel に push → 自動 deploy
6. https://toi-suite.vercel.app/ で確認
