// youtube/scripts/generate_images.mjs
// 章ごとの「実画像」をWikipedia/Wikimedia Commonsから取得（AI画像は使わない）
// フォールバックでも実画像のみ。最終フォールバックは黒背景（compileがハードコード字幕で生かす）。
//
// input:  state.json.currentTopic, state.lastScriptChapters
// output: youtube/output/<id>_img_1.png 〜 <id>_img_5.png (1280x720)

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { fetchWikiImage, buildCandidateQueries } from './fetch_portrait.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

const IMAGE_W = 1280;
const IMAGE_H = 720;

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

// 章ごとの検索候補クエリ
function buildChapterQueries(topic, chapter) {
  const queries = [];
  if (chapter?.title) {
    const cleaned = chapter.title.replace(/[「」『』【】]/g, '').trim();
    if (cleaned.length >= 3) queries.push(cleaned);
  }
  queries.push(...buildCandidateQueries(topic.title || ''));
  if (topic?.category) queries.push(topic.category);
  return [...new Set(queries)].filter(Boolean);
}

async function fetchChapterImage(topic, chapter) {
  const queries = buildChapterQueries(topic, chapter);
  for (const q of queries) {
    const r = await fetchWikiImage(q);
    if (r && r.buffer) {
      console.log(`[generate_images]   matched "${q}" -> ${r.sourceUrl}`);
      return r.buffer;
    }
  }
  return null;
}

async function fallbackBlackImage() {
  return sharp({
    create: { width: IMAGE_W, height: IMAGE_H, channels: 3, background: { r: 14, g: 14, b: 14 } },
  })
    .png()
    .toBuffer();
}

async function processImage(rawBuf) {
  // すべて 1280x720 cover で整形 + わずかに sepia / vignette を掛けて統一感を出す
  return sharp(rawBuf)
    .resize(IMAGE_W, IMAGE_H, { fit: 'cover', position: 'centre' })
    .modulate({ saturation: 0.85 })
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
    console.warn('[generate_images] No chapters. Fallback to 5 generic chapter slots.');
    for (let i = 1; i <= 5; i++) chapters.push({ index: i, title: `第${i}章` });
  }

  const imagePaths = [];
  for (const ch of chapters) {
    const outPath = path.join(OUTPUT_DIR, `${topic.id}_img_${ch.index}.png`);
    console.log(`[generate_images] Chapter ${ch.index} "${ch.title}" -> ${outPath}`);
    try {
      let raw = await fetchChapterImage(topic, ch);
      if (!raw) {
        console.warn(`[generate_images]   no wiki image, fallback black`);
        raw = await fallbackBlackImage();
      }
      const finalBuf = await processImage(raw);
      await fs.writeFile(outPath, finalBuf);
      imagePaths.push(outPath);
      console.log(`[generate_images] saved ${outPath} (${finalBuf.length} bytes)`);
    } catch (e) {
      console.warn(`[generate_images]   FAILED chapter ${ch.index}: ${e.message}`);
    }
  }

  state.lastImagePaths = imagePaths;
  state.lastImageGenAt = new Date().toISOString();
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
  console.log(`[generate_images] DONE: ${imagePaths.length}/${chapters.length} images`);
}

main().catch((err) => {
  console.error('[generate_images] FAILED:', err);
  process.exit(1);
});
