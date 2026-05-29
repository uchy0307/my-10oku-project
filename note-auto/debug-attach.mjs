// note-auto/debug-attach.mjs
// note.com の編集ページ DOM を診断して、添付ロジック失敗原因を特定。
//
// 使い方:
//   node note-auto/debug-attach.mjs --draftId=n848deaa6139d
//   （ヘッドありで起動するので実画面が見える）

import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __dirname = dirname(fileURLToPath(import.meta.url));
const STORAGE_PATH = join(__dirname, 'storageState.json');

const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const m = a.match(/^--([^=]+)(?:=(.*))?$/);
    return m ? [m[1], m[2] ?? true] : [a, true];
  })
);
const draftId = args.draftId || 'n848deaa6139d';

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ headless: false });
  const ctx = await browser.newContext({ storageState: STORAGE_PATH });
  const page = await ctx.newPage();

  const url = `https://note.com/notes/${draftId}/edit`;
  console.log('[debug] navigating to', url);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(3000);

  // Final URL after redirects
  console.log('[debug] final URL:', page.url());

  // Page title
  const title = await page.title();
  console.log('[debug] page title:', title);

  // Look for editor
  const hasProseMirror = (await page.$$('.ProseMirror')).length;
  console.log('[debug] ProseMirror count:', hasProseMirror);

  // List all input[type=file]
  const fileInputs = await page.$$eval(
    'input[type="file"]',
    nodes => nodes.map(n => ({
      name: n.name,
      accept: n.accept,
      multiple: n.multiple,
      visible: n.offsetParent !== null,
      parent: n.parentElement?.tagName,
    }))
  );
  console.log('[debug] input[type=file] count:', fileInputs.length);
  console.log('[debug] details:', JSON.stringify(fileInputs, null, 2));

  // Look for various add-button patterns
  const possibleBtns = await page.$$eval(
    'button',
    nodes => nodes
      .filter(n => /添付|ファイル|アップロード|挿入|追加|画像|attach|upload/.test(n.textContent || n.ariaLabel || ''))
      .map(n => ({
        text: (n.textContent || '').trim().slice(0, 30),
        aria: n.ariaLabel,
        cls: n.className?.slice(0, 60),
      }))
  );
  console.log('[debug] candidate add-buttons:', JSON.stringify(possibleBtns.slice(0, 10), null, 2));

  // Take screenshot
  await page.screenshot({ path: join(__dirname, '_debug_screen.png'), fullPage: false });
  console.log('[debug] screenshot saved: note-auto/_debug_screen.png');

  console.log('\n[debug] Browser stays open 30sec for manual inspection...');
  await sleep(30000);

  await browser.close();
})();
