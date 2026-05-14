// youtube/scripts/generate_images.mjs
// 章ごとに「異なる」実画像（Wikipedia / Wikimedia Commons）を取得して保存する。
//
// 厳守事項:
//   - AI生成画像は一切使用しない（Pollinations / Imagen / DALL-E 等のコードは存在しない）
//   - 取得元は Wikipedia / Commons の実在画像のみ
//   - 5枚すべてが異なる sourceUrl になるよう dedup
//   - 取れなかったら章タイトルテキストだけの黒背景プレースホルダー（AIフォールバックは禁止）
//
// 章ごとの戦略:
//   chapter.index === 1 -> 主人公の肖像（topic主クエリ）
//   chapter.index === 2-5 -> 章タイトルから抽出した固有名詞 → 関連史跡・合戦絵・別年代肖像 等
//
// input:  state.json.currentTopic, state.lastScriptChapters
// output: youtube/output/<id>_img_1.png 〜 <id>_img_5.png (1280x720)

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { fetchWikiImageMulti, buildCandidateQueries } from './fetch_portrait.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

const IMAGE_W = 1280;
const IMAGE_H = 720;

// カテゴリ別の Commons カテゴリ ヒント（章ごとに混ぜる）
const COMMONS_CATEGORIES = {
  '合戦軸': ['Category:Battles_of_Japan', 'Category:Sengoku_period', 'Category:Samurai'],
  '人物軸': ['Category:Samurai', 'Category:Daimyo'],
  '文化軸': ['Category:Edo_period_art', 'Category:Japanese_castles'],
  '経済軸': ['Category:Edo_period', 'Category:Japanese_economic_history'],
  '地理軸': ['Category:Japanese_castles', 'Category:Historic_sites_of_Japan'],
};

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

// 章タイトルから検索クエリ候補を作る
function buildChapterQueries(topic, chapter) {
  const queries = [];
  const main = buildCandidateQueries(topic.title || '')[0] || '';
  const chTitle = (chapter?.title || '').replace(/[「」『』【】]/g, '').trim();

  // 章1は主人公中心
  if (chapter?.index === 1 && main) {
    queries.push(main);
  }

  // 章タイトル全体 / 漢字抜き出し
  if (chTitle) {
    queries.push(chTitle);
    if (main) queries.push(`${main} ${chTitle}`);
    const kanjiTerms = chTitle.match(/[一-龠]{2,}/g) || [];
    for (const kt of kanjiTerms) {
      queries.push(kt);
      queries.push(`${kt}の戦い`);
      if (main && kt.length >= 2) queries.push(`${main} ${kt}`);
    }
  }

  // 主人公派生クエリ（章ごとに別パターンを優先）
  if (main) {
    const idx = (chapter?.index || 1) - 1;
    const personalAngles = [
      `${main}`,
      `${main} 戦い`,
      `${main} 居城`,
      `${main} 家臣`,
      `${main} 墓`,
    ];
    queries.push(personalAngles[idx % personalAngles.length]);
  }

  // 戦国時代の広いフォールバック（章ごとに違うものを優先）
  const broadFallbacks = [
    '戦国時代',
    '戦国大名',
    '川中島の戦い',
    '日本の城',
    '戦国武将',
    '関ヶ原の戦い',
    '武家',
  ];
  const fbIdx = ((chapter?.index || 1) - 1) % broadFallbacks.length;
  queries.push(broadFallbacks[fbIdx]);
  queries.push(...broadFallbacks);

  return [...new Set(queries)].filter((q) => q && q.length >= 2);
}

// 章タイトル付きプレースホルダー画像（AIフォールバック不使用）
async function placeholderImage(chapterTitle, chapterIndex) {
  const W = IMAGE_W;
  const H = IMAGE_H;
  const text = (chapterTitle || `第${chapterIndex}章`).slice(0, 28);
  const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <rect width="${W}" height="${H}" fill="#1a1a1a"/>
  <text x="50%" y="50%" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="56" font-weight="700" fill="#e7c66a"
        stroke="#000" stroke-width="2" paint-order="stroke">${escape(text)}</text>
  <text x="50%" y="90%" text-anchor="middle"
        font-family="Noto Sans CJK JP, sans-serif"
        font-size="24" fill="#888">― 第${chapterIndex}章 ―</text>
</svg>`;
  return sharp(Buffer.from(svg)).png().toBuffer();
}

async function processImage(rawBuf) {
  return sharp(rawBuf)
    .resize(IMAGE_W, IMAGE_H, { fit: 'cover', position: 'centre' })
    .modulate({ saturation: 0.9 })
    .png()
    .toBuffer();
}

async function main() {
  const state = await loadState();
  const topic = state.currentTopic;
  if (!topic) {
    console.log('[generate_images] No currentTopic. Skip.');
    return;
  }
  const chapters = state.lastScriptChapters || [];
  if (chapters.length === 0) {
    console.warn('[generate_images] No chapters. Fallback to 5 generic.');
    for (let i = 1; i <= 5; i++) chapters.push({ index: i, title: `第${i}章` });
  }

  // dedup用の Set（5章すべてで共有）
  const usedUrls = new Set();
  const usedPages = new Set();
  const categoryHints = COMMONS_CATEGORIES[topic.category] || [];

  const imagePaths = [];
  for (const ch of chapters) {
    const outPath = path.join(OUTPUT_DIR, `${topic.id}_img_${ch.index}.png`);
    console.log(`[generate_images] Chapter ${ch.index} "${ch.title}" -> ${outPath}`);

    const queries = buildChapterQueries(topic, ch);
    let result = null;
    for (const q of queries) {
      result = await fetchWikiImageMulti(q, { excludeUrls: usedUrls, excludePages: usedPages });
      if (result) break;
    }
    // commons category fallback per chapter (重複除外)
    if (!result && categoryHints.length > 0) {
      const cat = categoryHints[(ch.index - 1) % categoryHints.length];
      result = await fetchWikiImageMulti('', { excludeUrls: usedUrls, excludePages: usedPages, commonsCategory: cat });
    }

    try {
      let finalBuf;
      if (result && result.buffer) {
        usedUrls.add(result.sourceUrl);
        if (result.pageTitle) usedPages.add(result.pageTitle);
        console.log(`[generate_images]   matched -> "${result.pageTitle}" -> ${result.sourceUrl}`);
        finalBuf = await processImage(result.buffer);
      } else {
        console.warn(`[generate_images]   no wiki match for ch${ch.index}, using placeholder (NO AI fallback)`);
        finalBuf = await placeholderImage(ch.title, ch.index);
      }
      await fs.writeFile(outPath, finalBuf);
      imagePaths.push(outPath);
      console.log(`[generate_images] saved ${outPath} (${finalBuf.length} bytes)`);
    } catch (e) {
      console.warn(`[generate_images]   FAILED chapter ${ch.index}: ${e.message}`);
    }
  }

  state.lastImagePaths = imagePaths;
  state.lastImageGenAt = new Date().toISOString();
  state.lastImageSources = [...usedUrls];
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
  console.log(`[generate_images] DONE: ${imagePaths.length}/${chapters.length} images. unique sources=${usedUrls.size}`);
}

main().catch((err) => {
  console.error('[generate_images] FAILED:', err);
  process.exit(1);
});
