#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全 uploaded 動画の video/audio duration 同期確認。
問題: video > audio + 60s = ナレーション途切れ、視聴体験崩壊。
"""
import json, subprocess, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')

PIPELINES = [
    # (label, work_dir,                audio_dir,                upload_json)
    ('history_v2',  'history_v2/.work',  'history_v2/audio',  'history_v2/uploaded.json'),
    ('psych_v2',    'psych_v2/.work',    'psych_v2/audio',    'psych_v2/uploaded.json'),
    ('audio_drama', 'audio_drama/.work', None,                'audio_drama/uploaded.json'),
    ('history_shorts_v2', 'history_shorts_v2/.work', None,    'history_shorts_v2/uploaded.json'),
    ('shorts_v2', 'shorts_v2/.work', None,                    'shorts_v2/uploaded.json'),
    ('psych_shorts_v2', 'psych_shorts_v2/.work', None,        'psych_shorts_v2/uploaded.json'),
    ('otona_shorts_v2', 'otona_shorts_v2/.work', None,        'otona_shorts_v2/uploaded.json'),
]


def get_duration(p):
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
            capture_output=True, text=True, timeout=30
        )
        s = (r.stdout or '').strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0


problems = []
all_results = []

for label, work_dir, audio_dir, upl_file in PIPELINES:
    upl_p = ROOT / 'youtube' / upl_file
    if not upl_p.exists():
        continue
    try:
        upl = json.loads(upl_p.read_text(encoding='utf-8'))
    except Exception:
        continue
    work_p = ROOT / 'youtube' / work_dir
    for idx, info in upl.items():
        # audio_drama は .work/<idx>/output.mp4 だが、別ディレクトリ構造もある
        vid_paths = [
            work_p / idx / 'output.mp4',
            ROOT / 'youtube' / label / idx / 'output.mp4',
            work_p / f'{idx}.mp4',
        ]
        vid = next((p for p in vid_paths if p.exists()), None)
        if not vid:
            continue
        v_dur = get_duration(vid)
        a_dur = 0.0
        if audio_dir:
            aud = ROOT / 'youtube' / audio_dir / f'{idx}.mp3'
            if aud.exists():
                a_dur = get_duration(aud)
        else:
            for cand in [work_p / idx / 'voice.mp3', work_p / idx / 'audio.mp3']:
                if cand.exists():
                    a_dur = get_duration(cand)
                    break
        diff = v_dur - a_dur
        is_shorts = 'shorts' in label
        status = 'OK'
        if is_shorts:
            if v_dur < 14 or v_dur > 62:
                status = f'SHORTS_DUR_BAD_{v_dur:.0f}s'
            elif a_dur > 0 and diff > 5:
                status = f'AUDIO_GAP_{diff:.0f}s'
        else:
            if v_dur < 1700:
                status = f'TOO_SHORT_{v_dur:.0f}s'
            elif a_dur > 0 and diff > 30:
                status = f'AUDIO_GAP_{diff:.0f}s'
        rec = (label, idx, v_dur, a_dur, diff, status, info.get('title', '')[:30], info.get('videoUrl', ''))
        all_results.append(rec)
        if status != 'OK':
            problems.append(rec)

# 全結果
print('=' * 80)
print('全結果')
print('=' * 80)
for r in all_results:
    label, idx, v, a, d, st, t, u = r
    print(f'{label:25s} {idx:8s} v={v:7.1f}s a={a:7.1f}s diff={d:+7.1f}s {st:25s} {t}')

print()
print('=' * 80)
print(f'問題 {len(problems)} 件 / 全 {len(all_results)} 件')
print('=' * 80)
for r in problems:
    label, idx, v, a, d, st, t, u = r
    print(f'  [{st}] {label} {idx}: {t}')
    print(f'    {u}')
