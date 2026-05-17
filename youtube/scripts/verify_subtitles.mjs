#!/usr/bin/env node
// youtube/scripts/verify_subtitles.mjs
// Compare generated .ass subtitle file to the source script.txt.
// If text overlap < 90%, FAIL the workflow so the bad video is NEVER uploaded.

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');

const STATE_PATH = path.join(OUTPUT_DIR, 'state.json');
const MIN_OVERLAP = 0.85; // 85% character overlap

function normalize(s) {
  return (s || '')
    .replace(/\r/g, '')
    .replace(/[「」『』。、！？\s〜・……]/g, '')
    .replace(/[a-zA-Z0-9_\-]/g, '')
    .trim();
}

function bigramSet(s) {
  const out = new Set();
  for (let i = 0; i < s.length - 1; i++) out.add(s.slice(i, i + 2));
  return out;
}

function overlapRatio(a, b) {
  const A = bigramSet(a);
  const B = bigramSet(b);
  if (A.size === 0) return 0;
  let hits = 0;
  for (const x of A) if (B.has(x)) hits++;
  return hits / A.size;
}

function extractAssText(assContent) {
  // Lines starting with "Dialogue:" — capture text portion (after 9th comma)
  const lines = assContent.split(/\r?\n/).filter(l => l.startsWith('Dialogue:'));
  return lines.map(l => {
    const idx = l.indexOf(',,');
    if (idx === -1) return '';
    // skip 9 commas to get the text field
    const fields = l.split(',');
    return fields.slice(9).join(',').replace(/\{[^}]*\}/g, '');
  }).join('\n');
}

async function main() {
  const state = JSON.parse(await fs.readFile(STATE_PATH, 'utf-8'));
  const topicId = state.currentTopic && state.currentTopic.id;
  if (!topicId) {
    console.log('[verify_subs] no currentTopic — nothing to verify');
    return;
  }
  const scriptPath = path.join(OUTPUT_DIR, `${topicId}_script.txt`);
  const assPath = path.join(OUTPUT_DIR, `${topicId}_subs.ass`);
  const [scriptText, assText] = await Promise.all([
    fs.readFile(scriptPath, 'utf-8').catch(() => ''),
    fs.readFile(assPath, 'utf-8').catch(() => ''),
  ]);
  if (!scriptText) throw new Error(`[verify_subs] script missing: ${scriptPath}`);
  if (!assText) throw new Error(`[verify_subs] ass missing: ${assPath}`);
  const scriptN = normalize(scriptText);
  const assN = normalize(extractAssText(assText));
  const ratio = overlapRatio(scriptN, assN);
  console.log(`[verify_subs] script.length=${scriptN.length} ass.length=${assN.length} overlap=${(ratio*100).toFixed(1)}%`);
  if (ratio < MIN_OVERLAP) {
    throw new Error(`[verify_subs] FAIL: subtitle text deviates from script (${(ratio*100).toFixed(1)}% < ${MIN_OVERLAP*100}%). Upload aborted to prevent garbage video.`);
  }
  console.log('[verify_subs] OK');
}

main().catch(err => { console.error(err.message); process.exit(1); });
