#!/usr/bin/env node
/**
 * upload_shorts.mjs
 * =================
 * ロングからの切り出しショートを YouTube Shorts として upload。
 * 対象: youtube/<kind>_shorts_v2/.work/<idx>_<seg>/output.mp4 (idx=3digit, seg=intro|peak|outro)
 *
 * Usage:
 *   node scripts/upload_shorts.mjs --kind history --count 5
 *   --kind: history_shorts | psych_shorts (history/psych の alias も受け付け)
 *   --count: 上限本数 (デフォルト 5)
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
const args = { kind: null, count: 5 };
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  const mk = a.match(/^--kind=([a-z_]+)$/);
  if (mk) { args.kind = mk[1]; continue; }
  const mc = a.match(/^--count=(\d+)$/);
  if (mc) { args.count = parseInt(mc[1]); continue; }
  if (a === '--kind' && argv[i + 1]) { args.kind = argv[++i]; continue; }
  if (a === '--count' && argv[i + 1]) { args.count = parseInt(argv[++i]); continue; }
}

// alias normalization
if (args.kind === 'history') args.kind = 'history_shorts';
if (args.kind === 'psych' || args.kind === 'otona' || args.kind === 'otona_shorts') args.kind = 'psych_shorts';

const CFG = {
  history_shorts: { dir: 'history_shorts_v2', oauth: 'samurai', categoryId: '22' },
  psych_shorts:   { dir: 'psych_shorts_v2',   oauth: 'otona',   categoryId: '27' },
};

if (!args.kind || !CFG[args.kind]) {
  console.error(`--kind required: ${Object.keys(CFG).join('|')} (got: ${args.kind})`);
  process.exit(2);
}
const cfg = CFG[args.kind];

// ===== OAuth =====
const clientId = process.env.YOUTUBE_CLIENT_ID;
const clientSec = process.env.YOUTUBE_CLIENT_SECRET;
let refreshTok;
if (cfg.oauth === 'samurai') refreshTok = process.env.YOUTUBE_REFRESH_TOKEN;
else if (cfg.oauth === 'otona') refreshTok = process.env.OTONA_YOUTUBE_REFRESH_TOKEN || process.env.YOUTUBE_REFRESH_TOKEN;

if (!clientId || !clientSec || !refreshTok) {
  console.error('Missing OAuth env vars (YOUTUBE_CLIENT_ID/SECRET + refresh_token for ' + cfg.oauth + ')');
  process.exit(2);
}
const oauth2 = new google.auth.OAuth2(clientId, clientSec);
oauth2.setCredentials({ refresh_token: refreshTok });
const youtube = google.youtube({ version: 'v3', auth: oauth2 });

// ===== paths =====
const channelRoot = path.join(ROOT, 'youtube', cfg.dir);
const workDir = path.join(channelRoot, '.work');
const scriptsDir = path.join(channelRoot, 'scripts');
const uploadedJson = path.join(channelRoot, 'uploaded.json');

if (!fs.existsSync(workDir)) {
  console.log(`[upload_shorts] no .work dir: ${workDir}`);
  process.exit(0);
}

let uploadedDb = {};
if (fs.existsSync(uploadedJson)) {
  try { uploadedDb = JSON.parse(fs.readFileSync(uploadedJson, 'utf8')) || {}; } catch {}
}

// candidate: <idx>_<seg> または archive_<vid>_<seg> ディレクトリで output.mp4 を持ち、未投稿のもの
const IDX_SEG_RE = /^(?:\d{3}|archive_[A-Za-z0-9_-]+)_(intro|peak|outro)$/;

// 2026-05-29: ffprobe で moov atom 不在 (破損) + duration < 14s を除外
import { execSync } from 'node:child_process';
function probeOK(p) {
  try {
    const out = execSync(`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 ${JSON.stringify(p)}`, { stdio: ['pipe', 'pipe', 'pipe'] }).toString();
    const dur = parseFloat((out.match(/duration=(\S+)/) || [])[1] || '0');
    return dur >= 14;
  } catch { return false; }
}

const candidates = fs.readdirSync(workDir, { withFileTypes: true })
  .filter(d => d.isDirectory())
  .map(d => d.name)
  .filter(name => IDX_SEG_RE.test(name))
  .filter(name => fs.existsSync(path.join(workDir, name, 'output.mp4')))
  .filter(name => fs.statSync(path.join(workDir, name, 'output.mp4')).size > 100000)
  .filter(name => !uploadedDb[name])
  .filter(name => {
    const ok = probeOK(path.join(workDir, name, 'output.mp4'));
    if (!ok) console.warn(`[upload_shorts] INVALID mp4: ${name} (moov missing or duration<14s)`);
    return ok;
  })
  .sort();

console.log(`[upload_shorts] kind=${args.kind} candidates=${candidates.length} max=${args.count}`);
if (candidates.length === 0) {
  console.log('[upload_shorts] no candidates to upload');
  process.exit(0);
}

let uploaded = 0;
const targets = candidates.slice(0, args.count);

for (const name of targets) {
  const dir = path.join(workDir, name);
  const mp4 = path.join(dir, 'output.mp4');
  const scriptPath = path.join(scriptsDir, `short_${name}.json`);

  // 2026-05-29 ハルシネーション対策: script JSON 必須 + placeholder タイトル禁止
  if (!fs.existsSync(scriptPath)) {
    console.error(`[upload_shorts] SKIP ${name}: script JSON not found at ${scriptPath} — refusing to publish placeholder`);
    continue;
  }
  let spec;
  try {
    spec = JSON.parse(fs.readFileSync(scriptPath, 'utf8'));
  } catch (e) {
    console.error(`[upload_shorts] SKIP ${name}: script JSON parse fail: ${e.message}`);
    continue;
  }
  let title = (spec.title || '').trim();
  let description = spec.description || '';
  let tags = Array.isArray(spec.tags) ? spec.tags.slice(0, 15) : ['Shorts'];

  if (!title) {
    console.error(`[upload_shorts] SKIP ${name}: empty title in script JSON`);
    continue;
  }
  if (/^Shorts\s+/i.test(title) || /^(?:otona_shorts|history_shorts|psych_shorts)\s+/i.test(title)) {
    console.error(`[upload_shorts] SKIP ${name}: placeholder-like title "${title}" — refusing to publish`);
    continue;
  }
  // 2026-05-30 (Task #41 再発防止): 文字化け (U+FFFD) や cp932 化け疑い検出 → 即 abort
  if (title.includes('�') || /[-]/.test(title.slice(0, 30))) {
    console.error(`[upload_shorts] SKIP ${name}: mojibake detected in title "${title.slice(0,60)}" — abort to prevent broken publish`);
    continue;
  }

  // ensure #Shorts marker is in title or description (YouTube requires for Shorts detection)
  if (!/#shorts/i.test(title) && !/#shorts/i.test(description)) {
    description = description + '\n\n#Shorts';
  }

  console.log(`[upload_shorts] uploading ${name}: ${title}`);

  try {
    const res = await youtube.videos.insert({
      part: ['snippet', 'status'],
      requestBody: {
        snippet: {
          title: title.slice(0, 95),
          description: description.slice(0, 4500),
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

    const videoId = res.data?.id;
    if (!videoId) {
      console.warn(`[upload_shorts] ${name} no videoId returned`);
      continue;
    }
    const videoUrl = `https://youtube.com/shorts/${videoId}`;
    console.log(`[upload_shorts] ${name} -> ${videoUrl}`);

    uploadedDb[name] = {
      videoId,
      videoUrl,
      title: title.slice(0, 95),
      uploadedAt: new Date().toISOString(),
      source: 'upload_shorts',
    };
    fs.writeFileSync(uploadedJson, JSON.stringify(uploadedDb, null, 2), 'utf8');
    uploaded++;

    if (uploaded < targets.length) await new Promise(r => setTimeout(r, 30000));
  } catch (e) {
    const msg = e?.message || String(e);
    console.error(`[upload_shorts] ${name} FAIL: ${msg}`);
    if (msg.includes('quotaExceeded') || msg.includes('403')) {
      console.error('[upload_shorts] QUOTA EXCEEDED -- stopping');
      break;
    }
  }
}

console.log(`[upload_shorts] DONE uploaded=${uploaded}/${targets.length}`);
