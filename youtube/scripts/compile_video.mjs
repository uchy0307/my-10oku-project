// youtube/scripts/compile_video.mjs
// 最小品質の動画コンパイル: ffmpeg + 黒背景PNG（タイトル文字付き） + 音声mp3 → mp4
//
// 入力:
//   - youtube/output/<id>_voice.mp3     （generate_voice.mjs 出力）
//   - youtube/output/<id>_script.txt    （generate_script.mjs 出力）
//   - state.json.currentTopic           （id, title, category 等）
//
// 出力:
//   - youtube/output/<id>_thumb.png     （1280x720 黒背景にタイトル文字）
//   - youtube/output/<id>_video.mp4     （音声+静止画 mp4）
//   - youtube/output/<id>_meta.json     （title/description/tags 等）
//
// 依存:
//   - ffmpeg（CI では apt install ffmpeg、ローカルは事前インストール）
//   - sharp（npm package: PNG生成）

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import sharp from 'sharp';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

async function saveState(state) {
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
}

async function fileExists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

/** タイトル文字を SVG にして PNG 化（1280x720 黒背景・白文字） */
async function renderThumb(title, outPath) {
  const W = 1280;
  const H = 720;
  // タイトル長で字サイズ調整
  const len = title.length;
  let fontSize = 72;
  if (len > 16) fontSize = 56;
  if (len > 24) fontSize = 44;
  if (len > 36) fontSize = 34;

  // 長いタイトルは折り返し（2行）
  const half = Math.ceil(len / 2);
  const breakPos = title.lastIndexOf(' ', half);
  const line1 = breakPos > 0 ? title.slice(0, breakPos) : title;
  const line2 = breakPos > 0 ? title.slice(breakPos + 1) : '';
  const escape = (s) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <rect width="100%" height="100%" fill="#0a0a0a"/>
  <text x="50%" y="${line2 ? '42%' : '52%'}" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="${fontSize}" fill="#f5f0e1" font-weight="bold">${escape(line1)}</text>
  ${line2 ? `<text x="50%" y="62%" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="${fontSize}" fill="#f5f0e1" font-weight="bold">${escape(line2)}</text>` : ''}
  <text x="50%" y="92%" text-anchor="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="28" fill="#a08864" font-style="italic">― 侍の美学 ―</text>
</svg>`;

  await sharp(Buffer.from(svg)).png().toFile(outPath);
}

/** ffmpeg を spawn して mp4 生成 */
function runFfmpeg(thumbPath, voicePath, outPath) {
  return new Promise((resolve, reject) => {
    const args = [
      '-y',
      '-loop', '1',
      '-i', thumbPath,
      '-i', voicePath,
      '-c:v', 'libx264',
      '-tune', 'stillimage',
      '-c:a', 'aac',
      '-b:a', '192k',
      '-pix_fmt', 'yuv420p',
      '-shortest',
      outPath,
    ];
    console.log(`[compile_video] ffmpeg ${args.join(' ')}`);
    const proc = spawn('ffmpeg', args, { stdio: ['ignore', 'inherit', 'inherit'] });
    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited with code ${code}`));
    });
  });
}

function generateMeta(topic, scriptText) {
  const cleanText = scriptText
    .replace(/\[VISUAL:[^\]]*\]/g, '')
    .replace(/\n+/g, ' ')
    .trim();
  const opening = cleanText.slice(0, 180);

  const tags = ['日本史', '歴史', topic.category, '侍の美学', '武士道'];
  const titleWords = (topic.title || '').split(/[ 　]/).filter((w) => w.length >= 2);
  tags.push(...titleWords);

  return {
    id: topic.id,
    title: `【侍の美学】${topic.title}`,
    description: `${opening}...\n\n#日本史 #歴史 #${topic.category || ''}\n\n― 侍の美学 ―\n10oku-project｜年商10億完全自動化プロジェクト`,
    tags: [...new Set(tags)].slice(0, 15),
    categoryId: '27', // YouTube category: Education
    defaultLanguage: 'ja',
    privacyStatus: 'public', // 完全自動化方針: 公開で投稿
    madeForKids: false,
  };
}

async function main() {
  const state = await loadState();
  const topic = state.currentTopic;
  if (!topic) {
    console.log('[compile_video] No currentTopic in state. Skip.');
    return;
  }

  const scriptPath = path.join(OUTPUT_DIR, `${topic.id}_script.txt`);
  const voicePath = path.join(OUTPUT_DIR, `${topic.id}_voice.mp3`);
  const thumbPath = path.join(OUTPUT_DIR, `${topic.id}_thumb.png`);
  const videoPath = path.join(OUTPUT_DIR, `${topic.id}_video.mp4`);
  const metaPath = path.join(OUTPUT_DIR, `${topic.id}_meta.json`);

  if (!(await fileExists(scriptPath))) {
    throw new Error(`Script file missing: ${scriptPath}`);
  }
  if (!(await fileExists(voicePath))) {
    throw new Error(`Voice file missing: ${voicePath}`);
  }

  // meta 生成
  const scriptText = await fs.readFile(scriptPath, 'utf-8');
  const meta = generateMeta(topic, scriptText);
  await fs.writeFile(metaPath, JSON.stringify(meta, null, 2), 'utf-8');
  console.log(`[compile_video] meta: ${metaPath}`);

  // サムネイル生成
  console.log(`[compile_video] thumb 生成: ${thumbPath}`);
  await renderThumb(topic.title || meta.title, thumbPath);

  // 動画生成
  console.log(`[compile_video] video 生成: ${videoPath}`);
  await runFfmpeg(thumbPath, voicePath, videoPath);
  console.log('[compile_video] DONE');

  state.lastMetaPath = metaPath;
  state.lastThumbPath = thumbPath;
  state.lastVideoPath = videoPath;
  state.lastCompileAt = new Date().toISOString();
  state.videoStatus = 'ready';
  await saveState(state);
}

main().catch((err) => {
  console.error('[compile_video] FAILED:', err);
  process.exit(1);
});
