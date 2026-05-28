#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wiki_image_refill.py
====================
Wikimedia Commons から CC ライセンスの画像を自動ダウンロードして
`youtube/stock_images/wiki/` にストックし続けるスクリプト。

使い方:
    # 初回大量取得 (1000枚目標)
    python wiki_image_refill.py --initial

    # 自動補充 (1日1回想定: ストック < 500 なら 500枚追加)
    python wiki_image_refill.py

    # 任意の枚数を強制ダウンロード
    python wiki_image_refill.py --target 200

依存:
    requests   (pip install requests)
標準ライブラリのみで動かしたい場合は urllib にフォールバックします。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ---- 設定 ----------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent  # 10oku-project/
STOCK_DIR = ROOT / "youtube" / "stock_images" / "wiki"
LOG_FILE = ROOT / "scripts" / "wiki_refill.log"
HASH_INDEX = STOCK_DIR / ".hash_index.json"

REFILL_THRESHOLD = 500     # この枚数を下回ったら補充
REFILL_AMOUNT = 500        # 補充時に追加する目標枚数
INITIAL_TARGET = 1000      # --initial 指定時の目標
PER_KEYWORD_LIMIT = 40     # 1キーワードあたりの最大取得枚数
THUMB_WIDTH = 1280         # サムネイル幅 (Commons の thumburl 用)
MAX_CONCURRENT = 6         # 並列ダウンロード数
TIMEOUT = 30               # HTTP タイムアウト秒
USER_AGENT = (
    "10oku-stock-image-refill/1.0 "
    "(YouTube stock image builder; contact: uchiyamatakayuki0307@gmail.com)"
)
API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"

# ---- キーワード辞書 -----------------------------------------------------
# 各カテゴリは「prefix → list[search_query]」の構造。
# prefix は保存ファイル名のキー (wiki_<prefix>_001_*.jpg)
KEYWORDS = {
    # 風景系 ------------------------------------------------------------
    "cafe": [
        "cafe interior", "coffee shop interior", "vintage cafe", "japanese cafe interior",
        "european cafe interior", "cafe table window", "cafe morning light",
    ],
    "library": [
        "library reading room", "old library interior", "university library",
        "japanese library", "public library hall", "library bookshelf",
    ],
    "tokyo": [
        "tokyo street night", "shinjuku night", "shibuya crossing", "tokyo neon",
        "tokyo skyline night", "tokyo alley night",
    ],
    "kyoto": [
        "kyoto street", "kyoto gion", "kyoto temple", "kyoto bamboo grove",
        "kyoto autumn", "kyoto traditional house",
    ],
    "autumn": [
        "autumn park japan", "autumn leaves japan", "momiji koyo", "autumn forest",
        "autumn road", "autumn mountain japan",
    ],
    "sunset": [
        "sunset hill landscape", "sunset sea", "sunset mountain", "sunset city skyline",
        "sunset rural japan", "golden hour landscape",
    ],
    "station": [
        "train station platform", "japan train station", "shinkansen platform",
        "tokyo station", "subway platform japan", "rural train station japan",
    ],
    "rainy": [
        "rainy street city", "rain tokyo", "rainy umbrella", "wet asphalt night",
        "rainy day japan", "rain window",
    ],
    "stars": [
        "starry night sky", "milky way japan", "night sky stars", "star trail landscape",
        "stargazing mountain",
    ],
    "balcony": [
        "morning balcony plants", "balcony garden", "apartment balcony japan",
        "houseplants window light", "balcony coffee morning",
    ],
    "bedroom": [
        "quiet bedroom window", "minimalist bedroom", "japanese tatami bedroom",
        "bedroom morning light", "cozy bedroom",
    ],
    "temple": [
        "japanese temple", "shinto shrine", "torii gate", "buddhist temple japan",
        "pagoda japan", "zen garden",
    ],
    "park": [
        "japan park", "tokyo park", "yoyogi park", "ueno park", "japanese garden",
    ],

    # 歴史人物・絵画系 (パブリックドメイン主体) -----------------------
    "hist_nobunaga": [
        "Oda Nobunaga portrait", "Oda Nobunaga", "Azuchi castle painting",
        "Nobunaga Honnoji",
    ],
    "hist_ieyasu": [
        "Tokugawa Ieyasu portrait", "Tokugawa Ieyasu", "Tokugawa shogun portrait",
    ],
    "hist_hideyoshi": [
        "Toyotomi Hideyoshi portrait", "Toyotomi Hideyoshi", "Hideyoshi painting",
    ],
    "hist_ryoma": [
        "Sakamoto Ryoma portrait", "Sakamoto Ryoma photograph", "Bakumatsu Ryoma",
    ],
    "hist_saigo": [
        "Saigo Takamori portrait", "Saigo Takamori", "Satsuma rebellion painting",
    ],
    "hist_masamune": [
        "Date Masamune portrait", "Date Masamune", "Sendai castle painting",
    ],
    "hist_shingen": [
        "Takeda Shingen portrait", "Takeda Shingen", "Kai province samurai",
    ],
    "hist_kenshin": [
        "Uesugi Kenshin portrait", "Uesugi Kenshin", "Echigo samurai",
    ],
    "hist_armor": [
        "samurai armor ukiyo-e", "samurai armor", "japanese yoroi", "samurai helmet kabuto",
    ],
    "hist_edo": [
        "Edo period painting", "Edo period ukiyo-e", "Edo town painting", "Edo merchant",
    ],
    "hist_meiji": [
        "Meiji era photograph", "Meiji period", "Meiji emperor", "Meiji Tokyo photograph",
    ],
    "hist_bakumatsu": [
        "Bakumatsu samurai", "Bakumatsu photograph", "shinsengumi", "late Edo samurai",
    ],
    "hist_sengoku": [
        "Sengoku battle ukiyo-e", "Sengoku period painting", "Sekigahara battle",
        "Osaka castle battle painting",
    ],
    "hist_heian": [
        "Heian court painting", "Heian period painting", "Genji monogatari emaki",
        "Heian noble",
    ],
    "hist_kabuki": [
        "kabuki actor ukiyo-e", "kabuki print", "Sharaku kabuki", "Toshusai Sharaku",
    ],
    "hist_ukiyoe": [
        "Hokusai", "Hiroshige ukiyo-e", "ukiyo-e print", "Utamaro ukiyo-e",
        "Yoshitoshi ukiyo-e",
    ],

    # バッファ (汎用) ---------------------------------------------------
    "buffer_japan": [
        "Japan landscape", "Mount Fuji landscape", "Japanese countryside",
        "Hokkaido landscape", "Okinawa beach",
    ],
    "buffer_tokyo": [
        "Tokyo skyline", "Tokyo daytime", "Tokyo rooftop", "Shibuya day",
    ],
    "buffer_kyoto": [
        "Kyoto landscape", "Kyoto temple sunlight", "Kyoto canal",
    ],
    "buffer_seasons": [
        "cherry blossom japan", "sakura japan", "japan winter snow", "japan summer fields",
    ],
}

# ---- ロギング -----------------------------------------------------------

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("wiki-refill")


# ---- ユーティリティ ----------------------------------------------------

def slugify(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s[:40]


def http_get(url: str, *, binary: bool = False, retries: int = 3) -> bytes | str:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
            return data if binary else data.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            last_exc = e
            sleep_s = min(2 ** attempt, 10) + random.random()
            log.debug("HTTP fail (%s) attempt %d, sleeping %.1fs", e, attempt + 1, sleep_s)
            time.sleep(sleep_s)
    raise RuntimeError(f"HTTP failed after {retries} retries: {url}") from last_exc


def load_hash_index() -> dict:
    if HASH_INDEX.exists():
        try:
            return json.loads(HASH_INDEX.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            log.warning("hash index corrupt; rebuilding")
    return {"sha1": {}, "url": {}, "next_seq": {}}


def save_hash_index(idx: dict) -> None:
    HASH_INDEX.parent.mkdir(parents=True, exist_ok=True)
    tmp = HASH_INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(HASH_INDEX)


def rebuild_hash_index_from_disk(idx: dict) -> dict:
    """初回 / 破損時用: フォルダ内ファイルを走査してハッシュ index を埋める"""
    if not STOCK_DIR.exists():
        return idx
    for p in STOCK_DIR.iterdir():
        if not p.is_file() or not p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        try:
            h = hashlib.sha1(p.read_bytes()).hexdigest()
            idx.setdefault("sha1", {})[h] = p.name
        except Exception:  # noqa: BLE001
            continue
    return idx


def current_stock_count() -> int:
    if not STOCK_DIR.exists():
        return 0
    return sum(
        1 for p in STOCK_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        and p.name.startswith("wiki_")
    )


# ---- Wikimedia Commons API --------------------------------------------

def search_commons(query: str, limit: int, offset: int = 0, width: int = THUMB_WIDTH) -> list[dict]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": query,
        "gsrlimit": str(limit),
        "gsroffset": str(offset),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": str(width),
        "origin": "*",
    }
    url = f"{API_ENDPOINT}?{urllib.parse.urlencode(params)}"
    raw = http_get(url, binary=False)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    pages = data.get("query", {}).get("pages") or {}
    results = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [None])[0]
        if not ii:
            continue
        thumb = ii.get("thumburl") or ii.get("url")
        if not thumb:
            continue
        # サムネイルが取れる画像ファイル形式のみ
        if not re.search(r"\.(jpe?g|png|webp)(?:$|\?)", thumb, flags=re.I):
            continue
        results.append({
            "title": p.get("title", ""),
            "url": thumb,
            "size": ii.get("size") or 0,
            "license": (ii.get("extmetadata") or {}).get("LicenseShortName", {}).get("value", ""),
        })
    return results


# ---- ダウンロード -----------------------------------------------------

def download_one(prefix: str, query: str, seq: int, item: dict, idx: dict) -> tuple[bool, str]:
    url = item["url"]
    if url in idx.get("url", {}):
        return False, "dup-url"
    ext = ".jpg"
    m = re.search(r"\.(jpe?g|png|webp)(?:$|\?)", url, flags=re.I)
    if m:
        ext = "." + m.group(1).lower().replace("jpeg", "jpg")
    fname = f"wiki_{prefix}_{seq:04d}_{slugify(query)}{ext}"
    out = STOCK_DIR / fname
    if out.exists():
        return False, "dup-name"
    try:
        data = http_get(url, binary=True)
    except Exception as e:  # noqa: BLE001
        return False, f"http-error:{e}"
    if not data or len(data) < 5000:
        return False, "too-small"
    h = hashlib.sha1(data).hexdigest()
    if h in idx.get("sha1", {}):
        return False, "dup-hash"
    out.write_bytes(data)
    idx.setdefault("sha1", {})[h] = fname
    idx.setdefault("url", {})[url] = fname
    return True, fname


def fetch_category(prefix: str, queries: list[str], remaining: int, idx: dict) -> int:
    """このカテゴリで何枚保存できたかを返す"""
    if remaining <= 0:
        return 0
    saved = 0
    seq = idx.setdefault("next_seq", {}).get(prefix, 1)
    target_per_query = max(8, min(PER_KEYWORD_LIMIT, (remaining // max(1, len(queries))) + 4))
    candidates: list[tuple[str, dict]] = []
    for q in queries:
        for offset in (0, 20, 40):  # ページングで重複を避けつつ広く取る
            try:
                results = search_commons(q, limit=target_per_query, offset=offset)
            except Exception as e:  # noqa: BLE001
                log.warning("search fail [%s/%s @%d]: %s", prefix, q, offset, e)
                continue
            for r in results:
                candidates.append((q, r))
            if len(results) < target_per_query:
                break
            time.sleep(0.2)
        if len(candidates) >= remaining * 3:
            break
    random.shuffle(candidates)
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as ex:
        future_meta: dict = {}
        for q, item in candidates:
            if saved >= remaining:
                break
            f = ex.submit(download_one, prefix, q, seq, item, idx)
            future_meta[f] = (q, item)
            seq += 1
        for f in as_completed(future_meta):
            ok, info = f.result()
            if ok:
                saved += 1
                if saved % 25 == 0:
                    log.info("[%s] %d saved (%s)", prefix, saved, info)
                if saved >= remaining:
                    break
    idx["next_seq"][prefix] = seq
    log.info("[%s] complete: %d saved (target %d)", prefix, saved, remaining)
    return saved


# ---- メインロジック ---------------------------------------------------

def plan_quota(target: int) -> dict[str, int]:
    """各カテゴリに割り当てる枚数を決める"""
    scenery = ["cafe", "library", "tokyo", "kyoto", "autumn", "sunset",
               "station", "rainy", "stars", "balcony", "bedroom", "temple", "park"]
    historic = [k for k in KEYWORDS if k.startswith("hist_")]
    buffer = [k for k in KEYWORDS if k.startswith("buffer_")]

    # 風景40% / 歴史40% / バッファ20%
    sc_total = max(1, int(target * 0.4))
    hi_total = max(1, int(target * 0.4))
    bu_total = max(1, target - sc_total - hi_total)

    quota: dict[str, int] = {}
    for cat, names, total in (("sc", scenery, sc_total),
                              ("hi", historic, hi_total),
                              ("bu", buffer, bu_total)):
        each = total // len(names)
        rem = total - each * len(names)
        for i, n in enumerate(names):
            quota[n] = each + (1 if i < rem else 0)
    return quota


def run_download(target: int) -> int:
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    idx = load_hash_index()
    if not idx.get("sha1"):
        log.info("hash index empty; rebuilding from disk")
        idx = rebuild_hash_index_from_disk(idx)

    quota = plan_quota(target)
    log.info("download plan (target=%d): %s", target,
             {k: v for k, v in quota.items() if v})

    total_saved = 0
    try:
        for prefix, need in quota.items():
            if need <= 0:
                continue
            queries = KEYWORDS.get(prefix, [])
            if not queries:
                continue
            got = fetch_category(prefix, queries, need, idx)
            total_saved += got
            save_hash_index(idx)
    finally:
        save_hash_index(idx)
    log.info("run_download finished: %d new files (target %d)", total_saved, target)
    return total_saved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--initial", action="store_true",
                    help=f"initial bulk fetch (default {INITIAL_TARGET} images)")
    ap.add_argument("--target", type=int, default=0,
                    help="explicit number of images to fetch this run")
    ap.add_argument("--threshold", type=int, default=REFILL_THRESHOLD,
                    help="auto mode: only refill when stock falls below this")
    args = ap.parse_args()

    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    have = current_stock_count()
    log.info("current stock count: %d (dir=%s)", have, STOCK_DIR)

    if args.target > 0:
        target = args.target
    elif args.initial:
        # 初回モード: 既存分を引いた残り、最低 INITIAL_TARGET 必要
        target = max(0, INITIAL_TARGET - have)
        if target == 0:
            log.info("already have %d (>= %d); nothing to do", have, INITIAL_TARGET)
            return 0
    else:
        # 自動補充モード
        if have >= args.threshold:
            log.info("stock %d >= threshold %d; no refill needed", have, args.threshold)
            return 0
        target = REFILL_AMOUNT

    log.info("starting download: target=%d", target)
    saved = run_download(target)
    final = current_stock_count()
    log.info("done. saved=%d new, total=%d", saved, final)
    print(f"RESULT saved={saved} total={final} dir={STOCK_DIR}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("interrupted")
        sys.exit(130)
