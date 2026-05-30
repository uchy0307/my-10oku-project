#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""既存 script JSON に chapter_image_map (chapter→image_urls index 配列) を均等分配で注入 (Task #36)。

例: 5 chapters + 12 images → {"1":[0,1,2], "2":[3,4], "3":[5,6,7], "4":[8,9], "5":[10,11]}

pipeline.mjs 側で利用する将来改修と組み合わせて、 chapter 切替時に画像も切替 (タイトル合致改善)。
現状の均等分配 (pipeline 内部) と互換、 chapter_image_map あれば優先使用するロジックを pipeline に追加可能。
"""
import json, sys
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent


def calc_chapter_image_map(num_chapters: int, num_images: int) -> dict:
    """chapter 数 + image 数で均等分配 mapping 計算"""
    if num_chapters == 0 or num_images == 0:
        return {}
    per = num_images / num_chapters
    out = {}
    for ch in range(1, num_chapters + 1):
        start = int((ch - 1) * per)
        end = num_images if ch == num_chapters else int(ch * per)
        out[str(ch)] = list(range(start, end))
    return out


def process_dir(scripts_dir: Path, label: str):
    if not scripts_dir.exists():
        return
    ok, skip = 0, 0
    for p in sorted(scripts_dir.glob('*.json')):
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        chapters = data.get('chapters') or []
        images = data.get('image_urls') or []
        if not chapters or not images:
            skip += 1
            continue
        cmap = calc_chapter_image_map(len(chapters), len(images))
        data['chapter_image_map'] = cmap
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        ok += 1
    print(f'[{label}] modified={ok} skipped={skip}')


if __name__ == '__main__':
    process_dir(ROOT / 'youtube' / 'history_v2' / 'scripts', 'history_v2')
    process_dir(ROOT / 'youtube' / 'psych_v2' / 'scripts', 'psych_v2')
