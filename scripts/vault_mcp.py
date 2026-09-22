#!/usr/bin/env python3
"""vault_mcp.py -- minimal MCP (Model Context Protocol) server for the memory vault.

Speaks JSON-RPC 2.0 over stdio (newline-delimited). Read tools search/read the
compiled wiki. Write tools: `stage_note` drops/overwrites a note under
`Raw/Projects/<project>/` (optionally under a component/module folder),
`project_ingest` compiles Raw/Projects into Wiki and rebuilds the catalog, and
`log` appends to Wiki/log.md. Writes take a global lock (Schema/.vault.lock);
reads do not.

Tools
-----
  search_catalog(query, project?, limit?)              search Wiki/catalog.jsonl
  read_note(path)                                      read a Wiki/ or Raw/ markdown file
  read_project(project)                                anchor + component list for a project
  list_recent(limit?)                                  recently updated compiled notes
  stage_note(project, kind, name, body, component?)    write/overwrite a raw project note (locked)
  project_ingest(project?)                             compile Raw/Projects -> Wiki + rebuild catalog
  log(title, details?)                                 append to Wiki/log.md (locked)

Stdlib only. Configure an MCP client with:  python scripts/vault_mcp.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import wiki_tool as wt  # noqa: E402  (same directory)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "memory-vault"
SERVER_VERSION = "0.2.0"
LOCK = wt.SCHEMA / ".vault.lock"
PROJECT_SUB = {
    "context": "",
    "index": "",
    "domain": "domains",
    "entity": "entities",
    "layer": "layers",
    "contract": "contracts",
    "tech": "tech",
    "module": "modules",
    "artifact": "artifacts",
}
# Folder names reserved for kinds — cannot be used as component/module ids.
RESERVED_COMPONENT_NAMES = frozenset(
    list(PROJECT_SUB.values()) + list(wt.PROJECT_SUB_KIND) + ["packs", ""]
)
SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-()]*$")


def _kind_sub(kind: str) -> str:
    """Map a raw kind to its kind-folder under the project or component.

    Canonical kinds (see PROJECT_SUB) map to their folder; a bare folder name
    (`domains`, `modules`, or a generic `partitions`) is used as-is. Returns ''
    for a top-level note (context/index/module-at-component-root).
    """
    if kind in PROJECT_SUB:
        return PROJECT_SUB[kind]
    if kind in wt.PROJECT_SUB_KIND or wt.valid_project_raw_kind(kind):
        return kind
    return ""


def _kind_norm(kind: str, sub: str, *, under_component: bool = False) -> str:
    """Normalize the frontmatter `kind` so it matches the folder-derived kind."""
    if under_component and kind == "module":
        return "module"
    if sub == "":
        if under_component and kind in ("index", "module", "context"):
            return "module" if kind in ("index", "module") else "context"
        return kind if kind in ("context", "index") else "context"
    return wt.PROJECT_SUB_KIND.get(sub, sub)


def _stage_out_path(project: str, kind: str, name: str, component: str = "") -> tuple[Path, str]:
    """Resolve output path + frontmatter kind for stage_note.

    Without component:
      index/context → Raw/Projects/<project>/<name>.md
      domain        → Raw/Projects/<project>/domains/<name>.md
      module        → Raw/Projects/<project>/modules/<name>.md

    With component (monorepo service / SPA / future backend):
      module|index  → Raw/Projects/<project>/<component>/<name>.md  (usually INDEX)
      domain        → Raw/Projects/<project>/<component>/domains/<name>.md
      …same for entity/layer/contract/tech/artifact
    """
    sub = _kind_sub(kind)
    under = bool(component)
    if under and kind in ("module", "index", "context"):
        # Component shell notes live at the component root, not under modules/.
        sub = ""
    kind_norm = _kind_norm(kind, sub, under_component=under)
    base = wt.RAW_PROJECTS / project
    if component:
        base = base / component
    out = (base / sub / f"{name}.md") if sub else (base / f"{name}.md")
    return out, kind_norm


# --------------------------------------------------------------------------- #
# lock
# --------------------------------------------------------------------------- #
def acquire_lock(timeout: float = 30.0):
    start = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return
        except FileExistsError:
            if time.time() - start > timeout:
                raise RuntimeError("vault lock timeout")
            time.sleep(0.25)


def release_lock():
    try:
        LOCK.unlink()
    except OSError:
        pass


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# tools
# --------------------------------------------------------------------------- #
def tool_search_catalog(query: str, project: str = "", limit: int = 20):
    if not wt.CATALOG.exists():
        return "catalog missing (run: wiki_tool.py build)"
    needle = (query or "").lower()
    hits = []
    for row in wt.read_jsonl(wt.CATALOG):
        if project and str(row.get("project", "")) != project:
            continue
        hay = " ".join([
            str(row.get("title", "")), str(row.get("tag", "")),
            str(row.get("project", "")), " ".join(map(str, row.get("topics") or [])),
            str(row.get("path", "")),
        ]).lower()
        if needle in hay:
            hits.append(row)
        if len(hits) >= max(1, limit):
            break
    if not hits:
        return f"no notes matched '{query}'"
    out = [f"{len(hits)} match(es) for '{query}':"]
    for r in hits:
        tag = r.get("tag") or "?"
        proj = r.get("project") or ""
        suffix = f" [{proj}]" if proj else ""
        out.append(f"- [[{r.get('title')}]] ({tag}){suffix} — {r.get('path')}")
    return "\n".join(out)


def _safe_rel(path: str):
    rel = str(path).replace("\\", "/").lstrip("/")
    target = (wt.ROOT / rel).resolve()
    if not str(target).startswith(str(wt.ROOT)):
        raise ValueError("path escapes vault")
    if not (rel.startswith("Wiki/") or rel.startswith("Raw/")):
        raise ValueError("only Wiki/ and Raw/ may be read")
    return target


def tool_read_note(path: str):
    target = _safe_rel(path)
    if not target.is_file():
        return f"not found: {path}"
    return wt.read_text(target)


def tool_read_project(project: str):
    if not SAFE.match(project or ""):
        return "invalid project name"
    anchor_dir = wt.WIKI_PROJECTS / project
    if not anchor_dir.exists():
        return f"no compiled project '{project}'"
    lines = [f"# Project {project}", ""]
    anchor = anchor_dir / f"{project}.md"
    if anchor.exists():
        lines.append("## Anchor")
        lines.append(wt.read_text(anchor))
        lines.append("")
    lines.append("## Components")
    for p in sorted(anchor_dir.rglob("*.md")):
        if p.name == "index.md" or p == anchor:
            continue
        lines.append(f"- {wt.rel(p)}")
    return "\n".join(lines)


def tool_list_recent(limit: int = 15):
    if not wt.CATALOG.exists():
        return "catalog missing (run: wiki_tool.py build)"
    rows = wt.read_jsonl(wt.CATALOG)
    rows.sort(key=lambda r: str(r.get("updated", "")), reverse=True)
    out = []
    for r in rows[: max(1, limit)]:
        proj = r.get("project") or ""
        suffix = f" [{proj}]" if proj else ""
        out.append(f"- [[{r.get('title')}]] ({r.get('tag')}){suffix} — {r.get('updated')}")
    return "\n".join(out) or "no notes"


def tool_stage_note(project: str, kind: str, name: str, body: str, component: str = ""):
    if not SAFE.match(project or ""):
        return "invalid project name"
    if not wt.valid_project_raw_kind(kind or ""):
        return (
            f"invalid kind '{kind}' "
            "(use context|index|domain|entity|layer|contract|tech|module|artifact "
            "or a folder name such as domains/entities/partitions)"
        )
    if not SAFE.match(name or ""):
        return "invalid note name"
    component = (component or "").strip()
    if component:
        if not SAFE.match(component):
            return "invalid component name"
        if component.lower() in {r.lower() for r in RESERVED_COMPONENT_NAMES if r}:
            return (
                f"component '{component}' collides with a kind folder; "
                "use a service/module id (e.g. vue-project, auth-service)"
            )
    out, kind_norm = _stage_out_path(project, kind, name, component)
    title = name
    header = (
        "---\n"
        f'Title: "{title}"\n'
        'Author: "mcp"\n'
        f'Reference: "project:{project}"\n'
        "ContentType:\n"
        '  - "markdown"\n'
        f"Created: {_now()}\n"
        "Processed: false\n"
        'tags:\n'
        '  - "source"\n'
        f'project: "{project}"\n'
        f'kind: "{kind_norm}"\n'
        "---\n"
    )
    acquire_lock()
    try:
        existed = out.exists()
        # Raw/Projects/ is a refreshable mirror of project context: overwrite is
        # allowed here (unlike Raw/Sources/, which stays strictly write-once).
        wt.write_text(out, header + "\n" + (body or "").lstrip("\n"))
    finally:
        release_lock()
    return f"{'updated' if existed else 'staged'}: {wt.rel(out)}"


def tool_project_ingest(project: str = ""):
    """Normalize + compile Raw/Projects into Wiki/Projects and rebuild the catalog.

    Lets the context-curator make freshly staged raw notes searchable in the wiki
    immediately, without waiting for the scheduled maintenance job.
    """
    if project and not SAFE.match(project):
        return "invalid project name"
    acquire_lock()
    try:
        names = sorted({
            wt.raw_project_name(s["rel"]) for s in wt.collect_sources()
            if s.get("area") == "projects"
        })
        if project:
            names = [n for n in names if n == project]
        if not names:
            return f"project-ingest: no raw notes for {project or 'any project'}"
        compiled = 0
        captured = 0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            for name in names:
                for s in wt._project_raw_notes(name):
                    if not wt.valid_project_raw_kind(wt.raw_project_kind(s["rel"])):
                        continue
                    if wt.normalize_project_raw(s["path"], s["rel"], False) in ("normalized", "ok"):
                        captured += 1
                compiled += wt.compile_project(name, False)
            wt.cmd_build(None)
    finally:
        release_lock()
    return (
        f"project-ingest: {len(names)} project(s) [{', '.join(names)}]; "
        f"captured {captured} raw, compiled {compiled} note(s); catalog rebuilt"
    )


def tool_log(title: str, details: str = ""):
    acquire_lock()
    try:
        entry = f"## [{_now()}] {title}\n"
        if details:
            entry += f"- {details}\n"
        entry += "\n"
        if not wt.WIKI_LOG.exists():
            wt.write_text(wt.WIKI_LOG, "# Log\n\nAppend-only. Entries: `## [YYYY-MM-DD] Title`.\n\n---\n\n")
        with wt.WIKI_LOG.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(entry)
    finally:
        release_lock()
    return f"logged: {title}"


TOOLS = {
    "search_catalog": {
        "description": "Search compiled wiki notes via Wiki/catalog.jsonl. Run before reading broad Raw context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "project": {"type": "string", "description": "restrict to this project"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
        "fn": lambda a: tool_search_catalog(a.get("query", ""), a.get("project", ""), a.get("limit", 20)),
    },
    "read_note": {
        "description": "Read a compiled Wiki/ note or a Raw/ source file (path relative to vault root).",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        "fn": lambda a: tool_read_note(a["path"]),
    },
    "read_project": {
        "description": "Read a project's compiled knowledge: anchor note plus its component list.",
        "inputSchema": {"type": "object", "properties": {"project": {"type": "string"}}, "required": ["project"]},
        "fn": lambda a: tool_read_project(a["project"]),
    },
    "list_recent": {
        "description": "List recently updated compiled notes.",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 15}}},
        "fn": lambda a: tool_list_recent(a.get("limit", 15)),
    },
    "stage_note": {
        "description": (
            "Write/overwrite a raw project note under Raw/Projects/<project>/ "
            "for project-ingest to compile (locked). "
            "kind: context|index|domain|entity|layer|contract|tech|module|artifact "
            "or a folder name. "
            "Optional component: monorepo service/SPA id (vue-project, auth-service) — "
            "writes Raw/Projects/<project>/<component>/<kind-folder>/<name>.md "
            "(module|index → <component>/INDEX.md). "
            "Without component, kinds land at the project root as before. "
            "Raw/Projects is a refreshable mirror (overwrite allowed)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "kind": {"type": "string"},
                "name": {"type": "string"},
                "body": {"type": "string"},
                "component": {
                    "type": "string",
                    "description": (
                        "Optional module/service folder under the project "
                        "(e.g. vue-project, item-info-service). "
                        "Each component has its own domains/entities/layers/…"
                    ),
                },
            },
            "required": ["project", "kind", "name", "body"],
        },
        "fn": lambda a: tool_stage_note(
            a["project"], a["kind"], a["name"], a.get("body", ""), a.get("component", "")
        ),
    },
    "project_ingest": {
        "description": (
            "Normalize + compile Raw/Projects/<project>/ into Wiki/Projects and rebuild "
            "the catalog, so freshly staged raw notes become searchable immediately. "
            "Omit project to ingest all projects."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}},
        },
        "fn": lambda a: tool_project_ingest(a.get("project", "")),
    },
    "log": {
        "description": "Append an entry to Wiki/log.md (locked).",
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "details": {"type": "string"}},
            "required": ["title"],
        },
        "fn": lambda a: tool_log(a["title"], a.get("details", "")),
    },
}


# --------------------------------------------------------------------------- #
# JSON-RPC / MCP loop
# --------------------------------------------------------------------------- #
def reply(msg_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\n")
    sys.stdout.flush()


def error(msg_id, code, message):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}) + "\n")
    sys.stdout.flush()


def handle(msg):
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}
    if method == "initialize":
        reply(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    elif method in ("notifications/initialized", "initialized"):
        return
    elif method == "ping":
        reply(msg_id, {})
    elif method == "tools/list":
        reply(msg_id, {
            "tools": [
                {"name": n, "description": t["description"], "inputSchema": t["inputSchema"]}
                for n, t in TOOLS.items()
            ]
        })
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if not tool:
            error(msg_id, -32602, f"unknown tool '{name}'")
            return
        try:
            text = tool["fn"](args)
            reply(msg_id, {"content": [{"type": "text", "text": str(text)}], "isError": False})
        except Exception as exc:  # noqa: BLE001
            reply(msg_id, {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True})
    elif msg_id is not None:
        error(msg_id, -32601, f"method not found: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            handle(msg)
        except Exception as exc:  # noqa: BLE001
            if msg.get("id") is not None:
                error(msg["id"], -32603, str(exc))


if __name__ == "__main__":
    main()
