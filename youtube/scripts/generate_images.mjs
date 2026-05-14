// youtube/scripts/generate_images.mjs
// Pollinations.ai で章ごとのシーン画像を生成（5枚 / 動画）
// 無料・APIキー不要。PNGバイナリを直接 GET。
//
// input:
//   state.json.currentTopic, state.lastScriptChapters
// output:
//   youtube/output/<id>_img_1.png 〜 <id>_img_5.png (1280x720)

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fetch from 'node-fetch';
import sharp from 'sharp';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

const IMAGE_MODEL = process.env.POLLINATIONS_MODEL || 'flux';
const IMAGE_WIDTH = 1280;
const IMAGE_HEIGHT = 720;
const REQUEST_TIMEOUT_MS = 30000;

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

function buildImagePrompt(topic, chapterTitle, chapterIndex) {
  const moods = [
    'serene and majestic, pre-dawn twilight, opening moment of history',
    'tense confrontation, deep shadows, cold light',
    'intense action, clashing swords, dust and fire',
    'a moment of decision, quiet resolve, solitary, moonlight',
    'aftermath, dusk, emptiness, wind-swept banners, silence',
  ];
  const mood = moods[(chapterIndex - 1) % moods.length];
  // Mix Japanese title context + English style keywords for Pollinations / flux.
  return `Japanese ukiyo-e style historical painting depicting "${topic.title}" — ${chapterTitle}.
Samurai warriors, Sengoku era, cinematic dramatic lighting. ${mood}.
Oil painting style, theatrical and realistic, deep contrast, 16:9 widescreen.
No text, no captions, no lettering, no watermark.`;
}

async function fetchWithTimeout(url, ms) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

async function generateImage(prompt, attempt = 1) {
  const seed = Math.floor(Math.random() * 1000000);
  const encoded = encodeURIComponent(prompt);
  const url = `https://image.pollinations.ai/prompt/${encoded}?width=${IMAGE_WIDTH}&height=${IMAGE_HEIGHT}&model=${IMAGE_MODEL}&nologo=true&seed=${seed}`;
  let res;
  try {
    res = await fetchWithTimeout(url, REQUEST_TIMEOUT_MS);
  } catch (e) {
    if (attempt < 4) {
      const wait = Math.pow(2, attempt) * 15;
      console.warn(`[generate_images] network/timeout retry in ${wait}s (attempt ${attempt + 1}): ${e.message}`);
      await new Promise((r) => setTimeout(r, wait * 1000));
      return generateImage(prompt, attempt + 1);
    }
    throw e;
  }
  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    if ((res.status === 503 || res.status === 429 || res.status === 502 || res.status === 500) && attempt < 4) {
      const wait = Math.pow(2, attempt) * 15;
      console.warn(`[generate_images] ${res.status} retry in ${wait}s (attempt ${attempt + 1})`);
      await new Promise((r) => setTimeout(r, wait * 1000));
      return generateImage(prompt, attempt + 1);
    }
    throw new Error(`Image API error ${res.status}: ${errText.slice(0, 200)}`);
  }
  const ab = await res.arrayBuffer();
  const rawBuf = Buffer.from(ab);
  if (rawBuf.length < 1024) {
    throw new Error(`Image API returned suspiciously small payload: ${rawBuf.length} bytes`);
  }
  // re-encode to exact 1280x720 PNG (idempotent: guarantees codec + size)
  const resized = await sharp(rawBuf).resize(IMAGE_WIDTH, IMAGE_HEIGHT, { fit: 'cover' }).png().toBuffer();
  return resized;
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
    console.warn('[generate_images] No chapters info in state. Fallback to 5 generic.');
    for (let i = 1; i <= 5; i++) {
      chapters.push({ index: i, title: `第${i}章` });
    }
  }

  const imagePaths = [];
  for (const ch of chapters) {
    const prompt = buildImagePrompt(topic, ch.title, ch.index);
    const outPath = path.join(OUTPUT_DIR, `${topic.id}_img_${ch.index}.png`);
    console.log(`[generate_images] Chapter ${ch.index} "${ch.title}" -> ${outPath}`);
    try {
      const buf = await generateImage(prompt);
      await fs.writeFile(outPath, buf);
      imagePaths.push(outPath);
      console.log(`[generate_images] saved ${outPath} (${buf.length} bytes)`);
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
