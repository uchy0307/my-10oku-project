#!/usr/bin/env node
// tools/memory_review.mjs
// Auto-review a new/changed memory rule via Gemini API.

import fs from 'node:fs/promises';
import path from 'node:path';

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const DRAFT_PATH = process.env.DRAFT_PATH;
const MEMORY_DIR = process.env.MEMORY_DIR;

if (!GEMINI_API_KEY) { console.error('GEMINI_API_KEY required'); process.exit(1); }
if (!DRAFT_PATH) { console.error('DRAFT_PATH required'); process.exit(1); }
if (!MEMORY_DIR) { console.error('MEMORY_DIR required'); process.exit(1); }

async function collectExistingRules() {
  const out = [];
  try {
    const files = await fs.readdir(MEMORY_DIR);
    for (const f of files) {
      if (!f.endsWith('.md') || f === 'MEMORY.md') continue;
      const full = path.join(MEMORY_DIR, f);
      const content = await fs.readFile(full, 'utf-8');
      out.push({ name: f, content: content.slice(0, 4000) });
    }
  } catch (e) { console.warn('memory dir not accessible:', e.message); }
  return out;
}

async function callGemini(prompt) {
  const url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key=' + GEMINI_API_KEY;
  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { temperature: 0.3, maxOutputTokens: 8192, responseMimeType: 'application/json' },
  };
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error('Gemini API ' + r.status + ': ' + (await r.text()).slice(0, 200));
  const j = await r.json();
  const txt = j?.candidates?.[0]?.content?.parts?.[0]?.text || '';
  return JSON.parse(txt);
}

async function main() {
  const draft = await fs.readFile(DRAFT_PATH, 'utf-8');
  const existing = await collectExistingRules();
  const prompt = [
    'You are a senior automation engineer reviewing a new rule for a YouTube/note.com automation system.',
    '',
    'EXISTING RULES (' + existing.length + ' files):',
    existing.map(r => '=== ' + r.name + ' ===\n' + r.content).join('\n\n'),
    '',
    'NEW DRAFT:',
    draft,
    '',
    'Your task:',
    '1. Identify duplicates with existing rules',
    '2. Identify conflicts',
    '3. Identify gaps (edge cases)',
    '4. Suggest concrete improvements',
    '5. Output improved final draft markdown (same frontmatter format)',
    '',
    'Return strict JSON: {"duplicates":[],"conflicts":[],"gaps":[],"improvements":[],"finalDraft":"<full md>","shouldUpdate":bool}'
  ].join('\n');
  const review = await callGemini(prompt);
  console.log('[memory_review] ' + JSON.stringify({
    duplicates: review.duplicates,
    conflicts: review.conflicts?.length || 0,
    gaps: review.gaps?.length || 0,
    improvements: review.improvements?.length || 0,
    shouldUpdate: review.shouldUpdate,
  }));
  if (review.shouldUpdate && review.finalDraft) {
    await fs.writeFile(DRAFT_PATH, review.finalDraft, 'utf-8');
    console.log('[memory_review] DRAFT updated with Gemini improvements');
  } else {
    console.log('[memory_review] no update needed');
  }
}

main().catch(e => { console.error(e.message); process.exit(1); });
