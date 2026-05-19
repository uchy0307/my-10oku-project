"""
Step 0: Gemini API で台本JSONを自動生成

入力: topics.json のトピック1件 (or --topic 引数)
出力: inputs/script_NNN.json (Step 1 のスキーマに準拠)

設計方針 (新チャンネル運用の方針):
- 顔なし運用・性的表現/euphemism 完全除外 (大人向け健康的な台本)
- Gemini プロンプトで顔なし・対人心理を主体に
- 未成年/制服/JK 表現禁止
- 出力 JSON は Step 1 の read_script() に通る。NGワード混入は ValueError
- 各章ナレーション 1200-1500 字 × 8 章 = 9600-12000 字 (TTS で約30-37分尺)
"""
from __future__ import annotations
import sys as _flush_sys
try:
    _flush_sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
import builtins as _flush_b
if not hasattr(_flush_b, "_orig_print"):
    _flush_b._orig_print = _flush_b.print
    def _flush_print(*a, **k):
        k.setdefault("flush", True)
        return _flush_b._orig_print(*a, **k)
    _flush_b.print = _flush_print

import json
import os
import re
import sys
import time
from pathlib import Path
import requests

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_PRIMARY = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MODEL_FALLBACKS = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.5-flash-lite"]
def _build_url(model_name):
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
GEMINI_URL = _build_url(GEMINI_MODEL_PRIMARY)

SYSTEM_PROMPT = """あなたは大人向け YouTube チャンネルのナレーターです。
30代-40代女性 (OL / キャリア / 主婦) を主なターゲットに、対人心理学・恋愛心理・自己成長などの落ち着いた大人向け台本を、
ライフスタイル視点の長めの本文で書きます。

【ルール】
- テーマ範囲: 大人の対人心理学 (恋愛・職場の人間関係) / 女性のコミュニケーション術 /
  認知心理学的な学習 / 仕事と恋愛の両立 / 大人の自己成長戦略 / 人間関係改善法 /
  大人の品格・所作・ライフスタイル
- 性的表現・性的示唆・性器・身体描写 は **一切使わない**
- 学生・未成年・制服・セーラー・JK 等の連想表現は **絶対禁止**
- 視聴対象は大人にしぼる (「学生にも当てはまる」などの言及不可)
- 出力の最後まで、上記禁止語を一切混入させない・自己成長心理学の範囲で書く

【出力形式】以下の JSON のみ出力。前後の説明文や code fence は一切不要:
{
  "title": "string (40字以内)",
  "description": "string (200字程度)",
  "topic": "string",
  "tags": ["..."],
  "bgm": "calm_lounge.mp3",
  "chapters": [
    { "id": 1, "heading": "string", "narration": "1200-1500字の本文",
      "image_prompts": ["scene description in English"] },
    ... 計8章
  ]
}

【image_prompts ルール】
- 各章 2-3枚、英文 1行。背景の {scene} 部分のみ書く (説明禁止)。
  シーン例: office desk / cafe interior / hotel lobby / city night view /
  rainy window / sunrise window / wine glass / reading book / morning routine /
  walking street / home office
- 禁止語: bedroom, lingerie, school, uniform, schoolgirl, student, nude,
  naked, topless, nipple, breast, sultry, bedroom eyes, parted lips,
  body-conscious, fitted body, tight knit
- 人物は常に「professional Japanese woman in her 30s」を文末に置くこと。


【NGワード - 本文・タイトル・description・narration・tags・image_promptsに以下の単語を絶対に含めないこと】
- 性的、エッチ、セックス、裸、露出、胸、淫ら、淫面
- 含んだ場合は出力全体を無効として再生成されます

【出力例】
{
  "title": "30代女性が職場で実際にやりがちな『信頼を失う言動』5選",
  "description": "30代の働く女性が、職場の同僚や上司との関係を悪化させてしまう何気ない言動を、心理学の視点から5つ紹介します。",
  "topic": "職場の人間関係",
  "tags": ["心理学", "職場", "30代女性", "コミュニケーション"],
  "bgm": "calm_lounge.mp3",
  "chapters": [
    {"id": 1, "heading": "感情的になって声を荒げる", "narration": "(1200-1500字の本文。落ち着いた語り口で、心理学的な背景も交えて具体例とともに解説します。)", "image_prompts": ["office desk, professional Japanese woman in her 30s, calm lighting"]},
    {"id": 2, "heading": "他人の陰口を口にする", "narration": "(1200-1500字の本文。)", "image_prompts": ["cafe interior, professional Japanese woman in her 30s, soft daylight"]},
    {"id": 3, "heading": "自分の手柄ばかり話す", "narration": "(1200-1500字の本文。)", "image_prompts": ["meeting room, professional Japanese woman in her 30s, warm tone"]},
    {"id": 4, "heading": "話を遮って自分の意見だけを述べる", "narration": "(1200-1500字の本文。)", "image_prompts": ["hotel lobby, professional Japanese woman in her 30s, evening light"]},
    {"id": 5, "heading": "約束を軽視して遅刻する", "narration": "(1200-1500字の本文。)", "image_prompts": ["city night view, professional Japanese woman in her 30s, reflective mood"]},
    {"id": 6, "heading": "口だけ謝るが助け言葉がない", "narration": "(1200-1500字の本文。)", "image_prompts": ["rainy window, professional Japanese woman in her 30s, contemplative"]},
    {"id": 7, "heading": "周りと比べて人を評価する", "narration": "(1200-1500字の本文。)", "image_prompts": ["walking street, professional Japanese woman in her 30s, daylight"]},
    {"id": 8, "heading": "感謝を伝えず、取り扱いしてしまう", "narration": "(1200-1500字の本文。)", "image_prompts": ["sunrise window, professional Japanese woman in her 30s, hopeful mood"]}
  ]
}
※上記はフォーマット見本です。トピックに合わせて内容は入れ替えてください。必ず 8 章、全チャプターに十分な narration (1200-1500字) を生成し、JSON は途中で打ち切らず、必ず閉じカッコ } まで出力してください。
"""


def call_gemini(user_prompt: str) -> str:
    """429（quota）時は別モデルへ自動 fallback。"""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY env var is required")
    body = {
        "contents": [
            {"role": "user",
             "parts": [{"text": SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.8, "topP": 0.95, "maxOutputTokens": 65536,
            "responseMimeType": "application/json",
        },
    }
    last_err = None
    models_to_try = [GEMINI_MODEL_PRIMARY] + [m for m in GEMINI_MODEL_FALLBACKS if m != GEMINI_MODEL_PRIMARY]
    for model_idx, model_name in enumerate(models_to_try):
        url = _build_url(model_name)
        for attempt in range(3):
            try:
                r = requests.post(
                    url, params={"key": GEMINI_API_KEY},
                    json=body, timeout=120,
                )
                if r.status_code == 429:
                    print(f"[WARN] gemini model={model_name} attempt {attempt+1}: 429 quota")
                    last_err = Exception(f"429 quota on {model_name}")
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                data = r.json()
                if model_idx > 0:
                    print(f"[OK] gemini fallback succeeded on model={model_name}")
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                last_err = e
                print(f"[WARN] gemini model={model_name} attempt {attempt+1}: {e}")
                time.sleep(2 ** attempt)
        print(f"[INFO] gemini model={model_name} all attempts failed, switching to next fallback")
    raise RuntimeError(f"Gemini API failed across all models: {last_err}")


def _strip_codefence(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s


def _generate_once(topic, out_dir, attempt):
    out_dir.mkdir(parents=True, exist_ok=True)
    user = f"今回のテーマ: 「{topic}」\n上記スキーマに従う JSON のみ出力してください。\n[試行{attempt}]"
    raw = call_gemini(user)
    raw = _strip_codefence(raw)
    obj = json.loads(raw)
    existing = sorted(out_dir.glob("script_*.json"))
    n = 1
    if existing:
        m = re.search(r"script_(\d+)", existing[-1].stem)
        if m:
            n = int(m.group(1)) + 1
    out = out_dir / f"script_{n:03d}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script
    read_script(out)
    return out


def generate_script(topic: str, out_dir: Path) -> Path:
    last_err = None
    for attempt in range(1, 11):
        try:
            out = _generate_once(topic, out_dir, attempt)
            print(f"OK generated & validated: {out}")
            return out
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            print(f"[WARN] generate attempt {attempt} rejected: {e}")
    raise RuntimeError(f"All Gemini attempts produced invalid script: {last_err}")


def pick_topic(topics_path: Path, mode: str = "next") -> str:
    """topics.json から1件取り出す。
    mode=next : state.json の index を進める
    mode=random : 乱択
    """
    topics = json.loads(topics_path.read_text(encoding="utf-8"))
    if not topics:
        raise RuntimeError("topics.json is empty")
    if mode == "random":
        import random
        return random.choice(topics)
    state = topics_path.parent / "state.json"
    idx = 0
    if state.exists():
        idx = json.loads(state.read_text(encoding="utf-8")).get("topic_idx", 0)
    t = topics[idx % len(topics)]
    state.write_text(
        json.dumps({"topic_idx": (idx + 1) % len(topics)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return t


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="指定したトピックで生成")
    ap.add_argument("--topics-file", default="inputs/topics.json")
    ap.add_argument("--mode", choices=["next", "random"], default="next")
    ap.add_argument("--out-dir", default="inputs")
    args = ap.parse_args()

    topic = args.topic or pick_topic(Path(args.topics_file), args.mode)
    print(f"topic: {topic}")
    generate_script(topic, Path(args.out_dir))
