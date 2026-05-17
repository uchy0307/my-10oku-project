#!/usr/bin/env node
// note-auto/verify_published.mjs
// After publishing, fetch the public note URL and verify:
//  - Article is published (status 200, is_published:true)
//  - Price is 100 yen
//  - Has the toi-suite link (アプリリンク)
//  - Has the 🔑 boundary marker in body
// If any check fails, log fatal and exit non-zero (workflow fails → self-heal retries).

import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const QUEUE_PATH = path.join(__dirname, 'queue.json');

const NOTE_API = 'https://note.com/api/v3/notes/';

async function verifyNote(noteKey, articleId) {
  const url = NOTE_API + noteKey + '?draft=false';
  const r = await fetch(url);
  if (r.status !== 200) throw new Error(`note ${articleId} GET status ${r.status}`);
  const j = await r.json();
  const d = j.data || {};
  const checks = {
    isPublished: d.is_published === true,
    price100: d.price === 100,
    hasBody: typeof d.body === 'string' && d.body.length > 100,
    hasAppLink: typeof d.body === 'string' && d.body.includes('toi-suite.vercel.app/page/'),
    hasBoundary: typeof d.body === 'string' && d.body.includes('🔑'),
    hasAttachment: Array.isArray(d.attachments) && d.attachments.length >= 3,
    notHas47歳: typeof d.body !== 'string' || !d.body.includes('47歳'),
  };
  const failed = Object.entries(checks).filter(([k, v]) => !v).map(([k]) => k);
  return { url, checks, failed, attachmentCount: (d.attachments || []).length };
}

async function main() {
  const queue = JSON.parse(await readFile(QUEUE_PATH, 'utf-8'));
  // Get last 3 published entries
  const published = (queue.articles || []).filter(a => a.note_key && a.posted_at).slice(-3);
  let allOk = true;
  for (const a of published) {
    try {
      const v = await verifyNote(a.note_key, a.id);
      if (v.failed.length === 0) {
        console.log(`[verify_published] OK ${a.id} (${v.url}) attachments=${v.attachmentCount}`);
      } else {
        console.error(`[verify_published] FAIL ${a.id} (${v.url}) — ${v.failed.join(',')}`);
        allOk = false;
      }
    } catch (e) {
      console.error(`[verify_published] ERROR ${a.id}: ${e.message}`);
      allOk = false;
    }
  }
  if (!allOk) {
    console.error('[verify_published] Some checks failed — self-heal will retry');
    process.exit(1);
  }
}

main().catch(e => { console.error(e.message); process.exit(1); });
