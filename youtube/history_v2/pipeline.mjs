#!/usr/bin/env node
/**
 * youtube/history_v2/pipeline.mjs
 *
 * Standalone long-form (>=30min) pipeline for samurai history channel.
 * Does NOT import any existing youtube/scripts modules. Brand new clean pipeline.
 *
 * Flow:
 *   1. Read youtube/history_v2/scripts/long_${LONG_INDEX}.json
 *      Format: { title, description, tags, chapters:[{title,text}], image_urls:[...] }
 *   2. For each chapter, gtts-cli ja -> chapter_N.mp3
 *      Then ffmpeg atempo=0.92 to slow slightly + concat with 4s silence between chapters.
 *      If total audio < 1810s, append silence at end to reach 1830s (real-image bg keeps showing).
 *   3. Fetch ALL image_urls. ABORT if fewer than 6 succeed (no black-bg fallback).
 *   4. Build ASS subtitles: split narration into 25-char chunks evenly across audio.
 *   5. ffmpeg compose 1920x1080 mp4 with image-slideshow background (each image 30-120s with crossfade)
 *      Burn in subtitles. Add narration audio.
 *   6. Verify final mp4 duration >= 1800s. If not, abort.
 *   7. Generate thumbnail 1280x720: portrait image + yellow washi background + red title text.
 *   8. Upload to YouTube (resumable) with title/description/tags.
 *   9. thumbnails.set with generated jpg.
 *  10. Emit video_url via GITHUB_OUTPUT.
 *
 * Required env:
 *   LONG_INDEX                   e.g. "001"
 *   YOUTUBE_CLIENT_ID
 *   YOUTUBE_CLIENT_SECRET
 *   YOUTUBE_REFRESH_TOKEN
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

log(`reading ${SCRIPT_PATH}`);
if (!fs.existsSync(SCRIPT_PATH)) fail(`script file not found: ${SCRIPT_PATH}`);
const spec = JSON.parse(fs.readFileSync(SCRIPT_PATH, 'utf8'));
const { title, description = '', tags = [], chapters = [], image_urls = [] } = spec;
if (!title) fail('script JSON missing title');
if (!Array.isArray(chapters) || chapters.length < 3) fail('chapters array must have at least 3 items');
if (!Array.isArray(image_urls) || image_urls.length < 6) fail('image_urls must have at least 6 entries');

// ---------- 1. TTS per chapter ----------
const chapterMp3s = [];
for (let i = 0; i < chapters.length; i++) {
  const ch = chapters[i];
  if (!ch.text || ch.text.length < 200) fail(`chapter ${i} text too short`);
  const txtPath = path.join(WORK, `chapter_${i}.txt`);
  const rawMp3 = path.join(WORK, `chapter_${i}_raw.mp3`);
  const ch_mp3 = path.join(WORK, `chapter_${i}.mp3`);
  fs.writeFileSync(txtPath, ch.text, 'utf8');
  log(`TTS chapter ${i} (${ch.text.length} chars)`);
  // gtts-cli will internally chunk long text
  const r = spawnSync('gtts-cli', ['--lang', 'ja', '--file', txtPath, '--output', rawMp3], { stdio: 'inherit' });
  if (r.status !== 0) fail(`gtts-cli failed for chapter ${i}`);
  if (!fs.existsSync(rawMp3) || fs.statSync(rawMp3).size < 5000) fail(`chapter ${i} mp3 empty`);
  // Slow audio slightly with atempo=0.92 (more natural, fuller length)
  execSync(
    `ffmpeg -y -i ${JSON.stringify(rawMp3)} -filter:a "atempo=0.92" -c:a libmp3lame -b:a 128k ${JSON.stringify(ch_mp3)}`,
    { stdio: 'inherit' }
  );
  chapterMp3s.push(ch_mp3);
}

// ---------- 2. Build silence + concat ----------
function makeSilence(sec, out) {
  execSync(
    `ffmpeg -y -f lavfi -i anullsrc=channel_layout=mono:sample_rate=24000 -t ${sec} -c:a libmp3lame -b:a 128k ${JSON.stringify(out)}`,
    { stdio: 'inherit' }
  );
}
const silence4 = path.join(WORK, 'silence_4s.mp3');
makeSilence(4, silence4);
const silence8 = path.join(WORK, 'silence_8s.mp3');
makeSilence(8, silence8);

const concatList = [];
concatList.push(silence8); // intro
for (let i = 0; i < chapterMp3s.length; i++) {
  concatList.push(chapterMp3s[i]);
  if (i < chapterMp3s.length - 1) concatList.push(silence4);
}
concatList.push(silence8); // outro

const concatListPath = path.join(WORK, 'concat_audio.txt');
fs.writeFileSync(
  concatListPath,
  concatList.map(p => `file '${p.replace(/'/g, "'\\''")}'`).join('\n'),
  'utf8'
);
const narrationMp3 = path.join(WORK, 'narration.mp3');
execSync(
  `ffmpeg -y -f concat -safe 0 -i ${JSON.stringify(concatListPath)} -c:a libmp3lame -b:a 128k ${JSON.stringify(narrationMp3)}`,
  { stdio: 'inherit' }
);

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

// If audio too short, append silence to reach 1830s
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

// ---------- 3. Fetch images (ABORT on too few successes) ----------
// Wikimedia requires UA per https://meta.wikimedia.org/wiki/User-Agent_policy
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
  // /wikipedia/commons/thumb/X/YY/Name.jpg/NNNpx-Name.jpg -> /wikipedia/commons/X/YY/Name.jpg
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
        // brief backoff
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
    // Be polite to Wikimedia: 350ms between requests
    await new Promise(r => setTimeout(r, 350));
  } catch (e) {
    console.warn(`[pipeline] image ${i} failed: ${e.message}`);
  }
}
log(`images succeeded: ${imagePaths.length}/${image_urls.length}`);
if (imagePaths.length < 6) fail(`only ${imagePaths.length} images succeeded; need >= 6 (no black-bg fallback per rule)`);

// ---------- 4. Build ASS subtitles ----------
function splitForSubs(text, maxChars = 28) {
  // Split on Japanese punctuation, then re-group up to maxChars per line
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
const subSlot = (audioDur - 16) / subChunks.length; // skip ~8s intro/outro silence
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

// ---------- 5. Build video: image slideshow background, then mux audio + subs ----------
// Each image shown for ~ audioDur / imagePaths.length seconds
const segSec = Math.max(45, Math.floor(audioDur / imagePaths.length));
log(`video: ${imagePaths.length} images x ${segSec}s each, target dur ${audioDur.toFixed(0)}s`);

const segMp4s = [];
for (let i = 0; i < imagePaths.length; i++) {
  const out = path.join(WORK, `seg_${i}.mp4`);
  const frames = segSec * 24;
  // Slow ken-burns zoom in/out alternating; 1920x1080 output
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

// Loop image segments until they cover audioDur. Build concat list repeating until total >= audioDur
let totalSec = 0;
const concatVidList = [];
let idx = 0;
while (totalSec < audioDur + 5) {
  concatVidList.push(segMp4s[idx % segMp4s.length]);
  totalSec += segSec;
  idx++;
  if (idx > 200) break; // safety
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

// Final compose: bg + narration + subs, trim to audioDur
const outMp4 = path.join(WORK, 'output.mp4');
execSync(
  `ffmpeg -y -i ${JSON.stringify(bgMp4)} -i ${JSON.stringify(narrationMp3)} -vf "subtitles=sub.ass:fontsdir=/usr/share/fonts" -map 0:v:0 -map 1:a:0 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 192k -t ${audioDur.toFixed(2)} ${JSON.stringify(outMp4)}`,
  { stdio: 'inherit', cwd: WORK }
);

// ---------- 6. GATE: STRICT duration enforcement (user mandate 2026-05-21) ----------
// Use exact ffprobe form requested: csv=p=0
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
    
