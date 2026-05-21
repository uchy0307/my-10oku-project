#!/usr/bin/env node
/**
 * youtube/history_v2/scripts/retro_thumbs_apply.mjs
 *
 * Re-generate yellow/red thumbnails for already-uploaded history_v2 videos
 * and apply them via youtube.thumbnails().set.
 *
 * Inputs (env):
 *   VIDEO_IDS   comma-sep YouTube video IDs (in order)
 *   SCRIPT_IDS  comma-sep matching script IDs (e.g. "001,002,003")
 *   YOUTUBE_CLIENT_ID
 *   YOUTUBE_CLIENT_SECRET
 *   YOUTUBE_REFRESH_TOKEN
 *
 * For each (vid, sid) pair:
 *   1. Load youtube/history_v2/scripts/long_<sid>.json â title, image_urls[0] (hero)
 *   2. Download hero image (Wikimedia)
 *   3. Run make_thumb.py to produce yellow/red thumbnail
 *   4. youtube.thumbnails().set({ videoId: vid, media_body: thumb })
 *   5. Log result
 *
 * Does NOT re-upload video. Does NOT touch any other metadata. Thumbnail only.
 */
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync, execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { google } from 'googleapis';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

function log(m) { console.log(`[retro_thumbs] ${m}`); }
function fail(m, code = 1) {
  console.error(`[retro_thumbs][FATAL] ${m}`);
  process.exit(code);
}

const { YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, VIDEO_IDS, SCRIPT_IDS } = process.env;
if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) {
  fail('YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN required', 2);
}
if (!VIDEO_IDS || !SCRIPT_IDS) fail('VIDEO_IDS and SCRIPT_IDS env vars required');

const vids = VIDEO_IDS.split(',').map(s => s.trim()).filter(Boolean);
const sids = SCRIPT_IDS.split(',').map(s => s.trim()).filter(Boolean);
if (vids.length !== sids.length) fail(`VIDEO_IDS (${vids.length}) and SCRIPT_IDS (${sids.length}) length mismatch`);
if (vids.length === 0) fail('empty input');

const WORK = path.join(ROOT, '.work_retro');
fs.mkdirSync(WORK, { recursive: true });

const WIKI_UA = '10oku-history-bot/1.0 (https://github.com/uchy0307/my-10oku-project; uchiyamatakayuki0307@gmail.com) node-fetch';
async function fetchHero(url, dst) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(url, {
        headers: {
          'User-Agent': WIKI_UA,
          'Accept': 'image/*,*/*;q=0.8',
        },
        redirect: 'follow',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const buf = Buffer.from(await res.arrayBuffer());
      if (buf.length < 3000) throw new Error(`too small ${buf.length}B`);
      fs.writeFileSync(dst, buf);
      return;
    } catch (e) {
      if (attempt === 2) throw e;
      await new Promise(r => setTimeout(r, 500 + attempt * 600));
    }
  }
}

const oauth2 = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET);
oauth2.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
const youtube = google.youtube({ version: 'v3', auth: oauth2 });

const results = [];

for (let i = 0; i < vids.length; i++) {
  const vid = vids[i];
  const sid = sids[i];
  const scriptPath = path.join(ROOT, 'scripts', `long_${sid}.json`);
  log(`[${i + 1}/${vids.length}] video=${vid} script=long_${sid}.json`);
  if (!fs.existsSync(scriptPath)) {
    console.error(`  script missing: ${scriptPath}`);
    results.push({ vid, sid, status: 'script_missing' });
    continue;
  }
  let spec;
  try {
    spec = JSON.parse(fs.readFileSync(scriptPath, 'utf8'));
  } catch (e) {
    console.error(`  script parse error: ${e.message}`);
    results.push({ vid, sid, status: 'script_parse_error' });
    continue;
  }
  const title = spec.title;
  const heroUrl = (spec.image_urls && spec.image_urls[0]) || null;
  if (!title) {
    results.push({ vid, sid, status: 'missing_title' });
    continue;
  }
  const heroJpg = path.join(WORK, `hero_${sid}.jpg`);
  let heroArg = [];
  if (heroUrl) {
    try {
      log(`  fetch hero ${heroUrl}`);
      await fetchHero(heroUrl, heroJpg);
      heroArg = ['--hero', heroJpg];
    } catch (e) {
      console.warn(`  hero fetch failed (${e.message}), continuing without hero`);
    }
  }
  const thumbPath = path.join(WORK, `thumb_${sid}.jpg`);
  const makeThumbPy = path.join(ROOT, 'scripts', 'make_thumb.py');
  const run = spawnSync('python3', [makeThumbPy, '--title', title, '--out', thumbPath, ...heroArg], { stdio: 'inherit' });
  if (run.status !== 0 || !fs.existsSync(thumbPath)) {
    results.push({ vid, sid, status: `thumb_gen_failed_status_${run.status}` });
    continue;
  }
  const thumbSize = fs.statSync(thumbPath).size;
  log(`  thumb generated: ${thumbPath} (${thumbSize}B)`);
  try {
    await youtube.thumbnails.set({
      videoId: vid,
      media: { mimeType: 'image/jpeg', body: fs.createReadStream(thumbPath) },
    });
    log(`  thumbnails.set OK for ${vid}`);
    results.push({ vid, sid, status: 'ok', size: thumbSize });
  } catch (e) {
    console.error(`  thumbnails.set failed: ${e.message}`);
    results.push({ vid, sid, status: 'api_error', error: e.message });
  }
  await new Promise(r => setTimeout(r, 2000));
}

console.log('\n[retro_thumbs] summary:');
for (const r of results) console.log(`  ${r.vid} (long_${r.sid}) -> ${r.status}${r.size ? ` ${r.size}B` : ''}`);
const okCount = results.filter(r => r.status === 'ok').length;
console.log(`[retro_thumbs] ${okCount}/${results.length} succeeded`);

// Write summary to GITHUB_OUTPUT if set
if (process.env.GITHUB_OUTPUT) {
  const summary = results.map(r => `${r.vid}=${r.status}`).join(';');
  fs.appendFileSync(process.env.GITHUB_OUTPUT, `summary=${summary}\nok_count=${okCount}\ntotal=${results.length}\n`);
}
process.exit(okCount === results.length ? 0 : 1);
