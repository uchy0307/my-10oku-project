// youtube/scripts/generate_script.mjs
// Gemini APIで「侍の美学」トーンの30分台本を生成
// input: youtube/topics.json から次の未投稿テーマ
// output: youtube/output/<id>_script.txt

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fetch from 'node-fetch';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const TOPICS_FILE = path.join(ROOT, 'topics.json');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
const GEMINI_ENDPOINT = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`;

// ─── プロンプト群 ───
const OUTLINE_PROMPT = (title, category) => `あなたは「侍の美学」を体現する歴史ナレーション作家。
以下のテーマで30分のYouTube動画台本の「章立てアウトライン」を作成せよ。

【テーマ】${title}
【カテゴリ】${category}

【出力ルール】
- 5章構成。各章タイトル（10〜20字）と、その章で語る要点を2〜4行
- マークダウン記号（**, ##, *）禁止
- 「ナレーション:」「BGM:」「VISUAL:」等のラベル禁止
- 出力は純粋な日本語の章タイトルと要点のみ

【出力例】
第一章 闇を裂く問いかけ
桶狭間の戦いとは何であったか、視聴者に最初の謎を投げかける。
信長の出生と尾張の地政学的背景を簡潔に提示。

第二章 ……
……

それでは執筆を開始せよ。`;

const CHAPTER_PROMPT = (title, category, outline, chapterIndex, chapterTitle, chapterBrief, prevSummary) => `あなたは「侍の美学」を体現する歴史ナレーション作家。
全5章構成の歴史ナレーション動画の「第${chapterIndex}章」本文を執筆せよ。

【動画テーマ】${title}
【カテゴリ】${category}
【全体アウトライン】
${outline}

【今書く章】
第${chapterIndex}章 ${chapterTitle}
要点: ${chapterBrief}

${prevSummary ? `【前章までの要約】\n${prevSummary}\n` : ''}

【絶対要件】
1. 文字数: 日本語で6000〜8000字（句読点・改行含む）
2. 純粋なナレーション本文のみ。マークダウン記号（**, ##, *, _, バッククォート）禁止
3. 「ナレーション:」「ナレーター:」「BGM:」「SE:」「VISUAL:」「テロップ:」等のラベル禁止
4. ハッシュタグ（#）禁止
5. 括弧書き（注釈・ト書き・カメラ指示）禁止
6. 「※」「→」等の記号は最小限
7. 章タイトルも省略。本文だけ書く
8. 段落は2〜4行、改行で区切る
9. 侍の美学トーン: 凛とした断言・余白を尊ぶ・短文と長文のリズム

【トーン参考】
「闇を裂く一閃の刃ーー それが、織田信長という男であった。」
「彼は、何を見ていたのか。何を、賭けていたのか。」

第${chapterIndex}章の本文を、純粋なナレーションとしてのみ出力せよ。`;

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
}

async function loadState() {
  try {
    const raw = await fs.readFile(STATE_FILE, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return { processed: [], lastRun: null, currentTopic: null };
  }
}

async function saveState(state) {
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
}

async function loadTopics() {
  const raw = await fs.readFile(TOPICS_FILE, 'utf-8');
  return JSON.parse(raw);
}

function pickNextTopic(topics, state) {
  const processed = new Set(state.processed || []);
  return topics.find(t => !processed.has(t.id)) || null;
}

async function callGemini(prompt, attempt = 1) {
  if (!GEMINI_API_KEY) {
    console.warn('[generate_script] GEMINI_API_KEY not set — emitting stub script.');
    return `[STUB SCRIPT]\n${prompt}\n\n--- ここにGemini生成台本が入ります ---`;
  }
  const url = `${GEMINI_ENDPOINT}?key=${GEMINI_API_KEY}`;
  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.85,
      // gemini-2.5-flash は thinkingMode が default で有効。thinking が
      // maxOutputTokens を食い潰すので、thinkingBudget=0 で無効化する。
      thinkingConfig: { thinkingBudget: 0 },
      maxOutputTokens: 32768,
      responseMimeType: 'text/plain',
    },
    // 歴史題材で safety filter が誤発動するケースを抑止
    safetySettings: [
      { category: 'HARM_CATEGORY_HARASSMENT', threshold: 'BLOCK_NONE' },
      { category: 'HARM_CATEGORY_HATE_SPEECH', threshold: 'BLOCK_NONE' },
      { category: 'HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold: 'BLOCK_NONE' },
      { category: 'HARM_CATEGORY_DANGEROUS_CONTENT', threshold: 'BLOCK_NONE' },
    ],
  };
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errText = await res.text();
    // 503 / 429 は一時的過負荷。指数バックオフで最大5回リトライ
    if ((res.status === 503 || res.status === 429) && attempt < 5) {
      const waitSec = Math.pow(2, attempt) * 15; // 30, 60, 120, 240, 480秒
      console.warn(`[generate_script] ${res.status} retryable. wait ${waitSec}s then attempt ${attempt + 1}`);
      await new Promise((r) => setTimeout(r, waitSec * 1000));
      return callGemini(prompt, attempt + 1);
    }
    throw new Error(`Gemini API error ${res.status}: ${errText}`);
  }
  const json = await res.json();
  const cand = json?.candidates?.[0];
  const text = cand?.content?.parts?.[0]?.text;
  const finishReason = cand?.finishReason;
  const usage = json?.usageMetadata;
  console.log(
    `[generate_script] attempt=${attempt} finishReason=${finishReason} ` +
    `promptTokens=${usage?.promptTokenCount} candidateTokens=${usage?.candidatesTokenCount} ` +
    `totalTokens=${usage?.totalTokenCount} text.length=${text?.length || 0}`,
  );
  if (!text) {
    // safetyや空応答の場合 1回だけリトライ
    if (attempt < 2) {
      console.warn('[generate_script] empty text. Retrying...');
      return callGemini(prompt, attempt + 1);
    }
    throw new Error(`Gemini returned empty content (finishReason=${finishReason})`);
  }
  // 200文字以下は事実上失敗とみなしリトライ
  if (text.length < 1000 && attempt < 2) {
    console.warn(`[generate_script] suspiciously short response (${text.length} chars). Retrying...`);
    return callGemini(prompt, attempt + 1);
  }
  return text;
}

/** アウトラインテキストから章タイトルと要点を5個取り出す */
function parseOutline(outlineText) {
  const lines = outlineText.split('\n').map((l) => l.trim()).filter(Boolean);
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
  return chapters.slice(0, 5);
}

async function main() {
  await ensureDir(OUTPUT_DIR);
  const topics = await loadTopics();
  const state = await loadState();

  const topic = pickNextTopic(topics, state);
  if (!topic) {
    console.log('[generate_script] All topics processed. Nothing to do.');
    return;
  }

  console.log(`[generate_script] Selected topic: [${topic.id}] ${topic.title} (${topic.category})`);

  // ─── 1. アウトライン生成 ───
  console.log('[generate_script] Step 1/6: outline generation');
  const outlineText = await callGemini(OUTLINE_PROMPT(topic.title, topic.category));
  const chapters = parseOutline(outlineText);
  console.log(`[generate_script] Parsed ${chapters.length} chapters from outline`);
  if (chapters.length < 3) {
    // フォールバック: 固定5章
    chapters.splice(0, chapters.length,
      { title: '導入と謎', brief: 'テーマと最初の問いを提示' },
      { title: '対立と展開', brief: '中心人物と背景を描く' },
      { title: '深淵と決断', brief: '転換点と覚悟' },
      { title: '結末と余韻', brief: '勝敗と人々への影響' },
      { title: '結語', brief: '視聴者への教訓' },
    );
  }

  // ─── 2〜6. 各章を順番に生成 ───
  const sections = [];
  let prevSummary = '';
  for (let i = 0; i < chapters.length; i++) {
    const idx = i + 1;
    const ch = chapters[i];
    console.log(`[generate_script] Step ${idx + 1}/${chapters.length + 1}: chapter ${idx} "${ch.title}"`);
    const body = await callGemini(
      CHAPTER_PROMPT(topic.title, topic.category, outlineText, idx, ch.title, ch.brief, prevSummary),
    );
    sections.push({ index: idx, title: ch.title, body });
    // 次章へ渡す要約は冒頭300字でOK
    prevSummary += `第${idx}章「${ch.title}」概要: ${body.slice(0, 300).replace(/\n/g, ' ')}\n`;
  }

  // 結合
  const fullScript = sections
    .map((s) => `第${s.index}章 ${s.title}\n\n${s.body}`)
    .join('\n\n');

  const totalChars = fullScript.length;
  console.log(`[generate_script] Total script: ${totalChars} chars (${sections.length} chapters)`);

  const scriptPath = path.join(OUTPUT_DIR, `${topic.id}_script.txt`);
  await fs.writeFile(scriptPath, fullScript, 'utf-8');
  console.log(`[generate_script] Script written: ${scriptPath}`);

  state.currentTopic = topic;
  state.lastRun = new Date().toISOString();
  state.lastScriptPath = scriptPath;
  state.lastScriptChars = totalChars;
  state.lastScriptChapters = sections.map((s) => ({ index: s.index, title: s.title, chars: s.body.length }));
  await saveState(state);
  console.log('[generate_script] State updated.');
}

main().catch(err => {
  console.error('[generate_script] FAILED:', err);
  process.exit(1);
});
