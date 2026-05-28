#!/usr/bin/env node
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
if (!/^\d{3}$/.test(SHORT_INDEX)) fail(`SHORT_INDEX must be 3 digits. got: "${SHORT_INDEX}"`);

const ROOT = path.resolve(__dirname);
const SCRIPT_PATH = path.join(ROOT, 'scripts', `short_${SHORT_INDEX}.json`);
const WORK_DIR = path.join(ROOT, '.work', SHORT_INDEX);
fs.mkdirSync(WORK_DIR, { recursive: true });

// ---------- DUP-GUARD (re-added 2026-05-28): exit 99 if already uploaded ----------
const UPLOADED_JSON = path.join(ROOT, 'uploaded.json');
{
  let db = {};
  if (fs.existsSync(UPLOADED_JSON)) {
    try { db = JSON.parse(fs.readFileSync(UPLOADED_JSON, 'utf8')) || {}; } catch {}
  }
  if (db[SHORT_INDEX]) {
    console.log(`[pipeline][SKIP] short ${SHORT_INDEX} already uploaded: ${db[SHORT_INDEX].videoUrl || db[SHORT_INDEX]}`);
    process.exit(99);
  }
}

if (!fs.existsSync(SCRIPT_PATH)) fail(`script file not found: ${SCRIPT_PATH}`);
const spec = JSON.parse(fs.readFileSync(SCRIPT_PATH, 'utf8'));
const { title, narration_text, image_urls = [], tags = [], description = '' } = spec;
if (!title || !narration_text) fail('script JSON must have title and narration_text');

// 1. TTS via gtts
const mp3RawPath = path.join(WORK_DIR, 'raw.mp3');
const mp3Path = path.join(WORK_DIR, 'narration.mp3');
const ttsTextPath = path.join(WORK_DIR, 'narration.txt');
fs.writeFileSync(ttsTextPath, narration_text, 'utf8');
console.log('[pipeline] gtts TTS...');
execSync(`gtts-cli --lang ja --file ${JSON.stringify(ttsTextPath)} --output ${JSON.stringify(mp3RawPath)}`, { stdio: 'inherit' });
if (!fs.existsSync(mp3RawPath) || fs.statSync(mp3RawPath).size < 1000) fail('TTS empty mp3');
execSync(`ffmpeg -y -i ${JSON.stringify(mp3RawPath)} -filter:a "atempo=1.18" -c:a libmp3lame -b:a 192k ${JSON.stringify(mp3Path)}`, { stdio: 'inherit' });
if (!fs.existsSync(mp3Path) || fs.statSync(mp3Path).size < 1000) fail('speed-adjust empty');

// 2. probe duration
const audioDuration = parseFloat(execSync(`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 ${JSON.stringify(mp3Path)}`).toString().trim());
if (!Number.isFinite(audioDuration) || audioDuration <= 0) fail('bad audio duration');
console.log(`[pipeline] audio ${audioDuration.toFixed(2)}s`);
const videoDuration = Math.min(audioDuration + 0.6, 58);

// pre-spec gate: 15-60s window (Shorts spec)
if (videoDuration < 15) fail(`video duration too short: ${videoDuration.toFixed(2)}s < 15s`, 6);
if (videoDuration > 60) fail(`video duration too long: ${videoDuration.toFixed(2)}s > 60s`, 6);

// 3. fetch images (Wikipedia API resolution + fail-fast)
const UA = '10oku-shorts-bot/1.0 (https://github.com/uchy0307/my-10oku-project; contact: uchiyamatakayuki0307@gmail.com)';

async function resolveWikipediaImage(url) {
  // accepts thumb URL like .../commons/thumb/x/yy/Name.jpg/800px-Name.jpg
  // or full URL like .../commons/x/yy/Name.jpg
  // Strategy: extract filename, ask Commons API for canonical thumburl at 1080w.
  if (!/wikimedia\.org/.test(url)) return url;
  const m = url.match(/\/commons\/(?:thumb\/[^/]+\/[^/]+\/)?([^/]+?\.(?:jpe?g|png|gif|webp|svg))(?:\/|$)/i);
  if (!m) return url;
  const filename = decodeURIComponent(m[1]);
  const api = `https://commons.wikimedia.org/w/api.php?action=query&titles=${encodeURIComponent('File:' + filename)}&prop=imageinfo&iiprop=url&iiurlwidth=1080&format=json&formatversion=2&origin=*`;
  const r = await fetch(api, { headers: { 'User-Agent': UA } });
  if (!r.ok) throw new Error(`commons api HTTP ${r.status}`);
  const j = await r.json();
  const page = j?.query?.pages?.[0];
  if (page?.missing) throw new Error(`commons file missing: ${filename}`);
  const ii = page?.imageinfo?.[0];
  const resolved = ii?.thumburl || ii?.url;
  if (!resolved) throw new Error(`commons no url for ${filename}`);
  return resolved;
}

async function fetchImage(originalUrl, dst) {
  let url = originalUrl;
  try {
    const resolved = await resolveWikipediaImage(originalUrl);
    if (resolved !== originalUrl) {
      console.log(`[pipeline] resolved wikimedia: ${originalUrl.split('/').slice(-1)[0]} -> ${resolved.split('/').slice(-1)[0]}`);
      url = resolved;
    }
  } catch (e) {
    throw new Error(`resolve failed: ${e.message}`);
  }
  const res = await fetch(url, { headers: { 'User-Agent': UA }, redirect: 'follow' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.length < 1000) throw new Error('image too small');
  fs.writeFileSync(dst, buf);
}

const imagePaths = [];
const imageErrors = [];
for (let i = 0; i < image_urls.length; i++) {
  const dst = path.join(WORK_DIR, `img_${i}.jpg`);
  try {
    await fetchImage(image_urls[i], dst);
    imagePaths.push(dst);
  } catch (e) {
    console.warn(`[pipeline] image ${i} failed: ${e.message}`);
    imageErrors.push(`img ${i}: ${e.message}`);
  }
}
if (imagePaths.length === 0) {
  fail(`all ${image_urls.length} images failed to fetch — refusing to upload solid-color placeholder. errors: ${imageErrors.join(' | ')}`, 7);
}

// 4. ASS subtitles
function splitNarr(text, max = 18) {
  const sents = text.split(/(?<=[。！？、])/).filter(s => s.trim().length > 0);
  const chunks = [];
  let buf = '';
  for (const s of sents) {
    if ((buf + s).length > max && buf) { chunks.push(buf.trim()); buf = s; }
    else { buf += s; }
  }
  if (buf.trim()) chunks.push(buf.trim());
  return chunks.length > 0 ? chunks : [text];
}
function fmtT(sec) {
  const t = Math.max(0, sec);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = (t % 60).toFixed(2).padStart(5, '0');
  return `${h}:${String(m).padStart(2, '0')}:${s}`;
}
const subs = splitNarr(narration_text, 18);
const slot = audioDuration / subs.length;
let ass = `[Script Info]
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
for (let i = 0; i < subs.length; i++) {
  const safe = subs[i].replace(/[\\{}]/g, '');
  ass += `Dialogue: 0,${fmtT(i * slot)},${fmtT(Math.min((i + 1) * slot, audioDuration))},Default,,0,0,0,,${safe}\n`;
}
fs.writeFileSync(path.join(WORK_DIR, 'sub.ass'), ass, 'utf8');

// 5. ffmpeg compose
const segDur = videoDuration / imagePaths.length;
const segs = [];
for (let i = 0; i < imagePaths.length; i++) {
  const so = path.join(WORK_DIR, `s${i}.mp4`);
  const frames = Math.max(30, Math.round(segDur * 30));
  const z = i % 2 === 0 ? `'min(1+0.0006*on,1.25)'` : `'max(1.25-0.0006*on,1.0)'`;
  const f = `scale=2400:4400:force_original_aspect_ratio=increase,crop=2160:3840,zoompan=z=${z}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=1080x1920:fps=30,setsar=1`;
  execSync(`ffmpeg -y -loop 1 -i ${JSON.stringify(imagePaths[i])} -t ${segDur.toFixed(3)} -vf "${f}" -c:v libx264 -preset veryfast -pix_fmt yuv420p -r 30 ${JSON.stringify(so)}`, { stdio: 'inherit' });
  segs.push(so);
}
let concatMp4 = segs[0];
if (segs.length > 1) {
  const lp = path.join(WORK_DIR, 'list.txt');
  fs.writeFileSync(lp, segs.map(p => `file '${p.replace(/'/g, "'\\''")}'`).join('\n'));
  concatMp4 = path.join(WORK_DIR, 'concat.mp4');
  execSync(`ffmpeg -y -f concat -safe 0 -i ${JSON.stringify(lp)} -c copy ${JSON.stringify(concatMp4)}`, { stdio: 'inherit' });
}
const outMp4 = path.join(WORK_DIR, 'output.mp4');
execSync(`ffmpeg -y -i ${JSON.stringify(concatMp4)} -i ${JSON.stringify(mp3Path)} -vf "subtitles=sub.ass:fontsdir=/usr/share/fonts" -map 0:v:0 -map 1:a:0 -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 192k -shortest ${JSON.stringify(outMp4)}`, { stdio: 'inherit', cwd: WORK_DIR });

const outSize = fs.statSync(outMp4).size;
console.log(`[pipeline] composed ${(outSize / 1024 / 1024).toFixed(2)} MB`);
if (outSize < 500000) fail(`output mp4 suspiciously small: ${outSize} bytes — likely missing visuals`, 8);

// post-compose duration gate
const finalDur = parseFloat(execSync(`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 ${JSON.stringify(outMp4)}`).toString().trim());
console.log(`[pipeline] final mp4 duration ${finalDur.toFixed(2)}s`);
if (finalDur < 15 || finalDur > 60) fail(`final video duration outside 15-60s: ${finalDur.toFixed(2)}s`, 9);

// 6. Upload
const { YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN } = process.env;
if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) fail('YOUTUBE_* env required', 2);
const oauth2 = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET);
oauth2.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
const youtube = google.youtube({ version: 'v3', auth: oauth2 });

const finalTitle = title.slice(0, 95);
const finalDescription = `${description}\n\n#Shorts`.slice(0, 4500);
const finalTags = (tags && tags.length ? tags : ['Shorts', '日本史']).slice(0, 15);

// duplicate-title check: scan uploads playlist for exact title match
console.log('[pipeline] checking duplicate title...');
try {
  const ch = await youtube.channels.list({ part: ['contentDetails'], mine: true });
  const uploadsId = ch.data?.items?.[0]?.contentDetails?.relatedPlaylists?.uploads;
  if (uploadsId) {
    let pageToken = undefined;
    let scanned = 0;
    let found = null;
    do {
      const pl = await youtube.playlistItems.list({ part: ['snippet', 'status'], playlistId: uploadsId, maxResults: 50, pageToken });
      for (const it of (pl.data?.items || [])) {
        scanned++;
        if (it.snippet?.title === finalTitle) {
          found = it.snippet?.resourceId?.videoId || 'unknown';
          break;
        }
      }
      pageToken = pl.data?.nextPageToken;
      if (found || scanned >= 500) break;
    } while (pageToken);
    if (found) fail(`duplicate title already on channel: "${finalTitle}" (existing videoId=${found})`, 10);
    console.log(`[pipeline] duplicate-title check OK (scanned ${scanned})`);
  } else {
    console.warn('[pipeline] could not resolve uploads playlist — skipping duplicate check');
  }
} catch (e) {
  fail(`duplicate-title check failed: ${e.message}`, 11);
}

console.log('[pipeline] uploading...');
const up = await youtube.videos.insert({
  part: ['snippet', 'status'],
  requestBody: {
    snippet: { title: finalTitle, description: finalDescription, tags: finalTags, categoryId: '22', defaultLanguage: 'ja', defaultAudioLanguage: 'ja' },
    status: { privacyStatus: 'public', selfDeclaredMadeForKids: false, madeForKids: false },
  },
  media: { body: fs.createReadStream(outMp4) },
}, { maxBodyLength: 256 * 1024 * 1024 });

const videoId = up.data?.id;
if (!videoId) fail(`upload failed: ${JSON.stringify(up.data)}`, 3);
const url = `https://youtube.com/shorts/${videoId}`;
console.log(`[pipeline] SUCCESS: ${url}`);
if (process.env.GITHUB_OUTPUT) {
  fs.appendFileSync(process.env.GITHUB_OUTPUT, `video_url=${url}\nvideo_id=${videoId}\n`);
}
console.log(`VIDEO_URL=${url}`);
console.log(`VIDEO_ID=${videoId}`);
