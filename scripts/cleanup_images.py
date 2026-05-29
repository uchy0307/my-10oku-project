#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cleanup_images.py
stock_images/wiki/ の不要画像を削除し容量と検索効率を改善。

削除対象:
1. buffer カテゴリ（カテゴリ不明）
2. 重複ハッシュ
3. --dry-run でプレビューのみ

Usage:
  python cleanup_images.py --dry-run    # 削除候補表示
  python cleanup_images.py              # 実行
  python cleanup_images.py --keep-buffer  # bufferは残す
"""
import argparse, hashlib, sys
from pathlib import Path
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STOCK_DIR = ROOT / "youtube" / "stock_images" / "wiki"

# 有効カテゴリ（pipeline で参照されるもの）
VALID_CATEGORIES = {
    "hist", "sengoku", "edo", "meiji", "bakumatsu", "armor", "kabuki",
    "cafe", "library", "bedroom", "balcony", "sunset", "stars",
    "tokyo", "kyoto", "station", "rainy", "autumn", "park", "temple",
    "yamato", "samurai",
}


def categorize(filename):
    import re
    m = re.match(r"wiki_([a-z]+)_", filename)
    return m.group(1) if m else "unknown"


def file_hash(p, chunks=1024):
    h = hashlib.md5()
    with open(p, "rb") as f:
        # Sample first + middle + last chunk for speed
        h.update(f.read(chunks * 4))
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-buffer", action="store_true", help="buffer カテゴリ残す")
    ap.add_argument("--max", type=int, default=2000, help="上限超えたら古い順削除")
    args = ap.parse_args()

    if not STOCK_DIR.exists():
        print(f"NO {STOCK_DIR}")
        return 1

    all_files = list(STOCK_DIR.glob("*.jpg")) + list(STOCK_DIR.glob("*.png"))
    print(f"=== {len(all_files)}枚 / {sum(f.stat().st_size for f in all_files)/1024/1024:.0f}MB ===")

    delete = []
    # 1. 無効カテゴリ
    for f in all_files:
        cat = categorize(f.name)
        if cat not in VALID_CATEGORIES:
            if args.keep_buffer and cat == "buffer":
                continue
            delete.append((f, f"invalid_cat:{cat}"))

    # 2. 重複（簡易ハッシュ）
    print("--- 重複検出（部分hash）---")
    seen = defaultdict(list)
    for f in all_files:
        try:
            h = file_hash(f)
            seen[h].append(f)
        except Exception:
            pass
    for h, files in seen.items():
        if len(files) > 1:
            # 最大サイズ以外を delete
            files.sort(key=lambda x: -x.stat().st_size)
            for dup in files[1:]:
                if (dup, None) not in [(d, _) for d, _ in delete]:
                    delete.append((dup, "duplicate"))

    # 3. 上限超え
    keep_count = len(all_files) - len(set(d for d, _ in delete))
    if keep_count > args.max:
        # 古い順
        remaining = [f for f in all_files if not any(f == d for d, _ in delete)]
        remaining.sort(key=lambda x: x.stat().st_mtime)
        for f in remaining[: keep_count - args.max]:
            delete.append((f, "over_limit"))

    if not delete:
        print("✓ 削除対象なし")
        return 0

    delete_unique = list({d: r for d, r in delete}.items())
    total_freed = sum(d.stat().st_size for d, _ in delete_unique) / 1024 / 1024
    by_reason = defaultdict(int)
    for d, r in delete_unique:
        by_reason[r] += 1
    print(f"\n=== 削除候補: {len(delete_unique)}本 / {total_freed:.1f}MB ===")
    for r, n in sorted(by_reason.items(), key=lambda x: -x[1]):
        print(f"  {r}: {n}")

    if args.dry_run:
        print("\n(--dry-run なので削除しません)")
        return 0

    for d, r in delete_unique:
        try:
            d.unlink()
        except Exception as e:
            print(f"  fail: {d.name}: {e}")
    print(f"✓ {len(delete_unique)}本 削除完了 / {total_freed:.1f}MB 解放")
    return 0


if __name__ == "__main__":
    sys.exit(main())
