#!/usr/bin/env node
/**
 * _upload_audio_drama.mjs
 * 音声ドラマ専用 upload。短尺 OK (ffprobe duration check なし)。
 *
 * Usage:
 *   node scripts/_upload_audio_drama.mjs --spec youtube/audio_drama/scripts/history_001.json
 */
import fs from 'node:fs';
import path from 'node:path';
import { google } from 'googleapis';

const ROOT = process.cwd();
const envPath = path.join(ROOT, '.env');
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
    const m = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}

const argv = process.argv.slice(2);
let specPath = null;
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--spec' && argv[i + 1]) specPath = argv[++i];
}
if (!specPath) {
  console.error('--spec required');
  process.exit(2);
}

const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
const title = (spec.title || '').trim();
if (!title) { console.error('empty title'); process.exit(2); }

const kind = spec.kind || 'history';
const cfg = {
  history: { oauth: 'samurai', categoryId: '22', dir: 'audio_drama' },
  otona:   { oauth: 'otona',   categoryId: '27', dir: 'audio_drama' },
}[kind];

const idx = path.basename(specPath, '.json'); // e.g. history_001
const workDir = path.join(ROOT, 'youtube', 'audio_drama', '.work', idx);
const mp4 = path.join(workDir, 'output.mp4');
if (!fs.existsSync(mp4)) {
  console.error(`mp4 not found: ${mp4}`);
  process.exit(1);
}

// OAuth
const clientId = process.env.YOUTUBE_CLIENT_ID;
const clientSec = process.env.YOUTUBE_CLIENT_SECRET;
const refresh = cfg.oauth === 'samurai'
  ? process.env.YOUTUBE_REFRESH_TOKEN
  : process.env.OTONA_YOUTUBE_REFRESH_TOKEN;
if (!clientId || !clientSec || !refresh) {
  console.error('missing OAuth env');
  process.exit(2);
}
const oa = new google.auth.OAuth2(clientId, clientSec);
oa.setCredentials({ refresh_token: refresh });
const youtube = google.youtube({ version: 'v3', auth: oa });

// 2026-05-30: 内部実装言及禁止 (memory: description-no-internal-impl)
// fallback も「本編訴求のみ」、edge-tts / 試作 / 後日公開等は絶対書かない
const description = (spec.description || title).slice(0, 4500);
const tags = (spec.tags || ['音声ドラマ', '日本史']).slice(0, 15);

console.log(`[audio_drama] uploading ${idx} (${kind}): ${title}`);
console.log(`  mp4: ${mp4} (${(fs.statSync(mp4).size / 1024 / 1024).toFixed(1)}MB)`);

try {
  const res = await youtube.videos.insert({
    part: ['snippet', 'status'],
    requestBody: {
      snippet: {
        title: title.slice(0, 95),
        description,
        tags,
        categoryId: cfg.categoryId,
        defaultLanguage: 'ja',
        defaultAudioLanguage: 'ja',
      },
      status: {
        privacyStatus: 'public',
        selfDeclaredMadeForKids: false,
        madeForKids: false,
      },
    },
    media: { body: fs.createReadStream(mp4) },
  }, { maxBodyLength: 2 * 1024 * 1024 * 1024 });

  const vid = res.data?.id;
  if (!vid) { console.error('no videoId'); process.exit(1); }
  const url = `https://youtube.com/watch?v=${vid}`;
  console.log(`[audio_drama] ${idx} -> ${url}`);

  // 専用 uploaded.json に記録
  const upPath = path.join(ROOT, 'youtube', 'audio_drama', 'uploaded.json');
  let db = {};
  if (fs.existsSync(upPath)) try { db = JSON.parse(fs.readFileSync(upPath, 'utf8')); } catch {}
  db[idx] = { videoId: vid, videoUrl: url, title, kind, uploadedAt: new Date().toISOString() };
  fs.writeFileSync(upPath, JSON.stringify(db, null, 2), 'utf8');
  console.log(`[audio_drama] uploaded.json updated`);
} catch (e) {
  console.error(`[audio_drama] FAIL: ${e?.message || e}`);
  process.exit(1);
}
