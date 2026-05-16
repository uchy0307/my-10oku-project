// scripts/preprocess-articles.mjs
// 47歳含む段落削除 + access_codes.json からアプリリンクブロック挿入 + 改行整理
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

/**
 * 改行ルール:
 *  - 章番号(H2 ## / H3 ###)の前後に空行2行
 *  - 「🔑 アクセスコード」「▼アプリで深く問う」の前に空行3行
 *  - リスト(- / * / 1.)の前後に空行1行
 *  - 連続3+改行は最大2行に圧縮（特殊マーカー直前のみ3行許可）
 */
function formatLineBreaks(text) {
  let t = text.replace(/\r\n/g, '\n');
  // 連続3+改行を一旦2に正規化
  t = t.replace(/\n{3,}/g, '\n\n');
  const lines = t.split('\n');
  const out = [];
  const isHeading = l => /^#{1,6}\s/.test(l);
  const isSpecial = l => /🔑\s*アクセス|▼\s*アプリで深く問う/.test(l);
  const isList    = l => /^\s*([-*+]|\d+\.)\s/.test(l);
  const trimTailBlanks = () => { while (out.length && out[out.length-1] === '') out.pop(); };

  for (let i = 0; i < lines.length; i++) {
    const cur = lines[i];
    const prev = out[out.length-1] ?? '';
    if (isSpecial(cur)) {
      trimTailBlanks();
      if (out.length > 0) out.push('','','');
    } else if (isHeading(cur)) {
      trimTailBlanks();
      if (out.length > 0) out.push('','');
    } else if (isList(cur) && !isList(prev) && prev !== '') {
      out.push('');
    } else if (!isList(cur) && isList(prev) && cur.trim() !== '') {
      out.push('');
    }
    out.push(cur);
    if (isHeading(cur) && i+1 < lines.length && lines[i+1].trim() !== '') {
      out.push('','');
    }
  }
  while (out.length && out[out.length-1] === '') out.pop();
  return out.join('\n') + '\n';
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
    next += `\n\n\n\n---\n\n▼アプリで深く問う\n\nURL: https://toi-suite.vercel.app/page/${id}\n\nアクセスコード: ${code}\n`;
  }

  next = formatLineBreaks(next);

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
