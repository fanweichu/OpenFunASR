#!/usr/bin/env python3
"""Review publishable files without echoing any matching sensitive values."""
from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = {".git", ".venv", ".cache", "__pycache__", "runtime-assets", "backups", "benchmark-results", "fixtures"}
SUFFIXES = {".py", ".sh", ".md", ".json", ".txt", ".plist", ".cnf", ".yml", ".yaml"}
PATTERNS = {
    "absolute user path": re.compile(r"(?:/Users|/home)/[A-Za-z0-9_.-]+|[A-Z]:\\Users\\[A-Za-z0-9_.-]+"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "access token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16})\b"),
    "email address": re.compile(r"\b[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}


def publishable_files() -> list[Path]:
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True)
    if top.returncode == 0 and Path(top.stdout.strip()).resolve() == ROOT:
        files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT)
        return sorted({ROOT / os.fsdecode(name) for name in files.split(b"\0") if name})
    return sorted(p for p in ROOT.rglob("*") if p.is_file() and not any(
        part in EXCLUDED or part.startswith(("build-", "dist-")) for part in p.relative_to(ROOT).parts
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forbid", action="append", default=[], help="Additional private name/value; matches are never printed")
    args = parser.parse_args()
    private_names = {getpass.getuser(), Path.home().name, *args.forbid}
    try:
        import pwd
        private_names.add(pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0])
    except (ImportError, KeyError):
        pass
    private_names = {s.casefold() for s in private_names if len(s.strip()) >= 4 and s.casefold() not in {"root", "openfunasr"}}
    problems = []
    files = publishable_files()
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True)
    own_repository = top.returncode == 0 and Path(top.stdout.strip()).resolve() == ROOT
    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED or part.startswith(("build-", "dist-")) for part in relative.parts):
            problems.append((relative, 0, "private/generated file is tracked"))
        if path.is_symlink() or path.suffix not in SUFFIXES and path.name not in {".gitignore", "LICENSE"}:
            problems.append((relative, 0, "unexpected file type"))
            continue
        if not path.exists():
            problems.append((relative, 0, "tracked deletion must be staged"))
            continue
        if path.stat().st_size > 1024 * 1024:
            problems.append((relative, 0, "unexpected large file"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append((relative, 0, "binary data"))
            continue
        versions = [("working tree", content)]
        if own_repository:
            staged = subprocess.run(["git", "show", f":{relative}"], cwd=ROOT, capture_output=True)
            if staged.returncode == 0:
                try:
                    versions.append(("Git index", staged.stdout.decode("utf-8")))
                except UnicodeDecodeError:
                    problems.append((relative, 0, "binary data in Git index"))
        for version, text in versions:
            for number, line in enumerate(text.splitlines(), 1):
                for label, pattern in PATTERNS.items():
                    matches = list(pattern.finditer(line))
                    if label == "email address":
                        matches = [m for m in matches if not m.group().endswith(".invalid")]
                    if matches:
                        problems.append((relative, number, f"{label} ({version})"))
                if any(name in line.casefold() for name in private_names):
                    problems.append((relative, number, f"private account/name ({version})"))
        if any(name in str(relative).casefold() for name in private_names):
            problems.append(("<redacted filename>", 0, "private name in filename"))
    for relative, number, reason in problems:
        display = str(relative)
        if any(name in display.casefold() for name in private_names):
            display = "<redacted filename>"
        print(f"FAIL {display}:{number}: {reason}")
    if problems:
        raise SystemExit(1)
    print(f"Privacy scan passed: {len(files)} publishable text files; no matches in configured checks.")
    print("Before a public push, also review Git author metadata, remote URLs and the complete staged diff.")


if __name__ == "__main__":
    main()
