#!/usr/bin/env node
/**
 * /publish/ ページの DOM dump
 * post.mjs configurePaidAndPublish() の selector 検証用
 */
import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

async function main() {
  let storageState;
  const raw = process.env.NOTE_STORAGE_STATE;
  if (raw) {
    storageState = JSON.parse(raw);
  } else {
    const ssPath = join(__dirname, 'storageState.json');
    if (!existsSync(ssPath)) throw new Error('storageState.json not found');
    storageState = JSON.parse(await readFile(ssPath, 'utf-8'));
  }
  const QUEUE = JSON.parse(await readFile(join(__dirname, 'queue.json'), 'utf-8'));
  const targetId = process.argv[2] || '150';
  const target = QUEUE.items.find(i => i.id === targetId);
  if (!target || !target.draftId) {
    console.error(`#${targetId} draftId not found`);
    process.exit(1);
  }
  const draftId = target.draftId;
  console.log(`[DOM-DUMP-PUBLISH] target draftId: ${draftId}`);

  const browser = await chromium.launch({ headless: true, args: ['--disable-blink-features=AutomationControlled'] });
  const ctx = await browser.newContext({
    storageState,
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    viewport: { width: 1280, height: 800 },
  });
  const page = await ctx.newPage();
  try {
    const url = `https://editor.note.com/notes/${draftId}/publish/`;
    console.log(`[DOM-DUMP-PUBLISH] navigate: ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(8000);

    const finalUrl = page.url();
    const buttons = await page.evaluate(() => {
      return [...document.querySelectorAll('button')].slice(0, 80).map(b => ({
        text: (b.textContent || '').trim().slice(0, 40),
        cls: (b.className || '').slice(0, 60),
        ariaLabel: b.getAttribute('aria-label') || '',
        dataTestid: b.getAttribute('data-testid') || '',
        visible: b.offsetParent !== null,
      })).filter(b => b.text || b.ariaLabel);
    });
    const inputs = await page.evaluate(() => {
      return [...document.querySelectorAll('input, textarea')].map(el => ({
        tag: el.tagName,
        type: el.getAttribute('type') || '',
        name: el.getAttribute('name') || '',
        placeholder: el.getAttribute('placeholder') || '',
        cls: (el.className || '').slice(0, 60),
        visible: el.offsetParent !== null,
      }));
    });
    const radios = await page.evaluate(() => {
      return [...document.querySelectorAll('input[type="radio"]')].map(r => ({
        name: r.getAttribute('name') || '',
        value: r.getAttribute('value') || '',
        checked: r.checked,
        id: r.id,
      }));
    });

    const dump = { meta: { url: finalUrl, originalUrl: url }, buttons, inputs, radios };
    await writeFile(join(__dirname, '_dom_dump_publish.json'), JSON.stringify(dump, null, 2), 'utf-8');
    console.log(`[DOM-DUMP-PUBLISH] dumped`);
    console.log(`  final url: ${finalUrl}`);
    console.log(`  buttons=${buttons.length} inputs=${inputs.length} radios=${radios.length}`);
    console.log('\n  visible buttons:');
    for (const b of buttons.filter(x => x.visible).slice(0, 20)) console.log('   ', JSON.stringify(b));
    console.log('\n  radios:');
    for (const r of radios) console.log('   ', JSON.stringify(r));
  } finally {
    await browser.close();
  }
}

main().catch(e => { console.error('FATAL', e?.message || e); process.exit(1); });
