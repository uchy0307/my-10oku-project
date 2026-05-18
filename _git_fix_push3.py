"""Fix push v3: stash only the 6 conflicting files (not whole tree),
then merge origin/main, then push. Avoids 'file locked' stash failure."""
import os, subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\user\Documents\10oku-project")
LOG = ROOT / "_git_fix_push3_log.txt"
HEAD = ROOT / "_git_fix_push3_head.txt"
DONE = ROOT / "_git_fix_push3_done.txt"

CONFLICT_FILES = [
    ".github/workflows/youtube_auto.yml",
    "new-youtube-local/scripts/step3_images_imagen.py",
    "new-youtube-local/scripts/step5_upload.py",
    "youtube/scripts/compile_video.mjs",
    "youtube/scripts/generate_script.mjs",
    "youtube/scripts/generate_voice.mjs",
]

env = os.environ.copy()
env["GIT_TERMINAL_PROMPT"] = "0"


def run(cmd_list, label, timeout=120):
    LOG.open("a", encoding="utf-8").write(f"\n--- {label} ---\n$ {' '.join(cmd_list)}\n")
    try:
        p = subprocess.run(cmd_list, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        rc = p.returncode
    except subprocess.TimeoutExpired as e:
        out = f"TIMEOUT after {timeout}s: {e}"
        rc = -1
    log = LOG.open("a", encoding="utf-8")
    log.write(out)
    log.write(f"\nrc={rc}\n")
    log.close()
    return rc, out


def main():
    LOG.write_text("=== FIX PUSH 3 ===\n", encoding="utf-8")
    # 1. stash ONLY the conflict files (pathspec stash)
    run(["git", "stash", "push", "-m", "conflicts-only", "--"] + CONFLICT_FILES, "stash conflicts")
    # 2. fetch
    run(["git", "fetch", "origin", "main"], "fetch")
    # 3. merge (since rebase needs clean tree)
    rc_m, _ = run(["git", "merge", "origin/main", "--no-edit"], "merge")
    if rc_m != 0:
        # try with allow-unrelated-histories
        run(["git", "merge", "--abort"], "merge abort")
        rc_m, _ = run(["git", "rebase", "origin/main"], "rebase fallback")
        if rc_m != 0:
            run(["git", "rebase", "--abort"], "rebase abort")
    # 4. push
    rc_pu, _ = run(["git", "push", "origin", "main"], "push", timeout=180)
    # 5. unstash
    run(["git", "stash", "pop"], "stash pop")
    # 6. head
    _, head_out = run(["git", "rev-parse", "HEAD"], "head")
    head_sha = head_out.strip().split("\n")[0]
    HEAD.write_text(head_sha + "\n", encoding="utf-8")
    DONE.write_text(f"push_rc={rc_pu}\nhead={head_sha}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
