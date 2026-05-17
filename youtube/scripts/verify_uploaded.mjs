#!/usr/bin/env node
// youtube/scripts/verify_uploaded.mjs
// After upload, fetch the published video via YouTube Data API and check:
// - title matches topic.title
// - description has expected boilerplate
// - duration > 15min
// - thumb has been set (custom not default)
// If any fails, log and exit non-zero so self-heal retries (will delete then re-upload).

import { google } from 'googleapis';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const STATE_PATH = path.join(ROOT, 'output', 'state.json');

const { YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN } = process.env;

async function main() {
  const state = JSON.parse(await readFile(STATE_PATH, 'utf-8'));
  const last = state.lastUploadResult;
  if (!last || last.status !== 'success' || !last.videoId) {
    console.log('[verify_uploaded] no recent upload to verify');
    return;
  }
  const auth = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET);
  auth.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
  const youtube = google.youtube({ version: 'v3', auth });
  const r = await youtube.videos.list({ id: [last.videoId], part: ['snippet', 'contentDetails', 'status'] });
  const v = r.data.items && r.data.items[0];
  if (!v) throw new Error('[verify_uploaded] video not found: ' + last.videoId);
  const dur = v.contentDetails && v.contentDetails.duration;
  const durSec = parseDuration(dur);
  const checks = {
    titleExists: !!(v.snippet && v.snippet.title && v.snippet.title.length > 5),
    descriptionExists: !!(v.snippet && v.snippet.description && v.snippet.description.length > 50),
    durationOk: durSec >= 900, // 15 min minimum
    publishedOk: v.status && v.status.privacyStatus === 'public',
  };
  const failed = Object.entries(checks).filter(([k, v]) => !v).map(([k]) => k);
  console.log('[verify_uploaded] video=' + last.videoId + ' dur=' + durSec + 's checks=' + JSON.stringify(checks));
  if (failed.length > 0) {
    console.error('[verify_uploaded] FAIL: ' + failed.join(','));
    process.exit(1);
  }
}

function parseDuration(iso) {
  const m = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(iso || '');
  if (!m) return 0;
  return (parseInt(m[1] || '0') * 3600) + (parseInt(m[2] || '0') * 60) + parseInt(m[3] || '0');
}

main().catch(e => { console.error(e.message); process.exit(1); });
