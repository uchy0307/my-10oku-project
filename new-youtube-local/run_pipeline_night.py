"""run_pipeline_night.py
B案（夜版）パイプライン:
  step0_gemini → step1_load → step2_voice_google_tts → step3_video_clips →
  step3b_thumbnail → step4_compile_night → step5_upload → verify_uploaded

[2026-05-19] VOICEVOX local 依存を廃止し、Google Cloud TTS Neural2-B
（無料枠 1M chars/月）に統一。 完全 cloud / 完全無料軸。
従来の `step2_voice_voicevox.py` は実装維持・パイプラインから除外。

実行環境はそのまま Windows Task Scheduler 21:00 JST 毎日想定。
必要な env: GEMINI_API_KEY または GOOGLE_API_KEY (TTS 兼用)。
"""
import os, sys, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip()
        if k and k not in os.environ:
            os.environ[k] = v

STEPS = [
    ("step0_gemini.py",           "Gemini script"),
    ("step1_load.py",             "Load & validate"),
    ("step2_voice_google_tts.py", "Google Cloud TTS synth (ja-JP-Neural2-B)"),
    ("step3_video_clips.py",      "Pixabay video clips"),
    ("step3b_thumbnail.py",       "Gemini Imagen thumbnail"),
    ("step4_compile_night.py",    "MoviePy clip compose + subtitle burn"),
    ("step5_upload.py",           "YouTube upload"),
    ("verify_uploaded.py",        "Atom feed verify"),
]


def run_step(idx: int, name: str, label: str, extra_args):
    log_path = LOG_DIR / f"night_step{idx}_{time.strftime('%Y%m%d_%H%M%S')}.log"
    print(f"\n=== [night-step{idx}] {label} ===")
    cmd = [sys.executable, str(SCRIPTS / name)] + extra_args
    print(" ".join(cmd))
    with open(log_path, "w", encoding="utf-8") as logf:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        logf.write(p.stdout or "")
    if p.stdout:
        print(p.stdout[-3000:])
    if p.returncode != 0:
        print(f"[run_pipeline_night] step{idx} FAILED rc={p.returncode}. see {log_path}")
        sys.exit(p.returncode)


def main():
    args = sys.argv[1:]
    test_mode = "--test" in args
    skip = set()
    for a in args:
        if a.startswith("--skip="):
            for s in a.split("=", 1)[1].split(","):
                if s.strip().isdigit():
                    skip.add(int(s.strip()))
    extra = ["--test"] if test_mode else []

    print(f"[run_pipeline_night] start at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[run_pipeline_night] test_mode={test_mode} skip={sorted(skip)}")

    # TTS env preflight (step2 skip 時は不要)
    if 2 not in skip:
        if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
            print("[run_pipeline_night] FATAL: GOOGLE_API_KEY / GEMINI_API_KEY env not set")
            print("  → .env か Task Scheduler 環境に key をセットしてから再実行してください")
            sys.exit(2)
        print("[run_pipeline_night] TTS env OK: Google Cloud TTS (Neural2-B)")
    else:
        print("[run_pipeline_night] step2 skipped → TTS env check bypassed")

    for i, (name, label) in enumerate(STEPS):
        if i in skip:
            print(f"[run_pipeline_night] SKIP step{i} {label}")
            continue
        # step0 だけ --test を渡す（他は --test 引数を見ない）
        step_extra = extra if name == "step0_gemini.py" else []
        # step5 は test_mode のとき --test
        if name == "step5_upload.py" and test_mode:
            step_extra = ["--test"]
        run_step(i, name, label, step_extra)

    print(f"\n[run_pipeline_night] complete at {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
