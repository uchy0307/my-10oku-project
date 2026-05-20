#!/usr/bin/env node
/**
 * shorts_v2/pipeline.mjs
 *
 * Standalone Shorts pipeline. Does NOT import any existing youtube/scripts modules.
 *
 * Flow:
 *   1. Read shorts_v2/scripts/short_${SHORT_INDEX}.json
 *   2. TTS via edge-tts (Python CLI) -> narration.mp3
 *   3. Fetch image_urls -> jpg (fallback to solid color if all fail)
 *   4. Build ASS subtitles (chunks of narration_text timed across audio)
 *   5. ffmpeg compose 9:16 1080x1920 with ken-burns zoompan + burned subtitles
 *   6. Upload to YouTube via googleapis (OAuth refresh token)
 *
 * Required env:
 *   SHORT_INDEX                  e.g. "001"
 *   YOUTUBE_CLIENT_ID
 *   YOUTUBE_CLIENT_SECRET
 *   YOUTUBE_REFRESH_TOKEN
 */
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function fail(msg, code = 1) {
  console.error(`[pipeline][FATAL] ${msg}`);
  process.exit(code);
}

const SHORT_INDEX = (process.env.SHORT_INDEX || '').trim();
if (!/^\d{3}$/.test(SHORT_INDEX)) {
  fail(`SHORT_INDEX must be 3 digits (e.g. 001). got: "${SHORT_INDEX}"`);
}

const ROOT = path.resolve(__dirname);
const SCRIPT_PATH = path.join(ROOT, 'scripts', `short_${SHORT_INDEX}.json`);
const WORK_DIR = path.join(ROOT, '.work', SHORT_INDEX);
fs.mkdirSync(WORK_DIR, { recursive: true });

console.log(`[pipeline] reading ${SCRIPT_PATH}`);
if (!fs.existsSync(SCRIPT_PATH)) fail(`script file not found: ${SCRIPT_PATH}`);
const spec = JSON.parse(fs.readFileSync(SCRIPT_PATH, 'utf8'));
const { title, narration_text, image_urls = [], tags = [], description = '', duration_sec = 55 } = spec;
if (!title || !narration_text) fail('script JSON must have title and narration_text');

// === 1. TTS via edge-tts ===
const mp3Path = path.join(WORK_DIR, 'narration.mp3');
console.log('[pipeline] generating TTS via edge-tts');
const ttsArgs = [
  'edge-tts',
  '--voice', 'ja-JP-NanamiNeural',
  '--rate', '+5%',
  '--text', JSON.stringify(narration_text),
  '--write-media', JSON.stringify(mp3Path),
].join(' ');
execSync(ttsArgs, { stdio: 'inherit' });
if (!fs.existsSync(mp3Path) || fs.statSync(mp3Path).size < 1000) fail('TTS produced empty mp3');

// === 2. Probe audio duration ===
const probeOut = execSync(
  `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 ${JSON.stringify(mp3Path)}`
).toString().trim();
const audioDuration = parseFloat(probeOut);
if (!Number.isFinite(audioDuration) || audioDuration <= 0) fail(`bad audio duration: ${probeOut}`);
console.log(`[pipeline] audio duration: ${audioDuration.toFixed(2)}s`);

// Shorts must be <60s. Cap at 58.
const videoDuration = Math.min(audioDuration + 0.6, 58);

// === 3. Fetch images ===
async function fetchImage(url, dst) {
  console.log(`[pipeline] fetching ${url}`);
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (10oku-shorts-bot/1.0)' },
    redirect: 'follow',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.length < 1000) throw new Error(`image too small (${buf.length}B): ${url}`);
  fs.writeFileSync(dst, buf);
  return dst;
}

const imagePaths = [];
for (let i = 0; i < image_urls.length; i++) {
  const dst = path.join(WORK_DIR, `image_${i}.jpg`);
  try {
    await fetchImage(image_urls[i], dst);
    imagePaths.push(dst);
  } catch (e) {
    console.warn(`[pipeline] image ${i} failed: ${e.message}`);
  }
}

if (imagePaths.length === 0) {
  console.log('[pipeline] all images failed -> using solid color fallback');
  const fallback = path.join(WORK_DIR, 'fallback.png');
  execSync(
    `ffmpeg -y -f lavfi -i color=c=0x1a1a2e:s=1080x1920 -frames:v 1 ${JSON.stringify(fallback)}`,
    { stdio: 'inherit' }
  );
  imagePaths.push(fallback);
}

// === 4. Build ASS subtitles ===
function splitNarration(text, maxChars = 18) {
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
  return chunks.length > 0 ? chunks : [text];
}

function fmtAssTime(sec) {
  const total = Math.max(0, sec);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = (total % 60).toFixed(2).padStart(5, '0');
  return `${h}:${String(m).padStart(2, '0')}:${s}`;
}

const subChunks = splitNarration(narration_text, 18);
const subSlot = audioDuration / subChunks.length;

let assText = `[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK JP,68,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;
for (let i = 0; i < subChunks.length; i++) {
  const start = i * subSlot;
  const end = Math.min((i + 1) * subSlot, audioDuration);
  const safe = subChunks[i].replace(/[\\{}]/g, '');
  assText += `Dialogue: 0,${fmtAssTime(start)},${fmtAssTime(end)},Default,,0,0,0,,${safe}\n`;
}
const assPath = path.join(WORK_DIR, 'sub.ass');
fs.writeFileSync(assPath, assText, 'utf8');

// === 5. ffmpeg compose ===
// Strategy: build per-image ken-burns segments, concat, overlay audio+subtitles.
const segDuration = videoDuration / imagePaths.length;
const segClips = [];
for (let i = 0; i < imagePaths.length; i++) {
  const segOut = path.join(WORK_DIR, `seg_${i}.mp4`);
  const frames = Math.max(30, Math.round(segDuration * 30));
  // Alternate zoom in / zoom out for variety
  const zoomExpr = i % 2 === 0
    ? `'min(1+0.0006*on,1.25)'`
    : `'max(1.25-0.0006*on,1.0)'`;
  const filter = [
    `scale=2400:4400:force_original_aspect_ratio=increase`,
    `crop=2160:3840`,
    `zoompan=z=${zoomExpr}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=1080x1920:fps=30`,
    `setsar=1`,
  ].join(',');
  execSync(
    `ffmpeg -y -loop 1 -i ${JSON.stringify(imagePaths[i])} -t ${segDuration.toFixed(3)} -vf "${filter}" -c:v libx264 -preset veryfast -pix_fmt yuv420p -r 30 ${JSON.stringify(segOut)}`,
    { stdio: 'inherit' }
  );
  segClips.push(segOut);
}

let concatMp4;
if (segClips.length === 1) {
  concatMp4 = segClips[0];
} else {
  const listPath = path.join(WORK_DIR, 'concat_list.txt');
  fs.writeFileSync(listPath, segClips.map(p => `file '${p.replace(/'/g, "'\\''")}'`).join('\n'));
  concatMp4 = path.join(WORK_DIR, 'concat.mp4');
  execSync(
    `ffmpeg -y -f concat -safe 0 -i ${JSON.stringify(listPath)} -c copy ${JSON.stringify(concatMp4)}`,
    { stdio: 'inherit' }
  );
}

const outMp4 = path.join(WORK_DIR, 'output.mp4');
// Run ffmpeg with WORK_DIR as cwd so 'sub.ass' relative path is safe for libass.
execSync(
  `ffmpeg -y -i ${JSON.stringify(concatMp4)} -i ${JSON.stringify(mp3Path)} -vf "subtitles=sub.ass:fontsdir=/usr/share/fonts" -map 0:v:0 -map 1:a:0 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 192k -shortest ${JSON.stringify(outMp4)}`,
  { stdio: 'inherit', cwd: WORK_DIR }
);

const outSize = fs.statSync(outMp4).size;
console.log(`[pipeline] composed ${outMp4} (${(outSize / 1024 / 1024).toFixed(2)} MB)`);
if (outSize < 50000) fail('output mp4 suspiciously small');

// === 6. Upload to YouTube ===
const { YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN } = process.env;
if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) {
  fail('YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN required', 2);
}

const oauth2 = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET);
oauth2.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
const youtube = google.youtube({ version: 'v3', auth: oauth2 });

const finalTitle = title.slice(0, 95);
const finalDescription = `${description}\n\n#Shorts`.slice(0, 4500);
const finalTags = (tags && tags.length ? tags : ['Shorts', '日本史']).slice(0, 15);

console.log('[pipeline] uploading to YouTube...');
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
}, { maxBodyLength: 256 * 1024 * 1024 });

const videoId = upload.data?.id;
if (!videoId) fail(`upload failed: no videoId in response: ${JSON.stringify(upload.data)}`, 3);

const url = `https://youtube.com/shorts/${videoId}`;
console.log(`[pipeline] SUCCESS: ${url}`);

// Emit to GITHUB_OUTPUT if available
if (process.env.GITHUB_OUTPUT) {
  fs.appendFileSync(process.env.GITHUB_OUTPUT, `video_url=${url}\nvideo_id=${videoId}\n`);
}
console.log(`VIDEO_URL=${url}`);
console.log(`VIDEO_ID=${videoId}`);
