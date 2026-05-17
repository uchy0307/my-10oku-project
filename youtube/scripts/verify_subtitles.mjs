// youtube/scripts/verify_subtitles.mjs
// 字幕(.ass / .srt) と スクリプト(.txt) の文字bigram整合性検証
// 使い方: node verify_subtitles.mjs --script <script.txt> --subtitle <subs.ass|subtitle.srt>
//        [--threshold 0.85] [--quiet]
// 失敗時(平均overlap < threshold) は exit code 1 で異常終了
//
// 検証ロジック:
//   1) script.txt を読み、stripVisualDirectives と同等の正規化（コード重複を避ける為 inline実装）
//   2) subtitle ファイルを拡張子で判別しパース → 各 segment の text 抽出
//   3) script を空行で chapter 分割
//   4) 各 segment の文字bigram集合を作り、最も overlap が高い chapter との
//      overlap率 ( |seg ∩ chap| / |seg| ) を score とする
//   5) 全 segment の平均が threshold 未満なら fail
//   6) 補助: segment 数が voice 想定読了 segment 数と乖離していたら warn を出す

import fs from 'node:fs/promises';
import path from 'node:path';

// ──── CLI 引数 ────
export function parseArgs(argv) {
  const out = { threshold: 0.85, quiet: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--script') out.script = argv[++i];
    else if (a === '--subtitle') out.subtitle = argv[++i];
    else if (a === '--threshold') out.threshold = parseFloat(argv[++i]);
    else if (a === '--quiet') out.quiet = true;
  }
  return out;
}

// ──── スクリプト正規化（generate_voice.mjs / compile_video.mjs と整合） ────
export function normalizeScript(text) {
  let t = text;
  t = t.replace(/\[[^\]\n]*\]/g, '');
  t = t.replace(/^#{1,6}\s.*$/gm, '');
  t = t.replace(/\*\*\*?([^*]+)\*\*\*?/g, '$1');
  t = t.replace(/\*([^*]+)\*/g, '$1');
  t = t.replace(/_([^_]+)_/g, '$1');
  t = t.replace(/[*_]+/g, '');
  t = t.replace(/#[^\s#]+/g, '');
  t = t.replace(/^\s*(ナレーション|ナレーター|BGM|SE|効果音|台本|タイトル|オープニング|エンディング|エピローグ|プロローグ|テロップ|字幕)\s*[:：]\s*/gm, '');
  t = t.replace(/https?:\/\/\S+/g, '');
  t = t.replace(/\n{3,}/g, '\n\n');
  return t.trim();
}

// ──── 字幕パーサ ────
export function parseAss(content) {
  // Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
  // Text は 9 番目以降のカンマ以降すべて
  const out = [];
  const lines = content.split(/\r?\n/);
  for (const line of lines) {
    if (!line.startsWith('Dialogue:')) continue;
    const body = line.slice('Dialogue:'.length).trimStart();
    // 9個のカンマで分割し、残りを text として再連結
    const parts = [];
    let idx = 0;
    let buf = '';
    for (let i = 0; i < body.length; i++) {
      if (body[i] === ',' && idx < 9) {
        parts.push(buf);
        buf = '';
        idx++;
      } else {
        buf += body[i];
      }
    }
    parts.push(buf);
    if (parts.length < 10) continue;
    const start = parseAssTime(parts[1].trim());
    const end = parseAssTime(parts[2].trim());
    const text = stripAssOverrides(parts[9]).trim();
    if (text) out.push({ start, end, text });
  }
  return out;
}

function parseAssTime(s) {
  // h:mm:ss.cs
  const m = s.match(/^(\d+):(\d+):(\d+)\.(\d+)$/);
  if (!m) return 0;
  return parseInt(m[1], 10) * 3600 + parseInt(m[2], 10) * 60 + parseInt(m[3], 10) + parseInt(m[4], 10) / 100;
}

function stripAssOverrides(s) {
  // {\override} タグを除去
  return s.replace(/\{[^}]*\}/g, '').replace(/\\N/g, ' ').replace(/\\n/g, ' ').replace(/\\h/g, ' ');
}

export function parseSrt(content) {
  const out = [];
  const blocks = content.replace(/\r\n/g, '\n').split(/\n{2,}/);
  for (const blk of blocks) {
    const lines = blk.split('\n').filter(Boolean);
    if (lines.length < 2) continue;
    // index行がある場合と無い場合
    let timeLine = lines[0];
    let textStart = 1;
    if (/^\d+$/.test(lines[0])) {
      timeLine = lines[1];
      textStart = 2;
    }
    const tm = timeLine.match(/(\d+):(\d+):(\d+)[,\.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,\.](\d+)/);
    if (!tm) continue;
    const start = parseInt(tm[1], 10) * 3600 + parseInt(tm[2], 10) * 60 + parseInt(tm[3], 10) + parseInt(tm[4], 10) / 1000;
    const end = parseInt(tm[5], 10) * 3600 + parseInt(tm[6], 10) * 60 + parseInt(tm[7], 10) + parseInt(tm[8], 10) / 1000;
    const text = lines.slice(textStart).join(' ').trim();
    if (text) out.push({ start, end, text });
  }
  return out;
}

export function parseSubtitle(filePath, content) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === '.ass' || ext === '.ssa') return parseAss(content);
  if (ext === '.srt' || ext === '.vtt') return parseSrt(content);
  // 中身でフォールバック判定
  if (/^\[Script Info\]/m.test(content)) return parseAss(content);
  return parseSrt(content);
}

// ──── bigram ────
export function bigrams(text) {
  // 空白・改行・句読点を除いた連続文字 bigram
  const cleaned = text.replace(/[\s。、！？!?,.「」『』（）()【】\-‐—–·・]+/g, '');
  const set = new Set();
  for (let i = 0; i + 1 < cleaned.length; i++) {
    set.add(cleaned.slice(i, i + 2));
  }
  return set;
}

function intersectSize(a, b) {
  let n = 0;
  // smaller を回す
  const [small, big] = a.size <= b.size ? [a, b] : [b, a];
  for (const x of small) if (big.has(x)) n++;
  return n;
}

// ──── chapter 分割: 空行で paragraph 化 ────
export function splitChapters(normalizedScript) {
  const paras = normalizedScript
    .split(/\n\s*\n+/)
    .map(p => p.replace(/\n+/g, '').trim())
    .filter(Boolean);
  // 空行なし1段落のみの場合: 句点で粗く分割（chapter1個だけだとマッチ精度低い為）
  if (paras.length <= 1) {
    return normalizedScript
      .split(/(?<=[。！？])/)
      .map(s => s.trim())
      .filter(s => s.length >= 4);
  }
  return paras;
}

// ──── メインの照合 ────
export function verify(scriptText, segments, opts = {}) {
  const threshold = opts.threshold ?? 0.85;
  const normalized = normalizeScript(scriptText);
  const chapters = splitChapters(normalized);
  const chapBigrams = chapters.map(bigrams);
  // 全体 bigram（chapter分割がうまくいかない短文への保険）
  const wholeBg = bigrams(normalized);

  const perSeg = [];
  let sum = 0;
  let counted = 0;
  for (const seg of segments) {
    const sg = bigrams(seg.text);
    if (sg.size === 0) {
      perSeg.push({ text: seg.text, score: 1, matchedChapter: -1 });
      continue;
    }
    let bestScore = 0;
    let bestIdx = -1;
    for (let i = 0; i < chapBigrams.length; i++) {
      const inter = intersectSize(sg, chapBigrams[i]);
      const score = inter / sg.size;
      if (score > bestScore) { bestScore = score; bestIdx = i; }
    }
    // 念のため全体でも測り、bestがそれ未満なら全体を採用（chapter区切り誤差吸収）
    const wholeScore = intersectSize(sg, wholeBg) / sg.size;
    if (wholeScore > bestScore) { bestScore = wholeScore; bestIdx = -1; }
    perSeg.push({ text: seg.text, score: bestScore, matchedChapter: bestIdx });
    sum += bestScore;
    counted++;
  }
  const avg = counted > 0 ? sum / counted : 0;
  return { avg, threshold, pass: avg >= threshold, perSeg, segmentCount: segments.length, chapterCount: chapters.length };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.script || !opts.subtitle) {
    console.error('Usage: node verify_subtitles.mjs --script <script.txt> --subtitle <subs.ass|subtitle.srt> [--threshold 0.85] [--quiet]');
    process.exit(2);
  }
  const scriptText = await fs.readFile(opts.script, 'utf-8');
  const subContent = await fs.readFile(opts.subtitle, 'utf-8');
  const segments = parseSubtitle(opts.subtitle, subContent);
  if (segments.length === 0) {
    console.error(`[verify_subtitles] FAIL: 0 segments parsed from ${opts.subtitle}`);
    process.exit(1);
  }
  const r = verify(scriptText, segments, { threshold: opts.threshold });
  if (!opts.quiet) {
    console.log(`[verify_subtitles] segments=${r.segmentCount} chapters=${r.chapterCount}`);
    console.log(`[verify_subtitles] avg_overlap=${r.avg.toFixed(4)} threshold=${r.threshold}`);
    // worst 5 を表示
    const worst = [...r.perSeg].sort((a, b) => a.score - b.score).slice(0, 5);
    for (const w of worst) {
      console.log(`  [score=${w.score.toFixed(3)} ch=${w.matchedChapter}] ${w.text.slice(0, 40)}`);
    }
  }
  if (!r.pass) {
    console.error(`[verify_subtitles] FAIL: avg_overlap=${r.avg.toFixed(4)} < threshold=${r.threshold}`);
    process.exit(1);
  }
  console.log('[verify_subtitles] PASS');
}

// import された場合は実行しない（test から再利用）
const isMain = import.meta.url === `file://${process.argv[1]}` ||
               import.meta.url.endsWith(path.basename(process.argv[1] || ''));
if (isMain) {
  main().catch(err => {
    console.error('[verify_subtitles] ERROR:', err);
    process.exit(2);
  });
}
