#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
archive_to_shorts.py
====================
過去の YouTube 投稿動画 (samurai/otona) を yt-dlp で DL → ロング MP4 + ja 字幕取得
→ make_shorts_from_long のロジックで intro/peak/outro ショート切り出し
→ youtube/<kind>_shorts_v2/.work/archive_<vid>_<seg>/output.mp4

依存:
  pip install yt-dlp  (済)
  openai-whisper       (字幕欠落時の fallback、ローカル GPU/CPU)
  ffmpeg (PATH)

Usage:
  # 単一 video ID
  python scripts/archive_to_shorts.py --kind history --video-id fJSZD7HIlvM

  # チャンネル全体 (上限 5 本)
  python scripts/archive_to_shorts.py --kind history --limit 5

  # peak のみ
  python scripts/archive_to_shorts.py --kind history --limit 10 --segments peak
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# make_shorts_from_long のロジック再利用
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_shorts_from_long import (
    parse_srt, cues_in_range,
    pick_intro, pick_peak, pick_outro,
    cues_to_ass, ffmpeg_extract_vertical,
)

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')
TMP_DIR = ROOT / '.archive_dl'  # 一時 DL 先

KIND_CFG = {
    'history': {
        'shorts_dir':     ROOT / 'youtube' / 'history_shorts_v2',
        'channel_handle': '@Japanese.Samurai.Channel',
        'category_id':    '22',
    },
    'psych': {
        'shorts_dir':     ROOT / 'youtube' / 'psych_shorts_v2',
        'channel_handle': '@Otona_Psychology',
        'category_id':    '27',
    },
}


def yt_dlp_run(args, capture=True):
    # 2026-05-30 (Task #41): UTF-8 強制で Windows cp932 化け再発防止
    # PYTHONIOENCODING + PYTHONUTF8 + --encoding utf-8 の三段重ね
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    # --encoding utf-8 を既存 args に必ず先頭追加 (既存だと yt-dlp が重複拒否しない)
    cmd = [sys.executable, '-m', 'yt_dlp', '--encoding', 'utf-8'] + args
    return subprocess.run(cmd, capture_output=capture, text=True, encoding='utf-8', errors='replace', env=env)


def fetch_uploads(channel_handle, limit=10):
    """チャンネルから video ID + title リストを取得 (新しい順)"""
    out_dir = TMP_DIR / '_listing'
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f'https://www.youtube.com/{channel_handle}/videos'
    args = [
        '--flat-playlist',
        '--playlist-end', str(limit),
        '--print', '%(id)s|%(title)s|%(duration)s',
        '--no-warnings',
        url,
    ]
    r = yt_dlp_run(args)
    if r.returncode != 0:
        print(f'[archive] channel scan FAIL: {(r.stderr or "")[-500:]}', flush=True)
        return []
    result = []
    for line in (r.stdout or '').splitlines():
        parts = line.strip().split('|', 2)
        if len(parts) < 2 or not parts[0]:
            continue
        vid = parts[0]
        title = parts[1] if len(parts) > 1 else ''
        try:
            dur = float(parts[2]) if len(parts) > 2 and parts[2] not in ('', 'None') else 0
        except ValueError:
            dur = 0
        # ショート (60s 以下) は除外 (素材は長尺だけ)
        if 0 < dur < 90:
            continue
        result.append({'video_id': vid, 'title': title, 'duration': dur})
    return result


def download_video(video_id, out_dir):
    """video ID の動画 + 日本語字幕 (auto-sub fallback) を DL"""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tpl = str(out_dir / f'{video_id}.%(ext)s')
    args = [
        '-o', out_tpl,
        '-f', 'best[ext=mp4]/best',
        '--write-subs',
        '--sub-langs', 'ja,ja-orig',
        '--write-auto-subs',
        '--convert-subs', 'srt',
        '--no-warnings',
        f'https://www.youtube.com/watch?v={video_id}',
    ]
    r = yt_dlp_run(args, capture=True)
    if r.returncode != 0:
        print(f'[archive] DL FAIL {video_id}: {(r.stderr or "")[-400:]}', flush=True)
        return None, None

    mp4_candidates = list(out_dir.glob(f'{video_id}.mp4')) + \
                     list(out_dir.glob(f'{video_id}.*.mp4'))
    mp4 = mp4_candidates[0] if mp4_candidates else None
    if not mp4 or not mp4.exists() or mp4.stat().st_size < 1_000_000:
        print(f'[archive] {video_id}: mp4 missing or too small', flush=True)
        return None, None

    srt_candidates = list(out_dir.glob(f'{video_id}*.ja*.srt')) + \
                     list(out_dir.glob(f'{video_id}*.srt'))
    srt = next((p for p in srt_candidates if p.stat().st_size > 100), None)
    return mp4, srt


def whisper_fallback(mp4):
    """字幕が無い時 ffmpeg で mp3 抽出 → whisper_subtitle_gen.py 呼出"""
    mp3 = mp4.with_suffix('.mp3')
    if not mp3.exists():
        r = subprocess.run([
            'ffmpeg', '-y', '-i', str(mp4),
            '-vn', '-acodec', 'libmp3lame', '-b:a', '128k', str(mp3)
        ], capture_output=True, text=True)
        if r.returncode != 0:
            return None
    r = subprocess.run([
        sys.executable, str(ROOT / 'scripts' / 'whisper_subtitle_gen.py'),
        '--audio', str(mp3), '--model', 'tiny'
    ], capture_output=True, text=True, encoding='utf-8', errors='replace')
    srt = mp3.with_suffix('.srt')
    return srt if srt.exists() and srt.stat().st_size > 100 else None


def probe_duration(mp4):
    r = subprocess.run([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(mp4)
    ], capture_output=True, text=True)
    try:
        return float((r.stdout or '').strip())
    except Exception:
        return 0.0


def process_video(kind, video_meta, segments, force, uploaded_db):
    cfg = KIND_CFG[kind]
    vid = video_meta['video_id']
    title = video_meta['title']

    # 既出 skip
    if not force and any(k.startswith(f'archive_{vid}_') for k in uploaded_db):
        print(f'[archive] {vid}: already uploaded, skip', flush=True)
        return 0

    # 全 seg 完成済なら skip
    shorts_dir = cfg['shorts_dir']
    work_root = shorts_dir / '.work'
    work_root.mkdir(parents=True, exist_ok=True)
    if not force and all(
        (work_root / f'archive_{vid}_{s}' / 'output.mp4').exists() and
        (work_root / f'archive_{vid}_{s}' / 'output.mp4').stat().st_size > 100_000
        for s in segments
    ):
        print(f'[archive] {vid}: all segments built, skip', flush=True)
        return 0

    print(f'[archive] processing {vid}: {title[:60]}', flush=True)

    tmp = TMP_DIR / vid
    mp4, srt = download_video(vid, tmp)
    if not mp4:
        return 0
    if not srt:
        print(f'[archive] {vid}: no subtitle, trying whisper fallback...', flush=True)
        srt = whisper_fallback(mp4)
        if not srt:
            print(f'[archive] {vid}: whisper fallback failed, skip', flush=True)
            return 0

    cues = parse_srt(srt)
    if not cues:
        print(f'[archive] {vid}: srt parsed 0 cues, skip', flush=True)
        return 0

    duration = probe_duration(mp4)
    if duration < 60:
        print(f'[archive] {vid}: video too short ({duration:.1f}s), skip', flush=True)
        return 0

    keywords = [title]
    pickers = {
        'intro': lambda: pick_intro(cues, duration),
        'peak':  lambda: pick_peak(cues, duration, keywords),
        'outro': lambda: pick_outro(cues, duration),
    }

    scripts_root = shorts_dir / 'scripts'
    scripts_root.mkdir(parents=True, exist_ok=True)

    made = 0
    for seg in segments:
        if seg not in pickers:
            continue
        t0, t1 = pickers[seg]()
        if t1 - t0 < 15:
            continue
        if t1 - t0 > 58:
            t1 = t0 + 58

        seg_dir = work_root / f'archive_{vid}_{seg}'
        seg_dir.mkdir(exist_ok=True)
        out_mp4 = seg_dir / 'output.mp4'
        if out_mp4.exists() and out_mp4.stat().st_size > 100_000 and not force:
            print(f'[archive] {vid}/{seg}: already built, skip', flush=True)
            made += 1
            continue

        ass_path = seg_dir / 'sub.ass'
        cues_seg = cues_in_range(cues, t0, t1)
        cues_to_ass(cues_seg, ass_path)

        # video src と audio src 両方同じ mp4
        if ffmpeg_extract_vertical(mp4, mp4, t0, t1, ass_path, out_mp4):
            made += 1
            seg_label = {'intro': '導入', 'peak': '感動', 'outro': '結末'}.get(seg, seg)
            short_title = f'{title[:75]} #Shorts {seg_label}'[:95]
            spec_out = scripts_root / f'short_archive_{vid}_{seg}.json'
            spec_out.write_text(json.dumps({
                'title':            short_title,
                'description':      f'過去動画より切り出し #Shorts #{seg_label}',
                'tags':             ['Shorts', seg_label] + (['日本史', '歴史', '侍'] if kind == 'history' else ['心理学', '大人']),
                'source_video_id':  vid,
                'source_title':     title,
                'segment':          seg,
                'source_range_sec': [t0, t1],
            }, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'[archive] {vid}/{seg}: OK -> {out_mp4}', flush=True)

    # 一時 DL クリーンアップ
    try:
        for f in tmp.iterdir():
            f.unlink()
        tmp.rmdir()
    except Exception:
        pass

    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', choices=list(KIND_CFG.keys()), required=True)
    ap.add_argument('--video-id', help='single video ID (mutually exclusive with --limit)')
    ap.add_argument('--limit', type=int, default=5, help='max videos to process from channel uploads')
    ap.add_argument('--segments', default='peak', help='intro,peak,outro (default: peak only for quality)')
    ap.add_argument('--force', action='store_true', help='re-process even if already built')
    args = ap.parse_args()

    cfg = KIND_CFG[args.kind]
    segments = [s.strip() for s in args.segments.split(',') if s.strip()]

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    uploaded_json = cfg['shorts_dir'] / 'uploaded.json'
    uploaded_db = {}
    if uploaded_json.exists():
        try:
            uploaded_db = json.loads(uploaded_json.read_text(encoding='utf-8')) or {}
        except Exception:
            pass

    if args.video_id:
        videos = [{'video_id': args.video_id, 'title': '', 'duration': 0}]
    else:
        videos = fetch_uploads(cfg['channel_handle'], limit=args.limit)
        print(f'[archive] channel={cfg["channel_handle"]} found={len(videos)}', flush=True)

    total_made = 0
    for v in videos:
        made = process_video(args.kind, v, segments, args.force, uploaded_db)
        total_made += made

    print(f'[archive] DONE total_segments_built={total_made}', flush=True)
    sys.exit(0 if total_made > 0 else 1)


if __name__ == '__main__':
    main()
