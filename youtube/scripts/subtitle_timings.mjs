// youtube/scripts/subtitle_timings.mjs
// テキストを Google TTS の 5000 byte 制限に収まるよう byte 数基準で分割する。
// 自然な切れ目（。.!?！？\n）を尊重する。
//
// 2026-05-20 ROOT FIX:
//   generate_voice.mjs が `import { chunkTextByBytes } from './subtitle_timings.mjs'`
//   しているが、このファイル自体が origin/main に存在しなかったため
//   GitHub Actions で ERR_MODULE_NOT_FOUND が発生していた。
//   Run #80/#81/#83/#84 が「Generate voice」step で 1s 即死した真因。

/**
 * 文字列を UTF-8 byte 数基準で分割する。
 * 文末記号（。.!?！？\n）でなるべく自然に切る。
 * 1チャンクが maxBytes を超えないことを保証する。
 *
 * @param {string} text       入力テキスト
 * @param {number} maxBytes   1チャンクあたりの最大 UTF-8 バイト数（Google TTS は 5000 上限）
 * @returns {string[]}        分割後の文字列配列
 */
export function chunkTextByBytes(text, maxBytes = 4500) {
  if (typeof text !== 'string') {
    throw new TypeError('chunkTextByBytes: text must be a string');
  }
  if (!Number.isInteger(maxBytes) || maxBytes <= 0) {
    throw new RangeError('chunkTextByBytes: maxBytes must be a positive integer');
  }

  const cleaned = text.replace(/\r\n?/g, '\n').trim();
  if (cleaned === '') return [];

  // 1) 自然な切れ目（文末・改行）で primitive な分割
  //    句点で区切るが「。」自体は前の sentence に残す
  const sentences = [];
  {
    let buf = '';
    for (const ch of cleaned) {
      buf += ch;
      if (/[。.!?！？]/.test(ch)) {
        const trimmed = buf.trim();
        if (trimmed) sentences.push(trimmed);
        buf = '';
      } else if (ch === '\n') {
        const trimmed = buf.trim();
        if (trimmed) sentences.push(trimmed);
        buf = '';
      }
    }
    const trimmed = buf.trim();
    if (trimmed) sentences.push(trimmed);
  }

  // 2) sentence を貪欲に集めて maxBytes に収まる chunk を作る
  const chunks = [];
  let current = '';
  let currentBytes = 0;

  for (const s of sentences) {
    const sBytes = Buffer.byteLength(s, 'utf8');

    // 単一 sentence が maxBytes を超えるケース → 強制的に文字単位で分割
    if (sBytes > maxBytes) {
      if (current) {
        chunks.push(current);
        current = '';
        currentBytes = 0;
      }
      for (const piece of splitOversize(s, maxBytes)) {
        chunks.push(piece);
      }
      continue;
    }

    const joiner = current ? '' : '';
    const joinerBytes = Buffer.byteLength(joiner, 'utf8');
    const projected = currentBytes + joinerBytes + sBytes;

    if (projected <= maxBytes) {
      current = current ? current + joiner + s : s;
      currentBytes = projected;
    } else {
      // flush current, start new
      if (current) chunks.push(current);
      current = s;
      currentBytes = sBytes;
    }
  }
  if (current) chunks.push(current);

  return chunks;
}

/**
 * 単一の sentence が maxBytes を超える場合の強制分割。
 * 文字単位で切るが、UTF-8 のマルチバイト境界は壊さない。
 *
 * @param {string} text
 * @param {number} maxBytes
 * @returns {string[]}
 */
function splitOversize(text, maxBytes) {
  const out = [];
  let buf = '';
  let bufBytes = 0;
  for (const ch of text) {
    const chBytes = Buffer.byteLength(ch, 'utf8');
    if (bufBytes + chBytes > maxBytes) {
      if (buf) out.push(buf);
      buf = ch;
      bufBytes = chBytes;
    } else {
      buf += ch;
      bufBytes += chBytes;
    }
  }
  if (buf) out.push(buf);
  return out;
}
