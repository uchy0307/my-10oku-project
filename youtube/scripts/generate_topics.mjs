// youtube/scripts/generate_topics.mjs
// Gemini で topics.json を自動補充
//
// 動作:
//   1. topics.json と state.json を読む
//   2. 未処理テーマ数を計算（topics.length - state.processed.length）
//   3. 未処理数が閾値（GENERATE_THRESHOLD・既定10）未満なら Gemini に追加生成依頼
//   4. 既存全テーマを「重複禁止リスト」として送り、新規50本生成
//   5. パース→既存と重複しないものだけ追加→topics.json 上書き

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
// 2026-05-19: 429 / 404 quota 対策・確認済み正しいモデル名のみ
const GEMINI_FALLBACK_MODELS = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-flash-8b', 'gemini-2.5-flash-lite'];
const _gemini_endpoint = (model) => `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
const GEMINI_ENDPOINT = _gemini_endpoint(GEMINI_MODEL);

const GENERATE_THRESHOLD = parseInt(process.env.TOPIC_THRESHOLD || '10', 10);
const BATCH_SIZE = parseInt(process.env.TOPIC_BATCH || '50', 10);
const CATEGORIES = ['人物軸', '合戦軸', '文化軸', '経済軸', '地理軸', '風俗軸'];

async function loadTopics() {
  try {
    return JSON.parse(await fs.readFile(TOPICS_FILE, 'utf-8'));
  } catch {
    return [];
  }
}

async function saveTopics(topics) {
  await fs.writeFile(TOPICS_FILE, JSON.stringify(topics, null, 2) + '\n', 'utf-8');
}

async function loadState() {
  try {
    return JSON.parse(await fs.readFile(STATE_FILE, 'utf-8'));
  } catch {
    return { processed: [], lastRun: null, currentTopic: null };
  }
}

function nextIdStart(existing) {
  let max = 0;
  for (const t of existing) {
    const n = parseInt(t.id, 10);
    if (!isNaN(n) && n > max) max = n;
  }
  return max + 1;
}

function buildPrompt(existingTitles, count, categories) {
  return `あなたは日本史エンタメYouTubeチャンネル「侍・戦国・幕末チャンネル」のディレクター。
これから30分尺ナレーション動画のテーマを${count}本一気に提案する。

【チャンネル軸（厳守）】
- 対象時代: 戦国・安土桃山・江戸・幕末・明治初期（平安以前は不可）
- 対象ジャンル: 既存テーマと同じ「人物軸・合戦軸・文化軸・経済軸・地理軸・風俗軸」のみ
- それ以外の時代やジャンル拡張は厳禁
- 視聴者は40代以上の歴史好き男女
- 「侍の美学」「凛とした断言」「人物の覚悟」「合戦の真実」を切り口にする
- 教育より物語性重視。重厚なナレーションで30分視聴を保つ題材
- 風俗軸の場合：庶民生活・遊郭・刑罰・性風俗・貧民・芸能等の人間ドラマを切り口にする。ただしYouTubeコミュニティガイドライン抵触の過度な性的・暴力的表現は避け、社会制度・経済・心理の角度から描くこと

【既存テーマ（${existingTitles.length}本・全て重複禁止）】
${existingTitles.map((t, i) => `${i + 1}. ${t}`).join('\n')}

【出力ルール（厳守）】
- ${count}本提案
- 重複NG。既存テーマと言い回しを変えても被るものはNG
- カテゴリは以下から自由に選択: ${categories.join('・')}
- タイトル例:「織田信長 桶狭間の真実」「葉隠 武士道とは死ぬことと見つけたり」
- 1行1題材で以下の厳密フォーマット:
\`\`\`
タイトル / カテゴリ
\`\`\`
- マークダウン記号(*,#)・連番・括弧説明・前置き禁止
- ${count}行ぴったり出力

それでは執筆開始。`;
}

async function callGemini(prompt, attempt = 1, modelIdx = 0) {
  if (!GEMINI_API_KEY) throw new Error('GEMINI_API_KEY 未設定');
  const modelsChain = [GEMINI_MODEL, ...GEMINI_FALLBACK_MODELS.filter(m => m !== GEMINI_MODEL)];
  const currentModel = modelsChain[modelIdx] || GEMINI_MODEL;
  const url = `${_gemini_endpoint(currentModel)}?key=${GEMINI_API_KEY}`;
  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.9,
      thinkingConfig: { thinkingBudget: 0 },
      maxOutputTokens: 16384,
      responseMimeType: 'text/plain',
    },
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
    // 429 / 404 → 次モデルへ fallback
    if ((res.status === 429 || res.status === 404) && modelIdx < modelsChain.length - 1) {
      console.warn(`[generate_topics] model=${currentModel} ${res.status}; fallback to next model`);
      return callGemini(prompt, 1, modelIdx + 1);
    }
    if (res.status === 503 && attempt < 3) {
      const wait = Math.min(60, Math.pow(2, attempt) * 10);
      console.warn(`[generate_topics] model=${currentModel} 503 retry in ${wait}s`);
      await new Promise((r) => setTimeout(r, wait * 1000));
      return callGemini(prompt, attempt + 1, modelIdx);
    }
    throw new Error(`Gemini API error ${res.status} on model=${currentModel}: ${errText}`);
  }
  const json = await res.json();
  const text = json?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error('Gemini returned empty content');
  return text;
}

function parseLines(text, validCats) {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  const items = [];
  const catSet = new Set(validCats);
  for (const line of lines) {
    // "タイトル / カテゴリ" or "タイトル / カテゴリ軸"
    const m = line.match(/^(.+?)\s*[/／]\s*(.+?)$/);
    if (!m) continue;
    let title = m[1].trim();
    let category = m[2].trim();
    // 余計な記号除去
    title = title.replace(/^[*•・\-\d.\s]+/, '').replace(/\*+/g, '').trim();
    category = category.replace(/\*+/g, '').trim();
    if (!title || title.length < 4) continue;
    // カテゴリ補正
    if (!catSet.has(category) && !category.endsWith('軸')) category = category + '軸';
    if (!catSet.has(category)) {
      // 一致しなかったら先頭一致を試す
      const hit = validCats.find((c) => category.includes(c.replace('軸', '')));
      if (hit) category = hit;
      else category = validCats[0];
    }
    items.push({ title, category });
  }
  return items;
}

async function main() {
  const existing = await loadTopics();
  const state = await loadState();
  const processed = new Set(state.processed || []);
  const unprocessed = existing.filter((t) => !processed.has(t.id));
  console.log(`[generate_topics] existing=${existing.length} processed=${processed.size} unprocessed=${unprocessed.length}`);

  if (unprocessed.length >= GENERATE_THRESHOLD) {
    console.log(`[generate_topics] unprocessed >= threshold(${GENERATE_THRESHOLD}). Skip.`);
    return;
  }

  console.log(`[generate_topics] BELOW threshold. Generating ${BATCH_SIZE} new topics...`);

  const existingTitles = existing.map((t) => t.title);
  const prompt = buildPrompt(existingTitles, BATCH_SIZE, CATEGORIES);
  const raw = await callGemini(prompt);
  const parsed = parseLines(raw, CATEGORIES);
  console.log(`[generate_topics] parsed ${parsed.length} candidates from Gemini`);

  // 重複除去
  const existingSet = new Set(existingTitles);
  const fresh = parsed.filter((p) => !existingSet.has(p.title));
  console.log(`[generate_topics] ${fresh.length} unique additions after dedup`);

  if (fresh.length === 0) {
    console.warn('[generate_topics] No new unique topics produced. Aborting.');
    return;
  }

  let nextId = nextIdStart(existing);
  const added = fresh.map((p) => ({ id: String(nextId++).padStart(3, '0'), title: p.title, category: p.category }));
  const updated = [...existing, ...added];
  await saveTopics(updated);
  console.log(`[generate_topics] DONE. topics.json: ${existing.length} -> ${updated.length}`);
}

main().catch((err) => {
  console.error('[generate_topics] FAILED:', err);
  process.exit(1);
});
