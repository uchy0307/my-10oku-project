#!/usr/bin/env node
/**
 * upload_quarantine.mjs
 * =====================
 * .work_quarantine/<idx>/output.mp4 を直接 YouTube に upload する。
 * 動画再ビルドはしない。uploaded.json に既存なら skip.
 *
 * Usage:
 *   node scripts/upload_quarantine.mjs --kind otona_shorts --count 6
 *   --kind: history / psych / shorts / otona_shorts
 *   --count: 上限本数 (quota安全のため指定)
 */
import fs from 'node:fs';
import path from 'node:path';
import { google } from 'googleapis';

// ===== .env load =====
const ROOT = process.cwd();
const envPath = path.join(ROOT, '.env');
if (fs.existsSync(envPath)) {
  const txt = fs.readFileSync(envPath, 'utf8');
  for (const line of txt.split(/\r?\n/)) {
    const m = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}

// ===== args =====
// --kind=<>: history/psych/shorts/otona_shorts
// --count=<>: 上限本数 (default 3)
// --ids=009,016: 特定 idx 強制再投稿 (uploaded.json 既存でも投稿、 順序 ids 通り)
// --force: uploaded.json 既存 idx もスキップせず投稿
const args = { kind: null, count: 3, ids: null, force: false };
for (let i = 0; i < process.argv.slice(2).length; i++) {
  const a = process.argv.slice(2)[i];
  const mk = a.match(/^--kind=([a-z_]+)$/);
  if (mk) args.kind = mk[1];
  const mc = a.match(/^--count=(\d+)$/);
  if (mc) args.count = parseInt(mc[1]);
  const mi = a.match(/^--ids=(.+)$/);
  if (mi) args.ids = mi[1].split(',').map(s => s.trim()).filter(s => /^\d{3}(?:_(?:intro|peak|outro))?$/.test(s));
  if (a === '--force') args.force = true;
  if (a.startsWith('--kind') && !mk) args.kind = process.argv.slice(2)[i + 1];
  if (a.startsWith('--count') && !mc) args.count = parseInt(process.argv.slice(2)[i + 1]);
  if (a.startsWith('--ids') && !mi && process.argv.slice(2)[i + 1]) {
    args.ids = process.argv.slice(2)[i + 1].split(',').map(s => s.trim()).filter(s => /^\d{3}(?:_(?:intro|peak|outro))?$/.test(s));
  }
}

const CFG = {
  history:      { dir: 'history_v2',      scriptPrefix: 'long_',  oauth: 'samurai', shorts: false },
  psych:        { dir: 'psych_v2',        scriptPrefix: 'psych_', oauth: 'otona',   shorts: false },
  shorts:       { dir: 'shorts_v2',       scriptPrefix: 'short_', oauth: 'samurai', shorts: true },
  otona_shorts: { dir: 'otona_shorts_v2', scriptPrefix: 'short_', oauth: 'otona',   shorts: true },
};

if (!args.kind || !CFG[args.kind]) {
  console.error(`--kind required: ${Object.keys(CFG).join('|')}`);
  process.exit(2);
}
const cfg = CFG[args.kind];

// ===== OAuth =====
const clientId  = process.env.YOUTUBE_CLIENT_ID;
const clientSec = process.env.YOUTUBE_CLIENT_SECRET;
let refreshTok;
if (cfg.oauth === 'samurai') refreshTok = process.env.YOUTUBE_REFRESH_TOKEN;
else if (cfg.oauth === 'otona') refreshTok = process.env.OTONA_YOUTUBE_REFRESH_TOKEN || process.env.YOUTUBE_REFRESH_TOKEN;

if (!clientId || !clientSec || !refreshTok) {
  console.error('Missing OAuth env vars');
  process.exit(2);
}
const oauth2 = new google.auth.OAuth2(clientId, clientSec);
oauth2.setCredentials({ refresh_token: refreshTok });
const youtube = google.youtube({ version: 'v3', auth: oauth2 });

// ===== paths =====
const channelRoot  = path.join(ROOT, 'youtube', cfg.dir);
const quarantineDir = path.join(channelRoot, '.work_quarantine');
const workDir = path.join(channelRoot, '.work');
const scriptsDir   = path.join(channelRoot, 'scripts');
const uploadedJson = path.join(channelRoot, 'uploaded.json');

let uploadedDb = {};
if (fs.existsSync(uploadedJson)) {
  try { uploadedDb = JSON.parse(fs.readFileSync(uploadedJson, 'utf8')) || {}; } catch {}
}

// 2026-05-29 破損 mp4 対策: ffprobe で validity + duration 確認、valid な方を採用
import { execSync } from 'node:child_process';
function probeMp4(p) {
  try {
    const out = execSync(`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 ${JSON.stringify(p)}`, { stdio: ['pipe', 'pipe', 'pipe'] }).toString();
    const dur = parseFloat((out.match(/duration=(\S+)/) || [])[1] || '0');
    return { ok: dur > 0, duration: dur };
  } catch (e) {
    return { ok: false, duration: 0, err: (e?.message || '').slice(0, 80) };
  }
}

// quarantine と .work 両方探索 + ffprobe validity check
function collectFrom(baseDir) {
  if (!fs.existsSync(baseDir)) return [];
  return fs.readdirSync(baseDir, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => d.name)
    .filter(idx => /^\d{3}$/.test(idx))
    .filter(idx => fs.existsSync(path.join(baseDir, idx, 'output.mp4')))
    .map(idx => ({ idx, dir: path.join(baseDir, idx) }));
}
const minDuration = cfg.shorts ? 14 : 1500;   // shorts >= 14s, long >= 25min
const allRaw0 = [...collectFrom(quarantineDir), ...collectFrom(workDir)];
// --ids 指定時は filter、 未指定 + !force なら uploaded.json 既存 skip
const allRaw = args.ids
  ? allRaw0.filter(c => args.ids.includes(c.idx))
  : (args.force ? allRaw0 : allRaw0.filter(c => !uploadedDb[c.idx]));
if (args.ids) {
  console.log(`[upload_quarantine] --ids 指定: ${args.ids.join(',')} (uploaded.json 無視で強制投稿)`);
}
// idx ごとに ffprobe → valid + duration 大きい方を採用
const byIdx = {};
for (const c of allRaw) {
  const probe = probeMp4(path.join(c.dir, 'output.mp4'));
  if (!probe.ok || probe.duration < minDuration) {
    console.warn(`[upload_quarantine] INVALID mp4 ${c.idx} (${c.dir}): duration=${probe.duration.toFixed(1)}s err=${probe.err || ''}`);
    continue;
  }
  if (!byIdx[c.idx] || byIdx[c.idx].duration < probe.duration) {
    byIdx[c.idx] = { idx: c.idx, dir: c.dir, duration: probe.duration };
  }
}
// --ids 指定時は ids 順序維持、 通常は idx 昇順
let allCandidates;
if (args.ids) {
  allCandidates = args.ids
    .map(id => byIdx[id])
    .filter(Boolean);
} else {
  allCandidates = Object.values(byIdx).sort((a, b) => a.idx.localeCompare(b.idx));
}
const candidates = allCandidates.map(c => c.idx);
const candidateDirs = Object.fromEntries(allCandidates.map(c => [c.idx, c.dir]));

console.log(`[upload_quarantine] kind=${args.kind} candidates=${candidates.length} max=${args.count}`);
if (candidates.length === 0) {
  console.log('[upload_quarantine] no candidates to upload');
  process.exit(0);
}

let uploaded = 0;
const targets = candidates.slice(0, args.count);

for (const idx of targets) {
  const mp4 = path.join(candidateDirs[idx], 'output.mp4');
  // 2026-05-29 ハルシネーション対策: script JSON 必須 + placeholder タイトル禁止
  const scriptPath = path.join(scriptsDir, `${cfg.scriptPrefix}${idx}.json`);
  if (!fs.existsSync(scriptPath)) {
    console.error(`[upload_quarantine] SKIP ${idx}: script JSON not found at ${scriptPath} — refusing to publish with placeholder title`);
    continue;
  }
  let spec;
  try {
    spec = JSON.parse(fs.readFileSync(scriptPath, 'utf8'));
  } catch (e) {
    console.error(`[upload_quarantine] SKIP ${idx}: script JSON parse fail: ${e.message}`);
    continue;
  }
  const title = (spec.title || '').trim();
  if (!title) {
    console.error(`[upload_quarantine] SKIP ${idx}: empty title in script JSON`);
    continue;
  }
  if (/^(?:history|psych|shorts|otona_shorts|history_shorts|psych_shorts)\s+\d{3}$/i.test(title)) {
    console.error(`[upload_quarantine] SKIP ${idx}: placeholder-like title "${title}" — refusing to publish`);
    continue;
  }
  // 2026-05-30 (Task #41 再発防止): 文字化け (U+FFFD) や cp932 化け疑い検出 → 即 abort
  if (title.includes('�') || /[-]/.test(title.slice(0, 30))) {
    console.error(`[upload_quarantine] SKIP ${idx}: mojibake detected in title "${title.slice(0,60)}" — abort to prevent broken publish`);
    continue;
  }
  const description = spec.description || '';
  const tags = Array.isArray(spec.tags) ? spec.tags.slice(0, 15) : [];

  console.log(`[upload_quarantine] uploading ${idx}: ${title}`);

  try {
    const res = await youtube.videos.insert({
      part: ['snippet', 'status'],
      requestBody: {
        snippet: {
          title,
          description,
          tags,
          categoryId: args.kind === 'psych' ? '27' : '22',
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

    const videoId = res.data?.id;
    if (!videoId) {
      console.warn(`[upload_quarantine] ${idx} no videoId returned`);
      continue;
    }
    const videoUrl = cfg.shorts ? `https://youtube.com/shorts/${videoId}` : `https://youtube.com/watch?v=${videoId}`;
    console.log(`[upload_quarantine] ${idx} -> ${videoUrl}`);

    // thumbnail (optional, may not exist)
    const thumbPath = path.join(candidateDirs[idx], 'thumbnail.jpg');
    if (fs.existsSync(thumbPath)) {
      try {
        await youtube.thumbnails.set({
          videoId,
          media: { mimeType: 'image/jpeg', body: fs.createReadStream(thumbPath) },
        });
        console.log(`[upload_quarantine] ${idx} thumbnail set`);
      } catch (e) {
        console.warn(`[upload_quarantine] ${idx} thumbnail fail: ${e?.message || e}`);
      }
    }

    // uploaded.json update
    uploadedDb[idx] = {
      videoId,
      videoUrl,
      title,
      uploadedAt: new Date().toISOString(),
      source: 'upload_quarantine',
    };
    fs.writeFileSync(uploadedJson, JSON.stringify(uploadedDb, null, 2), 'utf8');
    uploaded++;

    // 30sec spacing for politeness
    if (uploaded < targets.length) await new Promise(r => setTimeout(r, 30000));

  } catch (e) {
    const msg = e?.message || String(e);
    console.error(`[upload_quarantine] ${idx} FAIL: ${msg}`);
    if (msg.includes('quotaExceeded') || msg.includes('403')) {
      console.error('[upload_quarantine] QUOTA EXCEEDED -- stopping');
      break;
    }
  }
}

console.log(`[upload_quarantine] DONE uploaded=${uploaded}/${targets.length}`);
