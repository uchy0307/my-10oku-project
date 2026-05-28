#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
auto_disk_cleanup.py
====================
ディスク容量の自動確保. 安全な削除のみ.

ルール:
  - 削除して良い: uploaded.json 既存 idx の .work / .work_quarantine 中間ファイル,
                    古いログ, Windows Temp の古いキャッシュ
  - 触らない:    audio/*.mp3 (edge-tts コスト), scripts/*.json (Gemini コスト),
                    stock_images/, .env, settings, queue.json

実行タイミング:
  - daily_cycle.py 冒頭 (毎朝 8:00 タスクスケジューラ)
  - ボタンサーバーの "disk_cleanup" アクション (手動)
  - 緊急時 (Free < 5GB) 自動発火

報告: scripts/messages.json に追記
"""
import sys, os, json, shutil, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
JST = timezone(timedelta(hours=9))

deleted_files = 0
freed_bytes = 0
errors = []

def safe_unlink(p: Path):
    global deleted_files, freed_bytes
    try:
        sz = p.stat().st_size
        p.unlink()
        deleted_files += 1
        freed_bytes += sz
        return True
    except Exception as e:
        errors.append(f'{p}: {e}')
        return False

def safe_rmtree_size(d: Path):
    global deleted_files, freed_bytes
    total = 0
    cnt = 0
    try:
        for root, dirs, files in os.walk(d):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                    cnt += 1
                except: pass
        shutil.rmtree(d, ignore_errors=True)
        deleted_files += cnt
        freed_bytes += total
    except Exception as e:
        errors.append(f'{d}: {e}')

# ───────── 1) uploaded.json 既存 idx の中間ファイル削除 ─────────
for ch in ['history_v2', 'psych_v2', 'shorts_v2', 'otona_shorts_v2']:
    base = ROOT / 'youtube' / ch
    up = base / 'uploaded.json'
    if not up.exists():
        continue
    try:
        uploaded = set(json.loads(up.read_text(encoding='utf-8')).keys())
    except Exception:
        continue
    for sub in ['.work', '.work_quarantine']:
        d = base / sub
        if not d.exists():
            continue
        for idx_dir in d.iterdir():
            if not idx_dir.is_dir() or idx_dir.name not in uploaded:
                continue
            # 中間ファイル削除 (output.mp4, narration, thumbnail, image_*)
            for fname in ['output.mp4', 'narration.mp3', 'narration_padded.mp3',
                          'silence_pad.mp3', 'concat_pad.txt', 'thumbnail.jpg',
                          'subtitles.ass', 'subtitles.srt']:
                p = idx_dir / fname
                if p.exists():
                    safe_unlink(p)
            # image_*.jpg もまとめて
            for p in idx_dir.glob('image_*.jpg'):
                safe_unlink(p)
            # ディレクトリ空ならそのまま (uploaded.json は残してるので参考情報)

# ───────── 2) 古いログ (48時間以上前) ─────────
log_dir = ROOT / 'scripts' / 'logs'
cutoff = time.time() - 48 * 3600
if log_dir.exists():
    for p in log_dir.glob('action_*.log'):
        try:
            if p.stat().st_mtime < cutoff:
                safe_unlink(p)
        except: pass

# ───────── 3) note-auto / youtube_api_review の使い捨て ─────────
disposables = [
    ROOT / 'note-auto' / '_debug_screen.png',
    ROOT / 'note-auto' / '_dom_dump.json',
    ROOT / 'note-auto' / '_add_attach_full.log',
    ROOT / 'note-auto' / '_add_attach_test3.log',
    ROOT / 'note-auto' / '_add_attach_006_014.log',
]
for p in disposables:
    if p.exists():
        safe_unlink(p)

# ───────── 4) Windows Temp の古いファイル (7日以上前) ─────────
import tempfile
temp_dir = Path(tempfile.gettempdir())
temp_cutoff = time.time() - 7 * 24 * 3600
if temp_dir.exists():
    for p in temp_dir.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < temp_cutoff:
                safe_unlink(p)
            elif p.is_dir() and p.name.startswith('npm-') and p.stat().st_mtime < temp_cutoff:
                safe_rmtree_size(p)
        except: pass

# ───────── 結果出力 + messages.json 報告 ─────────
free_gb = shutil.disk_usage('C:').free / 1024 / 1024 / 1024
total_gb = shutil.disk_usage('C:').total / 1024 / 1024 / 1024
freed_mb = freed_bytes / 1024 / 1024
now = datetime.now(JST).isoformat()
ts_unix = int(datetime.now(JST).timestamp())

print(f'[auto_disk_cleanup] deleted_files={deleted_files} freed_MB={freed_mb:.1f}')
print(f'[auto_disk_cleanup] free_GB={free_gb:.2f} / total_GB={total_gb:.2f}')
if errors:
    print(f'[auto_disk_cleanup] errors={len(errors)}')

# messages.json に簡潔報告 (Free < 10GB の時のみ警告レベル)
try:
    mp = ROOT / 'scripts' / 'messages.json'
    if mp.exists():
        msgs = json.loads(mp.read_text(encoding='utf-8'))
    else:
        msgs = []
    title = f'🧹 ディスク掃除 (空き {free_gb:.1f}GB)'
    if free_gb < 5:
        title = f'⚠ ディスク危険 (空き {free_gb:.1f}GB のみ)'
    msgs.insert(0, {
        'id': f'msg_diskcleanup_{ts_unix}',
        'ts': now,
        'title': title,
        'text': f'削除: {deleted_files} 件, 解放: {freed_mb:.1f} MB\n空き: {free_gb:.2f} GB / {total_gb:.2f} GB\nerrors: {len(errors)}',
        'type': 'claude_to_user',
        'read': False,
    })
    mp.write_text(json.dumps(msgs[:200], ensure_ascii=False, indent=2), encoding='utf-8')
except Exception as e:
    print(f'[auto_disk_cleanup] messages.json write fail: {e}')
