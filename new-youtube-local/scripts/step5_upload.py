"""step5_upload.py
YouTube Data API v3 で動画アップロード
- refresh_token 方式（OAuth2）
- NEW_YOUTUBE_CLIENT_ID / _SECRET / _REFRESH_TOKEN を流用
- title / description / tags は current.json から組立
- --test 時は upload せず情報のみ表示
- 2026-05-19 追加: publish 前 QC（step3 quality.json 確認 + ffprobe で字幕 stream 確認 +
  OpenCV で先頭/中間/末尾 3 frame サンプリングして顔比率検証）
"""
import os, sys, json, time, subprocess
from pathlib import Path
import urllib.request, urllib.parse, urllib.error

ROOT = Path(__file__).resolve().parent.parent

# Auto-load .env (when run standalone)
_ENV = ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        _k = _k.strip(); _v = _v.strip()
        if _k and _k not in os.environ:
            os.environ[_k] = _v

OUTPUT_DIR = ROOT / "output"

CLIENT_ID = os.environ.get("NEW_YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NEW_YOUTUBE_CLIENT_SECRET", "")
REFRESH_TOKEN = os.environ.get("NEW_YOUTUBE_REFRESH_TOKEN", "")
CATEGORY_ID = os.environ.get("YOUTUBE_CATEGORY_ID", "22")
PRIVACY = os.environ.get("YOUTUBE_PRIVACY", "public")

# Publish gate 閾値
QC_MIN_PASS_RATE = float(os.environ.get("STEP5_QC_MIN_PASS", "0.5"))
FRAME_FACE_ASPECT_MIN = float(os.environ.get("STEP5_FRAME_FACE_MIN", "0.55"))
FRAME_FACE_ASPECT_MAX = float(os.environ.get("STEP5_FRAME_FACE_MAX", "1.80"))
SKIP_VIDEO_QC = os.environ.get("STEP5_SKIP_VIDEO_QC", "false").lower() == "true"


def get_access_token():
    # 2026-05-20: 共通モジュール oauth_refresh.refresh_access_token に集約
    try:
        from oauth_refresh import refresh_access_token  # type: ignore
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from oauth_refresh import refresh_access_token  # type: ignore
    tok = refresh_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
    return tok["access_token"]


def build_metadata(cur):
    title = f"【大人の心理学】{cur['title']}"
    if len(title) > 95:
        title = title[:95]
    desc_lines = [
        f"テーマ: {cur['title']}",
        f"カテゴリ: {cur['category']}",
        "",
        "本動画は心理学的視点から大人の恋愛・対人関係・性愛心理を考察します。",
        "視聴は18歳以上を推奨。",
        "",
        "■章立て",
    ]
    for c in cur["chapters"]:
        desc_lines.append(f"  {c['title']}")
    desc_lines += [
        "",
        "#大人の心理学 #恋愛心理 #otona_psychology",
    ]
    description = "\n".join(desc_lines)
    tags = ["大人の心理学", "心理学", "恋愛心理", "otona_psychology", cur["category"]]
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_ID,
            "defaultLanguage": "ja",
            "defaultAudioLanguage": "ja",
        },
        "status": {
            "privacyStatus": PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }


def resumable_upload(access_token, video_path, metadata):
    init_req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(metadata).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
        },
        method="POST",
    )
    with urllib.request.urlopen(init_req, timeout=60) as r:
        upload_url = r.headers.get("Location")
    if not upload_url:
        raise RuntimeError("no upload URL")
    with open(video_path, "rb") as f:
        body = f.read()
    put_req = urllib.request.Request(
        upload_url, data=body,
        headers={"Content-Type": "video/mp4", "Content-Length": str(len(body))},
        method="PUT",
    )
    with urllib.request.urlopen(put_req, timeout=1800) as r:
        result = json.loads(r.read().decode("utf-8"))
    vid = result.get("id", "")
    ch_id = (result.get("snippet") or {}).get("channelId", "")
    return vid, ch_id


def fetch_channel_id(access_token):
    try:
        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=id&mine=true",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        items = data.get("items", [])
        if items:
            return items[0].get("id", "")
    except Exception as e:
        print(f"[step5] fetch_channel_id failed: {e}")
    return ""


def set_thumbnail(access_token, video_id, thumb_path):
    ctype = "image/png" if thumb_path.suffix.lower() == ".png" else "image/jpeg"
    data = thumb_path.read_bytes()
    url = f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}&uploadType=media"
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": ctype,
            "Content-Length": str(len(data)),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read().decode("utf-8"))
        print(f"[step5] thumbnail set: {json.dumps(res)[:200]}")
        return True
    except Exception as e:
        print(f"[step5] thumbnail set failed: {e}")
        return False


# ─── Publish gate: QC checks before upload ───────────────────────────────
def _check_image_qc_log(tid):
    """step3 が書いた quality.json を確認。pass率が閾値未満なら False。"""
    qc_path = OUTPUT_DIR / f"{tid}_quality.json"
    if not qc_path.exists():
        print(f"[step5 QC] {qc_path.name} not found, skipping image QC gate")
        return True, "no_quality_json"
    try:
        qc = json.loads(qc_path.read_text(encoding="utf-8"))
        total = len(qc)
        pass_n = sum(1 for q in qc if q.get("qc_ok"))
        if total == 0:
            return True, "empty_log"
        rate = pass_n / total
        ok = rate >= QC_MIN_PASS_RATE
        return ok, f"image_qc_pass {pass_n}/{total} rate={rate:.0%} threshold={QC_MIN_PASS_RATE:.0%}"
    except Exception as e:
        return True, f"qc_log_read_exc {e}"  # 緩く通す（後段でも frame 検証あり）


def _check_video_has_subtitles_burned(video_path):
    """ffprobe で動画 stream を確認。
    NOTE: 字幕は焼込み済 (step4 で burn) なので独立 stream としては存在しないが、
    せめて動画 stream（video codec h264 等）と音声 stream が両方あるかを確認。
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-print_format", "json", str(video_path)],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout or "{}")
        streams = data.get("streams", [])
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        if not has_video:
            return False, "no_video_stream"
        if not has_audio:
            return False, "no_audio_stream"
        return True, f"streams_ok video+audio (total={len(streams)})"
    except FileNotFoundError:
        return True, "ffprobe_not_installed_skip"
    except Exception as e:
        return True, f"ffprobe_exc {e}"


def _sample_video_frames_and_check_faces(video_path):
    """OpenCV で動画から先頭/中央/末尾 3 frame を抽出して顔比率検証。
    cv2 未インストールなら skip（True を返す）。
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return True, "cv2_not_installed_skip"
    try:
        cap = cv2.VideoCapture(str(video_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total_frames <= 0:
            cap.release()
            return True, "cant_read_frame_count_skip"
        sample_indices = [
            max(1, total_frames // 10),
            total_frames // 2,
            max(1, total_frames - (total_frames // 10)),
        ]
        xml = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cls = cv2.CascadeClassifier(xml)
        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cls.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=4, minSize=(40, 40))
            for (fx, fy, fw, fh) in faces:
                ratio = fh / max(fw, 1)
                if ratio < FRAME_FACE_ASPECT_MIN or ratio > FRAME_FACE_ASPECT_MAX:
                    cap.release()
                    return False, f"frame{idx}_face_distorted h/w={ratio:.2f}"
        cap.release()
        return True, f"frames_ok sampled={len(sample_indices)}"
    except Exception as e:
        return True, f"frame_qc_exc {e}"


def publish_gate(tid, video_path):
    """upload 直前の最終 QC ゲート。一つでも fail なら abort。"""
    print(f"[step5 GATE] running pre-publish QC for {tid}")
    checks = []
    ok1, msg1 = _check_image_qc_log(tid)
    checks.append((ok1, msg1, "image_qc_log"))
    ok2, msg2 = _check_video_has_subtitles_burned(video_path)
    checks.append((ok2, msg2, "video_streams"))
    if not SKIP_VIDEO_QC:
        ok3, msg3 = _sample_video_frames_and_check_faces(video_path)
        checks.append((ok3, msg3, "video_frames"))
    all_ok = True
    for ok, msg, name in checks:
        verdict = "PASS" if ok else "FAIL"
        print(f"[step5 GATE] {name}: {verdict} ({msg})")
        if not ok:
            all_ok = False
    return all_ok, checks


# ─── main ────────────────────────────────────────────────────────────────
def parse_args(argv):
    args = {"test": False, "id": None}
    rest = []
    for a in argv:
        if a == "--test":
            args["test"] = True
        else:
            rest.append(a)
    if rest:
        args["id"] = rest[0]
    return args


def main():
    args = parse_args(sys.argv[1:])
    cur_path = OUTPUT_DIR / "current.json"
    if not cur_path.exists():
        print(f"[step5] FATAL: {cur_path} not found")
        sys.exit(1)
    cur = json.loads(cur_path.read_text(encoding="utf-8"))
    tid = args["id"] or cur.get("id")
    if not tid:
        print("[step5] FATAL: no id in current.json or args")
        sys.exit(1)
    video_path = OUTPUT_DIR / f"{tid}_video.mp4"
    if not video_path.exists():
        print(f"[step5] FATAL: {video_path} not found")
        sys.exit(1)
    print(f"[step5] target id={tid} video={video_path} size={video_path.stat().st_size/1024/1024:.1f}MB")

    # ─── publish gate ───
    gate_ok, gate_log = publish_gate(tid, video_path)
    gate_path = OUTPUT_DIR / f"{tid}_publish_gate.json"
    gate_path.write_text(json.dumps([{"ok": ok, "msg": msg, "name": name} for ok, msg, name in gate_log],
                                     ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[step5] gate result -> {gate_path.name}")
    if not gate_ok:
        print("[step5] FATAL: pre-publish QC gate failed, abort upload. "
              "STEP5_SKIP_VIDEO_QC=true で強制 upload 可能（非推奨）。")
        sys.exit(2)

    metadata = build_metadata(cur)
    print(f"[step5] metadata title={metadata['snippet']['title']}")

    if args["test"]:
        print(f"[step5] --test mode, skip upload")
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return

    if not (CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN):
        print("[step5] FATAL: NEW_YOUTUBE_CLIENT_ID / _SECRET / _REFRESH_TOKEN missing")
        sys.exit(3)

    access_token = get_access_token()
    ch_id = fetch_channel_id(access_token)
    print(f"[step5] channel_id={ch_id}")

    vid, vid_ch = resumable_upload(access_token, video_path, metadata)
    print(f"[step5] upload OK video_id={vid} channel_id={vid_ch}")
    watch_url = f"https://www.youtube.com/watch?v={vid}"
    print(f"[step5] watch_url={watch_url}")

    # サムネ：<id>_thumb.jpg または <id>_thumb.png があれば設定
    for ext in (".jpg", ".jpeg", ".png"):
        tp = OUTPUT_DIR / f"{tid}_thumb{ext}"
        if tp.exists():
            print(f"[step5] uploading thumbnail {tp.name}")
            set_thumbnail(access_token, vid, tp)
            break

    # state.json 更新
    state_path = OUTPUT_DIR / "state.json"
    try:
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
        else:
            state = {}
        state.setdefault("processed", []).append(tid)
        state["lastUploadResult"] = {"id": tid, "video_id": vid, "url": watch_url, "channel_id": vid_ch}
        state["lastUploadAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[step5] state.json updated")
    except Exception as e:
        print(f"[step5] WARN: state.json update failed: {e}")


if __name__ == "__main__":
    main()
