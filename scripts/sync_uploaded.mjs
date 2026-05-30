#!/usr/bin/env node
/**
 * scripts/sync_uploaded.mjs
 *
 * YouTube API で各チャンネルの全アップ動画を取得し、
 * 対応する scripts/*.json のタイトルとマッチング → uploaded.json を構築。
 *
 * 4 チャンネル:
 *   - history_v2  (YOUTUBE_REFRESH_TOKEN, 歴史長尺)
 *   - shorts_v2   (YOUTUBE_REFRESH_TOKEN, 歴史ショート)
 *   - psych_v2    (OTONA_YOUTUBE_REFRESH_TOKEN, 大人長尺)
 *   - otona_shorts_v2 (OTONA_YOUTUBE_REFRESH_TOKEN, 大人ショート)
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');

// .env 読み込み
const envPath = path.join(PROJECT_ROOT, '.env');
const env = {};
if (fs.existsSync(envPath)) {
  const text = fs.readFileSync(envPath, 'utf8');
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}
for (const k of Object.keys(env)) process.env[k] = process.env[k] || env[k];

function oauthClient(refreshToken) {
  const clientId = process.env.YOUTUBE_CLIENT_ID || process.env.OTONA_YOUTUBE_CLIENT_ID;
  const clientSecret = process.env.YOUTUBE_CLIENT_SECRET || process.env.OTONA_YOUTUBE_CLIENT_SECRET;
  if (!clientId || !clientSecret || !refreshToken) {
    throw new Error('missing OAuth credentials in .env');
  }
  const oa = new google.auth.OAuth2(clientId, clientSecret);
  oa.setCredentials({ refresh_token: refreshToken });
  return oa;
}

function normalize(s) {
  return (s || '')
    .toString()
    .replace(/\s+/g, '')
    .replace(/[「」『』【】（）\(\)\[\]、,。\.！\!？\?〜~ー\-—–　]/g, '')
    .toLowerCase();
}

async function listAllUploads(yt) {
  // 1. channels.list mine=true で uploads playlist id 取得
  const ch = await yt.channels.list({ part: ['contentDetails'], mine: true });
  const playlistId = ch.data?.items?.[0]?.contentDetails?.relatedPlaylists?.uploads;
  if (!playlistId) throw new Error('uploads playlist not found');
  const items = [];
  let pageToken;
  do {
    const r = await yt.playlistItems.list({
      part: ['snippet'],
      playlistId,
      maxResults: 50,
      pageToken,
    });
    for (const it of (r.data?.items || [])) {
      items.push({
        videoId: it.snippet?.resourceId?.videoId,
        title: it.snippet?.title || '',
        publishedAt: it.snippet?.publishedAt || '',
      });
    }
    pageToken = r.data?.nextPageToken;
  } while (pageToken);
  return items;
}

async function syncChannel(channelDir, scriptGlobPrefix, refreshToken, label) {
  const root = path.join(PROJECT_ROOT, 'youtube', channelDir);
  const scriptsDir = path.join(root, 'scripts');
  const uploadedFile = path.join(root, 'uploaded.json');
  if (!fs.existsSync(scriptsDir)) {
    console.log(`[${label}] scripts dir not found, skip`);
    return;
  }
  // ローカル scripts/*.json title→idx マップ
  const localTitleToIdx = new Map();
  for (const f of fs.readdirSync(scriptsDir).filter(x => x.endsWith('.json'))) {
    let idx;
    const m = f.match(/^(?:long_|psych_|short_|)(\d{3})\.json$/);
    if (m) idx = m[1];
    if (!idx) continue;
    try {
      const j = JSON.parse(fs.readFileSync(path.join(scriptsDir, f), 'utf8'));
      const t = (j.title || '').trim();
      if (t) localTitleToIdx.set(normalize(t), { idx, rawTitle: t });
    } catch {}
  }

  console.log(`[${label}] local scripts: ${localTitleToIdx.size}`);

  // YouTube API
  const oa = oauthClient(refreshToken);
  const yt = google.youtube({ version: 'v3', auth: oa });
  let uploaded;
  try {
    uploaded = await listAllUploads(yt);
  } catch (e) {
    console.error(`[${label}] uploads fetch failed: ${e?.message || e}`);
    return;
  }
  console.log(`[${label}] YouTube uploaded count: ${uploaded.length}`);

  // 突合
  const db = {};
  const matchedByIdx = new Map();
  for (const v of uploaded) {
    const hit = localTitleToIdx.get(normalize(v.title));
    if (!hit) continue;
    if (!matchedByIdx.has(hit.idx)) matchedByIdx.set(hit.idx, []);
    matchedByIdx.get(hit.idx).push(v);
  }

  let dupSummary = [];
  for (const [idx, vids] of matchedByIdx) {
    db[idx] = {
      videoId: vids[0].videoId,
      videoUrl: `https://youtube.com/watch?v=${vids[0].videoId}`,
      title: vids[0].title,
      uploadedAt: vids[0].publishedAt,
    };
    if (vids.length > 1) {
      db[idx].duplicates = vids.slice(1).map(v => ({
        videoId: v.videoId,
        title: v.title,
        publishedAt: v.publishedAt,
      }));
      dupSummary.push({ idx, title: vids[0].title, count: vids.length });
    }
  }

  fs.writeFileSync(uploadedFile, JSON.stringify(db, null, 2), 'utf8');
  console.log(`[${label}] uploaded.json written. matched_idx=${Object.keys(db).length} duplicates_found=${dupSummary.length}`);
  if (dupSummary.length > 0) {
    console.log(`[${label}] 重複動画リスト:`);
    for (const d of dupSummary) {
      console.log(`  idx=${d.idx}  count=${d.count}  title="${d.title}"`);
    }
  }
  return { label, total: uploaded.length, matched: Object.keys(db).length, duplicates: dupSummary };
}

async function main() {
  const reports = [];
  const samurai = process.env.YOUTUBE_REFRESH_TOKEN;
  const otona = process.env.OTONA_YOUTUBE_REFRESH_TOKEN;

  if (samurai) {
    reports.push(await syncChannel('history_v2', 'long_', samurai, 'history_v2'));
    reports.push(await syncChannel('shorts_v2', 'short_', samurai, 'shorts_v2'));
  } else {
    console.error('YOUTUBE_REFRESH_TOKEN missing — skip samurai channel');
  }
  if (otona) {
    reports.push(await syncChannel('psych_v2', 'psych_', otona, 'psych_v2'));
    reports.push(await syncChannel('otona_shorts_v2', 'short_', otona, 'otona_shorts_v2'));
  } else {
    console.error('OTONA_YOUTUBE_REFRESH_TOKEN missing — skip otona channel');
  }

  console.log('\n=== SUMMARY ===');
  for (const r of reports) {
    if (!r) continue;
    console.log(`${r.label}: youtube=${r.total} matched=${r.matched} duplicates=${r.duplicates.length}`);
  }

  // 2026-05-30 (Task #13): uploaded_titles.json 集約出力 (title_dedup_check 用 DB)
  const allTitles = [];
  for (const sub of ['history_v2', 'shorts_v2', 'psych_v2', 'otona_shorts_v2', 'history_shorts_v2', 'psych_shorts_v2']) {
    const up = path.join(PROJECT_ROOT, 'youtube', sub, 'uploaded.json');
    if (!fs.existsSync(up)) continue;
    try {
      const db = JSON.parse(fs.readFileSync(up, 'utf8'));
      for (const [idx, v] of Object.entries(db)) {
        if (v?.title) allTitles.push({ channel: sub, idx, title: v.title, videoId: v.videoId });
      }
    } catch {}
  }
  const aggregatedPath = path.join(PROJECT_ROOT, 'youtube', 'uploaded_titles.json');
  fs.writeFileSync(aggregatedPath, JSON.stringify({ updatedAt: new Date().toISOString(), count: allTitles.length, titles: allTitles }, null, 2), 'utf8');
  console.log(`\n[aggregated] uploaded_titles.json written (${allTitles.length} titles) → ${aggregatedPath}`);
}

main().catch(e => {
  console.error('FATAL:', e?.message || e);
  process.exit(1);
});
