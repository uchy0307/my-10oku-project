// youtube/scripts/shorts_pipeline.mjs
// 60秒 YouTube Shorts を既存 long video から生成→upload。
// 入力: state.json から最新 uploaded videoId / topicId を取得
// 工程: yt-dlp で source 取得 → ffmpeg で 60s × 1080x1920 縦長 crop → YouTube upload as Shorts
//
// env: YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
//      YOUTUBE_PLAYLIST_ALL_ID (optional)
//      SHORTS_VIDEO_ID (optional: workflow_dispatch input)
//      SHORTS_CLIP_START (optional: default 30)
//      SHORTS_CLIP_DURATION (optional: default 58)

import fs from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');
const SHORTS_STATE_FILE = path.join(OUTPUT_DIR, 'shorts_state.json');

const {
  YOUTUBE_CLIENT_ID,
  YOUTUBE_CLIENT_SECRET,
  YOUTUBE_REFRESH_TOKEN,
  YOUTUBE_PLAYLIST_ALL_ID,
  SHORTS_VIDEO_ID,
  SHORTS_CLIP_START,
  SHORTS_CLIP_DURATION,
} = process.env;

const CLIP_START = Number(SHORTS_CLIP_START || 30);
const CLIP_DURATION = Math.min(Number(SHORTS_CLIP_DURATION || 58), 59);

function run(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    console.log('[run]', cmd, args.join(' '));
    const p = spawn(cmd, args, { stdio: 'inherit', ...opts });
    p.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(cmd + ' exit ' + code))));
  });
}

async function loadJson(p, dflt) {
  try { return JSON.parse(await fs.readFile(p, 'utf-8')); } catch { return dflt; }
}

async function saveJson(p, obj) {
  await fs.writeFile(p, JSON.stringify(obj, null, 2), 'utf-8');
}

function buildOauth() {
  if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) return null;
  const o = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, 'urn:ietf:wg:oauth:2.0:oob');
  o.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
  return o;
}

async function pickSourceCandidates() {
  if (SHORTS_VIDEO_ID && SHORTS_VIDEO_ID.trim()) return [SHORTS_VIDEO_ID.trim()];
  const state = await loadJson(STATE_FILE, {});
  const shortsState = await loadJson(SHORTS_STATE_FILE, { processed: [], deadVideos: [] });
  const processed = new Set(shortsState.processed || []);
  const dead = new Set(shortsState.deadVideos || []);
  const skip = (id) => !id || processed.has(id) || dead.has(id);
  const candidates = [];
  const seen = new Set();
  const push = (id, when) => {
    if (skip(id) || seen.has(id)) return;
    seen.add(id);
    candidates.push({ videoId: id, uploadedAt: when || '' });
  };
  const last = state.lastUploadResult;
  if (last && last.status === 'success' && last.videoId) {
    push(last.videoId, state.lastUploadAt || last.uploadedAt);
  }
  let files = [];
  try { files = (await fs.readdir(OUTPUT_DIR)).filter((f) => f.endsWith('_uploaded.json')); } catch {}
  const records = [];
  for (const f of files) {
    try {
      const r = JSON.parse(await fs.readFile(path.join(OUTPUT_DIR, f), 'utf-8'));
      if (r && r.videoId) records.push({ ...r, file: f });
    } catch {}
  }
  records.sort((a, b) => (b.uploadedAt || '').localeCompare(a.uploadedAt || ''));
  for (const r of records) push(r.videoId, r.uploadedAt);
  return candidates.map((c) => c.videoId);
}

async function fetchVideoMeta(youtube, videoId) {
  const r = await youtube.videos.list({ part: ['snippet'], id: [videoId] });
  const item = (r.data.items || [])[0];
  if (!item) {
    const err = new Error('Video ' + videoId + ' not found on YouTube');
    err.code = 'VIDEO_NOT_FOUND';
    throw err;
  }
  return item.snippet;
}

async function markVideoDead(videoId, reason) {
  try {
    const s = await loadJson(SHORTS_STATE_FILE, { processed: [], records: [], deadVideos: [] });
    s.deadVideos = Array.from(new Set([...(s.deadVideos || []), videoId]));
    s.deadVideoLog = (s.deadVideoLog || []).concat([{ videoId, reason, at: new Date().toISOString() }]).slice(-50);
    await saveJson(SHORTS_STATE_FILE, s);
    console.warn('[shorts] marked dead videoId=' + videoId + ' reason=' + reason);
  } catch (e) {
    console.warn('[shorts] markVideoDead failed:', e.message);
  }
}

async function pickAndFetchSnippet(youtube) {
  const candidates = await pickSourceCandidates();
  if (candidates.length === 0) throw new Error('No un-shortified video found in state / uploaded records');
  console.log('[shorts] candidates (newest first): ' + candidates.join(', '));
  let lastErr = null;
  for (const id of candidates) {
    try {
      const snippet = await fetchVideoMeta(youtube, id);
      console.log('[shorts] selected videoId=' + id + ' title="' + snippet.title + '"');
      return { videoId: id, snippet };
    } catch (e) {
      lastErr = e;
      if (e.code === 'VIDEO_NOT_FOUND') {
        await markVideoDead(id, 'fetchVideoMeta 404');
        continue;
      }
      throw e;
    }
  }
  throw lastErr || new Error('All candidates failed YouTube fetch');
}

async function downloadSource(videoId, dest) {
  const tryArgs = [
    ['--extractor-args', 'youtube:player_client=android', '--user-agent', 'com.google.android.youtube/19.09.37 (Linux; U; Android 14; en_US) gzip'],
    ['--extractor-args', 'youtube:player_client=ios', '--user-agent', 'com.google.ios.youtube/19.09.3 (iPhone16,2; U; CPU iOS 17_0 like Mac OS X)'],
    ['--extractor-args', 'youtube:player_client=web_safari'],
    [],
  ];
  let lastErr = null;
  for (const extra of tryArgs) {
    try {
      await run('yt-dlp', [
        ...extra, '--no-check-certificate', '--no-playlist',
        '-f', 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
        '-o', dest,
        'https://www.youtube.com/watch?v=' + videoId,
      ]);
      console.log('[yt-dlp] OK with', JSON.stringify(extra));
      return;
    } catch (e) {
      console.warn('[yt-dlp] strategy failed:', e.message);
      lastErr = e;
    }
  }
  throw lastErr || new Error('yt-dlp all strategies failed');
}

async function makeShortsVideo(srcPath, outPath) {
  const vf = "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920,setsar=1";
  await run('ffmpeg', [
    '-y', '-ss', String(CLIP_START), '-i', srcPath, '-t', String(CLIP_DURATION),
    '-vf', vf, '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', outPath,
  ]);
}

async function uploadShorts(youtube, videoPath, snippet, sourceVideoId) {
  const baseTitle = (snippet.title || 'Shorts').slice(0, 80);
  const title = (baseTitle + ' #Shorts').slice(0, 100);
  const description = ((snippet.description || '') + '\n\n──\n本編: https://www.youtube.com/watch?v=' + sourceVideoId + '\n#Shorts #日本史 #侍 #samurai').slice(0, 4900);
  const tags = (snippet.tags || []).concat(['Shorts', '日本史', '侍', 'samurai']).slice(0, 30);
  const stat = await fs.stat(videoPath);
  console.log('[upload] size=' + stat.size + ' bytes title="' + title + '"');
  const res = await youtube.videos.insert(
    {
      part: ['snippet', 'status'],
      requestBody: {
        snippet: { title, description, tags, categoryId: snippet.categoryId || '27', defaultLanguage: 'ja', defaultAudioLanguage: 'ja' },
        status: { privacyStatus: 'public', selfDeclaredMadeForKids: false },
      },
      media: { body: createReadStream(videoPath) },
    },
    { onUploadProgress: (evt) => { const pct = stat.size ? Math.round((evt.bytesRead / stat.size) * 100) : 0; process.stdout.write('\r[upload] ' + pct + '%'); } },
  );
  process.stdout.write('\n');
  return res.data;
}

async function main() {
  const oauth = buildOauth();
  if (!oauth) throw new Error('OAuth env missing (YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN)');
  const youtube = google.youtube({ version: 'v3', auth: oauth });
  const { videoId: sourceVideoId, snippet } = await pickAndFetchSnippet(youtube);
  console.log('[shorts] source videoId = ' + sourceVideoId);
  console.log('[shorts] source title = "' + snippet.title + '"');
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  let srcPath = path.join(OUTPUT_DIR, 'shorts_src_' + sourceVideoId + '.mp4');
  const outPath = path.join(OUTPUT_DIR, 'shorts_' + sourceVideoId + '.mp4');
  const localFile = process.env.SHORTS_LOCAL_FILE;
  if (localFile) {
    try {
      const s = await fs.stat(localFile);
      if (s.size > 0) {
        console.log('[shorts] using local file: ' + localFile + ' (' + s.size + ' bytes)');
        srcPath = localFile;
      }
    } catch (e) {
      console.warn('[shorts] SHORTS_LOCAL_FILE not usable: ' + e.message + '. Falling back to download.');
    }
  }
  if (srcPath !== localFile) {
    await downloadSource(sourceVideoId, srcPath);
  }
  await makeShortsVideo(srcPath, outPath);
  const result = await uploadShorts(youtube, outPath, snippet, sourceVideoId);
  const shortsVideoId = result.id;
  const shortsUrl = 'https://www.youtube.com/shorts/' + shortsVideoId;
  console.log('[shorts] uploaded videoId=' + shortsVideoId + ' url=' + shortsUrl);
  if (YOUTUBE_PLAYLIST_ALL_ID) {
    try {
      await youtube.playlistItems.insert({
        part: ['snippet'],
        requestBody: { snippet: { playlistId: YOUTUBE_PLAYLIST_ALL_ID, resourceId: { kind: 'youtube#video', videoId: shortsVideoId } } },
      });
      console.log('[shorts] playlist add OK');
    } catch (e) {
      console.warn('[shorts] playlist add failed (non-fatal):', e.message);
    }
  }
  const shortsState = await loadJson(SHORTS_STATE_FILE, { processed: [], records: [], deadVideos: [] });
  shortsState.processed = Array.from(new Set([...(shortsState.processed || []), sourceVideoId]));
  shortsState.records = (shortsState.records || []).concat([{ sourceVideoId, shortsVideoId, shortsUrl, title: snippet.title, uploadedAt: new Date().toISOString() }]);
  shortsState.lastUpload = { sourceVideoId, shortsVideoId, shortsUrl, at: new Date().toISOString() };
  await saveJson(SHORTS_STATE_FILE, shortsState);
  try { await fs.unlink(srcPath); } catch {}
  try { await fs.unlink(outPath); } catch {}
  console.log('[shorts] DONE');
}

main().catch((e) => {
  console.error('[shorts] FAILED:', e);
  process.exit(1);
});
