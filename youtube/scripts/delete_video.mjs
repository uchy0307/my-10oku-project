#!/usr/bin/env node
// youtube/scripts/delete_video.mjs
// Delete a YouTube video by ID using OAuth refresh token.

import { google } from 'googleapis';

const VIDEO_ID = process.env.VIDEO_ID;
const { YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN } = process.env;

if (!VIDEO_ID) { console.error('VIDEO_ID env var required'); process.exit(1); }

const auth = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET);
auth.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
const youtube = google.youtube({ version: 'v3', auth });

try {
  await youtube.videos.delete({ id: VIDEO_ID });
  console.log(`[delete_video] deleted: ${VIDEO_ID}`);
} catch (e) {
  console.error(`[delete_video] failed: ${e.message}`);
  process.exit(1);
}
