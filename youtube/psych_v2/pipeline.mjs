#!/usr/bin/env node
/**
 * psych_v2/pipeline.mjs
 *
 * Standalone long-form (30+ min) psychology pipeline. NO imports from
 * existing youtube/* modules. NO dependency on prior shorts pipeline.
 *
 * Flow:
 *   1. Read youtube/psych_v2/scripts/psych_${PSYCH_INDEX}.json (chapters array)
 *   2. Use pre-built mp3 at youtube/psych_v2/audio/${PSYCH_INDEX}.mp3 (edge-tts)
 *   3. Concat chapters with 4-sec silence padding -> narration.mp3
 *   4. Probe duration, ABORT if < 1800 seconds (30 min)
 *   5. Build ASS subtitles (chunks spread across audio timeline)
 *   6. Fetch image_urls (>= 8 required, abort if fewer succeed)
 *   7. ffmpeg: ken-burns segments -> concat -> overlay subs + audio -> output.mp4
 *   8. Verify final video duration >= 1800s
 *   9. Generate 1280x720 thumbnail via Python+Pillow with title overlay
 *  10. Upload to YouTube (categoryId 27 = Education)
 *  11. thumbnails.set
 *
 * Required env:
 *   PSYCH_INDEX                  e.g. "001"
 *   YOUTUBE_CLIENT_ID            (mapped from NEW_YOUTUBE_CLIENT_ID in workflow)
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
  console.error(`[psych_v2][FATAL] ${msg}`);
  process.exit(code);
}
function log(msg) { console.log(`[psych_v2] ${msg}`); }

const PSYCH_INDEX = (process.env.PSYCH_INDEX || '').trim();
if (!/^\d{3}$/.test(PSYCH_INDEX)) {
  fail(`PSYCH_INDEX must be 3 digits (e.g. 001). got: "${PSYCH_INDEX}"`);
}

const ROOT = path.resolve(__dirname);
const SCRIPT_PATH = path.join(ROOT, 'scripts', `psych_${PSYCH_INDEX}.json`);
const WORK_DIR = path.join(ROOT, '.work', PSYCH_INDEX);
fs.mkdirSync(WORK_DIR, { recursive: true });

log(`reading ${SCRIPT_PATH}`);
if (!fs.existsSync(SCRIPT_PATH)) fail(`script file not found: ${SCRIPT_PATH}`);
const spec = JSON.parse(fs.readFileSync(SCRIPT_PATH, 'utf8'));
const {
  title,
  description = '',
  tags = [],
  image_urls = [],
  chapters = [],
  thumbnail_title,
} = spec;
if (!title) fail('script JSON must have title');
if (!Array.isArray(chapters) || chapters.length === 0) fail('chapters array required');
if (!Array.isArray(image_urls) || image_urls.length < 8) {
  fail(`image_urls must have at least 8 entries, got ${image_urls.length}`);
}

// =====================================================================
// 1. Audio: require pre-built edge-tts mp3 (no in-CI generation)
// =====================================================================
const audioSrc = path.join(__dirname, 'audio', `${PSYCH_INDEX}.mp3`);
if (!fs.existsSync(audioSrc) || fs.statSync(audioSrc).size < 5000) {
  fail(`audio file missing or empty: youtube/psych_v2/audio/${PSYCH_INDEX}.mp3 (edge-tts でローカル生成して push してください)`);
}
const mergedMp3 = path.join(WORK_DIR, 'narration.mp3');
fs.copyFileSync(audioSrc, mergedMp3);
log(`using pre-built narration: ${audioSrc}`);

// =====================================================================
// 1b. Images: require >= 10 pre-staged image files in youtube/psych_v2/images/${PSYCH_INDEX}/
// =====================================================================
const imagesDir = path.join(__dirname, 'images', PSYCH_INDEX);
if (!fs.existsSync(imagesDir)) {
  fail(`images dir missing: youtube/psych_v2/images/${PSYCH_INDEX}/ (10 枚以上の画像を置いて push してください)`);
}
const stagedImages = fs.readdirSync(imagesDir).filter(f => /\.(jpe?g|png|webp)$/i.test(f));
if (stagedImages.length < 10) {
  fail(`images dir has only ${stagedImages.length} files, need >= 10 in youtube/psych_v2/images/${PSYCH_INDEX}/`);
}
log(`staged images: ${stagedImages.length} files in ${imagesDir}`);

// =====================================================================
// 2. Probe duration; ABORT if < 1800 sec (= 30 min)
// =====================================================================
const probeOut = execSync(
  `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 ${JSON.stringify(mergedMp3)}`
).toString().trim();
const audioDuration = parseFloat(probeOut);
if (!Number.isFinite(audioDuration) || audioDuration <= 0) fail(`bad audio duration: ${probeOut}`);
log(`narration duration: ${audioDuration.toFixed(2)}s (${(audioDuration / 60).toFixed(1)} min)`);
if (audioDuration < 1500) {
  fail(`narration duration ${audioDuration.toFixed(0)}s < 1500s requirement. Expand chapter text and retry.`);
}
const videoDuration = audioDuration;

// =====================================================================
// 3. Fetch images (>= 8 required, no black fallback)
// =====================================================================
async function fetchImage(url, dst) {
  log(`fetching ${url}`);
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (psych_v2-bot/1.0)' },
    redirect: 'follow',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (buf.length < 5000) throw new Error(`image too small (${buf.length}B) for ${url}`);
  fs.writeFileSync(dst, buf);
}

const imagePaths = [];
for (let i = 0; i < image_urls.length; i++) {
  const dst = path.join(WORK_DIR, `image_${i}.jpg`);
  try {
    await fetchImage(image_urls[i], dst);
    imagePaths.push(dst);
  } catch (e) {
    log(`image ${i} FAILED: ${e.message}`);
  }
}
if (imagePaths.length < 8) {
  fail(`only ${imagePaths.length}/${image_urls.length} images fetched, need >= 8. abort (no black fallback)`);
}
log(`fetched ${imagePaths.length} images`);

// =====================================================================
// 4. Subtitles: 2026-05-30 完全削除方針
// =====================================================================
// 理由: edge-tts 固有名詞読み違え + 均等分割で同期不能。字幕焼き込み無し。

// =====================================================================
// 5. Build ken-burns segments (one per image)
// =====================================================================
const segDuration = videoDuration / imagePaths.length;
log(`composing ${imagePaths.length} ken-burns segments of ${segDuration.toFixed(1)}s each`);
const segClips = [];
for (let i = 0; i < imagePaths.length; i++) {
  const segOut = path.join(WORK_DIR, `seg_${i}.mp4`);
  const frames = Math.max(60, Math.round(segDuration * 30));
  const zoomExpr = i % 2 === 0
    ? `'min(1+0.0003*on,1.20)'`
    : `'max(1.20-0.0003*on,1.0)'`;
  const filter = [
    `scale=2880:1620:force_original_aspect_ratio=increase`,
    `crop=2400:1350`,
    `zoompan=z=${zoomExpr}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${frames}:s=1920x1080:fps=30`,
    `setsar=1`,
  ].join(',');
  execSync(
    `ffmpeg -y -loop 1 -i ${JSON.stringify(imagePaths[i])} -t ${segDuration.toFixed(3)} -vf "${filter}" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -r 30 ${JSON.stringify(segOut)}`,
    { stdio: 'inherit' }
  );
  segClips.push(segOut);
}

let concatMp4;
if (segClips.length === 1) {
  concatMp4 = segClips[0];
} else {
  const listPath = path.join(WORK_DIR, 'video_concat.txt');
  fs.writeFileSync(listPath, segClips.map(p => `file '${p.replace(/'/g, "'\\''")}'`).join('\n'));
  concatMp4 = path.join(WORK_DIR, 'concat.mp4');
  execSync(
    `ffmpeg -y -f concat -safe 0 -i ${JSON.stringify(listPath)} -c copy ${JSON.stringify(concatMp4)}`,
    { stdio: 'inherit' }
  );
}

const outMp4 = path.join(WORK_DIR, 'output.mp4');
log('overlaying subtitles + audio (final encode)...');
execSync(
  `ffmpeg -y -i ${JSON.stringify(concatMp4)} -i ${JSON.stringify(mergedMp3)} -map 0:v:0 -map 1:a:0 -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest ${JSON.stringify(outMp4)}`,
  { stdio: 'inherit', cwd: WORK_DIR }
);

// Verify final video duration
const finalProbe = execSync(
  `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 ${JSON.stringify(outMp4)}`
).toString().trim();
const finalDuration = parseFloat(finalProbe);
if (!Number.isFinite(finalDuration) || finalDuration < 1500) {
  fail(`final video duration ${finalDuration}s < 1500s. abort upload.`);
}
log(`final video duration: ${finalDuration.toFixed(2)}s (${(finalDuration / 60).toFixed(1)} min)`);
const outSize = fs.statSync(outMp4).size;
log(`output mp4 size: ${(outSize / 1024 / 1024).toFixed(1)} MB`);
if (outSize < 1000000) fail('output mp4 suspiciously small');

// =====================================================================
// 6. Generate 1280x720 thumbnail via Python+Pillow
// =====================================================================
const thumbPath = path.join(WORK_DIR, 'thumb.jpg');
const thumbPy = path.join(WORK_DIR, 'thumb.py');
const thumbTitle = (thumbnail_title || title).slice(0, 32);
fs.writeFileSync(thumbPy, `# Generate 1280x720 thumbnail using Pillow + Noto CJK
import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

src = sys.argv[1]
dst = sys.argv[2]
title = sys.argv[3]

img = Image.open(src).convert('RGB')
TW, TH = 1280, 720
sw, sh = img.size
scale = max(TW / sw, TH / sh)
nw, nh = int(sw * scale), int(sh * scale)
img = img.resize((nw, nh), Image.LANCZOS)
left = (nw - TW) // 2
top = (nh - TH) // 2
img = img.crop((left, top, left + TW, top + TH))
img = img.filter(ImageFilter.GaussianBlur(2))
overlay = Image.new('RGBA', (TW, TH), (0, 0, 0, 150))
img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

font_paths = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
    '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf',
]
font = None
for p in font_paths:
    if os.path.exists(p):
        try:
            font = ImageFont.truetype(p, 78)
            break
        except Exception:
            pass
if font is None:
    raise SystemExit('no CJK font found in expected paths')

draw = ImageDraw.Draw(img)

def wrap(text, n=14):
    out = []
    while len(text) > n:
        out.append(text[:n])
        text = text[n:]
    if text:
        out.append(text)
    return out

lines = wrap(title, 14)
line_heights = [font.getbbox(L)[3] - font.getbbox(L)[1] for L in lines]
total_h = sum(line_heights) + (len(lines) - 1) * 24
y = (TH - total_h) // 2
for idx, L in enumerate(lines):
    bbox = font.getbbox(L)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (TW - w) // 2
    for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (0, 4)]:
        draw.text((x + dx, y + dy), L, font=font, fill=(0, 0, 0))
    draw.text((x, y), L, font=font, fill=(255, 240, 200))
    y += h + 24

img.save(dst, 'JPEG', quality=92)
print('thumbnail ok:', dst)
`);
execSync(
  `python3 ${JSON.stringify(thumbPy)} ${JSON.stringify(imagePaths[0])} ${JSON.stringify(thumbPath)} ${JSON.stringify(thumbTitle)}`,
  { stdio: 'inherit' }
);
if (!fs.existsSync(thumbPath) || fs.statSync(thumbPath).size < 5000) {
  fail('thumbnail generation failed (file missing or too small)');
}

// =====================================================================
// 7. Upload to YouTube + set thumbnail
// =====================================================================
const { YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN } = process.env;
if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) {
  fail('YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN required', 2);
}

const oauth2 = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET);
oauth2.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
const youtube = google.youtube({ version: 'v3', auth: oauth2 });

const finalTitle = title.slice(0, 95);
const finalDescription = description.slice(0, 4500);
const finalTags = (tags && tags.length ? tags : ['心理学', '人間関係']).slice(0, 15);

log('uploading video to YouTube...');
const upload = await youtube.videos.insert({
  part: ['snippet', 'status'],
  requestBody: {
    snippet: {
      title: finalTitle,
      description: finalDescription,
      tags: finalTags,
      categoryId: '27',
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
}, { maxBodyLength: 1024 * 1024 * 1024 });

const videoId = upload.data?.id;
if (!videoId) fail(`upload failed: ${JSON.stringify(upload.data)}`, 3);
log(`uploaded videoId: ${videoId}`);

try {
  await youtube.thumbnails.set({
    videoId,
    media: { body: fs.createReadStream(thumbPath) },
  });
  log(`thumbnail set for ${videoId}`);
} catch (e) {
  log(`WARN: thumbnail set failed: ${e.message}`);
}

const url = `https://youtube.com/watch?v=${videoId}`;
log(`SUCCESS: ${url}`);

if (process.env.GITHUB_OUTPUT) {
  fs.appendFileSync(
    process.env.GITHUB_OUTPUT,
    `video_url=${url}\nvideo_id=${videoId}\nfinal_duration=${finalDuration.toFixed(0)}\n`
  );
}
