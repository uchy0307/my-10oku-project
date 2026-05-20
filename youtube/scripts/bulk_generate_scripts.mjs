// youtube/scripts/bulk_generate_scripts.mjs
// 2026-05-20: 100本事前ストック化用 bulk generator
//
// 機能:
//   - topics.json を読み、まだ inputs/scripts/script_NNN.json が無い topic を選ぶ
//   - 1テーマあたり: outline → 5章本文 → metadata (description/tags/image_prompts) を Gemini で生成
//   - 結果を youtube/inputs/scripts/script_NNN.json に保存
//   - Gemini quota 枯渇 (全 fallback chain で 429) を検知したら graceful exit (process.exit 0)
//     → CI 側で「中断状態」をそのまま commit し、次の手動 dispatch で続きから再開
//
// 使い方:
//   node youtube/scripts/bulk_generate_scripts.mjs --max=20      # 最大20本生成
//   node youtube/scripts/bulk_generate_scripts.mjs --ids=081,082 # 指定IDのみ
//   node youtube/scripts/bulk_generate_scripts.mjs                # 残り全部 (CI timeout の安全のため max=30 推奨)

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fetch from 'node-fetch';

import { getCategoryGuidance } from './generate_script.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const TOPICS_FILE = path.join(ROOT, 'topics.json');
const SCRIPTS_DIR = path.join(ROOT, 'inputs', 'scripts');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
// 2026-05-20 (root fix): removed gemma-3-* models (404 NOT_FOUND on v1beta
// generateContent — confirmed in run #80 stderr). Aligned with generate_script.mjs.
const GEMINI_FALLBACK_MODELS = [
  'gemini-2.0-flash',
  'gemini-2.0-flash-lite',
  'gemini-2.5-flash-lite',
  'gemini-flash-latest',
  'gemini-flash-lite-latest',
];
const _gemini_endpoint = (m) => `https://generativelanguage.googleapis.com/v1beta/models/${m}:generateContent`;

// 章ごとの目標字数: 9600-12000 / 5章 ≒ 1920-2400/章。
// flash 実測 2000-3500/章 なので無理筋ではない。
const CHAPTERS_PER_SCRIPT = 5;
const CHAPTER_MIN_CHARS = 1800;
const TARGET_TOTAL_MIN = 9600;
const TARGET_TOTAL_MAX = 12000;

// CLI args
function parseArgs() {
  const out = { max: null, ids: null, dryRun: false };
  for (const a of process.argv.slice(2)) {
    if (a.startsWith('--max=')) out.max = parseInt(a.slice(6), 10);
    else if (a.startsWith('--ids=')) out.ids = a.slice(6).split(',').map(s => s.trim()).filter(Boolean);
    else if (a === '--dry-run') out.dryRun = true;
  }
  return out;
}

async function ensureDir(d) { await fs.mkdir(d, { recursive: true }); }

async function loadTopics() {
  const raw = await fs.readFile(TOPICS_FILE, 'utf-8');
  return JSON.parse(raw);
}

async function listAlreadyGenerated() {
  try {
    const files = await fs.readdir(SCRIPTS_DIR);
    const ids = new Set();
    for (const f of files) {
      const m = f.match(/^script_(\d{3})\.json$/);
      if (m) ids.add(m[1]);
    }
    return ids;
  } catch {
    return new Set();
  }
}

// ─── QuotaExhaustedError: 全 fallback model が 429 を返した時 ───
class QuotaExhaustedError extends Error {
  constructor(model) { super(`All Gemini models exhausted (last=${model})`); this.name = 'QuotaExhaustedError'; }
}

async function callGemini(prompt, { temperature = 0.85, maxOutputTokens = 32768 } = {}) {
  if (!GEMINI_API_KEY) {
    throw new Error('GEMINI_API_KEY not set');
  }
  const modelsChain = [GEMINI_MODEL, ...GEMINI_FALLBACK_MODELS.filter(m => m !== GEMINI_MODEL)];
  for (let modelIdx = 0; modelIdx < modelsChain.length; modelIdx++) {
    const model = modelsChain[modelIdx];
    const url = `${_gemini_endpoint(model)}?key=${GEMINI_API_KEY}`;
    const body = {
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: {
        temperature,
        thinkingConfig: { thinkingBudget: 0 },
        maxOutputTokens,
        responseMimeType: 'text/plain',
      },
      safetySettings: [
        { category: 'HARM_CATEGORY_HARASSMENT', threshold: 'BLOCK_NONE' },
        { category: 'HARM_CATEGORY_HATE_SPEECH', threshold: 'BLOCK_NONE' },
        { category: 'HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold: 'BLOCK_NONE' },
        { category: 'HARM_CATEGORY_DANGEROUS_CONTENT', threshold: 'BLOCK_NONE' },
      ],
    };
    let res;
    try {
      res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (e) {
      console.warn(`[bulk] model=${model} fetch error: ${e.message}`);
      continue;
    }
    if (res.ok) {
      const json = await res.json();
      const text = json?.candidates?.[0]?.content?.parts?.[0]?.text;
      const finishReason = json?.candidates?.[0]?.finishReason;
      const usage = json?.usageMetadata;
      console.log(`[bulk] model=${model} finish=${finishReason} promptTok=${usage?.promptTokenCount} candTok=${usage?.candidatesTokenCount} len=${text?.length || 0}`);
      if (text && text.length > 0) return { text, model, finishReason };
      console.warn(`[bulk] model=${model} returned empty text (finishReason=${finishReason}); next model`);
      continue;
    }
    const errText = await res.text();
    if (res.status === 429) {
      console.warn(`[bulk] model=${model} 429 quota exhausted; trying next model`);
      continue;
    }
    if (res.status === 404) {
      console.warn(`[bulk] model=${model} 404 not found; trying next model`);
      continue;
    }
    if (res.status >= 500) {
      // 5xx は同モデルで1回だけ短いリトライ
      await new Promise(r => setTimeout(r, 5000));
      try {
        const res2 = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (res2.ok) {
          const json2 = await res2.json();
          const text2 = json2?.candidates?.[0]?.content?.parts?.[0]?.text;
          if (text2) return { text: text2, model, finishReason: json2?.candidates?.[0]?.finishReason };
        }
      } catch {}
      console.warn(`[bulk] model=${model} ${res.status} (after retry); next model`);
      continue;
    }
    throw new Error(`Gemini API ${res.status} on ${model}: ${errText.slice(0, 500)}`);
  }
  // 全モデルダメだった → quota枯渇判定
  throw new QuotaExhaustedError(modelsChain[modelsChain.length - 1]);
}

// ─── プロンプト群 ───
function outlinePrompt(title, category) {
  const { guidance, outlineExample } = getCategoryGuidance(category, title);
  return `あなたは「侍の美学」を体現する歴史ナレーション作家。
以下のテーマで30分のYouTube動画台本の「章立てアウトライン」を作成せよ。

【テーマ】${title}
【カテゴリ】${category}

${guidance}

【出力ルール】
- ${CHAPTERS_PER_SCRIPT}章構成。各章タイトル（10〜20字）と、その章で語る要点を2〜4行
- マークダウン記号（**, ##, *）禁止
- 「ナレーション:」「BGM:」「VISUAL:」等のラベル禁止
- 出力は純粋な日本語の章タイトルと要点のみ

${outlineExample}

それでは執筆を開始せよ。`;
}

function chapterPrompt(title, category, outline, idx, chapterTitle, chapterBrief, prevSummary) {
  const { guidance } = getCategoryGuidance(category, title);
  const battleConstraint = category === '合戦軸'
    ? `\n11. 「合戦軸」のため、武将個人の伝記的記述（出生、幼少期、思想）に偏らない。タイトル「${title}」に含まれる**合戦名**を**この章だけで最低3回**、武器・象徴語を最低2回登場させよ。
12. 主役の取り違え禁止: タイトル「${title}」に明記されない武将を主役格として扱ってはならない。`
    : '';
  return `あなたは「侍の美学」を体現する歴史ナレーション作家。
全${CHAPTERS_PER_SCRIPT}章構成の歴史ナレーション動画の「第${idx}章」本文を執筆せよ。

【動画テーマ】${title}
【カテゴリ】${category}
${guidance}

【全体アウトライン】
${outline}

【今書く章】
第${idx}章 ${chapterTitle}
要点: ${chapterBrief}

${prevSummary ? `【前章までの要約】\n${prevSummary}\n` : ''}
【絶対要件】
1. 文字数: 日本語で最低${CHAPTER_MIN_CHARS}字、理想2200字（句読点・改行含む）
2. 純粋なナレーション本文のみ。マークダウン記号（**, ##, *, _, バッククォート）禁止
3. 「ナレーション:」「ナレーター:」「BGM:」「SE:」「VISUAL:」「テロップ:」等のラベル禁止
4. ハッシュタグ（#）禁止
5. 括弧書き（注釈・ト書き・カメラ指示）禁止
6. 章タイトルも省略。本文だけ書く
7. 段落は2〜4行、改行で区切る
8. 侍の美学トーン: 凛とした断言・余白を尊ぶ・短文と長文のリズム
9. テーマ「${title}」から逸脱しない。タイトルのキーワードを必ず複数回登場させる${battleConstraint}

【トーン参考】
「闇を裂く一閃の刃ーー それが、織田信長という男であった。」
「彼は、何を見ていたのか。何を、賭けていたのか。」

第${idx}章の本文を、純粋なナレーションとしてのみ出力せよ。`;
}

function metadataPrompt(title, category, fullScript) {
  const excerpt = fullScript.slice(0, 1500);
  return `以下は30分YouTubeナレーション動画の本編冒頭1500字の抜粋。
これに最適化された動画メタ情報を JSON で出力せよ。

【動画タイトル】${title}
【カテゴリ】${category}

【本編抜粋】
${excerpt}

【出力形式】（純粋なJSONのみ。マークダウン記法・コードブロック・前置き禁止）
{
  "description": "YouTube説明文。500〜800字。日本語。改行込み。冒頭3行で動画内容を魅力的に要約し、章立て案内、最後にチャンネル案内。ハッシュタグは末尾にまとめる",
  "tags": ["タグ1","タグ2","タグ3","タグ4","タグ5","タグ6","タグ7","タグ8","タグ9","タグ10"],
  "thumbnail_text": "サムネ用2行コピー (各12字以内)",
  "chapter_image_prompts": [
    ["第1章の代表画像プロンプト1", "プロンプト2", "プロンプト3"],
    ["第2章の代表画像プロンプト1", "プロンプト2", "プロンプト3"],
    ["第3章の代表画像プロンプト1", "プロンプト2", "プロンプト3"],
    ["第4章の代表画像プロンプト1", "プロンプト2", "プロンプト3"],
    ["第5章の代表画像プロンプト1", "プロンプト2", "プロンプト3"]
  ]
}

image_prompts は英語推奨。各プロンプトは「historic Japanese ...」で始める統一感を持たせる。`;
}

function parseOutline(outlineText) {
  const lines = outlineText.split('\n').map(l => l.trim()).filter(Boolean);
  const chapters = [];
  let current = null;
  for (const line of lines) {
    const m = line.match(/^第([一二三四五六七八九十0-9０-９]+)章\s*[ 　・:：]?\s*(.+)$/);
    if (m) {
      if (current) chapters.push(current);
      current = { title: m[2].trim(), brief: '' };
    } else if (current) {
      current.brief += (current.brief ? '\n' : '') + line;
    }
  }
  if (current) chapters.push(current);
  return chapters.slice(0, CHAPTERS_PER_SCRIPT);
}

function safeParseJson(text) {
  // remove ```json ... ``` fences if any
  let t = text.trim();
  t = t.replace(/^```(?:json)?\s*/i, '').replace(/\s*```\s*$/, '');
  try { return JSON.parse(t); } catch (e) {
    // try to find first {...}
    const m = t.match(/\{[\s\S]*\}/);
    if (m) { try { return JSON.parse(m[0]); } catch {} }
    return null;
  }
}

async function generateOneScript(topic) {
  console.log(`\n[bulk] === topic [${topic.id}] ${topic.title} (${topic.category}) ===`);
  const t0 = Date.now();

  // 1) outline
  const { text: outlineText } = await callGemini(outlinePrompt(topic.title, topic.category));
  let chapters = parseOutline(outlineText);
  if (chapters.length < 3) {
    chapters = [
      { title: '導入と謎', brief: 'テーマと最初の問いを提示' },
      { title: '対立と展開', brief: '中心人物と背景を描く' },
      { title: '深淵と決断', brief: '転換点と覚悟' },
      { title: '結末と余韻', brief: '勝敗と人々への影響' },
      { title: '結語と教訓', brief: '視聴者への問いと締めくくり' },
    ];
  }
  // pad to 5
  while (chapters.length < CHAPTERS_PER_SCRIPT) {
    chapters.push({ title: '余韻', brief: '余白と問いの再提示' });
  }
  chapters = chapters.slice(0, CHAPTERS_PER_SCRIPT);

  // 2) chapters
  const chapterOut = [];
  let prevSummary = '';
  let fullScript = '';
  for (let i = 0; i < chapters.length; i++) {
    const idx = i + 1;
    const ch = chapters[i];
    console.log(`[bulk]   ch${idx}/${chapters.length}: ${ch.title}`);
    const { text: body } = await callGemini(
      chapterPrompt(topic.title, topic.category, outlineText, idx, ch.title, ch.brief, prevSummary)
    );
    const narration = body.trim();
    chapterOut.push({ index: idx, title: ch.title, narration, image_prompts: [] });
    prevSummary += `第${idx}章「${ch.title}」概要: ${narration.slice(0, 250).replace(/\n/g, ' ')}\n`;
    fullScript += `第${idx}章 ${ch.title}\n\n${narration}\n\n`;
  }

  // 3) metadata
  let description = '';
  let tags = [];
  let thumbnailText = '';
  try {
    const { text: metaText } = await callGemini(metadataPrompt(topic.title, topic.category, fullScript));
    const meta = safeParseJson(metaText);
    if (meta) {
      description = meta.description || '';
      tags = Array.isArray(meta.tags) ? meta.tags.slice(0, 15) : [];
      thumbnailText = meta.thumbnail_text || '';
      if (Array.isArray(meta.chapter_image_prompts)) {
        for (let i = 0; i < chapterOut.length; i++) {
          const prompts = meta.chapter_image_prompts[i];
          if (Array.isArray(prompts)) chapterOut[i].image_prompts = prompts.slice(0, 5);
        }
      }
    }
  } catch (e) {
    if (e instanceof QuotaExhaustedError) throw e;
    console.warn(`[bulk]   metadata generation failed: ${e.message} — continuing without metadata`);
  }

  // fallback image prompts (English-prefixed) if metadata failed
  for (const ch of chapterOut) {
    if (!ch.image_prompts || ch.image_prompts.length === 0) {
      ch.image_prompts = [
        `historic Japanese ${topic.category} scene depicting ${topic.title}, dramatic lighting, cinematic`,
        `historic Japanese ${topic.category} portrait related to ${topic.title}, traditional aesthetic`,
        `historic Japanese ${topic.category} landscape related to ${topic.title}, evocative atmosphere`,
      ];
    }
  }

  const total = chapterOut.reduce((s, c) => s + c.narration.length, 0);
  const elapsedSec = ((Date.now() - t0) / 1000).toFixed(1);
  console.log(`[bulk]   total=${total}chars in ${elapsedSec}s`);

  return {
    id: topic.id,
    topic_id: topic.id,
    title: topic.title,
    category: topic.category,
    description,
    tags,
    thumbnail_text: thumbnailText,
    chapters: chapterOut,
    total_chars: total,
    target_chars_min: TARGET_TOTAL_MIN,
    target_chars_max: TARGET_TOTAL_MAX,
    generated_at: new Date().toISOString(),
    generator: 'bulk_generate_scripts.mjs v1',
  };
}

async function main() {
  const args = parseArgs();
  await ensureDir(SCRIPTS_DIR);
  const topics = await loadTopics();
  const already = await listAlreadyGenerated();

  let target;
  if (args.ids) {
    target = topics.filter(t => args.ids.includes(t.id));
  } else {
    target = topics.filter(t => !already.has(t.id));
  }
  if (args.max && target.length > args.max) target = target.slice(0, args.max);

  console.log(`[bulk] topics_total=${topics.length} already=${already.size} target=${target.length}`);
  if (args.dryRun) {
    console.log('[bulk] dry-run; target:', target.map(t => t.id).join(','));
    return;
  }
  if (target.length === 0) {
    console.log('[bulk] nothing to do');
    return;
  }

  let done = 0;
  let quotaHit = false;
  for (const topic of target) {
    try {
      const script = await generateOneScript(topic);
      const out = path.join(SCRIPTS_DIR, `script_${topic.id}.json`);
      await fs.writeFile(out, JSON.stringify(script, null, 2), 'utf-8');
      done++;
      console.log(`[bulk] WROTE ${out} (cumulative ${done}/${target.length})`);
    } catch (e) {
      if (e instanceof QuotaExhaustedError) {
        console.error(`[bulk] QUOTA EXHAUSTED at topic ${topic.id} — stopping bulk gracefully`);
        quotaHit = true;
        break;
      }
      console.error(`[bulk] topic ${topic.id} FAILED: ${e.message} — skipping`);
    }
  }

  console.log(`\n[bulk] === summary ===`);
  console.log(`[bulk] done_this_run=${done}`);
  console.log(`[bulk] quota_hit=${quotaHit}`);
  const finalAlready = await listAlreadyGenerated();
  console.log(`[bulk] total_scripts_in_repo=${finalAlready.size}`);
  console.log(`[bulk] remaining=${topics.length - finalAlready.size}`);

  // exit 0 even on quota hit — let CI commit progress
  process.exit(0);
}

const isMain = import.meta.url === `file://${process.argv[1]}` ||
               import.meta.url.endsWith(path.basename(process.argv[1] || ''));
if (isMain) {
  main().catch(err => {
    console.error('[bulk] FATAL:', err);
    process.exit(1);
  });
}
