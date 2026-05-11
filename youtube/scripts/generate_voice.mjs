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

const ELEVENLABS_API_KEY = process.env.ELEVENLABS_API_KEY;
const ELEVENLABS_VOICE_ID = process.env.ELEVENLABS_VOICE_ID;
const ELEVENLABS_MODEL = process.env.ELEVENLABS_MODEL || 'eleven_multilingual_v2';

// 台本から[VISUAL: ...]や章マーカーを除いて純粋な読み上げテキストにする
function stripVisualDirectives(text) {
  return text
    .replace(/\[VISUAL:[^\]]*\]/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
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

  const audio = await callElevenLabs(cleanText);
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
