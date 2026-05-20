// youtube/scripts/shorts_pipeline.mjs
// 60秒 YouTube Shorts を既存 long video から生成→upload。
//
// 設計 (2026-05-20 全面改訂・user 明示):
//   source = 侍チャンネル (@japanese.samurai.channel) に既にアップ済の 30 分本編動画群。
//   topics.json で 1:1 固定するのではなく、自チャンネル uploads playlist の full archive を
//   YouTube Data API で取得して rotation する。
//
//   永続 state (shorts_state.json#usedSegments) に (sourceVideoId, startSec) を記録し、
//   毎 Run 「未使用の (videoId, startSec) 組合せ」を選ぶことで、
//   同じ素材・同じ秒位置の重複 upload を構造的に防ぐ。
//
//   ★ 古い video から優先して rotation する。
//     最新の長尺動画 (真田幸村など) は当面 Short 化せず、
//     まだ Short 化していない古い video から順に消化する。
//
// 工程:
//   1) channelUploads を YouTube Data API で全件取得 + duration を batch fetch
//   2) shorts_state.usedSegments と照合し未使用の (videoId, startSec) を 1 つ確定
//      (rotation: startSec 外 × videoId 内 = まず別動画を優先 / videoId は 古い順)
//   3) その時点で state に予約 (reservedAt 付き) commit
//   4) yt-dlp で source mp4 取得 → ffmpeg で 60s × 1080x1920 縦長 crop
//   5) YouTube upload as Shorts → state を upload 結果で確定
//
// env: YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
//      YOUTUBE_PLAYLIST_ALL_ID (optional)
//      SHORTS_VIDEO_ID (optional: 手動 override — workflow_dispatch input)
//      SHORTS_CLIP_START (optional: 手動 override — 空なら state ベースで自動選定)
//      SHORTS_CLIP_DURATION (optional: default 58)

import fs from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { google } from 'googleapis';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');
const SHORTS_STATE_FILE = path.join(OUTPUT_DIR, 'shorts_state.json');

const {
  YOUTUBE_CLIENT_ID,
  YOUTUBE_CLIENT_SECRET,
  YOUTUBE_REFRESH_TOKEN,
  YOUTUBE_PLAYLIST_ALL_ID,
  SHORTS_VIDEO_ID,
  SHORTS_CLIP_START,
  SHORTS_CLIP_DURATION,
} = process.env;

export const CLIP_DURATION = Math.min(Number(SHORTS_CLIP_DURATION || 58), 59);

// rotation 用の開始秒グリッド。
//   - 60s: イントロ後の本編冒頭
//   - 300/600/900/1500/1800/2400: 5〜10 分間隔の異なる章
// 30 分本編なら最大 6〜7 combination / 1 source video が確保できる。
export const START_GRID = [60, 300, 600, 900, 1500, 1800, 2400];
// 重複検知の許容差 (秒)。これ以下の差は「ほぼ同じシーン」とみなして拒否する。
export const DUP_TOLERANCE_SEC = 5;
// source 末尾の余裕 (秒)。startSec + CLIP_DURATION + TAIL_BUFFER <= durationSec を要求。
export const TAIL_BUFFER = 30;

function run(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    console.log('[run]', cmd, args.join(' '));
    const p = spawn(cmd, args, { stdio: 'inherit', ...opts });
    p.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(cmd + ' exit ' + code))));
  });
}

async function loadJson(p, dflt) {
  try { return JSON.parse(await fs.readFile(p, 'utf-8')); } catch { return dflt; }
}

async function saveJson(p, obj) {
  await fs.writeFile(p, JSON.stringify(obj, null, 2), 'utf-8');
}

function buildOauth() {
  if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET || !YOUTUBE_REFRESH_TOKEN) return null;
  const o = new google.auth.OAuth2(YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, 'urn:ietf:wg:oauth:2.0:oob');
  o.setCredentials({ refresh_token: YOUTUBE_REFRESH_TOKEN });
  return o;
}

function parseIsoDurationSec(iso) {
  // ISO 8601 PT#H#M#S -> seconds
  if (!iso) return null;
  const m = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(iso);
  if (!m) return null;
  return (Number(m[1] || 0) * 3600) + (Number(m[2] || 0) * 60) + Number(m[3] || 0);
}

// ──────────────────────────────────────────────────────────────────────────
// Pure helpers (unit-testable)
// ──────────────────────────────────────────────────────────────────────────

/**
 * 既存 usedSegments と (sourceVideoId, startSec) 候補が衝突するか判定。
 * 同 videoId かつ startSec の差が tolerance 以下なら衝突 = true。
 */
export function isDuplicateSegment(usedSegments, sourceVideoId, startSec, tolerance = DUP_TOLERANCE_SEC) {
  if (!Array.isArray(usedSegments)) return false;
  for (const s of usedSegments) {
    if (!s || s.sourceVideoId !== sourceVideoId) continue;
    const ss = typeof s.startSec === 'number' ? s.startSec : null;
    if (ss === null) continue;
    if (Math.abs(ss - startSec) <= tolerance) return true;
  }
  return false;
}

/**
 * channel video 群 + usedSegments から未使用の (videoId, startSec) 組合せを 1 つ返す。
 * candidates は事前に「古い順」(oldest first) でソート済の前提。
 *
 * @param {Array<{videoId: string, durationSec: number, uploadedAt?: string}>} candidates
 * @param {Array} usedSegments
 * @param {object} opts
 * @returns {{sourceVideoId: string, startSec: number} | null}
 */
export function pickUnusedComboPure(candidates, usedSegments, opts = {}) {
  const clipDuration = opts.clipDuration ?? CLIP_DURATION;
  const tailBuffer = opts.tailBuffer ?? TAIL_BUFFER;
  const grid = opts.startGrid ?? START_GRID;
  const tolerance = opts.tolerance ?? DUP_TOLERANCE_SEC;
  if (!Array.isArray(candidates) || candidates.length === 0) return null;
  // rotation: startSec 外 × videoId 内。
  //   → Run N と Run N+1 では同じ startSec でも 別の videoId が選ばれ、映像が変わる。
  //   → 全 videoId を 1 巡してから 次の startSec へ進む。
  //   → candidates は「古い順」なので、まだ Short 化していない古い video から消化される。
  for (const startSec of grid) {
    for (const c of candidates) {
      if (!c || !c.videoId) continue;
      if (typeof c.durationSec !== 'number' || c.durationSec <= 0) continue;
      if (startSec + clipDuration + tailBuffer > c.durationSec) continue;
      if (isDuplicateSegment(usedSegments, c.videoId, startSec, tolerance)) continue;
      return { sourceVideoId: c.videoId, startSec };
    }
  }
  return null;
}

/**
 * 旧スキーマ records (startSec を持たない) を usedSegments に backfill する。
 * 旧 default CLIP_START=30 を仮定して登録 → 同じ素材+冒頭の再選択を防ぐ。
 */
export function backfillUsedSegments(shortsState, legacyStartSec = 30) {
  if (!shortsState || typeof shortsState !== 'object') return { changed: false, state: shortsState };
  const out = { ...shortsState };
  out.usedSegments = Array.isArray(out.usedSegments) ? [...out.usedSegments] : [];
  const seen = new Set(out.usedSegments
    .filter((s) => s && s.sourceVideoId != null && typeof s.startSec === 'number')
    .map((s) => s.sourceVideoId + ':' + s.startSec));
  let changed = false;
  for (const r of (out.records || [])) {
    if (!r || !r.sourceVideoId) continue;
    const startSec = typeof r.startSec === 'number' ? r.startSec : legacyStartSec;
    const k = r.sourceVideoId + ':' + startSec;
    if (seen.has(k)) continue;
    out.usedSegments.push({
      sourceVideoId: r.sourceVideoId,
      startSec,
      shortsVideoId: r.shortsVideoId,
      shortsUrl: r.shortsUrl,
      uploadedAt: r.uploadedAt,
      legacy: typeof r.startSec === 'number' ? undefined : true,
    });
    seen.add(k);
    changed = true;
  }
  return { changed, state: out };
}

// ──────────────────────────────────────────────────────────────────────────
// YouTube API helpers
// ──────────────────────────────────────────────────────────────────────────

async function listChannelUploadsAll(youtube) {
  // 自分のチャンネル uploads playlist の全件 (最大 ~1000 件) を取得。
  try {
    const ch = await youtube.channels.list({ part: ['contentDetails'], mine: true });
    const uploadsPl = ch.data.items?.[0]?.contentDetails?.relatedPlaylists?.uploads;
    if (!uploadsPl) return [];
    const out = [];
    let pageToken;
    for (let page = 0; page < 20; page++) {
      const r = await youtube.playlistItems.list({
        part: ['snippet', 'contentDetails'],
        playlistId: uploadsPl,
        maxResults: 50,
        pageToken,
      });
      for (const it of (r.data.items || [])) {
        const vid = it.contentDetails?.videoId;
        const when = it.contentDetails?.videoPublishedAt || it.snippet?.publishedAt;
        if (vid) out.push({ videoId: vid, uploadedAt: when || '' });
      }
      pageToken = r.data.nextPageToken;
      if (!pageToken) break;
    }
    return out;
  } catch (e) {
    console.warn('[shorts] listChannelUploadsAll failed:', e.message);
    return [];
  }
}

async function fetchVideoMetaBatch(youtube, ids) {
  // videos.list は id を最大 50 件まで指定可。snippet + contentDetails を一括取得。
  const out = {};
  for (let i = 0; i < ids.length; i += 50) {
    const chunk = ids.slice(i, i + 50);
    const r = await youtube.videos.list({ part: ['snippet', 'contentDetails'], id: chunk });
    for (const it of (r.data.items || [])) {
      out[it.id] = {
        snippet: it.snippet,
        durationSec: parseIsoDurationSec(it.contentDetails?.duration),
      };
    }
  }
  return out;
}

async function buildCandidatePool(youtube, shortsState) {
  const dead = new Set(shortsState.deadVideos || []);
  const ownShorts = new Set((shortsState.records || []).map((r) => r.shortsVideoId).filter(Boolean));

  const uploads = await listChannelUploadsAll(youtube);
  console.log('[shorts] channel uploads total: ' + uploads.length);
  if (uploads.length === 0) throw new Error('listChannelUploadsAll returned 0 items');

  // ★ 古い順 (ASC) でソート → まだ Short 化していない古い動画から優先消化。
  const filtered = uploads
    .filter((u) => u && u.videoId && !dead.has(u.videoId) && !ownShorts.has(u.videoId))
    .sort((a, b) => (a.uploadedAt || '').localeCompare(b.uploadedAt || ''));
  const ids = filtered.map((u) => u.videoId);
  if (ids.length === 0) throw new Error('No live channel uploads remain after dead/own-shorts filter');

  const meta = await fetchVideoMetaBatch(youtube, ids);
  const candidates = [];
  for (const u of filtered) {
    const m = meta[u.videoId];
    if (!m) continue;
    if (typeof m.durationSec !== 'number' || m.durationSec < 70) {
      console.warn('[shorts] skip ' + u.videoId + ' (duration=' + m.durationSec + 's, likely a Short itself)');
      continue;
    }
    candidates.push({
      videoId: u.videoId,
      durationSec: m.durationSec,
      uploadedAt: u.uploadedAt,
      snippet: m.snippet,
    });
  }
  if (candidates.length === 0) throw new Error('No long-form candidates (all skipped as too short)');
  console.log('[shorts] long-form candidate pool: ' + candidates.length + ' (oldest first)');
  console.log('[shorts] top 5 oldest: ' + candidates.slice(0, 5).map((c) => c.videoId + '@' + (c.uploadedAt || '?')).join(', '));
  return candidates;
}

async function markVideoDead(videoId, reason) {
  try {
    const s = await loadJson(SHORTS_STATE_FILE, { processed: [], records: [], deadVideos: [], usedSegments: [] });
    s.deadVideos = Array.from(new Set([...(s.deadVideos || []), videoId]));
    s.deadVideoLog = (s.deadVideoLog || []).concat([{ videoId, reason, at: new Date().toISOString() }]).slice(-50);
    await saveJson(SHORTS_STATE_FILE, s);
    console.warn('[shorts] marked dead videoId=' + videoId + ' reason=' + reason);
  } catch (e) {
    console.warn('[shorts] markVideoDead failed:', e.message);
  }
}

// ──────────────────────────────────────────────────────────────────────────
// Download / ffmpeg / upload
// ──────────────────────────────────────────────────────────────────────────

async function downloadSource(videoId, dest) {
  const tryArgs = [
    ['--extractor-args', 'youtube:player_client=android', '--user-agent', 'com.google.android.youtube/19.09.37 (Linux; U; Android 14; en_US) gzip'],
    ['--extractor-args', 'youtube:player_client=ios', '--user-agent', 'com.google.ios.youtube/19.09.3 (iPhone16,2; U; CPU iOS 17_0 like Mac OS X)'],
    ['--extractor-args', 'youtube:player_client=web_safari'],
    [],
  ];
  let lastErr = null;
  for (const extra of tryArgs) {
    try {
      await run('yt-dlp', [
        ...extra, '--no-check-certificate', '--no-playlist',
        '-f', 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
        '-o', dest,
        'https://www.youtube.com/watch?v=' + videoId,
      ]);
      console.log('[yt-dlp] OK with', JSON.stringify(extra));
      return;
    } catch (e) {
      console.warn('[yt-dlp] strategy failed:', e.message);
      lastErr = e;
    }
  }
  throw lastErr || new Error('yt-dlp all strategies failed');
}

async function makeShortsVideo(srcPath, outPath, clipStart) {
  const vf = "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920,setsar=1";
  await run('ffmpeg', [
    '-y', '-ss', String(clipStart), '-i', srcPath, '-t', String(CLIP_DURATION),
    '-vf', vf, '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', outPath,
  ]);
}

async function uploadShorts(youtube, videoPath, snippet, sourceVideoId, startSec) {
  const baseTitle = (snippet?.title || 'Shorts').slice(0, 80);
  const title = (baseTitle + ' #Shorts').slice(0, 100);
  const description = (((snippet && snippet.description) || '')
    + '\n\n──'
    + '\n本編: https://www.youtube.com/watch?v=' + sourceVideoId
    + '\n切り出し: ' + startSec + 's〜'
    + '\n#Shorts #日本史 #侍 #samurai').slice(0, 4900);
  const tags = ((snippet?.tags) || []).concat(['Shorts', '日本史', '侍', 'samurai']).slice(0, 30);
  const stat = await fs.stat(videoPath);
  console.log('[upload] size=' + stat.size + ' bytes title="' + title + '"');
  const res = await youtube.videos.insert(
    {
      part: ['snippet', 'status'],
      requestBody: {
        snippet: {
          title,
          description,
          tags,
          categoryId: snippet?.categoryId || '27',
          defaultLanguage: 'ja',
          defaultAudioLanguage: 'ja',
        },
        status: { privacyStatus: 'public', selfDeclaredMadeForKids: false },
      },
      media: { body: createReadStream(videoPath) },
    },
    {
      onUploadProgress: (evt) => {
        const pct = stat.size ? Math.round((evt.bytesRead / stat.size) * 100) : 0;
        process.stdout.write('\r[upload] ' + pct + '%');
      },
    },
  );
  process.stdout.write('\n');
  return res.data;
}

// ──────────────────────────────────────────────────────────────────────────
// main
// ──────────────────────────────────────────────────────────────────────────

async function main() {
  const oauth = buildOauth();
  if (!oauth) throw new Error('OAuth env missing (YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN)');
  const youtube = google.youtube({ version: 'v3', auth: oauth });

  // ── load + backfill state ────────────────────────────────────────────
  let shortsState = await loadJson(SHORTS_STATE_FILE, {
    processed: [], records: [], deadVideos: [], usedSegments: [],
  });
  if (!Array.isArray(shortsState.usedSegments)) shortsState.usedSegments = [];
  const backfill = backfillUsedSegments(shortsState);
  if (backfill.changed) {
    shortsState = backfill.state;
    console.log('[shorts] backfilled ' + shortsState.usedSegments.length + ' legacy segments into usedSegments');
    await saveJson(SHORTS_STATE_FILE, shortsState);
  }

  // ── pick source + startSec ────────────────────────────────────────────
  let sourceVideoId, snippet, durationSec, startSec;

  if (SHORTS_VIDEO_ID && SHORTS_VIDEO_ID.trim()) {
    // 手動 override path
    sourceVideoId = SHORTS_VIDEO_ID.trim();
    const meta = await fetchVideoMetaBatch(youtube, [sourceVideoId]);
    const m = meta[sourceVideoId];
    if (!m) {
      await markVideoDead(sourceVideoId, 'manual override target not found');
      throw new Error('Override SHORTS_VIDEO_ID not found on YouTube: ' + sourceVideoId);
    }
    if (typeof m.durationSec !== 'number' || m.durationSec < 70) {
      await markVideoDead(sourceVideoId, 'too short (' + m.durationSec + 's)');
      throw new Error('Override SHORTS_VIDEO_ID is too short (likely a Short): ' + m.durationSec + 's');
    }
    snippet = m.snippet;
    durationSec = m.durationSec;

    const envStart = (SHORTS_CLIP_START || '').toString().trim();
    if (envStart !== '') {
      const parsed = Number(envStart);
      if (!Number.isFinite(parsed) || parsed < 0) throw new Error('Invalid SHORTS_CLIP_START: ' + envStart);
      if (parsed + CLIP_DURATION + TAIL_BUFFER > durationSec) {
        throw new Error('SHORTS_CLIP_START + duration overflows source (start=' + parsed + ', dur=' + durationSec + ')');
      }
      startSec = parsed;
    } else {
      const cand = [{ videoId: sourceVideoId, durationSec, uploadedAt: '' }];
      const picked = pickUnusedComboPure(cand, shortsState.usedSegments);
      if (!picked) throw new Error('No unused startSec slot left for override video ' + sourceVideoId);
      startSec = picked.startSec;
    }
  } else {
    // 自動 rotation path (古い順)
    const candidates = await buildCandidatePool(youtube, shortsState);

    const envStart = (SHORTS_CLIP_START || '').toString().trim();
    if (envStart !== '') {
      const parsed = Number(envStart);
      if (!Number.isFinite(parsed) || parsed < 0) throw new Error('Invalid SHORTS_CLIP_START: ' + envStart);
      const picked = pickUnusedComboPure(candidates, shortsState.usedSegments, { startGrid: [parsed] });
      if (!picked) throw new Error('No unused videoId at startSec=' + parsed + ' (all combinations used or source too short)');
      sourceVideoId = picked.sourceVideoId;
      startSec = picked.startSec;
    } else {
      const picked = pickUnusedComboPure(candidates, shortsState.usedSegments);
      if (!picked) throw new Error('All (videoId, startSec) combinations exhausted in START_GRID; expand grid or clear usedSegments');
      sourceVideoId = picked.sourceVideoId;
      startSec = picked.startSec;
    }
    const c = candidates.find((x) => x.videoId === sourceVideoId);
    if (!c) throw new Error('Internal: picked candidate not found in pool');
    snippet = c.snippet;
    durationSec = c.durationSec;
  }

  // ── duplicate gate (再確認) ────────────────────────────────────────────
  if (isDuplicateSegment(shortsState.usedSegments, sourceVideoId, startSec)) {
    throw new Error(
      'Duplicate gate tripped: (' + sourceVideoId + ', ' + startSec + 's) collides with existing usedSegments. '
      + 'Refusing to upload to avoid duplicate Short.',
    );
  }

  console.log('[shorts] selected sourceVideoId=' + sourceVideoId
    + ' duration=' + durationSec + 's'
    + ' startSec=' + startSec + 's'
    + ' clipDuration=' + CLIP_DURATION + 's'
    + ' title="' + (snippet?.title || '') + '"');

  // ── reserve slot in state BEFORE download/upload ─────────────────────
  shortsState.usedSegments.push({
    sourceVideoId,
    startSec,
    clipDuration: CLIP_DURATION,
    reservedAt: new Date().toISOString(),
  });
  await saveJson(SHORTS_STATE_FILE, shortsState);

  // ── download + ffmpeg ────────────────────────────────────────────────
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  let srcPath = path.join(OUTPUT_DIR, 'shorts_src_' + sourceVideoId + '.mp4');
  const outPath = path.join(OUTPUT_DIR, 'shorts_' + sourceVideoId + '_' + startSec + 's.mp4');

  // SHORTS_LOCAL_FILE: 直近 main pipeline がアップ前に生成した mp4 を再利用する経路。
  // ただし「source videoId と無関係なローカル mp4 を使ってしまう」と内容ズレを起こすため、
  // ファイル名に sourceVideoId を含むか、明示的に SHORTS_LOCAL_FILE_FORCE=1 のとき以外は使わない。
  const localFile = process.env.SHORTS_LOCAL_FILE;
  const localForce = process.env.SHORTS_LOCAL_FILE_FORCE === '1';
  let useLocal = false;
  if (localFile) {
    try {
      const s = await fs.stat(localFile);
      const baseName = path.basename(localFile);
      const matchesId = baseName.includes(sourceVideoId);
      if (s.size > 0 && (matchesId || localForce)) {
        console.log('[shorts] using local file: ' + localFile + ' (' + s.size + ' bytes, matchesId=' + matchesId + ', force=' + localForce + ')');
        srcPath = localFile;
        useLocal = true;
      } else if (s.size > 0) {
        console.warn('[shorts] SHORTS_LOCAL_FILE ignored (filename does not match sourceVideoId=' + sourceVideoId + '): ' + baseName);
      }
    } catch (e) {
      console.warn('[shorts] SHORTS_LOCAL_FILE not usable: ' + e.message);
    }
  }
  if (!useLocal) {
    await downloadSource(sourceVideoId, srcPath);
  }
  await makeShortsVideo(srcPath, outPath, startSec);

  // ── upload ────────────────────────────────────────────────────────────
  const result = await uploadShorts(youtube, outPath, snippet, sourceVideoId, startSec);
  const shortsVideoId = result.id;
  const shortsUrl = 'https://www.youtube.com/shorts/' + shortsVideoId;
  console.log('[shorts] uploaded videoId=' + shortsVideoId + ' url=' + shortsUrl);

  if (YOUTUBE_PLAYLIST_ALL_ID) {
    try {
      await youtube.playlistItems.insert({
        part: ['snippet'],
        requestBody: { snippet: { playlistId: YOUTUBE_PLAYLIST_ALL_ID, resourceId: { kind: 'youtube#video', videoId: shortsVideoId } } },
      });
      console.log('[shorts] playlist add OK');
    } catch (e) {
      console.warn('[shorts] playlist add failed (non-fatal):', e.message);
    }
  }

  // ── finalize state ────────────────────────────────────────────────────
  const finalState = await loadJson(SHORTS_STATE_FILE, shortsState);
  if (!Array.isArray(finalState.usedSegments)) finalState.usedSegments = [];
  const segRecord = {
    sourceVideoId,
    startSec,
    clipDuration: CLIP_DURATION,
    shortsVideoId,
    shortsUrl,
    uploadedAt: new Date().toISOString(),
  };
  const segIdx = finalState.usedSegments.findIndex(
    (s) => s && s.sourceVideoId === sourceVideoId && s.startSec === startSec,
  );
  if (segIdx >= 0) finalState.usedSegments[segIdx] = segRecord;
  else finalState.usedSegments.push(segRecord);

  finalState.processed = Array.from(new Set([...(finalState.processed || []), sourceVideoId]));
  finalState.records = (finalState.records || []).concat([{
    sourceVideoId,
    startSec,
    clipDuration: CLIP_DURATION,
    shortsVideoId,
    shortsUrl,
    title: snippet?.title || '',
    uploadedAt: new Date().toISOString(),
  }]);
  finalState.lastUpload = { sourceVideoId, startSec, shortsVideoId, shortsUrl, at: new Date().toISOString() };
  await saveJson(SHORTS_STATE_FILE, finalState);

  try { if (!useLocal) await fs.unlink(srcPath); } catch {}
  try { await fs.unlink(outPath); } catch {}
  console.log('[shorts] DONE');
}

// CLI 実行時のみ main を呼ぶ (test import 時の自動実行を避ける)
const isMain = (() => {
  try {
    return import.meta.url === pathToFileURL(process.argv[1] || '').href;
  } catch { return false; }
})();
if (isMain) {
  main().catch((e) => {
    console.error('[shorts] FAILED:', e);
    process.exit(1);
  });
}
