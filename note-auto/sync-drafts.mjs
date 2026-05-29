// note-auto/sync-drafts.mjs
// ───────────────────────────────────────────────────────────────
// note.com の下書き / 公開記事一覧を取得し、ローカルの articles/note_NNN.md と
// #NNN パターンで自動マッチさせて queue.json を再構築する。
//
// 取得方法（2026-05 editor.note.com 移行後）:
//   一覧 URL : https://note.com/notes?status={draft|published}&page=N
//   各 SPA ページの Nuxt store `(await(async()=>{try{const u=new URL(location.href);const s=u.searchParams.get('status')||'draft';const p=u.searchParams.get('page')||'1';const r=await fetch('/api/v2/note_list/contents?status='+s+'&page='+p,{credentials:'include',headers:{accept:'application/json'}});if(!r.ok)return null;const j=await r.json();return {notes:(j.data&&j.data.notes)||[],page:{pageCount:null,totalCount:(j.data&&j.data.totalCount)||null,isLastPage:!!(j.data&&j.data.isLastPage)}};}catch(e){return null;}})())` から
//   ノート配列を読む。各ノートの `key` フィールドが editor.note.com で
//   使われる hash 形式の note_key（"n" + hex）。
//
//   - key       : ハッシュ note_key（例: "ne4ad430f2837"）← draftId として保存
//   - id        : 旧・数値 ID（editor.note.com では既に無効）
//   - status    : "draft" | "published"
//   - name      : 公開済みのタイトル
//   - noteDraft.name : 下書きのタイトル
//
// env:
//   NOTE_STORAGE_STATE   storageState JSON 文字列 (GitHub Secrets)
//   NOTE_HEADLESS        "false" 指定で headed 実行 (デフォルト true)
// ───────────────────────────────────────────────────────────────

import { chromium } from 'playwright';
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const QUEUE_PATH = join(__dirname, 'queue.json');
const ARTICLES_DIR = join(__dirname, '..', 'articles');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseStorageState() {
  const raw = process.env.NOTE_STORAGE_STATE;
  if (raw) {
    try { return JSON.parse(raw); } catch {}
  }
  // fallback: storageState.json file (ESM)
  const ssPath = join(__dirname, 'storageState.json');
  if (existsSync(ssPath)) {
    return JSON.parse(readFileSync(ssPath, 'utf8'));
  }
  if (!raw) {
    throw new Error(
      'NOTE_STORAGE_STATE 未設定 かつ storageState.json も無い',
    );
  }
  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`NOTE_STORAGE_STATE が JSON として不正です: ${err.message}`);
  }
}

/** タイトル文字列から #NNN を抽出し 3桁ゼロ埋めの番号を返す */
function extractNumber(title) {
  if (!title) return null;
  const m = title.match(/[#＃]\s*(\d{1,3})/);
  if (!m) return null;
  const n = parseInt(m[1], 10);
  if (n < 1 || n > 200) return null;
  return String(n).padStart(3, '0');
}

/** ローカル articles/note_NNN.md を読み込み body を返す */
async function loadLocalBody(num) {
  const fp = join(ARTICLES_DIR, `note_${num}.md`);
  if (!existsSync(fp)) return null;
  return await readFile(fp, 'utf-8');
}

/**
 * 一覧ページを page= ベースでページネーション巡回し、全件を返す。
 * DOM ではなく Nuxt store (`(await(async()=>{try{const u=new URL(location.href);const s=u.searchParams.get('status')||'draft';const p=u.searchParams.get('page')||'1';const r=await fetch('/api/v2/note_list/contents?status='+s+'&page='+p,{credentials:'include',headers:{accept:'application/json'}});if(!r.ok)return null;const j=await r.json();return {notes:(j.data&&j.data.notes)||[],page:{pageCount:null,totalCount:(j.data&&j.data.totalCount)||null,isLastPage:!!(j.data&&j.data.isLastPage)}};}catch(e){return null;}})())`) から
 * 取得することで、hash 形式の note_key (`n` + hex) を確実に拾える。
 */
async function scrapeListing(page, status) {
  const collected = new Map();
  const MAX_PAGES = 30;

  for (let pageNum = 1; pageNum <= MAX_PAGES; pageNum++) {
    const url = `https://note.com/notes?status=${status}&page=${pageNum}`;
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    } catch (err) {
      console.warn(`[WARN] navigation failed: ${url}: ${err.message}`);
      break;
    }

    // Nuxt 初期化を待つ
    try {
      await page.waitForFunction(
        async () => !!(window.__NUXT__ && window.__NUXT__.state && (await(async()=>{try{const u=new URL(location.href);const s=u.searchParams.get('status')||'draft';const p=u.searchParams.get('page')||'1';const r=await fetch('/api/v2/note_list/contents?status='+s+'&page='+p,{credentials:'include',headers:{accept:'application/json'}});if(!r.ok)return null;const j=await r.json();return {notes:(j.data&&j.data.notes)||[],page:{pageCount:null,totalCount:(j.data&&j.data.totalCount)||null,isLastPage:!!(j.data&&j.data.isLastPage)}};}catch(e){return null;}})())),
        { timeout: 20000 },
      );
    } catch {
      console.log(`[INFO] status=${status} page=${pageNum}: Nuxt state not ready, stop`);
      break;
    }

    await sleep(800);

    const payload = await page.evaluate(async () => {
      const nl = (await(async()=>{try{const u=new URL(location.href);const s=u.searchParams.get('status')||'draft';const p=u.searchParams.get('page')||'1';const r=await fetch('/api/v2/note_list/contents?status='+s+'&page='+p,{credentials:'include',headers:{accept:'application/json'}});if(!r.ok)return null;const j=await r.json();return {notes:(j.data&&j.data.notes)||[],page:{pageCount:null,totalCount:(j.data&&j.data.totalCount)||null,isLastPage:!!(j.data&&j.data.isLastPage)}};}catch(e){return null;}})());
      const notes = (nl && nl.notes) || [];
      const pageInfo = (nl && nl.page) || {};
      const out = notes.map((n) => {
        const title =
          (n.noteDraft && n.noteDraft.name) ||
          n.name ||
          '';
        return {
          draftId: n.key || '', // ← hash note_key
          legacyId: n.id || null,
          title: (title || '').trim(),
          status: n.status || null,
        };
      });
      return {
        items: out,
        pageCount: pageInfo.pageCount || null,
        totalCount: pageInfo.totalCount || null,
        isLastPage: !!pageInfo.isLastPage,
      };
    });

    const items = payload.items || [];
    if (items.length === 0) {
      console.log(`[INFO] status=${status} page=${pageNum}: 0 items (end)`);
      break;
    }

    console.log(
      `[INFO] status=${status} page=${pageNum}: ${items.length} items (totalCount=${payload.totalCount}, pageCount=${payload.pageCount})`,
    );

    const beforeCount = collected.size;
    for (const it of items) {
      if (!it.draftId || !it.title) continue;
      const s = it.status || status;
      if (!collected.has(it.draftId)) {
        collected.set(it.draftId, { ...it, status: s });
      } else {
        const prev = collected.get(it.draftId);
        if ((it.title || '').length > (prev.title || '').length) prev.title = it.title;
        if (s === 'published') prev.status = 'published';
      }
    }

    if (collected.size === beforeCount) {
      console.log(`[INFO] status=${status} page=${pageNum}: no new items, stop`);
      break;
    }
    if (payload.isLastPage) {
      console.log(`[INFO] status=${status} page=${pageNum}: isLastPage=true, stop`);
      break;
    }
    if (payload.pageCount && pageNum >= payload.pageCount) {
      console.log(`[INFO] status=${status} page=${pageNum}: reached pageCount=${payload.pageCount}, stop`);
      break;
    }
  }
  return Array.from(collected.values());
}

async function main() {
  console.log('[INFO] sync-drafts.mjs start (hash-key edition)');
  const storageState = parseStorageState();

  let existing = { version: 3, items: [] };
  if (existsSync(QUEUE_PATH)) {
    try {
      existing = JSON.parse(await readFile(QUEUE_PATH, 'utf-8'));
    } catch (e) {
      console.warn('[WARN] queue.json parse fail:', e.message);
    }
  }
  const existingById = new Map((existing.items || []).map((i) => [i.id, i]));

  let localNums = [];
  if (existsSync(ARTICLES_DIR)) {
    const files = await readdir(ARTICLES_DIR);
    localNums = files
      .map((f) => (f.match(/^note_(\d{3})\.md$/) || [])[1])
      .filter(Boolean)
      .sort();
  }
  console.log(`[INFO] local articles: ${localNums.length}`);

  const headless = process.env.NOTE_HEADLESS !== 'false';
  const browser = await chromium.launch({
    headless,
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const context = await browser.newContext({
    storageState,
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    timezoneId: 'Asia/Tokyo',
    viewport: { width: 1280, height: 1000 },
  });
  const page = await context.newPage();

  let scraped = [];
  try {
    try {
      await page.goto('https://note.com/notes?status=draft', {
        waitUntil: 'domcontentloaded',
        timeout: 30000,
      });
      await sleep(1500);
      const pt = await page.title();
      console.log(`[DEBUG] warmup title: ${pt}`);
    } catch (e) {
      console.warn(`[WARN] warmup failed: ${e.message}`);
    }

    const drafts = await scrapeListing(page, 'draft');
    const published = await scrapeListing(page, 'published');
    console.log(`[INFO] scraped: draft=${drafts.length}, published=${published.length}`);

    const merged = new Map();
    for (const it of [...drafts, ...published]) {
      if (!merged.has(it.draftId)) merged.set(it.draftId, it);
      else if (it.status === 'published') merged.set(it.draftId, it);
    }
    scraped = Array.from(merged.values());
  } finally {
    await context.close();
    await browser.close();
  }
  console.log(`[INFO] scraped total: ${scraped.length} posts`);

  const byNum = new Map();
  for (const s of scraped) {
    const num = extractNumber(s.title);
    if (!num) continue;
    if (!byNum.has(num)) {
      byNum.set(num, s);
    } else {
      const prev = byNum.get(num);
      if (s.status === 'published' && prev.status !== 'published') byNum.set(num, s);
      else if ((s.title || '').length > (prev.title || '').length) byNum.set(num, s);
    }
  }
  console.log(`[INFO] matched by #NNN: ${byNum.size}`);

  const newItems = [];
  for (const num of localNums) {
    const matched = byNum.get(num);
    const prev = existingById.get(num);

    // 旧 queue.json の数値 ID は editor.note.com 移行で無効。
    // matched（新 hash key）が取れたら必ず上書き、なければ空文字。
    const draftId = matched?.draftId || '';
    const title = matched?.title || prev?.title || '';
    const noteStatus = matched?.status;

    let status;
    if (
      prev?.status === 'published' ||
      prev?.status === 'draft_saved' ||
      prev?.status === 'published_manual'
    ) {
      status = prev.status;
    } else if (noteStatus === 'published') {
      status = 'published';
    } else {
      status = 'pending';
    }

    const body = await loadLocalBody(num);

    newItems.push({
      id: num,
      draftId,
      title,
      publish: prev?.publish ?? false,
      status,
      scheduled_at: prev?.scheduled_at || null,
      posted_at: prev?.posted_at || null,
      error: prev?.error || null,
      _hasLocalBody: body !== null,
    });
  }

  const out = {
    version: 4,
    synced_at: new Date().toISOString(),
    items: newItems,
  };
  await writeFile(QUEUE_PATH, JSON.stringify(out, null, 2) + '\n', 'utf-8');

  const counts = newItems.reduce((acc, i) => {
    acc[i.status] = (acc[i.status] || 0) + 1;
    return acc;
  }, {});
  const withDraftId = newItems.filter((i) => i.draftId).length;
  const withLocalBody = newItems.filter((i) => i._hasLocalBody).length;
  console.log(`[INFO] queue.json updated: ${newItems.length} items`);
  console.log(`[INFO] draftId(hash): ${withDraftId} / localBody: ${withLocalBody}`);
  console.log(`[INFO] matched=${byNum.size}`);
  console.log(`[INFO] status:`, counts);

  // 2026-05-29: draftId 取得失敗 + 破損 article (鉤括弧 open/close 大幅不一致) を warn 集計
  const missingDraftId = newItems.filter((i) => i._hasLocalBody && !i.draftId && i.publish);
  if (missingDraftId.length > 0) {
    console.warn(`[WARN] ${missingDraftId.length} items have local body + publish=true but NO draftId (note sync missed them):`);
    for (const m of missingDraftId.slice(0, 20)) {
      console.warn(`  id=${m.id} title="${(m.title || '').slice(0, 60)}"`);
    }
  }

  // 破損 article 検出: 「『」と「』」の数が大きく乖離している article は本文が壊れてる可能性
  const corruptionCheck = [];
  for (const it of newItems) {
    if (!it._hasLocalBody) continue;
    try {
      const body = await loadLocalBody(it.id);
      if (!body) continue;
      const openCount = (body.match(/『/g) || []).length;
      const closeCount = (body.match(/』/g) || []).length;
      const diff = Math.abs(openCount - closeCount);
      // 100 を超える差は明らかに placeholder 垂れ流し系の破損
      if (diff > 100) {
        corruptionCheck.push({ id: it.id, openCount, closeCount, diff });
      }
    } catch {}
  }
  if (corruptionCheck.length > 0) {
    console.warn(`[WARN] ${corruptionCheck.length} corrupted articles detected (bracket imbalance > 100):`);
    for (const c of corruptionCheck) {
      console.warn(`  id=${c.id} open=${c.openCount} close=${c.closeCount} diff=${c.diff}`);
    }
    console.warn('[WARN] これらは publish=false にして手動修復を推奨');
  }
}

main().catch((err) => {
  console.error('[FATAL]', err);
  process.exit(1);
});
