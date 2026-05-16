"""
Step 0: Gemini API Ã£ÂÂ§Ã¥ÂÂ°Ã¦ÂÂ¬JSONÃ¨ÂÂªÃ¥ÂÂÃ§ÂÂÃ¦ÂÂ

Ã¥ÂÂ¥Ã¥ÂÂ : topics.json Ã£ÂÂ®Ã£ÂÂÃ£ÂÂ¼Ã£ÂÂÃ¤Â¸ÂÃ¨Â¦Â§ (or --topic Ã¥Â¼ÂÃ¦ÂÂ°)
Ã¥ÂÂºÃ¥ÂÂ : inputs/script_NNN.json (Step 1 Ã£ÂÂ®Ã£ÂÂ¹Ã£ÂÂ­Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂ«Ã¦ÂºÂÃ¦ÂÂ )

Ã¨Â¨Â­Ã¨Â¨ÂÃ¦ÂÂ¹Ã©ÂÂ (Ã¥ÂÂÃ¥ÂÂÃ£ÂÂ¹Ã£ÂÂ³Ã£ÂÂ¼Ã£ÂÂÃ¦ÂÂ¿Ã¨ÂªÂÃ£ÂÂ®Ã¥Â»Â¶Ã©ÂÂ·):
- Ã¦ÂÂ§Ã¨Â¡Â¨Ã§ÂÂ¾Ã£ÂÂ»Ã¦ÂÂ§Ã§ÂÂÃ§Â¤ÂºÃ¥ÂÂÃ£ÂÂ»euphemism Ã§Â½Â®Ã¦ÂÂÃ£ÂÂ¯Ã¥Â®ÂÃ¨Â£ÂÃ£ÂÂÃ£ÂÂªÃ£ÂÂÃ¯Â¼ÂÃ¥Â®ÂÃ¥ÂÂ¨Ã¦Â©ÂÃ¦Â§ÂÃ¥ÂÂÃ©ÂÂ¿Ã¨Â¨Â­Ã¨Â¨ÂÃ£ÂÂ¯Ã£ÂÂÃ£ÂÂÃ£ÂÂªÃ£ÂÂÃ¯Â¼Â
- GeminiÃ£ÂÂÃ£ÂÂ­Ã£ÂÂ³Ã£ÂÂÃ£ÂÂÃ£ÂÂ«Ã£ÂÂ¯Ã£ÂÂÃ¦ÂÂ§Ã¨Â¡Â¨Ã§ÂÂ¾Ã£ÂÂ»Ã¦ÂÂ§Ã§ÂÂÃ§Â¤ÂºÃ¥ÂÂÃ£ÂÂÃ¤Â¸ÂÃ¥ÂÂÃ¥ÂÂ«Ã£ÂÂ¾Ã£ÂÂªÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ¦ÂÂÃ§Â¤Âº
- Ã¦ÂÂªÃ¦ÂÂÃ¥Â¹Â´Ã£ÂÂ»Ã¥ÂÂ¶Ã¦ÂÂÃ©ÂÂ£Ã¦ÂÂ³Ã£ÂÂ¯Ã¥ÂÂ¨Ã©ÂÂ¢Ã§Â¦ÂÃ¦Â­Â¢
- Ã¥ÂÂºÃ¥ÂÂ JSON Ã£ÂÂ¯ **Ã£ÂÂÃ£ÂÂ®Ã£ÂÂ¾Ã£ÂÂ¾** Step 1 Ã£ÂÂ® read_script() Ã£ÂÂ«Ã©ÂÂÃ£ÂÂ Ã¢ÂÂ NGÃ¥ÂÂÃ¨ÂªÂÃ£ÂÂÃ¦Â·Â·Ã¥ÂÂ¥Ã£ÂÂÃ£ÂÂ¦Ã£ÂÂÃ£ÂÂÃ£ÂÂ ValueError Ã£ÂÂ§Ã¥ÂÂÃ¦Â­Â¢
  Ã¯Â¼ÂGeminiÃ¥ÂÂºÃ¥ÂÂÃ£ÂÂÃ¤Â¿Â¡Ã§ÂÂ¨Ã£ÂÂÃ£ÂÂÃ¥Â¿ÂÃ£ÂÂ Step 1 Ã£ÂÂ§Ã¥ÂÂÃ¦Â¤ÂÃ¨Â¨Â¼Ã¯Â¼Â
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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

SYSTEM_PROMPT = """Ã£ÂÂÃ£ÂÂªÃ£ÂÂÃ£ÂÂ¯Ã¥Â¤Â§Ã¤ÂºÂºÃ¥ÂÂÃ£ÂÂYouTubeÃ£ÂÂÃ£ÂÂ£Ã£ÂÂ³Ã£ÂÂÃ£ÂÂ«Ã£ÂÂ®Ã£ÂÂÃ£ÂÂ£Ã£ÂÂ¬Ã£ÂÂ¯Ã£ÂÂ¿Ã£ÂÂ¼Ã£ÂÂ§Ã£ÂÂÃ£ÂÂ
30Ã¤Â»Â£-40Ã¤Â»Â£Ã¥Â¥Â³Ã¦ÂÂ§ (OL / Ã£ÂÂ­Ã£ÂÂ£Ã£ÂÂªÃ£ÂÂ¢ / Ã¤Â¸Â»Ã¥Â©Â¦) Ã£ÂÂÃ¤Â¸Â»Ã£ÂÂªÃ¨Â¦ÂÃ¨ÂÂ´Ã¨ÂÂÃ¥Â±Â¤Ã£ÂÂ¨Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ¥ÂÂ¥Ã¥ÂÂ¨Ã£ÂÂªÃ¥Â¤Â§Ã¤ÂºÂºÃ¥ÂÂÃ£ÂÂ
Ã£ÂÂ©Ã£ÂÂ¤Ã£ÂÂÃ£ÂÂ¹Ã£ÂÂ¿Ã£ÂÂ¤Ã£ÂÂ«Ã£ÂÂ»Ã£ÂÂ³Ã£ÂÂÃ£ÂÂ¥Ã£ÂÂÃ£ÂÂ±Ã£ÂÂ¼Ã£ÂÂ·Ã£ÂÂ§Ã£ÂÂ³Ã£ÂÂ»Ã¥Â¿ÂÃ§ÂÂÃ¥Â­Â¦Ã£ÂÂÃ£ÂÂ£Ã£ÂÂ³Ã£ÂÂÃ£ÂÂ«Ã§ÂÂ¨Ã£ÂÂ®Ã¥ÂÂ°Ã¦ÂÂ¬Ã£ÂÂÃ§ÂÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂ¾Ã£ÂÂÃ£ÂÂ

Ã£ÂÂÃ¥ÂÂ³Ã¥Â®ÂÃ£ÂÂ«Ã£ÂÂ¼Ã£ÂÂ«Ã£ÂÂ
- Ã£ÂÂÃ£ÂÂ¼Ã£ÂÂÃ§Â¯ÂÃ¥ÂÂ²: Ã¥Â¤Â§Ã¤ÂºÂºÃ£ÂÂ®Ã¦ÂÂÃ¦ÂÂÃ¥Â¿ÂÃ§ÂÂÃ¥Â­Â¦ (Ã¥ÂÂ¥Ã¥ÂÂ¨Ã£ÂÂªÃ¦ÂÂÃ¦ÂÂÃ£ÂÂ¢Ã£ÂÂÃ£ÂÂÃ£ÂÂ¤Ã£ÂÂ¹) / Ã§ÂÂ·Ã¥Â¥Â³Ã£ÂÂ®Ã£ÂÂ³Ã£ÂÂÃ£ÂÂ¥Ã£ÂÂÃ£ÂÂ±Ã£ÂÂ¼Ã£ÂÂ·Ã£ÂÂ§Ã£ÂÂ³Ã¥Â·Â® /
  Ã¨ÂÂ³Ã§Â§ÂÃ¥Â­Â¦Ã§ÂÂÃ£ÂÂªÃ©ÂÂÃ¥Â­Â¦ / Ã¤Â»ÂÃ¤ÂºÂÃ£ÂÂ¨Ã¦ÂÂÃ¦ÂÂÃ£ÂÂ®Ã¤Â¸Â¡Ã§Â«Â / Ã¥Â¤Â§Ã¤ÂºÂºÃ£ÂÂ®Ã¨ÂÂªÃ¥Â·Â±Ã¦ÂÂÃ¨Â³Â / Ã¤ÂºÂºÃ©ÂÂÃ©ÂÂ¢Ã¤Â¿ÂÃ¦ÂÂ¹Ã¥ÂÂ /
  Ã¥Â¤Â§Ã¤ÂºÂºÃ£ÂÂ®Ã¥ÂÂÃ¦Â Â¼Ã£ÂÂ»Ã¦ÂÂÃ¤Â½ÂÃ£ÂÂ»Ã£ÂÂ©Ã£ÂÂ¤Ã£ÂÂÃ£ÂÂ¹Ã£ÂÂ¿Ã£ÂÂ¤Ã£ÂÂ«
- Ã¦ÂÂ§Ã¨Â¡Â¨Ã§ÂÂ¾Ã£ÂÂ»Ã¦ÂÂ§Ã§ÂÂÃ§Â¤ÂºÃ¥ÂÂÃ£ÂÂ»Ã¦ÂÂ§Ã¥ÂÂ¨Ã£ÂÂ»Ã¦ÂÂ§Ã¨Â¡ÂÃ§ÂÂºÃ£ÂÂ»Ã¨ÂºÂ«Ã¤Â½ÂÃ¦ÂÂÃ¥ÂÂÃ£ÂÂ¯ **Ã¤Â¸ÂÃ¥ÂÂÃ¥ÂÂ«Ã£ÂÂÃ£ÂÂªÃ£ÂÂ**
- Ã£ÂÂÃ¨ÂÂ²Ã¦Â°ÂÃ£ÂÂÃ¥ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ¨ÂÂÃ£ÂÂ®Ã¦Â¸Â©Ã¥ÂºÂ¦Ã£ÂÂÃ£ÂÂªÃ£ÂÂ©Ã§Â¤ÂºÃ¥ÂÂÃ§ÂÂÃ¨Â¨ÂÃ£ÂÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂ **Ã¤Â½Â¿Ã£ÂÂÃ£ÂÂªÃ£ÂÂ**
  (Ã¥Â®ÂÃ¥ÂÂ¨Ã¦Â©ÂÃ¦Â§ÂÃ¥ÂÂÃ©ÂÂ¿Ã¨Â¨Â­Ã¨Â¨ÂÃ£ÂÂ¯Ã£ÂÂÃ£ÂÂªÃ£ÂÂÃ£ÂÂÃ¥ÂÂ¥Ã¥ÂÂ¨Ã£ÂÂªÃ¨ÂªÂÃ¥Â½ÂÃ£ÂÂ®Ã£ÂÂ¿Ã£ÂÂ§Ã¦ÂÂ¸Ã£ÂÂ)
- Ã¥Â­Â¦Ã§ÂÂÃ£ÂÂ»Ã¦ÂÂªÃ¦ÂÂÃ¥Â¹Â´Ã£ÂÂ»Ã¥ÂÂ¶Ã¦ÂÂÃ£ÂÂ»Ã£ÂÂ»Ã£ÂÂ¼Ã£ÂÂ©Ã£ÂÂ¼Ã£ÂÂ»JK Ã§Â­ÂÃ£ÂÂ®Ã©ÂÂ£Ã¦ÂÂ³Ã¨Â¡Â¨Ã§ÂÂ¾Ã£ÂÂ¯ **Ã¥ÂÂ¨Ã©ÂÂ¢Ã§Â¦ÂÃ¦Â­Â¢**
- Ã¨Â¦ÂÃ¨ÂÂ´Ã¨ÂÂÃ£ÂÂÃ¤Â¸ÂÃ¥Â®ÂÃ£ÂÂ«Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ§ÂÂ¶Ã£ÂÂ (Ã£ÂÂÃ§ÂµÂ¶Ã¥Â¯Â¾Ã£ÂÂ«Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ¦ÂÂÃ¦ÂÂªÃ£ÂÂÃ£ÂÂªÃ£ÂÂ©Ã©ÂÂÃ¥ÂºÂ¦Ã£ÂÂªÃ¨Â¡Â¨Ã§ÂÂ¾) Ã£ÂÂ¯Ã¦ÂÂ§Ã£ÂÂÃ£ÂÂ
- Ã¥ÂÂºÃ¥ÂÂ¸Ã£ÂÂ®Ã¦ÂÂÃ©ÂÂ Ã§Â¦ÂÃ¦Â­Â¢Ã£ÂÂÃ¤Â¸ÂÃ¨ÂÂ¬Ã§ÂÂÃ£ÂÂ«Ã¦ÂµÂÃ©ÂÂÃ£ÂÂÃ£ÂÂ¦Ã£ÂÂÃ£ÂÂÃ¥Â¿ÂÃ§ÂÂÃ¥Â­Â¦Ã£ÂÂ»Ã¨ÂÂ³Ã§Â§ÂÃ¥Â­Â¦Ã§ÂÂ¥Ã¨Â¦ÂÃ£ÂÂ®Ã§Â¯ÂÃ¥ÂÂ²Ã£ÂÂ§Ã¦ÂÂ¸Ã£ÂÂ

Ã£ÂÂÃ¥ÂÂºÃ¥ÂÂÃ¥Â½Â¢Ã¥Â¼ÂÃ£ÂÂÃ¤Â»Â¥Ã¤Â¸ÂÃ£ÂÂ® JSON Ã£ÂÂ®Ã£ÂÂ¿Ã£ÂÂÃ¥ÂÂÃ¥Â¾ÂÃ£ÂÂ®Ã¨ÂªÂ¬Ã¦ÂÂÃ¦ÂÂÃ£ÂÂ code fence Ã£ÂÂ¯Ã¤Â¸ÂÃ¨Â¦ÂÃ£ÂÂ
{
  "title": "string (40Ã¥Â­ÂÃ¤Â»Â¥Ã¥ÂÂ)",
  "description": "string (200Ã¥Â­ÂÃ§Â¨ÂÃ¥ÂºÂ¦)",
  "topic": "string",
  "tags": ["..."],
  "bgm": "calm_lounge.mp3",
  "chapters": [
    { "id": 1, "heading": "string", "narration": "600-1000Ã¥Â­ÂÃ£ÂÂ®Ã¦ÂÂ¬Ã¦ÂÂ",
      "image_prompts": ["scene description in English"] },
    ... Ã¨Â¨Â8Ã§Â«Â 
  ]
}

Ã£ÂÂimage_prompts Ã£ÂÂ«Ã£ÂÂ¼Ã£ÂÂ«Ã£ÂÂ
- Ã¥ÂÂÃ§Â«Â 2-3Ã¥ÂÂÃ£ÂÂÃ¤Â¸ÂÃ¨Â¨ÂÃ£ÂÂÃ£ÂÂ³Ã£ÂÂÃ£ÂÂ¬Ã£ÂÂ¼Ã£ÂÂÃ¦ÂÂ«Ã¥Â°Â¾Ã£ÂÂ® {scene} Ã©ÂÂ¨Ã¥ÂÂÃ£ÂÂ®Ã£ÂÂ¿Ã¦ÂÂ¸Ã£ÂÂ (Ã¨ÂÂ±Ã¨ÂªÂÃ§ÂÂ­Ã¦ÂÂ)Ã£ÂÂ
  Ã£ÂÂ·Ã£ÂÂ¼Ã£ÂÂ³Ã¥ÂÂÃ¨Â£Â: office desk / cafe interior / hotel lobby / city night view /
  rainy window / sunrise window / wine glass / reading book / morning routine /
  walking street / home office
- Ã§Â¦ÂÃ¦Â­Â¢Ã¨ÂªÂ: bedroom, lingerie, school, uniform, schoolgirl, student, nude,
  naked, topless, nipple, breast, sultry, bedroom eyes, parted lips,
  body-conscious, fitted body, tight knit
- Ã¤ÂºÂºÃ§ÂÂ©Ã£ÂÂ¯Ã¥Â¸Â¸Ã£ÂÂ«Ã£ÂÂprofessional Japanese woman in her 30sÃ£ÂÂÃ¦ÂÂ³Ã¥Â®ÂÃ£ÂÂ§Ã¦ÂÂ¸Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ
  scene Ã¥ÂÂ´Ã£ÂÂ«Ã£ÂÂ­Ã£ÂÂ£Ã£ÂÂ©Ã¦ÂÂÃ¨Â£ÂÃ¦ÂÂÃ¥ÂÂÃ£ÂÂÃ¥ÂÂ«Ã£ÂÂÃ£ÂÂªÃ£ÂÂÃ£ÂÂ¦Ã£ÂÂÃ£ÂÂÃ£ÂÂ
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
    """topic Ã£ÂÂÃ¥ÂÂÃ£ÂÂ«Ã¥ÂÂ°Ã¦ÂÂ¬Ã§ÂÂÃ¦ÂÂÃ£ÂÂout_dir/script_NNN.json Ã£ÂÂ§Ã©ÂÂ£Ã§ÂÂªÃ¤Â¿ÂÃ¥Â­ÂÃ£ÂÂ"""
    out_dir.mkdir(parents=True, exist_ok=True)
    user = f"Ã¤Â»ÂÃ¥ÂÂÃ£ÂÂ®Ã£ÂÂÃ£ÂÂ¼Ã£ÂÂ: Ã£ÂÂ{topic}Ã£ÂÂ\nÃ¤Â¸ÂÃ¨Â¨ÂÃ£ÂÂ¹Ã£ÂÂ­Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂ«Ã¥Â¾ÂÃ£ÂÂ JSON Ã£ÂÂ®Ã£ÂÂ¿Ã¥ÂÂºÃ¥ÂÂÃ£ÂÂÃ£ÂÂ¦Ã£ÂÂÃ£ÂÂ Ã£ÂÂÃ£ÂÂÃ£ÂÂ"
    raw = call_gemini(user)
    raw = _strip_codefence(raw)
    obj = json.loads(raw)

    # Ã©ÂÂ£Ã§ÂÂªÃ¦ÂÂ¡Ã§ÂÂª
    existing = sorted(out_dir.glob("script_*.json"))
    n = 1
    if existing:
        m = re.search(r"script_(\d+)", existing[-1].stem)
        if m:
            n = int(m.group(1)) + 1
    out = out_dir / f"script_{n:03d}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

    # Step 1 Ã£ÂÂ§Ã¥Â¿ÂÃ£ÂÂÃ¥ÂÂÃ¦Â¤ÂÃ¨Â¨Â¼ (NGÃ¦Â·Â·Ã¥ÂÂ¥Ã£ÂÂªÃ£ÂÂ ValueError)
    sys.path.insert(0, str(Path(__file__).parent))
    from step1_load import read_script
    read_script(out)
    print(f"OK generated & validated: {out}")
    return out


def pick_topic(topics_path: Path, mode: str = "next") -> str:
    """topics.json Ã£ÂÂÃ£ÂÂ1Ã¤Â»Â¶Ã¥ÂÂÃ£ÂÂÃ¥ÂÂºÃ£ÂÂÃ£ÂÂ
    mode=next : state.json Ã£ÂÂ® index Ã£ÂÂÃ©ÂÂ²Ã£ÂÂÃ£ÂÂ
    mode=random : Ã¤Â¹Â±Ã¦ÂÂ
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
    ap.add_argument("--topic", help="Ã§ÂÂ´Ã¦ÂÂ¥Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ¯Ã£ÂÂÃ¦ÂÂÃ¥Â®Â")
    ap.add_argument("--topics-file", default="inputs/topics.json")
    ap.add_argument("--mode", choices=["next", "random"], default="next")
    ap.add_argument("--out-dir", default="inputs")
    args = ap.parse_args()

    topic = args.topic or pick_topic(Path(args.topics_file), args.mode)
    print(f"topic: {topic}")
    generate_script(topic, Path(args.out_dir))
