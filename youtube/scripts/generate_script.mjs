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

const PROMPT_TEMPLATE = (title, category) => `あなたは「侍の美学」を体現する歴史ナレーション作家です。
以下のテーマで、YouTube向け約30分の台本を執筆してください。

【テーマ】${title}
【カテゴリ】${category}

【絶対要件】
1. **序盤30秒で強力なフック** ─ 視聴者の心臓を掴む問いかけから始める
2. **3幕構成** ─ 第一幕「導入と謎」/ 第二幕「対立と展開」/ 第三幕「結末と教訓」
3. **3-5秒ごとに視覚変化指示** ─ 各段落の冒頭に [VISUAL: ...] でカメラワーク・素材指示を明記
4. **侍の美学トーン** ─ 簡潔・凛とした言葉遣い・余白を尊ぶ・断言を恐れない
5. **約30分尺** ─ 日本語で約8000〜10000字
6. **章立て** ─ 「第一章 ◯◯」「第二章 ◯◯」のように章タイトルを付ける
7. **最後に「結語」** ─ 視聴者の人生に持ち帰れる教訓を1〜2文で凝縮

【トーンの参考】
「闇を裂く一閃の刃ーー それが、織田信長という男であった。」
「彼は、何を見ていたのか。何を、賭けていたのか。」

それでは、執筆を開始してください。`;

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

  const prompt = PROMPT_TEMPLATE(topic.title, topic.category);
  const script = await callGemini(prompt);

  const scriptPath = path.join(OUTPUT_DIR, `${topic.id}_script.txt`);
  await fs.writeFile(scriptPath, script, 'utf-8');
  console.log(`[generate_script] Script written: ${scriptPath}`);

  state.currentTopic = topic;
  state.lastRun = new Date().toISOString();
  state.lastScriptPath = scriptPath;
  await saveState(state);
  console.log('[generate_script] State updated.');
}

main().catch(err => {
  console.error('[generate_script] FAILED:', err);
  process.exit(1);
});
