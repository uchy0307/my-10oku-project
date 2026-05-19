# -*- coding: utf-8 -*-
"""
Emergency 1-video upload pipeline for @Japanese.Samurai.Channel
- VoiceVox @ localhost:50021 → audio.wav
- ffmpeg → black+text+audio mp4
- YouTube Data API v3 upload using refresh_token from ../note-auto/youtube_tokens.json
"""
import json, os, sys, time, subprocess, urllib.request, urllib.parse, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKDIR = ROOT
PROJECT_ROOT = ROOT.parent
TOKEN_FILE = PROJECT_ROOT / "note-auto" / "youtube_tokens.json"

VOICEVOX_URL = "http://localhost:50021"
SPEAKER_NAME = "玄野武宏"   # serious male tone, samurai-appropriate
STYLE_NAME = "ノーマル"

# Topic 011 preview content (legit samurai content)
TITLE = "【予告】長篠の戦い 鉄砲が変えた戦場"
DESCRIPTION = (
    "天正三年五月二十一日、三河国設楽原。\n"
    "織田信長・徳川家康の連合軍と、武田勝頼率いる武田軍が対峙した。\n"
    "三千挺の鉄砲、三重の馬防柵——戦の常識を覆した一日を、まもなく本編にて。\n\n"
    "■チャンネル: 侍の美学 — 日本史を語り継ぐ\n"
    "■カテゴリ: 合戦軸\n\n"
    "#日本史 #長篠の戦い #織田信長 #徳川家康 #武田勝頼 #戦国時代 #侍の美学"
)
TAGS = ["日本史", "歴史", "長篠の戦い", "織田信長", "武田勝頼", "鉄砲", "戦国時代", "侍の美学", "ナレーション"]

NARRATION = (
    "天正三年、五月二十一日。"
    "三河国、設楽原。"
    "織田信長、徳川家康の連合軍と、武田勝頼率いる精鋭騎馬軍団が、この地で対峙した。"
    "三千挺の鉄砲、三重に巡らされた馬防柵——。"
    "戦の常識を、ただ一日にして覆した合戦。"
    "長篠の戦い、その真実を、まもなくお届けする。"
)

def http_get(url, timeout=30):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def http_post(url, data=None, headers=None, timeout=120):
    h = headers or {}
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def resolve_style_id():
    speakers = json.loads(http_get(f"{VOICEVOX_URL}/speakers").decode("utf-8"))
    for sp in speakers:
        if sp.get("name") == SPEAKER_NAME:
            for st in sp.get("styles", []):
                if st.get("name") == STYLE_NAME:
                    return int(st["id"])
            # fallback: any style
            return int(sp.get("styles", [{}])[0].get("id", 0))
    raise RuntimeError(f"Speaker {SPEAKER_NAME} not found")

def make_voice(text, out_wav):
    style_id = resolve_style_id()
    print(f"[voicevox] style_id={style_id}")
    # 1) audio_query
    q_url = f"{VOICEVOX_URL}/audio_query?{urllib.parse.urlencode({'speaker': style_id, 'text': text})}"
    q_bytes = http_post(q_url, data=b"", headers={"Content-Type": "application/json"})
    q = json.loads(q_bytes.decode("utf-8"))
    # adjust prosody
    q["speedScale"] = 1.0
    q["pitchScale"] = 0.0
    q["intonationScale"] = 1.0
    q["volumeScale"] = 1.2
    q["prePhonemeLength"] = 0.5
    q["postPhonemeLength"] = 0.8
    # 2) synthesis
    s_url = f"{VOICEVOX_URL}/synthesis?{urllib.parse.urlencode({'speaker': style_id})}"
    wav_bytes = http_post(s_url, data=json.dumps(q).encode("utf-8"),
                          headers={"Content-Type": "application/json"})
    out_wav.write_bytes(wav_bytes)
    print(f"[voicevox] wrote {out_wav} ({len(wav_bytes)} bytes)")

def find_ffmpeg():
    import shutil
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        print(f"[ffmpeg] imageio_ffmpeg unavailable: {e}")
    # last resort: try standard install dirs
    for cand in [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
        if Path(cand).exists():
            return cand
    raise RuntimeError("ffmpeg not found")

def ffprobe_duration(ffmpeg, audio_wav):
    """Use ffmpeg -i to parse Duration (no separate ffprobe needed)."""
    r = subprocess.run([ffmpeg, "-i", str(audio_wav)], capture_output=True, text=True)
    # Duration line: Duration: 00:00:30.00,
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        raise RuntimeError(f"Cannot parse duration: {r.stderr[-500:]}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)

def make_video(audio_wav, out_mp4):
    ffmpeg = find_ffmpeg()
    print(f"[ffmpeg] using {ffmpeg}")
    dur = ffprobe_duration(ffmpeg, audio_wav)
    print(f"[ffmpeg] audio duration={dur:.2f}s")

    # Create a 1280x720 black bg with title text and Japanese font using drawtext
    # Use a Noto/Yu Gothic font on Windows
    font_paths = [
        r"C:\Windows\Fonts\YuGothB.ttc",
        r"C:\Windows\Fonts\YuGothic-Bold.ttf",
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
    ]
    font = None
    for fp in font_paths:
        if Path(fp).exists():
            font = fp
            break
    if not font:
        raise RuntimeError("No Japanese font found on Windows")
    print(f"[ffmpeg] font={font}")

    # ffmpeg drawtext requires escaping backslashes and colons in path
    font_esc = font.replace("\\", "/").replace(":", r"\:")

    # Build subtitle/title image with two lines
    # Using -filter_complex to overlay text on black background
    # On Windows, "drawtext" may need text encoded properly; use textfile for safety
    title_txt = WORKDIR / "title.txt"
    title_txt.write_text("長篠の戦い\n鉄砲が変えた戦場", encoding="utf-8")
    sub_txt = WORKDIR / "sub.txt"
    sub_txt.write_text("予 告 編", encoding="utf-8")

    title_path_esc = str(title_txt).replace("\\", "/").replace(":", r"\:")
    sub_path_esc = str(sub_txt).replace("\\", "/").replace(":", r"\:")

    vf = (
        f"drawtext=fontfile='{font_esc}':textfile='{title_path_esc}':"
        f"fontcolor=white:fontsize=72:x=(w-text_w)/2:y=(h-text_h)/2-60:line_spacing=20,"
        f"drawtext=fontfile='{font_esc}':textfile='{sub_path_esc}':"
        f"fontcolor=#c0a060:fontsize=44:x=(w-text_w)/2:y=h-120"
    )

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1280x720:d={dur:.3f}:r=30",
        "-i", str(audio_wav),
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_mp4),
    ]
    print(f"[ffmpeg] cmd={' '.join(cmd[:6])}...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("[ffmpeg STDERR]:", r.stderr[-2000:])
        raise RuntimeError(f"ffmpeg failed rc={r.returncode}")
    print(f"[ffmpeg] wrote {out_mp4} ({out_mp4.stat().st_size} bytes)")

def get_access_token(tokens):
    data = urllib.parse.urlencode({
        "client_id": tokens["YOUTUBE_CLIENT_ID"],
        "client_secret": tokens["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": tokens["YOUTUBE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode("utf-8")
    r = urllib.request.urlopen(urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    ), timeout=30)
    body = json.loads(r.read().decode("utf-8"))
    return body["access_token"]

def upload_video(mp4_path, access_token, privacy="public"):
    metadata = {
        "snippet": {
            "title": TITLE,
            "description": DESCRIPTION,
            "tags": TAGS,
            "categoryId": "27",  # Education
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }
    metadata_bytes = json.dumps(metadata).encode("utf-8")

    # Resumable upload init
    init_req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=metadata_bytes,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(mp4_path.stat().st_size),
        },
        method="POST",
    )
    r = urllib.request.urlopen(init_req, timeout=60)
    upload_url = r.headers.get("Location")
    if not upload_url:
        raise RuntimeError(f"No upload URL returned. headers={dict(r.headers)}")
    print(f"[upload] resumable URL acquired")

    # Upload file body
    with open(mp4_path, "rb") as fp:
        body = fp.read()
    put_req = urllib.request.Request(
        upload_url,
        data=body,
        headers={
            "Content-Type": "video/mp4",
            "Content-Length": str(len(body)),
        },
        method="PUT",
    )
    r = urllib.request.urlopen(put_req, timeout=600)
    resp = json.loads(r.read().decode("utf-8"))
    return resp

def make_silent_audio(out_wav, duration=30.0):
    """Fallback: generate silent audio via ffmpeg when TTS unavailable."""
    ffmpeg = find_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=24000",
        "-t", str(duration),
        "-c:a", "pcm_s16le",
        str(out_wav),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"silent audio gen failed: {r.stderr[-500:]}")
    print(f"[fallback] wrote silent audio {out_wav} ({duration}s)")

def make_voice_sapi(text, out_wav):
    """Fallback: Windows SAPI Japanese voice via PowerShell."""
    ps_script = f'''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
# Try to find Japanese voice
$jp = $synth.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like 'ja*' }} | Select-Object -First 1
if ($jp) {{ $synth.SelectVoice($jp.VoiceInfo.Name) }}
$synth.Rate = -1
$synth.SetOutputToWaveFile("{out_wav}")
$synth.Speak(@"
{text}
"@)
$synth.Dispose()
Write-Host "SAPI WAV written"
'''
    ps_file = WORKDIR / "sapi.ps1"
    ps_file.write_text(ps_script, encoding="utf-8")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_file)],
        capture_output=True, text=True
    )
    print("[sapi] stdout:", r.stdout[:500])
    if r.returncode != 0 or not Path(out_wav).exists() or Path(out_wav).stat().st_size < 1000:
        print("[sapi] stderr:", r.stderr[:1000])
        return False
    print(f"[sapi] wrote {out_wav} ({Path(out_wav).stat().st_size} bytes)")
    return True

def main():
    audio_wav = WORKDIR / "narration.wav"
    out_mp4 = WORKDIR / "emergency_011_preview.mp4"

    print("=== STEP 1: voice synthesis (cascade) ===")
    voice_ok = False
    try:
        make_voice(NARRATION, audio_wav)
        voice_ok = True
        print("[voice] VoiceVox path OK")
    except Exception as e:
        print(f"[voice] VoiceVox failed: {e}")
    if not voice_ok:
        try:
            if make_voice_sapi(NARRATION, audio_wav):
                voice_ok = True
                print("[voice] SAPI path OK")
        except Exception as e:
            print(f"[voice] SAPI failed: {e}")
    if not voice_ok:
        print("[voice] all TTS failed - using silent placeholder")
        make_silent_audio(audio_wav, duration=30.0)

    print("=== STEP 2: ffmpeg ===")
    make_video(audio_wav, out_mp4)

    print("=== STEP 3: YouTube upload ===")
    tokens = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    access_token = get_access_token(tokens)
    print(f"[oauth] access_token acquired (len={len(access_token)})")

    resp = upload_video(out_mp4, access_token, privacy="public")
    video_id = resp.get("id")
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"[upload] DONE id={video_id}")
    print(f"[upload] URL={url}")

    (WORKDIR / "upload_result.json").write_text(
        json.dumps({"videoId": video_id, "url": url, "response": resp},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("=== ALL DONE ===")

if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTPError {e.code}: {body[:2000]}")
        sys.exit(2)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
