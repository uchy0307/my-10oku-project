#!/usr/bin/env node
/**
 * editor.note.com の新 DOM を解析して新セレクタを発見するスクリプト
 * post.mjs の壊れた selector を更新するために使用
 */
import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

async function main() {
  // env 優先、なければ storageState.json 直接読み (承認回避)
  let storageState;
  const raw = process.env.NOTE_STORAGE_STATE;
  if (raw) {
    storageState = JSON.parse(raw);
  } else {
    const ssPath = join(__dirname, 'storageState.json');
    if (!existsSync(ssPath)) throw new Error('storageState.json not found');
    storageState = JSON.parse(await readFile(ssPath, 'utf-8'));
  }
  // 対象: 既存 draftId (queue.json の #112)
  const QUEUE = JSON.parse(await readFile(join(__dirname, 'queue.json'), 'utf-8'));
  const target = QUEUE.items.find(i => i.id === '112');
  if (!target || !target.draftId) {
    console.error('#112 draftId not found');
    process.exit(1);
  }
  const draftId = target.draftId;
  console.log(`[DOM-DUMP] target draftId: ${draftId}`);

  const browser = await chromium.launch({ headless: true, args: ['--disable-blink-features=AutomationControlled'] });
  const ctx = await browser.newContext({
    storageState,
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    viewport: { width: 1280, height: 800 },
  });
  const page = await ctx.newPage();
  try {
    const url = `https://editor.note.com/notes/${draftId}/edit/`;
    console.log(`[DOM-DUMP] navigate: ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(8000);  // SPA hydration 待ち

    // 1. 全 <button> の textContent と クラス
    const buttons = await page.evaluate(() => {
      return [...document.querySelectorAll('button')].slice(0, 80).map(b => ({
        text: (b.textContent || '').trim().slice(0, 40),
        cls: (b.className || '').slice(0, 60),
        ariaLabel: b.getAttribute('aria-label') || '',
        dataTestid: b.getAttribute('data-testid') || '',
        visible: b.offsetParent !== null,
      })).filter(b => b.text || b.ariaLabel);
    });

    // 2. 編集領域候補 (ProseMirror / contenteditable / editor)
    const editors = await page.evaluate(() => {
      const cand = [
        ...document.querySelectorAll('[contenteditable="true"]'),
        ...document.querySelectorAll('.ProseMirror'),
        ...document.querySelectorAll('[role="textbox"]'),
        ...document.querySelectorAll('[data-testid*="editor"]'),
      ];
      return cand.slice(0, 10).map(el => ({
        tag: el.tagName,
        cls: (el.className || '').slice(0, 80),
        role: el.getAttribute('role') || '',
        contenteditable: el.getAttribute('contenteditable') || '',
        dataTestid: el.getAttribute('data-testid') || '',
        innerLen: (el.innerText || '').length,
      }));
    });

    // 3. input[type=file] の存在
    const fileInputs = await page.evaluate(() => {
      return [...document.querySelectorAll('input[type="file"]')].map(el => ({
        accept: el.getAttribute('accept') || '',
        cls: (el.className || '').slice(0, 60),
        name: el.getAttribute('name') || '',
        visible: el.offsetParent !== null,
      }));
    });

    // 4. URL とタイトル
    const meta = await page.evaluate(() => ({
      url: location.href,
      title: document.title,
      h1: document.querySelector('h1')?.textContent?.trim() || '',
    }));

    const dump = { meta, buttons, editors, fileInputs };
    await writeFile(join(__dirname, '_dom_dump.json'), JSON.stringify(dump, null, 2), 'utf-8');
    console.log(`[DOM-DUMP] dumped to _dom_dump.json`);
    console.log(`  buttons=${buttons.length} editors=${editors.length} fileInputs=${fileInputs.length}`);
    console.log(`  url=${meta.url}`);
    console.log(`  editors first 3:`);
    for (const e of editors.slice(0, 3)) console.log('   ', JSON.stringify(e));
    console.log(`  buttons (visible only, first 15):`);
    for (const b of buttons.filter(x => x.visible).slice(0, 15)) console.log('   ', JSON.stringify(b));
  } finally {
    await browser.close();
  }
}

main().catch(e => { console.error('FATAL', e?.message || e); process.exit(1); });
