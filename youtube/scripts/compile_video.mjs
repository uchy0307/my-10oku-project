// youtube/scripts/compile_video.mjs
// 動画コンパイル: 章ごとの画像切替 + 字幕焼き込み + 音声 → mp4
//
// 入力:
//   - youtube/output/<id>_voice.mp3
//   - youtube/output/<id>_script.txt
//   - youtube/output/<id>_img_1.png 〜 <id>_img_N.png (generate_images.mjs)
//   - state.json
//
// 出力:
//   - youtube/output/<id>_thumb.png (1280x720)
//   - youtube/output/<id>_video.mp4
//   - youtube/output/<id>_meta.json
//   - youtube/output/<id>_subs.ass (字幕焼き込み元)

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
  try { await fs.access(p); return true; } catch { return false; }
}

// ─────────────────────────────────────────────
// 読み上げ用テキスト正規化（generate_voice.mjs と同じロジック）
// ─────────────────────────────────────────────
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

// ─────────────────────────────────────────────
// 字幕：句点・改行で文単位に分割
// ─────────────────────────────────────────────
function splitToSentences(text) {
  // 行内では「。」「！」「？」で分割。短すぎる断片は次へ結合。
  const sentences = [];
  const paragraphs = text.split(/\n+/);
  for (const para of paragraphs) {
    if (!para.trim()) continue;
    // 句読点で分割しつつデリミタ保持
    const parts = para.split(/(?<=[。！？])/).map((s) => s.trim()).filter(Boolean);
    let buf = '';
    for (const p of parts) {
      buf += p;
      // 30字以上溜まったら確定
      if (buf.length >= 28) {
        sentences.push(buf);
        buf = '';
      }
    }
    if (buf) sentences.push(buf);
  }
  return sentences;
}

// 文字数比でタイミングを割り振り、長すぎる文はさらに分割表示
function buildSubtitleSegments(sentences, totalSec) {
  const totalChars = sentences.reduce((s, x) => s + x.length, 0) || 1;
  const cps = totalChars / totalSec; // chars per sec
  let cursor = 0;
  const segs = [];
  for (const sent of sentences) {
    const dur = Math.max(0.8, sent.length / cps);
    const start = cursor;
    const end = cursor + dur;
    cursor = end;
    // 1セグメントが長すぎる(>5s)場合は分割
    if (dur > 5) {
      const chunks = Math.ceil(dur / 4);
      const chunkDur = dur / chunks;
      const chunkLen = Math.ceil(sent.length / chunks);
      for (let i = 0; i < chunks; i++) {
        const text = sent.slice(i * chunkLen, (i + 1) * chunkLen);
        if (!text) continue;
        segs.push({
          start: start + i * chunkDur,
          end: start + (i + 1) * chunkDur,
          text,
        });
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
  // ASS字幕フォーマット。下部中央・大きめ白文字＋黒縁取り
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

// ─────────────────────────────────────────────
// 画像コンキャットリスト（章ごとに均等割り）
// ─────────────────────────────────────────────
async function buildImageConcatList(topicId, imagePaths, totalSec) {
  if (imagePaths.length === 0) return null;
  const perImage = totalSec / imagePaths.length;
  const lines = [];
  for (const p of imagePaths) {
    lines.push(`file '${p}'`);
    lines.push(`duration ${perImage.toFixed(3)}`);
  }
  // ffmpeg concat requirement: last file repeated without duration
  lines.push(`file '${imagePaths[imagePaths.length - 1]}'`);
  const listPath = path.join(OUTPUT_DIR, `${topicId}_imgs.txt`);
  await fs.writeFile(listPath, lines.join('\n'), 'utf-8');
  return listPath;
}

// ─────────────────────────────────────────────
// サムネ生成：第1章画像があれば使い、無ければ黒背景。タイトル文字オーバーレイ
// ─────────────────────────────────────────────
async function renderThumb(title, outPath, bgImagePath) {
  const W = 1280;
  const H = 720;
  const len = title.length;
  let fontSize = 88;
  if (len > 14) fontSize = 72;
  if (len > 22) fontSize = 58;
  if (len > 34) fontSize = 44;

  const half = Math.ceil(len / 2);
  const breakPos = title.lastIndexOf(' ', half);
  const line1 = breakPos > 0 ? title.slice(0, breakPos) : title;
  const line2 = breakPos > 0 ? title.slice(breakPos + 1) : '';
  const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // 下半分にグラデの暗幕を敷いて文字を読みやすく
  const overlaySvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#000" stop-opacity="0.0"/>
      <stop offset="0.4" stop-color="#000" stop-opacity="0.45"/>
      <stop offset="1" stop-color="#000" stop-opacity="0.85"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="${W}" height="${H}" fill="url(#g)"/>
  <text x="50%" y="${line2 ? '60%' : '70%'}" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="${fontSize}" fill="#fff7e0" font-weight="900"
        stroke="#000" stroke-width="3" paint-order="stroke">${escape(line1)}</text>
  ${line2 ? `<text x="50%" y="78%" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="${fontSize}" fill="#fff7e0" font-weight="900"
        stroke="#000" stroke-width="3" paint-order="stroke">${escape(line2)}</text>` : ''}
  <text x="50%" y="93%" text-anchor="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="30" fill="#e7c66a" font-style="italic"
        stroke="#000" stroke-width="2" paint-order="stroke">― 侍の美学 ―</text>
</svg>`;

  if (bgImagePath && (await fileExists(bgImagePath))) {
    // 背景画像にオーバーレイ合成
    await sharp(bgImagePath)
      .resize(W, H, { fit: 'cover', position: 'centre' })
      .composite([{ input: Buffer.from(overlaySvg), top: 0, left: 0 }])
      .png()
      .toFile(outPath);
  } else {
    // 画像なしフォールバック: 黒背景
    const bg = await sharp({
      create: { width: W, height: H, channels: 3, background: { r: 10, g: 10, b: 10 } },
    }).png().toBuffer();
    await sharp(bg)
      .composite([{ input: Buffer.from(overlaySvg), top: 0, left: 0 }])
      .png()
      .toFile(outPath);
  }
}

// ─────────────────────────────────────────────
// ffprobe で音声長を取得
// ─────────────────────────────────────────────
function probeDuration(filePath) {
  return new Promise((resolve, reject) => {
    const proc = spawn('ffprobe', [
      '-v', 'error', '-show_entries', 'format=duration',
      '-of', 'default=noprint_wrappers=1:nokey=1', filePath,
    ]);
    let out = '';
    proc.stdout.on('data', (d) => { out += d.toString(); });
    proc.on('error', reject);
    proc.on('close', (code) => {
      if (code === 0) resolve(parseFloat(out.trim()));
      else reject(new Error(`ffprobe exited ${code}`));
    });
  });
}

// ─────────────────────────────────────────────
// ffmpeg で動画生成（画像切替 + 字幕焼き込み + 音声）
// ─────────────────────────────────────────────
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

// ─────────────────────────────────────────────
// メタ生成
// ─────────────────────────────────────────────
function generateMeta(topic, scriptText) {
  const cleanText = scriptText
    .replace(/\[VISUAL:[^\]]*\]/g, '')
    .replace(/\n+/g, ' ')
    .trim();
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

// ─────────────────────────────────────────────
// メイン
// ─────────────────────────────────────────────
async function main() {
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
  const metaPath = path.join(OUTPUT_DIR, `${topic.id}_meta.json`);
  const assPath = path.join(OUTPUT_DIR, `${topic.id}_subs.ass`);

  if (!(await fileExists(scriptPath))) throw new Error(`Script missing: ${scriptPath}`);
  if (!(await fileExists(voicePath))) throw new Error(`Voice missing: ${voicePath}`);

  // 画像探索（generate_images.mjs が生成）
  const imagePaths = [];
  for (let i = 1; i <= 10; i++) {
    const p = path.join(OUTPUT_DIR, `${topic.id}_img_${i}.png`);
    if (await fileExists(p)) imagePaths.push(p);
  }
  console.log(`[compile_video] images: ${imagePaths.length}`);

  // 音声長
  const totalSec = await probeDuration(voicePath);
  console.log(`[compile_video] voice duration: ${totalSec.toFixed(1)}s`);

  // 字幕生成
  const scriptText = await fs.readFile(scriptPath, 'utf-8');
  const cleanText = cleanScriptForSubs(scriptText);
  const sentences = splitToSentences(cleanText);
  const segments = buildSubtitleSegments(sentences, totalSec);
  const assContent = buildAss(segments);
  await fs.writeFile(assPath, assContent, 'utf-8');
  console.log(`[compile_video] subs: ${segments.length} cues -> ${assPath}`);

  // メタ
  const meta = generateMeta(topic, scriptText);
  await fs.writeFile(metaPath, JSON.stringify(meta, null, 2), 'utf-8');

  // サムネ (第1画像があれば背景に)
  console.log(`[compile_video] thumb`);
  await renderThumb(topic.title || meta.title, thumbPath, imagePaths[0] || null);

  // ffmpeg コマンド構築
  let ffmpegArgs;
  if (imagePaths.length >= 1) {
    // 画像コンキャット + 音声 + 字幕
    const listPath = await buildImageConcatList(topic.id, imagePaths, totalSec);
    ffmpegArgs = [
      '-y',
      '-f', 'concat', '-safe', '0', '-i', listPath,
      '-i', voicePath,
      '-vf', `scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30,subtitles=${assPath}`,
      '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
      '-c:a', 'aac', '-b:a', '192k',
      '-shortest',
      videoPath,
    ];
  } else {
    // フォールバック: 黒背景単色 + 字幕 + 音声
    ffmpegArgs = [
      '-y',
      '-f', 'lavfi', '-t', String(totalSec), '-i', 'color=c=#0a0a0a:s=1280x720:r=30',
      '-i', voicePath,
      '-vf', `subtitles=${assPath}`,
      '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
      '-c:a', 'aac', '-b:a', '192k',
      '-shortest',
      videoPath,
    ];
  }

  console.log(`[compile_video] video 生成: ${videoPath}`);
  await runFfmpeg(ffmpegArgs);

  state.lastMetaPath = metaPath;
  state.lastThumbPath = thumbPath;
  state.lastVideoPath = videoPath;
  state.lastAssPath = assPath;
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
