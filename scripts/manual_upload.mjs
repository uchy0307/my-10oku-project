#!/usr/bin/env node
// scripts/manual_upload.mjs
// 既ビルドの output.mp4 + thumbnail.jpg を YouTube にアップロードする
// Usage: node scripts/manual_upload.mjs --kind psych --index 001

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

// Load .env (utf-8-sig)
const envFile = path.join(ROOT, '.env');
if (fs.existsSync(envFile)) {
  let txt = fs.readFileSync(envFile, 'utf8');
  if (txt.charCodeAt(0) === 0xFEFF) txt = txt.slice(1);
  for (const line of txt.split(/\r?\n/)) {
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const [k, ...rest] = line.split('=');
    if (!process.env[k.trim()]) process.env[k.trim()] = rest.join('=').trim();
  }
}

// Args
const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  const k = process.argv[i].replace(/^--/, '');
  args[k] = process.argv[i + 1];
}
if (!args.kind || !args.index) {
  console.error('Usage: node scripts/manual_upload.mjs --kind <history|psych|shorts|otona_shorts> --index 001');
  process.exit(1);
}

const cfgs = {
  history: {
    work: path.join(ROOT, 'youtube', 'history_v2', '.work', args.index),
    script: path.join(ROOT, 'youtube', 'history_v2', 'scripts', `long_${args.index}.json`),
    tokenEnv: 'YOUTUBE_REFRESH_TOKEN',
    category: '27',
  },
  psych: {
    work: path.join(ROOT, 'youtube', 'psych_v2', '.work', args.index),
    script: path.join(ROOT, 'youtube', 'psych_v2', 'scripts', `psych_${args.index}.json`),
    tokenEnv: 'OTONA_YOUTUBE_REFRESH_TOKEN',
    category: '27',
  },
  shorts: {
    work: path.join(ROOT, 'youtube', 'shorts_v2', '.work', args.index),
    script: path.join(ROOT, 'youtube', 'shorts_v2', 'scripts', `short_${args.index}.json`),
    tokenEnv: 'YOUTUBE_REFRESH_TOKEN',
    category: '22',
    shorts: true,
  },
  otona_shorts: {
    work: path.join(ROOT, 'youtube', 'otona_shorts_v2', '.work', args.index),
    script: path.join(ROOT, 'youtube', 'otona_shorts_v2', 'scripts', `short_${args.index}.json`),
    tokenEnv: 'OTONA_YOUTUBE_REFRESH_TOKEN',
    category: '27',
    shorts: true,
  },
};
const cfg = cfgs[args.kind];
if (!cfg) { console.error('unknown kind'); process.exit(1); }

const mp4 = path.join(cfg.work, 'output.mp4');
if (!fs.existsSync(mp4)) { console.error(`no output.mp4: ${mp4}`); process.exit(2); }
const thumb = path.join(cfg.work, 'thumbnail.jpg');
const spec = JSON.parse(fs.readFileSync(cfg.script, 'utf8'));
let title = (spec.title || '').trim();
const description = (spec.description || '').trim();
const tags = spec.tags || [];
if (!title) { console.error('no title in script'); process.exit(2); }

const cid = process.env.YOUTUBE_CLIENT_ID;
const csec = process.env.YOUTUBE_CLIENT_SECRET;
const rtoken = process.env[cfg.tokenEnv];
if (!cid || !csec || !rtoken) {
  console.error(`missing env: YOUTUBE_CLIENT_ID/_SECRET/${cfg.tokenEnv}`);
  process.exit(2);
}

const oauth2 = new google.auth.OAuth2(cid, csec);
oauth2.setCredentials({ refresh_token: rtoken });
const yt = google.youtube({ version: 'v3', auth: oauth2 });

// Get uploads playlist + existing titles
const ch = await yt.channels.list({ part: ['contentDetails', 'snippet'], mine: true });
const channelName = ch.data.items[0]?.snippet?.title;
console.log(`[manual_upload] uploading to channel: ${channelName}`);
const uplPl = ch.data.items[0].contentDetails.relatedPlaylists.uploads;
const existingTitles = new Set();
let pageToken = undefined;
let pageCount = 0;
do {
  const pl = await yt.playlistItems.list({ part: ['snippet'], playlistId: uplPl, maxResults: 50, pageToken });
  for (const it of pl.data.items || []) existingTitles.add(it.snippet.title);
  pageToken = pl.data.nextPageToken;
  pageCount++;
} while (pageToken && pageCount < 6);

if (cfg.shorts && !title.includes('#Shorts') && !title.includes('#shorts')) {
  title = title + ' #Shorts';
}
let finalTitle = title;
if (existingTitles.has(finalTitle)) {
  const d = new Date();
  const jst = new Date(d.getTime() + 9 * 3600 * 1000);
  const suffix = ` (${jst.getUTCMonth()+1}/${jst.getUTCDate()}再)`;
  finalTitle = title.slice(0, 100 - suffix.length) + suffix;
  console.log(`[manual_upload] title duplicate → using: ${finalTitle}`);
}

console.log(`[manual_upload] file ${(fs.statSync(mp4).size/1024/1024).toFixed(1)}MB`);
const insertRes = await yt.videos.insert({
  part: ['snippet', 'status'],
  requestBody: {
    snippet: { title: finalTitle.slice(0, 100), description: description.slice(0, 4500), tags: tags.slice(0, 15), categoryId: cfg.category },
    status: { privacyStatus: 'public', selfDeclaredMadeForKids: false },
  },
  media: { body: fs.createReadStream(mp4) },
});
const videoId = insertRes.data.id;
const url = cfg.shorts ? `https://youtube.com/shorts/${videoId}` : `https://youtube.com/watch?v=${videoId}`;
console.log(`video_url=${url}`);

if (fs.existsSync(thumb)) {
  try {
    await yt.thumbnails.set({ videoId, media: { body: fs.createReadStream(thumb) } });
    console.log('thumbnail set');
  } catch (e) {
    console.log(`thumbnail set failed (non-fatal): ${e?.message || e}`);
  }
}

// Post to messages.json
const msgPath = path.join(ROOT, 'scripts', 'messages.json');
let msgs = [];
try { msgs = JSON.parse(fs.readFileSync(msgPath, 'utf8')); } catch {}
const now = new Date();
const jst = new Date(now.getTime() + 9 * 3600 * 1000);
const iso = jst.toISOString().replace('Z', '+09:00');
const emoji = { history: '⚔️', psych: '🧠', shorts: '⚡', otona_shorts: '✨' }[args.kind];
msgs.push({
  id: `manual_${args.kind}_${args.index}_${Math.floor(now.getTime()/1000)}`,
  ts: iso,
  title: `${emoji} ${args.kind} #${args.index} 手動アップ完了`,
  body: `${url}\n\nタイトル: ${finalTitle}\nファイル: ${(fs.statSync(mp4).size/1024/1024).toFixed(1)}MB`,
  read: false,
  auto: true,
});
fs.writeFileSync(msgPath, JSON.stringify(msgs, null, 2), 'utf8');
console.log('done, messages.json updated');
