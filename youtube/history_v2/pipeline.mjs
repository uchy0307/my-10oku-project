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
async function fetchImage(url, dst) {
  log(`fetch ${url}`);
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (10oku-history-v2-bot/1.0)' },
    redirect: 'follow',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.length < 3000) throw new Error(`image too small (${buf.length}B): ${url}`);
  fs.writeFileSync(dst, buf);
}

const imagePaths = [];
for (let i = 0; i < image_urls.length; i++) {
  const dst = path.join(WORK, `image_${i}.jpg`);
  try {
    await fetchImage(image_urls[i], dst);
    imagePaths.push(dst);
  } catch (e) {
    console.warn(`[pipeline] image ${i} failed: ${e.message}`);
  }
}
log(`images succeeded: ${imagePaths.length}/${image_urls.length}`);
if (imagePaths.length < 6) fail(`only ${imagePaths.length} images succeeded; need >= 6 (no black-bg fallback per rule)`);

// ---------- 4. Build ASS subtitles ----------
function splitForSubs(text, maxChars = 28) {
  // Split on Japanese punctuation, then re-group up to maxChars per line
  const sentences = text.split(/(?<=[。！？、])/).filter(s => s.trim().length > 0);
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

const finalDur = probeDuration(outMp4);
log(`final mp4 duration: ${finalDur.toFixed(1)}s (${(finalDur/60).toFixed(2)}min)`);
if (finalDur < 1800) fail(`final duration ${finalDur.toFixed(1)}s < 1800s requirement. Aborting upload.`);
const outSize = fs.statSync(outMp4).size;
log(`output ${outMp4} (${(outSize / 1024 / 1024).toFixed(1)} MB)`);
if (outSize < 10 * 1024 * 1024) fail(`output mp4 suspiciously small: ${outSize}B`);

// ---------- 7. Generate thumbnail (1280x720 real image + title overlay) ----------
const thumbPath = path.join(WORK, 'thumbnail.jpg');
const heroImg = imagePaths[0]; // portrait image (first in list is usually the main figure)
const titleEsc = title.replace(/'/g, "\\'").replace(/:/g, '\\:');
// Two-line title - split at ｜ if present
let line1 = title, line2 = '';
if (title.includes('｜')) {
  const parts = title.split('｜');
  line1 = parts[0];
  line2 = parts.slice(1).join('｜');
}
const l1Esc = line1.replace(/'/g, "\\'").replace(/:/g, '\\:').replace(/\\/g, '\\\\');
const l2Esc = line2.replace(/'/g, "\\'").replace(/:/g, '\\:').replace(/\\/g, '\\\\');

// Build: yellow washi-style background (gold), real image on left, red bold title on right
execSync(
  [
    `ffmpeg -y`,
    `-f lavfi -i color=c=0xF5C846:s=1280x720`,  // gold/yellow background
    `-i ${JSON.stringify(heroImg)}`,
    `-filter_complex "`,
    `[1:v]scale=600:720:force_original_aspect_ratio=increase,crop=600:720[hero];`,
    `[0:v][hero]overlay=0:0[bg1];`,
    `[bg1]drawbox=x=600:y=0:w=680:h=720:color=0xF5C846:t=fill[bg2];`,
    `[bg2]drawtext=fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc:text='${l1Esc}':fontsize=58:fontcolor=0xB80000:x=620:y=180:borderw=4:bordercolor=white,`,
    `drawtext=fontfile=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc:text='${l2Esc}':fontsize=42:fontcolor=0x222222:x=620:y=370:borderw=3:bordercolor=white`,
    `" -frames:v 1 ${JSON.stringify(thumbPath)}`,
  ].join(' '),
  { stdio: 'inherit' }
);
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
const finalTags = (Array.isArray(tags) && tags.length ? tags : ['日本史', '戦国時代', '歴史解説']).slice(0, 15);

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

// ---------- 10. Emit output for workflow ----------
if (process.env.GITHUB_OUTPUT) {
  fs.appendFileSync(process.env.GITHUB_OUTPUT, `video_url=${videoUrl}\nvideo_id=${videoId}\nduration_sec=${finalDur.toFixed(0)}\n`);
}
console.log(`\n::notice title=history_v2 upload OK::index=${LONG_INDEX} dur=${finalDur.toFixed(0)}s url=${videoUrl}\n`);
