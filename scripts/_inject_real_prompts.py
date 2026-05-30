#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""200 アプリ 上級プロンプト 実体生成 + 注入 (Phase 2、 2026-05-30)。

問題: 182 本が「下記を AI に貼り付け」と書いて実プロンプトが無い (¥100 中核価値が空)。
対策: 各アプリ title から Gemini で「そのまま AI に貼れる実用プロンプト」生成 → code block 注入。
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
    """# 【AI対話アプリ】200の問い #001「1on1マスターAI」 → 1on1マスターAI"""
    m = re.search(r'#\d{3}「(.+?)」', text)
    if m:
        return m.group(1)
    m2 = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    return m2.group(1) if m2 else 'このアプリ'


def has_prompt_body(text: str) -> bool:
    """上級プロンプト section に code block があるか"""
    m = re.search(r'## 🎯 上級プロンプト', text)
    if not m:
        return True  # section 自体ない → 対象外
    after = text[m.start():m.start() + 1500]
    return '```' in after[:1200]


def gen_prompt(app_title: str, concept: str) -> str:
    """Gemini で実用プロンプト生成"""
    meta = (
        f'あなたは AI 対話プロンプトの専門設計者。\n'
        f'「{app_title}」という自己対話アプリ用の、 ユーザーが ChatGPT/Gemini/Claude に '
        f'そのままコピペして使える実用プロンプトを 1 つ作成せよ。\n\n'
        f'【アプリの趣旨】{concept[:200]}\n\n'
        f'【要件】\n'
        f'1. AI に役割を与える書き出し (例:「あなたは〜の専門コーチです」)\n'
        f'2. ユーザーに 3-5 個の段階的な問いを投げさせる構成\n'
        f'3. 最後に「具体的な次の一歩」を 3 つ提案させて締める\n'
        f'4. 400-600 字。 マークダウン記号 (#, *, **) は使わない\n'
        f'5. そのまま貼れる完成形。 説明文・前置き・後書きは一切不要。 プロンプト本文のみ出力\n'
        f'6. 日本語\n'
    )
    return call_gemini(meta).strip()


def inject(p: Path) -> str:
    """1 ファイルに prompt 注入。 戻り値: 'ok'/'skip'/'fail'"""
    text = p.read_text(encoding='utf-8')
    if has_prompt_body(text):
        return 'skip'
    app_title = extract_app_title(text)
    # concept: 冒頭の説明文 (最初の本文段落)
    concept_m = re.search(r'^#[^\n]+\n+(.+?)\n', text, re.MULTILINE)
    concept = concept_m.group(1) if concept_m else app_title
    try:
        prompt_body = gen_prompt(app_title, concept)
    except Exception as e:
        print(f'  [FAIL] Gemini: {e}', file=sys.stderr)
        return 'fail'
    if not prompt_body or len(prompt_body) < 100:
        print(f'  [FAIL] prompt too short ({len(prompt_body)})', file=sys.stderr)
        return 'fail'
    # 🎯 section の intro 段落の後に code block 挿入
    # 「貼り付けてください」を含む段落の直後に挿入
    m = re.search(r'(## 🎯 上級プロンプト[^\n]*\n)', text)
    if not m:
        return 'fail'
    # header の後、 最初の空行2つ (段落区切り) を探して挿入位置決定
    header_end = m.end()
    # header 後の最初の段落 (intro) の終わりを探す
    rest = text[header_end:]
    # 最初の \n\n 以降に挿入 (intro 段落の後)
    para_m = re.search(r'\n\n', rest)
    insert_pos = header_end + (para_m.end() if para_m else 0)
    code_block = f'```\n{prompt_body}\n```\n\n'
    new_text = text[:insert_pos] + code_block + text[insert_pos:]
    p.write_text(new_text, encoding='utf-8')
    return 'ok'


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='ifrom', type=int, default=1)
    ap.add_argument('--to', dest='ito', type=int, default=200)
    args = ap.parse_args()

    ok, skip, fail = 0, 0, 0
    for i in range(args.ifrom, args.ito + 1):
        p = ART / f'note_{i:03d}.md'
        if not p.exists():
            continue
        r = inject(p)
        if r == 'ok':
            ok += 1
            print(f'[ok] {p.name}')
            time.sleep(4.5)  # Gemini rate limit
        elif r == 'skip':
            skip += 1
        else:
            fail += 1
            time.sleep(8)
    print(f'\n=== Done: ok={ok} skip={skip} fail={fail} ===')


if __name__ == '__main__':
    main()
