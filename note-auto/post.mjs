// note-auto/post.mjs
// ───────────────────────────────────────────────────────────────
// note.com 下書き編集型自動投稿（B案・新方針 / v7）
//
// 2026-05-16 v7 改修（実機UIフロー検証済み）:
//   - /publish/ で 有料radio + 価格100入力（Playwright keyboard）
//   - 「有料エリア設定」ボタン click → 境界線プレビュー画面に遷移
//   - 「ラインをこの場所に変更」(🔑 H2 直前) ボタン click → 境界線移動
//   - publish=true 時のみ「投稿する」ボタン click → 本番公開
//   - publish=false (FORCE_PAID) 時はキャンセル→/edit/→下書き保存
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
  console.warn('[WARN] access_codes.json:', err.message);
}

function preprocessBody(body, articleId) {
  let out = body;
  out = out.replace(/47歳の/g, '').replace(/47歳が/g, '私が').replace(/47歳に/g, '').replace(/47歳/g, '').replace(/[#＃]\s?47歳\s*/g, '');
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
  if (item.body && typeof item.body === 'string' && item.body.trim().length > 0) raw = item.body;
  else {
    const fp = join(ARTICLES_DIR, `note_${item.id}.md`);
    if (!existsSync(fp)) throw new Error(`本文なし: ${fp}`);
    raw = await readFile(fp, 'utf-8');
  }
  return preprocessBody(raw, item.id);
}

async function resolveAttachments(id) {
  const dir = join(ATTACHMENTS_DIR, `app${id}`);
  if (!existsSync(dir)) { console.warn(`[WARN] attach dir 不倨: ${dir}`); return []; }
  const entries = await readdir(dir);
  return entries.filter((f) => f.toLowerCase().endsWith('.docx')).map((f) => join(dir, f));
}

const SELECTORS = {
  bodyEditor: '.ProseMirror',
  titleInput: 'textarea[placeholder*="タイトル"]',
  saveDraftButton: 'button:has-text("下書き保存")',
  cancelButton: 'button:has-text("キャンセル")',
  plusMenuOpen: '[aria-label="メニューを開く"], [data-testid="plusMenu"], button[aria-label*="メニュー"], button[aria-label*="追加"]',
  filePickerButton: 'button:has-text("ファイル"), [data-testid*="file"], button:has-text("File")',
  fileInput: 'input[type="file"]',
  paidConfigBtn: 'button:has-text("有料エリア設定")',
  publishNowBtn: 'button:has-text("投稿する")',
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
      if (fc) await fc.setFiles(fp);
      else {
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

/** /publish/ 経由で 有料設定+価格+境界線移動+(publish=true時のみ)投稿する */
async function configurePaidAndPublish(page, draftId, yen, doPublish) {
  const result = { paidConfigured: false, boundaryRepositioned: false, published: false, anonStatus: null };
  try {
    const publishUrl = `https://editor.note.com/notes/${draftId}/publish/`;
    console.log(`[INFO] /publish/ へ遷移: ${publishUrl}`);
    await page.goto(publishUrl, { waitUntil: 'domcontentloaded' });
    await randDelay(3500, 5000);

    // 1. 有料 radio ON
    const radioState = await page.evaluate(() => {
      const radios = [...document.querySelectorAll('input[type="radio"][name="is_paid"]')];
      if (radios.length < 2) return 'no_radios';
      const paid = radios[1];
      if (paid.checked) return 'already';
      paid.click();
      paid.dispatchEvent(new Event('change', { bubbles: true }));
      return paid.checked ? 'just' : 'fail';
    });
    console.log(`[INFO] 有料radio: ${radioState}`);
    await sleep(2000);

    // 2. 価格 input - Playwright keyboard で実入力
    try {
      const priceLoc = page.locator('input[placeholder="300"]').first();
      if (await priceLoc.count()) {
        await priceLoc.scrollIntoViewIfNeeded();
        await priceLoc.click({ timeout: 5000 });
        await sleep(400);
        await page.keyboard.press('Control+A');
        await page.keyboard.press('Delete');
        await sleep(200);
        for (const ch of String(yen)) {
          await page.keyboard.type(ch, { delay: 80 });
        }
        await sleep(500);
        await page.keyboard.press('Tab');
        await sleep(1000);
        const v = await priceLoc.inputValue().catch(() => '');
        result.paidConfigured = (v === String(yen) || v === String(yen) + '0');
        console.log(`[INFO] 価格 typed value="${v}"`);
      }
    } catch (err) { console.warn('[WARN] price input:', err.message); }

    // 3. 「有料エリア設定」ボタン → boundary preview 画面
    const paidBtn = page.locator(SELECTORS.paidConfigBtn).first();
    if (!(await paidBtn.count())) {
      console.warn('[WARN] 「有料エリア設定」ボタン未発見');
      return result;
    }
    console.log('[INFO] 「有料エリア設定」ボタン押下');
    await paidBtn.click();
    await randDelay(3500, 5500);

    // 4. 境界線を 🔑 H2 直前に移動
    const moveResult = await page.evaluate(() => {
      const keyEl = [...document.querySelectorAll('h2')].find(el => /🔑/.test(el.textContent || ''));
      if (!keyEl) return { ok: false, reason: 'no_key' };
      const keyAbsY = keyEl.getBoundingClientRect().top + window.scrollY;
      const changeBtns = [...document.querySelectorAll('button')]
        .filter(b => (b.textContent || '').trim() === 'ラインをこの場所に変更')
        .map(b => ({ absY: b.getBoundingClientRect().top + window.scrollY, btn: b }))
        .filter(x => x.absY < keyAbsY)
        .sort((a, b) => b.absY - a.absY);
      if (changeBtns.length === 0) return { ok: false, reason: 'no_btn_before_key' };
      changeBtns[0].btn.click();
      return { ok: true, movedToY: changeBtns[0].absY, keyAbsY };
    });
    console.log(`[INFO] 境界線移動: ${JSON.stringify(moveResult)}`);
    result.boundaryRepositioned = moveResult.ok;
    await sleep(2500);

    if (!doPublish) {
      // draft mode: キャンセルで /edit/ に戻り保存（boundary state は保持）
      console.log('[INFO] draft mode - キャンセルへ');
      const cancelBtn = page.locator(SELECTORS.cancelButton).first();
      if (await cancelBtn.count()) {
        await cancelBtn.click();
        await randDelay(2000, 3000);
      }
      return result;
    }

    // 5. 「投稿する」ボタン → 本番公開
    const postBtn = page.locator(SELECTORS.publishNowBtn).first();
    if (!(await postBtn.count())) {
      console.warn('[WARN] 「投稿する」ボタン未発見');
      return result;
    }
    console.log('[INFO] 「投稿する」ボタン押下 → 本番公開');
    await postBtn.click();
    await randDelay(6000, 9000);

    // 6. 匿名APIで公開確認
    try {
      const anonStatus = await page.evaluate(async (key) => {
        const r = await fetch(`https://note.com/api/v3/notes/${key}?draft=false`, { credentials: 'omit', headers: { accept: 'application/json' } });
        return r.status;
      }, draftId);
      result.anonStatus = anonStatus;
      result.published = (anonStatus === 200);
      console.log(`[INFO] 匿名API 検証: status=${anonStatus} published=${result.published}`);
    } catch (err) { console.warn('[WARN] anon verify:', err.message); }
  } catch (err) {
    console.warn('[WARN] configurePaidAndPublish:', err.message);
    result.err = err.message;
  }
  return result;
}

async function editDraft(page, item) {
  if (!item.draftId) throw new Error(`item ${item.id} に draftId なし`);
  const resolvedBody = await resolveBody(item);
  const attachPaths = await resolveAttachments(item.id);
  const runPaid = !!item.publish || FORCE_PAID;
  console.log(`[INFO] id=${item.id} publish=${!!item.publish} FORCE_PAID=${FORCE_PAID} runPaid=${runPaid}`);

  // Step 1: /edit/ で 本文置換 + 添付
  const draftUrl = `https://note.com/notes/${item.draftId}/edit`;
  await page.goto(draftUrl, { waitUntil: 'domcontentloaded' });
  await randDelay(3000, 5000);

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

  // Step 2: 添付docx
  let attachedCount = 0;
  if (attachPaths.length > 0) attachedCount = await attachFiles(page, attachPaths);
  // Loud verification: if attachments were expected but none uploaded, fail hard.
  if (attachPaths.length > 0 && attachedCount === 0) {
    console.error(`[FATAL] 添付ファイル ${attachPaths.length}件 期待だが 0件しか添付されなかった (article=${articleId}) — 投稿中止`);
    throw new Error('attachment-uploader-failure: expected ' + attachPaths.length + ' but uploaded 0');
  }
  if (attachPaths.length > 0 && attachedCount < attachPaths.length) {
    console.warn(`[WARN] 添付期待 ${attachPaths.length}件中 ${attachedCount}件 のみ成功 (article=${articleId})`);
  }

  // Step 3: 下書き保存（body+添付を確定）
  try {
    await page.locator(SELECTORS.saveDraftButton).first().click({ timeout: 10000 });
    await randDelay(3000, 5000);
  } catch (err) { console.warn('[WARN] save draft:', err.message); }

  // Step 4: 有料化 + 境界線移動 + (publish=true時) 投稿する
  let paidResult = { paidConfigured: false, boundaryRepositioned: false, published: false };
  if (runPaid) {
    paidResult = await configurePaidAndPublish(page, item.draftId, PRICE_YEN, !!item.publish);
  }

  return {
    result: paidResult.published ? 'published' : 'draft_saved',
    attached: attachedCount,
    priceSet: paidResult.paidConfigured,
    boundarySet: paidResult.boundaryRepositioned,
    paidEnabled: paidResult.paidConfigured,
    published: paidResult.published,
    anonStatus: paidResult.anonStatus,
  };
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
        item.published = ret.published;
        item.anonStatus = ret.anonStatus;
        console.log(`[OK] id=${item.id} ${ret.result} attached=${ret.attached} priceSet=${ret.priceSet} boundary=${ret.boundarySet} published=${ret.published} anonStatus=${ret.anonStatus}`);
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
