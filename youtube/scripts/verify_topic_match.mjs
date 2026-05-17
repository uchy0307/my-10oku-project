// youtube/scripts/verify_topic_match.mjs
// Phase D2: 生成された script.txt が topic.title のキーワードを十分に含むか検証
// 含まない場合は Gemini が題目から逸脱した（例: 「長篠」題で武田信玄伝記化）と判断 → exit 1
//
// 使い方: node verify_topic_match.mjs --script <script.txt> --topic-id <id> [--topics youtube/topics.json]
//        [--min-occurrences 5] [--coverage 0.7] [--category-aware] [--quiet]
//
// 判定 (Phase D2 強化版):
//   1) topic.title からキーワードを抽出（カタカナ/漢字連続、2字以上）
//   2) 「の戦い」「の変」等の汎用語と1字keywordは除外
//   3) 全キーワードのうち、min_occurrences 回以上 script に出現したキーワードの率を coverage と定義
//   4) coverage < 閾値（既定 0.7）なら fail
//   5) 合戦軸: タイトル先頭の合戦名 (PRIMARY) が script で primaryMinOccurrences (既定 7) 未満なら fail

import fs from 'node:fs/promises';
import path from 'node:path';

// ──── CLI 引数 ────
export function parseArgs(argv) {
  // Phase D2: 既定値を強化 (3→5, 0.5→0.7)
  const out = {
    minOccurrences: 5,
    coverage: 0.7,
    primaryMinOccurrences: 7,
    quiet: false,
    topicsFile: 'youtube/topics.json',
    categoryAware: true,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--script') out.script = argv[++i];
    else if (a === '--topic-id') out.topicId = argv[++i];
    else if (a === '--title') out.title = argv[++i];
    else if (a === '--category') out.category = argv[++i];
    else if (a === '--topics') out.topicsFile = argv[++i];
    else if (a === '--min-occurrences') out.minOccurrences = parseInt(argv[++i], 10);
    else if (a === '--coverage') out.coverage = parseFloat(argv[++i]);
    else if (a === '--primary-min') out.primaryMinOccurrences = parseInt(argv[++i], 10);
    else if (a === '--no-category-aware') out.categoryAware = false;
    else if (a === '--quiet') out.quiet = true;
  }
  return out;
}

// ──── タイトルからキーワード抽出 ────
const GENERIC_WORDS = new Set([
  '戦い', '合戦', '時代', '物語', '伝説', '事件', '事変', '攻め',
  '世紀', '日本', '日本史', '歴史', 'シリーズ', 'ナレーション', '主役', '武将',
]);
export function extractKeywords(title) {
  if (!title) return [];
  const kanji = title.match(/[一-鿿々ヶ]{2,}/g) || [];
  const kata = title.match(/[ァ-ヴー]{2,}/g) || [];
  const matches = [...kanji, ...kata];
  const out = [];
  for (const m of matches) {
    if (GENERIC_WORDS.has(m)) continue;
    out.push(m);
  }
  return [...new Set(out)];
}

// ──── 検証 (Phase D2: category-aware primary keyword check) ────
export function verifyTopicMatch(scriptText, keywords, opts = {}) {
  const minOcc = opts.minOccurrences ?? 5;
  const coverageThreshold = opts.coverage ?? 0.7;
  const primaryMinOcc = opts.primaryMinOccurrences ?? 7;
  const category = opts.category || '';
  const perKw = [];
  let covered = 0;
  for (const kw of keywords) {
    if (kw.length < 2) continue;
    let n = 0;
    let idx = 0;
    while (true) {
      const found = scriptText.indexOf(kw, idx);
      if (found < 0) break;
      n++;
      idx = found + 1;
    }
    perKw.push({ kw, count: n, sufficient: n >= minOcc });
    if (n >= minOcc) covered++;
  }
  const coverage = keywords.length > 0 ? covered / keywords.length : 0;
  let primaryPass = true;
  let primaryKw = null;
  let primaryCount = 0;
  if (category === '合戦軸' && keywords.length > 0) {
    primaryKw = keywords[0];
    primaryCount = perKw.find(x => x.kw === primaryKw)?.count ?? 0;
    primaryPass = primaryCount >= primaryMinOcc;
  }
  const coveragePass = coverage >= coverageThreshold;
  return {
    coverage,
    coverageThreshold,
    pass: coveragePass && primaryPass,
    coveragePass,
    primaryPass,
    primaryKw,
    primaryCount,
    primaryMinOccurrences: primaryMinOcc,
    perKw,
    keywordsCount: keywords.length,
    coveredCount: covered,
    minOccurrences: minOcc,
    category,
  };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.script) {
    console.error('Usage: node verify_topic_match.mjs --script <script.txt> --topic-id <id> [--title <override>] [--category <override>] [--topics youtube/topics.json] [--min-occurrences 5] [--coverage 0.7] [--primary-min 7] [--no-category-aware] [--quiet]');
    process.exit(2);
  }
  let title = opts.title;
  let category = opts.category || '';
  if (!title) {
    if (!opts.topicId) { console.error('Either --title or --topic-id is required'); process.exit(2); }
    const raw = await fs.readFile(opts.topicsFile, 'utf-8');
    const topics = JSON.parse(raw);
    const topic = (Array.isArray(topics) ? topics : (topics.topics || [])).find(t => String(t.id) === String(opts.topicId));
    if (!topic) { console.error(`topic id=${opts.topicId} not found in ${opts.topicsFile}`); process.exit(2); }
    title = topic.title;
    if (!category) category = topic.category || '';
  }
  const script = await fs.readFile(opts.script, 'utf-8');
  const keywords = extractKeywords(title);
  if (!opts.quiet) {
    console.log(`[verify_topic_match] title="${title}" category="${category}"`);
    console.log(`[verify_topic_match] keywords (${keywords.length}): ${keywords.join(' / ')}`);
  }
  if (keywords.length === 0) {
    console.warn('[verify_topic_match] WARNING: タイトルから抽出可能なキーワードがありません');
    console.log('[verify_topic_match] PASS (no keywords to verify)');
    return;
  }
  const r = verifyTopicMatch(script, keywords, {
    minOccurrences: opts.minOccurrences,
    coverage: opts.coverage,
    primaryMinOccurrences: opts.primaryMinOccurrences,
    category: opts.categoryAware ? category : '',
  });
  if (!opts.quiet) {
    console.log(`[verify_topic_match] script chars=${script.length}`);
    console.log(`[verify_topic_match] coverage=${(r.coverage*100).toFixed(1)}% (${r.coveredCount}/${r.keywordsCount} keywords met >=${r.minOccurrences} occurrences) threshold=${(r.coverageThreshold*100).toFixed(1)}%`);
    for (const k of r.perKw) {
      console.log(`  ${k.sufficient ? 'OK ' : 'FAIL'} "${k.kw}": ${k.count} occurrences (need >=${r.minOccurrences})`);
    }
    if (r.primaryKw) {
      console.log(`  PRIMARY (${category}) "${r.primaryKw}": ${r.primaryCount} occurrences (need >=${r.primaryMinOccurrences}) -> ${r.primaryPass ? 'OK' : 'FAIL'}`);
    }
  }
  if (!r.pass) {
    const reasons = [];
    if (!r.coveragePass) reasons.push(`coverage=${(r.coverage*100).toFixed(1)}% < ${(r.coverageThreshold*100).toFixed(1)}%`);
    if (!r.primaryPass) reasons.push(`primary "${r.primaryKw}" occurs ${r.primaryCount} < ${r.primaryMinOccurrences}`);
    console.error(`[verify_topic_match] FAIL: ${reasons.join('; ')}. Script likely off-topic.`);
    process.exit(1);
  }
  console.log('[verify_topic_match] PASS');
}

const isMain = import.meta.url === `file://${process.argv[1]}` ||
               import.meta.url.endsWith(path.basename(process.argv[1] || ''));
if (isMain) {
  main().catch(err => {
    console.error('[verify_topic_match] ERROR:', err);
    process.exit(2);
  });
}
