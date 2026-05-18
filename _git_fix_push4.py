"""Fix push v4: save patched files, sync with origin/main, restore patched files, commit, push.
This abandons local d6154be and creates a fresh commit on top of origin/main."""
import os, subprocess, shutil
from pathlib import Path

ROOT = Path(r"C:\Users\user\Documents\10oku-project")
LOG = ROOT / "_git_fix_push4_log.txt"
HEAD = ROOT / "_git_fix_push4_head.txt"
DONE = ROOT / "_git_fix_push4_done.txt"

# Files to preserve (my patched versions)
PRESERVE = [
    "new-youtube-local/scripts/step3b_thumbnail.py",
    "new-youtube-local/scripts/step4_compile_night.py",
    "new-youtube-local/scripts/step3_video_clips.py",
    "new-youtube-local/scripts/step2_voice_voicevox.py",
    "new-youtube-local/scripts/gen_subtitle.py",
    "new-youtube-local/scripts/set_thumb_for_video.py",
    "new-youtube-local/run_pipeline_night.py",
    "new-youtube-local/output/state.json",
    "new-youtube-local/topics.json",
    "new-youtube-local/_resume_from_thumb.bat",
    "new-youtube-local/_go_night.bat",
    "new-youtube-local/_resume_night.bat",
    "new-youtube-local/_register_task_night.bat",
    "new-youtube-local/_kill_pipeline.bat",
    "new-youtube-local/_go_p003_full.bat",
    "new-youtube-local/.env.example",
]
BACKUP_DIR = ROOT / "_backup_for_push"

env = os.environ.copy()
env["GIT_TERMINAL_PROMPT"] = "0"


def run(cmd_list, label, timeout=180):
    LOG.open("a", encoding="utf-8").write(f"\n--- {label} ---\n$ {' '.join(cmd_list)}\n")
    try:
        p = subprocess.run(cmd_list, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        rc = p.returncode
    except subprocess.TimeoutExpired as e:
        out = f"TIMEOUT after {timeout}s"
        rc = -1
    log = LOG.open("a", encoding="utf-8")
    log.write(out)
    log.write(f"\nrc={rc}\n")
    log.close()
    return rc, out


def main():
    LOG.write_text("=== FIX PUSH 4 ===\n", encoding="utf-8")

    # 0. Save current versions of preserve files
    LOG.open("a", encoding="utf-8").write("\n--- backup files ---\n")
    BACKUP_DIR.mkdir(exist_ok=True)
    saved = []
    for relp in PRESERVE:
        src = ROOT / relp
        if not src.exists():
            LOG.open("a", encoding="utf-8").write(f"miss: {relp}\n")
            continue
        dst = BACKUP_DIR / relp.replace("/", "__")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        saved.append((relp, dst))
        LOG.open("a", encoding="utf-8").write(f"saved {relp} -> {dst.name}\n")

    # 1. Fetch
    run(["git", "fetch", "origin", "main"], "fetch")

    # 2. Reset hard to origin/main (abandons local d6154be)
    run(["git", "reset", "--hard", "origin/main"], "reset hard")

    # 3. Clean untracked (but preserve our backup dir + run logs + temp bats)
    run(["git", "clean", "-fd", "-e", "_backup_for_push", "-e", "_git_*", "-e", "_run_*",
         "-e", "_gpv*", "-e", "_kill_*", "-e", "_test_*", "-e", "_commit_push*",
         "-e", "_check_*", "-e", "_copy_*", "-e", "_diag_*", "-e", "_fetch_*",
         "-e", "_monitor_*", "-e", "_post_*", "-e", "_push_*", "-e", "_register_*",
         "-e", "_reset_*", "-e", "_setup_*", "-e", "_trigger_*", "-e", "_upload_*",
         "-e", "_set_*", "-e", "_install_*", "-e", "_python_path*",
         "-e", "_local_backup", "-e", "*.log", "-e", "*.txt",
         "-e", "GEMINI_HANDOFF*", "-e", "HANDOFF*",
         "-e", "new-youtube-local/output", "-e", "new-youtube-local/logs",
         "-e", "new-youtube-local/_*", "-e", "toi-suite-access-codes.json"], "clean")

    # 4. Restore preserved files
    LOG.open("a", encoding="utf-8").write("\n--- restore files ---\n")
    for relp, bak in saved:
        dst = ROOT / relp
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bak, dst)
        LOG.open("a", encoding="utf-8").write(f"restored {relp}\n")

    # 5. Stage them
    rc, _ = run(["git", "add"] + PRESERVE, "add preserved files")

    # 6. Commit
    run([
        "git", "commit", "-m",
        "feat(otona-night): VOICEVOX 冥鳴ひまり pipeline + step4 letterbox/14:30 cap + step3b Imagen fallback chain",
    ], "commit")

    # 7. Push
    rc_pu, _ = run(["git", "push", "origin", "main"], "push", timeout=180)

    # 8. Head
    _, head_out = run(["git", "rev-parse", "HEAD"], "head")
    head_sha = head_out.strip().split("\n")[0]
    HEAD.write_text(head_sha + "\n", encoding="utf-8")
    DONE.write_text(f"push_rc={rc_pu}\nhead={head_sha}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
