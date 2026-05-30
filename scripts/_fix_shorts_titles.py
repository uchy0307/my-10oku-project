#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""YT ショート 10 本の文字化け title 緊急修正 (2026-05-30、 Task #41)。

原因: archive_to_shorts.py の yt-dlp --print 出力が Windows console cp932 で
受信 → script JSON に化け書き込み → upload_shorts.mjs がそのまま YT 送信。

対策: source_video_id から yt-dlp 再取得 (utf-8 強制 + PYTHONIOENCODING)
→ script JSON + uploaded.json 上書き → videos.update で YT 上 title 修正
"""
import json, os, subprocess, sys, time
from pathlib import Path

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent

# .env load
env_path = ROOT / '.env'
if env_path.exists():
    for line in env_path.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


TARGETS = [
    # history (samurai oauth)
    {'kind': 'history_shorts', 'idx': 'archive_QYKdjDxSIyM_peak',  'video_id': 'j0SX5B_4hBY',  'source_vid': 'QYKdjDxSIyM',  'seg': 'peak'},
    {'kind': 'history_shorts', 'idx': 'archive_nyJtZDUqjRI_peak',  'video_id': 'efBpnnMy-FI',  'source_vid': 'nyJtZDUqjRI',  'seg': 'peak'},
    {'kind': 'history_shorts', 'idx': 'archive_qDI1lCGxRsg_peak',  'video_id': '3liWDn647Aw',  'source_vid': 'qDI1lCGxRsg',  'seg': 'peak'},
    {'kind': 'history_shorts', 'idx': 'archive_fJSZD7HIlvM_intro', 'video_id': '7ud2kP1-TT8',  'source_vid': 'fJSZD7HIlvM', 'seg': 'intro'},
    {'kind': 'history_shorts', 'idx': 'archive_fJSZD7HIlvM_outro', 'video_id': 'cIGLyl5nRGc',  'source_vid': 'fJSZD7HIlvM', 'seg': 'outro'},
    # psych (otona oauth)
    {'kind': 'psych_shorts', 'idx': 'archive_CCgFjnDlxvM_peak',   'video_id': 'DFvfLRpA3CM',  'source_vid': 'CCgFjnDlxvM',  'seg': 'peak'},
    {'kind': 'psych_shorts', 'idx': 'archive_LAVSg_jvnkY_peak',   'video_id': 'SBPFvMvtemk',  'source_vid': 'LAVSg_jvnkY',  'seg': 'peak'},
    {'kind': 'psych_shorts', 'idx': 'archive_OdK_Z-qOWOY_peak',   'video_id': 'O4RcWdYImuc',  'source_vid': 'OdK_Z-qOWOY',  'seg': 'peak'},
    {'kind': 'psych_shorts', 'idx': 'archive_-mDkSwQDiMI_intro',  'video_id': 'UQQC6Pwo26U',  'source_vid': '-mDkSwQDiMI', 'seg': 'intro'},
    {'kind': 'psych_shorts', 'idx': 'archive_-mDkSwQDiMI_outro',  'video_id': '3GmXEJeNL10',  'source_vid': '-mDkSwQDiMI', 'seg': 'outro'},
]

SEG_LABEL = {'intro': '導入', 'peak': '感動', 'outro': '結末'}


def get_yt_title(video_id: str) -> str:
    """yt-dlp で UTF-8 strict で title 取得 (PYTHONIOENCODING + --encoding utf-8 で確実化)"""
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    args = [
        sys.executable, '-m', 'yt_dlp',
        '--encoding', 'utf-8',
        '--skip-download',
        '--print', '%(title)s',
        '--no-warnings',
        f'https://www.youtube.com/watch?v={video_id}',
    ]
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           env=env, timeout=60)
        title = (r.stdout or '').strip().split('\n')[-1].strip()
        return title
    except Exception as e:
        print(f'  [WARN] yt-dlp fail for {video_id}: {e}', file=sys.stderr)
        return ''


def update_yt_video(video_id: str, new_title: str, new_desc: str, new_tags: list, category_id: str, kind: str) -> bool:
    """videos.update で YT 上 title 修正 (force-ssl scope)"""
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    client_id = os.environ.get('YOUTUBE_CLIENT_ID')
    client_secret = os.environ.get('YOUTUBE_CLIENT_SECRET')
    if kind == 'history_shorts':
        refresh_token = os.environ.get('YOUTUBE_REFRESH_TOKEN')
    else:
        refresh_token = os.environ.get('OTONA_YOUTUBE_REFRESH_TOKEN') or os.environ.get('YOUTUBE_REFRESH_TOKEN')
    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError('OAuth credentials missing in .env')
    creds = Credentials(
        token=None, refresh_token=refresh_token,
        client_id=client_id, client_secret=client_secret,
        token_uri='https://oauth2.googleapis.com/token',
        scopes=['https://www.googleapis.com/auth/youtube.force-ssl'],
    )
    yt = build('youtube', 'v3', credentials=creds)
    try:
        yt.videos().update(
            part='snippet',
            body={
                'id': video_id,
                'snippet': {
                    'title': new_title[:100],
                    'description': new_desc,
                    'tags': new_tags,
                    'categoryId': category_id,
                    'defaultLanguage': 'ja',
                    'defaultAudioLanguage': 'ja',
                },
            },
        ).execute()
        return True
    except Exception as e:
        print(f'  [FAIL] videos.update {video_id}: {e}', file=sys.stderr)
        return False


def is_broken(s: str) -> bool:
    if not s or len(s) < 3:
        return True
    return '�' in s or any(0x80 <= ord(c) <= 0xa0 for c in s[:30])


def main():
    ok, fail = 0, 0
    for t in TARGETS:
        kind = t['kind']
        vid = t['video_id']
        source_vid = t['source_vid']
        seg = t['seg']
        print(f"\n=== {vid} (source={source_vid}, seg={seg}, kind={kind}) ===")

        # 1. 正しい title 取得
        source_title = get_yt_title(source_vid)
        if not source_title or is_broken(source_title):
            print(f"  [SKIP] source title broken/empty: {source_title!r}")
            fail += 1
            continue
        print(f"  source title: {source_title}")
        seg_label = SEG_LABEL.get(seg, seg)
        new_title = f"{source_title[:75]} #Shorts {seg_label}"[:95]
        print(f"  new short title: {new_title}")

        # 2. script JSON 上書き
        kind_v2 = f'{kind}_v2'
        script_path = ROOT / 'youtube' / kind_v2 / 'scripts' / f"short_{t['idx']}.json"
        if script_path.exists():
            try:
                data = json.loads(script_path.read_text(encoding='utf-8'))
            except Exception:
                data = {}
            data['title'] = new_title
            data['source_title'] = source_title
            data['description'] = f'過去動画より切り出し #Shorts #{seg_label}'
            data['tags'] = ['Shorts', seg_label] + (['日本史', '歴史', '侍'] if kind == 'history_shorts' else ['心理学', '大人'])
            script_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"  [1/3] script JSON updated: {script_path.name}")

        # 3. uploaded.json 上書き
        uploaded_path = ROOT / 'youtube' / kind_v2 / 'uploaded.json'
        if uploaded_path.exists():
            try:
                udb = json.loads(uploaded_path.read_text(encoding='utf-8'))
            except Exception:
                udb = {}
            if t['idx'] in udb:
                udb[t['idx']]['title'] = new_title
                uploaded_path.write_text(json.dumps(udb, ensure_ascii=False, indent=2), encoding='utf-8')
                print(f"  [2/3] uploaded.json updated")

        # 4. videos.update で YT 上 title 修正 (failure tolerant)
        category_id = '22' if kind == 'history_shorts' else '27'
        tags = ['Shorts', seg_label] + (['日本史', '歴史', '侍'] if kind == 'history_shorts' else ['心理学', '大人'])
        try:
            if update_yt_video(vid, new_title, f'過去動画より切り出し #Shorts #{seg_label}', tags, category_id, kind):
                print(f"  [3/3] ✓ YT title updated → https://youtube.com/shorts/{vid}")
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  [3/3 SKIP] YT update failed (will retry with mjs): {e}")
            fail += 1
        time.sleep(2)

    print(f"\n=== Done: ok={ok} fail={fail} ===")


if __name__ == '__main__':
    main()
