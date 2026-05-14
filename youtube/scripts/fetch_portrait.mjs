// youtube/scripts/fetch_portrait.mjs
// Wikipedia / Wikimedia Commons から実在画像を取得するユーティリティ。
// AI画像は一切扱わない。
//
// 公開関数:
//   fetchWikiImage(query, opts)            -> { buffer, sourceUrl, pageTitle } | null
//   fetchWikiImageMulti(query, opts)       -> { buffer, sourceUrl, pageTitle } | null (excludeUrls / excludePages 対応)
//   listWikiPageCandidates(query, opts)    -> [{title, url}]  opensearch 結果
//   buildCandidateQueries(topicTitle)      -> [string]
//
// すべての取得元は Wikipedia / Commons の実在画像のみ。

import fetch from 'node-fetch';

const SEARCH_TIMEOUT = 15000;
const IMAGE_TIMEOUT = 30000;
const UA = '10oku-project-bot/1.0 (Wikipedia/Commons image fetch)';

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
  const res = await fetchWithTimeout(url, SEARCH_TIMEOUT, { headers: { 'User-Agent': UA } });
  if (!res.ok) return null;
  const json = await res.json();
  const hits = json?.query?.search || [];
  return hits.length > 0 ? hits[0].title : null;
}

// opensearch returns multiple page titles
async function opensearchTitles(query, lang, limit) {
  const url = `https://${lang}.wikipedia.org/w/api.php?action=opensearch&search=${encodeURIComponent(query)}&limit=${limit}&format=json&origin=*`;
  const res = await fetchWithTimeout(url, SEARCH_TIMEOUT, { headers: { 'User-Agent': UA } });
  if (!res.ok) return [];
  const json = await res.json();
  // [query, [titles], [descriptions], [urls]]
  return Array.isArray(json?.[1]) ? json[1] : [];
}

async function summaryImage(title, lang) {
  const url = `https://${lang}.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}`;
  const res = await fetchWithTimeout(url, SEARCH_TIMEOUT, { headers: { 'User-Agent': UA } });
  if (!res.ok) return null;
  const json = await res.json();
  return json?.originalimage?.source || json?.thumbnail?.source || null;
}

async function commonsCategoryImages(category, limit = 10) {
  const url = `https://commons.wikimedia.org/w/api.php?action=query&generator=categorymembers&gcmtitle=${encodeURIComponent(category)}&gcmtype=file&gcmlimit=${limit}&prop=imageinfo&iiprop=url&iiurlwidth=1280&format=json&origin=*`;
  const res = await fetchWithTimeout(url, SEARCH_TIMEOUT, { headers: { 'User-Agent': UA } });
  if (!res.ok) return [];
  const json = await res.json();
  const pages = json?.query?.pages || {};
  const urls = [];
  for (const k of Object.keys(pages)) {
    const ii = pages[k]?.imageinfo?.[0];
    const src = ii?.thumburl || ii?.url;
    if (src && /\.(jpe?g|png)$/i.test(src)) urls.push(src);
  }
  return urls;
}

async function commonsFileSearch(query) {
  const url = `https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrsearch=${encodeURIComponent(query)}&prop=imageinfo&iiprop=url&iiurlwidth=1280&format=json&gsrlimit=5&origin=*`;
  const res = await fetchWithTimeout(url, SEARCH_TIMEOUT, { headers: { 'User-Agent': UA } });
  if (!res.ok) return [];
  const json = await res.json();
  const pages = json?.query?.pages || {};
  const urls = [];
  for (const k of Object.keys(pages)) {
    const ii = pages[k]?.imageinfo?.[0];
    const src = ii?.thumburl || ii?.url;
    if (src && /\.(jpe?g|png)$/i.test(src)) urls.push(src);
  }
  return urls;
}

async function downloadImage(url) {
  const res = await fetchWithTimeout(url, IMAGE_TIMEOUT, { headers: { 'User-Agent': UA } });
  if (!res.ok) throw new Error(`image fetch ${res.status}`);
  const ab = await res.arrayBuffer();
  return Buffer.from(ab);
}

// 旧API: 単一の最良候補を返す
export async function fetchWikiImage(query, opts = {}) {
  const lang = opts.lang || 'ja';
  if (!query) return null;
  try {
    let title = await searchWikiTitle(query, lang);
    let imgUrl = null;
    if (title) imgUrl = await summaryImage(title, lang);
    if (!imgUrl && lang !== 'en') {
      const enTitle = await searchWikiTitle(query, 'en');
      if (enTitle) imgUrl = await summaryImage(enTitle, 'en');
      if (enTitle && !title) title = enTitle;
    }
    if (!imgUrl) {
      const urls = await commonsFileSearch(query);
      if (urls.length > 0) imgUrl = urls[0];
    }
    if (!imgUrl) return null;
    const buffer = await downloadImage(imgUrl);
    if (!buffer || buffer.length < 1024) return null;
    return { buffer, sourceUrl: imgUrl, pageTitle: title };
  } catch (e) {
    console.warn(`[fetch_portrait] fetchWikiImage failed for "${query}": ${e.message}`);
    return null;
  }
}

// 新API: 重複除外可能。複数候補を順に試して最初の取れたものを返す。
// opts.excludeUrls : Set<string> ... 既に使った imageUrl
// opts.excludePages: Set<string> ... 既に使った pageTitle
// opts.commonsCategory: 試したい Commons カテゴリ名 (例: 'Category:Battles_of_the_Sengoku_period')
export async function fetchWikiImageMulti(query, opts = {}) {
  const lang = opts.lang || 'ja';
  const excludeUrls = opts.excludeUrls || new Set();
  const excludePages = opts.excludePages || new Set();
  if (!query && !opts.commonsCategory) return null;

  const candidatePages = [];

  if (query) {
    try {
      const jaTitles = await opensearchTitles(query, lang, 8);
      for (const t of jaTitles) candidatePages.push({ title: t, lang });
    } catch {}
    if (lang !== 'en') {
      try {
        const enTitles = await opensearchTitles(query, 'en', 5);
        for (const t of enTitles) candidatePages.push({ title: t, lang: 'en' });
      } catch {}
    }
  }

  // try summary image for each candidate
  for (const cand of candidatePages) {
    if (excludePages.has(cand.title)) continue;
    try {
      const imgUrl = await summaryImage(cand.title, cand.lang);
      if (!imgUrl) continue;
      if (excludeUrls.has(imgUrl)) continue;
      const buffer = await downloadImage(imgUrl);
      if (!buffer || buffer.length < 1024) continue;
      return { buffer, sourceUrl: imgUrl, pageTitle: cand.title };
    } catch (e) {
      console.warn(`[fetch_portrait] page "${cand.title}" image fetch failed: ${e.message}`);
    }
  }

  // commons file search fallback
  if (query) {
    try {
      const urls = await commonsFileSearch(query);
      for (const u of urls) {
        if (excludeUrls.has(u)) continue;
        try {
          const buffer = await downloadImage(u);
          if (!buffer || buffer.length < 1024) continue;
          return { buffer, sourceUrl: u, pageTitle: `(commons:${u.split('/').pop()})` };
        } catch (e) {
          continue;
        }
      }
    } catch {}
  }

  // commons category fallback (multiple candidates)
  if (opts.commonsCategory) {
    try {
      const urls = await commonsCategoryImages(opts.commonsCategory, 10);
      for (const u of urls) {
        if (excludeUrls.has(u)) continue;
        try {
          const buffer = await downloadImage(u);
          if (!buffer || buffer.length < 1024) continue;
          return { buffer, sourceUrl: u, pageTitle: opts.commonsCategory };
        } catch (e) { continue; }
      }
    } catch {}
  }

  return null;
}

export async function listWikiPageCandidates(query, opts = {}) {
  const lang = opts.lang || 'ja';
  const titles = await opensearchTitles(query, lang, opts.limit || 5);
  return titles.map((t) => ({ title: t, lang }));
}

// Extract candidate person/topic name from a noisy topic title.
// e.g. "武田信玄 風林火山の哲学" -> ["武田信玄", "武田信玄 風林火山の哲学"]
export function buildCandidateQueries(topicTitle) {
  if (!topicTitle) return [];
  const candidates = [];
  const cleaned = topicTitle.replace(/^[【「『][^】」』]*[】」』]\s*/g, '').trim();
  const head = cleaned.split(/[\s　,、・「」]/)[0];
  if (head && head.length >= 2) candidates.push(head);
  if (cleaned !== head) candidates.push(cleaned);
  candidates.push(topicTitle);
  return [...new Set(candidates)].filter(Boolean);
}
