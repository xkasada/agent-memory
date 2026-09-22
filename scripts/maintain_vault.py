#!/usr/bin/env python3
"""Periodic maintenance of the memory vault (LLM Wiki).

Hybrid job:
  1. deterministic toolchain
     (doctor/project-ingest/build/lint/source-*/audit_public);
  2. Cursor Agent CLI (preferred) runs llm-wiki-maintain + llm-wiki-lint
     judgment work: connect, stale, gaps, contradictions, shared vs project.
     Optional fallback: OpenCode (`--agent opencode`).

Intended to be run by Windows Task Scheduler every 3 hours (and manually):

    python scripts/maintain_vault.py                 # toolchain + Cursor agent
    python scripts/maintain_vault.py --skip-agent    # toolchain only
    python scripts/maintain_vault.py --agent cursor  # default
    python scripts/maintain_vault.py --agent opencode
    python scripts/maintain_vault.py --agent none    # same as --skip-agent

Requires Cursor Agent CLI on PATH (`agent` or `cursor-agent`), authenticated
(`agent login` or CURSOR_API_KEY). Install: https://cursor.com/docs/cli/headless

Logs are written to <vault>/.runs/ (latest.log + a timestamped copy).
"""

from __future__ import annotations

import argparse
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


def run(cmd, env=None, timeout=None):
    log("--- " + " ".join(str(c) for c in cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(VAULT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        for line in out.splitlines():
            log(line)
        log(f"    [timeout after {timeout}s]")
        return 124
    if proc.stdout:
        for line in proc.stdout.splitlines():
            log(line)
    log(f"    [exit {proc.returncode}]")
    return proc.returncode


def finish(code):
    _LOG.close()
    try:
        shutil.copyfile(LOG_PATH, LATEST)
    except OSError:
        pass
    sys.exit(code)


def _which_exe(*names: str):
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def find_cursor_agent():
    """Locate Cursor Agent CLI (`agent` / `cursor-agent`).

    On Windows the installer drops shims under `%LOCALAPPDATA%\\cursor-agent\\`.
    Prefer `.ps1` over `.cmd` — `cmd.exe /c` truncates long prompts (~8191 chars).
    """
    found = _which_exe(
        "agent.exe", "cursor-agent.exe",
        "agent.ps1", "cursor-agent.ps1",
        "agent.cmd", "cursor-agent.cmd",
        "agent", "cursor-agent",
    )
    if found:
        return found
    home = pathlib.Path.home()
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        pathlib.Path(local) / "cursor-agent" / "agent.ps1",
        pathlib.Path(local) / "cursor-agent" / "cursor-agent.ps1",
        pathlib.Path(local) / "cursor-agent" / "agent.cmd",
        pathlib.Path(local) / "cursor-agent" / "cursor-agent.cmd",
        pathlib.Path(local) / "cursor-agent" / "agent.exe",
        pathlib.Path(local) / "Programs" / "cursor-agent" / "agent.exe",
        home / ".local" / "bin" / "agent.exe",
        home / ".local" / "bin" / "cursor-agent.exe",
        home / ".local" / "bin" / "agent",
        home / ".local" / "bin" / "cursor-agent",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def _agent_cmd(agent: str, *flags: str, prompt_file: pathlib.Path | None = None) -> list:
    """Build a subprocess argv that launches Windows shims without cmd length limits.

    When `prompt_file` is set, PowerShell reads the prompt from disk so we never
    hit the ~8191-char `cmd.exe` command-line cap.
    """
    path = pathlib.Path(agent)
    ps1 = path
    if path.suffix.lower() in (".cmd", ".bat"):
        sibling = path.with_suffix(".ps1")
        if sibling.is_file():
            ps1 = sibling

    if prompt_file is not None:
        script = ps1 if ps1.suffix.lower() == ".ps1" else path
        sc = str(script).replace("'", "''")
        pf = str(prompt_file).replace("'", "''")

        def _ps_quote(s: str) -> str:
            return "'" + s.replace("'", "''") + "'"

        flag_lit = " ".join(_ps_quote(f) for f in flags)
        command = (
            f"& {_ps_quote(str(script))} {flag_lit} -- "
            f"(Get-Content -LiteralPath {_ps_quote(str(prompt_file))} -Raw -Encoding utf8)"
        )
        return [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]

    if ps1.suffix.lower() == ".ps1":
        return [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            *flags,
        ]
    if path.suffix.lower() in (".cmd", ".bat"):
        return ["cmd.exe", "/c", str(path), *flags]
    return [agent, *flags]


def find_opencode():
    """Locate the native opencode binary (optional fallback)."""
    exe = shutil.which("opencode.exe") or shutil.which("opencode")
    if exe:
        return exe
    appdata = os.environ.get("APPDATA", "")
    candidate = (
        pathlib.Path(appdata) / "npm" / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
    )
    if candidate.is_file():
        return str(candidate)
    return None


def maintain_prompt(log_path: pathlib.Path) -> str:
    return (
        f"Periodic maintenance of the memory vault (LLM Wiki) at {VAULT}. "
        "Read AGENTS.md, then the local skills "
        ".agents/skills/llm-wiki-maintain/SKILL.md and "
        ".agents/skills/llm-wiki-lint/SKILL.md and follow them. "
        "The deterministic toolchain "
        "(doctor/project-ingest/build/lint/source-scan/source-lint/source-delta/audit_public) "
        f"has already run; its output is in this log: {log_path}. "
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


def run_cursor_agent(prompt: str, env: dict) -> int:
    agent = find_cursor_agent()
    if not agent:
        log("Cursor Agent CLI not found (`agent` / `cursor-agent` not on PATH).")
        log("Install: https://cursor.com/docs/cli/headless")
        log("Then authenticate: agent login   (or set CURSOR_API_KEY)")
        log("agent step skipped")
        return 2
    # Persist prompt to avoid Windows cmd.exe ~8191-char command-line limit.
    prompt_file = RUN_DIR / f"maintain-{STAMP}.prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    log(f"prompt file: {prompt_file}")
    cmd = _agent_cmd(
        agent,
        "-p",
        "--force",
        "--trust",
        "--output-format",
        "text",
        prompt_file=prompt_file,
    )
    log(f"--- cursor agent ({agent}) -p --force --trust (agent step) ---")
    # Judgment passes can be long; 30 min cap avoids hung workers forever.
    return run(cmd, env=env, timeout=30 * 60)


def run_opencode_agent(prompt: str, env: dict) -> int:
    opencode = find_opencode()
    if not opencode:
        log("opencode CLI not found — agent step skipped")
        return 2
    log("--- opencode run --auto --agent build (agent step) ---")
    return run([opencode, "run", "--auto", "--agent", "build", prompt], env=env)


def parse_args(argv):
    p = argparse.ArgumentParser(description="Memory vault maintenance (toolchain + agent)")
    p.add_argument(
        "--skip-agent",
        action="store_true",
        help="Run deterministic toolchain only (no Cursor/OpenCode agent)",
    )
    p.add_argument(
        "--agent",
        choices=("cursor", "opencode", "none"),
        default="cursor",
        help="Which agent backend to use after the toolchain (default: cursor)",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.skip_agent:
        args.agent = "none"

    log(f"== memory vault maintenance :: {STAMP} ==")
    log(f"vault : {VAULT}")
    log(f"python: {sys.executable}")
    log(f"agent : {args.agent}")

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

    if args.agent == "none":
        log("agent step skipped (--skip-agent / --agent none)")
        finish(1 if failed else 0)

    prompt = maintain_prompt(LOG_PATH)
    if args.agent == "cursor":
        agent_rc = run_cursor_agent(prompt, child_env)
    else:
        agent_rc = run_opencode_agent(prompt, child_env)

    log(f"--- agent step exit: {agent_rc} ---")
    log(f"== maintenance finished :: {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ==")
    # Missing agent CLI (2) should not mask toolchain failures, but if toolchain
    # is clean and only the agent is missing, surface 2 so schedulers can alert.
    if failed:
        finish(1)
    finish(agent_rc)


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
