// youtube/scripts/generate_images.mjs
// Gemini Image API で章ごとのシーン画像を生成（5枚 / 動画）
//
// input:
//   state.json.currentTopic, state.lastScriptChapters
// output:
//   youtube/output/<id>_img_1.png 〜 <id>_img_5.png (1280x720)

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fetch from 'node-fetch';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const IMAGE_MODEL = process.env.GEMINI_IMAGE_MODEL || 'gemini-2.5-flash-image';
const IMAGE_ENDPOINT = `https://generativelanguage.googleapis.com/v1beta/models/${IMAGE_MODEL}:generateContent`;

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

function buildImagePrompt(topic, chapterTitle, chapterIndex) {
  const moods = [
    '静謐で重厚、夜明け前の薄明、歴史の始まりを告げる構図',
    '緊迫感、対峙、緊張、深い影と冷たい光',
    '激しい動き、衝突、刀の閃き、砂塵、炎の影',
    '決断の瞬間、静かな覚悟、孤高、月光',
    '余韻、夕暮れ、虚無、風に揺れる旗、静寂',
  ];
  const mood = moods[(chapterIndex - 1) % moods.length];
  return `日本史「${topic.title}」の${chapterTitle}を描いた歴史画。
${mood}。
油絵風・劇画調・写実的な人物表現・深いコントラスト・16:9横長。
文字・キャプション・テロップは描かない。`;
}

async function generateImage(prompt, attempt = 1) {
  if (!GEMINI_API_KEY) {
    throw new Error('GEMINI_API_KEY not set');
  }
  const url = `${IMAGE_ENDPOINT}?key=${GEMINI_API_KEY}`;
  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      responseModalities: ['IMAGE'],
    },
  };
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errText = await res.text();
    if ((res.status === 503 || res.status === 429) && attempt < 4) {
      const wait = Math.pow(2, attempt) * 15;
      console.warn(`[generate_images] ${res.status} retry in ${wait}s (attempt ${attempt + 1})`);
      await new Promise((r) => setTimeout(r, wait * 1000));
      return generateImage(prompt, attempt + 1);
    }
    throw new Error(`Image API error ${res.status}: ${errText}`);
  }
  const json = await res.json();
  const parts = json?.candidates?.[0]?.content?.parts || [];
  for (const p of parts) {
    const inline = p.inline_data || p.inlineData;
    if (inline?.data) {
      return Buffer.from(inline.data, 'base64');
    }
  }
  throw new Error(`Image API returned no image data: ${JSON.stringify(json).slice(0, 500)}`);
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
      console.log(`[generate_images]   ${buf.length} bytes`);
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
