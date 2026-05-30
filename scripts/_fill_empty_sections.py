#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""200 アプリ 空セクション本文生成 + 注入 (Phase 3、 2026-05-30)。

問題: 136 件の番号付き/体験談セクションが見出しだけで本文なし。
対策: 各空セクションの見出し + アプリ趣旨から Gemini で本文生成 → 注入。

⚠ _inject_real_prompts.py 完了後に実行 (同一ファイル競合回避)。
"""
import re, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_stock_scripts import call_gemini, load_env  # noqa: E402
load_env()

ART = ROOT / 'articles'


def extract_app_title(text: str) -> str:
    m = re.search(r'#\d{3}「(.+?)」', text)
    return m.group(1) if m else 'このアプリ'


def find_empty_sections(lines: list) -> list:
    """空セクション (## 見出し直後に本文なし) の行 index リストを返す。
    対象: 番号付き ## N. と ## 体験談"""
    empties = []
    for j, line in enumerate(lines):
        is_target = bool(re.match(r'^##\s+\d+\.', line)) or line.strip().startswith('## 体験談')
        if not is_target:
            continue
        body = []
        for k in range(j + 1, len(lines)):
            nxt = lines[k].strip()
            if nxt.startswith('##') or nxt == '---':
                break
            if nxt:
                body.append(nxt)
        if not body:
            empties.append((j, line.strip()))
    return empties


def gen_section_body(app_title: str, concept: str, section_title: str, is_taiken: bool) -> str:
    if is_taiken:
        meta = (
            f'「{app_title}」という自己対話アプリの体験談を 1 つ書け。\n'
            f'【アプリ趣旨】{concept[:150]}\n'
            f'【見出し】{section_title}\n'
            f'【要件】一人称「私」。 成熟した悩める大人の実体験風。 '
            f'AI 対話でどう変化したかを具体的に。 250-350 字。 '
            f'年齢・役職の固有表記禁止 (47歳/管理職/部長 等は使わない)。 '
            f'マークダウン記号禁止。 本文のみ出力。'
        )
    else:
        meta = (
            f'「{app_title}」という自己対話アプリの解説セクション本文を書け。\n'
            f'【アプリ趣旨】{concept[:150]}\n'
            f'【このセクションの見出し】{section_title}\n'
            f'【要件】見出しの内容を具体的に解説。 AI への問いかけ例を 1-2 個含める。 '
            f'一人称「私」の気づき体験も少し交える。 250-400 字。 '
            f'年齢・役職の固有表記禁止 (47歳/管理職/部長 等)。 '
            f'マークダウン記号禁止。 本文のみ出力。'
        )
    return call_gemini(meta).strip()


def process(p: Path) -> tuple:
    text = p.read_text(encoding='utf-8')
    lines = text.split('\n')
    empties = find_empty_sections(lines)
    if not empties:
        return ('skip', 0)
    app_title = extract_app_title(text)
    concept_m = re.search(r'^#[^\n]+\n+(.+?)\n', text, re.MULTILINE)
    concept = concept_m.group(1) if concept_m else app_title

    # 後ろから挿入 (index ずれ防止)
    filled = 0
    for j, sec_title in reversed(empties):
        is_taiken = sec_title.startswith('## 体験談')
        clean_title = re.sub(r'^##\s*', '', sec_title)
        clean_title = re.sub(r'^\d+\.\s*', '', clean_title)
        try:
            body = gen_section_body(app_title, concept, clean_title, is_taiken)
            time.sleep(4.5)
        except Exception as e:
            print(f'  [FAIL] {p.name} sec "{clean_title[:20]}": {e}', file=sys.stderr)
            time.sleep(8)
            continue
        if not body or len(body) < 80:
            continue
        # 見出し行 j の直後に本文挿入
        lines.insert(j + 1, '')
        lines.insert(j + 2, body)
        filled += 1
    if filled:
        p.write_text('\n'.join(lines), encoding='utf-8')
    return ('ok', filled)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='ifrom', type=int, default=1)
    ap.add_argument('--to', dest='ito', type=int, default=200)
    args = ap.parse_args()

    total_ok, total_filled = 0, 0
    for i in range(args.ifrom, args.ito + 1):
        p = ART / f'note_{i:03d}.md'
        if not p.exists():
            continue
        status, filled = process(p)
        if status == 'ok':
            total_ok += 1
            total_filled += filled
            print(f'[ok] {p.name}: +{filled} sections')
    print(f'\n=== Done: {total_ok} files, {total_filled} sections filled ===')


if __name__ == '__main__':
    main()
