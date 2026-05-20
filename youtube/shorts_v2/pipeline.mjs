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

// 3. fetch images
async function fetchImage(url, dst) {
  const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (10oku-shorts-bot/1.0)' }, redirect: 'follow' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.length < 1000) throw new Error('image too small');
  fs.writeFileSync(dst, buf);
}
const imagePaths = [];
for (let i = 0; i < image_urls.length; i++) {
  const dst = path.join(WORK_DIR, `img_${i}.jpg`);
  try { await fetchImage(image_urls[i], dst); imagePaths.push(dst); }
  catch (e) { console.warn(`[pipeline] image ${i} failed: ${e.message}`); }
}
if (imagePaths.length === 0) {
  const fb = path.join(WORK_DIR, 'fb.png');
  execSync(`ffmpeg -y -f lavfi -i color=c=0x1a1a2e:s=1080x1920 -frames:v 1 ${JSON.stringify(fb)}`, { stdio: 'inherit' });
  imagePaths.push(fb);
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
if (outSize < 50000) fail('output mp4 small');

// 6. Upload
const { YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN } = process.env;
if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) fail('YOUTUBE_* env required', 2);
const oauth2 = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET);
oauth2.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
const youtube = google.youtube({ version: 'v3', auth: oauth2 });

const finalTitle = title.slice(0, 95);
const finalDescription = `${description}\n\n#Shorts`.slice(0, 4500);
const finalTags = (tags && tags.length ? tags : ['Shorts', '日本史']).slice(0, 15);

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
