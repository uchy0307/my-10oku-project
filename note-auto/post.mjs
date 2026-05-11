// ⚠️ note.com Terms of Service グレーゾーン
// 自動操作・自動投稿は規約で明示禁止されている。本スクリプトは
// 1) 1日2本以下 2) ランダム遅延 3) 人間操作シミュレート で BAN回避を試みる。
// アカウント凍結のリスクは残る。利用者責任で使用すること。

import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const QUEUE_PATH = join(__dirname, 'queue.json');

// セレクタは note 側 DOM 変更時にここを更新
const SELECTORS = {
  loginEmail: 'input[type="email"]',
  loginPassword: 'input[type="password"]',
  loginSubmit: 'button[type="submit"]',
  newPostButton: 'a[href="/notes/new"]',
  titleInput: 'textarea[placeholder*="タイトル"]',
  bodyEditor: 'div[contenteditable="true"]',
  saveDraftButton: 'button:has-text("下書き保存")',
  publishButton: 'button:has-text("公開")',
  publishConfirmButton: 'button:has-text("公開する")',
};

const NOTE_URL = 'https://note.com';
const LOGIN_URL = 'https://note.com/login';

// ---------- helpers ----------

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const randDelay = (min = 3000, max = 7000) =>
  sleep(min + Math.floor(Math.random() * (max - min)));

async function humanType(locator, text) {
  // 人間っぽいタイピング（1文字あたり 40-120ms ばらつき）
  for (const ch of text) {
    await locator.type(ch, { delay: 40 + Math.floor(Math.random() * 80) });
  }
}

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

// ---------- core ----------

async function login(page, email, password) {
  await page.goto(LOGIN_URL, { waitUntil: 'domcontentloaded' });
  await randDelay(1500, 3000);

  await page.waitForSelector(SELECTORS.loginEmail, { timeout: 15000 });
  await humanType(page.locator(SELECTORS.loginEmail), email);
  await randDelay(800, 1500);
  await humanType(page.locator(SELECTORS.loginPassword), password);
  await randDelay(1000, 2000);
  await page.locator(SELECTORS.loginSubmit).click();
  await page.waitForLoadState('networkidle', { timeout: 20000 });
  await randDelay(2000, 4000);
}

async function createPost(page, item) {
  // 新規投稿ページへ
  await page.goto(`${NOTE_URL}/notes/new`, { waitUntil: 'domcontentloaded' });
  await randDelay(3000, 5000);

  // タイトル入力
  await page.waitForSelector(SELECTORS.titleInput, { timeout: 15000 });
  await page.locator(SELECTORS.titleInput).click();
  await randDelay(500, 1000);
  await humanType(page.locator(SELECTORS.titleInput), item.title);
  await randDelay(1500, 3000);

  // 本文入力
  const body = page.locator(SELECTORS.bodyEditor).first();
  await body.click();
  await randDelay(500, 1000);
  // 改行を含む本文は分割して入力
  const paragraphs = item.body.split('\n');
  for (let i = 0; i < paragraphs.length; i++) {
    await humanType(body, paragraphs[i]);
    if (i < paragraphs.length - 1) {
      await page.keyboard.press('Enter');
      await sleep(150 + Math.floor(Math.random() * 200));
    }
  }
  await randDelay(2000, 4000);

  // 下書き保存 or 公開
  if (item.publish) {
    await page.locator(SELECTORS.publishButton).first().click();
    await randDelay(2000, 4000);
    await page.locator(SELECTORS.publishConfirmButton).first().click();
  } else {
    await page.locator(SELECTORS.saveDraftButton).first().click();
  }
  await randDelay(3000, 5000);
}

async function main() {
  const { max } = parseArgs();
  const email = process.env.NOTE_EMAIL;
  const password = process.env.NOTE_PASSWORD;

  if (!email || !password) {
    console.error('[ERROR] NOTE_EMAIL / NOTE_PASSWORD が未設定です。');
    process.exit(1);
  }

  const queue = await loadQueue();
  const pendings = queue.items.filter((i) => i.status === 'pending');
  if (pendings.length === 0) {
    console.log('[INFO] pending な記事はありません。終了します。');
    return;
  }

  // B案ルール: 1回の起動で max 件まで（既定 1）
  const targets = pendings.slice(0, max);
  console.log(`[INFO] 投稿対象: ${targets.length} 件 (max=${max})`);

  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-blink-features=AutomationControlled'],
  });
  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    timezoneId: 'Asia/Tokyo',
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  try {
    await login(page, email, password);
    console.log('[OK] ログイン完了');

    for (const item of targets) {
      try {
        console.log(`[INFO] 投稿開始: id=${item.id} title="${item.title}"`);
        await createPost(page, item);
        item.status = 'posted';
        item.posted_at = new Date().toISOString();
        item.error = null;
        console.log(`[OK] 投稿完了: id=${item.id}`);
        await saveQueue(queue);
        // 連続投稿の間隔
        await randDelay(15000, 30000);
      } catch (err) {
        item.status = 'error';
        item.error = String(err?.message || err);
        console.error(`[ERROR] 投稿失敗: id=${item.id} ${item.error}`);
        await saveQueue(queue);
        throw err; // 1件でも失敗したら abort
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
