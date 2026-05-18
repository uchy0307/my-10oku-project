"""compile_ffmpeg.py
ffmpeg ONLY (no moviepy): concat clips + add audio + burn subtitle.
Output: output/<tid>_video.mp4
"""
import os, sys, json, subprocess, shutil
from pathlib import Path
import glob

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

# Auto-load .env
_ENV = ROOT / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        if _k.strip() and _k.strip() not in os.environ:
            os.environ[_k.strip()] = _v.strip()

TARGET_W = int(os.environ.get("VIDEO_W", "1280"))
TARGET_H = int(os.environ.get("VIDEO_H", "720"))
TARGET_FPS = int(os.environ.get("VIDEO_FPS", "24"))
MAX_SEC = float(os.environ.get("VIDEO_MAX_SEC", "870"))  # 14.5min cap


def find_ffmpeg():
    ff = shutil.which("ffmpeg")
    if ff: return ff
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def ffprobe_dur(ffmpeg, path):
    # ffmpeg can print duration to stderr
    r = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True)
    for line in r.stderr.split("\n"):
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return float(h)*3600 + float(m)*60 + float(s)
    return 0.0


def main():
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    tid = cur["id"]

    voice = OUTPUT_DIR / f"{tid}_voice.wav"
    srt = OUTPUT_DIR / f"{tid}_subtitle.srt"
    out = OUTPUT_DIR / f"{tid}_video.mp4"

    if not voice.exists():
        print(f"[compile_ffmpeg] missing voice: {voice}")
        sys.exit(1)

    ffmpeg = find_ffmpeg()
    print(f"[compile_ffmpeg] ffmpeg={ffmpeg}")

    clips = sorted(glob.glob(str(OUTPUT_DIR / f"{tid}_clip_*.mp4")))
    if not clips:
        print(f"[compile_ffmpeg] no clips")
        sys.exit(1)
    print(f"[compile_ffmpeg] {len(clips)} clips")

    # voice duration
    aud_dur = ffprobe_dur(ffmpeg, voice)
    target_dur = min(aud_dur, MAX_SEC)
    print(f"[compile_ffmpeg] audio={aud_dur:.1f}s target={target_dur:.1f}s")

    # Each clip = target_dur / len(clips), trim long clips to that length
    per_clip = target_dur / len(clips)
    print(f"[compile_ffmpeg] per_clip={per_clip:.2f}s")

    # Step 1: trim+pad each clip to exactly per_clip, scaled to TARGET_WxH
    tmp_dir = OUTPUT_DIR / "_compile_tmp"
    tmp_dir.mkdir(exist_ok=True)
    trimmed = []
    for i, c in enumerate(clips):
        t = tmp_dir / f"trim_{i:02d}.mp4"
        # Loop if shorter than per_clip
        c_dur = ffprobe_dur(ffmpeg, c)
        if c_dur < per_clip:
            # loop
            cmd = [ffmpeg, "-y", "-stream_loop", "-1", "-i", c,
                   "-t", str(per_clip),
                   "-vf", f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black,fps={TARGET_FPS}",
                   "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                   "-an", str(t)]
        else:
            cmd = [ffmpeg, "-y", "-i", c,
                   "-t", str(per_clip),
                   "-vf", f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black,fps={TARGET_FPS}",
                   "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                   "-an", str(t)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[compile_ffmpeg] trim FAIL {c}: {r.stderr[-500:]}")
            sys.exit(2)
        trimmed.append(t)
        print(f"[compile_ffmpeg] trimmed {i+1}/{len(clips)} ({per_clip:.1f}s)")

    # Step 2: concat using concat demuxer
    concat_list = tmp_dir / "concat.txt"
    concat_list.write_text("\n".join(f"file '{t.as_posix()}'" for t in trimmed), encoding="utf-8")
    no_sub = tmp_dir / "video_nosub.mp4"
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
           "-i", str(voice), "-t", str(target_dur),
           "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
           "-shortest", str(no_sub)]
    print(f"[compile_ffmpeg] concat + audio mux ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[compile_ffmpeg] concat FAIL: {r.stderr[-1000:]}")
        sys.exit(3)
    print(f"[compile_ffmpeg] concat OK ({no_sub.stat().st_size//1024//1024}MB)")

    # Step 3: burn subtitles
    if srt.exists():
        # Escape for ffmpeg subtitles filter
        srt_arg = str(srt).replace("\\", "/").replace(":", r"\:")
        vf = f"subtitles={srt_arg}:force_style='FontName=Yu Gothic UI,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=30'"
        cmd = [ffmpeg, "-y", "-i", str(no_sub),
               "-vf", vf,
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
               "-c:a", "copy", str(out)]
        print(f"[compile_ffmpeg] burn subtitles ...")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[compile_ffmpeg] subtitle burn FAIL ({r.stderr[-500:]}); fallback no-sub")
            shutil.copy(str(no_sub), str(out))
    else:
        print(f"[compile_ffmpeg] no SRT, copy no-sub as final")
        shutil.copy(str(no_sub), str(out))

    # Cleanup tmp
    try:
        for t in trimmed: t.unlink(missing_ok=True)
        concat_list.unlink(missing_ok=True)
        no_sub.unlink(missing_ok=True)
    except Exception:
        pass

    print(f"[compile_ffmpeg] FINAL: {out} ({out.stat().st_size//1024//1024}MB)")


if __name__ == "__main__":
    main()
