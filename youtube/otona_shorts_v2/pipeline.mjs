#!/usr/bin/env node
/**
 * youtube/otona_shorts_v2/pipeline.mjs
 * 大人 ショート（縦動画60秒以内）パイプライン。
 *
 * Flow:
 *   1. 台本 scripts/short_${OTONA_SHORT_INDEX}.json
 *   2. 音声 audio/${OTONA_SHORT_INDEX}.mp3
 *   3. 縦長 1080x1920 動画 (image + 焼込字幕)
 *   4. サムネ 1080x1920 (大人スタイル: 写真背景+下半分黒帯+黄色字+チャンネル署名)
 *   5. YouTube アップロード (Shorts として自動判定)
 *
 * Env: OTONA_SHORT_INDEX, YOUTUBE_CLIENT_ID, _SECRET, _REFRESH_TOKEN
 */
import fs from 'node:fs';
import path from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';
import { buildDescription } from '../../scripts/build_description.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function fail(msg, code = 1) { console.error(`[otona_shorts][FATAL] ${msg}`); process.exit(code); }
function log(msg) { console.log(`[otona_shorts] ${msg}`); }

const IDX = (process.env.OTONA_SHORT_INDEX || '').trim();
if (!/^\d{3}$/.test(IDX)) fail(`OTONA_SHORT_INDEX must be 3 digits. got: "${IDX}"`);

const ROOT = path.resolve(__dirname);
const SCRIPT_PATH = path.join(ROOT, 'scripts', `short_${IDX}.json`);
const WORK = path.join(ROOT, '.work', IDX);
fs.mkdirSync(WORK, { recursive: true });

// ---------- DUP-GUARD: uploaded.json 既アップ済 idx は即終了 ----------
const UPLOADED_JSON = path.join(ROOT, 'uploaded.json');
{
  let db = {};
  if (fs.existsSync(UPLOADED_JSON)) {
    try { db = JSON.parse(fs.readFileSync(UPLOADED_JSON, 'utf8')) || {}; } catch {}
  }
  if (db[IDX]) {
    console.log(`[pipeline][SKIP] otona_short ${IDX} already uploaded: ${db[IDX].videoUrl || db[IDX]}`);
    process.exit(99);
  }
}

if (!fs.existsSync(SCRIPT_PATH)) fail(`script missing: ${SCRIPT_PATH}`);
const spec = JSON.parse(fs.readFileSync(SCRIPT_PATH, 'utf8'));
const { title, description = '', tags = [], chapters = [], image_urls = [], thumbnail_title } = spec;

// 音声（30秒〜60秒目安）
const audioSrc = path.join(__dirname, 'audio', `${IDX}.mp3`);
if (!fs.existsSync(audioSrc)) fail(`audio missing: ${audioSrc}`);
const narrationMp3 = path.join(WORK, 'narration.mp3');
fs.copyFileSync(audioSrc, narrationMp3);

const dur = parseFloat(execSync(`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 ${JSON.stringify(narrationMp3)}`).toString().trim());
log(`audio: ${dur.toFixed(1)}s`);
if (dur < 15 || dur > 180) fail(`shorts duration must be 15-180s, got ${dur.toFixed(1)}s`);

// 画像（image_urls or stock fallback）
const stockDir = path.join(__dirname, '..', 'stock_images', 'wiki');
let imageFile = null;
if (Array.isArray(image_urls) && image_urls.length > 0 && image_urls[0].startsWith('http')) {
  // fetch first image
  const dst = path.join(WORK, 'image.jpg');
  const res = await fetch(image_urls[0], { headers: { 'User-Agent': 'Mozilla/5.0' } });
  if (!res.ok) fail(`image fetch ${res.status}`);
  fs.writeFileSync(dst, Buffer.from(await res.arrayBuffer()));
  imageFile = dst;
} else if (fs.existsSync(stockDir)) {
  const candidates = fs.readdirSync(stockDir).filter(f => /^wiki_(cafe|library|bedroom|balcony|sunset|stars)_.*\.(jpe?g|png)$/i.test(f));
  if (candidates.length === 0) fail('no psych-style stock images');
  const pick = candidates[Math.floor(Math.random() * candidates.length)];
  imageFile = path.join(stockDir, pick);
  log(`using stock: ${pick}`);
}
if (!imageFile) fail('no image source');

// テロップ ASS (縦動画用)
const allText = chapters.map(c => c.text || '').join('') || title;
function splitJP(text, max = 14) {
  const sents = text.split(/(?<=[。！？])/).filter(s => s.trim());
  const chunks = []; let buf = '';
  for (const s of sents) {
    if ((buf + s).length > max && buf) { chunks.push(buf.trim()); buf = s; }
    else buf += s;
  }
  if (buf.trim()) chunks.push(buf.trim());
  return chunks.length ? chunks : [text];
}
// 10字/cue (1080幅 / Fontsize60 = 余裕で収まる) ＋ 11字超は \N で折り返し
const rawChunks = splitJP(allText, 10);
const subChunks = rawChunks.map(c => {
  if (c.length <= 11) return c;
  const half = Math.ceil(c.length / 2);
  return c.slice(0, half) + '\\N' + c.slice(half);
}).filter(c => c.trim().length > 0);  // 空 chunk を除去 (文字ナシ防止)
const subSlot = dur / subChunks.length;
function fmt(s) { const t = Math.max(0, s); const m = Math.floor(t/60); const sec = (t%60).toFixed(2).padStart(5,'0'); return `0:${String(m).padStart(2,'0')}:${sec}`; }
// Fontsize 90→60、MarginL/R 80→120、MarginV 200→260 (下寄せ強化)
let ass = `[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Noto Sans CJK JP,60,&H00FFD73C,&H000000FF,&H00000000,&HC0000000,1,0,0,0,100,100,0,0,1,5,3,2,120,120,260,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n`;
for (let i = 0; i < subChunks.length; i++) {
  const st = i * subSlot;
  const ed = Math.min((i+1)*subSlot - 0.05, dur);
  const safe = subChunks[i].replace(/[{}]/g,'').replace(/\\(?!N)/g, '');
  if (!safe) continue;
  ass += `Dialogue: 0,${fmt(st)},${fmt(ed)},Default,,0,0,0,,${safe}\n`;
}
fs.writeFileSync(path.join(WORK, 'sub.ass'), ass, 'utf8');

// 縦動画生成（1枚画像 + 字幕 + 音声）
const outMp4 = path.join(WORK, 'output.mp4');
const filter = `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(1+0.0003*on,1.10)':d=${Math.ceil(dur*30)}:s=1080x1920:fps=30,subtitles=sub.ass`;
execSync(
  `ffmpeg -y -loop 1 -i ${JSON.stringify(imageFile)} -i ${JSON.stringify(narrationMp3)} -vf "${filter}" -t ${dur.toFixed(2)} -c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac -b:a 192k -shortest ${JSON.stringify(outMp4)}`,
  { stdio: 'inherit', cwd: WORK }
);

// サムネ生成（縦長 1080x1920）
const thumbPath = path.join(WORK, 'thumb.jpg');
const thumbPy = path.join(WORK, 'thumb.py');
fs.writeFileSync(thumbPy, `import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
src, dst, title = sys.argv[1], sys.argv[2], sys.argv[3]
img = Image.open(src).convert('RGB')
TW, TH = 1080, 1920
sw, sh = img.size
scale = max(TW/sw, TH/sh)
img = img.resize((int(sw*scale), int(sh*scale)), Image.LANCZOS)
left, top = (img.size[0]-TW)//2, (img.size[1]-TH)//2
img = img.crop((left, top, left+TW, top+TH))
overlay = Image.new('RGBA', (TW, TH), (0,0,0,0))
od = ImageDraw.Draw(overlay)
od.rectangle([(0, int(TH*0.45)), (TW, TH)], fill=(0,0,0,130))
img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
fonts = ['C:/Windows/Fonts/meiryo.ttc','C:/Windows/Fonts/YuGothM.ttc','C:/Windows/Fonts/msgothic.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc']
fp = next((p for p in fonts if os.path.exists(p)), None)
font = ImageFont.truetype(fp, 110, index=0)
font_small = ImageFont.truetype(fp, 50, index=0)
d = ImageDraw.Draw(img)
def wrap(t, n=10):
    out=[]
    while len(t)>n:
        out.append(t[:n]); t=t[n:]
    if t: out.append(t)
    return out
lines = wrap(title, 10)
total_h = len(lines)*150
y = int(TH*0.52) + (int(TH*0.43)-total_h)//2
YELLOW = (255, 215, 60)
for L in lines:
    bbox = font.getbbox(L); w = bbox[2]-bbox[0]
    x = (TW-w)//2
    for dx,dy in [(-3,-3),(3,-3),(-3,3),(3,3),(-3,0),(3,0),(0,-3),(0,3),(0,5)]:
        d.text((x+dx, y+dy), L, font=font, fill=(0,0,0))
    d.text((x, y), L, font=font, fill=YELLOW)
    y += 150
sig = '大人の心理学'
sb = font_small.getbbox(sig)
sx, sy = TW-sb[2]+sb[0]-40, TH-100
for dx,dy in [(-2,-2),(2,-2),(-2,2),(2,2)]:
    d.text((sx+dx, sy+dy), sig, font=font_small, fill=(0,0,0))
d.text((sx, sy), sig, font=font_small, fill=(255,255,255))
img.save(dst, 'JPEG', quality=92)
`, 'utf8');
const PY = process.platform === 'win32' ? 'python' : 'python3';
execSync(`${PY} ${JSON.stringify(thumbPy)} ${JSON.stringify(imageFile)} ${JSON.stringify(thumbPath)} ${JSON.stringify((thumbnail_title || title).slice(0, 30))}`, { stdio: 'inherit' });

// YouTube アップロード — 大人チャンネル専用トークン必須（誤投稿防止）
const otonaToken = process.env.OTONA_YOUTUBE_REFRESH_TOKEN;
if (!otonaToken) {
  fail('OTONA_YOUTUBE_REFRESH_TOKEN required for otona_shorts upload. Default YOUTUBE_REFRESH_TOKEN is bound to history channel and uploads here would mix channels. Get a fresh refresh token authorized for @Otona_Psychology and add to .env as OTONA_YOUTUBE_REFRESH_TOKEN.', 2);
}
const auth = new google.auth.OAuth2(
  process.env.OTONA_YOUTUBE_CLIENT_ID || process.env.YOUTUBE_CLIENT_ID,
  process.env.OTONA_YOUTUBE_CLIENT_SECRET || process.env.YOUTUBE_CLIENT_SECRET,
);
auth.setCredentials({ refresh_token: otonaToken });
const yt = google.youtube({ version: 'v3', auth });

const ins = await yt.videos.insert({
  part: ['snippet', 'status'],
  requestBody: {
    snippet: { title: title + ' #Shorts', description: buildDescription({ kind: 'otona_shorts', spec: { ...spec, description }, audioDur: Math.floor(dur) }), tags, categoryId: '27' },
    status: { privacyStatus: 'public', selfDeclaredMadeForKids: false },
  },
  media: { body: fs.createReadStream(outMp4) },
});
const videoId = ins.data.id;
log(`uploaded videoId=${videoId}`);
const _videoUrl = `https://youtu.be/${videoId}`;
console.log(`video_url=${_videoUrl}`);

// ---------- DUP-GUARD: uploaded.json 書込 ----------
try {
  let db = {};
  if (fs.existsSync(UPLOADED_JSON)) {
    try { db = JSON.parse(fs.readFileSync(UPLOADED_JSON, 'utf8')) || {}; } catch {}
  }
  db[IDX] = { videoId, videoUrl: _videoUrl, uploadedAt: new Date().toISOString() };
  fs.writeFileSync(UPLOADED_JSON, JSON.stringify(db, null, 2), 'utf8');
  log(`uploaded.json updated for otona_short ${IDX}`);
} catch (e) {
  log(`WARN uploaded.json write: ${e?.message || e}`);
}

try {
  await yt.thumbnails.set({ videoId, media: { body: fs.createReadStream(thumbPath) } });
  log('thumbnail set');
} catch (e) { log(`thumbnail warn: ${e.message}`); }
