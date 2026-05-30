#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_stock_scripts.py
=========================
台本ストック生成スクリプト（Gemini API使用）

使い方:
    python generate_stock_scripts.py --kind history --count 30
    python generate_stock_scripts.py --kind psych --count 30
    python generate_stock_scripts.py --kind history_shorts --count 30

動作:
    1. topics.json を読む
    2. 既に scripts/ に存在する ID はスキップ
    3. 残りのうち、count 本を Gemini で生成
    4. scripts/long_XXX.json (history) / psych_XXX.json (psych) 形式で出力

必要環境変数:
    GEMINI_API_KEY  (.env から自動読み込み)

注意:
    - Geminiコスト目安: 1本あたり約 $0.02 (Flash) / 30本 = $0.6
    - レート制限: Gemini 2.5 Flash 無料枠 15RPM。1分間隔で送信。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Windows UTF-8
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent

# .env 読み込み（GEMINI_API_KEY等）
def load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

load_env()

# 複数キー対応: GEMINI_API_KEY (primary) / GEMINI_API_KEY_2, _3 (fallback)
GEMINI_KEYS = []
for var in ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_FREE"]:
    v = os.environ.get(var, "").strip()
    if v and v not in GEMINI_KEYS:
        GEMINI_KEYS.append(v)

GEMINI_MODELS = [
    os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
]
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"

# レガシー互換
GEMINI_API_KEY = GEMINI_KEYS[0] if GEMINI_KEYS else ""


KIND_CONFIG = {
    "history": {
        "topics": ROOT / "youtube" / "topics.json",
        "out_dir": ROOT / "youtube" / "history_v2" / "scripts",
        "filename_tpl": "long_{id}.json",
        "channel_name": "歴史侍チャンネル @Japanese.Samurai.Channel",
        "chapters": 5,
        # 2026-05-30: char_min/max を倍増 (Task #40)。 既存 7500 chars × edge-tts 12 chars/秒 = 600s で
        # pipeline 1500s 要件未達 fail。 12000 chars に増 + ffmpeg atempo 0.6 で約 1666s 確保。
        "char_min": 11000,
        "char_max": 14000,
        "tone": "落ち着いた侍語り・戦国〜幕末ファン向け・断言と問いかけ・ナレーション一人称",
        "ng": "現代政治への直接言及、医療・法律の確定助言、暴力扇動",
    },
    "psych": {
        "topics": ROOT / "youtube" / "psych_v2" / "topics.json",
        "out_dir": ROOT / "youtube" / "psych_v2" / "scripts",
        "filename_tpl": "psych_{id}.json",
        "channel_name": "大人心理学チャンネル @Otona_Psychology",
        "chapters": 5,
        # 2026-05-30: 同上 (Task #40)
        "char_min": 11000,
        "char_max": 14000,
        "tone": "落ち着いた大人向け・知的かつ官能の余韻・直接的な表現も可・成熟した悩める大人向け",
        "ng": "未成年関連、暴力扇動、明確な性行為描写、医療・法律の確定助言",
    },
    "history_shorts": {
        "topics": ROOT / "youtube" / "shorts_v2" / "topics.json",
        "out_dir": ROOT / "youtube" / "shorts_v2" / "scripts",
        "filename_tpl": "short_{id}.json",
        "channel_name": "歴史ショート @Japanese.Samurai.Channel/shorts",
        "chapters": 1,
        "char_min": 350,
        "char_max": 500,
        "tone": "侍語り・1分以内・冒頭3秒で引き込む・落ちで終わる",
        "ng": "現代政治への直接言及、医療・法律の確定助言、暴力扇動",
    },
    "otona_shorts": {
        "topics": ROOT / "youtube" / "otona_shorts_v2" / "topics.json",
        "out_dir": ROOT / "youtube" / "otona_shorts_v2" / "scripts",
        "filename_tpl": "short_{id}.json",
        "channel_name": "大人ショート @Otona_Psychology/shorts",
        "chapters": 1,
        "char_min": 350,
        "char_max": 500,
        "tone": "成熟した悩める大人向け・1分以内・冒頭3秒で引き込む・心理学トリビア",
        "ng": "未成年関連、暴力扇動、医療・法律の確定助言、明確な性行為描写",
    },
}


def call_gemini(prompt: str, max_retries: int = 2) -> str:
    """Gemini API呼び出し（複数キー × 複数モデル fallback）"""
    if not GEMINI_KEYS:
        raise RuntimeError("No GEMINI_API_KEY set. Add to .env")
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.85, "maxOutputTokens": 8192},
    }).encode("utf-8")

    last_err = None
    # キー → モデルの順で試行
    for key_idx, key in enumerate(GEMINI_KEYS):
        key_label = f"KEY{key_idx+1}({key[-4:]})"
        for model in GEMINI_MODELS:
            url = ENDPOINT.format(m=model) + f"?key={key}"
            for attempt in range(max_retries):
                try:
                    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=120) as res:
                        data = json.loads(res.read().decode("utf-8"))
                        candidates = data.get("candidates", [])
                        if not candidates:
                            last_err = f"empty candidates ({key_label} {model})"
                            break
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts).strip()
                        if text:
                            return text
                        last_err = f"empty text ({key_label} {model})"
                        break
                except urllib.error.HTTPError as e:
                    code = e.code
                    err_body = ""
                    try:
                        err_body = e.read().decode("utf-8", errors="replace")[:200]
                    except Exception:
                        pass
                    last_err = f"HTTP {code} {key_label} {model}: {err_body[:80]}"
                    # 前払い枯渇 or quota切れ → このキーは諦める
                    if code == 429 and ("depleted" in err_body or "RESOURCE_EXHAUSTED" in err_body):
                        print(f"  [skip] {key_label} {model}: credits/quota exhausted")
                        break  # next model (but likely same issue) -- inner break
                    if code == 429:
                        print(f"  [retry] {key_label} {model} 429, sleep 5s then next model")
                        time.sleep(5)
                        break
                    if code == 503:
                        print(f"  [retry] {key_label} {model} 503, fall to next")
                        break
                    if code >= 500:
                        wait = 5 * (attempt + 1)
                        print(f"  [retry] {key_label} {model} {code}, wait {wait}s")
                        time.sleep(wait)
                        continue
                    break
                except Exception as e:
                    last_err = str(e)
                    time.sleep(3)
                    continue
            else:
                continue
        # キー切替前に短く待つ
        if key_idx < len(GEMINI_KEYS) - 1:
            print(f"  [next-key] {key_label} exhausted, trying next key")
    raise RuntimeError(f"All keys+models failed: {last_err}")


def build_chapter_prompt(topic: dict, ch_idx: int, ch_total: int, outline: str, prev_text: str, cfg: dict) -> str:
    return f"""あなたは「{cfg['channel_name']}」のナレーション作家。
全{ch_total}章構成の動画 第{ch_idx}章 本文を執筆せよ。

【動画テーマ】{topic['title']}
【カテゴリ】{topic.get('category', '')}
【トーン】{cfg['tone']}
【NG】{cfg['ng']}

【全体アウトライン】
{outline}

【絶対要件】
1. 文字数: 日本語で{cfg['char_min']}〜{cfg['char_max']}字（厳守）
2. マークダウン記号（**, ##, *, _, バッククォート）禁止
3. ラベル（ナレーション:/BGM:/SE:/VISUAL:/テロップ:）禁止
4. ハッシュタグ禁止、括弧書きト書き禁止
5. 章タイトルは出力しない。本文のみ
6. 段落は2-4行で改行区切り

それでは本文を執筆せよ。"""


def build_outline_prompt(topic: dict, cfg: dict) -> str:
    return f"""あなたは「{cfg['channel_name']}」の構成作家。
以下のテーマで全{cfg['chapters']}章構成の動画アウトラインを作成せよ。

【テーマ】{topic['title']}
【カテゴリ】{topic.get('category', '')}
【トーン】{cfg['tone']}

【出力】
- 全{cfg['chapters']}章。各章タイトル(10-20字)と要点を2-3行
- マークダウン記号禁止、ラベル禁止
- 純粋な日本語のテキストのみ

それでは作成せよ。"""


def check_title_dup(title: str, threshold: float = 0.7) -> bool:
    """既存タイトルと類似度チェック。 True = 重複 (REJECT)、 False = OK。
    title_dedup_check.py を subprocess 経由で呼ぶ。"""
    import subprocess
    try:
        r = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'title_dedup_check.py'),
             '--title', title, '--threshold', str(threshold)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30
        )
        return r.returncode != 0  # exit 1 = REJECT
    except Exception as e:
        print(f"  [WARN] dedup check failed: {e} (skip check)")
        return False


def generate_one(topic: dict, cfg: dict, skip_dup_check: bool = False) -> dict:
    """1本分の台本JSONを生成"""
    print(f"[gen] {topic['id']}: {topic['title']}")
    # 2026-05-30: title 重複防止 (Task #13)。 --force 再生成時は自己重複で skip されるので無効化
    if not skip_dup_check and check_title_dup(topic['title'], threshold=0.7):
        print(f"  [DUP] title 重複検出、 skip: {topic['title']}")
        return None
    outline = call_gemini(build_outline_prompt(topic, cfg))
    chapters = []
    prev = ""
    for i in range(1, cfg["chapters"] + 1):
        time.sleep(4.5)  # Free tier rate limit: 15 RPM (4s+ between calls)
        body = call_gemini(build_chapter_prompt(topic, i, cfg["chapters"], outline, prev, cfg))
        chapters.append({"index": i, "text": body})
        prev = body[-500:]
    return {
        "id": topic["id"],
        "title": topic["title"],
        "category": topic.get("category", ""),
        "description": (
            f"{topic['title']}を深掘り解説します。\n\nチャンネル登録もお願いします。\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "📌 関連プラットフォーム / 苦徹成珠\n"
            "X (Twitter): https://x.com/SoothingSoothin\n"
            "toi-suite (200の問い): https://toi-suite.vercel.app/\n"
            "note: https://note.com/happy_happy_4649\n"
            "━━━━━━━━━━━━━━━━━"
        ),
        "tags": [topic.get("category", ""), "解説", "心理学", "侍"],
        "chapters": chapters,
        "image_urls": [],
        "thumbnail_title": topic["title"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(KIND_CONFIG.keys()))
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--topics-file", default=None,
                    help="diverse topics JSON のパス (例: youtube/topics_history_diverse.json) を指定すると "
                         "KIND_CONFIG のデフォルトを上書きする")
    ap.add_argument("--force", action="store_true",
                    help="既存 ID も上書き再生成 (char_max 変更後の全本再生成用)")
    ap.add_argument("--idx-from", type=int, default=1)
    ap.add_argument("--idx-to", type=int, default=999)
    args = ap.parse_args()

    cfg = KIND_CONFIG[args.kind]
    topics_path = Path(args.topics_file) if args.topics_file else cfg["topics"]
    if not topics_path.is_absolute():
        topics_path = ROOT / topics_path
    out_dir = cfg["out_dir"]
    if not topics_path.exists():
        print(f"[FATAL] topics.json not found: {topics_path}")
        sys.exit(1)
    out_dir.mkdir(parents=True, exist_ok=True)

    # topics_*_diverse.json は {topics: {category: [items]}} ネスト形式の場合あり → 平坦化
    raw = json.loads(topics_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "topics" in raw and isinstance(raw["topics"], dict):
        # diverse 形式: {topics: {category: [{title, tags}]}}
        topics = []
        next_id = 1
        # 既存出力で最大の id を avoidance のため取得
        for p in out_dir.glob("*.json"):
            try:
                n = int(p.stem.split("_")[-1])
                next_id = max(next_id, n + 1)
            except Exception:
                pass
        for category, items in raw["topics"].items():
            for it in items:
                topics.append({
                    "id": f"{next_id:03d}",
                    "title": it["title"],
                    "category": category,
                    "tags": it.get("tags", []),
                })
                next_id += 1
    elif isinstance(raw, list):
        topics = raw
    else:
        # 古い形式 (dict だがネストなし) はそのまま
        topics = raw

    existing = {p.stem for p in out_dir.glob("*.json")}
    print(f"[info] kind={args.kind} topics={len(topics)} existing={len(existing)} (source: {topics_path.name})")

    # --force 時は既存 skip しない、 --idx-from/to で範囲絞り込み可
    pending = []
    for t in topics:
        tid = t["id"]
        try:
            tid_n = int(tid)
            if not (args.idx_from <= tid_n <= args.idx_to):
                continue
        except (ValueError, TypeError):
            pass
        fname = cfg["filename_tpl"].format(id=tid).rsplit(".", 1)[0]
        if fname in existing and not args.force:
            continue
        pending.append(t)

    target = pending[: args.count]
    print(f"[info] generating {len(target)} scripts (force={args.force}, skipped {len(topics) - len(pending)} non-target)")
    if not target:
        print("[info] nothing to generate")
        return

    if not GEMINI_KEYS:
        print("[FATAL] GEMINI_API_KEY (and _2 / _FREE) not in .env")
        sys.exit(2)
    print(f"[info] {len(GEMINI_KEYS)} Gemini key(s) available")

    ok = 0
    fail = 0
    skip = 0
    for t in target:
        try:
            data = generate_one(t, cfg, skip_dup_check=args.force)
            if data is None:
                # 重複検出で skip
                skip += 1
                continue
            fpath = out_dir / cfg["filename_tpl"].format(id=t["id"])
            fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            ok += 1
            print(f"[OK] {fpath.name} ({sum(len(c['text']) for c in data['chapters'])} chars)")
        except KeyboardInterrupt:
            print("\n[STOP] interrupted by user")
            break
        except Exception as e:
            fail += 1
            print(f"[FAIL] {t['id']}: {e}")
            time.sleep(10)

    print(f"\n=== Done: {ok} OK, {skip} SKIP (dup), {fail} FAIL ===")


if __name__ == "__main__":
    main()
