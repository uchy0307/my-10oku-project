// note-auto/sync-drafts.mjs
// ───────────────────────────────────────────────────────────────
// note.com の下書き一覧を取得し、ローカルの articles/note_NNN.md と
// #NNN パターンで自動マッチさせて queue.json を再構築する。
//
// DOM 構造（2026-05 確認済）:
//   一覧 URL  : https://note.com/notes?status={draft|published}&page=N
//   1ページ   : 32件 (固定)
//   アイテム  : div.o-articleList__item
//   draftId  : input[type=checkbox] の id="listCheckbox_<NNN>" の <NNN>
//   タイトル : .o-articleList__heading
//
// env:
//   NOTE_STORAGE_STATE  storageState JSON 文字列 (GitHub Secrets)
//   NOTE_HEADLESS       "false" 指定で headed 実行 (デフォルト true)
// ───────────────────────────────────────────────────────────────

import { chromium } from 'playwright';
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const QUEUE_PATH = join(__dirname, 'queue.json');
const ARTICLES_DIR = join(__dirname, '..', 'articles');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseStorageState() {
    const raw = process.env.NOTE_STORAGE_STATE;
    if (!raw) {
          throw new Error(
                  'NOTE_STORAGE_STATE が未設定です。note-auto/capture-session.mjs で取得し、Secret に登録してください。',
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

/** 一覧ページを page= ベースでページネーション巡回し、全件を返す */
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

      try {
              await page.waitForSelector('.o-articleList__item', { timeout: 15000 });
      } catch {
              const txt = await page.evaluate(() => document.body.innerText.slice(0, 500)).catch(() => '');
              console.log(`[INFO] status=${status} page=${pageNum}: 0 items (end) preview="${txt.replace(/\s+/g, ' ').slice(0, 120)}"`);
              break;
      }

      await sleep(800);

      const beforeCount = collected.size;
        const items = await page.evaluate(() => {
                const nodes = document.querySelectorAll('.o-articleList__item');
                const out = [];
                for (const el of nodes) {
                          const cb = el.querySelector('input[type="checkbox"]');
                          const id = cb && cb.id ? cb.id.replace(/^listCheckbox_/, '') : null;
                          const headingEl = el.querySelector('.o-articleList__heading');
                          const title = headingEl ? (headingEl.textContent || '').trim() : '';
                          let s = null;
                          if (el.querySelector('.o-articleList__status--draft')) s = 'draft';
                          else if (el.querySelector('.o-articleList__status--published')) s = 'published';
                          if (id && title) out.push({ draftId: id, title, status: s });
                }
                return out;
        });

      console.log(`[INFO] status=${status} page=${pageNum}: ${items.length} items`);
        for (const it of items) {
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
        if (items.length < 32) {
                console.log(`[INFO] status=${status} page=${pageNum}: <32 items, last page`);
                break;
        }
  }
    return Array.from(collected.values());
}

async function main() {
    console.log('[INFO] sync-drafts.mjs start');
    const storageState = parseStorageState();

  let existing = { version: 2, items: [] };
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

      const draftId = matched?.draftId || prev?.draftId || '';
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
              publish: false,
              status,
              scheduled_at: prev?.scheduled_at || null,
              posted_at: prev?.posted_at || null,
              error: prev?.error || null,
              _hasLocalBody: body !== null,
      });
    }

  const out = {
        version: 3,
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
    console.log(`[INFO] draftId: ${withDraftId} / localBody: ${withLocalBody}`);
    console.log(`[INFO] matched=${byNum.size}`);
    console.log(`[INFO] status:`, counts);
}

main().catch((err) => {
    console.error('[FATAL]', err);
    process.exit(1);
});
