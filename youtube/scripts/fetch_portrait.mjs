// youtube/scripts/fetch_portrait.mjs
// Wikipedia / Wikimedia Commons から実在の人物肖像・関連画像を取得するユーティリティ。
//
// 公開関数:
//   fetchWikiImage(query, { lang='ja' }) -> { buffer, sourceUrl, pageTitle } | null
//
// 処理:
//   1. Wikipedia search API で query を検索 -> 最初のヒットの page title
//   2. REST summary API で originalimage / thumbnail.source を取得
//   3. その画像を fetch して Buffer 化
//   4. 失敗時は Commons API でファイル検索のフォールバック

import fetch from 'node-fetch';

const SEARCH_TIMEOUT = 15000;
const IMAGE_TIMEOUT = 30000;

async function fetchWithTimeout(url, ms, opts = {}) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: controller.signal });
  } finally {
    clearTimeout(id);
  }
}

async function searchWikiTitle(query, lang) {
  const url = `https://${lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch=${encodeURIComponent(query)}&format=json&srlimit=3&origin=*`;
  const res = await fetchWithTimeout(url, SEARCH_TIMEOUT, { headers: { 'User-Agent': '10oku-project-bot/1.0' } });
  if (!res.ok) return null;
  const json = await res.json();
  const hits = json?.query?.search || [];
  return hits.length > 0 ? hits[0].title : null;
}

async function summaryImage(title, lang) {
  const url = `https://${lang}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}`;
  const res = await fetchWithTimeout(url, SEARCH_TIMEOUT, { headers: { 'User-Agent': '10oku-project-bot/1.0' } });
  if (!res.ok) return null;
  const json = await res.json();
  return json?.originalimage?.source || json?.thumbnail?.source || null;
}

async function commonsFallback(query) {
  // Commons API for image file search
  const url = `https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrsearch=${encodeURIComponent(query)}&prop=imageinfo&iiprop=url&iiurlwidth=1280&format=json&gsrlimit=3&origin=*`;
  const res = await fetchWithTimeout(url, SEARCH_TIMEOUT, { headers: { 'User-Agent': '10oku-project-bot/1.0' } });
  if (!res.ok) return null;
  const json = await res.json();
  const pages = json?.query?.pages || {};
  for (const k of Object.keys(pages)) {
    const ii = pages[k]?.imageinfo?.[0];
    const src = ii?.thumburl || ii?.url;
    if (src && /\.(jpe?g|png)$/i.test(src)) return src;
  }
  return null;
}

async function downloadImage(url) {
  const res = await fetchWithTimeout(url, IMAGE_TIMEOUT, { headers: { 'User-Agent': '10oku-project-bot/1.0' } });
  if (!res.ok) throw new Error(`image fetch ${res.status}`);
  const ab = await res.arrayBuffer();
  return Buffer.from(ab);
}

export async function fetchWikiImage(query, opts = {}) {
  const lang = opts.lang || 'ja';
  if (!query) return null;
  try {
    let title = await searchWikiTitle(query, lang);
    let imgUrl = null;
    if (title) imgUrl = await summaryImage(title, lang);
    // fallback to english wikipedia
    if (!imgUrl && lang !== 'en') {
      const enTitle = await searchWikiTitle(query, 'en');
      if (enTitle) imgUrl = await summaryImage(enTitle, 'en');
      if (enTitle && !title) title = enTitle;
    }
    // commons fallback
    if (!imgUrl) imgUrl = await commonsFallback(query);
    if (!imgUrl) return null;
    const buffer = await downloadImage(imgUrl);
    if (!buffer || buffer.length < 1024) return null;
    return { buffer, sourceUrl: imgUrl, pageTitle: title };
  } catch (e) {
    console.warn(`[fetch_portrait] failed for "${query}": ${e.message}`);
    return null;
  }
}

// Extract candidate person name from a noisy topic title.
// e.g. "武田信玄 風林火山の哲学" -> ["武田信玄", "武田信玄 風林火山の哲学"]
export function buildCandidateQueries(topicTitle) {
  if (!topicTitle) return [];
  const candidates = [];
  const cleaned = topicTitle.replace(/^[【「『][^】」』]*[】」』]\s*/g, '').trim();
  // first word block (separated by space, comma, middle dot)
  const head = cleaned.split(/[\s　,、・「」]/)[0];
  if (head && head.length >= 2) candidates.push(head);
  if (cleaned !== head) candidates.push(cleaned);
  candidates.push(topicTitle);
  // dedup, keep order
  return [...new Set(candidates)].filter(Boolean);
}
