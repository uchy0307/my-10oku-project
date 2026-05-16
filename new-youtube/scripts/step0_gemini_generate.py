"""
Step 0: Gemini API で台本JSON自動生成

入力 : topics.json のテーマ一覧 (or --topic 引数)
出力 : inputs/script_NNN.json (Step 1 のスキーマに準拠)

設計方針 (前回スコープ承認の延長):
- 性表現・性的示唆・euphemism 置換は実装しない（安全機構回避設計はやらない）
- Geminiプロンプトには「性表現・性的示唆を一切含まない」を明示
- 未成年・制服連想は全面禁止
- 出力 JSON は **そのまま** Step 1 の read_script() に通す → NG単語が混入していたら ValueError で停止
  （Gemini出力を信用せず必ず Step 1 で再検証）
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
from pathlib import Path
import requests

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro-latest")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

SYSTEM_PROMPT = """あなたは大人向けYouTubeチャンネルのディレクターです。
30代-40代女性 (OL / キャリア / 主婦) を主な視聴者層とする、健全な大人向け
ライフスタイル・コミュニケーション・心理学チャンネル用の台本を生成します。

【厳守ルール】
- テーマ範囲: 大人の恋愛心理学 (健全な恋愛アドバイス) / 男女のコミュニケーション差 /
  脳科学的な雑学 / 仕事と恋愛の両立 / 大人の自己投資 / 人間関係改善 /
  大人の品格・所作・ライフスタイル
- 性表現・性的示唆・性器・性行為・身体描写は **一切含めない**
- 「色気を匂わせる」「肌の温度」など示唆的言い換えも **使わない**
  (安全機構回避設計はしない。健全な語彙のみで書く)
- 学生・未成年・制服・セーラー・JK 等の連想表現は **全面禁止**
- 視聴者を不安にさせる煶り (「絶対に〇〇」「最悪」など過度な表現) は控える
- 出典の捏造禁止。一般的に流通している心理学・脳科学知見の範囲で書く

【出力形式】以下の JSON のみ。前後の説明文や code fence は不要。
{
  "title": "string (40字以内)",
  "description": "string (200字程度)",
  "topic": "string",
  "tags": ["..."],
  "bgm": "calm_lounge.mp3",
  "chapters": [
    { "id": 1, "heading": "string", "narration": "600-1000字の本文",
      "image_prompts": ["scene description in English"] },
    ... 計8章
  ]
}

【image_prompts ルール】
- 各章2-3個。下記テンプレート末尾の {scene} 部分のみ書く (英語短文)。
  シーン候補: office desk / cafe interior / hotel lobby / city night view /
  rainy window / sunrise window / wine glass / reading book / morning routine /
  walking street / home office
- 禁止語: bedroom, lingerie, school, uniform, schoolgirl, student, nude,
  naked, topless, nipple, breast, sultry, bedroom eyes, parted lips,
  body-conscious, fitted body, tight knit
- 人物は常に「professional Japanese woman in her 30s」想定で書くため、
  scene 側にキャラ服装描写を含めなくてよい。
"""


def call_gemini(user_prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY env var is required")
    body = {
        "contents": [
            {"role": "user",
             "parts": [{"text": SYSTEM_PROMPT + "\n\n---\n\n" + user_prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.8, "topP": 0.95, "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }
    last_err = None
    for attempt in range(3):
        try:
            r = requests.post(
                GEMINI_URL, params={"key": GEMINI_API_KEY},
                json=body, timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            last_err = e
            print(f"[WARN] gemini attempt {attempt+1}: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Gemini API failed: {last_err}")


def _strip_codefence(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s


def generate_script(topic: str, out_dir: Path) -> Path:
    """topic を元に台本生成。out_dir/script_NNN.json で連番保存。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    user = f"今回のテーマ: 「{topic}」\n上記スキーマに従い JSON のみ出力してください。"
    raw = call_gemini(user)
    raw = _strip_codefence(raw)
    obj = json.loads(raw)

    # 連番採番
    existing = sorted(out_dir.glob("script_*.json"))
    n = 1
    if existing:
        m = re.search(r"script_(\d+)", existing[-1].stem)
        if m:
            n = int(m.group(1)) + 1
    out = out_dir / f"script_{n:03d}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

    # Step 1 で必ず再検証 (NG混入なら ValueError)
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script
    read_script(out)
    print(f"OK generated & validated: {out}")
    return out


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
    ap.add_argument("--topic", help="直接トピックを指定")
    ap.add_argument("--topics-file", default="inputs/topics.json")
    ap.add_argument("--mode", choices=["next", "random"], default="next")
    ap.add_argument("--out-dir", default="inputs")
    args = ap.parse_args()

    topic = args.topic or pick_topic(Path(args.topics_file), args.mode)
    print(f"topic: {topic}")
    generate_script(topic, Path(args.out_dir))
