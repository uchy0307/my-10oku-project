// note-auto/post.mjs
// ───────────────────────────────────────────────────────────────
// note.com 下書き編集型自動投稿（B案・新方針）
//
// 完全自動ログインは bot 検知で失敗しやすいため、Playwright の storageState
// に保存された認証済みセッションを再利用する。queue.json で指定された
// `draftId` の下書きを開いて、本文を流し込み、下書き保存 or 公開する。
//
// env:
//   NOTE_STORAGE_STATE   storageState JSON 文字列（GitHub Secrets で管理）
//                        ローカルでは note-auto/capture-session.mjs で取得して
//                        Secret 化する。
//   NOTE_HEADLESS        "false" 指定で headed 実行（デフォルト true）
//
// queue.json 各 item の draftId フィールドが必須（手動で note.com 上に
// 下書きを1回作って URL から取得しておく）。
// ───────────────────────────────────────────────────────────────

import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const QUEUE_PATH = join(__dirname, 'queue.json');
const ARTICLES_DIR = join(__dirname, '..', 'articles');

/**
 * queue.json item から body を解決する。
 * 優先順位:
 *   1. item.body があればそれを使う (旧互換)
 *   2. articles/note_${item.id}.md を読み込む (新方式)
 *      ※ sync-drafts.mjs が _hasLocalBody フラグを立てている。
 */
async function resolveBody(item) {
  if (item.body && typeof item.body === 'string' && item.body.trim().length > 0) {
    return item.body;
  }
  const fp = join(ARTICLES_DIR, `note_${item.id}.md`);
  if (existsSync(fp)) {
    return await readFile(fp, 'utf-8');
  }
  throw new Error(
    `本文が見つかりません: item.body も articles/note_${item.id}.md も存在しません。`,
  );
}

// note.com DOMセレクタ（editor.note.com 移行後・2026-05 更新）
const SELECTORS = {
  bodyEditor: '.ProseMirror[contenteditable="true"], [role="textbox"][contenteditable="true"]',
  titleInput: 'textarea[placeholder*="タイトル"]',
  saveDraftButton: 'button:has-text("下書き保存")',
  publishSettingsButton: 'button:has-text("公開に進む"), button:has-text("公開設定")',
  publishButton: 'button:has-text("公開する"), button:has-text("公開に進む")',
  publishConfirmButton: 'button:has-text("公開する")',
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

// ---------- core ----------

/** 下書きページに遷移して本文を置換し、保存 or 公開する */
/** Word 添付 + 100円有料設定 */
async function applyPriceAndAttachment(page, id) {
  const num = String(id).padStart(3, '0');
  const attachDir = join(__dirname, 'attachments', `app${num}`);
  // ----- (1) Word 添付 -----
  try {
    if (existsSync(attachDir)) {
      const files = (await readdir(attachDir)).filter(f => f.toLowerCase().endsWith('.docx')).map(f => join(attachDir, f));
      if (files.length > 0) {
        console.log(`[INFO] #${num} attaching ${files.length} docx file(s)`);
        const fileBtn = page.locator('button:has-text("ファイル"), [aria-label*="ファイル"], [data-testid*="file"]').first();
        await fileBtn.click({ timeout: 8000 }).catch(() => {});
        await sleep(500);
        const fileInput = page.locator('input[type="file"]').first();
        await fileInput.setInputFiles(files).catch(e => console.warn(`[WARN] setInputFiles failed: ${e.message}`));
        await sleep(2500);
      } else {
        console.log(`[WARN] #${num} no docx files in ${attachDir}`);
      }
    } else {
      console.log(`[WARN] #${num} attach dir not found: ${attachDir}`);
    }
  } catch (e) {
    console.warn(`[WARN] attach error #${num}: ${e.message}`);
  }

  // ----- (2) 有料エリア境界線 + 100円 -----
  try {
    const body = page.locator('div.ProseMirror[contenteditable="true"]').first();
    await body.click({ position: { x: 100, y: 30 } }).catch(() => {});
    await page.keyboard.press('Control+End').catch(() => {});
    await sleep(300);
    const boundaryBtn = page.locator('button:has-text("有料エリア境界線"), button:has-text("有料エリア"), [aria-label*="有料エリア"]').first();
    await boundaryBtn.click({ timeout: 5000 }).catch(async () => {
      await page.keyboard.type('/有料', { delay: 30 });
      await sleep(400);
      await page.keyboard.press('Enter').catch(() => {});
    });
    await sleep(1500);
    const pubSettings = page.locator(SELECTORS.publishSettingsButton).first();
    await pubSettings.click({ timeout: 5000 }).catch(() => {});
    await sleep(1500);
    const priceInput = page.locator('input[type="number"]:visible, input[name*="price"]:visible, input[placeholder*="価格"]:visible, input[aria-label*="価格"]:visible').first();
    await priceInput.click({ timeout: 5000 }).catch(() => {});
    await page.keyboard.press('Control+A').catch(() => {});
    await page.keyboard.press('Delete').catch(() => {});
    await priceInput.fill('100').catch(async () => {
      await priceInput.type('100', { delay: 30 }).catch(() => {});
    });
    await sleep(800);
    console.log(`[INFO] #${num} price set to 100`);
    await page.keyboard.press('Escape').catch(() => {});
    await sleep(500);
  } catch (e) {
    console.warn(`[WARN] price-setting error #${num}: ${e.message}`);
  }
}

async function editDraft(page, item) {
  if (!item.draftId) {
    throw new Error(`item ${item.id} に draftId がありません。`);
  }
  const resolvedBody = await resolveBody(item);
  // 2026-05: note.com → editor.note.com サブドメインへ移行済み
  const draftUrl = `https://editor.note.com/notes/${item.draftId}/edit/`;
  console.log(`[INFO] open draft: ${draftUrl}`);
  await page.goto(draftUrl, { waitUntil: 'domcontentloaded' });
  await randDelay(5000, 8000);

  // タイトル更新（指定時のみ）
  if (item.title && item.title.trim()) {
    try {
      const titleEl = page.locator(SELECTORS.titleInput).first();
      if (await titleEl.count()) {
        await titleEl.click();
        await randDelay(400, 900);
        // 全選択 → 削除 → 入力
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

  // 本文置換: .ProseMirror をクリック→全選択→削除→流し込み
  // editor.note.com への移行後はレンダリングが遅いので 60s に延長
  await page.waitForSelector(SELECTORS.bodyEditor, { timeout: 60000 });
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
      // 1文字ずつ人間風タイピング
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

  // ===== 100円有料設定 + Word添付 =====
  await applyPriceAndAttachment(page, item.id);
  await randDelay(800, 1500);

  // 保存 or 公開
  if (item.publish) {
    // 「公開に進む」→「公開する」確認
    const pubBtn = page.locator(SELECTORS.publishSettingsButton).first();
    if (await pubBtn.count()) {
      await pubBtn.click();
      await randDelay(2000, 4000);
    }
    await page.locator(SELECTORS.publishButton).first().click();
    await randDelay(2000, 4000);
    const confirm = page.locator(SELECTORS.publishConfirmButton).first();
    if (await confirm.count()) {
      await confirm.click();
      await randDelay(3000, 5000);
    }
    return 'published';
  } else {
    await page.locator(SELECTORS.saveDraftButton).first().click();
    await randDelay(3000, 5000);
    return 'draft_saved';
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
    console.warn(`[WARN] draftId 未設定の pending を ${skipped} 件スキップ（sync-drafts未マッチ）`);
  }
  if (pendings.length === 0) {
    console.log('[INFO] 投稿対象（pending + draftId付き）はありません。終了します。');
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
        const result = await editDraft(page, item);
        item.status = result; // 'draft_saved' or 'published'
        item.posted_at = new Date().toISOString();
        item.error = null;
        console.log(`[OK] ${result}: id=${item.id}`);
        await saveQueue(queue);
        await randDelay(15000, 30000);
      } catch (err) {
        const msg = String(err?.message || err);
        item.status = `error: ${msg.slice(0, 200)}`;
        item.error = msg;
        console.error(`[ERROR] 投稿失敗: id=${item.id} ${msg}`);
        await saveQueue(queue);
        // 1件失敗してもループは継続（全件で同じバグなら次でも落ちる）
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
