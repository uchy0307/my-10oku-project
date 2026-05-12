// youtube/scripts/upload_youtube.mjs
// YouTube Data API v3（googleapis）で動画をアップロードする本実装。
//
// env:
//   YOUTUBE_CLIENT_ID
//   YOUTUBE_CLIENT_SECRET
//   YOUTUBE_REFRESH_TOKEN
//
// 入力: youtube/output/<id>_video.mp4 + <id>_meta.json
// 出力: youtube/output/<id>_uploaded.json （videoId, url, snippet）
// state.json も更新。

import fs from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

const {
  YOUTUBE_CLIENT_ID,
  YOUTUBE_CLIENT_SECRET,
  YOUTUBE_REFRESH_TOKEN,
} = process.env;

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

function buildOauthClient() {
  if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) {
    return null;
  }
  const oauth2 = new google.auth.OAuth2(
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    'urn:ietf:wg:oauth:2.0:oob',
  );
  oauth2.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
  return oauth2;
}

async function uploadVideo(youtube, videoPath, meta) {
  console.log(`[upload_youtube] resumable upload 開始: ${videoPath}`);
  const stat = await fs.stat(videoPath);
  console.log(`[upload_youtube] file size: ${stat.size} bytes`);

  const res = await youtube.videos.insert(
    {
      part: ['snippet', 'status'],
      requestBody: {
        snippet: {
          title: meta.title,
          description: meta.description,
          tags: meta.tags || [],
          categoryId: meta.categoryId || '27',
          defaultLanguage: meta.defaultLanguage || 'ja',
          defaultAudioLanguage: meta.defaultLanguage || 'ja',
        },
        status: {
          privacyStatus: meta.privacyStatus || 'public',
          selfDeclaredMadeForKids: !!meta.madeForKids,
        },
      },
      media: {
        body: createReadStream(videoPath),
      },
    },
    {
      // resumable upload: googleapis が自動で扱う
      onUploadProgress: (evt) => {
        const pct = stat.size ? Math.round((evt.bytesRead / stat.size) * 100) : 0;
        process.stdout.write(`\r[upload_youtube] progress: ${pct}% (${evt.bytesRead}/${stat.size})`);
      },
    },
  );
  process.stdout.write('\n');
  return res.data;
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
  const uploadedPath = path.join(OUTPUT_DIR, `${topic.id}_uploaded.json`);

  if (!(await fileExists(videoPath))) {
    throw new Error(`Video file not found: ${videoPath}`);
  }
  if (!(await fileExists(metaPath))) {
    throw new Error(`Meta file not found: ${metaPath}`);
  }

  const meta = JSON.parse(await fs.readFile(metaPath, 'utf-8'));

  const oauth = buildOauthClient();
  if (!oauth) {
    console.warn('[upload_youtube] OAuth 資格情報が未設定。アップロードをスキップ。');
    state.lastUploadResult = { status: 'skipped_no_credentials', topicId: topic.id };
    state.lastUploadAt = new Date().toISOString();
    await saveState(state);
    return;
  }

  const youtube = google.youtube({ version: 'v3', auth: oauth });

  console.log(`[upload_youtube] Uploading [${topic.id}] ${meta.title}`);
  const result = await uploadVideo(youtube, videoPath, meta);
  const videoId = result.id;
  const url = `https://www.youtube.com/watch?v=${videoId}`;
  console.log(`[upload_youtube] SUCCESS. videoId=${videoId} url=${url}`);

  const uploadedRecord = {
    topicId: topic.id,
    videoId,
    url,
    title: meta.title,
    privacyStatus: meta.privacyStatus,
    uploadedAt: new Date().toISOString(),
    raw: {
      kind: result.kind,
      etag: result.etag,
    },
  };
  await fs.writeFile(uploadedPath, JSON.stringify(uploadedRecord, null, 2), 'utf-8');
  console.log(`[upload_youtube] record: ${uploadedPath}`);

  state.processed = state.processed || [];
  if (!state.processed.includes(topic.id)) state.processed.push(topic.id);
  state.lastUploadResult = {
    status: 'success',
    topicId: topic.id,
    videoId,
    url,
  };
  state.lastUploadAt = new Date().toISOString();
  state.currentTopic = null;
  await saveState(state);
}

main().catch((err) => {
  console.error('[upload_youtube] FAILED:', err);
  process.exit(1);
});
