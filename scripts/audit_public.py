#!/usr/bin/env python3
"""audit_public.py -- fail on material that must not be published.

Checks a tree for:
  * obvious secrets (API keys, tokens, passwords, cloud credentials)
  * machine-local paths (C:\\Users\\..., /Users/..., /home/...)
  * private keys (PEM/OpenSSH/PGP blocks)
  * plugin / cache state (node_modules, __pycache__, .obsidian, .venv, .env, ...)

Derived/cache paths are ignored by default (DEFAULT_ALLOW: VCS/cache dirs and
`Raw/Projects/*/packs/**`). Reviewed exceptions live in `Schema/audit-allow.txt`
(one glob per line); `--allow GLOB` adds one-off exemptions.

Exit code is non-zero when any finding is reported. Stdlib only.

Usage:
  python3 scripts/audit_public.py [ROOT] [--allow GLOB]... [--quiet]
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(os.environ.get("WIKI_ROOT") or Path(__file__).resolve().parent.parent).resolve()

SECRET_PATTERNS = [
    re.compile(r"""(?i)\b(aws_secret_access_key|aws_access_key_id|secret[_-]?key|api[_-]?key|access[_-]?token|auth[_-]?token|refresh[_-]?token|client[_-]?secret|private[_-]?key|password|passwd|pwd)\b\s*[:=]\s*['"]?([A-Za-z0-9/+_\-]{6,})"""),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"),
    re.compile(r"(?i)\b(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})"),
]
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
LOCAL_PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"),
    re.compile(r"[A-Za-z]:/Users/[^/\s]+"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"\\\\Users\\\\[^\\\s]+"),
]

CACHE_DIRS = {
    "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", ".obsidian", ".ipynb_checkpoints", ".cache", ".tox",
    ".gradle", ".idea", ".vscode-server", "dist", "build",
}
CACHE_FILES = {".DS_Store", "Thumbs.db", ".coverage", ".env"}
CACHE_SUFFIXES = (".pyc", ".pyo", ".swp", ".swo")
PRUNE_SILENT = {".git"}

DEFAULT_ALLOW = {
    ".git/", ".git/**",
    ".obsidian/", ".obsidian/**",
    ".runs/", ".runs/**",
    "**/__pycache__/", "**/__pycache__/**",
    ".pytest_cache/", ".pytest_cache/**",
    ".mypy_cache/", ".mypy_cache/**",
    ".ruff_cache/", ".ruff_cache/**",
    ".venv/", ".venv/**", "venv/", "venv/**",
    "Raw/Projects/*/packs/", "Raw/Projects/*/packs/**",
}

MAX_BYTES = 1_000_000
SNIPPET = 120
ALLOW_FILE = "Schema/audit-allow.txt"


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(4096)
    except OSError:
        return True
    return b"\x00" in chunk


def allowed(rel_path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(rel_path, pat) for pat in patterns)


def load_allow_file(root: Path):
    """Read optional `Schema/audit-allow.txt`: one glob per line, `#` comments."""
    path = root / ALLOW_FILE
    if not path.is_file():
        return []
    patterns = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def find_content_issues(rel_path: str, text: str):
    issues = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for pat in SECRET_PATTERNS:
            if pat.search(line):
                issues.append(("secret", lineno, line))
                break
        else:
            if PRIVATE_KEY_PATTERN.search(line):
                issues.append(("private-key", lineno, line))
        for pat in LOCAL_PATH_PATTERNS:
            if pat.search(line):
                issues.append(("machine-local-path", lineno, line))
                break
    return issues


def scan(root: Path, allow_patterns, findings):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = ""
        if Path(dirpath) != root:
            rel_dir = str(Path(dirpath).relative_to(root)).replace(os.sep, "/")
        dirnames[:] = sorted(d for d in dirnames if d not in PRUNE_SILENT
                             and not d.endswith(".egg-info"))
        # `packs/` under mirrored projects are derived by-products — never published.
        if rel_dir.startswith("Raw/Projects") and "packs" in dirnames:
            dirnames.remove("packs")
        for d in list(dirnames):
            rel_d = str(Path(dirpath, d).relative_to(root)).replace(os.sep, "/")
            if d in CACHE_DIRS and not allowed(rel_d + "/", allow_patterns):
                findings.append(("plugin-cache-state", rel_d + "/", 0, d))
                dirnames.remove(d)

        for fname in sorted(filenames):
            fpath = Path(dirpath, fname)
            rel_f = fpath.relative_to(root).as_posix()
            if allowed(rel_f, allow_patterns):
                continue
            if fname in CACHE_FILES or fname.endswith(CACHE_SUFFIXES):
                findings.append(("plugin-cache-state", rel_f, 0, fname))
                continue
            if fpath.is_symlink():
                continue
            try:
                if fpath.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            if is_binary(fpath):
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="strict")
            except (OSError, UnicodeDecodeError):
                try:
                    text = fpath.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
            for kind, lineno, line in find_content_issues(rel_f, text):
                findings.append((kind, rel_f, lineno, line.strip()[:SNIPPET]))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fail on material that must not be published.")
    parser.add_argument("root", nargs="?", default=str(DEFAULT_ROOT), help="tree to audit")
    parser.add_argument("--allow", action="append", default=[], metavar="GLOB",
                        help="path glob to ignore (repeatable), relative to root")
    parser.add_argument("--quiet", action="store_true", help="print only the summary")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    allow_patterns = list(DEFAULT_ALLOW) + load_allow_file(root) + list(args.allow)
    try:
        script_rel = Path(__file__).resolve().relative_to(root).as_posix()
        allow_patterns.append(script_rel)
    except ValueError:
        pass

    if not root.is_dir():
        print(f"audit_public: not a directory: {root}", file=sys.stderr)
        return 2

    findings = []
    scan(root, allow_patterns, findings)

    if findings and not args.quiet:
        for kind, rel_path, lineno, snippet in findings:
            loc = f"{rel_path}:{lineno}" if lineno else rel_path
            print(f"[{kind}] {loc}")
            if snippet and lineno:
                print(f"    {snippet}")

    counts = {}
    for kind, *_ in findings:
        counts[kind] = counts.get(kind, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "clean"
    print(f"audit_public: {len(findings)} finding(s) [{summary}] in {root}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
