"""step4_compile_night.py
B案（夜版）: Wikimedia/Pexels の動画クリップを連結 → ナレ重畳 → 字幕焼込み。

仕様 (2026-05-18 強化):
  * 動画尺は MAX_VIDEO_SEC (デフォ 870s = 14:30) を超えたら強制カット
  * 字幕フォントサイズは画面高さの 1/3 未満 (FontSize=32 ≈ 720x720 の 4.4%)
  * クリップ数は (音声秒 / 60) 以上 (足りない場合は既存クリップを循環再利用)
  * アスペクト比保持 (黒帯レターボックス / ピラーボックス)、ストレッチしない
  * 字幕 SRT が無ければ gen_subtitle.py をその場で生成

入力:
    output/<id>_voice.wav       (step2_voicevox or step2_gtts どちらでも可)
    output/<id>_clip_NN_NN.mp4  (step3_video_clips の成果物)
    output/<id>_subtitle.srt    (gen_subtitle.py が自動生成)

出力:
    output/<id>_video.mp4
"""
import os, sys, json, glob, shutil, subprocess, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUTPUT_DIR = ROOT / "output"

FPS = int(os.environ.get("VIDEO_FPS", "24"))
W = int(os.environ.get("VIDEO_W", "1280"))
H = int(os.environ.get("VIDEO_H", "720"))
CROSSFADE = float(os.environ.get("CROSSFADE_SEC", "0.6"))
SUB_FONT = os.environ.get("SUB_FONT", "Noto Sans CJK JP")
# 字幕フォントサイズは 1/3 H 未満 (720 → 240 上限) を強制
SUB_FONT_SIZE = min(int(os.environ.get("SUB_FONT_SIZE", "32")), H // 3 - 1)
# 動画長キャップ (デフォ 870s = 14:30)
MAX_VIDEO_SEC = float(os.environ.get("MAX_VIDEO_SEC", "870"))
# クリップ数下限 = max(N, ceil(動画秒/60))
MIN_CLIPS_PER_MIN = float(os.environ.get("MIN_CLIPS_PER_MIN", "1.0"))


def ensure_subtitle(tid: str) -> Path:
    """gen_subtitle.py が無い場合は呼んで生成。"""
    srt_path = OUTPUT_DIR / f"{tid}_subtitle.srt"
    if srt_path.exists() and srt_path.stat().st_size > 0:
        print(f"[step4_night] subtitle exists: {srt_path.name}")
        return srt_path
    gen = SCRIPTS / "gen_subtitle.py"
    if not gen.exists():
        print(f"[step4_night] WARN: gen_subtitle.py not found, will burn no subs")
        return srt_path
    print(f"[step4_night] generating subtitle via {gen.name}")
    r = subprocess.run([sys.executable, str(gen)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout[-1500:])
    if r.returncode != 0:
        print(f"[step4_night] WARN: gen_subtitle rc={r.returncode}")
    return srt_path


def cap_srt_at(srt_path: Path, max_sec: float):
    """SRT の cue で max_sec を越えるものを除去 / 切り詰め。"""
    if not srt_path.exists():
        return
    try:
        text = srt_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[step4_night] WARN: srt read fail: {e}")
        return

    def t2s(t):
        h, m, rest = t.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    def s2t(s):
        h = int(s // 3600); s -= h * 3600
        m = int(s // 60); s -= m * 60
        sec = int(s); ms = int((s - sec) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    blocks = text.strip().split("\n\n")
    kept = []
    for b in blocks:
        lines = b.split("\n")
        if len(lines) < 2 or "-->" not in lines[1]:
            continue
        a, c = lines[1].split("-->")
        s_a = t2s(a.strip()); s_c = t2s(c.strip())
        if s_a >= max_sec:
            continue
        if s_c > max_sec:
            s_c = max_sec
            lines[1] = f"{s2t(s_a)} --> {s2t(s_c)}"
        kept.append("\n".join(lines))
    out = "\n\n".join(kept) + "\n"
    srt_path.write_text(out, encoding="utf-8")
    print(f"[step4_night] capped srt at {max_sec:.0f}s: {len(kept)} cues kept")


def fit_letterbox(vc, target_w: int, target_h: int):
    """アスペクト比を保ちつつ target_w x target_h にフィット (黒帯入り)。"""
    from moviepy.editor import CompositeVideoClip, ColorClip
    from moviepy.video.fx.all import resize as fx_resize
    sw, sh = vc.size
    if sw <= 0 or sh <= 0:
        return vc
    src_ar = sw / sh
    tgt_ar = target_w / target_h
    if src_ar > tgt_ar:
        # source 横長 → 横幅合わせ、上下に黒帯
        new_w = target_w
        new_h = max(1, int(round(target_w / src_ar)))
    else:
        # source 縦長 → 縦合わせ、左右に黒帯
        new_h = target_h
        new_w = max(1, int(round(target_h * src_ar)))
    scaled = fx_resize(vc, newsize=(new_w, new_h))
    bg = ColorClip(size=(target_w, target_h), color=(0, 0, 0)).set_duration(scaled.duration)
    return CompositeVideoClip([bg, scaled.set_position("center")], size=(target_w, target_h))


def compile_clipped_video(tid: str) -> Path:
    from moviepy.editor import (
        AudioFileClip, VideoFileClip, concatenate_videoclips,
    )
    from moviepy.video.fx.all import loop as fx_loop

    voice_path = OUTPUT_DIR / f"{tid}_voice.wav"
    if not voice_path.exists():
        print(f"[step4_night] missing voice: {voice_path}")
        sys.exit(1)
    audio = AudioFileClip(str(voice_path))
    total_dur = audio.duration
    print(f"[step4_night] audio raw duration: {total_dur:.1f}s")

    # ★ duration cap
    if total_dur > MAX_VIDEO_SEC:
        print(f"[step4_night] CAP: {total_dur:.1f}s -> {MAX_VIDEO_SEC:.1f}s (limit)")
        audio = audio.subclip(0, MAX_VIDEO_SEC)
        total_dur = MAX_VIDEO_SEC

    clip_files = sorted(glob.glob(str(OUTPUT_DIR / f"{tid}_clip_*.mp4")))
    if not clip_files:
        print("[step4_night] no clips found")
        sys.exit(1)

    # ★ クリップ数 >= ceil(total_dur/60 * MIN_CLIPS_PER_MIN)
    required = int(math.ceil(total_dur / 60.0 * MIN_CLIPS_PER_MIN))
    if len(clip_files) < required:
        # 不足分は既存ファイルを循環追加
        print(f"[step4_night] only {len(clip_files)} clips < required {required}; cycling")
        cycled = []
        i = 0
        while len(clip_files) + len(cycled) < required:
            cycled.append(clip_files[i % len(clip_files)])
            i += 1
        clip_files = clip_files + cycled
    print(f"[step4_night] using {len(clip_files)} clips (need >= {required})")

    # ターゲット尺 = total_dur / N + crossfade
    target_per = total_dur / len(clip_files) + CROSSFADE

    raw_clips = []
    for cf in clip_files:
        try:
            vc = VideoFileClip(cf).without_audio()
        except Exception as e:
            print(f"[step4_night] WARN: cannot open {cf}: {e}")
            continue
        if vc.duration is None or vc.duration <= 0:
            print(f"[step4_night] WARN: invalid duration {cf}")
            continue
        if vc.duration < target_per:
            n = int(math.ceil(target_per / vc.duration))
            vc = fx_loop(vc, n=n)
        vc = vc.subclip(0, target_per)
        # ★ アスペクト比保持: letterbox/pillarbox
        vc = fit_letterbox(vc, W, H)
        raw_clips.append(vc)

    if not raw_clips:
        print("[step4_night] FATAL: 0 usable clips")
        sys.exit(1)

    # クロスフェード連結
    final_clips = []
    for i, vc in enumerate(raw_clips):
        if i > 0:
            vc = vc.crossfadein(CROSSFADE)
        final_clips.append(vc)

    video = concatenate_videoclips(final_clips, method="compose", padding=-CROSSFADE)
    # 最終尺を total_dur に合わせる (上限カット済み)
    if video.duration > total_dur:
        video = video.subclip(0, total_dur)
    video = video.set_audio(audio).set_duration(total_dur)

    pre_path = OUTPUT_DIR / f"{tid}_video_nosubs.mp4"
    video.write_videofile(
        str(pre_path), fps=FPS, codec="libx264", audio_codec="aac",
        threads=4, preset="medium", bitrate="3500k",
        temp_audiofile=str(OUTPUT_DIR / f"{tid}_tmp_audio.m4a"),
        remove_temp=True,
    )
    print(f"[step4_night] wrote pre-subs video: {pre_path}")
    return pre_path


def burn_subtitles(pre_path: Path, srt_path: Path, out_path: Path):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")
    force_style = (
        f"FontName={SUB_FONT},FontSize={SUB_FONT_SIZE},"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=40"
    )
    srt_arg = str(srt_path).replace("\\", "/").replace(":", r"\:")
    vf = f"subtitles={srt_arg}:force_style='{force_style}'"
    cmd = [
        "ffmpeg", "-y", "-i", str(pre_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "copy",
        str(out_path),
    ]
    print("[step4_night] ffmpeg:", " ".join(cmd))
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout[-3000:])
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg subtitle burn failed rc={r.returncode}")


def main():
    cur = json.loads((OUTPUT_DIR / "current.json").read_text(encoding="utf-8"))
    tid = cur["id"]
    out_path = OUTPUT_DIR / f"{tid}_video.mp4"

    # ★ step3 の QC 結果をチェック（image_quality.json が pass率 50% 以上か）
    qc_path = OUTPUT_DIR / f"{tid}_quality.json"
    if qc_path.exists():
        try:
            qc = json.loads(qc_path.read_text(encoding="utf-8"))
            total = len(qc)
            pass_n = sum(1 for q in qc if q.get("qc_ok"))
            if total > 0 and pass_n / total < 0.5:
                print(f"[step4_night] FATAL: image QC pass {pass_n}/{total} < 50%, abort compile")
                sys.exit(2)
            print(f"[step4_night] image QC pass {pass_n}/{total} OK")
        except Exception as e:
            print(f"[step4_night] WARN: quality.json read failed: {e}")

    # ★ SRT を確保 (無ければ生成)、その後 MAX_VIDEO_SEC でキャップ
    srt_path = ensure_subtitle(tid)
    if srt_path.exists():
        cap_srt_at(srt_path, MAX_VIDEO_SEC)

    # ★ うっちー様明示「テロップナシダメ」: 字幕無しなら fail-fast
    if not (srt_path.exists() and srt_path.stat().st_size > 0):
        print(f"[step4_night] FATAL: subtitle MUST be present ({srt_path}). "
              f"テロップナシは publish 不可. step1-2 を再実行して字幕生成してください.")
        sys.exit(3)

    pre_path = compile_clipped_video(tid)

    # ★ 字幕焼込みも MUST: 失敗時は no-subs フォールバックせず exit
    try:
        burn_subtitles(pre_path, srt_path, out_path)
        try:
            pre_path.unlink()
        except Exception:
            pass
    except Exception as e:
        print(f"[step4_night] FATAL: subtitle burn failed ({e}). "
              f"テロップ焼込みは MUST のため publish 不可.")
        # pre_path は残しておいて再実行で活用できるようにする
        sys.exit(4)

    print(f"[step4_night] FINAL: {out_path} ({out_path.stat().st_size/1024/1024:.1f}MB)")


if __name__ == "__main__":
    main()
