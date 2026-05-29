#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""edge-tts 投入前に台本テキストを固有名詞ふりがなに置換。

2026-05-30 開始 (Task #35)。
edge-tts は人名・地名・歴史用語の漢字読み弱い ("今川氏親→いまがしおや" 等)。
台本テキストをひらがな置換してから edge-tts に投入すれば正しく読まれる。

使い方:
  # 単体 (テスト):
  python preprocess_yomi.py < input.txt > output.txt
  python preprocess_yomi.py --in input.txt --out output.txt

  # ライブラリとして:
  from preprocess_yomi import apply_yomi
  text = apply_yomi("北条早雲の今川氏親への手紙")
  # → "ほうじょうそううんのいまがわうじちかへの手紙"
"""
import argparse, json, sys
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent
DICT_PATH = ROOT / '_yomi_dict.json'

_CACHE = None


def load_dict():
    """JSON 全カテゴリを flat にして単一 dict に統合。 module-level cache。"""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not DICT_PATH.exists():
        print(f'[preprocess_yomi] WARN: {DICT_PATH} not found, no yomi replacement applied', file=sys.stderr)
        _CACHE = {}
        return _CACHE
    try:
        raw = json.loads(DICT_PATH.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'[preprocess_yomi] ERR: failed to load {DICT_PATH}: {e}', file=sys.stderr)
        _CACHE = {}
        return _CACHE
    flat = {}
    for k, v in raw.items():
        if k.startswith('_'):  # _meta 等はスキップ
            continue
        if isinstance(v, dict):
            flat.update(v)
        elif isinstance(v, str):
            flat[k] = v
    _CACHE = flat
    return flat


def apply_yomi(text):
    """長い熟語から順に置換 (短い熟語による部分マッチを避ける)。
    例: 「今川氏親」「今川義忠」を「今川」より先に置換、 部分マッチ防止。"""
    if not isinstance(text, str) or not text:
        return text
    d = load_dict()
    if not d:
        return text
    for kanji in sorted(d.keys(), key=len, reverse=True):
        if kanji in text:
            text = text.replace(kanji, d[kanji])
    return text


def main():
    ap = argparse.ArgumentParser(description='Apply yomi (furigana) replacement to text for edge-tts.')
    ap.add_argument('--in', dest='in_path', help='input text file (default: stdin)')
    ap.add_argument('--out', dest='out_path', help='output text file (default: stdout)')
    ap.add_argument('--verbose', action='store_true', help='print replacement counts to stderr')
    args = ap.parse_args()

    if args.in_path:
        text = Path(args.in_path).read_text(encoding='utf-8')
    else:
        text = sys.stdin.read()

    d = load_dict()
    if args.verbose:
        replaced = 0
        out = text
        for kanji in sorted(d.keys(), key=len, reverse=True):
            if kanji in out:
                cnt = out.count(kanji)
                out = out.replace(kanji, d[kanji])
                replaced += cnt
        print(f'[preprocess_yomi] applied {replaced} replacements ({len(d)} dict entries loaded)', file=sys.stderr)
    else:
        out = apply_yomi(text)

    if args.out_path:
        Path(args.out_path).write_text(out, encoding='utf-8')
    else:
        sys.stdout.write(out)


if __name__ == '__main__':
    main()
