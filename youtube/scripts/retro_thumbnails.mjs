// youtube/scripts/retro_thumbnails.mjs
// 既存 YouTube 動画（自チャンネル最新N本）に対し、Pollinations.ai で
// タイトルベースの新サムネを生成して thumbnails.set で差し替える後付けスクリプト。
//
// env:
//   YOUTUBE_CLIENT_ID
//   YOUTUBE_CLIENT_SECRET
//   YOUTUBE_REFRESH_TOKEN
//   YOUTUBE_PLAYLIST_ALL_ID  (任意。未指定なら mine=true で uploadsプレイリストを引く)
//   RETRO_MAX (任意, デフォルト 4)
//   RETRO_INTERVAL_MS (任意, デフォルト 30000 - 1本ごとに待機)
//
// 動作:
//   1. uploads/プレイリストから最新N本の videoId/title を取得
//   2. 各動画ごとに:
//      a) Pollinations.ai 画像生成（flux, 1280x720, 浮世絵風）
//      b) sharp で暗幕オーバーレイ + タイトルテキスト焼き込み
//      c) youtube.thumbnails.set で差し替え
//      d) 30s 待機（スパム判定回避）

import fs from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fetch from 'node-fetch';
import sharp from 'sharp';
import { google } from 'googleapis';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const RETRO_DIR = path.join(OUTPUT_DIR, 'retro_thumbs');

const {
  YOUTUBE_CLIENT_ID,
  YOUTUBE_CLIENT_SECRET,
  YOUTUBE_REFRESH_TOKEN,
  YOUTUBE_PLAYLIST_ALL_ID,
} = process.env;

const RETRO_MAX = parseInt(process.env.RETRO_MAX || '4', 10);
const RETRO_INTERVAL_MS = parseInt(process.env.RETRO_INTERVAL_MS || '30000', 10);
const POLL_MODEL = process.env.POLLINATIONS_MODEL || 'flux';
const IMAGE_W = 1280;
const IMAGE_H = 720;
const POLL_TIMEOUT_MS = 60000;

function buildOauthClient() {
  if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) {
    throw new Error('YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN が未設定');
  }
  const oauth2 = new google.auth.OAuth2(
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    'urn:ietf:wg:oauth:2.0:oob',
  );
  oauth2.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
  return oauth2;
}

async function fetchWithTimeout(url, ms) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

function buildPrompt(title) {
  // 既存タイトルから純粋な題材だけ抽出（先頭の「【侍の美学】」などを除去）
  const cleanTitle = title.replace(/^[【「『][^】」』]*[】」』]\s*/g, '').trim();
  return `Japanese ukiyo-e style historical painting depicting "${cleanTitle}".
Samurai warriors, Sengoku era, dramatic cinematic lighting, oil painting style,
theatrical and realistic, deep contrast, 16:9 widescreen composition.
No text, no captions, no lettering, no watermark.`;
}

async function generateBgImage(prompt, attempt = 1) {
  const seed = Math.floor(Math.random() * 1000000);
  const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=${IMAGE_W}&height=${IMAGE_H}&model=${POLL_MODEL}&nologo=true&seed=${seed}`;
  let res;
  try {
    res = await fetchWithTimeout(url, POLL_TIMEOUT_MS);
  } catch (e) {
    if (attempt < 4) {
      const wait = Math.pow(2, attempt) * 15;
      console.warn(`[retro_thumbnails] network/timeout retry in ${wait}s (${e.message})`);
      await new Promise((r) => setTimeout(r, wait * 1000));
      return generateBgImage(prompt, attempt + 1);
    }
    throw e;
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    if ((res.status === 503 || res.status === 429 || res.status === 502 || res.status === 500) && attempt < 4) {
      const wait = Math.pow(2, attempt) * 15;
      console.warn(`[retro_thumbnails] ${res.status} retry in ${wait}s`);
      await new Promise((r) => setTimeout(r, wait * 1000));
      return generateBgImage(prompt, attempt + 1);
    }
    throw new Error(`Pollinations API ${res.status}: ${text.slice(0, 200)}`);
  }
  const ab = await res.arrayBuffer();
  return Buffer.from(ab);
}

async function renderThumb(title, outPath, bgBuffer) {
  const W = IMAGE_W;
  const H = IMAGE_H;
  // 表示用タイトル: 接頭辞 "【侍の美学】" を除去
  const displayTitle = title.replace(/^[【「『][^】」』]*[】」』]\s*/g, '').trim() || title;
  const len = displayTitle.length;
  let fontSize = 88;
  if (len > 14) fontSize = 72;
  if (len > 22) fontSize = 58;
  if (len > 34) fontSize = 44;

  const half = Math.ceil(len / 2);
  const breakPos = displayTitle.lastIndexOf(' ', half);
  const line1 = breakPos > 0 ? displayTitle.slice(0, breakPos) : displayTitle;
  const line2 = breakPos > 0 ? displayTitle.slice(breakPos + 1) : '';
  const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const overlaySvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#000" stop-opacity="0.0"/>
      <stop offset="0.4" stop-color="#000" stop-opacity="0.45"/>
      <stop offset="1" stop-color="#000" stop-opacity="0.85"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="${W}" height="${H}" fill="url(#g)"/>
  <text x="50%" y="${line2 ? '60%' : '70%'}" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="${fontSize}" fill="#fff7e0" font-weight="900"
        stroke="#000" stroke-width="3" paint-order="stroke">${escape(line1)}</text>
  ${line2 ? `<text x="50%" y="78%" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="${fontSize}" fill="#fff7e0" font-weight="900"
        stroke="#000" stroke-width="3" paint-order="stroke">${escape(line2)}</text>` : ''}
  <text x="50%" y="93%" text-anchor="middle"
        font-family="Noto Sans CJK JP, Hiragino Sans, sans-serif"
        font-size="30" fill="#e7c66a" font-style="italic"
        stroke="#000" stroke-width="2" paint-order="stroke">― 侍の美学 ―</text>
</svg>`;

  await sharp(bgBuffer)
    .resize(W, H, { fit: 'cover', position: 'centre' })
    .composite([{ input: Buffer.from(overlaySvg), top: 0, left: 0 }])
    .png()
    .toFile(outPath);
}

async function fetchRecentVideos(youtube) {
  // 1) チャンネルの uploads プレイリスト ID を取得
  const ch = await youtube.channels.list({ part: ['contentDetails'], mine: true });
  const uploadsId = ch?.data?.items?.[0]?.contentDetails?.relatedPlaylists?.uploads;
  console.log(`[retro_thumbnails] uploads playlist: ${uploadsId}`);
  const candidatePlaylists = [uploadsId, YOUTUBE_PLAYLIST_ALL_ID].filter(Boolean);

  for (const plId of candidatePlaylists) {
    try {
      const res = await youtube.playlistItems.list({
        part: ['snippet'],
        playlistId: plId,
        maxResults: RETRO_MAX,
      });
      const items = (res?.data?.items || []).map((it) => ({
        videoId: it.snippet?.resourceId?.videoId,
        title: it.snippet?.title,
        publishedAt: it.snippet?.publishedAt,
      })).filter((it) => it.videoId && it.title);
      if (items.length > 0) {
        console.log(`[retro_thumbnails] using playlist ${plId}: ${items.length} items`);
        return items.slice(0, RETRO_MAX);
      }
    } catch (e) {
      console.warn(`[retro_thumbnails] playlist ${plId} failed: ${e.message}`);
    }
  }
  throw new Error('動画候補が取得できませんでした');
}

async function setThumbnail(youtube, videoId, thumbPath) {
  console.log(`[retro_thumbnails] thumbnails.set videoId=${videoId}`);
  await youtube.thumbnails.set({
    videoId,
    media: { body: createReadStream(thumbPath), mimeType: 'image/png' },
  });
}

async function main() {
  await fs.mkdir(RETRO_DIR, { recursive: true });
  const oauth = buildOauthClient();
  const youtube = google.youtube({ version: 'v3', auth: oauth });

  const videos = await fetchRecentVideos(youtube);
  console.log(`[retro_thumbnails] target videos:`);
  for (const v of videos) {
    console.log(`  - ${v.videoId} ${v.title}`);
  }

  const results = [];
  for (let i = 0; i < videos.length; i++) {
    const v = videos[i];
    const safeId = v.videoId.replace(/[^a-zA-Z0-9_-]/g, '_');
    const bgPath = path.join(RETRO_DIR, `${safeId}_bg.png`);
    const thumbPath = path.join(RETRO_DIR, `${safeId}_thumb.png`);
    const result = { videoId: v.videoId, title: v.title, status: 'pending' };

    try {
      const prompt = buildPrompt(v.title);
      console.log(`[retro_thumbnails] [${i + 1}/${videos.length}] generating bg for ${v.videoId}`);
      const bgBuf = await generateBgImage(prompt);
      await fs.writeFile(bgPath, bgBuf);
      console.log(`[retro_thumbnails]   bg saved ${bgPath} (${bgBuf.length} bytes)`);

      await renderThumb(v.title, thumbPath, bgBuf);
      console.log(`[retro_thumbnails]   thumb composited ${thumbPath}`);

      await setThumbnail(youtube, v.videoId, thumbPath);
      console.log(`[retro_thumbnails]   thumbnails.set OK`);
      result.status = 'success';
      result.thumbPath = thumbPath;
    } catch (e) {
      console.error(`[retro_thumbnails]   FAILED ${v.videoId}: ${e.message}`);
      result.status = 'failed';
      result.error = e.message;
    }
    results.push(result);

    if (i < videos.length - 1) {
      console.log(`[retro_thumbnails] sleeping ${RETRO_INTERVAL_MS}ms before next video`);
      await new Promise((r) => setTimeout(r, RETRO_INTERVAL_MS));
    }
  }

  const summaryPath = path.join(RETRO_DIR, 'summary.json');
  await fs.writeFile(summaryPath, JSON.stringify({ ranAt: new Date().toISOString(), results }, null, 2), 'utf-8');
  console.log(`[retro_thumbnails] summary saved ${summaryPath}`);

  const failed = results.filter((r) => r.status !== 'success');
  console.log(`[retro_thumbnails] DONE. success=${results.length - failed.length}/${results.length}`);
  if (failed.length === results.length) {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error('[retro_thumbnails] FAILED:', err);
  process.exit(1);
});
