"""
Step 0: Gemini API ã§å°æ¬JSONèªåçæ

å¥å : topics.json ã®ãã¼ãä¸è¦§ (or --topic å¼æ°)
åºå : inputs/script_NNN.json (Step 1 ã®ã¹ã­ã¼ãã«æºæ )

è¨­è¨æ¹é (ååã¹ã³ã¼ãæ¿èªã®å»¶é·):
- æ§è¡¨ç¾ã»æ§çç¤ºåã»euphemism ç½®æã¯å®è£ããªãï¼å®å¨æ©æ§åé¿è¨­è¨ã¯ãããªãï¼
- Geminiãã­ã³ããã«ã¯ãæ§è¡¨ç¾ã»æ§çç¤ºåãä¸åå«ã¾ãªãããæç¤º
- æªæå¹´ã»å¶æé£æ³ã¯å¨é¢ç¦æ­¢
- åºå JSON ã¯ **ãã®ã¾ã¾** Step 1 ã® read_script() ã«éã â NGåèªãæ··å¥ãã¦ããã ValueError ã§åæ­¢
  ï¼Geminiåºåãä¿¡ç¨ããå¿ã Step 1 ã§åæ¤è¨¼ï¼
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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

SYSTEM_PROMPT = """ããªãã¯å¤§äººåãYouTubeãã£ã³ãã«ã®ãã£ã¬ã¯ã¿ã¼ã§ãã
30ä»£-40ä»£å¥³æ§ (OL / ã­ã£ãªã¢ / ä¸»å©¦) ãä¸»ãªè¦è´èå±¤ã¨ãããå¥å¨ãªå¤§äººåã
ã©ã¤ãã¹ã¿ã¤ã«ã»ã³ãã¥ãã±ã¼ã·ã§ã³ã»å¿çå­¦ãã£ã³ãã«ç¨ã®å°æ¬ãçæãã¾ãã

ãå³å®ã«ã¼ã«ã
- ãã¼ãç¯å²: å¤§äººã®ææå¿çå­¦ (å¥å¨ãªææã¢ããã¤ã¹) / ç·å¥³ã®ã³ãã¥ãã±ã¼ã·ã§ã³å·® /
  è³ç§å­¦çãªéå­¦ / ä»äºã¨ææã®ä¸¡ç« / å¤§äººã®èªå·±æè³ / äººéé¢ä¿æ¹å /
  å¤§äººã®åæ ¼ã»æä½ã»ã©ã¤ãã¹ã¿ã¤ã«
- æ§è¡¨ç¾ã»æ§çç¤ºåã»æ§å¨ã»æ§è¡çºã»èº«ä½æåã¯ **ä¸åå«ããªã**
- ãè²æ°ãåãããããèã®æ¸©åº¦ããªã©ç¤ºåçè¨ãæãã **ä½¿ããªã**
  (å®å¨æ©æ§åé¿è¨­è¨ã¯ããªããå¥å¨ãªèªå½ã®ã¿ã§æ¸ã)
- å­¦çã»æªæå¹´ã»å¶æã»ã»ã¼ã©ã¼ã»JK ç­ã®é£æ³è¡¨ç¾ã¯ **å¨é¢ç¦æ­¢**
- è¦è´èãä¸å®ã«ãããç¶ã (ãçµ¶å¯¾ã«ããããææªããªã©éåº¦ãªè¡¨ç¾) ã¯æ§ãã
- åºå¸ã®æé ç¦æ­¢ãä¸è¬çã«æµéãã¦ããå¿çå­¦ã»è³ç§å­¦ç¥è¦ã®ç¯å²ã§æ¸ã

ãåºåå½¢å¼ãä»¥ä¸ã® JSON ã®ã¿ãåå¾ã®èª¬ææã code fence ã¯ä¸è¦ã
{
  "title": "string (40å­ä»¥å)",
  "description": "string (200å­ç¨åº¦)",
  "topic": "string",
  "tags": ["..."],
  "bgm": "calm_lounge.mp3",
  "chapters": [
    { "id": 1, "heading": "string", "narration": "600-1000å­ã®æ¬æ",
      "image_prompts": ["scene description in English"] },
    ... è¨8ç« 
  ]
}

ãimage_prompts ã«ã¼ã«ã
- åç« 2-3åãä¸è¨ãã³ãã¬ã¼ãæ«å°¾ã® {scene} é¨åã®ã¿æ¸ã (è±èªç­æ)ã
  ã·ã¼ã³åè£: office desk / cafe interior / hotel lobby / city night view /
  rainy window / sunrise window / wine glass / reading book / morning routine /
  walking street / home office
- ç¦æ­¢èª: bedroom, lingerie, school, uniform, schoolgirl, student, nude,
  naked, topless, nipple, breast, sultry, bedroom eyes, parted lips,
  body-conscious, fitted body, tight knit
- äººç©ã¯å¸¸ã«ãprofessional Japanese woman in her 30sãæ³å®ã§æ¸ãããã
  scene å´ã«ã­ã£ã©æè£æåãå«ããªãã¦ããã
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
    """topic ãåã«å°æ¬çæãout_dir/script_NNN.json ã§é£çªä¿å­ã"""
    out_dir.mkdir(parents=True, exist_ok=True)
    user = f"ä»åã®ãã¼ã: ã{topic}ã\nä¸è¨ã¹ã­ã¼ãã«å¾ã JSON ã®ã¿åºåãã¦ãã ããã"
    raw = call_gemini(user)
    raw = _strip_codefence(raw)
    obj = json.loads(raw)

    # é£çªæ¡çª
    existing = sorted(out_dir.glob("script_*.json"))
    n = 1
    if existing:
        m = re.search(r"script_(\d+)", existing[-1].stem)
        if m:
            n = int(m.group(1)) + 1
    out = out_dir / f"script_{n:03d}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

    # Step 1 ã§å¿ãåæ¤è¨¼ (NGæ··å¥ãªã ValueError)
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script
    read_script(out)
    print(f"OK generated & validated: {out}")
    return out


def pick_topic(topics_path: Path, mode: str = "next") -> str:
    """topics.json ãã1ä»¶åãåºãã
    mode=next : state.json ã® index ãé²ãã
    mode=random : ä¹±æ
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
    ap.add_argument("--topic", help="ç´æ¥ãããã¯ãæå®")
    ap.add_argument("--topics-file", default="inputs/topics.json")
    ap.add_argument("--mode", choices=["next", "random"], default="next")
    ap.add_argument("--out-dir", default="inputs")
    args = ap.parse_args()

    topic = args.topic or pick_topic(Path(args.topics_file), args.mode)
    print(f"topic: {topic}")
    generate_script(topic, Path(args.out_dir))
