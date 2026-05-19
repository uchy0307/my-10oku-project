// youtube/scripts/generate_script.mjs
// Gemini APIで「侍の美学」トーンの30分台本を生成
// input: youtube/topics.json から次の未投稿テーマ
// output: youtube/output/<id>_script.txt
//
// Phase D: カテゴリ別 prompt 分岐
//   合戦軸 → 合戦そのものを主役（武将個人の伝記禁止）
//   人物軸 → 武将個人の生涯・思想を主役
//   文化軸/経済軸/地理軸/風俗軸 → 各テーマそのものを主役

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
// 2026-05-19: 完全無料化軸 → default を flash に変更（Free Tier RPD 多）
// gemini-2.5-pro は Free Tier 制限が厳しく即429。env で上書きする場合のみ pro 使用可
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
// 2026-05-19: 429 quota exhaust 対策・確認済み正しいモデル名のみ
const GEMINI_FALLBACK_MODELS = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-flash-8b', 'gemini-2.5-flash-lite'];
const _gemini_endpoint = (model) => `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
const GEMINI_ENDPOINT = _gemini_endpoint(GEMINI_MODEL);

// 章本文の最低文字数（これを下回ったら章単位で再生成）
const CHAPTER_MIN_CHARS = 8000;
const CHAPTER_MAX_RETRIES = 2;

// ─── カテゴリ別執筆方針＋出力例 (Phase D root-fix) ───
export function getCategoryGuidance(category, title) {
  switch (category) {
    case '合戦軸':
      return {
        guidance: `【重要・カテゴリ別執筆方針】(Phase D2 強化版)
このテーマは「合戦軸」である。**合戦・事件そのものを主役**として描け。
- 戦闘の経過、戦術、両軍の配置、決定的瞬間、地形、武器、戦後への影響を中心に
- 武将個人の生涯・幼少期・思想史に**深入りしてはならない**（必要最小限の人物紹介のみ可）
- タイトル「${title}」に直接含まれない武将（例: 上杉謙信、伊達政宗 等）を**主役にしてはならない**
- **合戦名そのもの**（例: 長篠、関ヶ原、桶狭間）を**全章合計で最低15回以上**反復せよ
- **タイトル内の武器・象徴語**（例: 鉄砲、刀剣）を**全章合計で最低10回以上**反復せよ
- 主役の取り違え（例: 「長篠の戦い」題目で武田信玄の伝記化）は**絶対禁止**。
  「長篠」題目では織田信長×徳川家康連合 vs 武田勝頼の合戦そのものを描く。
  「関ヶ原」題目では東軍×西軍の合戦そのものを描く。`,
        outlineExample: `【出力例（テーマが「長篠の戦い 鉄砲が変えた戦場」の場合）】
第一章 天正三年、長篠城の包囲
武田勝頼率いる一万五千が三河の長篠城を囲む。籠城戦の限界と、織田信長・徳川家康への急報。
鉄砲三千挺を運ぶ織田軍の進発。設楽原（したらがはら）への布陣。

第二章 馬防柵と鉄砲三段撃ちの仕掛け
設楽原に築かれた三重の馬防柵。鉄砲足軽の配置。武田の騎馬軍団に対する陣形の意味。
鉄砲を雨で湿らせない工夫と、火縄の管理。

第三章 五月二十一日、開戦の朝
武田勝頼の決断、突撃命令。山県昌景・馬場信春らの突進と、馬防柵越しの一斉射撃。
鉄砲三段撃ちの実際。武田騎馬隊が次々と倒れる長篠の野。

第四章 武田の崩壊と戦場の転換
名将の戦死と、勝頼の退却。鉄砲が騎馬の優位を覆した瞬間。長篠城の解放。

第五章 鉄砲が変えた戦場、そして時代
長篠の戦いがその後の戦国戦術に与えた影響。鉄砲中心の集団戦への移行と、武田家の衰亡。

【出力例（テーマが「関ヶ原の戦い 天下分け目の六時間」の場合）】
第一章 慶長五年、関ヶ原への道
家康と三成、東西両軍の集結。関ヶ原という盆地が決戦地に選ばれた理由。

第二章 関ヶ原、霧の中の布陣
東軍七万、西軍八万。関ヶ原の小早川・島津・大谷の位置取り。

第三章 関ヶ原、運命の六時間
開戦から小早川秀秋の裏切り、西軍崩壊まで。関ヶ原の地形が勝敗を決した瞬間。

第四章 関ヶ原の戦後処理
石田三成の処刑、関ヶ原で散った将たち。

第五章 関ヶ原が決した天下
関ヶ原がもたらした徳川幕府二百六十年の礎。`,
      };
    case '人物軸':
      return {
        guidance: `【重要・カテゴリ別執筆方針】
このテーマは「人物軸」である。**タイトルの人物そのものの生涯・思想・転機**を主役にせよ。
- 人物の出生・成長・代表的事件・思想・最期を骨子に
- 他人物（敵将等）は脇役として扱う`,
        outlineExample: `【出力例（テーマが「織田信長 桶狭間の真実」の場合）】
第一章 闇を裂く問いかけ
桶狭間の戦いとは何であったか、視聴者に最初の謎を投げかける。
信長の出生と尾張の地政学的背景を簡潔に提示。

第二章 ……（信長の少年期と「うつけ」の真相）
第三章 ……（桶狭間決戦と信長像の確立）
第四章 ……（その後の信長の歩み）
第五章 ……（信長から学ぶ侍の美学）`,
      };
    case '文化軸':
      return {
        guidance: `【重要・カテゴリ別執筆方針】
このテーマは「文化軸」である。**文化・芸能・思想そのもの**を主役にせよ。
- 起源・発展・象徴的作品・実践者を順に描く
- 一人の人物の伝記に偏らない`,
        outlineExample: '',
      };
    case '経済軸':
      return {
        guidance: `【重要・カテゴリ別執筆方針】
このテーマは「経済軸」である。**制度・産業・流通そのもの**を主役にせよ。
- 制度の仕組み、当事者の動機、社会への影響を順に描く
- 単一人物の伝記にしてはならない`,
        outlineExample: '',
      };
    case '地理軸':
      return {
        guidance: `【重要・カテゴリ別執筆方針】
このテーマは「地理軸」である。**土地・街道・拠点そのもの**を主役にせよ。
- 地勢・歴史的役割・象徴的事件・現代に残る痕跡を順に
- 単一人物の伝記にしてはならない`,
        outlineExample: '',
      };
    case '風俗軸':
      return {
        guidance: `【重要・カテゴリ別執筆方針】
このテーマは「風俗軸」である。**当時の生活・慣習・職業そのもの**を主役にせよ。
- 当事者群像、典型的1日、社会的位置づけ、現代との差異を順に
- 単一人物の伝記にしてはならない`,
        outlineExample: '',
      };
    default:
      return {
        guidance: `【執筆方針】
テーマ「${title}」そのものを主役にせよ。単一人物の伝記に偏ってはならない。`,
        outlineExample: '',
      };
  }
}

// ─── プロンプト群 (Phase D: カテゴリ別) ───
const OUTLINE_PROMPT = (title, category) => {
  const { guidance, outlineExample } = getCategoryGuidance(category, title);
  return `あなたは「侍の美学」を体現する歴史ナレーション作家。
以下のテーマで30分のYouTube動画台本の「章立てアウトライン」を作成せよ。

【テーマ】${title}
【カテゴリ】${category}

${guidance}

【出力ルール】
- 6章構成。各章タイトル（10〜20字）と、その章で語る要点を2〜4行
- マークダウン記号（**, ##, *）禁止
- 「ナレーション:」「BGM:」「VISUAL:」等のラベル禁止
- 出力は純粋な日本語の章タイトルと要点のみ

${outlineExample}

それでは執筆を開始せよ。`;
};

// Phase D2 強化: 合戦軸専用 prompt 追加 instruction
const BATTLE_AXIS_ADDENDUM = (title) => `
【合戦軸 特別要件】（このカテゴリでは絶対遵守）
- タイトルに含まれる戦の名前（例：「長篠の戦い」なら「長篠」）を、本章本文中で必ず5回以上明示せよ。代名詞や省略で逃げない。
- 合戦が起きた年号（西暦・元号の両方）を最低1回明記せよ。
- 両軍の主将名を最低2回ずつ明記せよ（例：長篠なら織田信長・徳川家康／武田勝頼）。
- 合戦の主要地名（例：長篠なら三河国設楽原・連吾川・鳶ヶ巣山）を本文中に最低2回登場させよ。
- その合戦に直接参加していない人物（武田信玄など故人）の伝記に脱線してはならない。

【正しいナレーション例（長篠の戦い・抜粋）】
時は天正三年、西暦千五百七十五年五月二十一日。三河国設楽原に、織田信長・徳川家康の連合軍と、武田勝頼率いる武田の精鋭騎馬軍団が対峙していた。長篠城を巡る攻防は、ここに至って全面決戦の様相を呈していた。連吾川を挟む両岸に、信長は三千挺の鉄砲と、それを守る馬防柵を幾重にも巡らせた。長篠の戦い——それは、騎馬の時代が、火薬の時代へと塗り替えられた瞬間であった。

【正しいナレーション例（桶狭間の戦い・抜粋）】
永禄三年、西暦千五百六十年五月十九日。尾張国桶狭間。今川義元率いる二万五千の軍勢が、織田信長わずか三千の手勢に討たれた。豪雨と地形の妙、信長の決断——桶狭間の戦いは、戦国の常識を一夜にして覆した。

【正しいナレーション例（関ヶ原の戦い・抜粋）】
慶長五年、西暦千六百年九月十五日。美濃国関ヶ原。徳川家康率いる東軍と、石田三成率いる西軍が、天下を二分する決戦に臨んだ。小早川秀秋の寝返りが戦局を一気に傾け、関ヶ原の戦いはわずか一日で天下分け目の決着を見たのである。

`;

const CHAPTER_PROMPT = (title, category, outline, chapterIndex, chapterTitle, chapterBrief, prevSummary) => {
  const { guidance } = getCategoryGuidance(category, title);
  const battleConstraint = category === '合戦軸'
    ? `\n11. 「合戦軸」のため、武将個人の伝記的記述（出生、幼少期、思想）に偏らない。タイトル「${title}」に含まれる**合戦名**を**この章だけで最低3回**、武器・象徴語を最低2回登場させよ。
12. 主役の取り違え禁止: タイトル「${title}」に明記されない武将（例: 上杉謙信、武田信玄等）を主役格として扱ってはならない。`
    : '';
  return `あなたは「侍の美学」を体現する歴史ナレーション作家。
全5章構成の歴史ナレーション動画の「第${chapterIndex}章」本文を執筆せよ。

【動画テーマ】${title}
【カテゴリ】${category}
${guidance}

【全体アウトライン】
${outline}

【今書く章】
第${chapterIndex}章 ${chapterTitle}
要点: ${chapterBrief}

${prevSummary ? `【前章までの要約】\n${prevSummary}\n` : ''}

${category === '合戦軸' ? BATTLE_AXIS_ADDENDUM(title) : ''}
【絶対要件】
1. 文字数: 日本語で最低8000字、理想10000字（必ず満たすこと、短い回答は不採用）（句読点・改行含む）。8000字未満は不合格。指定字数を必ず満たすこと。
2. 純粋なナレーション本文のみ。マークダウン記号（**, ##, *, _, バッククォート）禁止
3. 「ナレーション:」「ナレーター:」「BGM:」「SE:」「VISUAL:」「テロップ:」等のラベル禁止
4. ハッシュタグ（#）禁止
5. 括弧書き（注釈・ト書き・カメラ指示）禁止
6. 「※」「→」等の記号は最小限
7. 章タイトルも省略。本文だけ書く
8. 段落は2〜4行、改行で区切る
9. 侍の美学トーン: 凛とした断言・余白を尊ぶ・短文と長文のリズム
10. テーマ「${title}」から逸脱しない。タイトルのキーワードを必ず複数回登場させる${battleConstraint}

【トーン参考】
「闇を裂く一閃の刃ーー それが、織田信長という男であった。」
「彼は、何を見ていたのか。何を、賭けていたのか。」

【長文サンプル（このリズム・密度・字数感を必ず満たすこと。短い章は不採用）】
彼が見ていたのは、未来ではなかった。彼が見ていたのは、いま、ここに置かれた一手の重みだった。火縄銃の銃身に映る篝火の揺らぎ、湿った草の匂い、馬のいななき、夜半の風に乗って届く敵陣の旗の音——そのすべてを、彼は自らの体の延長として聴いていた。三千の兵を、二万五千の本陣に向けて放つ。常識から見れば、狂気。だが彼の中では、極めて冷たい算術であった。地形、天候、相手の油断、士気の臨界点。すべての変数を秤にかけ、最小の力で最大の崩壊を引き起こす一閃を、信長は数日かけて磨いていた。雨は静かに止みかけていた。義元の本陣まで、わずか数百歩。

第${chapterIndex}章の本文を、純粋なナレーションとしてのみ出力せよ。`;
};

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
}

export async function loadState() {
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

export async function loadTopics() {
  const raw = await fs.readFile(TOPICS_FILE, 'utf-8');
  return JSON.parse(raw);
}

// Phase D: currentTopic が明示されていれば優先（workflow_dispatch input.target で上書き可能）
export function pickNextTopic(topics, state) {
  // 1) state.currentTopic.id が processed に無く topics に存在すれば優先
  if (state.currentTopic && state.currentTopic.id) {
    const explicit = topics.find(t => String(t.id) === String(state.currentTopic.id));
    if (explicit && !(state.processed || []).includes(String(explicit.id))) {
      return explicit;
    }
  }
  // 2) TARGET_TOPIC_ID env も尊重（workflow_dispatch input → env で渡る）
  const target = (process.env.TARGET_TOPIC_ID || '').trim();
  if (target) {
    const tgt = topics.find(t => String(t.id) === target);
    if (tgt) return tgt;
  }
  // 3) processed に無い最初の topic を fallback
  const processed = new Set((state.processed || []).map(String));
  return topics.find(t => !processed.has(String(t.id))) || null;
}

async function callGemini(prompt, attempt = 1, modelIdx = 0) {
  if (!GEMINI_API_KEY) {
    console.warn('[generate_script] GEMINI_API_KEY not set — emitting stub script.');
    return `[STUB SCRIPT]\n${prompt}\n\n--- ここにGemini生成台本が入ります ---`;
  }
  // 2026-05-19: multi-model fallback chain
  const modelsChain = [GEMINI_MODEL, ...GEMINI_FALLBACK_MODELS.filter(m => m !== GEMINI_MODEL)];
  const currentModel = modelsChain[modelIdx] || GEMINI_MODEL;
  const url = `${_gemini_endpoint(currentModel)}?key=${GEMINI_API_KEY}`;
  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.85,
      // 2026-05-19 真因対策：flash モデルは thinking で出力 budget を食い潰すため thinkingBudget=0 に。
      // pro モデルは思考必須だが今は flash 主・thinkingBudget=0 で full output 確保。
      thinkingConfig: { thinkingBudget: 0 },
      maxOutputTokens: 32768,  // flash の実用上限・無駄に大きい値は逆効果
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
    // 429 quota exhaust → 次のモデルへ即 fallback
    if (res.status === 429 && modelIdx < modelsChain.length - 1) {
      console.warn(`[generate_script] model=${currentModel} 429 quota; falling back to next model`);
      return callGemini(prompt, 1, modelIdx + 1);
    }
    // 503 / 5xx は一時的過負荷。指数バックオフで最大3回リトライ（同じモデル）
    if ((res.status === 503 || res.status === 500 || res.status === 502 || res.status === 504) && attempt < 3) {
      const waitSec = Math.min(60, Math.pow(2, attempt) * 10);
      console.warn(`[generate_script] model=${currentModel} ${res.status} retryable. wait ${waitSec}s attempt ${attempt + 1}`);
      await new Promise((r) => setTimeout(r, waitSec * 1000));
      return callGemini(prompt, attempt + 1, modelIdx);
    }
    // 404 (model not found) → 次のモデルへ
    if (res.status === 404 && modelIdx < modelsChain.length - 1) {
      console.warn(`[generate_script] model=${currentModel} 404 not found; switching to next model`);
      return callGemini(prompt, 1, modelIdx + 1);
    }
    throw new Error(`Gemini API error ${res.status} on model=${currentModel}: ${errText}`);
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
    if (attempt < 2) {
      console.warn('[generate_script] empty text. Retrying...');
      return callGemini(prompt, attempt + 1, modelIdx);
    }
    throw new Error(`Gemini returned empty content (finishReason=${finishReason})`);
  }
  // 2026-05-19 緩和: 4000→2500 字（flash モデルは pro よりも応答が短くなりがち）
  // 同 model で 2回 retry → だめなら次 model に切替（短い応答も fallback 対象）
  if (text.length < 2500 && attempt < 2) {
    console.warn(`[generate_script] suspiciously short response (${text.length} chars, need >=2500) on model=${currentModel}. Retrying same model attempt ${attempt + 1}...`);
    return callGemini(prompt, attempt + 1, modelIdx);
  }
  if (text.length < 2500 && modelIdx < modelsChain.length - 1) {
    console.warn(`[generate_script] short response on model=${currentModel} after retries. Switching to next model.`);
    return callGemini(prompt, 1, modelIdx + 1);
  }
  return text;
}

export function parseOutline(outlineText) {
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

  console.log('[generate_script] Step 1/6: outline generation');
  const outlineText = await callGemini(OUTLINE_PROMPT(topic.title, topic.category));
  const chapters = parseOutline(outlineText);
  console.log(`[generate_script] Parsed ${chapters.length} chapters from outline`);
  if (chapters.length < 3) {
    // フォールバック: 固定6章
    chapters.splice(0, chapters.length,
      { title: '導入と謎', brief: 'テーマと最初の問いを提示' },
      { title: '対立と展開', brief: '中心人物と背景を描く' },
      { title: '深淵と決断', brief: '転換点と覚悟' },
      { title: '結末と余韻', brief: '勝敗と人々への影響' },
      { title: '結語', brief: '視聴者への教訓' },
      { title: '余韻と回帰', brief: '余白と問いの再提示で締めくくる' },
    );
  }

  const sections = [];
  let prevSummary = '';
  for (let i = 0; i < chapters.length; i++) {
    const idx = i + 1;
    const ch = chapters[i];
    console.log(`[generate_script] Step ${idx + 1}/${chapters.length + 1}: chapter ${idx} "${ch.title}"`);
    let body = await callGemini(
      CHAPTER_PROMPT(topic.title, topic.category, outlineText, idx, ch.title, ch.brief, prevSummary),
    );
    // 章本文が5000字未満なら章単位で最大2回再生成（30分長尺維持）
    for (let retry = 0; retry < CHAPTER_MAX_RETRIES && body.length < CHAPTER_MIN_CHARS; retry++) {
      console.warn(`[generate_script] chapter ${idx} body too short (${body.length} chars < ${CHAPTER_MIN_CHARS}). Regenerating (retry ${retry + 1}/${CHAPTER_MAX_RETRIES})`);
      body = await callGemini(
        CHAPTER_PROMPT(topic.title, topic.category, outlineText, idx, ch.title, ch.brief, prevSummary),
      );
    }
    if (body.length < CHAPTER_MIN_CHARS) {
      console.warn(`[generate_script] chapter ${idx} STILL short after retries (${body.length} chars). Proceeding with best effort.`);
    }
    sections.push({ index: idx, title: ch.title, body });
    prevSummary += `第${idx}章「${ch.title}」概要: ${body.slice(0, 300).replace(/\n/g, ' ')}\n`;
  }

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

const isMain = import.meta.url === `file://${process.argv[1]}` ||
               import.meta.url.endsWith(path.basename(process.argv[1] || ''));
if (isMain) {
  main().catch(err => {
    console.error('[generate_script] FAILED:', err);
    process.exit(1);
  });
}

// テストから getCategoryGuidance / pickNextTopic / parseOutline を再利用
export { OUTLINE_PROMPT, CHAPTER_PROMPT };
