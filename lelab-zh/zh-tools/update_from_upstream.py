#!/usr/bin/env python3
"""Pull the latest official LeLab into lelab-zh/ and keep the 中文/EN toggle working.

Run from anywhere inside the repository, with a clean working tree:

    python lelab-zh/zh-tools/update_from_upstream.py            # official main
    python lelab-zh/zh-tools/update_from_upstream.py --ref v0.2  # a tag or branch

What it does:
1. git subtree pull --squash from https://github.com/huggingface/leLab.git
2. The add-on only adds files and one import line to frontend/src/main.tsx. If upstream
   edited the same spot, that file conflicts; the script takes upstream's version and puts
   the import line back. A conflict in any other file stops the script for a human to look at.
3. Makes sure the import line is still there, then lists English strings the update added
   (node frontend/scripts/i18n-check.mjs). Add those to frontend/src/i18n/zh-TW.json.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

UPSTREAM = "https://github.com/huggingface/leLab.git"
PREFIX = "lelab-zh"
MAIN_TSX = f"{PREFIX}/frontend/src/main.tsx"
IMPORT_LINE = "import './i18n' // zh-TW add-on (中文/EN toggle), see I18N.zh-TW.md"


def git(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], check=check, text=True, encoding="utf-8",
                          stdout=subprocess.PIPE if capture else None, stderr=subprocess.STDOUT if capture else None)


def ensure_import(root: Path) -> bool:
    """Put the add-on import back at the top of main.tsx. Returns True if the file changed."""
    path = root / MAIN_TSX
    if not path.exists():
        sys.exit(f"!! {MAIN_TSX} no longer exists upstream. Find LeLab's new entry file and add this line at its top:\n   {IMPORT_LINE}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if any(l.strip().startswith("import './i18n'") or l.strip().startswith('import "./i18n"') for l in lines):
        return False
    path.write_text("\n".join([IMPORT_LINE, *lines]) + "\n", encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", default="main", help="upstream branch or tag (default: main)")
    ap.add_argument("--repo", default=UPSTREAM, help="upstream repository URL or path")
    args = ap.parse_args()

    root = Path(git("rev-parse", "--show-toplevel").stdout.strip())
    import os
    os.chdir(root)
    if git("status", "--porcelain").stdout.strip():
        sys.exit("!! Commit or stash your changes first; the working tree must be clean.")

    print(f"== Pulling {args.repo} {args.ref} into {PREFIX}/ ...")
    pull = git("subtree", "pull", f"--prefix={PREFIX}", args.repo, args.ref, "--squash",
               "-m", f"Merge upstream LeLab {args.ref} into {PREFIX}", check=False)
    print(pull.stdout.strip())

    conflicted = [p for p in git("diff", "--name-only", "--diff-filter=U").stdout.split() if p]
    if pull.returncode != 0 and not conflicted:
        sys.exit("!! git subtree pull failed (see above). Nothing was changed.")
    if conflicted:
        others = [p for p in conflicted if p != MAIN_TSX]
        if others:
            sys.exit("!! Conflicts outside main.tsx; the zh add-on never edits these, so check them by hand:\n   "
                     + "\n   ".join(others) + "\n   Resolve, `git add`, then `git commit`. Or undo with `git merge --abort`.")
        print(f"== {MAIN_TSX} conflicted (upstream edited the same lines). Taking upstream's version and re-adding the import.")
        git("checkout", "--theirs", "--", MAIN_TSX)
        ensure_import(root)
        git("add", MAIN_TSX)
        git("commit", "--no-edit")
    elif ensure_import(root):
        print(f"== Upstream dropped the add-on import; re-adding it to {MAIN_TSX}.")
        git("add", MAIN_TSX)
        git("commit", "-m", "lelab-zh: re-add the zh-TW add-on import after upstream merge")

    print("== Merge done:", git("log", "--oneline", "-1").stdout.strip())
    checker = root / PREFIX / "frontend/scripts/i18n-check.mjs"
    if shutil.which("node") and (root / PREFIX / "frontend/node_modules/typescript").exists():
        print("== Strings the update added (translate them in frontend/src/i18n/zh-TW.json):")
        subprocess.run(["node", str(checker)], check=False)
    else:
        print(f"== To list new English strings: cd {PREFIX}/frontend && npm ci && node scripts/i18n-check.mjs")


if __name__ == "__main__":
    main()
