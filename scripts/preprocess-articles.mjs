// scripts/preprocess-articles.mjs
// 47歳含む段落削除 + access_codes.json からアプリリンクブロック挿入
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..');
const ARTICLES_DIR = join(REPO_ROOT, 'articles');
const ACCESS_CODES_PATH = join(REPO_ROOT, 'note-auto', 'access_codes.json');
const APP_BLOCK_MARKER = '<!-- AUTO_APP_LINK_BLOCK -->';

function scrubAge(text) {
  // 段落単位で「47歳」を含むものを削除
  const paragraphs = text.split(/\n\s*\n/);
  const filtered = paragraphs.filter(p => !p.includes('47歳'));
  return filtered.join('\n\n');
}

async function processOne(id, accessCodes) {
  const fp = join(ARTICLES_DIR, `note_${id}.md`);
  if (!existsSync(fp)) return { id, skipped: 'no_file' };
  const body = await readFile(fp, 'utf-8');
  const before47 = (body.match(/47歳/g) || []).length;

  let next = scrubAge(body);

  const code = accessCodes[id];
  if (code) {
    const re = new RegExp(`\\n*${APP_BLOCK_MARKER}[\\s\\S]*$`, 'g');
    next = next.replace(re, '').trimEnd();
    next += `\n\n${APP_BLOCK_MARKER}\n---\n▼アプリで深く問う\nURL: https://toi-suite.vercel.app/page/${id}\nアクセスコード: ${code}\n`;
  }

  if (body !== next) {
    await writeFile(fp, next, 'utf-8');
    return { id, scrubbed: before47, hasCode: !!code, changed: true };
  }
  return { id, scrubbed: before47, hasCode: !!code, changed: false };
}

async function main() {
  console.log('[INFO] preprocess-articles.mjs start');
  const codesRaw = await readFile(ACCESS_CODES_PATH, 'utf-8');
  const accessCodes = JSON.parse(codesRaw);

  const stats = { processed: 0, changed: 0, totalScrubbed: 0, withCode: 0, noFile: 0 };
  for (let n = 1; n <= 200; n++) {
    const id = String(n).padStart(3, '0');
    const r = await processOne(id, accessCodes);
    if (r.skipped) { stats.noFile++; continue; }
    stats.processed++;
    if (r.changed) stats.changed++;
    stats.totalScrubbed += (r.scrubbed || 0);
    if (r.hasCode) stats.withCode++;
  }
  console.log('[INFO] stats:', JSON.stringify(stats));
}

main().catch(err => { console.error('[FATAL]', err); process.exit(1); });
