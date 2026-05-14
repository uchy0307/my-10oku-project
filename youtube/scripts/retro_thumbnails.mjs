// youtube/scripts/retro_thumbnails.mjs
// 既存 YouTube 動画（自チャンネル最新N本）に対し、Wikipedia 肖像 + 黄色和紙 +
// 赤+黄縁太字タイトルの v2 サムネを生成して thumbnails.set で差し替える。
// AI画像は一切使わない。

import fs from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { google } from 'googleapis';
import { fetchWikiImage, buildCandidateQueries } from './fetch_portrait.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const RETRO_DIR = path.join(OUTPUT_DIR, 'retro_thumbs');

const { YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, YOUTUBE_PLAYLIST_ALL_ID } = process.env;

const RETRO_MAX = parseInt(process.env.RETRO_MAX || '5', 10);
const RETRO_INTERVAL_MS = parseInt(process.env.RETRO_INTERVAL_MS || '30000', 10);
const IMAGE_W = 1280;
const IMAGE_H = 720;

function buildOauthClient() {
  if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) throw new Error('YOUTUBE secrets missing');
  const oauth2 = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, 'urn:ietf:wg:oauth:2.0:oob');
  oauth2.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
  return oauth2;
}

async function renderThumb(title, totalSec, outPath, portraitBuffer) {
  const W = IMAGE_W;
  const H = IMAGE_H;
  const LEFT_W = 576;
  const rawTitle = (title || '').replace(/^[【「『][^】」』]*[】」』]\s*/g, '').trim();
  const main = rawTitle.split(/[\s ,、・「」『』]/)[0] || rawTitle || '日本史';
  const len = main.length;
  const mid = Math.ceil(len / 2);
  const line1 = main.slice(0, mid);
  const line2 = main.slice(mid);
  const maxLine = Math.max(line1.length, line2.length || 0);
  let fontSize = 300;
  if (maxLine === 2) fontSize = 300;
  else if (maxLine === 3) fontSize = 220;
  else if (maxLine === 4) fontSize = 170;
  else if (maxLine >= 5) fontSize = 130;
  const textCx = LEFT_W + (W - LEFT_W) / 2;
  const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const dm = Math.floor((totalSec || 0) / 60);
  const ds = Math.floor((totalSec || 0) % 60).toString().padStart(2, '0');
  const durTxt = totalSec ? `${dm}:${ds}` : '';
  const bgSvg = `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs><pattern id="paper" patternUnits="userSpaceOnUse" width="14" height="14"><rect width="14" height="14" fill="#E8C547"/><circle cx="3" cy="3" r="0.6" fill="rgba(160,120,40,0.35)"/><circle cx="9" cy="7" r="0.4" fill="rgba(160,120,40,0.25)"/><circle cx="5" cy="11" r="0.5" fill="rgba(160,120,40,0.30)"/></pattern><linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F0D060"/><stop offset="1" stop-color="#D9A82B"/></linearGradient></defs><rect width="${W}" height="${H}" fill="url(#rim)"/><rect width="${W}" height="${H}" fill="url(#paper)" opacity="0.6"/></svg>`;
  const textSvg = `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><text x="${textCx}" y="${line2 ? '32%' : '50%'}" text-anchor="middle" dominant-baseline="middle" font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif" font-weight="900" font-size="${fontSize}" fill="#C8102E" stroke="#FFF6A8" stroke-width="8" paint-order="stroke">${escape(line1)}</text>${line2 ? `<text x="${textCx}" y="68%" text-anchor="middle" dominant-baseline="middle" font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif" font-weight="900" font-size="${fontSize}" fill="#C8102E" stroke="#FFF6A8" stroke-width="8" paint-order="stroke">${escape(line2)}</text>` : ''}${durTxt ? `<rect x="${W - 200}" y="${H - 76}" width="170" height="54" rx="27" fill="rgba(0,0,0,0.78)"/><text x="${W - 115}" y="${H - 36}" text-anchor="middle" dominant-baseline="middle" font-family="Noto Sans CJK JP, sans-serif" font-size="34" font-weight="700" fill="#FFFFFF">${durTxt}</text>` : ''}</svg>`;
  const baseBg = await sharp(Buffer.from(bgSvg)).png().toBuffer();
  const composites = [];
  if (portraitBuffer) {
    try {
      const portrait = await sharp(portraitBuffer).resize(LEFT_W, H, { fit: 'cover', position: 'centre' }).png().toBuffer();
      composites.push({ input: portrait, top: 0, left: 0 });
    } catch (e) { console.warn(`[retro_thumbnails] portrait resize failed: ${e.message}`); }
  }
  composites.push({ input: Buffer.from(textSvg), top: 0, left: 0 });
  await sharp(baseBg).composite(composites).png().toFile(outPath);
}

function parseISO8601Duration(iso) {
  const m = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(iso || '');
  if (!m) return 0;
  return (parseInt(m[1] || '0') * 3600) + (parseInt(m[2] || '0') * 60) + parseInt(m[3] || '0');
}

async function fetchRecentVideos(youtube) {
  const ch = await youtube.channels.list({ part: ['contentDetails'], mine: true });
  const uploadsId = ch?.data?.items?.[0]?.contentDetails?.relatedPlaylists?.uploads;
  console.log(`[retro_thumbnails] uploads playlist: ${uploadsId}`);
  const candidatePlaylists = [uploadsId, YOUTUBE_PLAYLIST_ALL_ID].filter(Boolean);
  for (const plId of candidatePlaylists) {
    try {
      const res = await youtube.playlistItems.list({ part: ['snippet'], playlistId: plId, maxResults: RETRO_MAX });
      const items = (res?.data?.items || []).map((it) => ({ videoId: it.snippet?.resourceId?.videoId, title: it.snippet?.title })).filter((it) => it.videoId && it.title);
      if (items.length > 0) {
        console.log(`[retro_thumbnails] using playlist ${plId}: ${items.length} items`);
        const ids = items.map(i => i.videoId);
        const videosRes = await youtube.videos.list({ part: ['contentDetails'], id: ids });
        const durMap = new Map();
        for (const v of (videosRes?.data?.items || [])) durMap.set(v.id, parseISO8601Duration(v.contentDetails?.duration));
        for (const it of items) it.duration = durMap.get(it.videoId) || 0;
        return items.slice(0, RETRO_MAX);
      }
    } catch (e) { console.warn(`[retro_thumbnails] playlist ${plId} failed: ${e.message}`); }
  }
  throw new Error('No videos found');
}

async function setThumbnail(youtube, videoId, thumbPath) {
  console.log(`[retro_thumbnails] thumbnails.set videoId=${videoId}`);
  await youtube.thumbnails.set({ videoId, media: { body: createReadStream(thumbPath), mimeType: 'image/png' } });
}

async function fetchTopicPortrait(title) {
  const queries = buildCandidateQueries(title);
  for (const q of queries) {
    const r = await fetchWikiImage(q);
    if (r && r.buffer) {
      console.log(`[retro_thumbnails] portrait matched "${q}" -> ${r.sourceUrl}`);
      return r.buffer;
    }
  }
  console.warn('[retro_thumbnails] no Wikipedia portrait, fallback to yellow bg text-only');
  return null;
}

async function main() {
  await fs.mkdir(RETRO_DIR, { recursive: true });
  const oauth = buildOauthClient();
  const youtube = google.youtube({ version: 'v3', auth: oauth });
  const videos = await fetchRecentVideos(youtube);
  console.log(`[retro_thumbnails] target videos:`);
  for (const v of videos) console.log(`  - ${v.videoId} ${v.title} (${v.duration}s)`);
  const results = [];
  for (let i = 0; i < videos.length; i++) {
    const v = videos[i];
    const safeId = v.videoId.replace(/[^a-zA-Z0-9_-]/g, '_');
    const thumbPath = path.join(RETRO_DIR, `${safeId}_thumb_v2.png`);
    const result = { videoId: v.videoId, title: v.title, status: 'pending' };
    try {
      console.log(`[retro_thumbnails] [${i + 1}/${videos.length}] portrait fetch for ${v.title}`);
      const portrait = await fetchTopicPortrait(v.title);
      await renderThumb(v.title, v.duration, thumbPath, portrait);
      console.log(`[retro_thumbnails] thumb rendered ${thumbPath}`);
      await setThumbnail(youtube, v.videoId, thumbPath);
      result.status = 'success';
      result.thumbPath = thumbPath;
      result.hasPortrait = !!portrait;
    } catch (e) {
      console.error(`[retro_thumbnails] FAILED ${v.videoId}: ${e.message}`);
      result.status = 'failed';
      result.error = e.message;
    }
    results.push(result);
    if (i < videos.length - 1) {
      console.log(`[retro_thumbnails] sleeping ${RETRO_INTERVAL_MS}ms before next`);
      await new Promise((r) => setTimeout(r, RETRO_INTERVAL_MS));
    }
  }
  const summaryPath = path.join(RETRO_DIR, 'summary.json');
  await fs.writeFile(summaryPath, JSON.stringify({ ranAt: new Date().toISOString(), results }, null, 2), 'utf-8');
  console.log(`[retro_thumbnails] summary saved ${summaryPath}`);
  const failed = results.filter((r) => r.status !== 'success');
  console.log(`[retro_thumbnails] DONE. success=${results.length - failed.length}/${results.length}`);
  if (failed.length === results.length) process.exit(1);
}

main().catch((err) => { console.error('[retro_thumbnails] FAILED:', err); process.exit(1); });
