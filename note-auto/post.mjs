// note-auto/post.mjs
// ───────────────────────────────────────────────────────────────
// note.com 下書き編集型自動投稿（B案・新方針 / v6）
//
// 2026-05-16 v6 改修:
//   - configurePaidSettings: /publish/ で radio + price 設定後
//     「有料エリア設定」ボタン (header の保存系ボタン) を click してサーバ保存
//     その後 /edit/ に強制URL遷移
//   - 価格 input は Playwright の locator.type() で実キーストローク入力
//     （React state にも DOM にも確実に反映）
//   - 「公開する」ボタンは publish=true 時のみクリック
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
  out = out.split('\n').map((l) => l.replace(/[ \t]{2,}/g, ' ').replace(/^ +| +$/g, '')).join('\n');
  out = out.replace(/\n{4,}/g, '\n\n\n');
  const code = ACCESS_CODES[articleId];
  if (code) {
    const link = `${URL_PATTERN}${articleId}`;
    if (!out.includes(link)) {
      out += `\n\n\n\n---\n\n▼アプリで深く問う\n\n${link}\n\nアクセスコード: ${code}\n`;
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
    if (!existsSync(fp)) throw new Error(`本文が見つかりません: ${fp}`);
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
  publishSaveSettingsBtn: 'button:has-text("有料エリア設定")',
  priceInputCandidates: 'input[placeholder="300"], input[type="text"][class*="sc-85966dc5"]',
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const randDelay = (min = 3000, max = 7000) => sleep(min + Math.floor(Math.random() * (max - min)));

function parseArgs() {
  const args = { max: 1 };
  for (const a of process.argv.slice(2)) {
    const m = a.match(/^--max=(\d+)$/);
    if (m) args.max = Number(m[1]);
  }
  return args;
}

async function loadQueue() { return JSON.parse(await readFile(QUEUE_PATH, 'utf-8')); }
async function saveQueue(q) { await writeFile(QUEUE_PATH, JSON.stringify(q, null, 2) + '\n', 'utf-8'); }

function parseStorageState() {
  const raw = process.env.NOTE_STORAGE_STATE;
  if (!raw) throw new Error('NOTE_STORAGE_STATE 未設定');
  return JSON.parse(raw);
}

/** /publish/ で 有料 radio + 価格 設定 → 「有料エリア設定」ボタン click でサーバ保存 → /edit/ 強制遷移 */
async function configurePaidSettings(page, draftId, yen) {
  const result = { paidEnabled: false, priceSet: false, savedToServer: false };
  try {
    const publishUrl = `https://editor.note.com/notes/${draftId}/publish/`;
    console.log(`[INFO] publish settings へ直接遷移: ${publishUrl}`);
    await page.goto(publishUrl, { waitUntil: 'domcontentloaded' });
    await randDelay(3000, 4500);

    // 有料 radio (input[name="is_paid"] index 1)
    const radioResult = await page.evaluate(() => {
      const radios = [...document.querySelectorAll('input[type="radio"][name="is_paid"]')];
      if (radios.length < 2) return 'no_radios';
      const paid = radios[1];
      if (paid.checked) return 'already_checked';
      paid.click();
      paid.dispatchEvent(new Event('change', { bubbles: true }));
      return paid.checked ? 'just_checked' : 'click_failed';
    });
    console.log(`[INFO] 有料 radio: ${radioResult}`);
    result.paidEnabled = ['already_checked', 'just_checked'].includes(radioResult);
    await sleep(2000);

    // 価格 input — Playwright の locator で実キーストローク入力
    try {
      const priceLoc = page.locator(SELECTORS.priceInputCandidates).first();
      const cnt = await priceLoc.count();
      if (cnt > 0) {
        await priceLoc.click({ timeout: 5000 });
        await sleep(400);
        // 既存値クリア
        await page.keyboard.press('Control+A').catch(() => {});
        await page.keyboard.press('Delete').catch(() => {});
        await sleep(200);
        // 実キーストロークで入力
        for (const ch of String(yen)) {
          await page.keyboard.type(ch, { delay: 80 });
        }
        await sleep(500);
        await page.keyboard.press('Tab'); // フォーカス外し
        await sleep(800);
        const v = await priceLoc.inputValue().catch(() => '');
        result.priceSet = (v === String(yen));
        console.log(`[INFO] price input typed value="${v}"`);
      } else {
        console.warn('[WARN] price input 未発見');
      }
    } catch (err) {
      console.warn('[WARN] price input エラー:', err.message);
    }

    // 「有料エリア設定」ボタン click でサーバ保存
    try {
      const saveBtn = page.locator(SELECTORS.publishSaveSettingsBtn).first();
      if ((await saveBtn.count()) > 0) {
        console.log('[INFO] 「有料エリア設定」ボタン押下…');
        await saveBtn.click();
        await randDelay(3000, 5000);
        result.savedToServer = true;
      } else {
        console.warn('[WARN] 「有料エリア設定」ボタン未発見');
      }
    } catch (err) {
      console.warn('[WARN] 有料エリア設定 click エラー:', err.message);
    }

    // 現URL確認 — /edit/ 以外なら強制 navigate
    const curUrl = page.url();
    console.log(`[INFO] 保存後URL: ${curUrl}`);
    if (!curUrl.includes('/edit')) {
      const editUrl = `https://editor.note.com/notes/${draftId}/edit/`;
      console.log(`[INFO] /edit/ に強制遷移: ${editUrl}`);
      await page.goto(editUrl, { waitUntil: 'domcontentloaded' });
      await randDelay(3000, 4500);
    }
  } catch (err) {
    console.warn('[WARN] configurePaidSettings エラー:', err.message);
    result.err = err.message;
  }
  return result;
}

async function placeCursorBeforeAccessCode(page) {
  const ok = await page.evaluate(() => {
    const pm = document.querySelector('.ProseMirror');
    if (!pm) return { ok: false };
    const items = [...pm.querySelectorAll('h1,h2,h3,p')];
    const target = items.find((el) => /🔑/.test(el.textContent || ''));
    if (!target) return { ok: false };
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
    if (!(await placeCursorBeforeAccessCode(page))) {
      console.warn('[WARN] 🔑未発見 → 境界線スキップ');
      return false;
    }
    await sleep(500);
    const plus = page.locator(SELECTORS.plusMenuOpen).first();
    if (!(await plus.count())) { console.warn('[WARN] "+"メニュー未発見'); return false; }
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
    const verified = await page.evaluate(() => {
      const strongs = [...document.querySelectorAll('.ProseMirror strong')];
      return strongs.some(s => /有料エリア/.test(s.textContent || ''));
    });
    console.log(`[INFO] 境界線 verified=${verified}`);
    return verified;
  } catch (err) {
    console.warn('[WARN] insertPaidBoundary:', err.message);
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
      if (!(await plus.count())) break;
      await plus.click();
      await sleep(800);
      const fileBtn = page.locator(SELECTORS.filePickerButton).first();
      if (!(await fileBtn.count())) {
        await page.keyboard.press('Escape').catch(() => {});
        continue;
      }
      const [fc] = await Promise.all([
        page.waitForEvent('filechooser', { timeout: 5000 }).catch(() => null),
        fileBtn.click(),
      ]);
      if (fc) {
        await fc.setFiles(fp);
      } else {
        const inp = page.locator(SELECTORS.fileInput).first();
        if (await inp.count()) await inp.setInputFiles(fp);
        else continue;
      }
      await sleep(4000);
      attached++;
      console.log(`[INFO] 添付 ${attached}/${filePaths.length}`);
    } catch (err) { console.warn(`[WARN] 添付:`, err.message); }
  }
  return attached;
}

async function editDraft(page, item) {
  if (!item.draftId) throw new Error(`item ${item.id} に draftId なし`);
  const resolvedBody = await resolveBody(item);
  const attachPaths = await resolveAttachments(item.id);
  const runPaid = !!item.publish || FORCE_PAID;
  console.log(`[INFO] id=${item.id} publish=${!!item.publish} FORCE_PAID=${FORCE_PAID} runPaid=${runPaid}`);

  let paidEnabled = false, priceSet = false, savedToServer = false;
  if (runPaid) {
    const cfg = await configurePaidSettings(page, item.draftId, PRICE_YEN);
    paidEnabled = cfg.paidEnabled;
    priceSet = cfg.priceSet;
    savedToServer = cfg.savedToServer;
  }

  // 必ず /edit/ にいることを保証
  if (!page.url().includes('/edit')) {
    await page.goto(`https://note.com/notes/${item.draftId}/edit`, { waitUntil: 'domcontentloaded' });
    await randDelay(3000, 5000);
  }

  // タイトル
  if (item.title && item.title.trim()) {
    try {
      const titleEl = page.locator(SELECTORS.titleInput).first();
      if (await titleEl.count()) {
        await titleEl.click();
        await randDelay(400, 900);
        await page.keyboard.press('Control+A');
        await page.keyboard.press('Delete');
        await randDelay(200, 500);
        for (const ch of item.title) await titleEl.type(ch, { delay: 40 + Math.floor(Math.random() * 80) });
        await randDelay(800, 1500);
      }
    } catch (err) { console.warn('[WARN] title:', err.message); }
  }

  // 本文置換
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

  // 境界線 (有料設定がサーバ保存済の状態で挿入)
  let boundarySet = false;
  if (runPaid) boundarySet = await insertPaidBoundary(page);

  // 添付
  let attachedCount = 0;
  if (attachPaths.length > 0) attachedCount = await attachFiles(page, attachPaths);

  // 保存
  if (item.publish) {
    const pubBtn = page.locator(SELECTORS.publishButton).first();
    if (await pubBtn.count()) {
      await pubBtn.click();
      await randDelay(3000, 5000);
    }
    return { result: 'published', attached: attachedCount, priceSet, boundarySet, paidEnabled, savedToServer };
  } else {
    await page.locator(SELECTORS.saveDraftButton).first().click();
    await randDelay(3000, 5000);
    return { result: 'draft_saved', attached: attachedCount, priceSet, boundarySet, paidEnabled, savedToServer };
  }
}

async function main() {
  const { max } = parseArgs();
  const storageState = parseStorageState();
  console.log(`[INFO] FORCE_PAID=${FORCE_PAID}`);
  const queue = await loadQueue();
  const pendings = (queue.items || []).filter((i) => i.status === 'pending' && i.draftId && i.draftId.trim());
  if (pendings.length === 0) { console.log('[INFO] 対象なし'); return; }
  const targets = pendings.slice(0, max);
  console.log(`[INFO] 対象 ${targets.length} 件`);

  const headless = process.env.NOTE_HEADLESS !== 'false';
  const browser = await chromium.launch({ headless, args: ['--disable-blink-features=AutomationControlled'] });
  const context = await browser.newContext({
    storageState,
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    locale: 'ja-JP', timezoneId: 'Asia/Tokyo', viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();
  try {
    for (const item of targets) {
      try {
        const ret = await editDraft(page, item);
        item.status = ret.result;
        item.posted_at = new Date().toISOString();
        item.error = null;
        item.attached = ret.attached;
        item.priceSet = ret.priceSet;
        item.boundarySet = ret.boundarySet;
        item.paidEnabled = ret.paidEnabled;
        item.savedToServer = ret.savedToServer;
        console.log(`[OK] id=${item.id} attached=${ret.attached} priceSet=${ret.priceSet} boundarySet=${ret.boundarySet} paidEnabled=${ret.paidEnabled} savedToServer=${ret.savedToServer}`);
        await saveQueue(queue);
        await randDelay(15000, 30000);
      } catch (err) {
        const msg = String(err?.message || err);
        item.status = `error: ${msg.slice(0, 200)}`;
        item.error = msg;
        console.error(`[ERROR] id=${item.id} ${msg}`);
        await saveQueue(queue);
        await randDelay(5000, 10000);
      }
    }
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((err) => { console.error('[FATAL]', err); process.exit(1); });
