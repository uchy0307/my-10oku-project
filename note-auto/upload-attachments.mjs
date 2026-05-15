// note-auto/upload-attachments.mjs
// ───────────────────────────────────────────────────────────────
// 目的:
//   1. ローカル `C:\Users\user\Documents\Claude\Projects\note 200本\app{015〜200}\*.docx`
//      (合計558本) を GitHub Git Data API 経由で 1コミットに集約して
//      `note-auto/attachments/app{NNN}/{filename}.docx` にpushする。
//   2. 同じコミットに以下のローカルファイルも含める:
//      - note-auto/post.mjs (改修版)
//      - note-auto/upload-attachments.mjs (本script)
//      - _upload_attachments.bat
//   3. push後 `note_auto_post.yml` workflow を dispatch (max=1)
//
// 認証: 環境変数 GITHUB_TOKEN を最優先。未設定なら repo の .git/config から
//       https://uchy0307:TOKEN@github.com/... のTOKEN部分を抽出。
//
// 使い方:
//   node note-auto/upload-attachments.mjs
//   node note-auto/upload-attachments.mjs --dry-run        // API実行せず計画のみ表示
//   node note-auto/upload-attachments.mjs --no-dispatch    // workflow起動しない
//   node note-auto/upload-attachments.mjs --from=015 --to=200
//
// 設計:
//   1. blobs (558+3本) を並列8でPOST → sha取得
//   2. base_tree=現tree、新tree作成
//   3. commit 作成、refs/heads/main を更新
//   4. workflow_dispatch POST
// ───────────────────────────────────────────────────────────────

import { readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { existsSync, readFileSync } from 'node:fs';
import { join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, '..');
const CHECKPOINT_PATH = join(__dirname, '.upload-checkpoint.json');

// -------- args ----------
const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const m = a.match(/^--([^=]+)(?:=(.*))?$/);
    return m ? [m[1], m[2] ?? true] : [a, true];
  }),
);
const DRY_RUN = !!args['dry-run'];
const NO_DISPATCH = !!args['no-dispatch'];
const FROM = parseInt(args.from ?? '15', 10);
const TO = parseInt(args.to ?? '200', 10);
const SRC =
  args.src || 'C:\\Users\\user\\Documents\\Claude\\Projects\\note 200本';
const OWNER = args.owner || 'uchy0307';
const REPO = args.repo || 'my-10oku-project';
const BRANCH = args.branch || 'main';
const PARALLEL = parseInt(args.parallel ?? '3', 10);
const BLOB_DELAY_MS = parseInt(args['blob-delay'] ?? '120', 10);
const COMMIT_MSG =
  args.message ||
  `docx attachments: bulk upload app${String(FROM).padStart(3, '0')}-app${String(TO).padStart(3, '0')}`;

// -------- token ----------
function getToken() {
  if (process.env.GITHUB_TOKEN) return process.env.GITHUB_TOKEN;
  const cfgPath = join(REPO_ROOT, '.git', 'config');
  if (existsSync(cfgPath)) {
    const cfg = readFileSync(cfgPath, 'utf-8');
    const m = cfg.match(/https:\/\/[^:]+:([^@]+)@github\.com/);
    if (m) return m[1];
  }
  throw new Error('GITHUB_TOKEN env not set and no token in .git/config');
}
const TOKEN = getToken();

// -------- HTTP helper ----------
async function ghFetch(method, path, body) {
  const url = path.startsWith('http')
    ? path
    : `https://api.github.com${path}`;
  const opts = {
    method,
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'note-auto-upload-attachments',
    },
  };
  if (body !== undefined) {
    opts.body = JSON.stringify(body);
    opts.headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(url, opts);
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`GH ${method} ${path} -> ${res.status}: ${text.slice(0, 400)}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function ghFetchWithRetry(method, path, body, retries = 6) {
  for (let i = 0; i < retries; i++) {
    try {
      return await ghFetch(method, path, body);
    } catch (err) {
      const msg = String(err.message || err);
      const isRateLimit = /(-> 403.*rate limit|secondary rate)/i.test(msg);
      const isTransient = /(-> 5\d\d|ECONNRESET|ETIMEDOUT|fetch failed)/.test(msg);
      if (i < retries - 1 && (isRateLimit || isTransient)) {
        // 二次レートリミット時は長めに待つ（60s, 90s, 120s...）
        const wait = isRateLimit ? 60000 + i * 30000 : 800 * Math.pow(2, i);
        console.warn(`[WARN] retry ${i + 1}/${retries} after ${(wait / 1000).toFixed(0)}s: ${msg.slice(0, 120)}`);
        await new Promise((r) => setTimeout(r, wait));
        continue;
      }
      throw err;
    }
  }
}

// -------- discover files ----------
async function discoverFiles() {
  const files = []; // { localPath, repoPath, app, name, size }
  for (let n = FROM; n <= TO; n++) {
    const id = String(n).padStart(3, '0');
    const appDir = join(SRC, `app${id}`);
    if (!existsSync(appDir)) {
      console.warn(`[WARN] skip missing dir: app${id}`);
      continue;
    }
    let entries;
    try {
      entries = await readdir(appDir);
    } catch (err) {
      console.warn(`[WARN] cannot read app${id}: ${err.message}`);
      continue;
    }
    const docxs = entries.filter((f) => f.toLowerCase().endsWith('.docx'));
    if (docxs.length === 0) {
      console.warn(`[WARN] no docx in app${id}`);
      continue;
    }
    for (const f of docxs) {
      const localPath = join(appDir, f);
      const st = await stat(localPath);
      files.push({
        localPath,
        repoPath: `note-auto/attachments/app${id}/${f}`,
        app: id,
        name: f,
        size: st.size,
      });
    }
  }
  // 追加ファイル: post.mjs, upload-attachments.mjs, _upload_attachments.bat
  const extras = [
    { localPath: join(REPO_ROOT, 'note-auto', 'post.mjs'), repoPath: 'note-auto/post.mjs' },
    { localPath: join(REPO_ROOT, 'note-auto', 'upload-attachments.mjs'), repoPath: 'note-auto/upload-attachments.mjs' },
    { localPath: join(REPO_ROOT, '_upload_attachments.bat'), repoPath: '_upload_attachments.bat' },
  ];
  for (const e of extras) {
    if (existsSync(e.localPath)) {
      const st = await stat(e.localPath);
      files.push({ ...e, app: '_extra', name: basename(e.localPath), size: st.size });
    } else {
      console.warn(`[WARN] extra file missing: ${e.localPath}`);
    }
  }
  return files;
}

// -------- concurrent map with limit ----------
async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let idx = 0;
  let done = 0;
  const total = items.length;
  async function worker() {
    while (true) {
      const i = idx++;
      if (i >= total) return;
      results[i] = await fn(items[i], i);
      done++;
      if (done % 20 === 0 || done === total) {
        process.stdout.write(`  progress: ${done}/${total}\r`);
      }
    }
  }
  const workers = Array.from({ length: Math.min(limit, total) }, worker);
  await Promise.all(workers);
  process.stdout.write('\n');
  return results;
}

// -------- main ----------
async function main() {
  console.log('=== upload-attachments.mjs ===');
  console.log(`owner/repo: ${OWNER}/${REPO}@${BRANCH}`);
  console.log(`src: ${SRC}`);
  console.log(`range: app${String(FROM).padStart(3, '0')} - app${String(TO).padStart(3, '0')}`);
  console.log(`parallel: ${PARALLEL}, dry-run: ${DRY_RUN}`);

  // 1. discover files
  console.log('\n[1] discover local docx files...');
  const files = await discoverFiles();
  const totalSize = files.reduce((s, f) => s + f.size, 0);
  console.log(`  -> ${files.length} files, total ${(totalSize / 1024 / 1024).toFixed(2)} MB`);
  if (files.length === 0) {
    throw new Error('no files to upload');
  }

  if (DRY_RUN) {
    console.log('\n[DRY-RUN] sample mapping:');
    for (const f of files.slice(0, 6)) {
      console.log(`  ${f.localPath}\n    -> ${f.repoPath} (${f.size} bytes)`);
    }
    console.log(`  ... and ${files.length - 6} more`);
    return;
  }

  // 2. get current ref + commit + tree
  console.log('\n[2] fetch current main ref...');
  const ref = await ghFetchWithRetry('GET', `/repos/${OWNER}/${REPO}/git/refs/heads/${BRANCH}`);
  const parentCommitSha = ref.object.sha;
  console.log(`  parent commit: ${parentCommitSha}`);
  const parentCommit = await ghFetchWithRetry('GET', `/repos/${OWNER}/${REPO}/git/commits/${parentCommitSha}`);
  const baseTreeSha = parentCommit.tree.sha;
  console.log(`  base tree: ${baseTreeSha}`);

  // 3. create blobs (with checkpoint for resume)
  let checkpoint = {};
  if (existsSync(CHECKPOINT_PATH)) {
    try {
      checkpoint = JSON.parse(await readFile(CHECKPOINT_PATH, 'utf-8'));
      console.log(`\n[3] resume from checkpoint: ${Object.keys(checkpoint).length} blobs already uploaded`);
    } catch {
      checkpoint = {};
    }
  }
  console.log(`\n[3] create ${files.length} blobs (parallel=${PARALLEL}, delay=${BLOB_DELAY_MS}ms)...`);
  let cached = 0;
  const blobs = await mapLimit(files, PARALLEL, async (f, idx) => {
    // ローカルパスをキーにキャッシュ
    const key = f.repoPath;
    if (checkpoint[key]) {
      cached++;
      return { ...f, sha: checkpoint[key] };
    }
    const content = await readFile(f.localPath);
    const b64 = content.toString('base64');
    const res = await ghFetchWithRetry('POST', `/repos/${OWNER}/${REPO}/git/blobs`, {
      content: b64,
      encoding: 'base64',
    });
    checkpoint[key] = res.sha;
    // checkpoint を逐次保存 (10件ごと)
    if (Object.keys(checkpoint).length % 10 === 0) {
      try {
        await writeFile(CHECKPOINT_PATH, JSON.stringify(checkpoint), 'utf-8');
      } catch {}
    }
    // jitter delay
    if (BLOB_DELAY_MS > 0) {
      await new Promise((r) => setTimeout(r, BLOB_DELAY_MS + Math.floor(Math.random() * 50)));
    }
    return { ...f, sha: res.sha };
  });
  // 最終 checkpoint 保存
  try {
    await writeFile(CHECKPOINT_PATH, JSON.stringify(checkpoint), 'utf-8');
  } catch {}
  console.log(`  -> ${blobs.length} blobs ready (${cached} from checkpoint)`);

  // 4. create tree incrementally (batches of 100 to avoid 422 timeout)
  const BATCH_SIZE = parseInt(args['tree-batch'] ?? '80', 10);
  console.log(`\n[4] create tree incrementally (batch=${BATCH_SIZE})...`);
  const treeEntries = blobs.map((b) => ({
    path: b.repoPath,
    mode: '100644',
    type: 'blob',
    sha: b.sha,
  }));
  let currentTreeSha = baseTreeSha;
  const totalBatches = Math.ceil(treeEntries.length / BATCH_SIZE);
  for (let i = 0; i < treeEntries.length; i += BATCH_SIZE) {
    const batch = treeEntries.slice(i, i + BATCH_SIZE);
    const res = await ghFetchWithRetry('POST', `/repos/${OWNER}/${REPO}/git/trees`, {
      base_tree: currentTreeSha,
      tree: batch,
    });
    currentTreeSha = res.sha;
    const idx = Math.floor(i / BATCH_SIZE) + 1;
    console.log(`  batch ${idx}/${totalBatches} (${batch.length} entries): tree=${currentTreeSha.slice(0, 8)}`);
  }
  const newTree = { sha: currentTreeSha };
  console.log(`  -> final tree ${newTree.sha}`);

  // 5. create commit
  console.log('\n[5] create commit...');
  const newCommit = await ghFetchWithRetry('POST', `/repos/${OWNER}/${REPO}/git/commits`, {
    message: COMMIT_MSG,
    tree: newTree.sha,
    parents: [parentCommitSha],
  });
  console.log(`  -> commit ${newCommit.sha}`);

  // 6. update ref (no force)
  console.log('\n[6] update ref...');
  const updated = await ghFetchWithRetry('PATCH', `/repos/${OWNER}/${REPO}/git/refs/heads/${BRANCH}`, {
    sha: newCommit.sha,
    force: false,
  });
  console.log(`  -> refs/heads/${BRANCH} now at ${updated.object.sha}`);

  console.log('\n=== UPLOAD DONE ===');
  console.log(`commit: https://github.com/${OWNER}/${REPO}/commit/${newCommit.sha}`);

  // 7. workflow_dispatch
  if (NO_DISPATCH) {
    console.log('\n[7] skip workflow_dispatch (--no-dispatch)');
    return;
  }
  console.log('\n[7] dispatch note_auto_post.yml workflow (max=1)...');
  try {
    await ghFetchWithRetry('POST', `/repos/${OWNER}/${REPO}/actions/workflows/note_auto_post.yml/dispatches`, {
      ref: BRANCH,
      inputs: { max: '1' },
    });
    console.log(`  -> dispatched. Watch: https://github.com/${OWNER}/${REPO}/actions/workflows/note_auto_post.yml`);
    // 直近runを取得して run number を表示
    await new Promise((r) => setTimeout(r, 3000));
    const runs = await ghFetchWithRetry(
      'GET',
      `/repos/${OWNER}/${REPO}/actions/workflows/note_auto_post.yml/runs?per_page=3&branch=${BRANCH}`,
    );
    if (runs.workflow_runs && runs.workflow_runs.length > 0) {
      const top = runs.workflow_runs[0];
      console.log(`  -> Run #${top.run_number} (id=${top.id}) status=${top.status}`);
      console.log(`     ${top.html_url}`);
    }
  } catch (err) {
    console.warn('[WARN] dispatch 失敗:', err.message);
  }
}

main().catch((err) => {
  console.error('\n[FATAL]', err.message || err);
  if (err.stack) console.error(err.stack.split('\n').slice(1, 4).join('\n'));
  process.exit(1);
});
