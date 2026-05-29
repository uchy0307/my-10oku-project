// scripts/build_description.mjs
// YouTube 用 リッチ説明文ビルダー
// usage: const desc = buildDescription({ kind, spec, audioDur, channel })

const BGM_BLOCK = `▼BGM提供
・音楽素材MusMus様 → https://musmus.main.jp/
・魔王魂様 → https://maoudamashii.jokersounds.com/
・PeriTune様 → https://peritune.com/
・DOVA-SYNDROME様 → https://dova-s.jp/
・甘茶の音楽工房様 → http://amachamusic.chagasi.com/
・ポケットサウンド様 → https://pocket-se.info/`;

const ILLUST_BLOCK = `▼イラスト・画像提供
・Wikimedia Commons → https://commons.wikimedia.org/
・Adobe Stock → https://stock.adobe.com/jp/
・ACイラスト → https://www.ac-illust.com/`;

const DIVIDER = '＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝';

const KIND_HASHTAGS = {
  history: ['戦国時代', '日本史', '歴史', '侍'],
  psych:   ['心理学', '人間関係', '恋愛心理', '大人の心理学'],
  shorts:  ['Shorts', '日本史', '戦国時代'],
  otona_shorts: ['Shorts', '心理学', '恋愛心理'],
};

function fmtTime(sec) {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(ss).padStart(2,'0')}`;
  return `${m}:${String(ss).padStart(2,'0')}`;
}

/**
 * Generate timestamps from chapters proportional to text length.
 * @param {Array} chapters - [{title, text}, ...]
 * @param {number} totalDur - audio duration seconds
 * @returns {Array<{time: number, label: string}>}
 */
function buildTimestamps(chapters, totalDur) {
  if (!chapters || chapters.length === 0) return [];
  // text length 比例
  const lengths = chapters.map(c => (c.text || '').length || 1);
  const totalLen = lengths.reduce((a, b) => a + b, 0);
  let acc = 0;
  const out = [];
  out.push({ time: 0, label: chapters[0].title || 'オープニング' });
  for (let i = 0; i < chapters.length - 1; i++) {
    acc += lengths[i];
    const t = (acc / totalLen) * totalDur;
    out.push({ time: t, label: chapters[i + 1].title || `第${i+2}章` });
  }
  return out;
}

/**
 * @param {Object} opts
 * @param {'history'|'psych'|'shorts'|'otona_shorts'} opts.kind
 * @param {Object} opts.spec  - script JSON parsed
 * @param {number} opts.audioDur - seconds
 * @returns {string}
 */
export function buildDescription({ kind, spec, audioDur = 0 }) {
  const isShorts = kind === 'shorts' || kind === 'otona_shorts';
  const hashtags = (spec.tags && spec.tags.length ? spec.tags : KIND_HASHTAGS[kind] || []).slice(0, 8);
  const hashtagLine = hashtags.map(t => `#${t.replace(/^#/, '')}`).join(' ');

  // Lead
  const leadRaw = spec.description || spec.intro || spec.summary || '';
  const lead = leadRaw.trim() || (
    isShorts
      ? `${spec.title}\n\n短時間でわかる核心ポイント。`
      : `${spec.title}\n\n本動画では、テーマを掘り下げて解説します。`
  );

  // Shorts はシンプル版
  if (isShorts) {
    return [
      lead,
      '',
      hashtagLine,
    ].join('\n').slice(0, 4500);
  }

  // Long-form: フル構成
  const blocks = [];
  blocks.push(lead);
  blocks.push('');
  blocks.push(DIVIDER);

  // 目次 (timestamps)
  const stamps = buildTimestamps(spec.chapters || [], audioDur || 0);
  if (stamps.length > 0 && audioDur > 60) {
    blocks.push('▼目次');
    for (const s of stamps) {
      blocks.push(`${fmtTime(s.time)} ${s.label}`);
    }
    blocks.push('');
    blocks.push(DIVIDER);
  }

  // 参考文献 (spec.references があれば使う、無ければデフォルト)
  if (Array.isArray(spec.references) && spec.references.length > 0) {
    blocks.push('▼参考文献');
    for (const r of spec.references.slice(0, 12)) {
      if (typeof r === 'string') blocks.push(`●${r}`);
      else if (r.title) blocks.push(`●${r.title}${r.url ? ` - ${r.url}` : ''}`);
    }
    blocks.push('');
    blocks.push(DIVIDER);
  }

  blocks.push(BGM_BLOCK);
  blocks.push('');
  blocks.push(ILLUST_BLOCK);
  blocks.push('');
  blocks.push(DIVIDER);
  blocks.push(hashtagLine);

  return blocks.join('\n').slice(0, 4500);
}

export default buildDescription;
