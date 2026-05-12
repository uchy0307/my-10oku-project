// note-auto/sync-drafts.mjs
// ───────────────────────────────────────────────────────────────
// note.com の下書き一覧を取得し、ローカルの articles/note_NNN.md と
// #NNN パターンで自動マッチさせて queue.json を再構築する。
//
// 実行前提:
//   - note.com に 200本の下書き/公開記事が存在し、各記事タイトルに
//     `#001` ... `#200` のような番号を含む
//   - articles/note_NNN.md が 200本存在する
//   - NOTE_STORAGE_STATE (Playwright storageState JSON) が認証済み
//
// env:
//   NOTE_STORAGE_STATE   storageState JSON 文字列 (GitHub Secrets)
//   NOTE_HEADLESS        "false" 指定で headed 実行 (デフォルト true)
//
// 動作:
//   1. note.com にログイン (storageState で復元)
//   2. ダッシュボードの下書き一覧 + 公開済一覧をすべてスクレイプ
//   3. タイトルから #NNN を抽出し draftId と紐付け
//   4. articles/note_NNN.md を読み込み body を取得
//   5. queue.json を再構築:
//      - 公開済 → status: 'published' (再投稿しない)
//      - 下書き → status: 'pending', publish: false
//      - 既に投稿済 (post.mjsで処理済) の status は保持
//
// 出力: queue.json (上書き)
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
  // #001, # 001, ＃001 すべて対応
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

/** JSON応答からノート配列を取り出す（note.comはレスポンス形式が多様） */
function pickNoteArray(data) {
  if (!data) return null;
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.notes)) return data.notes;
  if (data.data) {
    if (Array.isArray(data.data)) return data.data;
    if (Array.isArray(data.data.notes)) return data.data.notes;
    if (Array.isArray(data.data.contents)) return data.data.contents;
    if (Array.isArray(data.data.items)) return data.data.items;
  }
  if (Array.isArray(data.contents)) return data.contents;
  if (Array.isArray(data.items)) return data.items;
  return null;
}

/** ノートオブジェクトから status を推定 */
function inferStatus(it) {
  if (!it) return null;
  const s = String(it.status ?? it.state ?? it.note_status ?? '').toLowerCase();
  if (s.includes('publish')) return 'published';
  if (s.includes('draft')) return 'draft';
  if (it.published === true || it.publish === true) return 'published';
  if (it.is_draft === true || it.is_draft === 1) return 'draft';
  return null;
}

/** note.com の下書き/記事一覧ページをスクレイプ */
async function scrapeAllPosts(page) {
  const collected = new Map(); // draftId -> { draftId, title, status }
  const apiSeen = new Set();

  // ───────────────────────────────────────────────
  // 1) ネットワーク監視: note.com が裏で叩く /api/ コールを記録 + JSON解析
  //    note.com の管理一覧は SPA + 無限スクロールで /api/v2/notes 等を呼ぶ。
  //    そこから直接記事IDを拾うのが最も確実。
  // ───────────────────────────────────────────────
  page.on('response', async (response) => {
    try {
      const u = response.url();
      if (!/note\.com\/api\//.test(u)) return;
      if (!/notes|drafts|contents/i.test(u)) return;
      const ct = response.headers()['content-type'] || '';
      if (!ct.includes('json')) return;
      if (!apiSeen.has(u)) {
        apiSeen.add(u);
        console.log(`[API] ${u}`);
      }
      const data = await response.json().catch(() => null);
      if (!data) return;
      const arr = pickNoteArray(data);
      if (!arr || !arr.length) return;
      for (const it of arr) {
        const draftId = String(it.id ?? it.key ?? it.note_id ?? it.uuid ?? '').trim();
        const title = String(it.name ?? it.title ?? '').trim();
        if (!draftId || !title) continue;
        const status = inferStatus(it);
        if (!collected.has(draftId)) {
          collected.set(draftId, { draftId, title, status });
        } else {
          const prev = collected.get(draftId);
          if (title.length > (prev.title || '').length) prev.title = title;
          if (status === 'published') prev.status = 'published';
        }
      }
    } catch {}
  });

  // 下書き一覧 + 公開済 一覧 両方を、ページネーション巡回
  const bases = [
    { url: 'https://note.com/notes?status=draft', defaultStatus: 'draft' },
    { url: 'https://note.com/notes?status=published', defaultStatus: 'published' },
  ];

  for (const { url: baseUrl, defaultStatus } of bases) {
    console.log(`[INFO] scraping base: ${baseUrl} (defaultStatus=${defaultStatus})`);
    let prevTotalForThisBase = 0;
    for (let pageNum = 1; pageNum <= 50; pageNum++) {
      const url = baseUrl.includes('?') ? `${baseUrl}&page=${pageNum}` : `${baseUrl}?page=${pageNum}`;
      try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      } catch (err) {
        console.warn(`[WARN] navigation failed: ${url}: ${err.message}`);
        break;
      }
      const actualUrl = page.url();
      if (pageNum === 1) {
        const pageTitle = await page.title();
        console.log(`[DEBUG]   page=${pageNum} actual URL: ${actualUrl}`);
        console.log(`[DEBUG]   page=${pageNum} page title: ${pageTitle}`);
        const hasLoginBtn = await page.evaluate(() => {
          const t = document.body.innerText || '';
          return t.includes('ログイン') && t.includes('会員登録');
        }).catch(() => false);
        if (hasLoginBtn) {
          console.warn(`[WARN]   ログインが効いていません（"ログイン/会員登録"ボタン検出）`);
        }
      }
      await sleep(2500);

      // ───────────────────────────────────────────────
      // 2) 強化版・無限スクロール
      //    高さが N 回連続で変わらなかったら終了。最大 80 ループ。
      // ───────────────────────────────────────────────
      let lastHeight = 0;
      let stableCount = 0;
      for (let i = 0; i < 80; i++) {
        const height = await page.evaluate(() => document.body.scrollHeight);
        if (height === lastHeight) {
          stableCount++;
          if (stableCount >= 6) break; // 6回連続でheight変わらず → loaded
        } else {
          stableCount = 0;
          lastHeight = height;
        }
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await sleep(1500);
      }
      console.log(`[DEBUG]   final scrollHeight=${lastHeight}, collected so far=${collected.size}`);

      // 「もっと見る」「次へ」「Load more」ボタンが見つかれば全部クリック
      try {
        for (let k = 0; k < 30; k++) {
          const clicked = await page.evaluate(() => {
            const btns = Array.from(document.querySelectorAll('button, a'));
            const target = btns.find((b) => /もっと|続きを|Load more|次へ|次の/.test((b.textContent || '').trim()));
            if (target) { target.click(); return true; }
            return false;
          });
          if (!clicked) break;
          await sleep(1500);
        }
      } catch {}
      // この時点でのページ収集
      const beforeCount = collected.size;

    // ページ内の全カードから draftId とタイトルを取り出す
    const items = await page.evaluate(() => {
      // note.com の記事カードは a[href*="/notes/"] や a[href*="/n/"] を持つ
      const links = Array.from(document.querySelectorAll('a[href*="/notes/"], a[href*="/n/"]'));
      const results = [];
      for (const a of links) {
        const href = a.getAttribute('href') || '';
        // /notes/<id>/edit or /notes/<id> or /n/<id>
        let m = href.match(/\/notes\/([a-zA-Z0-9_-]+)(?:\/edit)?(?:[/?#]|$)/);
        let draftId = m ? m[1] : null;
        if (!draftId) {
          m = href.match(/\/n\/([a-zA-Z0-9_-]+)(?:[/?#]|$)/);
          if (m) draftId = m[1];
        }
        if (!draftId) continue;

        // タイトル候補: aタグ自体のtext、または近傍のh2/h3
        let title = (a.textContent || '').trim();
        if (!title || title.length < 3) {
          const card = a.closest('article, li, div[class*="note"], div[class*="Card"]');
          if (card) {
            const h = card.querySelector('h1, h2, h3, [class*="title"], [class*="Title"]');
            if (h) title = (h.textContent || '').trim();
          }
        }
        if (!title) continue;

        // ステータス推定: カード内に "下書き" / "公開" 文字列があるか
        let status = null;
        const card = a.closest('article, li, div');
        if (card) {
          const txt = card.textContent || '';
          if (/下書き/.test(txt)) status = 'draft';
          else if (/公開/.test(txt)) status = 'published';
        }

        results.push({ draftId, title, status });
      }
      return results;
    });

      console.log(`[INFO]   ${items.length} cards found`);
      for (const it of items) {
        const status = it.status || defaultStatus;
        if (!collected.has(it.draftId)) {
          collected.set(it.draftId, { ...it, status });
        } else {
          // 既存より長いタイトル or published情報があれば更新
          const prev = collected.get(it.draftId);
          if (!prev.title || it.title.length > prev.title.length) prev.title = it.title;
          if (status === 'published') prev.status = 'published';
        }
      }

      // このページで新規追加が無ければ次のbaseへ
      if (collected.size === beforeCount && pageNum > 1) {
        console.log(`[INFO]   no new items on page=${pageNum}, moving on`);
        break;
      }
    }
  }

  return Array.from(collected.values());
}

async function main() {
  console.log('[INFO] sync-drafts.mjs start');
  const storageState = parseStorageState();

  // 既存 queue.json があれば読み込み (status保持のため)
  let existing = { version: 2, items: [] };
  if (existsSync(QUEUE_PATH)) {
    try {
      existing = JSON.parse(await readFile(QUEUE_PATH, 'utf-8'));
    } catch (e) {
      console.warn('[WARN] 既存 queue.json パース失敗:', e.message);
    }
  }
  const existingById = new Map((existing.items || []).map((i) => [i.id, i]));

  // articles/ にあるローカル原稿の番号一覧
  let localNums = [];
  if (existsSync(ARTICLES_DIR)) {
    const files = await readdir(ARTICLES_DIR);
    localNums = files
      .map((f) => (f.match(/^note_(\d{3})\.md$/) || [])[1])
      .filter(Boolean)
      .sort();
  }
  console.log(`[INFO] local articles: ${localNums.length}`);

  // note.com 側スクレイプ
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
    scraped = await scrapeAllPosts(page);
  } finally {
    await context.close();
    await browser.close();
  }
  console.log(`[INFO] scraped total: ${scraped.length} posts`);

  // #NNN → 記事情報 へインデックス化
  const byNum = new Map();
  for (const s of scraped) {
    const num = extractNumber(s.title);
    if (!num) continue;
    if (!byNum.has(num)) {
      byNum.set(num, s);
    } else {
      // 既存より published 優先 / タイトル長優先
      const prev = byNum.get(num);
      if (s.status === 'published' && prev.status !== 'published') byNum.set(num, s);
      else if ((s.title || '').length > (prev.title || '').length) byNum.set(num, s);
    }
  }
  console.log(`[INFO] matched by #NNN: ${byNum.size}`);

  // 新しい items を構築 (001..200)
  const newItems = [];
  for (const num of localNums) {
    const matched = byNum.get(num);
    const prev = existingById.get(num);

    const draftId = matched?.draftId || prev?.draftId || '';
    const title = matched?.title || prev?.title || '';
    const noteStatus = matched?.status; // 'draft' / 'published' / null

    // status 決定ロジック:
    //   - prev.status が 'published' or 'draft_saved' (post.mjs完了) → 保持
    //   - note.com 側で 'published' → 'published' (これ以上触らない)
    //   - 上記以外 (note.com 上が draft) → 'pending'
    let status;
    if (prev?.status === 'published' || prev?.status === 'draft_saved') {
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
      // body は workflow 上で読み込むので queue.json には書かない (大きすぎるため)
      // post.mjs が articles/note_${num}.md を fallback で読む
      publish: false, // 下書き保存のみ (公開はしない)
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

  // サマリ
  const counts = newItems.reduce((acc, i) => {
    acc[i.status] = (acc[i.status] || 0) + 1;
    return acc;
  }, {});
  const withDraftId = newItems.filter((i) => i.draftId).length;
  const withLocalBody = newItems.filter((i) => i._hasLocalBody).length;
  console.log(`[INFO] queue.json updated: ${newItems.length} items`);
  console.log(`[INFO]   draftId 付き: ${withDraftId} / ローカル本文 有: ${withLocalBody}`);
  console.log(`[INFO]   status:`, counts);
}

main().catch((err) => {
  console.error('[FATAL]', err);
  process.exit(1);
});
