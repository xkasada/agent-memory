#!/usr/bin/env python3
"""Periodic maintenance of the memory vault (LLM Wiki).

Hybrid job:
  1. deterministic toolchain
     (doctor/project-ingest/build/lint/source-*/audit_public);
  2. the opencode agent runs the llm-wiki-maintain + llm-wiki-lint skills
     (judgment work: connect, stale, gaps, contradictions, shared vs project).

Intended to be run by Windows Task Scheduler every 3 hours (and manually):

    python scripts/maintain_vault.py            # full job (toolchain + agent)
    python scripts/maintain_vault.py --skip-agent   # toolchain only

Logs are written to <vault>/.runs/ (latest.log + a timestamped copy).
"""

import datetime
import os
import pathlib
import shutil
import subprocess
import sys

try:  # emit UTF-8 even under a legacy cp1251 console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VAULT = pathlib.Path(__file__).resolve().parent.parent
RUN_DIR = VAULT / ".runs"
RUN_DIR.mkdir(exist_ok=True)

SKIP_AGENT = "--skip-agent" in sys.argv

STAMP = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_PATH = RUN_DIR / f"maintain-{STAMP}.log"
LATEST = RUN_DIR / "latest.log"
_LOG = open(LOG_PATH, "w", encoding="utf-8", errors="replace")


def log(message=""):
    text = str(message)
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    _LOG.write(text + "\n")
    _LOG.flush()


def run(cmd, env=None):
    log("--- " + " ".join(str(c) for c in cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(VAULT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if proc.stdout:
        for line in proc.stdout.splitlines():
            log(line)
    log(f"    [exit {proc.returncode}]")
    return proc.returncode


def find_opencode():
    """Locate the native opencode binary (avoid the .cmd shim's quoting pitfalls)."""
    exe = shutil.which("opencode.exe")
    if exe:
        return exe
    appdata = os.environ.get("APPDATA", "")
    candidate = (
        pathlib.Path(appdata) / "npm" / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
    )
    if candidate.is_file():
        return str(candidate)
    return shutil.which("opencode")


def finish(code):
    _LOG.close()
    try:
        shutil.copyfile(LOG_PATH, LATEST)
    except OSError:
        pass
    sys.exit(code)


def main():
    log(f"== memory vault maintenance :: {STAMP} ==")
    log(f"vault : {VAULT}")
    log(f"python: {sys.executable}")

    child_env = dict(os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    py = sys.executable

    steps = [
        [py, "scripts/wiki_tool.py", "doctor"],
        [py, "scripts/wiki_tool.py", "project-ingest"],
        [py, "scripts/wiki_tool.py", "build"],
        [py, "scripts/wiki_tool.py", "lint"],
        [py, "scripts/wiki_tool.py", "source-scan", "--update", "--accept-covered"],
        [py, "scripts/wiki_tool.py", "source-lint"],
        [py, "scripts/wiki_tool.py", "source-delta"],
        [py, "scripts/audit_public.py", "--allow", ".obsidian/**", "--allow", ".runs/**"],
    ]

    failed = False
    for step in steps:
        if run(step, env=child_env) != 0:
            failed = True
    log("deterministic toolchain: " + ("SOME STEPS NON-ZERO" if failed else "OK"))

    if SKIP_AGENT:
        log("agent step skipped (--skip-agent)")
        finish(1 if failed else 0)

    opencode = find_opencode()
    if not opencode:
        log("opencode CLI not found — skipping agent step")
        finish(2)

    prompt = (
        f"Periodic maintenance of the memory vault (LLM Wiki) at {VAULT}. "
        "Read AGENTS.md, then the local skills "
        ".agents/skills/llm-wiki-maintain/SKILL.md and "
        ".agents/skills/llm-wiki-lint/SKILL.md and follow them. "
        "The deterministic toolchain "
        "(doctor/project-ingest/build/lint/source-scan/source-lint/source-delta/audit_public) "
        f"has already run; its output is in this log: {LOG_PATH}. "
        "Perform the judgment steps the tools cannot do: orphan pages, "
        "stale pages (set status: stale where appropriate), topic gaps "
        "(concepts mentioned in 3+ notes without their own page), missing "
        "cross-references, contradictions, and unsourced/provenance issues. "
        "For Raw/Projects/* sources, also decide shared vs project scope (promote "
        "reusable concepts/entities to Wiki/Concepts or Wiki/Entities with "
        "scope: shared) and actualize changed knowledge via a supersedes chain. "
        "Apply only well-justified edits, and only under Wiki/Concepts, Wiki/Entities, "
        "Wiki/Topics, Wiki/Logs (connections, statuses, prose). "
        "NEVER modify Raw/**, .obsidian/**, plans, or anything under Wiki/Projects/** "
        "(project pages are regenerated by project-ingest every run — edits there are "
        "lost; cross-reference projects only from global notes). "
        "If you changed anything, re-run: python scripts/wiki_tool.py build "
        "AND python scripts/wiki_tool.py lint until both are clean. "
        "Finish by appending a log entry: python scripts/wiki_tool.py log "
        '--title "maintain: auto-run" --details "<what changed>". '
        "Reply with a concise report: what was checked, what was changed, "
        "and what needs a human decision."
    )

    log("--- opencode run --auto --agent build (agent step) ---")
    agent_rc = run([opencode, "run", "--auto", "--agent", "build", prompt], env=child_env)
    log(f"--- agent step exit: {agent_rc} ---")
    log(f"== maintenance finished :: {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ==")
    finish(1 if failed else agent_rc)


def prune_logs(keep=30):
    logs = sorted(RUN_DIR.glob("maintain-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in logs[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    prune_logs()
    main()
