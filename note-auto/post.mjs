// note-auto/post.mjs
// ───────────────────────────────────────────────────────────────
// note.com 下書き編集型自動投稿（B案・新方針 / v5）
//
// 2026-05-16 v5 改修:
//   - 有料記事化フロー実装:
//     1) /publish/ ページに直接URL遷移（「公開に進む」ボタンは押さない）
//     2) input[name="is_paid"] の「有料」radio を React-safe setter で ON
//     3) 価格 input[placeholder="300"] を 100 にセット
//     4) /edit/ ページに直接URL遷移で戻る
//     5) ProseMirror 内 🔑直前にカーソル → "+"メニュー → 「有料エリア指定」
//   - 公開（publish=true）時のみ最終「公開する」ボタンクリック
//   - FORCE_PAID (NOTE_TEST_PAID=true) で publish:false 時も上記フロー全実行
// ───────────────────────────────────────────────────────────────

import { chromium } from 'playwright';
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const QUEUE_PATH = join(__dirname, 'queue.json');
const ARTICLES_DIR = join(__dirname, '..', 'articles');
const ATTACHMENTS_DIR = join(__dirname, 'attachments');
const ACCESS_CODES_PATH = join(__dirname, 'access_codes.json');

const PRICE_YEN = 100;
const URL_PATTERN = 'https://toi-suite.vercel.app/page/';
const FORCE_PAID = process.env.NOTE_TEST_PAID === 'true';

let ACCESS_CODES = {};
try {
  if (existsSync(ACCESS_CODES_PATH)) {
    ACCESS_CODES = JSON.parse(await readFile(ACCESS_CODES_PATH, 'utf-8'));
  }
} catch (err) {
  console.warn('[WARN] access_codes.json 読み込み失敗:', err.message);
}

function preprocessBody(body, articleId) {
  let out = body;
  out = out.replace(/47歳の/g, '');
  out = out.replace(/47歳が/g, '私が');
  out = out.replace(/47歳に/g, '');
  out = out.replace(/47歳/g, '');
  out = out.replace(/[#＃]\s?47歳\s*/g, '');
  out = out
    .split('\n')
    .map((line) => line.replace(/[ \t]{2,}/g, ' ').replace(/^ +| +$/g, ''))
    .join('\n');
  out = out.replace(/\n{4,}/g, '\n\n\n');
  const code = ACCESS_CODES[articleId];
  if (code) {
    const link = `${URL_PATTERN}${articleId}`;
    if (!out.includes(link)) {
      out +=
        `\n\n\n\n---\n\n▼アプリで深く問う\n\n` +
        `${link}\n\n` +
        `アクセスコード: ${code}\n`;
    }
  }
  return out;
}

async function resolveBody(item) {
  let raw;
  if (item.body && typeof item.body === 'string' && item.body.trim().length > 0) {
    raw = item.body;
  } else {
    const fp = join(ARTICLES_DIR, `note_${item.id}.md`);
    if (!existsSync(fp)) {
      throw new Error(`本文が見つかりません: item.body も articles/note_${item.id}.md も存在しません。`);
    }
    raw = await readFile(fp, 'utf-8');
  }
  return preprocessBody(raw, item.id);
}

async function resolveAttachments(id) {
  const dir = join(ATTACHMENTS_DIR, `app${id}`);
  if (!existsSync(dir)) {
    console.warn(`[WARN] attachments dir 不在: ${dir}`);
    return [];
  }
  const entries = await readdir(dir);
  return entries.filter((f) => f.toLowerCase().endsWith('.docx')).map((f) => join(dir, f));
}

const SELECTORS = {
  bodyEditor: '.ProseMirror',
  titleInput: 'textarea[placeholder*="タイトル"]',
  saveDraftButton: 'button:has-text("下書き保存")',
  publishButton: 'button:has-text("公開する")',
  plusMenuOpen: '[aria-label="メニューを開く"]',
  filePickerButton: 'button:has-text("ファイル")',
  paidBoundaryButton: 'button:has-text("有料エリア指定")',
  fileInput: 'input[type="file"]',
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const randDelay = (min = 3000, max = 7000) =>
  sleep(min + Math.floor(Math.random() * (max - min)));

function parseArgs() {
  const args = { max: 1 };
  for (const a of process.argv.slice(2)) {
    const m = a.match(/^--max=(\d+)$/);
    if (m) args.max = Number(m[1]);
  }
  return args;
}

async function loadQueue() {
  const raw = await readFile(QUEUE_PATH, 'utf-8');
  return JSON.parse(raw);
}

async function saveQueue(queue) {
  await writeFile(QUEUE_PATH, JSON.stringify(queue, null, 2) + '\n', 'utf-8');
}

function parseStorageState() {
  const raw = process.env.NOTE_STORAGE_STATE;
  if (!raw) throw new Error('NOTE_STORAGE_STATE が未設定です。');
  try { return JSON.parse(raw); }
  catch (err) { throw new Error(`NOTE_STORAGE_STATE が JSON として不正です: ${err.message}`); }
}

/** /publish/ に直接URL遷移して 有料記事化 radio ON + 価格設定。
 *  - 「公開に進む」ボタンは押さない（URL navigation）
 *  - 「公開する」ボタンも絶対押さない
 *  - 設定後 /edit/ に戻る（クリックではなく URL navigation）
 */
async function configurePaidSettings(page, draftId, yen) {
  try {
    const publishUrl = `https://editor.note.com/notes/${draftId}/publish/`;
    console.log(`[INFO] publish settings へ直接遷移: ${publishUrl}`);
    await page.goto(publishUrl, { waitUntil: 'domcontentloaded' });
    await randDelay(3000, 4500);

    const result = await page.evaluate((yen) => {
      const setterVal = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;

      // 1. 有料 radio (input[name="is_paid"] 2番目)
      const radios = [...document.querySelectorAll('input[type="radio"][name="is_paid"]')];
      let paidRadioState = 'no_radios';
      if (radios.length >= 2) {
        const paidRadio = radios[1];
        if (paidRadio.checked) {
          paidRadioState = 'already_checked';
        } else {
          paidRadio.click();
          paidRadio.dispatchEvent(new Event('change', { bubbles: true }));
          paidRadioState = paidRadio.checked ? 'just_checked' : 'click_failed';
        }
      }

      // 2. 価格 input
      let priceState = { ok: false };
      const priceSelectors = [
        'input[type="text"][placeholder="300"]',
        'input[type="number"][placeholder*="0"]',
        'input[type="text"][class*="sc-85966dc5"]',
        'input[type="text"]:not([readonly])',
      ];
      for (const sel of priceSelectors) {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
          if (el.offsetParent === null) continue;
          const ph = el.placeholder || '';
          // numeric placeholder (e.g., "300") のみ採用
          if (!/^\d+$/.test(ph)) continue;
          setterVal.call(el, String(yen));
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          el.dispatchEvent(new Event('blur', { bubbles: true }));
          priceState = { ok: true, selector: sel, value: el.value };
          break;
        }
        if (priceState.ok) break;
      }
      return { paidRadioState, priceState };
    }, yen);

    console.log('[INFO] publish settings:', JSON.stringify(result));
    await sleep(3000); // React auto-save 待ち
    return {
      paidEnabled: ['already_checked', 'just_checked'].includes(result.paidRadioState),
      priceSet: result.priceState.ok,
      detail: result,
    };
  } catch (err) {
    console.warn('[WARN] configurePaidSettings エラー:', err.message);
    return { paidEnabled: false, priceSet: false, err: err.message };
  }
}

/** ProseMirror内のH2「🔑 アクセスコード」直前にカーソル設定 */
async function placeCursorBeforeAccessCode(page) {
  const ok = await page.evaluate(() => {
    const pm = document.querySelector('.ProseMirror');
    if (!pm) return { ok: false, reason: 'no_prosemirror' };
    const items = [...pm.querySelectorAll('h1,h2,h3,p')];
    const target = items.find((el) => /🔑/.test(el.textContent || ''));
    if (!target) return { ok: false, reason: 'no_marker' };
    const range = document.createRange();
    range.setStartBefore(target);
    range.collapse(true);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    target.scrollIntoView({ block: 'center' });
    return { ok: true };
  });
  return !!ok?.ok;
}

async function insertPaidBoundary(page) {
  try {
    const placed = await placeCursorBeforeAccessCode(page);
    if (!placed) {
      console.warn('[WARN] 🔑マーカー未発見 → 境界線スキップ');
      return false;
    }
    await sleep(500);
    const plus = page.locator(SELECTORS.plusMenuOpen).first();
    if (!(await plus.count())) {
      console.warn('[WARN] "+"メニュー未発見 → 境界線スキップ');
      return false;
    }
    await plus.click();
    await sleep(1200);
    const paid = page.locator(SELECTORS.paidBoundaryButton).first();
    if (!(await paid.count())) {
      console.warn('[WARN] 「有料エリア指定」ボタン未発見');
      await page.keyboard.press('Escape').catch(() => {});
      return false;
    }
    await paid.click();
    await sleep(1800);
    // Verify boundary inserted
    const verified = await page.evaluate(() => {
      const strongs = [...document.querySelectorAll('.ProseMirror strong')];
      return strongs.some(s => /有料エリア/.test(s.textContent || ''));
    });
    console.log(`[INFO] 有料境界線 挿入完了 verified=${verified}`);
    return verified;
  } catch (err) {
    console.warn('[WARN] insertPaidBoundary エラー:', err.message);
    return false;
  }
}

async function attachFiles(page, filePaths) {
  if (filePaths.length === 0) return 0;
  let attached = 0;
  await page.evaluate(() => {
    const pm = document.querySelector('.ProseMirror');
    if (!pm) return;
    const last = pm.lastElementChild;
    if (!last) return;
    const range = document.createRange();
    range.selectNodeContents(last);
    range.collapse(false);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    last.scrollIntoView({ block: 'center' });
  });
  await sleep(500);

  for (const fp of filePaths) {
    try {
      const plus = page.locator(SELECTORS.plusMenuOpen).first();
      if (!(await plus.count())) {
        console.warn('[WARN] "+"メニュー消失');
        break;
      }
      await plus.click();
      await sleep(800);
      const fileBtn = page.locator(SELECTORS.filePickerButton).first();
      if (!(await fileBtn.count())) {
        console.warn('[WARN] 「ファイル」ボタン未発見');
        await page.keyboard.press('Escape').catch(() => {});
        continue;
      }
      const [fileChooser] = await Promise.all([
        page.waitForEvent('filechooser', { timeout: 5000 }).catch(() => null),
        fileBtn.click(),
      ]);
      if (fileChooser) {
        await fileChooser.setFiles(fp);
      } else {
        const inp = page.locator(SELECTORS.fileInput).first();
        if (await inp.count()) {
          await inp.setInputFiles(fp);
        } else {
          console.warn(`[WARN] input[type=file] 出現せず: ${fp}`);
          continue;
        }
      }
      await sleep(4000);
      attached++;
      console.log(`[INFO] 添付 ${attached}/${filePaths.length}: ${fp.split(/[\\/]/).pop()}`);
    } catch (err) {
      console.warn(`[WARN] 添付エラー: ${err.message}`);
    }
  }
  return attached;
}

async function editDraft(page, item) {
  if (!item.draftId) {
    throw new Error(`item ${item.id} に draftId がありません。`);
  }
  const resolvedBody = await resolveBody(item);
  const attachPaths = await resolveAttachments(item.id);
  const runPaid = !!item.publish || FORCE_PAID;
  console.log(`[INFO] id=${item.id} draftId=${item.draftId} publish=${!!item.publish} FORCE_PAID=${FORCE_PAID} runPaid=${runPaid} attach=${attachPaths.length}`);

  // ─── Step 1: 有料記事化 + 価格設定（/publish/ への直接URL遷移、ボタンクリックなし）
  let paidEnabled = false;
  let priceSet = false;
  if (runPaid) {
    const cfg = await configurePaidSettings(page, item.draftId, PRICE_YEN);
    paidEnabled = cfg.paidEnabled;
    priceSet = cfg.priceSet;
  }

  // ─── Step 2: /edit/ に直接URL遷移
  const draftUrl = `https://note.com/notes/${item.draftId}/edit`;
  await page.goto(draftUrl, { waitUntil: 'domcontentloaded' });
  await randDelay(3000, 5000);

  // ─── Step 3: タイトル更新（指定時のみ）
  if (item.title && item.title.trim()) {
    try {
      const titleEl = page.locator(SELECTORS.titleInput).first();
      if (await titleEl.count()) {
        await titleEl.click();
        await randDelay(400, 900);
        await page.keyboard.press('Control+A');
        await page.keyboard.press('Delete');
        await randDelay(200, 500);
        for (const ch of item.title) {
          await titleEl.type(ch, { delay: 40 + Math.floor(Math.random() * 80) });
        }
        await randDelay(800, 1500);
      }
    } catch (err) {
      console.warn('[WARN] タイトル更新スキップ:', err.message);
    }
  }

  // ─── Step 4: 本文置換
  await page.waitForSelector(SELECTORS.bodyEditor, { timeout: 20000 });
  const body = page.locator(SELECTORS.bodyEditor).first();
  await body.click();
  await randDelay(500, 1000);
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Delete');
  await randDelay(500, 1000);

  const paragraphs = (resolvedBody || '').split('\n');
  for (let i = 0; i < paragraphs.length; i++) {
    const line = paragraphs[i];
    if (line.length > 0) {
      for (const ch of line) {
        await body.type(ch, { delay: 25 + Math.floor(Math.random() * 60) });
      }
    }
    if (i < paragraphs.length - 1) {
      await page.keyboard.press('Enter');
      await sleep(120 + Math.floor(Math.random() * 200));
    }
  }
  await randDelay(2000, 4000);

  // ─── Step 5: 有料境界線 挿入 (🔑 アクセスコード 直前)
  let boundarySet = false;
  if (runPaid) {
    boundarySet = await insertPaidBoundary(page);
  }

  // ─── Step 6: docx 添付
  let attachedCount = 0;
  if (attachPaths.length > 0) {
    attachedCount = await attachFiles(page, attachPaths);
  }

  // ─── Step 7: 保存 or 公開
  if (item.publish) {
    // 本番公開モードのみ「公開する」ボタンクリック
    const pubBtn = page.locator(SELECTORS.publishButton).first();
    if (await pubBtn.count()) {
      await pubBtn.click();
      await randDelay(3000, 5000);
    }
    return { result: 'published', attached: attachedCount, priceSet, boundarySet, paidEnabled };
  } else {
    // draft保存（TEST_PAID時もここに来る）
    await page.locator(SELECTORS.saveDraftButton).first().click();
    await randDelay(3000, 5000);
    return { result: 'draft_saved', attached: attachedCount, priceSet, boundarySet, paidEnabled };
  }
}

async function main() {
  const { max } = parseArgs();
  const storageState = parseStorageState();
  console.log(`[INFO] FORCE_PAID(NOTE_TEST_PAID)=${FORCE_PAID}`);

  const queue = await loadQueue();
  const allPendings = (queue.items || []).filter((i) => i.status === 'pending');
  const pendings = allPendings.filter((i) => i.draftId && i.draftId.trim() !== '');
  const skipped = allPendings.length - pendings.length;
  if (skipped > 0) {
    console.warn(`[WARN] draftId 未設定の pending を ${skipped} 件スキップ`);
  }
  if (pendings.length === 0) {
    console.log('[INFO] 投稿対象なし。終了します。');
    return;
  }
  const targets = pendings.slice(0, max);
  console.log(`[INFO] 投稿対象: ${targets.length} 件 (max=${max})`);

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
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  try {
    for (const item of targets) {
      try {
        console.log(`[INFO] 編集開始: id=${item.id} draftId=${item.draftId} title="${item.title}"`);
        const ret = await editDraft(page, item);
        item.status = ret.result;
        item.posted_at = new Date().toISOString();
        item.error = null;
        item.attached = ret.attached;
        item.priceSet = ret.priceSet;
        item.boundarySet = ret.boundarySet;
        item.paidEnabled = ret.paidEnabled;
        console.log(`[OK] ${ret.result}: id=${item.id} attached=${ret.attached} priceSet=${ret.priceSet} boundarySet=${ret.boundarySet} paidEnabled=${ret.paidEnabled}`);
        await saveQueue(queue);
        await randDelay(15000, 30000);
      } catch (err) {
        const msg = String(err?.message || err);
        item.status = `error: ${msg.slice(0, 200)}`;
        item.error = msg;
        console.error(`[ERROR] 投稿失敗: id=${item.id} ${msg}`);
        await saveQueue(queue);
        await randDelay(5000, 10000);
      }
    }
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((err) => {
  console.error('[FATAL]', err);
  process.exit(1);
});
