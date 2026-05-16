// youtube/scripts/generate_voice.mjs
// ElevenLabs APIで台本テキストからナレーション音声を生成
// input: youtube/output/<id>_script.txt（state.json.currentTopic.id から特定）
// output: youtube/output/<id>_voice.mp3

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fetch from 'node-fetch';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

// ─── 主TTS: Google Cloud Text-to-Speech ─────────────
// Google Cloud Free Tierが100万字/月まで無料。ElevenLabsはGitHub Actions IPを
// VPN扱いするためFree Tier無効化される問題を回避。
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY;
const GOOGLE_TTS_VOICE = process.env.GOOGLE_TTS_VOICE || 'ja-JP-Neural2-B'; // 女性・落ち着いた声（30代）
const GOOGLE_TTS_SPEAKING_RATE = parseFloat(process.env.GOOGLE_TTS_SPEAKING_RATE || '1.0');
const GOOGLE_TTS_PITCH = parseFloat(process.env.GOOGLE_TTS_PITCH || '0.0'); // 標準ピッチ (30代女性向け)

// ─── 旧TTS: ElevenLabs (fallback) ─────────────
const ELEVENLABS_API_KEY = process.env.ELEVENLABS_API_KEY;
const ELEVENLABS_VOICE_ID = process.env.ELEVENLABS_VOICE_ID;
const ELEVENLABS_MODEL = process.env.ELEVENLABS_MODEL || 'eleven_multilingual_v2';
const USE_ELEVENLABS = process.env.USE_ELEVENLABS === 'true';

// 台本から読み上げ不要な装飾（マークダウン・ト書き）を全部剥がして純粋な日本語に
function stripVisualDirectives(text) {
  let t = text;
  // 1. ト書き・舞台指示 [VISUAL: ...] [BGM: ...] [SE: ...] [...] 全部消す
  t = t.replace(/\[[^\]\n]*\]/g, '');
  // 2. マークダウン見出し `## タイトル` 行ごと削除（章番号は別途残したいので注意）
  t = t.replace(/^#{1,6}\s.*$/gm, '');
  // 3. 太字・斜体マーカー **text** *text* _text_ を中身だけ残す
  t = t.replace(/\*\*\*?([^*]+)\*\*\*?/g, '$1');
  t = t.replace(/\*([^*]+)\*/g, '$1');
  t = t.replace(/_([^_]+)_/g, '$1');
  // 4. 残ったアスタリスク・アンダースコア単独を消す
  t = t.replace(/[*_]+/g, '');
  // 5. ハッシュタグ `#日本史` を読み上げない
  t = t.replace(/#[^\s#]+/g, '');
  // 6. 「ナレーション:」「ナレーター:」「BGM:」「SE:」「効果音:」等のラベル削除（行頭近辺）
  t = t.replace(/^\s*(ナレーション|ナレーター|BGM|SE|効果音|台本|タイトル|オープニング|エンディング|エピローグ|プロローグ|テロップ|字幕)\s*[:：]\s*/gm, '');
  // 7. URL や https? を読み上げない
  t = t.replace(/https?:\/\/\S+/g, '');
  // 8. バックティック・カギカッコ外のメタ括弧 (例: 「※注」) は残してOK。
  // 9. 連続改行整理
  t = t.replace(/\n{3,}/g, '\n\n');
  return t.trim();
}

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

/** Google Cloud TTS: 5000バイト/リクエスト制限があるので分割合成→結合 */
async function callGoogleTTS(text) {
  if (!GOOGLE_API_KEY) {
    throw new Error('GOOGLE_API_KEY (or GEMINI_API_KEY) が未設定');
  }
  // 句点 or 改行で分割し、約4000バイト以下のチャンクにまとめる
  const sentences = text.split(/(?<=[。\n！？])/);
  const chunks = [];
  let cur = '';
  for (const s of sentences) {
    const tentative = cur + s;
    if (Buffer.byteLength(tentative, 'utf8') > 4500) {
      if (cur) chunks.push(cur);
      cur = s;
    } else {
      cur = tentative;
    }
  }
  if (cur) chunks.push(cur);
  console.log(`[generate_voice] Google TTS: ${chunks.length} chunks`);

  const url = `https://texttospeech.googleapis.com/v1/text:synthesize?key=${GOOGLE_API_KEY}`;
  const audioBufs = [];
  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i];
    const body = {
      input: { text: chunk },
      voice: { languageCode: 'ja-JP', name: GOOGLE_TTS_VOICE },
      audioConfig: {
        audioEncoding: 'MP3',
        speakingRate: GOOGLE_TTS_SPEAKING_RATE,
        pitch: GOOGLE_TTS_PITCH,
      },
    };
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Google TTS API error ${res.status}: ${errText}`);
    }
    const json = await res.json();
    if (!json.audioContent) {
      throw new Error(`Google TTS returned no audioContent for chunk ${i + 1}`);
    }
    audioBufs.push(Buffer.from(json.audioContent, 'base64'));
    console.log(`[generate_voice]   chunk ${i + 1}/${chunks.length}: ${audioBufs[i].length} bytes`);
  }
  return Buffer.concat(audioBufs);
}

async function callElevenLabs(text) {
  if (!ELEVENLABS_API_KEY || !ELEVENLABS_VOICE_ID) {
    console.warn('[generate_voice] ElevenLabs credentials not set — writing stub mp3 placeholder.');
    return Buffer.from('STUB_AUDIO_PLACEHOLDER');
  }
  const url = `https://api.elevenlabs.io/v1/text-to-speech/${ELEVENLABS_VOICE_ID}`;
  const body = {
    text,
    model_id: ELEVENLABS_MODEL,
    voice_settings: {
      stability: 0.55,
      similarity_boost: 0.75,
      style: 0.35,
      use_speaker_boost: true,
    },
  };
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'xi-api-key': ELEVENLABS_API_KEY,
      'Content-Type': 'application/json',
      'Accept': 'audio/mpeg',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`ElevenLabs API error ${res.status}: ${errText}`);
  }
  const arrayBuf = await res.arrayBuffer();
  return Buffer.from(arrayBuf);
}

async function synthesize(text) {
  if (USE_ELEVENLABS) {
    console.log('[generate_voice] Engine: ElevenLabs (USE_ELEVENLABS=true)');
    return callElevenLabs(text);
  }
  console.log('[generate_voice] Engine: Google Cloud TTS');
  return callGoogleTTS(text);
}

async function main() {
  const state = await loadState();
  const topic = state.currentTopic;
  if (!topic) {
    console.log('[generate_voice] No currentTopic in state. Skip.');
    return;
  }

  const scriptPath = path.join(OUTPUT_DIR, `${topic.id}_script.txt`);
  const voicePath = path.join(OUTPUT_DIR, `${topic.id}_voice.mp3`);

  const scriptRaw = await fs.readFile(scriptPath, 'utf-8');
  const cleanText = stripVisualDirectives(scriptRaw);

  console.log(`[generate_voice] Synthesizing voice for [${topic.id}] ${topic.title}`);
  console.log(`[generate_voice] Text length: ${cleanText.length} chars`);

  const audio = await synthesize(cleanText);
  await fs.writeFile(voicePath, audio);
  console.log(`[generate_voice] Voice written: ${voicePath}`);

  state.lastVoicePath = voicePath;
  state.lastVoiceAt = new Date().toISOString();
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
}

main().catch(err => {
  console.error('[generate_voice] FAILED:', err);
  process.exit(1);
});
