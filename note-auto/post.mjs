// note-auto/post.mjs
// ───────────────────────────────────────────────────────────────
// note.com 下書き編集型自動投稿（B案・新方針 / v3）
//
// 完全自動ログインは bot 検知で失敗しやすいため、Playwright の storageState
// に保存された認証済みセッションを再利用する。queue.json で指定された
// `draftId` の下書きを開いて、本文を流し込み、下書き保存 or 公開する。
//
// 2026-05-16 v3 改修:
//   - 添付docx: "+"メニュー → 「ファイル」ボタン click → input[type=file] 出現後 setInputFiles
//   - 有料境界線: 🔑アクセスコード H2 直前にカーソル設定 → "+"メニュー → 「有料エリア指定」
//   - 価格 100円: 公開設定パネルへ遷移 → 多段セレクタ盲打ち → React-safe value setter
//   - 47歳除去 / アプリリンク / アクセスコード は preprocess-articles.mjs 側で対応済
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

let ACCESS_CODES = {};
try {
  if (existsSync(ACCESS_CODES_PATH)) {
    ACCESS_CODES = JSON.parse(await readFile(ACCESS_CODES_PATH, 'utf-8'));
  }
} catch (err) {
  console.warn('[WARN] access_codes.json 読み込み失敗:', err.message);
}

// ---------- body preprocessing (保守互換: preprocess-articles.mjs 未走時の補助) ----------

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

// ---------- DOMセレクタ ----------

const SELECTORS = {
  bodyEditor: '.ProseMirror',
  titleInput: 'textarea[placeholder*="タイトル"]',
  saveDraftButton: 'button:has-text("下書き保存")',
  publishStepButton: 'button:has-text("公開に進む")',
  publishButton: 'button:has-text("公開")',
  publishConfirmButton: 'button:has-text("公開する")',
  plusMenuOpen: '[aria-label="メニューを開く"]',
  filePickerButton: 'button:has-text("ファイル")',
  paidBoundaryButton: 'button:has-text("有料エリア指定")',
  fileInput: 'input[type="file"]',
};

// ---------- helpers ----------

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
  if (!raw) {
    throw new Error('NOTE_STORAGE_STATE が未設定です。');
  }
  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`NOTE_STORAGE_STATE が JSON として不正です: ${err.message}`);
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
    // 直前のDOM位置にRange/Selection設定
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

/** 🔑直前に有料境界線を挿入 */
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
    await sleep(1500);
    console.log('[INFO] 有料境界線 挿入完了 (🔑 アクセスコード 直前)');
    return true;
  } catch (err) {
    console.warn('[WARN] insertPaidBoundary エラー:', err.message);
    return false;
  }
}

/** ファイル添付。"+"メニュー → 「ファイル」 → input[type=file] setInputFiles */
async function attachFiles(page, filePaths) {
  if (filePaths.length === 0) return 0;
  let attached = 0;
  // 末尾にカーソルを移動（添付は本文末尾）
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
      // 「ファイル」ボタンclickで input[type=file] が露出する想定
      const [fileChooser] = await Promise.all([
        page.waitForEvent('filechooser', { timeout: 5000 }).catch(() => null),
        fileBtn.click(),
      ]);
      if (fileChooser) {
        await fileChooser.setFiles(fp);
      } else {
        // filechooserイベント取れない場合は input を直接探す
        const inp = page.locator(SELECTORS.fileInput).first();
        if (await inp.count()) {
          await inp.setInputFiles(fp);
        } else {
          console.warn(`[WARN] input[type=file] 出現せず: ${fp}`);
          continue;
        }
      }
      await sleep(4000); // アップロード待ち
      attached++;
      console.log(`[INFO] 添付 ${attached}/${filePaths.length}: ${fp.split(/[\\/]/).pop()}`);
    } catch (err) {
      console.warn(`[WARN] 添付エラー: ${err.message}`);
    }
  }
  return attached;
}

/** 価格 100円 設定。publish=true 時のみ呼ぶ。 */
async function setPrice(page, yen) {
  try {
    // 公開設定/公開に進む を押す
    const pubBtn = page.locator(SELECTORS.publishStepButton).first();
    if (await pubBtn.count()) {
      await pubBtn.click();
      await randDelay(2000, 3500);
    } else {
      console.warn('[WARN] 「公開に進む」ボタン未発見');
    }
    // 「有料」「販売」関連トグル試行
    for (const txt of ['有料記事', '販売', '有料エリア']) {
      const t = page.locator(`button:has-text("${txt}"), label:has-text("${txt}")`).first();
      if ((await t.count()) > 0) {
        await t.click().catch(() => {});
        await sleep(700);
      }
    }
    // 価格input 多段フォールバック (Reactの内部setter経由でセット)
    const set = await page.evaluate((yen) => {
      const candidates = [
        'input[name="price"]',
        'input[placeholder*="価格"]',
        'input[type="number"][min="100"]',
        '[data-testid*="price"] input',
        'input[aria-label*="価格"]',
        'input[type="number"]:not([readonly])',
      ];
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      for (const sel of candidates) {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
          if (el.offsetParent === null) continue;
          setter.call(el, String(yen));
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          el.dispatchEvent(new Event('blur', { bubbles: true }));
          return { ok: true, selector: sel, value: el.value };
        }
      }
      return { ok: false };
    }, yen);
    if (set.ok) {
      console.log(`[INFO] 価格 ${yen}円 設定 (sel=${set.selector})`);
      return true;
    }
    console.warn('[WARN] 価格input 未発見 → スキップ');
    return false;
  } catch (err) {
    console.warn('[WARN] setPrice エラー:', err.message);
    return false;
  }
}

// ---------- core ----------

async function editDraft(page, item) {
  if (!item.draftId) {
    throw new Error(`item ${item.id} に draftId がありません。`);
  }
  const resolvedBody = await resolveBody(item);
  const attachPaths = await resolveAttachments(item.id);
  const draftUrl = `https://note.com/notes/${item.draftId}/edit`;
  console.log(`[INFO] open draft: ${draftUrl}`);
  console.log(`[INFO] attachments: ${attachPaths.length} files`);
  await page.goto(draftUrl, { waitUntil: 'domcontentloaded' });
  await randDelay(3000, 5000);

  // タイトル更新（指定時のみ）
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

  // 有料境界線 挿入 (🔑 アクセスコード 直前)
  let boundarySet = false;
  if (item.publish) {
    boundarySet = await insertPaidBoundary(page);
  }

  // 添付docx
  let attachedCount = 0;
  if (attachPaths.length > 0) {
    attachedCount = await attachFiles(page, attachPaths);
  }

  // 価格 (publish=true時のみ)
  let priceSet = false;
  if (item.publish) {
    priceSet = await setPrice(page, PRICE_YEN);
  }

  if (item.publish) {
    const pubBtn = page.locator(SELECTORS.publishButton).first();
    if (await pubBtn.count()) {
      await pubBtn.click();
      await randDelay(2000, 4000);
    }
    const confirm = page.locator(SELECTORS.publishConfirmButton).first();
    if (await confirm.count()) {
      await confirm.click();
      await randDelay(3000, 5000);
    }
    return { result: 'published', attached: attachedCount, priceSet, boundarySet };
  } else {
    await page.locator(SELECTORS.saveDraftButton).first().click();
    await randDelay(3000, 5000);
    return { result: 'draft_saved', attached: attachedCount, priceSet, boundarySet };
  }
}

async function main() {
  const { max } = parseArgs();
  const storageState = parseStorageState();

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
        console.log(`[OK] ${ret.result}: id=${item.id} attached=${ret.attached} priceSet=${ret.priceSet} boundarySet=${ret.boundarySet}`);
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
