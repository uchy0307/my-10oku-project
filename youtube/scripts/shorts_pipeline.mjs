// youtube/scripts/shorts_pipeline.mjs
// 60秒 YouTube Shorts を既存 long video から生成→upload。
// 入力: state.json から最新 uploaded videoId / topicId を取得
// 工程: yt-dlp で source 取得 → ffmpeg で 60s × 1080x1920 縦長 crop → YouTube upload as Shorts
//
// env: YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
//      YOUTUBE_PLAYLIST_ALL_ID (optional)
//      SHORTS_VIDEO_ID (optional: workflow_dispatch input。空なら state.json から最新)
//      SHORTS_CLIP_START (optional: 秒, default 30)
//      SHORTS_CLIP_DURATION (optional: 秒, default 58)

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
const CLIP_DURATION = Math.min(Number(SHORTS_CLIP_DURATION || 58), 59); // 60s 厳守

function run(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    console.log('[run]', cmd, args.join(' '));
    const p = spawn(cmd, args, { stdio: 'inherit', ...opts });
    p.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`${cmd} exit ${code}`))));
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

async function pickSourceVideoId() {
  if (SHORTS_VIDEO_ID && SHORTS_VIDEO_ID.trim()) return SHORTS_VIDEO_ID.trim();
  const state = await loadJson(STATE_FILE, {});
  const shortsState = await loadJson(SHORTS_STATE_FILE, { processed: [] });
  // candidates: state.processed[] uploaded video IDs。state.processed is topicIds, not videoIds.
  // 過去 uploaded record から videoId を逆引き
  // 最新の lastUploadResult.videoId が未 short 化なら採用
  const last = state.lastUploadResult;
  if (last && last.status === 'success' && last.videoId && !shortsState.processed.includes(last.videoId)) {
    return last.videoId;
  }
  // フォールバック: youtube/output/*_uploaded.json を全探索
  const files = (await fs.readdir(OUTPUT_DIR)).filter((f) => f.endsWith('_uploaded.json'));
  const records = [];
  for (const f of files) {
    try {
      const r = JSON.parse(await fs.readFile(path.join(OUTPUT_DIR, f), 'utf-8'));
      if (r.videoId && !shortsState.processed.includes(r.videoId)) {
        records.push({ ...r, file: f });
      }
    } catch {}
  }
  records.sort((a, b) => (b.uploadedAt || '').localeCompare(a.uploadedAt || ''));
  if (records.length === 0) throw new Error('No un-shortified video found in state / uploaded records');
  return records[0].videoId;
}

async function fetchVideoMeta(youtube, videoId) {
  const r = await youtube.videos.list({ part: ['snippet'], id: [videoId] });
  const item = (r.data.items || [])[0];
  if (!item) throw new Error(`Video ${videoId} not found on YouTube`);
  return item.snippet;
}

async function downloadSource(videoId, dest) {
  // yt-dlp で 720p 以下の mp4
  await run('yt-dlp', [
    '-f', 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
    '-o', dest,
    '--merge-output-format', 'mp4',
    `https://www.youtube.com/watch?v=${videoId}`,
  ]);
}

async function makeShortsVideo(srcPath, outPath) {
  // 中央 vertical crop + clip
  // 入力: 16:9 (1920x1080) と想定
  // 出力: 1080x1920, 60s 以内
  // crop: 中央の 9:16 領域。w_in*9/16 -> w_out = h_in*9/16
  // for 1920x1080: crop=608:1080 then scale=1080:1920? いや、aspect 9:16 縦長は 1080x1920
  // 16:9 source from 1080 height → take center 608x1080 → scale to 1080x1920
  const vf = "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920,setsar=1";
  await run('ffmpeg', [
    '-y',
    '-ss', String(CLIP_START),
    '-i', srcPath,
    '-t', String(CLIP_DURATION),
    '-vf', vf,
    '-c:v', 'libx264',
    '-preset', 'medium',
    '-crf', '23',
    '-pix_fmt', 'yuv420p',
    '-c:a', 'aac',
    '-b:a', '128k',
    '-movflags', '+faststart',
    outPath,
  ]);
}

async function uploadShorts(youtube, videoPath, snippet, sourceVideoId) {
  const baseTitle = (snippet.title || 'Shorts').slice(0, 80);
  const title = `${baseTitle} #Shorts`.slice(0, 100);
  const description = `${snippet.description || ''}

──
本編: https://www.youtube.com/watch?v=${sourceVideoId}
#Shorts #日本史 #侍 #samurai`.slice(0, 4900);
  const tags = (snippet.tags || []).concat(['Shorts', '日本史', '侍', 'samurai']).slice(0, 30);

  const stat = await fs.stat(videoPath);
  console.log(`[upload] size=${stat.size} bytes title="${title}"`);

  const res = await youtube.videos.insert(
    {
      part: ['snippet', 'status'],
      requestBody: {
        snippet: {
          title,
          description,
          tags,
          categoryId: snippet.categoryId || '27',
          defaultLanguage: 'ja',
          defaultAudioLanguage: 'ja',
        },
        status: { privacyStatus: 'public', selfDeclaredMadeForKids: false },
      },
      media: { body: createReadStream(videoPath) },
    },
    {
      onUploadProgress: (evt) => {
        const pct = stat.size ? Math.round((evt.bytesRead / stat.size) * 100) : 0;
        process.stdout.write(`\r[upload] ${pct}%`);
      },
    },
  );
  process.stdout.write('\n');
  return res.data;
}

async function main() {
  const oauth = buildOauth();
  if (!oauth) throw new Error('OAuth env missing (YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN)');
  const youtube = google.youtube({ version: 'v3', auth: oauth });

  const sourceVideoId = await pickSourceVideoId();
  console.log(`[shorts] source videoId = ${sourceVideoId}`);

  const snippet = await fetchVideoMeta(youtube, sourceVideoId);
  console.log(`[shorts] source title = "${snippet.title}"`);

  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const srcPath = path.join(OUTPUT_DIR, `shorts_src_${sourceVideoId}.mp4`);
  const outPath = path.join(OUTPUT_DIR, `shorts_${sourceVideoId}.mp4`);

  await downloadSource(sourceVideoId, srcPath);
  await makeShortsVideo(srcPath, outPath);

  const result = await uploadShorts(youtube, outPath, snippet, sourceVideoId);
  const shortsVideoId = result.id;
  const shortsUrl = `https://www.youtube.com/shorts/${shortsVideoId}`;
  console.log(`[shorts] uploaded videoId=${shortsVideoId} url=${shortsUrl}`);

  // playlist add (optional)
  if (YOUTUBE_PLAYLIST_ALL_ID) {
    try {
      await youtube.playlistItems.insert({
        part: ['snippet'],
        requestBody: {
          snippet: { playlistId: YOUTUBE_PLAYLIST_ALL_ID, resourceId: { kind: 'youtube#video', videoId: shortsVideoId } },
        },
      });
      console.log('[shorts] playlist add OK');
    } catch (e) {
      console.warn('[shorts] playlist add failed (non-fatal):', e.message);
    }
  }

  // shorts_state.json 更新
  const shortsState = await loadJson(SHORTS_STATE_FILE, { processed: [], records: [] });
  shortsState.processed = Array.from(new Set([...(shortsState.processed || []), sourceVideoId]));
  shortsState.records = (shortsState.records || []).concat([{
    sourceVideoId,
    shortsVideoId,
    shortsUrl,
    title: snippet.title,
    uploadedAt: new Date().toISOString(),
  }]);
  shortsState.lastUpload = { sourceVideoId, shortsVideoId, shortsUrl, at: new Date().toISOString() };
  await saveJson(SHORTS_STATE_FILE, shortsState);

  // tmp ファイルは大きいので削除
  try { await fs.unlink(srcPath); } catch {}
  try { await fs.unlink(outPath); } catch {}

  console.log('[shorts] DONE');
}

main().catch((e) => {
  console.error('[shorts] FAILED:', e);
  process.exit(1);
});
