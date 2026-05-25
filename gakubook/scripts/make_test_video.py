"""make_test_video.py
学問・教養 解説系チャンネル（@gakubook 参考）のテスト動画ジェネレーター。

この環境では Gemini / Google TTS / ElevenLabs / edge-tts が全てプロキシ(403)で
使えないため、ナレーションは「オフライン espeak-ng + pykakasi(漢字→かな)」で代替する。
=> 音声はロボット声・構成/演出/字幕同期の確認用。本番は既存パイプライン
   (step0_gemini + step2_voice_google_tts 等) を API キー付きで使う想定。

入力 : gakubook/script.json
出力 : gakubook/output/<id>_video.mp4 (+ voice.wav, subtitle.srt, slides/*.png)
"""
import json, subprocess, wave, contextlib, shutil
from pathlib import Path

import pykakasi
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
SLIDES = OUT / "slides"
TMP = OUT / "_tmp"
for d in (OUT, SLIDES, TMP):
    d.mkdir(parents=True, exist_ok=True)

W, H, FPS = 1280, 720, 24
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"

# espeak: calm 教養 pace
ESPEAK_SPEED = 145   # wpm
ESPEAK_PITCH = 42
HEAD_MS, PARA_MS, CHAP_MS = 400, 350, 800

_kks = pykakasi.kakasi()


def to_kana(text: str) -> str:
    return "".join(r["hira"] for r in _kks.convert(text))


def espeak(text: str, out_wav: Path):
    kana = to_kana(text)
    subprocess.run(
        ["espeak-ng", "-v", "ja", "-s", str(ESPEAK_SPEED), "-p", str(ESPEAK_PITCH),
         "-w", str(out_wav), kana],
        check=True, capture_output=True,
    )


def wav_dur(p: Path) -> float:
    with contextlib.closing(wave.open(str(p), "rb")) as w:
        return w.getnframes() / float(w.getframerate())


def silence_wav(ref: Path, ms: int, out: Path):
    with contextlib.closing(wave.open(str(ref), "rb")) as w:
        params = w.getparams()
    nframes = int(params.framerate * ms / 1000.0)
    with contextlib.closing(wave.open(str(out), "wb")) as w:
        w.setparams(params)
        w.writeframes(b"\x00" * nframes * params.sampwidth * params.nchannels)


def concat_wavs(parts, out: Path):
    with contextlib.closing(wave.open(str(parts[0]), "rb")) as w0:
        params = w0.getparams()
    with contextlib.closing(wave.open(str(out), "wb")) as wout:
        wout.setparams(params)
        for p in parts:
            with contextlib.closing(wave.open(str(p), "rb")) as w:
                wout.writeframes(w.readframes(w.getnframes()))


def srt_time(sec: float) -> str:
    if sec < 0:
        sec = 0
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap(text: str, width: int = 22) -> str:
    out, buf = [], ""
    for ch in text:
        buf += ch
        if len(buf) >= width and ch in "。、！？…":
            out.append(buf); buf = ""
    if buf:
        out.append(buf)
    return "\\N".join(out[:2]) if out else text


# ---------- slides ----------
def grad_bg(top=(14, 20, 38), bot=(28, 38, 66)):
    img = Image.new("RGB", (W, H), top)
    px = img.load()
    for y in range(H):
        t = y / H
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img


def font(path, size):
    return ImageFont.truetype(path, size)


def draw_center(d, text, fpath, size, y, fill=(240, 244, 255)):
    f = font(fpath, size)
    bb = d.textbbox((0, 0), text, font=f)
    w = bb[2] - bb[0]
    d.text(((W - w) / 2, y), text, font=f, fill=fill)
    return bb[3] - bb[1]


def accent_line(d, y, w=180, color=(120, 170, 255)):
    d.rectangle([(W - w) // 2, y, (W + w) // 2, y + 5], fill=color)


def make_intro_slide(title, path):
    img = grad_bg()
    d = ImageDraw.Draw(img)
    draw_center(d, "学問と教養の話", FONT_SERIF, 30, 150, fill=(150, 175, 220))
    accent_line(d, 210)
    # title may be long -> wrap manually
    f = font(FONT_BOLD, 52)
    words = title.replace("―", " ― ").split(" ")
    lines, cur = [], ""
    for wd in words:
        test = (cur + wd).strip()
        if d.textlength(test, font=f) > W - 160 and cur:
            lines.append(cur.strip()); cur = wd
        else:
            cur = (cur + " " + wd).strip()
    if cur:
        lines.append(cur.strip())
    y = 300
    for ln in lines[:3]:
        wln = d.textlength(ln, font=f)
        d.text(((W - wln) / 2, y), ln, font=f, fill=(245, 248, 255))
        y += 70
    img.save(path)


def make_chapter_slide(idx, title, points, path):
    img = grad_bg()
    d = ImageDraw.Draw(img)
    draw_center(d, f"第 {idx} 章", FONT_SERIF, 34, 90, fill=(140, 170, 230))
    accent_line(d, 150)
    draw_center(d, title, FONT_BOLD, 50, 200)
    fp = font(FONT_BOLD, 34)
    y = 360
    for p in points:
        d.ellipse([200, y + 12, 216, y + 28], fill=(120, 170, 255))
        d.text((250, y), p, font=fp, fill=(225, 232, 248))
        y += 70
    img.save(path)


def make_outro_slide(path):
    img = grad_bg(top=(30, 20, 14), bot=(60, 38, 28))
    d = ImageDraw.Draw(img)
    accent_line(d, 250, color=(255, 190, 120))
    draw_center(d, "過去ではなく、未来へ", FONT_BOLD, 50, 300, fill=(255, 240, 225))
    draw_center(d, "ご視聴ありがとうございました", FONT_SERIF, 28, 420, fill=(210, 190, 175))
    img.save(path)


def main():
    data = json.loads((ROOT / "script.json").read_text(encoding="utf-8"))
    tid = data["id"]

    # Build segment list: (slide_key, [paragraphs])
    segments = []
    segments.append(("intro", data["intro"]))
    for ch in data["chapters"]:
        segments.append((f"ch{ch['index']}", ch["paragraphs"]))
    segments.append(("outro", data["outro"]))

    # slides
    make_intro_slide(data["title"], SLIDES / "intro.png")
    for ch in data["chapters"]:
        make_chapter_slide(ch["index"], ch["title"], ch["points"], SLIDES / f"ch{ch['index']}.png")
    make_outro_slide(SLIDES / "outro.png")
    print("[slides] done")

    # audio + timings
    ref = None
    wav_parts = []
    cues = []          # (start, end, text)
    seg_durations = {} # slide_key -> seconds
    cursor = HEAD_MS / 1000.0

    # head silence (need a ref wav: synth first para to get params)
    first = TMP / "p_first.wav"
    espeak(segments[0][1][0], first)
    ref = first
    head = TMP / "head.wav"
    silence_wav(ref, HEAD_MS, head)
    wav_parts.append(head)

    pidx = 0
    for key, paras in segments:
        seg_start = cursor
        for j, para in enumerate(paras):
            pw = TMP / f"p_{pidx:03d}.wav"
            espeak(para, pw)
            dur = wav_dur(pw)
            cues.append((cursor, cursor + dur, para))
            wav_parts.append(pw)
            cursor += dur
            # paragraph gap
            gap = TMP / f"g_{pidx:03d}.wav"
            silence_wav(ref, PARA_MS, gap)
            wav_parts.append(gap)
            cursor += PARA_MS / 1000.0
            pidx += 1
        # chapter gap
        cg = TMP / f"cg_{key}.wav"
        silence_wav(ref, CHAP_MS, cg)
        wav_parts.append(cg)
        cursor += CHAP_MS / 1000.0
        seg_durations[key] = cursor - seg_start
    total = cursor
    print(f"[audio] total {total:.1f}s, {len(cues)} cues")

    voice = OUT / f"{tid}_voice.wav"
    concat_wavs(wav_parts, voice)

    # SRT
    srt = OUT / f"{tid}_subtitle.srt"
    lines = []
    for i, (s, e, t) in enumerate(cues, 1):
        lines += [str(i), f"{srt_time(s)} --> {srt_time(e)}", wrap(t).replace("\\N", "\n"), ""]
    srt.write_text("\n".join(lines), encoding="utf-8")

    # per-segment video from slide
    ff = shutil.which("ffmpeg")
    trimmed = []
    slide_map = {"intro": "intro.png", "outro": "outro.png"}
    for ch in data["chapters"]:
        slide_map[f"ch{ch['index']}"] = f"ch{ch['index']}.png"
    for key, _ in segments:
        seg_v = TMP / f"seg_{key}.mp4"
        img = SLIDES / slide_map[key]
        dur = seg_durations[key]
        subprocess.run(
            [ff, "-y", "-loop", "1", "-i", str(img), "-t", f"{dur:.3f}",
             "-vf", f"scale={W}:{H},fps={FPS}",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
             "-pix_fmt", "yuv420p", str(seg_v)],
            check=True, capture_output=True,
        )
        trimmed.append(seg_v)
    print("[video] segments done")

    # concat
    clist = TMP / "concat.txt"
    clist.write_text("\n".join(f"file '{t.as_posix()}'" for t in trimmed), encoding="utf-8")
    nosub = TMP / "nosub.mp4"
    subprocess.run(
        [ff, "-y", "-f", "concat", "-safe", "0", "-i", str(clist),
         "-i", str(voice), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
         "-shortest", str(nosub)],
        check=True, capture_output=True,
    )

    # burn subtitles
    out = OUT / f"{tid}_video.mp4"
    srt_arg = str(srt).replace(":", r"\:")
    vf = (f"subtitles={srt_arg}:force_style='FontName=Noto Sans CJK JP,"
          f"FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00202020,"
          f"BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=40'")
    r = subprocess.run(
        [ff, "-y", "-i", str(nosub), "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-c:a", "copy", str(out)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"[subtitle] burn failed, fallback no-sub:\n{r.stderr[-600:]}")
        shutil.copy(str(nosub), str(out))

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"[DONE] {out} ({size_mb:.1f}MB, {total:.1f}s)")


if __name__ == "__main__":
    main()
