"""
articles/note_*.md をスキャンして 『 鉤括弧の異常多発を検出。
正常な文は『 と 』 がペアで使われる。corrupt は 開き 『 だけ大量挿入されてる。
"""
import re, sys, glob
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path('C:/Users/user/Documents/10oku-project')
ARTICLES = sorted(glob.glob(str(ROOT / 'articles/note_*.md')))

results = []
for fp in ARTICLES:
    p = Path(fp)
    try:
        text = p.read_text(encoding='utf-8')
    except Exception as e:
        continue
    open_count  = text.count('『')
    close_count = text.count('』')
    diff = open_count - close_count
    body_len = len(text)
    # Ratio: how much of body is 『 stretching
    ratio = open_count / max(1, body_len // 100)  # opens per 100 chars
    is_corrupt = (open_count > 30 and diff > 10) or ratio > 4
    results.append({
        'file': p.name,
        'open': open_count,
        'close': close_count,
        'diff': diff,
        'len': body_len,
        'ratio_per100': round(ratio, 2),
        'corrupt': is_corrupt,
    })

# Sort by corruption
corrupt_files = [r for r in results if r['corrupt']]
print(f'Total scanned: {len(results)}')
print(f'Corrupt (open ≫ close OR open ratio >4/100chars): {len(corrupt_files)}')
print()
print('FILE                 OPEN  CLOSE  DIFF  LEN  RATIO  STATUS')
for r in corrupt_files:
    print(f'{r["file"]:20s} {r["open"]:5d} {r["close"]:5d} {r["diff"]:5d} {r["len"]:5d} {r["ratio_per100"]:5.1f}  CORRUPT')

# Save full
import json
out = ROOT / 'scripts/logs/_corrupted_articles_report.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'corrupt_count': len(corrupt_files), 'all': results}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\nReport: {out}')
