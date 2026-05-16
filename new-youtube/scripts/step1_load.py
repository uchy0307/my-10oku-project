"""
Step 1: 台本JSON読込・検証

スキーマ:
{
  "title": str,
  "description": str,
  "chapters": [
    {"id": int, "heading": str, "narration": str, "image_prompts": [str, ...]},
    ...
  ],
  "bgm": str
}

NG単語が含まれていたら ValueError で即 raise（自動置換しない）。
"""
from __future__ import annotations
import sys as _flush_sys
try:
    _flush_sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
import builtins as _flush_b
_flush_b._orig_print = _flush_b.print
def _flush_print(*a, **k):
    k.setdefault("flush", True)
    return _flush_b._orig_print(*a, **k)
_flush_b.print = _flush_print

import json
from pathlib import Path

NG_WORDS = [
    "セックス", "性行為", "オナニー", "自慰", "アダルト動画",
    "ヌード", "全裸", "露出", "性器", "性的",
    "学生", "制服", "セーラー", "JK", "JC", "少女", "ロリ",
    "school uniform", "schoolgirl", "uniform", "loli",
    "nude", "naked", "topless", "porn", "erotic", "nsfw",
]

MIN_CHAPTERS = 8
MAX_CHAPTERS = 12
# 10分動画想定では1章600-1000字が本番値。プロトタイプ受入は150。
MIN_NARRATION_CHARS = 150
MAX_NARRATION_CHARS = 2000


def _check_ng(text: str, where: str) -> None:
    low = text.lower()
    for ng in NG_WORDS:
        if ng.lower() in low:
            raise ValueError(f"NG word '{ng}' found in {where}")


def read_script(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    for key in ("title", "description", "chapters", "bgm"):
        if key not in data:
            raise ValueError(f"Missing top-level key: {key}")
    if not isinstance(data["chapters"], list):
        raise ValueError("'chapters' must be a list")

    n = len(data["chapters"])
    if not (MIN_CHAPTERS <= n <= MAX_CHAPTERS):
        raise ValueError(f"Chapter count {n} not in [{MIN_CHAPTERS}, {MAX_CHAPTERS}]")

    _check_ng(data["title"], "title")
    _check_ng(data["description"], "description")

    for i, ch in enumerate(data["chapters"]):
        for k in ("id", "heading", "narration", "image_prompts"):
            if k not in ch:
                raise ValueError(f"Chapter {i}: missing '{k}'")
        if not isinstance(ch["image_prompts"], list) or not ch["image_prompts"]:
            raise ValueError(f"Chapter {i}: image_prompts must be non-empty list")
        nar = ch["narration"]
        if not (MIN_NARRATION_CHARS <= len(nar) <= MAX_NARRATION_CHARS):
            raise ValueError(
                f"Chapter {i}: narration length {len(nar)} not in "
                f"[{MIN_NARRATION_CHARS}, {MAX_NARRATION_CHARS}]"
            )
        _check_ng(ch["heading"], f"chapter {i} heading")
        _check_ng(nar, f"chapter {i} narration")
        for j, prm in enumerate(ch["image_prompts"]):
            _check_ng(prm, f"chapter {i} image_prompts[{j}]")

    return data


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "inputs/script_001.json"
    s = read_script(p)
    print(f"OK title={s['title']!r}")
    print(f"   chapters={len(s['chapters'])}, bgm={s['bgm']}")
    total = sum(len(c["narration"]) for c in s["chapters"])
    print(f"   total narration chars: {total}")
