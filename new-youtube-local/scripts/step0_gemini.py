Otona_PsychologyOtona_Psychology"""step0_gemini.py
@otonano_Psychology 夜19:00枠用 台本JSON生成
- 5章構成・各章 6000-8000字（10分動画では各章1500-2000字に短縮可）
- A案と同方針のtone・エロ度（大人の心理学・恋愛/性愛/対人/裏側系、攻めた表現OK）
- 出力: output/<id>_script.json
"""
import os, sys, json, time, re
from pathlib import Path
import urllib.request, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"
TOPICS_FILE = ROOT / "topics.json"
STATE_FILE = OUTPUT_DIR / "state.json"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# 2026-05-20 ROOT FIX: model fallback chain (was: blind retry on same model -> infinite 429).
# Order: primary first, then live free-tier models. Each 429/UNAVAILABLE falls to next pool.
GEMINI_FALLBACK_MODELS = [
    GEMINI_MODEL,
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
]
GEMINI_ENDPOINT_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 10分動画想定: 各章 1500-2000字（合計 約8000-10000字）
CHAR_MIN = int(os.environ.get("CHAPTER_CHAR_MIN", "1500"))
CHAR_MAX = int(os.environ.get("CHAPTER_CHAR_MAX", "2000"))

OUTLINE_PROMPT = """あなたは大人向け心理学チャンネル「@otonano_Psychology」の構成作家。
以下のテーマで10分のYouTube動画の章立て（5章構成）を作成せよ。

【テーマ】{title}
【カテゴリ】{category}

【ターゲット】30-50代男女・恋愛/性愛/対人関係/裏側心理に関心
【トーン】落ち着いた大人向け・知的かつ官能の余韻・直接的な表現も可（性愛・恋愛駆け引き・暗黒心理含む）
【NG】未成年関連、暴力扇動、明確な性行為描写、医療・法律の確定的助言

【出力】
- 5章構成。各章タイトル（10-20字）と要点を2-4行
- マークダウン記号（**, ##, *）禁止、ラベル禁止
- 純粋な日本語の章タイトルと要点のみ

【例】
第一章 沈黙が語る本音
夜更けの会話で生まれる距離の縮まり方。
言葉の代わりに視線が伝える欲望のサイン。

それでは執筆を開始せよ。"""

CHAPTER_PROMPT = """あなたは大人向け心理学チャンネル「@otonano_Psychology」のナレーション作家。
全5章構成・10分動画の「第{idx}章」本文を執筆せよ。

【動画テーマ】{title}
【カテゴリ】{category}
【全体アウトライン】
{outline}

【今書く章】
第{idx}章 {ch_title}
要点: {brief}

{prev_block}

【絶対要件】
1. 文字数: 日本語で{cmin}〜{cmax}字
2. 純粋なナレーション本文のみ。マークダウン記号（**, ##, *, _, バッククォート）禁止
3. ラベル（ナレーション:/BGM:/SE:/VISUAL:/テロップ:）禁止
4. ハッシュタグ禁止、括弧書き（ト書き）禁止
5. 章タイトルは出力しない。本文だけ
6. 段落は2-4行で改行区切り
7. 大人向け心理学トーン:
   - 落ち着いた断言と問いかけのリズム
   - 恋愛/性愛/暗黒心理に踏み込む表現可（直接的・官能的・心理的）
   - 「あなた」と読者に語りかける2人称多用
   - 余韻と間を意識した文体

【トーン参考】
「人は、なぜ手に入らないものほど欲しくなるのか。」
「触れたいと思った瞬間、すでに心は半分奪われている。」

第{idx}章の本文を、純粋なナレーションとしてのみ出力せよ。"""

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"processed": [], "lastRun": None, "currentTopic": None}

def save_state(s):
    ensure_dir(OUTPUT_DIR)
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

def load_topics():
    if not TOPICS_FILE.exists():
        # フォールバック: デフォルト topics
        default = [
            {"id": "p001", "title": "なぜ既婚者ほど深く堕ちるのか", "category": "恋愛心理"},
            {"id": "p002", "title": "沈黙のあとに訪れる本音の瞬間", "category": "対人心理"},
            {"id": "p003", "title": "触れたい欲求の正体", "category": "性愛心理"},
            {"id": "p004", "title": "嫉妬が愛を強める理由", "category": "恋愛心理"},
            {"id": "p005", "title": "夜にだけ語られる心の闇", "category": "暗黒心理"},
        ]
        TOPICS_FILE.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        return default
    return json.loads(TOPICS_FILE.read_text(encoding="utf-8"))

def pick_next_topic(topics, state, force_id=None):
    if force_id:
        for t in topics:
            if t["id"] == force_id:
                return t
    processed = set(state.get("processed", []))
    for t in topics:
        if t["id"] not in processed:
            return t
    return None

def _call_one_model(model: str, prompt: str) -> str:
    """Single model call. Returns text or raises (HTTPError / RuntimeError)."""
    url = f"{GEMINI_ENDPOINT_TMPL.format(model=model)}?key={GEMINI_API_KEY}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "thinkingConfig": {"thinkingBudget": 0},
            "maxOutputTokens": 32768,
            "responseMimeType": "text/plain",
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    cands = data.get("candidates", [])
    if not cands:
        raise RuntimeError(f"no candidates: {data}")
    parts = cands[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise RuntimeError(f"empty text: {data}")
    return text


def call_gemini(prompt: str, attempt: int = 1) -> str:
    """Try each model in GEMINI_FALLBACK_MODELS once.
    2026-05-20 ROOT FIX: previous version recursively retried the SAME model on 429,
    causing infinite quota errors. Now: 429/503 → try next model, no blind retry.
    `attempt` param kept for backwards compat with any external callers; unused.
    """
    if not GEMINI_API_KEY:
        print("[step0] WARN: GEMINI_API_KEY not set — emitting stub")
        return f"[STUB]\n{prompt[:200]}\n\n--- ここに本文が入ります ---\n" + ("ダミー本文。" * 200)
    last_err = None
    for model in GEMINI_FALLBACK_MODELS:
        try:
            print(f"[step0] try model={model}")
            return _call_one_model(model, prompt)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            print(f"[step0] model={model} HTTPError {e.code}: {body[:200]}")
            last_err = e
            # On 429/503/UNAVAILABLE: try next model immediately (no sleep, no retry)
            if e.code in (429, 503, 500):
                continue
            # On 404 (model unsupported): try next model
            if e.code == 404:
                continue
            # Other HTTP errors (4xx auth, 5xx) — fail fast
            raise
        except (urllib.error.URLError, RuntimeError) as e:
            print(f"[step0] model={model} error: {e}")
            last_err = e
            continue
    # All models exhausted
    raise RuntimeError(f"[step0] all {len(GEMINI_FALLBACK_MODELS)} models exhausted; last_err={last_err}")

def clean_text(t: str) -> str:
    t = re.sub(r"[#*_`]+", "", t)
    t = re.sub(r"^(ナレーション|ナレーター|BGM|SE|VISUAL|テロップ)[:：].*$", "", t, flags=re.M)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def parse_outline(text: str):
    """outline テキストから章タイトル+brief 5件抽出"""
    text = clean_text(text)
    blocks = re.split(r"\n(?=第[一二三四五六七八九十1-9]+章\s)", text)
    chapters = []
    for b in blocks:
        m = re.match(r"^(第[一二三四五六七八九十1-9]+章\s*[^\n]+)\n(.+)", b, flags=re.S)
        if m:
            title = m.group(1).strip()
            brief = m.group(2).strip()
            chapters.append({"title": title, "brief": brief})
    if len(chapters) < 5:
        # フォールバック
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        chapters = []
        for i in range(0, min(len(lines), 10), 2):
            chapters.append({"title": lines[i], "brief": lines[i+1] if i+1 < len(lines) else ""})
    return chapters[:5]

def summarize_prev(chapters_so_far):
    if not chapters_so_far:
        return ""
    items = []
    for i, c in enumerate(chapters_so_far, 1):
        body = c.get("body", "")
        items.append(f"第{i}章 {c['title']}: {body[:120]}…")
    return "\n".join(items)

def main():
    ensure_dir(OUTPUT_DIR)
    force_id = None
    test_mode = "--test" in sys.argv
    for a in sys.argv:
        if a.startswith("--topic="):
            force_id = a.split("=", 1)[1]

    topics = load_topics()
    state = load_state()
    topic = pick_next_topic(topics, state, force_id=force_id)
    if not topic:
        print("[step0] No unprocessed topic. Exit.")
        sys.exit(0)

    print(f"[step0] topic: {topic['id']} {topic['title']}")

    outline_text = call_gemini(OUTLINE_PROMPT.format(title=topic["title"], category=topic["category"]))
    chapters_meta = parse_outline(outline_text)
    if len(chapters_meta) < 5:
        # シンプルな補完
        while len(chapters_meta) < 5:
            chapters_meta.append({"title": f"第{len(chapters_meta)+1}章 補章", "brief": "補章。"})

    chapters_full = []
    for i, cm in enumerate(chapters_meta, 1):
        prev_block = ""
        prev = summarize_prev(chapters_full)
        if prev:
            prev_block = f"【前章までの要約】\n{prev}\n"
        prompt = CHAPTER_PROMPT.format(
            idx=i, title=topic["title"], category=topic["category"],
            outline=outline_text, ch_title=cm["title"], brief=cm["brief"],
            prev_block=prev_block, cmin=CHAR_MIN, cmax=CHAR_MAX,
        )
        body = clean_text(call_gemini(prompt))
        chapters_full.append({"index": i, "title": cm["title"], "brief": cm["brief"], "body": body})
        print(f"[step0] chapter {i}: {len(body)} chars")

    out = {
        "id": topic["id"],
        "title": topic["title"],
        "category": topic["category"],
        "outline": outline_text,
        "chapters": chapters_full,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": GEMINI_MODEL,
        "testMode": test_mode,
    }
    out_path = OUTPUT_DIR / f"{topic['id']}_script.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[step0] wrote {out_path}")

    state["currentTopic"] = topic["id"]
    state["lastRun"] = out["createdAt"]
    save_state(state)

if __name__ == "__main__":
    main()
