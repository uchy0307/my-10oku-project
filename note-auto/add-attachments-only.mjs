// note-auto/add-attachments-only.mjs
// =====================================================================
// 目的: queue.json の attachmentCount=0 な記事に対し、添付ファイルだけ追加する。
// post.mjs が「投稿は成功したが添付が0件」だった既存記事をrescueする。
//
// 動作:
//   1. queue.json 読み込み
//   2. attachmentCount==0 かつ draftId 有りの記事を抽出
//   3. 各記事の編集URL `https://note.com/notes/{draftId}/edit` を開く
//   4. note-auto/attachments/app{id}/*.docx を attachFiles で添付
//   5. 「保存」して queue.json の attachmentCount を更新
//
// 使い方:
//   node note-auto/add-attachments-only.mjs              # 全件
//   node note-auto/add-attachments-only.mjs --max=5      # 上位5件のみ
//   node note-auto/add-attachments-only.mjs --from=015 --to=050
//   node note-auto/add-attachments-only.mjs --dry-run    # 計画表示のみ
//
// 前提:
//   - note-auto/storageState.json でログイン済み（capture-session.mjs実行済）
//   - chromium インストール済（npx playwright install chromium）
// =====================================================================

import { readFile, readdir, writeFile, rename, copyFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..');

const QUEUE_PATH = join(__dirname, 'queue.json');
const STORAGE_PATH = join(__dirname, 'storageState.json');
const ATTACHMENTS_DIR = join(__dirname, 'attachments');

// ───── args ─────
const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const m = a.match(/^--([^=]+)(?:=(.*))?$/);
    return m ? [m[1], m[2] ?? true] : [a, true];
  })
);
const DRY_RUN = !!args['dry-run'];
const MAX = args.max ? parseInt(args.max, 10) : Infinity;
const FROM = args.from ? parseInt(args.from, 10) : 0;
const TO = args.to ? parseInt(args.to, 10) : 999;
const HEADLESS = args.headed ? false : true;

const log = (...a) => console.log('[add-att]', ...a);
const fail = (m) => { console.error('[add-att][FATAL]', m); process.exit(1); };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// ───── helpers ─────
async function resolveAttachments(id) {
  const dir = join(ATTACHMENTS_DIR, `app${id}`);
  if (!existsSync(dir)) return [];
  const entries = await readdir(dir);
  return entries.filter(f => f.toLowerCase().endsWith('.docx')).map(f => join(dir, f));
}

const SELECTORS = {
  fileInput: 'input[type="file"]',
  plusMenuOpen: 'button[aria-label="メニューを開く"], button[aria-label*="挿入"], button[data-testid*="add"]',
  saveButton: 'button[aria-label="保存"], button:has-text("保存")',
  publishStatus: '[data-testid*="publish"], .o-publish-status',
};

async function attachFilesViaInput(page, filePaths) {
  let attached = 0;
  let lastError = null;
  // Place caret at end of editor body
  try {
    await page.evaluate(() => {
      const pm = document.querySelector('.ProseMirror');
      if (!pm) return;
      const last = pm.lastElementChild;
      if (!last) return;
      const r = document.createRange();
      r.selectNodeContents(last);
      r.collapse(false);
      const sel = window.getSelection();
      sel.removeAllRanges(); sel.addRange(r);
      last.scrollIntoView({ block: 'center' });
    });
    await sleep(500);
  } catch {}

  for (const fp of filePaths) {
    let ok = false;
    // Method A: 直接input[type=file] (古いnoteで動いていた方式)
    try {
      const handles = await page.$$(SELECTORS.fileInput);
      for (const h of handles) {
        try {
          await h.setInputFiles(fp);
          await sleep(4500);
          ok = true;
          break;
        } catch (e) {
          lastError = `input err: ${e.message}`;
        }
      }
    } catch (e) {
      lastError = `query err: ${e.message}`;
    }

    // Method B: 「＋」を開く → 「ファイル」menu item → filechooser
    if (!ok) {
      try {
        // Place cursor at end & make a new empty block (the ＋ appears beside it)
        await page.evaluate(() => {
          const pm = document.querySelector('.ProseMirror');
          if (!pm) return;
          pm.focus();
          const last = pm.lastElementChild;
          if (last) {
            const r = document.createRange();
            r.selectNodeContents(last);
            r.collapse(false);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(r);
          }
        });
        await page.keyboard.press('End');
        await page.keyboard.press('Enter');
        await sleep(800);

        // open ＋ menu
        const plusSelectors = [
          '[aria-label="メニューを開く"]',
          '[data-testid="plusMenu"]',
          '[data-testid="block-add-button"]',
          'button[aria-label*="メニュー"]',
          'button[aria-label*="追加"]',
          'button[aria-label*="ブロック"]',
          'button[aria-label*="挿入"]',
        ];
        let plusClicked = false;
        for (const sel of plusSelectors) {
          const b = page.locator(sel).first();
          if (await b.count() && await b.isVisible().catch(() => false)) {
            await b.click({ force: true, timeout: 3000 }).then(() => { plusClicked = true; }).catch(() => {});
            if (plusClicked) break;
          }
        }
        if (!plusClicked) {
          lastError = 'no plus button';
        } else {
          await sleep(700);
          // click "ファイル" inside opened menu
          const fileItem = page.locator(
            '[role="menuitem"]:has-text("ファイル"), li:has-text("ファイル") button, button:has-text("ファイル")'
          ).first();
          if (await fileItem.count()) {
            const [fc] = await Promise.all([
              page.waitForEvent('filechooser', { timeout: 10000 }).catch(e => {
                lastError = `filechooser timeout: ${e.message}`;
                return null;
              }),
              fileItem.click({ force: true, timeout: 5000 }).catch(e => {
                lastError = `file item click: ${e.message}`;
              }),
            ]);
            if (fc) {
              await fc.setFiles(fp);
              await sleep(5000);
              ok = true;
            }
          } else {
            lastError = 'no ファイル menu item';
          }
        }
      } catch (e) {
        lastError = `method B err: ${e.message}`;
      }
    }

    if (ok) attached++;
    else log(`  WARN attach failed: ${fp.split(/[\\/]/).pop()} (${lastError})`);
  }
  return { attached, lastError };
}

async function clickSave(page) {
  // Try common save patterns
  const candidates = [
    'button:has-text("保存")',
    'button[aria-label="保存"]',
    'button:has-text("更新")',
  ];
  for (const sel of candidates) {
    const b = page.locator(sel).first();
    if (await b.count() && await b.isVisible().catch(() => false)) {
      try {
        await b.click({ timeout: 5000 });
        await sleep(2500);
        return true;
      } catch {}
    }
  }
  // Fallback: keyboard shortcut Cmd/Ctrl+S
  try {
    await page.keyboard.press('Control+s');
    await sleep(2500);
    return true;
  } catch {}
  return false;
}

// ───── main ─────
async function main() {
  if (!existsSync(STORAGE_PATH)) {
    fail(`storageState.json not found at ${STORAGE_PATH}. Run capture-session.mjs first.`);
  }
  const queueRaw = await readFile(QUEUE_PATH, 'utf-8');
  if (queueRaw.trim().length < 20) {
    fail(`queue.json appears empty/corrupted (${queueRaw.length} bytes). Restore from git: git checkout HEAD -- note-auto/queue.json`);
  }
  // 安全のためバックアップを作る
  await copyFile(QUEUE_PATH, QUEUE_PATH + '.bak');
  const queue = JSON.parse(queueRaw);
  const items = queue.items || [];

  // Filter targets
  const targets = [];
  for (const it of items) {
    const idNum = parseInt(it.id, 10);
    if (idNum < FROM || idNum > TO) continue;
    if (!it.draftId) continue;
    if (it.attachmentCount && it.attachmentCount >= 3) continue;
    // Need actual docx files
    const dir = join(ATTACHMENTS_DIR, `app${it.id}`);
    if (!existsSync(dir)) continue;
    targets.push(it);
    if (targets.length >= MAX) break;
  }

  log(`target items: ${targets.length}`);
  if (targets.length === 0) {
    log('nothing to do (all items already have attachments or no source files)');
    return;
  }

  if (DRY_RUN) {
    log('=== DRY RUN (no actual upload) ===');
    for (const t of targets) {
      const atts = await resolveAttachments(t.id);
      log(`  #${t.id} draft=${t.draftId} files=${atts.length} title=${(t.title || '').slice(0, 40)}`);
    }
    return;
  }

  const browser = await chromium.launch({ headless: HEADLESS });
  const context = await browser.newContext({ storageState: STORAGE_PATH });
  const page = await context.newPage();

  let success = 0;
  let failed = 0;

  for (let i = 0; i < targets.length; i++) {
    const it = targets[i];
    const editUrl = `https://note.com/notes/${it.draftId}/edit`;
    log(`[${i + 1}/${targets.length}] #${it.id} ${editUrl}`);

    try {
      await page.goto(editUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
      // Wait for editor
      await page.waitForSelector('.ProseMirror', { timeout: 15000 });
      await sleep(2000);

      const atts = await resolveAttachments(it.id);
      if (atts.length === 0) {
        log(`  SKIP no docx files for app${it.id}`);
        continue;
      }

      const { attached } = await attachFilesViaInput(page, atts);
      if (attached === 0) {
        log(`  FAIL attached 0 of ${atts.length}`);
        failed++;
        continue;
      }

      const saved = await clickSave(page);
      log(`  ${saved ? 'SAVED' : 'WARN save button not clicked'} attached=${attached}`);

      // Update queue
      it.attachmentCount = attached;
      it.attached_at = new Date().toISOString();
      success++;

      // Persist periodically (atomic write)
      if ((i + 1) % 5 === 0) {
        const tmp = QUEUE_PATH + '.tmp';
        await writeFile(tmp, JSON.stringify(queue, null, 2), 'utf-8');
        await rename(tmp, QUEUE_PATH);
        log(`  (queue.json checkpointed at ${i + 1})`);
      }

      // gentle delay between items
      await sleep(3000);
    } catch (e) {
      log(`  ERROR ${e.message}`);
      failed++;
    }
  }

  // Final save (atomic) - only if any success
  if (success > 0) {
    const tmp = QUEUE_PATH + '.tmp';
    await writeFile(tmp, JSON.stringify(queue, null, 2), 'utf-8');
    await rename(tmp, QUEUE_PATH);
  }
  log(`\n=== Done: ${success} success / ${failed} failed / ${targets.length} total ===`);

  await browser.close();
}

main().catch(e => fail(e.stack || e.message));
