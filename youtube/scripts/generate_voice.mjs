// youtube/scripts/generate_voice.mjs
// ElevenLabs / Google TTS API で台本テキストからナレーション音声を生成。
// + Phase C: 各 chunk を ffprobe で実測 → ${id}_voice_timings.json を出力。
//   compile_video.mjs はこれを使って subtitle cue を実時刻配置する（均一CPS廃止）。

import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import fetch from 'node-fetch';
import { chunkTextByBytes } from './subtitle_timings.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(ROOT, 'output');
const STATE_FILE = path.join(OUTPUT_DIR, 'state.json');

// ─── 主TTS: Google Cloud Text-to-Speech ─────────────
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY;
const GOOGLE_TTS_VOICE = process.env.GOOGLE_TTS_VOICE || 'ja-JP-Neural2-B'; // 女性・落ち着いた声（30代）
const GOOGLE_TTS_SPEAKING_RATE = parseFloat(process.env.GOOGLE_TTS_SPEAKING_RATE || '0.95');
const GOOGLE_TTS_PITCH = parseFloat(process.env.GOOGLE_TTS_PITCH || '0.0'); // 標準ピッチ (30代女性向け)

// ─── 旧TTS: ElevenLabs (fallback) ─────────────
const ELEVENLABS_API_KEY = process.env.ELEVENLABS_API_KEY;
const ELEVENLABS_VOICE_ID = process.env.ELEVENLABS_VOICE_ID;
const ELEVENLABS_MODEL = process.env.ELEVENLABS_MODEL || 'eleven_multilingual_v2';
const USE_ELEVENLABS = process.env.USE_ELEVENLABS === 'true';

// 台本から読み上げ不要な装飾（マークダウン・ト書き）を全部剥がして純粋な日本語に
export function stripVisualDirectives(text) {
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

async function loadState() {
  const raw = await fs.readFile(STATE_FILE, 'utf-8');
  return JSON.parse(raw);
}

// ──── ffprobe で MP3 buffer の duration を実測 (Phase C) ────
export function probeDurationFromBuffer(buf) {
  return new Promise((resolve, reject) => {
    const tmpPath = path.join(os.tmpdir(), `vc_${process.pid}_${Date.now()}_${Math.random().toString(36).slice(2)}.mp3`);
    fs.writeFile(tmpPath, buf).then(() => {
      const proc = spawn('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', tmpPath]);
      let out = '';
      proc.stdout.on('data', d => { out += d.toString(); });
      proc.on('error', async (e) => { await fs.unlink(tmpPath).catch(() => {}); reject(e); });
      proc.on('close', async (code) => {
        await fs.unlink(tmpPath).catch(() => {});
        if (code === 0) {
          const sec = parseFloat(out.trim());
          if (isFinite(sec)) resolve(sec);
          else reject(new Error(`ffprobe returned non-finite: ${out}`));
        } else reject(new Error(`ffprobe exited ${code}`));
      });
    }).catch(reject);
  });
}

// ──── Google Cloud TTS 1 chunk 合成 ────
async function callGoogleTTSChunk(text) {
  if (!GOOGLE_API_KEY) throw new Error('GOOGLE_API_KEY (or GEMINI_API_KEY) が未設定');
  const url = `https://texttospeech.googleapis.com/v1/text:synthesize?key=${GOOGLE_API_KEY}`;
  const body = {
    input: { text },
    voice: { languageCode: 'ja-JP', name: GOOGLE_TTS_VOICE },
    audioConfig: { audioEncoding: 'MP3', speakingRate: GOOGLE_TTS_SPEAKING_RATE, pitch: GOOGLE_TTS_PITCH },
  };
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Google TTS API error ${res.status}: ${errText}`);
  }
  const json = await res.json();
  if (!json.audioContent) throw new Error('Google TTS returned no audioContent');
  return Buffer.from(json.audioContent, 'base64');
}

// ──── Google TTS 全体: chunk 化 → 各 chunk 合成 → ffprobe で duration 実測 ────
async function callGoogleTTS(text) {
  const chunks = chunkTextByBytes(text, 4500);
  console.log(`[generate_voice] Google TTS: ${chunks.length} chunks`);
  const audioBufs = [];
  const timings = [];
  let cursorSec = 0;
  for (let i = 0; i < chunks.length; i++) {
    const buf = await callGoogleTTSChunk(chunks[i]);
    const dur = await probeDurationFromBuffer(buf);
    timings.push({
      index: i,
      text: chunks[i],
      byteLength: Buffer.byteLength(chunks[i], 'utf8'),
      audioBytes: buf.length,
      durationSec: dur,
      startSec: cursorSec,
      endSec: cursorSec + dur,
    });
    cursorSec += dur;
    audioBufs.push(buf);
    console.log(`[generate_voice]   chunk ${i+1}/${chunks.length}: ${buf.length} bytes, ${dur.toFixed(2)}s (total=${cursorSec.toFixed(2)}s)`);
  }
  return { audio: Buffer.concat(audioBufs), timings };
}

async function callElevenLabs(text) {
  if (!ELEVENLABS_API_KEY || !ELEVENLABS_VOICE_ID) {
    console.warn('[generate_voice] ElevenLabs credentials not set — writing stub mp3 placeholder.');
    const stub = Buffer.from('STUB_AUDIO_PLACEHOLDER');
    return { audio: stub, timings: [{ index: 0, text, byteLength: Buffer.byteLength(text, 'utf8'), audioBytes: stub.length, durationSec: 0, startSec: 0, endSec: 0 }] };
  }
  const url = `https://api.elevenlabs.io/v1/text-to-speech/${ELEVENLABS_VOICE_ID}`;
  const body = {
    text,
    model_id: ELEVENLABS_MODEL,
    voice_settings: { stability: 0.55, similarity_boost: 0.75, style: 0.35, use_speaker_boost: true },
  };
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'xi-api-key': ELEVENLABS_API_KEY, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`ElevenLabs API error ${res.status}: ${await res.text()}`);
  const arrayBuf = await res.arrayBuffer();
  const buf = Buffer.from(arrayBuf);
  let dur = 0;
  try { dur = await probeDurationFromBuffer(buf); }
  catch (e) { console.warn(`[generate_voice] ffprobe on ElevenLabs audio failed: ${e.message}`); }
  return { audio: buf, timings: [{ index: 0, text, byteLength: Buffer.byteLength(text, 'utf8'), audioBytes: buf.length, durationSec: dur, startSec: 0, endSec: dur }] };
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
  const timingsPath = path.join(OUTPUT_DIR, `${topic.id}_voice_timings.json`);

  const scriptRaw = await fs.readFile(scriptPath, 'utf-8');
  const cleanText = stripVisualDirectives(scriptRaw);

  console.log(`[generate_voice] Synthesizing voice for [${topic.id}] ${topic.title}`);
  console.log(`[generate_voice] Text length: ${cleanText.length} chars`);

  const { audio, timings } = await synthesize(cleanText);
  await fs.writeFile(voicePath, audio);
  await fs.writeFile(timingsPath, JSON.stringify(timings, null, 2), 'utf-8');
  const totalSec = timings.length ? timings[timings.length - 1].endSec : 0;
  console.log(`[generate_voice] Voice written: ${voicePath}`);
  console.log(`[generate_voice] Timings written: ${timingsPath} (${timings.length} chunks, total ${totalSec.toFixed(2)}s)`);

  state.lastVoicePath = voicePath;
  state.lastVoiceAt = new Date().toISOString();
  state.lastVoiceTimingsPath = timingsPath;
  state.lastVoiceTotalSec = totalSec;
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
}

const isMain = import.meta.url === `file://${process.argv[1]}` ||
               import.meta.url.endsWith(path.basename(process.argv[1] || ''));
if (isMain) {
  main().catch(err => {
    console.error('[generate_voice] FAILED:', err);
    process.exit(1);
  });
}
