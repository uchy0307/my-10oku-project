// youtube/scripts/compile_video.mjs
// 動画コンパイル ─ 現状はSTUB
// 本実装では ffmpeg + 画像/動画素材ライブラリで [VISUAL: ...] 指示に従って映像化する
// 現状は <id>_meta.json（タイトル・説明・タグ）のみ生成し、video pendingを記録

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

function generateMeta(topic, scriptText) {
  // 台本の冒頭2文を抽出して説明文に活用
  const cleanText = scriptText.replace(/\[VISUAL:[^\]]*\]/g, '').replace(/\n+/g, ' ').trim();
  const opening = cleanText.slice(0, 180);

  const tags = ['日本史', '歴史', topic.category, '侍の美学', '武士道'];
  // タイトルからキーワード抽出（簡易）
  const titleWords = topic.title.split(/[ 　]/).filter(w => w.length >= 2);
  tags.push(...titleWords);

  return {
    id: topic.id,
    title: `【侍の美学】${topic.title}`,
    description: `${opening}...\n\n#日本史 #歴史 #${topic.category}\n\n― 侍の美学 ―\n10oku-project｜年商10億完全自動化プロジェクト`,
    tags: [...new Set(tags)].slice(0, 15),
    categoryId: '27', // YouTube category: Education
    privacyStatus: 'public',
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
  const metaPath = path.join(OUTPUT_DIR, `${topic.id}_meta.json`);
  const videoPath = path.join(OUTPUT_DIR, `${topic.id}_video.mp4`);

  const scriptText = await fs.readFile(scriptPath, 'utf-8');
  const meta = generateMeta(topic, scriptText);
  await fs.writeFile(metaPath, JSON.stringify(meta, null, 2), 'utf-8');
  console.log(`[compile_video] Meta written: ${metaPath}`);

  // STUB: 実際の動画コンパイルは後実装
  console.log('[compile_video] STUB: video compilation requires ffmpeg + asset library; pending.');
  console.log('[compile_video] Future implementation will:');
  console.log('  1. Parse [VISUAL: ...] directives from script');
  console.log('  2. Match each directive to an asset (image/clip/effect)');
  console.log('  3. Sync with voice mp3 using ffmpeg concat + audio mux');
  console.log('  4. Render final mp4 to ' + videoPath);

  state.lastMetaPath = metaPath;
  state.lastVideoPath = null; // pending
  state.lastCompileAt = new Date().toISOString();
  state.videoStatus = 'pending_assets';
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
}

main().catch(err => {
  console.error('[compile_video] FAILED:', err);
  process.exit(1);
});
