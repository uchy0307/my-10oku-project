// note-auto/capture-session.mjs
// ローカル実行用ヘルパー: 手動ログインしたブラウザの storageState を JSON に保存する。
// 取得した JSON の中身を GitHub Secret `NOTE_STORAGE_STATE` にそのまま貼り付ける。
//
// 使い方:
//   node note-auto/capture-session.mjs
//   1) Chromium が起動する
//   2) note.com にログイン（CAPTCHA や2要素も画面操作でOK）
//   3) ログイン後、ターミナルで Enter キーを押す
//   4) note-auto/storageState.json が生成される
//   5) ファイル内容を GitHub Secret NOTE_STORAGE_STATE に登録
//
// 注意:
//  - storageState.json は .gitignore に追加すること（cookie漏洩防止）
//  - cookie は有効期限切れで失効する。失効したら再取得が必要。

import { chromium } from 'playwright';
import { writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import readline from 'node:readline/promises';
import { stdin as input, stdout as output } from 'node:process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_PATH = join(__dirname, 'storageState.json');

async function main() {
  console.log('[capture] Chromium を起動します（手動ログイン用）。');
  const browser = await chromium.launch({
    headless: false,
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
  await page.goto('https://note.com/login', { waitUntil: 'domcontentloaded' });
  console.log('[capture] ブラウザで note.com にログインしてください。');
  console.log('[capture] ログイン完了後、このターミナルで Enter を押すと state を保存します。');

  const rl = readline.createInterface({ input, output });
  await rl.question('ログイン完了したら Enter > ');
  rl.close();

  const state = await context.storageState();
  await writeFile(OUT_PATH, JSON.stringify(state, null, 2), 'utf-8');
  console.log(`[capture] 保存しました: ${OUT_PATH}`);
  console.log('[capture] このファイルの内容を GitHub Secret NOTE_STORAGE_STATE に貼り付けてください。');
  console.log('[capture] 注意: storageState.json は絶対に公開リポジトリに commit しないこと。');

  await context.close();
  await browser.close();
}

main().catch((err) => {
  console.error('[capture] FAILED:', err);
  process.exit(1);
});
