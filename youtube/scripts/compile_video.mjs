// youtube/scripts/compile_video.mjs
// 動画コンパイル: 章ごとの画像切替 + 字幕焼き込み + 音声 → mp4 (2-pass)
// + サムネ: Wikipedia人物写真 + 黄色和紙風背景 + 赤＋黄縁太字タイトル + 動画長pill

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import sharp from 'sharp';
import { fetchWikiImage, buildCandidateQueries } from './fetch_portrait.mjs';

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
  try { await fs.access(p); return true; } catch { return false; }
}

// ─── 読み上げ用テキスト正規化 ───
function cleanScriptForSubs(text) {
  let t = text;
  t = t.replace(/\[[^\]\n]*\]/g, '');
  t = t.replace(/^#{1,6}\s.*$/gm, '');
  t = t.replace(/\*\*\*?([^*]+)\*\*\*?/g, '$1');
  t = t.replace(/\*([^*]+)\*/g, '$1');
  t = t.replace(/_([^_]+)_/g, '$1');
  t = t.replace(/[*_]+/g, '');
  t = t.replace(/#[^\s#]+/g, '');
  t = t.replace(/^\s*(ナレーション|ナレーター|BGM|SE|効果音|台本|タイトル|オープニング|エンディング|エピローグ|プロローグ|テロップ|字幕)\s*[:：]\s*/gm, '');
  t = t.replace(/https?:\/\/\S+/g, '');
  t = t.replace(/\n{3,}/g, '\n\n');
  return t.trim();
}

function splitToSentences(text, opts = {}) {
  // rebuild モード時は cue 長を半分にする (drift 影響緩和: 短い cue ほど時刻ズレが目立たない)
  const minLen = opts.tight ? 14 : 28;
  const sentences = [];
  const paragraphs = text.split(/\n+/);
  for (const para of paragraphs) {
    if (!para.trim()) continue;
    const parts = para.split(/(?<=[。！？])/).map((s) => s.trim()).filter(Boolean);
    let buf = '';
    for (const p of parts) {
      buf += p;
      if (buf.length >= minLen) { sentences.push(buf); buf = ''; }
    }
    if (buf) sentences.push(buf);
  }
  return sentences;
}

function buildSubtitleSegments(sentences, totalSec) {
  const totalChars = sentences.reduce((s, x) => s + x.length, 0) || 1;
  const cps = totalChars / totalSec;
  let cursor = 0;
  const segs = [];
  for (const sent of sentences) {
    const dur = Math.max(0.8, sent.length / cps);
    const start = cursor;
    const end = cursor + dur;
    cursor = end;
    if (dur > 5) {
      const chunks = Math.ceil(dur / 4);
      const chunkDur = dur / chunks;
      const chunkLen = Math.ceil(sent.length / chunks);
      for (let i = 0; i < chunks; i++) {
        const text = sent.slice(i * chunkLen, (i + 1) * chunkLen);
        if (!text) continue;
        segs.push({ start: start + i * chunkDur, end: start + (i + 1) * chunkDur, text });
      }
    } else {
      segs.push({ start, end, text: sent });
    }
  }
  return segs;
}

function fmtAssTime(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec - h * 3600 - m * 60;
  const intS = Math.floor(s);
  const cs = Math.floor((s - intS) * 100);
  return `${h}:${String(m).padStart(2, '0')}:${String(intS).padStart(2, '0')}.${String(cs).padStart(2, '0')}`;
}

function buildAss(segments) {
  const header = `[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK JP,46,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,2,40,40,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;
  const events = segments
    .map((s) => `Dialogue: 0,${fmtAssTime(s.start)},${fmtAssTime(s.end)},Default,,0,0,0,,${s.text.replace(/\n/g, ' ')}`)
    .join('\n');
  return header + events + '\n';
}

async function buildImageConcatList(topicId, imagePaths, totalSec) {
  if (imagePaths.length === 0) return null;
  const perImage = totalSec / imagePaths.length;
  const lines = [];
  for (const p of imagePaths) {
    lines.push(`file '${p}'`);
    lines.push(`duration ${perImage.toFixed(3)}`);
  }
  lines.push(`file '${imagePaths[imagePaths.length - 1]}'`);
  const listPath = path.join(OUTPUT_DIR, `${topicId}_imgs.txt`);
  await fs.writeFile(listPath, lines.join('\n'), 'utf-8');
  return listPath;
}

// ─── サムネ生成: 黄色和紙背景 + Wiki肖像 + 赤+黄縁タイトル ───
async function renderThumb(topic, totalSec, outPath, portraitBuffer) {
  const W = 1280;
  const H = 720;
  const LEFT_W = 576; // 45%

  const rawTitle = (topic.title || '').replace(/^[【「『][^】」』]*[】」』]\s*/g, '').trim();
  // 主要部分: 半角・全角スペース/中黒/カンマで分割した先頭
  const main = rawTitle.split(/[\s　,、・「」『』]/)[0] || rawTitle || '日本史';
  const len = main.length;
  const mid = Math.ceil(len / 2);
  const line1 = main.slice(0, mid);
  const line2 = main.slice(mid);
  const maxLine = Math.max(line1.length, line2.length || 0);

  // フォントサイズ自動調整。利用幅 1280-576-80 = 624px
  let fontSize = 300;
  if (maxLine === 2) fontSize = 300;
  else if (maxLine === 3) fontSize = 220;
  else if (maxLine === 4) fontSize = 170;
  else if (maxLine >= 5) fontSize = 130;

  const textCx = LEFT_W + (W - LEFT_W) / 2;
  const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const dm = Math.floor(totalSec / 60);
  const ds = Math.floor(totalSec % 60).toString().padStart(2, '0');
  const durTxt = `${dm}:${ds}`;

  // 背景SVG: 黄色和紙テクスチャ
  const bgSvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <pattern id="paper" patternUnits="userSpaceOnUse" width="14" height="14">
      <rect width="14" height="14" fill="#E8C547"/>
      <circle cx="3" cy="3" r="0.6" fill="rgba(160,120,40,0.35)"/>
      <circle cx="9" cy="7" r="0.4" fill="rgba(160,120,40,0.25)"/>
      <circle cx="5" cy="11" r="0.5" fill="rgba(160,120,40,0.30)"/>
    </pattern>
    <linearGradient id="rim" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#F0D060"/>
      <stop offset="1" stop-color="#D9A82B"/>
    </linearGradient>
  </defs>
  <rect width="${W}" height="${H}" fill="url(#rim)"/>
  <rect width="${W}" height="${H}" fill="url(#paper)" opacity="0.6"/>
</svg>`;

  // テキスト+pill SVG（左肖像領域は除外）
  const textSvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <text x="${textCx}" y="${line2 ? '32%' : '50%'}" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif" font-weight="900"
        font-size="${fontSize}" fill="#C8102E"
        stroke="#FFF6A8" stroke-width="8" paint-order="stroke">${escape(line1)}</text>
  ${line2 ? `<text x="${textCx}" y="68%" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif" font-weight="900"
        font-size="${fontSize}" fill="#C8102E"
        stroke="#FFF6A8" stroke-width="8" paint-order="stroke">${escape(line2)}</text>` : ''}
  <rect x="${W - 200}" y="${H - 76}" width="170" height="54" rx="27" fill="rgba(0,0,0,0.78)"/>
  <text x="${W - 115}" y="${H - 36}" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, sans-serif" font-size="34" font-weight="700" fill="#FFFFFF">${durTxt}</text>
</svg>`;

  const baseBg = await sharp(Buffer.from(bgSvg)).png().toBuffer();
  const composites = [];

  if (portraitBuffer) {
    try {
      const portrait = await sharp(portraitBuffer)
        .resize(LEFT_W, H, { fit: 'cover', position: 'centre' })
        .png()
        .toBuffer();
      composites.push({ input: portrait, top: 0, left: 0 });
    } catch (e) {
      console.warn(`[compile_video] portrait resize failed: ${e.message}`);
    }
  }

  composites.push({ input: Buffer.from(textSvg), top: 0, left: 0 });

  await sharp(baseBg).composite(composites).png().toFile(outPath);
}

function probeDuration(filePath) {
  return new Promise((resolve, reject) => {
    const proc = spawn('ffprobe', ['-v', 'error', '-show_entries', 'format=duration',
      '-of', 'default=noprint_wrappers=1:nokey=1', filePath]);
    let out = '';
    proc.stdout.on('data', (d) => { out += d.toString(); });
    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code === 0) resolve(parseFloat(out.trim()));
      else reject(new Error(`ffprobe exited ${code}`));
    });
  });
}

function runFfmpeg(args) {
  return new Promise((resolve, reject) => {
    console.log(`[compile_video] ffmpeg ${args.join(' ')}`);
    const proc = spawn('ffmpeg', args, { stdio: ['ignore', 'inherit', 'inherit'] });
    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited with code ${code}`));
    });
  });
}

// ─── /mnt + /tmp cleanup before heavy ffmpeg pass to avoid OOM/disk-full ───
async function cleanupTempBeforeFfmpeg(label) {
  console.log('[compile_video] cleanup before ' + label + ': freeing /tmp and pruning caches');
  return new Promise((resolve) => {
    const proc = spawn('bash', ['-c',
      'echo "[compile_video] disk before:"; df -h / /mnt 2>/dev/null || df -h /; ' +
      'rm -rf /tmp/ffmpeg-* /tmp/*.mp4 /tmp/*.png /tmp/*.aac /tmp/*.m4a /tmp/*.wav /tmp/*.ass /tmp/*.srt 2>/dev/null || true; ' +
      'sudo rm -rf /mnt/tmp/* 2>/dev/null || true; ' +
      'sudo find /var/cache/apt/archives -name "*.deb" -delete 2>/dev/null || true; ' +
      'sudo journalctl --vacuum-size=10M 2>/dev/null || true; ' +
      'sync; ' +
      'echo "[compile_video] mem free:"; free -h 2>/dev/null || true; ' +
      'echo "[compile_video] disk after:"; df -h / /mnt 2>/dev/null || df -h /'
    ], { stdio: 'inherit' });
    proc.on('close', () => resolve());
    proc.on('error', () => resolve());
  });
}


function generateMeta(topic, scriptText) {
  const cleanText = scriptText.replace(/\[VISUAL:[^\]]*\]/g, '').replace(/\n+/g, ' ').trim();
  const opening = cleanText.slice(0, 200);
  const tags = ['日本史', '歴史', topic.category, '侍の美学', '武士道', 'ナレーション'];
  const titleWords = (topic.title || '').split(/[ 　]/).filter((w) => w.length >= 2);
  tags.push(...titleWords);
  return {
    id: topic.id,
    title: `【侍の美学】${topic.title}`,
    description: `${opening}...\n\n#日本史 #歴史 #${topic.category || ''} #ナレーション\n\n― 侍の美学 ―`,
    tags: [...new Set(tags)].slice(0, 15),
    categoryId: '27',
    defaultLanguage: 'ja',
    privacyStatus: 'public',
    madeForKids: false,
  };
}

async function fetchTopicPortrait(topic) {
  const queries = buildCandidateQueries(topic.title);
  for (const q of queries) {
    const r = await fetchWikiImage(q);
    if (r && r.buffer) {
      console.log(`[compile_video] portrait matched "${q}" -> ${r.sourceUrl}`);
      return r.buffer;
    }
  }
  console.warn('[compile_video] no Wikipedia portrait found, thumbnail will use yellow bg + text only');
  return null;
}

async function main() {
  const argv = process.argv.slice(2);
  const REBUILD_SUBTITLE = argv.includes('--rebuild-subtitle') || process.env.REBUILD_SUBTITLE === '1';
  if (REBUILD_SUBTITLE) console.log('[compile_video] --rebuild-subtitle: 短cueモードで字幕再構築');

  const state = await loadState();
  const topic = state.currentTopic;
  if (!topic) {
    console.log('[compile_video] No currentTopic. Skip.');
    return;
  }

  const scriptPath = path.join(OUTPUT_DIR, `${topic.id}_script.txt`);
  const voicePath = path.join(OUTPUT_DIR, `${topic.id}_voice.mp3`);
  const thumbPath = path.join(OUTPUT_DIR, `${topic.id}_thumb.png`);
  const videoPath = path.join(OUTPUT_DIR, `${topic.id}_video.mp4`);
  const silentPath = path.join(OUTPUT_DIR, `${topic.id}_silent.mp4`);
  const metaPath = path.join(OUTPUT_DIR, `${topic.id}_meta.json`);
  const assPath = path.join(OUTPUT_DIR, `${topic.id}_subs.ass`);

  if (!(await fileExists(scriptPath))) throw new Error(`Script missing: ${scriptPath}`);
  if (!(await fileExists(voicePath))) throw new Error(`Voice missing: ${voicePath}`);

  const imagePaths = [];
  for (let i = 1; i <= 10; i++) {
    const p = path.join(OUTPUT_DIR, `${topic.id}_img_${i}.png`);
    if (await fileExists(p)) imagePaths.push(p);
  }
  console.log(`[compile_video] images: ${imagePaths.length}`);

  const totalSec = await probeDuration(voicePath);
  console.log(`[compile_video] voice duration: ${totalSec.toFixed(1)}s`);

  const scriptText = await fs.readFile(scriptPath, 'utf-8');
  const cleanText = cleanScriptForSubs(scriptText);
  const sentences = splitToSentences(cleanText, { tight: REBUILD_SUBTITLE });
  const segments = buildSubtitleSegments(sentences, totalSec);
  const assContent = buildAss(segments);
  await fs.writeFile(assPath, assContent, 'utf-8');
  console.log(`[compile_video] subs: ${segments.length} cues -> ${assPath}${REBUILD_SUBTITLE ? ' (tight)' : ''}`);

  // 補助: verify_subtitles からも参照しやすい .srt スナップショット
  const srtPath = path.join(OUTPUT_DIR, `${topic.id}_subtitle.srt`);
  const srtContent = segments.map((s, i) => {
    const fmt = (sec) => {
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const ss = sec - h * 3600 - m * 60;
      const intS = Math.floor(ss);
      const ms = Math.floor((ss - intS) * 1000);
      return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(intS).padStart(2,'0')},${String(ms).padStart(3,'0')}`;
    };
    return `${i+1}\n${fmt(s.start)} --> ${fmt(s.end)}\n${s.text}\n`;
  }).join('\n');
  await fs.writeFile(srtPath, srtContent, 'utf-8');

  const meta = generateMeta(topic, scriptText);
  await fs.writeFile(metaPath, JSON.stringify(meta, null, 2), 'utf-8');

  // ── サムネ: Wikipedia portrait + 黄色和紙背景 + 赤+黄縁タイトル ──
  console.log(`[compile_video] fetching topic portrait from Wikipedia/Commons...`);
  const portraitBuf = await fetchTopicPortrait(topic);
  console.log(`[compile_video] rendering thumb: ${thumbPath}`);
  await renderThumb(topic, totalSec, thumbPath, portraitBuf);

  // ── 2パス ffmpeg ──
  // Pass1: 画像concat + 字幕焼き込み → 無音動画
  if (imagePaths.length >= 1) {
    const listPath = await buildImageConcatList(topic.id, imagePaths, totalSec);
    const pass1Args = [
      '-y',
      '-f', 'concat', '-safe', '0', '-i', listPath,
      '-vf', `scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=10,subtitles=${assPath}`,
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-pix_fmt', 'yuv420p', '-threads', '2',
      '-fps_mode', 'vfr',
      '-max_muxing_queue_size', '9999',
      '-t', String(totalSec),
      silentPath,
    ];
    await cleanupTempBeforeFfmpeg('PASS1 silent');
    console.log(`[compile_video] PASS1 silent video: ${silentPath}`);
    await runFfmpeg(pass1Args);
  } else {
    // 画像なしフォールバック: 黒背景＋字幕
    const pass1Args = [
      '-y',
      '-f', 'lavfi', '-t', String(totalSec), '-i', 'color=c=#0a0a0a:s=1280x720:r=30',
      '-vf', `subtitles=${assPath}`,
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-pix_fmt', 'yuv420p', '-threads', '2',
      '-fps_mode', 'vfr',
      '-max_muxing_queue_size', '9999',
      silentPath,
    ];
    await cleanupTempBeforeFfmpeg('PASS1 fallback');
    console.log(`[compile_video] PASS1 fallback silent: ${silentPath}`);
    await runFfmpeg(pass1Args);
  }

  // Pass2: 無音動画 + 音声 mux (-c:v copy で爆速)
  const pass2Args = [
    '-y',
    '-i', silentPath,
    '-i', voicePath,
    '-c:v', 'copy',
    '-c:a', 'aac', '-b:a', '192k',
    '-shortest',
    videoPath,
  ];
  console.log(`[compile_video] PASS2 mux audio: ${videoPath}`);
  await runFfmpeg(pass2Args);

  // silent.mp4 は中間生成物として残しておく（artifactsからdebug可能）

  state.lastMetaPath = metaPath;
  state.lastThumbPath = thumbPath;
  state.lastVideoPath = videoPath;
  state.lastAssPath = assPath;
  state.lastSrtPath = srtPath;
  state.lastSubsCount = segments.length;
  state.lastCompileAt = new Date().toISOString();
  state.videoStatus = 'ready';
  await saveState(state);
  console.log('[compile_video] DONE');
}

main().catch((err) => {
  console.error('[compile_video] FAILED:', err);
  process.exit(1);
});
