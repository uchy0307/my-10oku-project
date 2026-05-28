#!/usr/bin/env node
/**
 * youtube/history_v2/pipeline.mjs
 *
 * Standalone long-form (>=30min) pipeline for samurai history channel.
 * Does NOT import any existing youtube/scripts modules. Brand new clean pipeline.
 *
 * Flow:
 *   1. Read youtube/history_v2/scripts/long_${LONG_INDEX}.json
 *   2. Use pre-built mp3 at youtube/history_v2/audio/${LONG_INDEX}.mp3 (edge-tts)
 *   3. Fetch ALL image_urls (Wikimedia UA + retry + original-URL fallback). ABORT if < 6 succeed.
 *   4. Build ASS subtitles
 *   5. ffmpeg compose 1920x1080 mp4 with image-slideshow + burned subtitles
 *   6. GATE: csv=p=0 duration check >= 1800s, else exit 1
 *   7. Generate real-image thumbnail
 *   8. Upload to YouTube + thumbnails.set
 */
import fs from 'node:fs';
import path from 'node:path';
import { execSync, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function fail(msg, code = 1) {
  console.error(`[pipeline][FATAL] ${msg}`);
  process.exit(code);
}
function log(msg) { console.log(`[pipeline] ${msg}`); }

const LONG_INDEX = (process.env.LONG_INDEX || '').trim();
if (!/^\d{3}$/.test(LONG_INDEX)) fail(`LONG_INDEX must be 3 digits (e.g. 001). got: "${LONG_INDEX}"`);

const ROOT = path.resolve(__dirname);
const SCRIPT_PATH = path.join(ROOT, 'scripts', `long_${LONG_INDEX}.json`);
const WORK = path.join(ROOT, '.work', LONG_INDEX);
fs.mkdirSync(WORK, { recursive: true });

// ---------- DUP-GUARD (re-added 2026-05-28): exit 99 if already uploaded ----------
const UPLOADED_JSON = path.join(ROOT, 'uploaded.json');
let uploadedDb = {};
if (fs.existsSync(UPLOADED_JSON)) {
  try { uploadedDb = JSON.parse(fs.readFileSync(UPLOADED_JSON, 'utf8')) || {}; } catch {}
}
if (uploadedDb[LONG_INDEX]) {
  console.log(`[pipeline][SKIP] index ${LONG_INDEX} already uploaded: ${uploadedDb[LONG_INDEX].videoUrl || uploadedDb[LONG_INDEX]}`);
  process.exit(99);
}

log(`reading ${SCRIPT_PATH}`);
if (!fs.existsSync(SCRIPT_PATH)) fail(`script file not found: ${SCRIPT_PATH}`);
const spec = JSON.parse(fs.readFileSync(SCRIPT_PATH, 'utf8'));
const { title, description = '', tags = [], chapters = [], image_urls = [] } = spec;
if (!title) fail('script JSON missing title');
if (!Array.isArray(chapters) || chapters.length < 3) fail('chapters array must have at least 3 items');
if (!Array.isArray(image_urls) || image_urls.length < 6) fail('image_urls must have at least 6 entries');

// ---------- 1. Audio (edge-tts pre-built mp3 required) ----------
const audioSrc = path.join(__dirname, 'audio', `${LONG_INDEX}.mp3`);
if (!fs.existsSync(audioSrc) || fs.statSync(audioSrc).size < 5000) {
  fail(`audio file missing or empty: youtube/history_v2/audio/${LONG_INDEX}.mp3 (edge-tts でローカル生成して push してください)`);
}
const narrationMp3 = path.join(WORK, 'narration.mp3');
fs.copyFileSync(audioSrc, narrationMp3);
log(`using pre-built narration: ${audioSrc}`);

// ---------- 2. Silence helper (used for end-padding) ----------
function makeSilence(sec, out) {
  execSync(
    `ffmpeg -y -f lavfi -i anullsrc=channel_layout=mono:sample_rate=24000 -t ${sec} -c:a libmp3lame -b:a 128k ${JSON.stringify(out)}`,
    { stdio: 'inherit' }
  );
}

function probeDuration(p) {
  const out = execSync(
    `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 ${JSON.stringify(p)}`
  ).toString().trim();
  const d = parseFloat(out);
  if (!Number.isFinite(d) || d <= 0) fail(`bad duration probe: ${out} for ${p}`);
  return d;
}

let audioDur = probeDuration(narrationMp3);
log(`narration duration: ${audioDur.toFixed(1)}s (${(audioDur/60).toFixed(2)}min)`);

const TARGET_MIN_SEC = 1830;
if (audioDur < TARGET_MIN_SEC) {
  const padSec = Math.ceil(TARGET_MIN_SEC - audioDur + 5);
  log(`audio under target, padding ${padSec}s silence at end`);
  const padFile = path.join(WORK, `silence_pad.mp3`);
  makeSilence(padSec, padFile);
  const padListPath = path.join(WORK, 'concat_pad.txt');
  fs.writeFileSync(padListPath, `file '${narrationMp3}'\nfile '${padFile}'\n`, 'utf8');
  const narrationPadded = path.join(WORK, 'narration_padded.mp3');
  execSync(
    `ffmpeg -y -f concat -safe 0 -i ${JSON.stringify(padListPath)} -c:a libmp3lame -b:a 128k ${JSON.stringify(narrationPadded)}`,
    { stdio: 'inherit' }
  );
  fs.copyFileSync(narrationPadded, narrationMp3);
  audioDur = probeDuration(narrationMp3);
  log(`padded narration duration: ${audioDur.toFixed(1)}s`);
}

// ---------- 3. Fetch images: Wikimedia-compliant UA + retry + original-URL fallback ----------
const WIKI_UA = '10oku-history-bot/1.0 (https://github.com/uchy0307/my-10oku-project; uchiyamatakayuki0307@gmail.com) node-fetch';
async function fetchOnce(url) {
  const res = await fetch(url, {
    headers: {
      'User-Agent': WIKI_UA,
      'Accept': 'image/avif,image/webp,image/jpeg,image/*,*/*;q=0.8',
      'Accept-Language': 'ja,en;q=0.8',
    },
    redirect: 'follow',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.length < 3000) throw new Error(`image too small (${buf.length}B)`);
  return buf;
}
function deriveOriginalUrl(thumbUrl) {
  const m = thumbUrl.match(/^(https?:\/\/upload\.wikimedia\.org\/wikipedia\/[^/]+)\/thumb\/([^/]+\/[^/]+\/[^/]+)\/\d+px-/);
  if (m) return `${m[1]}/${m[2]}`;
  return null;
}
async function fetchImage(url, dst) {
  log(`fetch ${url}`);
  const tries = [url];
  const orig = deriveOriginalUrl(url);
  if (orig) tries.push(orig);
  let lastErr;
  for (const u of tries) {
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const buf = await fetchOnce(u);
        fs.writeFileSync(dst, buf);
        if (u !== url) log(`(fallback to original) ${u}`);
        return;
      } catch (e) {
        lastErr = e;
        await new Promise(r => setTimeout(r, 400 + attempt * 600));
      }
    }
  }
  throw lastErr;
}

const imagePaths = [];
for (let i = 0; i < image_urls.length; i++) {
  const dst = path.join(WORK, `image_${i}.jpg`);
  try {
    await fetchImage(image_urls[i], dst);
    imagePaths.push(dst);
    await new Promise(r => setTimeout(r, 350));
  } catch (e) {
    console.warn(`[pipeline] image ${i} failed: ${e.message}`);
  }
}
log(`images succeeded: ${imagePaths.length}/${image_urls.length}`);

// ---------- 3b. Stock fallback (2026-05-28 added): Wikimedia 失効URL 救済 ----------
// 不足してたら stock_images/wiki/ から自動補充して pipeline 続行
if (imagePaths.length < 8) {
  const stockFallbackDir = path.join(__dirname, '..', 'stock_images', 'wiki');
  if (fs.existsSync(stockFallbackDir)) {
    const allStock = fs.readdirSync(stockFallbackDir).filter(f => /\.(jpe?g|png|webp)$/i.test(f));
    const shuffled = allStock.sort(() => Math.random() - 0.5);
    let added = 0;
    for (const f of shuffled) {
      if (imagePaths.length >= 12) break;
      const srcPath = path.join(stockFallbackDir, f);
      const dst = path.join(WORK, `image_${imagePaths.length}.jpg`);
      try {
        fs.copyFileSync(srcPath, dst);
        imagePaths.push(dst);
        added++;
      } catch {}
    }
    log(`stock fallback added: ${added} images (total: ${imagePaths.length})`);
  } else {
    log(`stock fallback dir not found: ${stockFallbackDir}`);
  }
}

if (imagePaths.length < 6) fail(`only ${imagePaths.length} images succeeded; need >= 6 (Wikimedia all-404 even after stock fallback)`);

// ---------- 4. Build ASS subtitles ----------
function splitForSubs(text, maxChars = 28) {
  const sentences = text.split(/(?<=[ãï¼ï¼ã])/).filter(s => s.trim().length > 0);
  const chunks = [];
  let buf = '';
  for (const s of sentences) {
    if ((buf + s).length > maxChars && buf) {
      chunks.push(buf.trim());
      buf = s;
    } else {
      buf += s;
    }
  }
  if (buf.trim()) chunks.push(buf.trim());
  return chunks;
}
const allText = chapters.map(c => c.text).join('');
const subChunks = splitForSubs(allText, 28);
const subSlot = (audioDur - 16) / subChunks.length;
const subStart = 8;

function fmtAssTime(sec) {
  const total = Math.max(0, sec);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = (total % 60).toFixed(2).padStart(5, '0');
  return `${h}:${String(m).padStart(2, '0')}:${s}`;
}

let assText = `[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK JP,60,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,1,4,2,2,140,140,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;
for (let i = 0; i < subChunks.length; i++) {
  const st = subStart + i * subSlot;
  const ed = Math.min(subStart + (i + 1) * subSlot - 0.05, audioDur - 4);
  const safe = subChunks[i].replace(/[\\{}]/g, '').replace(/\n/g, ' ');
  assText += `Dialogue: 0,${fmtAssTime(st)},${fmtAssTime(ed)},Default,,0,0,0,,${safe}\n`;
}
const assPath = path.join(WORK, 'sub.ass');
fs.writeFileSync(assPath, assText, 'utf8');

// ---------- 5. Build video ----------
const segSec = Math.max(45, Math.floor(audioDur / imagePaths.length));
log(`video: ${imagePaths.length} images x ${segSec}s each, target dur ${audioDur.toFixed(0)}s`);

const segMp4s = [];
for (let i = 0; i < imagePaths.length; i++) {
  const out = path.join(WORK, `seg_${i}.mp4`);
  const frames = segSec * 24;
  const zoomExpr = i % 2 === 0
    ? `'min(1+0.00012*on,1.15)'`
    : `'max(1.15-0.00012*on,1.0)'`;
  const filter = [
    `scale=3200:1800:force_original_aspect_ratio=increase`,
    `crop=2880:1620`,
    `zoompan=z=${zoomExpr}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=1920x1080:fps=24`,
    `setsar=1`,
  ].join(',');
  execSync(
    `ffmpeg -y -loop 1 -i ${JSON.stringify(imagePaths[i])} -t ${segSec} -vf "${filter}" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -r 24 -an ${JSON.stringify(out)}`,
    { stdio: 'inherit' }
  );
  segMp4s.push(out);
}

let totalSec = 0;
const concatVidList = [];
let idx = 0;
while (totalSec < audioDur + 5) {
  concatVidList.push(segMp4s[idx % segMp4s.length]);
  totalSec += segSec;
  idx++;
  if (idx > 200) break;
}
log(`concatenating ${concatVidList.length} segments (~${totalSec}s)`);
const videoConcatListPath = path.join(WORK, 'concat_video.txt');
fs.writeFileSync(
  videoConcatListPath,
  concatVidList.map(p => `file '${p.replace(/'/g, "'\\''")}'`).join('\n'),
  'utf8'
);
const bgMp4 = path.join(WORK, 'bg.mp4');
execSync(
  `ffmpeg -y -f concat -safe 0 -i ${JSON.stringify(videoConcatListPath)} -c copy ${JSON.stringify(bgMp4)}`,
  { stdio: 'inherit' }
);

const outMp4 = path.join(WORK, 'output.mp4');
execSync(
  `ffmpeg -y -i ${JSON.stringify(bgMp4)} -i ${JSON.stringify(narrationMp3)} -vf "subtitles=sub.ass:fontsdir=/usr/share/fonts" -map 0:v:0 -map 1:a:0 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 192k -t ${audioDur.toFixed(2)} ${JSON.stringify(outMp4)}`,
  { stdio: 'inherit', cwd: WORK }
);

// ---------- 6. GATE: STRICT duration enforcement ----------
const gateProbe = execSync(
  `ffprobe -v error -show_entries format=duration -of csv=p=0 ${JSON.stringify(outMp4)}`
).toString().trim();
const finalDur = parseFloat(gateProbe);
if (!Number.isFinite(finalDur) || finalDur <= 0) fail(`[GATE] bad duration probe: ${gateProbe}`);
const finalDurInt = Math.round(finalDur);
console.log(`[GATE] duration=${finalDurInt}s (required >= 1800)`);
if (finalDurInt < 1800) {
  console.error(`[GATE] FAIL: duration=${finalDurInt}s < 1800s. ABORTING - no YouTube upload will be performed.`);
  process.exit(1);
}
console.log(`[GATE] PASS: duration=${finalDurInt}s >= 1800s. Proceeding to upload.`);
log(`final mp4 duration: ${finalDur.toFixed(1)}s (${(finalDur/60).toFixed(2)}min)`);
const outSize = fs.statSync(outMp4).size;
log(`output ${outMp4} (${(outSize / 1024 / 1024).toFixed(1)} MB)`);
if (outSize < 10 * 1024 * 1024) fail(`output mp4 suspiciously small: ${outSize}B`);

// ---------- 7. Generate thumbnail (1280x720 yellow bg + big red wrapped title) ----------
// Spec (2026-05-21): yellow background, bold RED title text, auto-wrapped within
// 92% of frame width. Optional hero portrait fades in on the right edge.
// Rendered via Pillow (scripts/make_thumb.py) for proper Japanese wrap & sizing.
const thumbPath = path.join(WORK, 'thumbnail.jpg');
const heroImg = imagePaths[0]; // portrait/main figure
const makeThumbPy = path.join(ROOT, 'scripts', 'make_thumb.py');
if (!fs.existsSync(makeThumbPy)) fail(`make_thumb.py missing at ${makeThumbPy}`);
const thumbRun = spawnSync(
  'python3',
  [
    makeThumbPy,
    '--title', title,
    '--out', thumbPath,
    '--hero', heroImg,
  ],
  { stdio: 'inherit' }
);
if (thumbRun.status !== 0) fail(`make_thumb.py exited ${thumbRun.status}`);
const thumbSize = fs.statSync(thumbPath).size;
log(`thumbnail generated: ${thumbPath} (${thumbSize}B)`);
if (thumbSize < 10000) fail('thumbnail too small / generation failed');

// ---------- 8. Upload to YouTube ----------
const { YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN } = process.env;
if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) {
  fail('YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN required', 2);
}
const oauth2 = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET);
oauth2.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
const youtube = google.youtube({ version: 'v3', auth: oauth2 });

const finalTitle = title.slice(0, 95);
const finalDescription = description.slice(0, 4500);
const finalTags = (Array.isArray(tags) && tags.length ? tags : ['æ¥æ¬å²', 'æ¦å½æä»£', 'æ­´å²è§£èª¬']).slice(0, 15);

log('uploading to YouTube (resumable)...');
const upload = await youtube.videos.insert({
  part: ['snippet', 'status'],
  requestBody: {
    snippet: {
      title: finalTitle,
      description: finalDescription,
      tags: finalTags,
      categoryId: '22',
      defaultLanguage: 'ja',
      defaultAudioLanguage: 'ja',
    },
    status: {
      privacyStatus: 'public',
      selfDeclaredMadeForKids: false,
      madeForKids: false,
    },
  },
  media: { body: fs.createReadStream(outMp4) },
}, { maxBodyLength: 2 * 1024 * 1024 * 1024 });

const videoId = upload.data?.id;
if (!videoId) fail(`upload failed: no videoId in response: ${JSON.stringify(upload.data)}`, 3);
const videoUrl = `https://youtube.com/watch?v=${videoId}`;
log(`uploaded! ${videoUrl}`);

// ---------- 9. Set thumbnail ----------
try {
  log(`setting thumbnail for videoId=${videoId}`);
  await youtube.thumbnails.set({
    videoId,
    media: { mimeType: 'image/jpeg', body: fs.createReadStream(thumbPath) },
  });
  log('thumbnail set');
} catch (e) {
  console.warn(`[pipeline] thumbnail set failed (non-fatal): ${e?.message || e}`);
}

// ---------- 10. Emit output ----------
if (process.env.GITHUB_OUTPUT) {
  fs.appendFileSync(process.env.GITHUB_OUTPUT, `video_url=${videoUrl}\nvideo_id=${videoId}\nduration_sec=${finalDurInt}\n`);
}
console.log(`\n::notice title=history_v2 upload OK::index=${LONG_INDEX} dur=${finalDurInt}s url=${videoUrl}\n`);
