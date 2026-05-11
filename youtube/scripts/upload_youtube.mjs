// youtube/scripts/upload_youtube.mjs
// YouTube Data API v3 で動画アップロード（resumable upload）
// 現状はSTUB ─ 動画ファイル未生成のため「skip upload」モード
// ただし、state.json には投稿ジョブの記録を残し、ファイル生成後の本実装に備える

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fetch from 'node-fetch';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

const YOUTUBE_CLIENT_ID = process.env.YOUTUBE_CLIENT_ID;
const YOUTUBE_CLIENT_SECRET = process.env.YOUTUBE_CLIENT_SECRET;
const YOUTUBE_REFRESH_TOKEN = process.env.YOUTUBE_REFRESH_TOKEN;

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

async function saveState(state) {
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
}

async function fileExists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

// OAuth refresh token から access token を取得
async function refreshAccessToken() {
  if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) {
    return null;
  }
  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: YOUTUBE_CLIENT_ID,
      client_secret: YOUTUBE_CLIENT_SECRET,
      refresh_token: YOUTUBE_REFRESH_TOKEN,
      grant_type: 'refresh_token',
    }),
  });
  if (!res.ok) {
    throw new Error(`OAuth refresh failed: ${await res.text()}`);
  }
  const json = await res.json();
  return json.access_token;
}

// 本実装: 動画ファイルをYouTube Data API v3 にアップロード
async function uploadVideo(videoPath, meta, accessToken) {
  // 1) Resumable upload セッション初期化
  const initRes = await fetch(
    'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'X-Upload-Content-Type': 'video/mp4',
      },
      body: JSON.stringify({
        snippet: {
          title: meta.title,
          description: meta.description,
          tags: meta.tags,
          categoryId: meta.categoryId,
        },
        status: {
          privacyStatus: meta.privacyStatus,
          madeForKids: meta.madeForKids,
        },
      }),
    }
  );
  if (!initRes.ok) {
    throw new Error(`Upload init failed: ${await initRes.text()}`);
  }
  const uploadUrl = initRes.headers.get('Location');

  // 2) 動画本体をPUT
  const videoBuf = await fs.readFile(videoPath);
  const putRes = await fetch(uploadUrl, {
    method: 'PUT',
    headers: { 'Content-Type': 'video/mp4', 'Content-Length': videoBuf.length.toString() },
    body: videoBuf,
  });
  if (!putRes.ok) {
    throw new Error(`Upload PUT failed: ${await putRes.text()}`);
  }
  return await putRes.json();
}

async function main() {
  const state = await loadState();
  const topic = state.currentTopic;
  if (!topic) {
    console.log('[upload_youtube] No currentTopic. Skip.');
    return;
  }

  const videoPath = path.join(OUTPUT_DIR, `${topic.id}_video.mp4`);
  const metaPath = path.join(OUTPUT_DIR, `${topic.id}_meta.json`);

  const hasVideo = await fileExists(videoPath);
  const hasMeta = await fileExists(metaPath);

  if (!hasVideo) {
    console.log(`[upload_youtube] STUB MODE: video file not generated yet (${videoPath}).`);
    console.log('[upload_youtube] Recording upload job in state.json and skipping actual upload.');

    state.uploadQueue = state.uploadQueue || [];
    state.uploadQueue.push({
      topicId: topic.id,
      title: topic.title,
      queuedAt: new Date().toISOString(),
      reason: 'video_pending_compile',
    });
    // STUBモードでもサイクルを進めるため processed に追加
    state.processed = state.processed || [];
    if (!state.processed.includes(topic.id)) state.processed.push(topic.id);
    state.lastUploadResult = { status: 'skipped_stub', topicId: topic.id };
    state.lastUploadAt = new Date().toISOString();
    state.currentTopic = null;
    await saveState(state);
    return;
  }

  if (!hasMeta) {
    throw new Error(`Meta file not found: ${metaPath}`);
  }

  const meta = JSON.parse(await fs.readFile(metaPath, 'utf-8'));
  const accessToken = await refreshAccessToken();
  if (!accessToken) {
    console.warn('[upload_youtube] YouTube credentials missing — skipping actual upload.');
    state.lastUploadResult = { status: 'skipped_no_credentials', topicId: topic.id };
    await saveState(state);
    return;
  }

  console.log(`[upload_youtube] Uploading [${topic.id}] ${meta.title}`);
  const result = await uploadVideo(videoPath, meta, accessToken);
  console.log(`[upload_youtube] SUCCESS. videoId=${result.id}`);

  state.processed = state.processed || [];
  if (!state.processed.includes(topic.id)) state.processed.push(topic.id);
  state.lastUploadResult = { status: 'success', topicId: topic.id, videoId: result.id };
  state.lastUploadAt = new Date().toISOString();
  state.currentTopic = null;
  await saveState(state);
}

main().catch(err => {
  console.error('[upload_youtube] FAILED:', err);
  process.exit(1);
});
