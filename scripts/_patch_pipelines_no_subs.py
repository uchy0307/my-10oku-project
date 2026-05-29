#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2026-05-30 パイプライン修正: 字幕焼き込み完全削除 + history 動画ループ削除。

うっちー様指示:
  「今後 YT 全て (歴史/大人/両ショート) 字幕一切なし」
  「音声と画像イメージは必ずタイトルに合わす」
  「アップロード済みは放置、今後の YT はマスト」
"""
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')

PATCHES = []

# =====================================================================
# history_v2/pipeline.mjs
# =====================================================================
hist = ROOT / 'youtube' / 'history_v2' / 'pipeline.mjs'
text = hist.read_text(encoding='utf-8')

# 1. ASS subtitles 生成全体 (L152-202 相当) を削除
#   start: "// ---------- 4. Build ASS subtitles ----------"
#   end  : "fs.writeFileSync(assPath, assText, 'utf8');"
ass_start = text.find('// ---------- 4. Build ASS subtitles ----------')
ass_end_marker = "fs.writeFileSync(assPath, assText, 'utf8');"
ass_end = text.find(ass_end_marker)
if ass_start >= 0 and ass_end >= 0:
    ass_end += len(ass_end_marker)
    new_block = (
        '// ---------- 4. Subtitles: 2026-05-30 完全削除方針 ----------\n'
        '// 理由: edge-tts 固有名詞読み違え + 均等分割で同期不能。字幕焼き込み無し。\n'
        '// 視聴体験は「ナレーション + ken-burns 画像」に集中。'
    )
    text = text[:ass_start] + new_block + text[ass_end:]
    PATCHES.append('history_v2: ASS subtitles 生成削除')

# 2. 動画 seg ループ削除 → segMp4s そのまま concat
loop_start_marker = 'let totalSec = 0;\nconst concatVidList = [];'
loop_end_marker = 'log(`concatenating ${concatVidList.length} segments'
i = text.find(loop_start_marker)
if i >= 0:
    j = text.find('}', text.find('break;\n  }', i)) + 1
    # j まで含めて削除 (while ブロックの閉じ })
    # ただ可読性のため別アプローチ: 行単位で書き換え
    pass  # 別ロジック以下で

# 2-alt: 安全策として正規表現で while ブロック全体を置換
loop_pattern = re.compile(
    r'let totalSec = 0;\s*\n'
    r'const concatVidList = \[\];\s*\n'
    r'let idx = 0;\s*\n'
    r'while \(totalSec < audioDur \+ 5\) \{\s*\n'
    r'\s*concatVidList\.push\(segMp4s\[idx % segMp4s\.length\]\);\s*\n'
    r'\s*totalSec \+= segSec;\s*\n'
    r'\s*idx\+\+;\s*\n'
    r'\s*if \(idx > 200\) break;\s*\n'
    r'\}',
    re.MULTILINE
)
new_loop = (
    '// 2026-05-30: 動画 seg ループ削除 (seg_0 が末尾に重複する温床だった)。\n'
    'const concatVidList = [...segMp4s];\n'
    'const totalSec = segMp4s.length * segSec;'
)
text2, n = loop_pattern.subn(new_loop, text)
if n > 0:
    text = text2
    PATCHES.append(f'history_v2: 動画 seg ループ削除 ({n} 箇所)')

# 3. subtitles=sub.ass filter を削除
text3, n = re.subn(
    r'-vf "subtitles=sub\.ass:fontsdir=/usr/share/fonts" ',
    '',
    text
)
if n > 0:
    text = text3
    PATCHES.append(f'history_v2: subtitles filter 削除 ({n} 箇所)')

hist.write_text(text, encoding='utf-8')

# =====================================================================
# psych_v2/pipeline.mjs
# =====================================================================
psych = ROOT / 'youtube' / 'psych_v2' / 'pipeline.mjs'
text = psych.read_text(encoding='utf-8')

# 1. ASS subtitles 生成削除 (psych は "// ===== 4. Build ASS subtitles =====" 相当)
ass_start_markers = [
    '// =====================================================================\n// 4. Build ASS subtitles',
    '// ====== 4. Build ASS subtitles ======',
    '// 4. Build ASS subtitles',
]
ass_start = -1
for m in ass_start_markers:
    ass_start = text.find(m)
    if ass_start >= 0:
        break

if ass_start >= 0:
    ass_end_marker = "fs.writeFileSync(assPath, assText, 'utf8');"
    ass_end = text.find(ass_end_marker, ass_start)
    if ass_end >= 0:
        ass_end += len(ass_end_marker)
        new_block = (
            '// =====================================================================\n'
            '// 4. Subtitles: 2026-05-30 完全削除方針\n'
            '// =====================================================================\n'
            '// 理由: edge-tts 固有名詞読み違え + 均等分割で同期不能。字幕焼き込み無し。'
        )
        text = text[:ass_start] + new_block + text[ass_end:]
        PATCHES.append('psych_v2: ASS subtitles 生成削除')

# 2. subtitles=sub.ass filter を削除
text2, n = re.subn(
    r'-vf "subtitles=sub\.ass:fontsdir=/usr/share/fonts" ',
    '',
    text
)
if n > 0:
    text = text2
    PATCHES.append(f'psych_v2: subtitles filter 削除 ({n} 箇所)')

psych.write_text(text, encoding='utf-8')

# =====================================================================
# 他 pipeline (shorts 系)
# =====================================================================
shorts_files = [
    'youtube/history_shorts_v2/pipeline.mjs',
    'youtube/otona_shorts_v2/pipeline.mjs',
    'youtube/shorts_v2/pipeline.mjs',
    'youtube/psych_shorts_v2/pipeline.mjs',
]
for rel in shorts_files:
    p = ROOT / rel
    if not p.exists():
        continue
    s = p.read_text(encoding='utf-8')
    # subtitles=sub.ass を含む -vf filter 削除 (ある場合)
    s2, n = re.subn(
        r'-vf "subtitles=sub\.ass[^"]*" ',
        '',
        s
    )
    s3, n3 = re.subn(
        r'-vf "subtitles=[^"]+\.ass[^"]*" ',
        '',
        s2
    )
    if n > 0 or n3 > 0:
        p.write_text(s3, encoding='utf-8')
        PATCHES.append(f'{rel}: subtitles filter 削除 ({n + n3} 箇所)')

# =====================================================================
print('=' * 60)
print('修正結果')
print('=' * 60)
for line in PATCHES:
    print(f'  - {line}')
print(f'\n計 {len(PATCHES)} 件適用')
