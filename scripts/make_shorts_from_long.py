#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
make_shorts_from_long.py
========================
ロング動画 (1920x1080, 30 分等) から intro/peak/outro の 3 ショート (1080x1920) を機械切り出し。
Gemini / edge-tts / whisper の追加コスト ZERO。

入力 (kind=history の例):
  youtube/history_v2/.work/<idx>/output.mp4    ロング動画
  youtube/history_v2/audio/<idx>.mp3           音声
  youtube/history_v2/audio/<idx>.srt           refine 済字幕
  youtube/history_v2/scripts/long_<idx>.json   メタ

出力:
  youtube/history_shorts_v2/.work/<idx>_<seg>/output.mp4
  youtube/history_shorts_v2/scripts/short_<idx>_<seg>.json

Usage:
  python scripts/make_shorts_from_long.py --kind history --index 009
  python scripts/make_shorts_from_long.py --kind psych --index 004 --segments intro,peak
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(r'C:\Users\user\Documents\10oku-project')

KIND_CFG = {
    'history': {
        'long_dir':    ROOT / 'youtube' / 'history_v2',
        'shorts_dir':  ROOT / 'youtube' / 'history_shorts_v2',
        'long_prefix': 'long_',
    },
    'psych': {
        'long_dir':    ROOT / 'youtube' / 'psych_v2',
        'shorts_dir':  ROOT / 'youtube' / 'psych_shorts_v2',
        'long_prefix': 'psych_',
    },
}

# peak スコアリング用感情語
EMO_KEYWORDS = set([
    '愛', '死', '血', '涙', '哀', '怒', '喜', '悲', '怖', '嫉妬',
    '別れ', '失恋', '戦', '滅', '勝利', '敗北', '絶望', '希望', '復活',
    '裏切', '信頼', '秘密', '真実', '感動', '衝撃', '驚愕', '運命', '宿命',
])

# ASS テンプレート (shorts_v2/pipeline.mjs L127-140 流用)
ASS_HEADER = """[Script Info]
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Yu Gothic,68,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

SRT_TIME_RE = re.compile(r'(\d+):(\d+):(\d+)[,\.](\d+)')


def parse_srt_time(s):
    m = SRT_TIME_RE.match(s.strip())
    if not m:
        return None
    h, mi, se, ms = map(int, m.groups())
    return h * 3600 + mi * 60 + se + ms / 1000


def parse_srt(srt_path):
    """SRT を [(start_sec, end_sec, text)] に変換"""
    if not srt_path.exists() or srt_path.stat().st_size == 0:
        return []
    text = srt_path.read_text(encoding='utf-8', errors='replace')
    cues = []
    blocks = re.split(r'\n\s*\n', text.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        time_line = lines[1]
        if '-->' not in time_line:
            continue
        start_s, end_s = time_line.split('-->')
        s = parse_srt_time(start_s)
        e = parse_srt_time(end_s)
        if s is None or e is None:
            continue
        txt = '\n'.join(lines[2:]).strip()
        if txt:
            cues.append((s, e, txt))
    return cues


def cues_in_range(cues, t0, t1):
    """t0-t1 秒の範囲に含まれる cue を抽出 (時刻を -t0 シフト)"""
    out = []
    for s, e, txt in cues:
        if e <= t0 or s >= t1:
            continue
        cs = max(0.0, s - t0)
        ce = min(t1 - t0, e - t0)
        if ce > cs:
            out.append((cs, ce, txt))
    return out


def pick_intro(cues, duration):
    return (0.0, min(60.0, duration))


def pick_outro(cues, duration):
    return (max(0.0, duration - 60.0), duration)


def pick_peak(cues, duration, keywords):
    """60s 窓を 5s スライドで探索、スコア最大の区間を返す"""
    if duration < 180:
        center = duration / 2
        return (max(0.0, center - 30), min(duration, center + 30))

    kw = set()
    for k in keywords:
        for ch in re.findall(r'[一-龥]{2,}', str(k)):
            kw.add(ch)
    kw |= EMO_KEYWORDS

    best_score = -1.0
    best_range = (60.0, 120.0)
    for t0 in range(60, int(duration) - 60, 5):
        t1 = t0 + 60
        cs = cues_in_range(cues, t0, t1)
        score = 0.0
        for s, e, txt in cs:
            cue_dur = e - s
            hit = sum(1 for k in kw if k in txt)
            hit += txt.count('!') + txt.count('?') + txt.count('!') + txt.count('?')
            score += cue_dur * (1 + hit)
        if score > best_score:
            best_score = score
            best_range = (float(t0), float(t1))
    return best_range


def ass_time(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def cues_to_ass(cues_segment, out_path):
    ass = ASS_HEADER
    for cs, ce, txt in cues_segment:
        safe = re.sub(r'[\\{}]', '', txt).replace('\n', '\\N')
        ass += f"Dialogue: 0,{ass_time(cs)},{ass_time(ce)},Default,,0,0,0,,{safe}\n"
    out_path.write_text(ass, encoding='utf-8')


def ass_filter_path(p):
    """ffmpeg subtitles= フィルタ用にパスをエスケープ"""
    s = str(p).replace('\\', '/').replace(':', '\\:')
    return s


def ffmpeg_extract_vertical(long_mp4, mp3, t0, t1, ass, out_mp4):
    dur = t1 - t0
    vf = (
        f"scale=2400:4400:force_original_aspect_ratio=increase,"
        f"crop=2160:3840,"
        f"zoompan=z='min(1+0.0006*on,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(dur * 30)}:s=1080x1920:fps=30,"
        f"setsar=1,"
        f"subtitles='{ass_filter_path(ass)}'"
    )
    cmd = [
        'ffmpeg', '-y',
        '-ss', f'{t0:.3f}', '-to', f'{t1:.3f}', '-i', str(long_mp4),
        '-ss', f'{t0:.3f}', '-to', f'{t1:.3f}', '-i', str(mp3),
        '-vf', vf,
        '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest',
        str(out_mp4),
    ]
    print(f'[make_shorts] ffmpeg cut={t0:.1f}-{t1:.1f}s dur={dur:.1f}s -> {out_mp4.name}', flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        print(f'[make_shorts] FFMPEG FAIL rc={r.returncode}')
        print((r.stderr or '')[-800:])
        return False
    if not out_mp4.exists() or out_mp4.stat().st_size < 100000:
        print(f'[make_shorts] output suspiciously small: {out_mp4.stat().st_size if out_mp4.exists() else "missing"}')
        return False
    return True


def write_meta(long_spec, idx, segment, t0, t1, out_path):
    seg_label = {'intro': '導入', 'peak': '感動', 'outro': '結末'}.get(segment, segment)
    base_title = long_spec.get('title', f'{idx}')[:75]
    short_title = f'{base_title} #Shorts {seg_label}'[:95]
    base_desc = long_spec.get('description', '')
    desc = f"{base_desc}\n\n#Shorts #{seg_label}"[:4500]
    tags = list(long_spec.get('tags', [])) + ['Shorts', seg_label]
    out_path.write_text(json.dumps({
        'title':            short_title,
        'description':      desc,
        'tags':             tags[:15],
        'source_idx':       idx,
        'segment':          segment,
        'source_range_sec': [t0, t1],
    }, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', choices=list(KIND_CFG.keys()), required=True)
    ap.add_argument('--index', required=True, help='3 digit idx, e.g. 009')
    ap.add_argument('--segments', default='intro,peak,outro')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    if not re.match(r'^\d{3}$', args.index):
        print(f'invalid index: {args.index}', file=sys.stderr)
        sys.exit(2)

    cfg = KIND_CFG[args.kind]
    idx = args.index
    long_mp4  = cfg['long_dir'] / '.work' / idx / 'output.mp4'
    mp3       = cfg['long_dir'] / 'audio' / f'{idx}.mp3'
    srt       = cfg['long_dir'] / 'audio' / f'{idx}.srt'
    spec_path = cfg['long_dir'] / 'scripts' / f"{cfg['long_prefix']}{idx}.json"

    if not long_mp4.exists():
        print(f'[make_shorts] SKIP: long mp4 missing: {long_mp4}')
        sys.exit(0)
    if not mp3.exists():
        print(f'[make_shorts] SKIP: mp3 missing: {mp3}')
        sys.exit(0)
    if not srt.exists() or srt.stat().st_size == 0:
        print(f'[make_shorts] SKIP: srt missing/empty: {srt}')
        sys.exit(0)

    long_spec = {}
    if spec_path.exists():
        try:
            long_spec = json.loads(spec_path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'[make_shorts] WARN: spec parse fail: {e}')

    cues = parse_srt(srt)
    if not cues:
        print('[make_shorts] SKIP: no cues parsed from srt')
        sys.exit(0)

    # duration
    r = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(long_mp4)],
        capture_output=True, text=True,
    )
    try:
        duration = float((r.stdout or '').strip())
    except Exception:
        print(f'[make_shorts] FAIL: bad duration probe: {r.stdout!r}')
        sys.exit(1)
    if duration < 60:
        print(f'[make_shorts] SKIP: long video too short ({duration:.1f}s)')
        sys.exit(0)

    keywords = [long_spec.get('title', '')] + list(long_spec.get('tags', []))

    segments = [s.strip() for s in args.segments.split(',') if s.strip()]
    pickers = {
        'intro': lambda: pick_intro(cues, duration),
        'peak':  lambda: pick_peak(cues, duration, keywords),
        'outro': lambda: pick_outro(cues, duration),
    }

    work_root    = cfg['shorts_dir'] / '.work'
    scripts_root = cfg['shorts_dir'] / 'scripts'
    work_root.mkdir(parents=True, exist_ok=True)
    scripts_root.mkdir(parents=True, exist_ok=True)

    success = 0
    for seg in segments:
        if seg not in pickers:
            print(f'[make_shorts] unknown segment: {seg}, skip')
            continue
        t0, t1 = pickers[seg]()
        if t1 - t0 < 15:
            print(f'[make_shorts] {seg}: range too short ({t1 - t0:.1f}s), skip')
            continue
        if t1 - t0 > 58:
            t1 = t0 + 58

        seg_dir = work_root / f'{idx}_{seg}'
        seg_dir.mkdir(exist_ok=True)
        out_mp4 = seg_dir / 'output.mp4'

        if out_mp4.exists() and out_mp4.stat().st_size > 100000 and not args.force:
            print(f'[make_shorts] {seg}: already built, skip')
            success += 1
            continue

        ass_path = seg_dir / 'sub.ass'
        cues_seg = cues_in_range(cues, t0, t1)
        cues_to_ass(cues_seg, ass_path)

        if ffmpeg_extract_vertical(long_mp4, mp3, t0, t1, ass_path, out_mp4):
            success += 1
            spec_out = scripts_root / f'short_{idx}_{seg}.json'
            write_meta(long_spec, idx, seg, t0, t1, spec_out)
            print(f'[make_shorts] {seg}: OK -> {out_mp4}')
        else:
            print(f'[make_shorts] {seg}: FAIL')

    print(f'[make_shorts] DONE {args.kind}/{idx}: {success}/{len(segments)}')
    sys.exit(0 if success > 0 else 1)


if __name__ == '__main__':
    main()
