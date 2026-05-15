// note-auto/post.mjs
// ───────────────────────────────────────────────────────────────
// note.com 下書き編集型自動投稿（B案・新方針）
//
// 完全自動ログインは bot 検知で失敗しやすいため、Playwright の storageState
// に保存された認証済みセッションを再利用する。queue.json で指定された
// `draftId` の下書きを開いて、本文を流し込み、下書き保存 or 公開する。
//
// 2026-05-16 改修:
//   - articles/note_${id}.md の本文から "47歳" 文言を除去
//   - 末尾にアプリリンク + アクセスコード (access_codes.json) を挿入
//   - note-auto/attachments/app${id}/ 内 docx 3本を input[type=file] で添付
//   - 公開時のみ価格 100円 設定（有料エリア） ※ publish:false の下書きでは未実行
//
// env:
//   NOTE_STORAGE_STATE   storageState JSON 文字列（GitHub Secrets で管理）
//   NOTE_HEADLESS        "false" 指定で headed 実行（デフォルト true）
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
const URL_PATTERN = 'https://toi-suite.vercel.app/page/'; // + id

let ACCESS_CODES = {};
try {
  if (existsSync(ACCESS_CODES_PATH)) {
    ACCESS_CODES = JSON.parse(await readFile(ACCESS_CODES_PATH, 'utf-8'));
  }
} catch (err) {
  console.warn('[WARN] access_codes.json 読み込み失敗:', err.message);
}

// ---------- body preprocessing ----------

/**
 * 47歳除去 + アプリリンク挿入。
 *   - "47歳の私" → "私"
 *   - "47歳が"   → "私が"
 *   - 文中の "47歳" / "#47歳" を削除
 *   - 末尾に「アプリにアクセス」セクションを追加
 */
function preprocessBody(body, articleId) {
  let out = body;
  // 47歳 除去（破壊的に置換しすぎないよう順序重視）
  out = out.replace(/47歳の/g, '');
  out = out.replace(/47歳が/g, '私が');
  out = out.replace(/47歳に/g, '');
  out = out.replace(/47歳/g, '');
  out = out.replace(/[#＃]\s?47歳\s*/g, '');
  // 連続空白の整理（行内のみ。改行は維持）
  out = out
    .split('\n')
    .map((line) => line.replace(/[ \t]{2,}/g, ' ').replace(/^ +| +$/g, ''))
    .join('\n');
  // 連続空行は2行までに抑える
  out = out.replace(/\n{3,}/g, '\n\n');

  // 末尾のアプリリンクセクション
  const code = ACCESS_CODES[articleId];
  if (code) {
    const link = `${URL_PATTERN}${articleId}`;
    const block =
      `\n\n---\n\n## 📱 アプリにアクセス\n\n` +
      `下記URLからWebアプリを利用できます。\n\n` +
      `${link}\n\n` +
      `アクセスコード: \`${code}\`\n`;
    // 既に同じ block がある場合は追加しない（idempotency）
    if (!out.includes(link)) {
      out += block;
    }
  }
  return out;
}

/**
 * queue.json item から body を解決する。
 *   1. item.body があればそれを使う (旧互換)
 *   2. articles/note_${item.id}.md を読み込む (新方式)
 * その後、preprocessBody() を適用する。
 */
async function resolveBody(item) {
  let raw;
  if (item.body && typeof item.body === 'string' && item.body.trim().length > 0) {
    raw = item.body;
  } else {
    const fp = join(ARTICLES_DIR, `note_${item.id}.md`);
    if (!existsSync(fp)) {
      throw new Error(
        `本文が見つかりません: item.body も articles/note_${item.id}.md も存在しません。`,
      );
    }
    raw = await readFile(fp, 'utf-8');
  }
  return preprocessBody(raw, item.id);
}

/** 添付対象 docx 3本のローカルパスを返す */
async function resolveAttachments(id) {
  const dir = join(ATTACHMENTS_DIR, `app${id}`);
  if (!existsSync(dir)) {
    console.warn(`[WARN] attachments dir 不在: ${dir}`);
    return [];
  }
  const entries = await readdir(dir);
  return entries.filter((f) => f.toLowerCase().endsWith('.docx')).map((f) => join(dir, f));
}

// note.com DOMセレクタ（変更時はここを更新）
const SELECTORS = {
  bodyEditor: '.ProseMirror',
  titleInput: 'textarea[placeholder*="タイトル"]',
  saveDraftButton: 'button:has-text("下書き保存")',
  publishSettingsButton: 'button:has-text("公開設定")',
  publishButton: 'button:has-text("公開")',
  publishConfirmButton: 'button:has-text("公開する")',
  // 添付・有料関連 (推定セレクタ、note.com UI変更時は要見直し)
  fileInput: 'input[type="file"]',
  attachMenuOpen: 'button[aria-label*="ファイル"], button:has-text("ファイル")',
  paidBoundaryButton: 'button:has-text("ここから先は有料エリア"), button:has-text("有料エリア"), button[aria-label*="有料"]',
  priceInput: 'input[type="number"][name*="price"], input[placeholder*="価格"], input[aria-label*="価格"]',
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

/** ファイル添付。input[type=file] に直接 setInputFiles でアップロード */
async function attachFiles(page, filePaths) {
  if (filePaths.length === 0) return 0;
  // hidden な input[type=file] でも setInputFiles は動く
  const inputs = await page.locator(SELECTORS.fileInput).all();
  if (inputs.length === 0) {
    console.warn('[WARN] input[type=file] が見つかりません。添付スキップ。');
    return 0;
  }
  // 通常 multiple 属性付きの input が1つあるはず。最初の input に全部送る。
  try {
    await inputs[0].setInputFiles(filePaths);
    await randDelay(3000, 6000); // アップロード完了待ち
    console.log(`[INFO] 添付完了: ${filePaths.length} files`);
    return filePaths.length;
  } catch (err) {
    console.warn('[WARN] setInputFiles 失敗:', err.message);
    return 0;
  }
}

/** 価格 100円 設定。publish=true 時のみ呼ぶ。 */
async function setPrice(page, yen) {
  try {
    // 公開設定パネルを開く
    const pubSettings = page.locator(SELECTORS.publishSettingsButton).first();
    if (await pubSettings.count()) {
      await pubSettings.click();
      await randDelay(1500, 3000);
    }
    // 有料エリア境界線の設定（任意・複数候補トライ）
    const paidBtn = page.locator(SELECTORS.paidBoundaryButton).first();
    if (await paidBtn.count()) {
      await paidBtn.click();
      await randDelay(1000, 2500);
    }
    const priceField = page.locator(SELECTORS.priceInput).first();
    if (await priceField.count()) {
      await priceField.click();
      await page.keyboard.press('Control+A');
      await page.keyboard.press('Delete');
      await priceField.type(String(yen), { delay: 60 });
      await randDelay(800, 1500);
      console.log(`[INFO] 価格 ${yen}円 設定`);
      return true;
    } else {
      console.warn('[WARN] 価格入力欄が見つかりません。価格設定スキップ。');
      return false;
    }
  } catch (err) {
    console.warn('[WARN] setPrice エラー:', err.message);
    return false;
  }
}

// ---------- core ----------

/** 下書きページに遷移して本文を置換し、保存 or 公開する */
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

  // 本文置換: .ProseMirror をクリック→全選択→削除→流し込み
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

  // ファイル添付 (docx 3本)
  let attachedCount = 0;
  if (attachPaths.length > 0) {
    attachedCount = await attachFiles(page, attachPaths);
  }

  // 価格設定 (publish=true 時のみ実行。下書き保存時はスキップ)
  let priceSet = false;
  if (item.publish) {
    priceSet = await setPrice(page, PRICE_YEN);
  }

  // 保存 or 公開
  if (item.publish) {
    // 既に setPrice で公開設定パネルを開いているはず
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
    return { result: 'published', attached: attachedCount, priceSet };
  } else {
    await page.locator(SELECTORS.saveDraftButton).first().click();
    await randDelay(3000, 5000);
    return { result: 'draft_saved', attached: attachedCount, priceSet };
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
        const ret = await editDraft(page, item);
        item.status = ret.result; // 'draft_saved' or 'published'
        item.posted_at = new Date().toISOString();
        item.error = null;
        item.attached = ret.attached;
        item.priceSet = ret.priceSet;
        console.log(`[OK] ${ret.result}: id=${item.id} attached=${ret.attached} priceSet=${ret.priceSet}`);
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
