#!/usr/bin/env node
/**
 * YT ショート 10 本 文字化け title 緊急修正 (2026-05-30、 Task #41)
 * Node 版: googleapis で videos.update を実行。
 *
 * 前提: _fix_shorts_titles.py で script JSON / uploaded.json は既に正しい title に更新済。
 * このスクリプトは「正しい title (新)」を uploaded.json から取得 → YT 上 update。
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

const SEG_LABEL = { intro: '導入', peak: '感動', outro: '結末' };

const TARGETS = [
  { kind: 'history_shorts', idx: 'archive_QYKdjDxSIyM_peak',  vid: 'j0SX5B_4hBY', seg: 'peak'  },
  { kind: 'history_shorts', idx: 'archive_nyJtZDUqjRI_peak',  vid: 'efBpnnMy-FI', seg: 'peak'  },
  { kind: 'history_shorts', idx: 'archive_qDI1lCGxRsg_peak',  vid: '3liWDn647Aw', seg: 'peak'  },
  { kind: 'history_shorts', idx: 'archive_fJSZD7HIlvM_intro', vid: '7ud2kP1-TT8', seg: 'intro' },
  { kind: 'history_shorts', idx: 'archive_fJSZD7HIlvM_outro', vid: 'cIGLyl5nRGc', seg: 'outro' },
  { kind: 'psych_shorts',   idx: 'archive_CCgFjnDlxvM_peak', vid: 'DFvfLRpA3CM', seg: 'peak'  },
  { kind: 'psych_shorts',   idx: 'archive_LAVSg_jvnkY_peak', vid: 'SBPFvMvtemk', seg: 'peak'  },
  { kind: 'psych_shorts',   idx: 'archive_OdK_Z-qOWOY_peak', vid: 'O4RcWdYImuc', seg: 'peak'  },
  { kind: 'psych_shorts',   idx: 'archive_-mDkSwQDiMI_intro', vid: 'UQQC6Pwo26U', seg: 'intro' },
  { kind: 'psych_shorts',   idx: 'archive_-mDkSwQDiMI_outro', vid: '3GmXEJeNL10', seg: 'outro' },
];

function getOAuth(kind) {
  const cid = process.env.YOUTUBE_CLIENT_ID;
  const csec = process.env.YOUTUBE_CLIENT_SECRET;
  const rtok = kind === 'history_shorts'
    ? process.env.YOUTUBE_REFRESH_TOKEN
    : (process.env.OTONA_YOUTUBE_REFRESH_TOKEN || process.env.YOUTUBE_REFRESH_TOKEN);
  if (!cid || !csec || !rtok) {
    throw new Error(`Missing OAuth env for ${kind}`);
  }
  const oa = new google.auth.OAuth2(cid, csec);
  oa.setCredentials({ refresh_token: rtok });
  return oa;
}

async function main() {
  let ok = 0, fail = 0;
  for (const t of TARGETS) {
    console.log(`\n=== ${t.vid} (${t.kind} ${t.seg}) ===`);
    // uploaded.json から新 title 取得
    const upPath = path.join(ROOT, 'youtube', `${t.kind}_v2`, 'uploaded.json');
    const udb = JSON.parse(fs.readFileSync(upPath, 'utf8'));
    const entry = udb[t.idx];
    if (!entry) {
      console.error(`  [SKIP] no entry in uploaded.json`);
      fail++;
      continue;
    }
    const newTitle = entry.title;
    if (!newTitle || newTitle.includes('�')) {
      console.error(`  [SKIP] title still broken: ${JSON.stringify(newTitle).slice(0,80)}`);
      fail++;
      continue;
    }
    console.log(`  new title: ${newTitle}`);

    const segLabel = SEG_LABEL[t.seg] || t.seg;
    const tags = ['Shorts', segLabel].concat(
      t.kind === 'history_shorts' ? ['日本史', '歴史', '侍'] : ['心理学', '大人']
    );
    const desc = `過去動画より切り出し #Shorts #${segLabel}`;
    const categoryId = t.kind === 'history_shorts' ? '22' : '27';

    try {
      const oa = getOAuth(t.kind);
      const yt = google.youtube({ version: 'v3', auth: oa });
      await yt.videos.update({
        part: ['snippet'],
        requestBody: {
          id: t.vid,
          snippet: {
            title: newTitle.slice(0, 100),
            description: desc,
            tags,
            categoryId,
            defaultLanguage: 'ja',
            defaultAudioLanguage: 'ja',
          },
        },
      });
      console.log(`  ✓ updated → https://youtube.com/shorts/${t.vid}`);
      ok++;
    } catch (e) {
      console.error(`  [FAIL] ${e?.message || e}`);
      fail++;
    }
    // rate limit
    await new Promise(r => setTimeout(r, 1500));
  }
  console.log(`\n=== Done: ok=${ok} fail=${fail} ===`);
}

main().catch(e => { console.error('FATAL:', e?.message || e); process.exit(1); });
