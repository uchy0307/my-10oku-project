// scripts/stock_image_picker.mjs
// ----------------------------------------------------------------------------
// 動画 pipeline (psych_v2 / history_v2 / shorts_v2) から呼ぶ
// 「ストックフォルダから N 枚ランダム抽出」ヘルパー。
//
// 使い方:
//   import { pickStockImages } from "../../scripts/stock_image_picker.mjs";
//   const images = await pickStockImages({
//     count: 10,
//     prefer: "scenery",      // "scenery" | "history" | "any"
//     destDir: "out/.../images",  // 抽出先ディレクトリ。コピー or symlink される
//   });
//   // images = [{ src: "...wiki/...jpg", dest: "out/.../images/01.jpg" }, ...]
//
// 各 pipeline.mjs の修正例 (差分のみ):
//
//   // import を追加
//   + import { pickStockImages } from "../../scripts/stock_image_picker.mjs";
//
//   // Gemini 画像生成のフォールバック箇所、または明示的に stock を使う処理で:
//   + try {
//   +   const picked = await pickStockImages({ count: 10, prefer: "scenery", destDir: imgOutDir });
//   +   if (picked.length >= 10) {
//   +     console.log(`[stock] using ${picked.length} wiki stock images`);
//   +     return picked.map(p => p.dest);
//   +   }
//   + } catch (e) {
//   +   console.warn("[stock] picker failed:", e.message);
//   + }
//
// 注意: シンボリックリンクは Windows 権限上失敗しやすいのでデフォルトはコピー。
// ----------------------------------------------------------------------------

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// scripts/stock_image_picker.mjs から見て 10oku-project ルート
const PROJECT_ROOT = path.resolve(__dirname, "..");
const STOCK_DIR = path.join(PROJECT_ROOT, "youtube", "stock_images", "wiki");

const SCENERY_PREFIXES = [
  "wiki_cafe_", "wiki_library_", "wiki_tokyo_", "wiki_kyoto_",
  "wiki_autumn_", "wiki_sunset_", "wiki_station_", "wiki_rainy_",
  "wiki_stars_", "wiki_balcony_", "wiki_bedroom_", "wiki_temple_",
  "wiki_park_", "wiki_buffer_",
];
const HISTORY_PREFIXES = ["wiki_hist_"];

const IMG_EXT = new Set([".jpg", ".jpeg", ".png", ".webp"]);

function classify(name) {
  if (HISTORY_PREFIXES.some(p => name.startsWith(p))) return "history";
  if (SCENERY_PREFIXES.some(p => name.startsWith(p))) return "scenery";
  return "other";
}

async function listStock() {
  let entries;
  try {
    entries = await fs.readdir(STOCK_DIR);
  } catch (e) {
    if (e.code === "ENOENT") return [];
    throw e;
  }
  const out = [];
  for (const name of entries) {
    const ext = path.extname(name).toLowerCase();
    if (!IMG_EXT.has(ext)) continue;
    if (!name.startsWith("wiki_")) continue;
    out.push({ name, kind: classify(name), full: path.join(STOCK_DIR, name) });
  }
  return out;
}

function pickRandom(arr, n) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a.slice(0, n);
}

/**
 * @param {object} opts
 * @param {number} [opts.count=10]
 * @param {"scenery"|"history"|"any"} [opts.prefer="any"]
 * @param {string} [opts.destDir]   コピー先 (省略時はコピーせず src のみ返す)
 * @param {boolean} [opts.copy=true]  false なら destDir に書かず src のみ
 * @param {(name:string)=>boolean} [opts.filter]  追加フィルタ
 * @returns {Promise<{ src:string, dest:string|null, kind:string }[]>}
 */
export async function pickStockImages(opts = {}) {
  const {
    count = 10,
    prefer = "any",
    destDir = null,
    copy = true,
    filter = null,
  } = opts;

  const stock = await listStock();
  if (stock.length === 0) {
    throw new Error(`stock dir empty: ${STOCK_DIR}. Run scripts/wiki_image_refill.py --initial`);
  }

  let pool = stock;
  if (prefer === "scenery") {
    const filt = stock.filter(s => s.kind === "scenery");
    if (filt.length >= count) pool = filt;
  } else if (prefer === "history") {
    const filt = stock.filter(s => s.kind === "history");
    if (filt.length >= count) pool = filt;
  }
  if (filter) pool = pool.filter(s => filter(s.name));

  if (pool.length < count) {
    console.warn(`[stock-picker] requested ${count}, available ${pool.length}; using all`);
  }
  const picked = pickRandom(pool, Math.min(count, pool.length));

  if (!destDir || !copy) {
    return picked.map(p => ({ src: p.full, dest: null, kind: p.kind }));
  }

  await fs.mkdir(destDir, { recursive: true });
  const results = [];
  for (let i = 0; i < picked.length; i++) {
    const p = picked[i];
    const num = String(i + 1).padStart(2, "0");
    const ext = path.extname(p.name).toLowerCase() || ".jpg";
    const destName = `${num}_${path.basename(p.name, path.extname(p.name)).slice(0, 60)}${ext}`;
    const dest = path.join(destDir, destName);
    try {
      await fs.copyFile(p.full, dest);
    } catch (e) {
      console.warn("[stock-picker] copy failed:", p.full, e.message);
      continue;
    }
    results.push({ src: p.full, dest, kind: p.kind });
  }
  return results;
}

/**
 * 簡易 CLI: `node scripts/stock_image_picker.mjs --count 10 --dest out/foo`
 */
if (import.meta.url === `file://${process.argv[1]}` || import.meta.url === pathToFileUrlSafe(process.argv[1])) {
  const argv = parseArgs(process.argv.slice(2));
  const out = await pickStockImages({
    count: argv.count ? Number(argv.count) : 10,
    prefer: argv.prefer || "any",
    destDir: argv.dest || null,
  });
  console.log(JSON.stringify(out, null, 2));
}

function pathToFileUrlSafe(p) {
  try { return new URL(`file://${p.replace(/\\/g, "/")}`).href; } catch { return ""; }
}

function parseArgs(arr) {
  const o = {};
  for (let i = 0; i < arr.length; i++) {
    const a = arr[i];
    if (a.startsWith("--")) {
      const k = a.slice(2);
      const v = (i + 1 < arr.length && !arr[i + 1].startsWith("--")) ? arr[++i] : true;
      o[k] = v;
    }
  }
  return o;
}
