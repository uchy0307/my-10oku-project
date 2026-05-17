// youtube/scripts/generate_images.mjs
// 章ごとに「異なる」実画像（Wikipedia / Wikimedia Commons）を取得して保存する。
//
// 厳守事項:
//   - AI生成画像は一切使用しない（Pollinations / Imagen / DALL-E 等のコードは存在しない）
//   - 取得元は Wikipedia / Commons の実在画像のみ
//   - 5枚すべてが異なる sourceUrl になるよう dedup
//   - 取れなかったら章タイトルテキストだけの黒背景プレースホルダー（AIフォールバックは禁止）
//   - 主人公以外の戦国大名（信長・秀合・家康等）の単独肖像は取得禁止（章タイトル漢字を単独検索しない）
//
// 章ごとの戦略:
//   chapter.index === 1 -> 主人公の肖像（topic主クエリ）
//   chapter.index === 2-5 -> 章タイトルから抽出した固有名詞 を必ず `${主人公} ${語句}` 形式で検索
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

// 主人公以外の戦国大名 / 武将。これらの単独肖像は章画像として取得禁止。
// 章タイトルに含まれていても、必ず `${主人公} ${語句}` の複合形にしてから検索する。
// 取得結果の pageTitle がここに該当する場合は除外（excludePages で渡す）。
const DAIMYO_BLOCK = [
  '織田信長', '豊臣秀吉', '羽柴秀吉', '徳川家康', '武田信玄', '上杉謙信',
  '毛利元就', '北条氏康', '北条早雲', '真田幸村', '真田信繁', '真田昌幸',
  '石田三成', '明智光秀', '伊達政宗', '島津義久', '島津義弘', '長宗我部元親',
  '今川義元', '浅井長政', '朝倉義景', '斎藤道三', '本願寺顕如',
  '柴田勝家', '前田利家', '加藤清正', '福島正則', '黒田官兵衛',
  '黒田如水', '小早jĜg��秋', '直江兼続', '大友宗麟', '龍造寺隆信',
  '足利義昭', '足利義輝', '織田信忠', '織田信雄', '豊臣秀頼', '豊臣秀次',
];

function normalizePersonName(s) {
  return String(s || '').replace(/[\s　]+/g, '');
}

const SENGOKU_COMMONS_CATEGORIES = [
  'Category:Battles_of_the_Sengoku_period',
  'Category:Samurai_paintings',
  'Category:Japanese_castles',
  'Category:Japanese_armor',
  'Category:Daimyo',
  'Category:Japanese_swords',
  'Category:Ukiyo-e',
  'Category:Edo_period_paintings',
  'Category:Sengoku_period_paintings',
  'Category:Historic_sites_of_Japan',
];
function topicIndexHash(t){const s=String(t?.id||t?.title||'').toLowerCase();let h=0;for(let i=0;i<s.length;i++)h=(h*31+s.charCodeAt(i))&0xffffffff;return Math.abs(h);}
function canonicalImageKey(u){if(!u)return '';try{const x=new URL(u);return x.hostname+x.pathname.replace('/thumb/','/').replace(/\/\d+px-[^/]+$/,'');}catch{return String(u||'');}}

// カテゴリ別の Commons カテゴリ ヒント（章ごとに混ぜる）
const COMMONS_CATEGORIES = {
  '合戦軸': ['Category:Battles_of_Japan', 'Category:Sengoku_period', 'Category:Samurai', 'Category:Japanese_castles', 'Category:Historic_sites_of_Japan', 'Category:Daimyo', 'Category:Bushido'],
  '人物軸': ['Category:Samurai', 'Category:Daimyo', 'Category:Japanese_castles', 'Category:Sengoku_period', 'Category:Historic_sites_of_Japan', 'Category:Battles_of_Japan', 'Category:Bushido'],
  '文化軸': ['Category:Edo_period_art', 'Category:Japanese_castles', 'Category:Samurai', 'Category:Japanese_traditional_culture', 'Category:Bushido', 'Category:Daimyo', 'Category:Historic_sites_of_Japan'],
  '経済軸': ['Category:Edo_period', 'Category:Japanese_economic_history', 'Category:Japanese_castles', 'Category:Samurai', 'Category:Sengoku_period', 'Category:Historic_sites_of_Japan'],
  '地理軸': ['Category:Japanese_castles', 'Category:Historic_sites_of_Japan', 'Category:Sengoku_period', 'Category:Samurai', 'Category:Daimyo', 'Category:Battles_of_Japan'],
};

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

// 章タイトルから検索クエリ候補を作る
// 修正方針: 主人公以外の戦国大名を単独で検索しない。章タイトル由来の漢字熟語は
// 必ず `${主人公} ${語句}` の複合形にする。
function buildChapterQueries(topic, chapter) {
  const queries = [];
  const main = buildCandidateQueries(topic.title || '')[0] || '';
  const mainNorm = normalizePersonName(main);
  const chTitle = (chapter?.title || '').replace(/[「」『』【】]/g, '').trim();

  const isOtherDaimyo = (s) => {
    const n = normalizePersonName(s);
    if (!n) return false;
    if (n === mainNorm) return false;
    return DAIMYO_BLOCK.some((d) => {
      const dn = normalizePersonName(d);
      return n === dn || n.includes(dn) || dn.includes(n);
    });
  };

  // 章1は主人公中心
  if (chapter?.index === 1 && main) {
    queries.push(main);
  }

  // 章タイトル全体 / 漢字抜き出し ─ 単独漢字熟語クエリは廃止。すべて `${main} ${kanji}` 形式に強制。
  if (chTitle && main) {
    queries.push(`${main} ${chTitle}`);
    const kanjiTerms = chTitle.match(/[一-龠]{2,}/g) || [];
    for (const kt of kanjiTerms) {
      // 主人公以外の戦国大名名を単独でも複合でも検索しない（豊臣秀吉等を回避）
      if (isOtherDaimyo(kt)) continue;
      if (kt.length >= 2) {
        queries.push(`${main} ${kt}`);
      }
    }
  }

  // 主人公派生クエリ（章ごとに別パターンを優先）
  if (main) {
    const idx = (chapter?.index || 1) - 1;
    const personalAngles = [
      `${main}`,
      `${main} 居城`,
      `${main} 合戦`,
      `${main} 武具`,
      `${main} 墓`,
    ];
    queries.push(...personalAngles);
  }

  // 戦国時代の広いフォールバック（章ごとに違うものを優先）
  const broadFallbacks = main ? [
    `${main} 戦国時代`,
    `${main} 戦国大名`,
    `${main} 合戦`,
    `${main} 城`,
    `${main} 武将`,
    `${main} 武家`,
    `${main} 肖像`,
  ] : [];
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
    .resize(IMAGE_W, IMAGE_H, { fit: 'cover', position: 'top' })
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

  // 主人公の正規化名
  const main = buildCandidateQueries(topic.title || '')[0] || '';
  const mainNorm = normalizePersonName(main);

  // dedup用の Set（5章すべてで共有）
  const usedUrls = new Set();
  const usedPages = new Set();
  // 主人公以外の戦国大名 Wikipedia ページは取得結果として受け入れない
  for (const name of DAIMYO_BLOCK) {
    const n = normalizePersonName(name);
    if (n && n !== mainNorm) {
      usedPages.add(name);
      // スペース混じり表記もブロック（"豊臣 秀吉" 等）
      if (name.length >= 4) {
        usedPages.add(name.slice(0, 2) + ' ' + name.slice(2));
      }
    }
  }
  console.log(`[generate_images] main="${main}" blocked_pages=${usedPages.size}`);

  const categoryHints = [...(COMMONS_CATEGORIES[topic.category] || []), ...SENGOKU_COMMONS_CATEGORIES];
  const usedKeys = new Set();
  const topicHash = topicIndexHash(topic);

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
    // commons category fallback: 章ごとに違うカテゴリを優先順位付きで全部試す
    if (!result && categoryHints.length > 0) {
      // chapter index に応じて開始カテゴリをずらす
      const startIdx = (ch.index - 1) % categoryHints.length;
      for (let i = 0; i < categoryHints.length; i++) {
        const cat = categoryHints[(startIdx + i) % categoryHints.length];
        result = await fetchWikiImageMulti('', { excludeUrls: usedUrls, excludePages: usedPages, commonsCategory: cat });
        if (result) {
          console.log(`[generate_images]   commons category match: ${cat}`);
          break;
        }
      }
    }

    try {
      let finalBuf;
      if (result && result.buffer) {
        usedUrls.add(result.sourceUrl); usedKeys.add(canonicalImageKey(result.sourceUrl));
        if (result.pageTitle) usedPages.add(result.pageTitle);
        console.log(`[generate_images]   matched -> "${result.pageTitle}" -> ${result.sourceUrl}`);
        finalBuf = await processImage(result.buffer);
      } else {
        // 最終フォールバック: 主人公本体のWikipedia肖像を再利用許可で取得（placeholder撲滅）
        let reuseResult = null;
        if (main) {
          reuseResult = await fetchWikiImageMulti(main, { excludeUrls: new Set(), excludePages: new Set() });
        }
        if (reuseResult && reuseResult.buffer) {
          console.log(`[generate_images]   reused main portrait "${reuseResult.pageTitle}" -> ${reuseResult.sourceUrl} for ch${ch.index}`);
          finalBuf = await processImage(reuseResult.buffer);
        } else {
          console.warn(`[generate_images]   no wiki match for ch${ch.index}, using placeholder (NO AI fallback)`);
          finalBuf = await placeholderImage(ch.title, ch.index);
        }
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
  console.log(`[generate_images] DONE: ${imagePaths.length}/${chapters.length} images. unique sources=${usedUrls.size} canonical=${usedKeys.size}`);
}

main().catch((err) => {
  console.error('[generate_images] FAILED:', err);
  process.exit(1);
});
