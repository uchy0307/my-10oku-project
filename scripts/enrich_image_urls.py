#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""enrich_image_urls.py
台本JSON の image_urls が空のものに、Wikipedia から記事タイトル関連画像を自動付与。

Usage:
  python enrich_image_urls.py --kind history --index 012
  python enrich_image_urls.py --kind history --all
"""
import argparse, json, sys, time, urllib.parse, urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

KIND_DIR = {
    "history": ROOT / "youtube" / "history_v2" / "scripts",
    "psych":   ROOT / "youtube" / "psych_v2" / "scripts",
    "shorts":  ROOT / "youtube" / "shorts_v2" / "scripts",
    "otona_shorts": ROOT / "youtube" / "otona_shorts_v2" / "scripts",
}

UA = "10oku-bot/1.0 (https://github.com/uchy0307; contact uchiyamatakayuki0307@gmail.com)"


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def search_article(query):
    """Wikipedia 検索で最も関連性の高い記事タイトル取得"""
    url = f"https://ja.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch={urllib.parse.quote(query)}&srlimit=5"
    try:
        d = http_json(url)
        for r in d.get("query", {}).get("search", []):
            return r["title"]
    except Exception as e:
        print(f"  search err: {e}")
    return None


def get_article_images(article_title, limit=15):
    """記事内の画像ファイル名一覧取得"""
    url = f"https://ja.wikipedia.org/w/api.php?action=query&format=json&prop=images&titles={urllib.parse.quote(article_title)}&imlimit={limit}"
    try:
        d = http_json(url)
        pages = d.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            files = page.get("images", [])
            # SVG/Logo/Icon 除外
            return [
                f["title"] for f in files
                if f["title"].lower().endswith((".jpg", ".jpeg", ".png"))
                and not any(skip in f["title"].lower() for skip in ["logo", "icon", "wiki-letter", "commons-logo", "symbol", "flag", ".svg", "edit-clear"])
            ]
    except Exception as e:
        print(f"  images err: {e}")
    return []


def resolve_image_url(filename):
    """File:xxx.jpg → https URL"""
    url = f"https://ja.wikipedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url&titles={urllib.parse.quote(filename)}"
    try:
        d = http_json(url)
        pages = d.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            ii = page.get("imageinfo", [])
            if ii: return ii[0].get("url")
    except Exception:
        pass
    return None


def enrich(script_path):
    """1ファイル enrich"""
    spec = json.loads(script_path.read_text(encoding="utf-8"))
    current = spec.get("image_urls", [])
    if isinstance(current, list) and len(current) >= 6:
        return ("skip", len(current))
    title = spec.get("title", "")
    if not title:
        return ("no_title", 0)
    # 検索: title そのまま → 主要キーワード抽出
    article = search_article(title)
    if not article:
        # フォールバック: title の最初の名詞っぽい部分
        keyword = title.split(" ")[0].split("　")[0]
        article = search_article(keyword)
    if not article:
        return ("no_article", 0)
    files = get_article_images(article, limit=15)
    if not files:
        return ("no_images", 0)
    urls = []
    for fn in files[:10]:
        u = resolve_image_url(fn)
        if u: urls.append(u)
        time.sleep(0.2)
    if len(urls) < 1:
        return ("resolve_fail", 0)
    spec["image_urls"] = urls
    spec["_wiki_article"] = article
    script_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return ("ok", len(urls))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(KIND_DIR.keys()))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--index", help="特定IDのみ (e.g. 012)")
    g.add_argument("--all", action="store_true", help="該当kind全件")
    args = ap.parse_args()

    d = KIND_DIR[args.kind]
    if not d.exists():
        print(f"missing: {d}")
        return 1
    if args.index:
        # find by id
        candidates = list(d.glob(f"*_{args.index}.json")) + list(d.glob(f"*{args.index}.json"))
        targets = [c for c in candidates if args.index in c.stem]
        if not targets:
            print(f"no script for index {args.index}")
            return 1
    else:
        targets = sorted(d.glob("*.json"))
    print(f"target: {len(targets)} scripts")
    ok = skip = fail = 0
    for sp in targets:
        try:
            status, n = enrich(sp)
            if status == "ok":
                ok += 1
                print(f"  ✓ {sp.name} → {n} images")
            elif status == "skip":
                skip += 1
            else:
                fail += 1
                print(f"  ✗ {sp.name} → {status}")
            time.sleep(0.3)
        except KeyboardInterrupt:
            print("interrupt")
            break
        except Exception as e:
            fail += 1
            print(f"  ✗ {sp.name}: {e}")
    print(f"\n=== Done: ok={ok} skip={skip} fail={fail} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
