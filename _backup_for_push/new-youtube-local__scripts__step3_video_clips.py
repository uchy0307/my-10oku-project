"""step3_video_clips.py
B案（夜版）用: Wikimedia Commons API で章ごとに無料動画クリップを取得。
- PIXABAY_KEY 不要・完全無認証
- Wikimedia Commons の .webm/.ogv をDL → ffmpeg で .mp4 に transcode
"""
import os, sys, json, time, random, subprocess, shutil
from pathlib import Path
import urllib.request, urllib.parse, urllib.error

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "output"

PIXABAY_KEY = os.environ.get("PIXABAY_KEY", "").strip()
PIXABAY_API = "https://pixabay.com/api/videos/"
WIKI_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "otona-night/1.0 (uchiyamatakayuki0307@gmail.com)"

CLIPS_PER_CHAPTER = int(os.environ.get("CLIPS_PER_CHAPTER", "3"))
MIN_CLIP_SEC = float(os.environ.get("CLIP_MIN_SEC", "2.5"))
MAX_CLIP_SEC = float(os.environ.get("CLIP_MAX_SEC", "120"))
TARGET_W = int(os.environ.get("VIDEO_W", "1280"))
TARGET_H = int(os.environ.get("VIDEO_H", "720"))
TARGET_FPS = int(os.environ.get("VIDEO_FPS", "24"))

CATEGORY_QUERIES = {
    "恋愛心理": ["candle flame", "rain night city", "moon clouds", "ocean sunset"],
    "性愛心理": ["silhouette dance", "fabric flow", "wine pouring", "perfume bottle"],
    "対人心理": ["city night street", "cafe bokeh", "rainy street", "pedestrians timelapse"],
    "暗黒心理": ["dark hallway", "shadow figure", "broken mirror", "rain droplets"],
}
DEFAULT_QUERIES = [
    "night cityscape", "rain window", "candle flame", "ocean waves",
    "neon lights", "smoke slow motion", "moon clouds", "fire close up",
    "forest trees", "river flowing", "leaves wind", "sunset clouds",
]


def http_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def http_download(url, out_path, timeout=300):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    out_path.write_bytes(data)
    return len(data)


def wiki_search(query, limit=20):
    q = "filetype:video " + query
    params = {"action": "query", "format": "json", "list": "search",
              "srnamespace": "6", "srsearch": q, "srlimit": str(limit)}
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    try:
        data = http_json(url, timeout=30)
    except Exception as e:
        print("[step3_video] wiki_search err q=" + query + ": " + str(e))
        return []
    return [h["title"] for h in data.get("query", {}).get("search", [])]


def wiki_fileinfo(title):
    params = {"action": "query", "format": "json", "titles": title,
              "prop": "imageinfo",
              "iiprop": "url|size|mediatype|mime|metadata"}
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    try:
        data = http_json(url, timeout=30)
    except Exception as e:
        print("[step3_video] wiki_fileinfo err " + title + ": " + str(e))
        return None
    pages = data.get("query", {}).get("pages", {})
    for _, p in pages.items():
        ii = p.get("imageinfo")
        if not ii:
            continue
        info = ii[0]
        mt = (info.get("mediatype") or "").upper()
        mime = info.get("mime", "")
        if mt != "VIDEO" and not mime.startswith("video/"):
            return None
        duration = None
        meta = info.get("metadata") or []
        for m in meta:
            if m.get("name") == "length":
                try:
                    duration = float(m.get("value"))
                except Exception:
                    pass
        return {
            "title": title, "url": info.get("url"),
            "width": info.get("width"), "height": info.get("height"),
            "size": info.get("size"), "mime": mime, "duration": duration,
        }
    return None


def wiki_pick(titles, used):
    random.shuffle(titles)
    for t in titles:
        if t in used:
            continue
        info = wiki_fileinfo(t)
        if not info:
            continue
        used.add(t)
        dur = info.get("duration")
        if dur is not None and (dur < MIN_CLIP_SEC or dur > MAX_CLIP_SEC):
            print("[step3_video] skip dur=" + str(dur) + "s: " + t)
            continue
        if info.get("width") and info["width"] < 640:
            print("[step3_video] skip w=" + str(info["width"]) + ": " + t)
            continue
        url = info["url"]
        # IMPORTANT: strip query string before extracting ext
        path_only = url.split("?")[0].split("#")[0]
        ext = path_only.rsplit(".", 1)[-1].lower() if "." in path_only else ""
        if ext not in ("webm", "ogv", "mp4", "mov", "ogg"):
            print("[step3_video] skip unknown ext=" + ext + ": " + t)
            continue
        return {
            "source": "wikimedia", "id": t, "url": url,
            "width": info.get("width"), "height": info.get("height"),
            "duration": dur,
            "pageURL": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(t),
            "ext": ext,
        }
    return None


def ensure_ffmpeg():
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise RuntimeError("ffmpeg not found")


def transcode_to_mp4(src, dst, ffmpeg_exe):
    vf = ("scale=" + str(TARGET_W) + ":" + str(TARGET_H) +
          ":force_original_aspect_ratio=decrease,"
          "pad=" + str(TARGET_W) + ":" + str(TARGET_H) +
          ":(ow-iw)/2:(oh-ih)/2:color=black,fps=" + str(TARGET_FPS))
    cmd = [ffmpeg_exe, "-y", "-i", str(src), "-vf", vf,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-an", str(dst)]
    print("[step3_video] transcode " + src.name + " -> " + dst.name)
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if r.returncode != 0:
        print(r.stdout[-1500:])
        return False
    return True


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    cat = cur.get("category", "")
    queries = CATEGORY_QUERIES.get(cat, DEFAULT_QUERIES)
    extra_queries = DEFAULT_QUERIES[:]
    print("[step3_video] category=" + cat + " queries=" + str(queries))

    ffmpeg_exe = ensure_ffmpeg()
    print("[step3_video] ffmpeg: " + ffmpeg_exe)

    out_clips = []
    used = set()
    for c in cur["chapters"]:
        idx = c["index"]
        q_pool = [queries[(idx - 1) % len(queries)]] + extra_queries
        got = 0
        for k in range(CLIPS_PER_CHAPTER):
            picked = None
            for query in q_pool:
                titles = wiki_search(query, limit=30)
                if not titles:
                    continue
                c2 = wiki_pick(titles, used)
                if c2:
                    picked = c2
                    break
            if not picked:
                print("[step3_video] ch" + str(idx) + " k" + str(k) + ": NO clip found")
                break
            raw_path = OUTPUT_DIR / ("_raw_" + cur["id"] + "_clip_" + ("%02d" % idx) + "_" + ("%02d" % k) + "." + picked["ext"])
            try:
                sz = http_download(picked["url"], raw_path)
            except Exception as e:
                print("[step3_video] dl FAIL: " + str(e))
                continue
            print("[step3_video] dl OK " + str(sz//1024//1024) + "MB " + picked["pageURL"])
            mp4_path = OUTPUT_DIR / (cur["id"] + "_clip_" + ("%02d" % idx) + "_" + ("%02d" % k) + ".mp4")
            if picked["ext"] == "mp4":
                shutil.move(str(raw_path), str(mp4_path))
            else:
                ok = transcode_to_mp4(raw_path, mp4_path, ffmpeg_exe)
                try:
                    raw_path.unlink()
                except Exception:
                    pass
                if not ok:
                    print("[step3_video] transcode FAIL")
                    continue
            out_clips.append({
                **picked, "chapter": idx, "path": str(mp4_path),
                "file": mp4_path.name, "size_bytes": mp4_path.stat().st_size,
            })
            got += 1
        if got == 0:
            print("[step3_video] WARN ch" + str(idx) + ": 0 clips")
    (OUTPUT_DIR / (cur["id"] + "_clips.json")).write_text(
        json.dumps(out_clips, ensure_ascii=False, indent=2), encoding="utf-8")
    if not out_clips:
        print("[step3_video] FATAL: 0 clips")
        sys.exit(3)
    print("[step3_video] total " + str(len(out_clips)) + " clips")


if __name__ == "__main__":
    main()
