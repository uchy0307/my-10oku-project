#!/usr/bin/env node
// scripts/batch_update_descriptions.mjs
// 今日アップした全動画の description を新テンプレートに更新
// Usage: node scripts/batch_update_descriptions.mjs

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';
import { buildDescription } from './build_description.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

// Load .env
let envTxt = fs.readFileSync(path.join(ROOT, '.env'), 'utf8');
if (envTxt.charCodeAt(0) === 0xFEFF) envTxt = envTxt.slice(1);
for (const line of envTxt.split(/\r?\n/)) {
  if (!line || line.startsWith('#') || !line.includes('=')) continue;
  const [k, ...rest] = line.split('=');
  if (!process.env[k.trim()]) process.env[k.trim()] = rest.join('=').trim();
}

const cid = process.env.YOUTUBE_CLIENT_ID;
const csec = process.env.YOUTUBE_CLIENT_SECRET;

async function getYoutube(tokenEnv) {
  const oauth2 = new google.auth.OAuth2(cid, csec);
  oauth2.setCredentials({ refresh_token: process.env[tokenEnv] });
  return google.youtube({ version: 'v3', auth: oauth2 });
}

// Map video title (or substring) → script JSON path
function findScriptFor(title, kind) {
  const dirs = {
    history: { dir: path.join(ROOT, 'youtube', 'history_v2', 'scripts'), prefix: 'long_' },
    psych:   { dir: path.join(ROOT, 'youtube', 'psych_v2', 'scripts'),   prefix: 'psych_' },
    shorts:  { dir: path.join(ROOT, 'youtube', 'shorts_v2', 'scripts'),  prefix: 'short_' },
    otona_shorts: { dir: path.join(ROOT, 'youtube', 'otona_shorts_v2', 'scripts'), prefix: 'short_' },
  }[kind];
  if (!dirs || !fs.existsSync(dirs.dir)) return null;
  const cleanTitle = title.replace(/\s*\(\d+\/\d+再\)$/, '').replace(/\s*#Shorts\s*$/i, '').trim();
  for (const f of fs.readdirSync(dirs.dir)) {
    if (!f.endsWith('.json')) continue;
    try {
      const sp = JSON.parse(fs.readFileSync(path.join(dirs.dir, f), 'utf8'));
      const t = (sp.title || '').replace(/\s*#Shorts\s*$/i, '').trim();
      if (t && (t === cleanTitle || cleanTitle.includes(t.slice(0, 15)) || t.includes(cleanTitle.slice(0, 15)))) {
        return { path: path.join(dirs.dir, f), spec: sp };
      }
    } catch {}
  }
  return null;
}

const channels = [
  { tokenEnv: 'YOUTUBE_REFRESH_TOKEN', name: '歴史侍', longKind: 'history', shortsKind: 'shorts' },
  { tokenEnv: 'OTONA_YOUTUBE_REFRESH_TOKEN', name: '大人', longKind: 'psych', shortsKind: 'otona_shorts' },
];

const todayCutoff = new Date();
todayCutoff.setHours(0, 0, 0, 0);  // local midnight
const dayAgo = new Date(todayCutoff.getTime() - 9 * 3600 * 1000);  // approximate JST 00:00 in UTC

let totalUpdated = 0;
let totalFailed = 0;

for (const ch of channels) {
  if (!process.env[ch.tokenEnv]) {
    console.log(`[skip] ${ch.name}: ${ch.tokenEnv} not set`);
    continue;
  }
  console.log(`\n=== ${ch.name} channel ===`);
  const yt = await getYoutube(ch.tokenEnv);
  const chRes = await yt.channels.list({ part: ['contentDetails'], mine: true });
  const upl = chRes.data.items[0].contentDetails.relatedPlaylists.uploads;
  const items = await yt.playlistItems.list({ part: ['snippet'], playlistId: upl, maxResults: 25 });
  const todayVideos = (items.data.items || []).filter(it => {
    const pub = new Date(it.snippet.publishedAt);
    return pub >= dayAgo;
  });
  console.log(`  today uploads: ${todayVideos.length}`);
  for (const it of todayVideos) {
    const vid = it.snippet.resourceId.videoId;
    const title = it.snippet.title;
    const isShorts = title.includes('#Shorts') || title.includes('#shorts');
    const kind = isShorts ? ch.shortsKind : ch.longKind;
    const match = findScriptFor(title, kind);
    if (!match) {
      console.log(`  [SKIP] ${vid} - script not found: ${title.slice(0, 40)}`);
      totalFailed++;
      continue;
    }
    // Get current video for duration
    const vinfo = await yt.videos.list({ part: ['contentDetails'], id: [vid] });
    const dur = vinfo.data.items[0]?.contentDetails?.duration || 'PT0S';
    const durSec = (() => {
      const m = dur.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
      return (parseInt(m[1] || 0) * 3600) + (parseInt(m[2] || 0) * 60) + parseInt(m[3] || 0);
    })();
    const newDesc = buildDescription({
      kind,
      spec: match.spec,
      audioDur: durSec,
    });
    try {
      await yt.videos.update({
        part: ['snippet'],
        requestBody: {
          id: vid,
          snippet: {
            title,
            description: newDesc,
            tags: it.snippet.tags || match.spec.tags || [],
            categoryId: isShorts ? '22' : '27',
          },
        },
      });
      console.log(`  ✓ ${vid} | ${title.slice(0, 40)} (desc: ${newDesc.length} chars)`);
      totalUpdated++;
    } catch (e) {
      console.log(`  ❌ ${vid} | ${e?.message || e}`);
      totalFailed++;
    }
  }
}
console.log(`\n=== DONE: updated=${totalUpdated} failed=${totalFailed} ===`);
