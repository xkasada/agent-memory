#!/usr/bin/env python3
"""wiki_tool.py -- stdlib-only toolkit for the memory vault (LLM Wiki pattern).

Commands
--------
  doctor           Non-mutating health check (folders, python, catalog, manifest, counts).
  build            Generate Wiki/catalog.jsonl, Wiki/index.md and per-folder index files.
  lint             Validate compiled Wiki notes (allowed tags, source_count, source links).
  source-scan      List Raw sources; --update writes Schema/source-manifest.jsonl.
  source-lint      Validate Raw source frontmatter and coverage state.
  source-delta     Show Raw sources missing from the manifest.
  source-coverage  Show which Raw sources are covered by compiled Wiki notes.
  project-ingest   Capture (normalize) Raw/Projects notes, then compile them into Wiki/Projects/.
  search-catalog   Search compiled Wiki notes via the catalog (--query TEXT).
  log              Append a short entry to Wiki/log.md (--title ... [--details ...]).

The vault root is the parent of this script's directory, or $WIKI_ROOT if set.
Only the Python standard library is used.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_PY = (3, 8)

ROOT = Path(os.environ.get("WIKI_ROOT") or Path(__file__).resolve().parent.parent).resolve()

RAW = ROOT / "Raw"
RAW_SOURCES = RAW / "Sources"
RAW_FILES = RAW / "Files"
RAW_PROJECTS = RAW / "Projects"
WIKI = ROOT / "Wiki"
WIKI_PROJECTS = WIKI / "Projects"
SCHEMA = ROOT / "Schema"
CATALOG = WIKI / "catalog.jsonl"
WIKI_INDEX = WIKI / "index.md"
WIKI_LOG = WIKI / "log.md"
MANIFEST = SCHEMA / "source-manifest.jsonl"

KIND_FOLDER = {
    "topic": "Topics",
    "concept": "Concepts",
    "entity": "Entities",
    "project": "Projects",
    "log": "Logs",
}

# Raw/Projects/<name>/<sub>/<file>.md -> compiled kind. `packs` are derived and skipped.
PROJECT_SUB_KIND = {
    "domains": "domain",
    "entities": "entity",
    "layers": "layer",
    "contracts": "contract",
    "tech": "tech",
    "modules": "module",
    "artifacts": "artifact",
}
PROJECT_RAW_KINDS = (
    "index", "context", "domain", "entity", "layer", "contract", "tech",
    "module", "artifact",
)


def valid_project_raw_kind(kind: str) -> bool:
    """Known kind, or any generic project subfolder name (e.g. `partitions`)."""
    if kind in PROJECT_RAW_KINDS:
        return True
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]*", kind or ""))
# raw kind -> compiled note tag
PROJECT_KIND_TAG = {
    "index": "project",
    "context": "concept",
    "domain": "concept",
    "layer": "concept",
    "contract": "concept",
    "tech": "concept",
    "module": "concept",
    "artifact": "concept",
    "entity": "entity",
}
PROJECT_COMPILED_TAGS = ("project", "concept", "entity")
SOURCE_PREFIXES = ("Raw/Sources/", "Raw/Projects/")
ALLOWED_TAGS = tuple(KIND_FOLDER.keys())
FOLDER_KIND = {v: k for k, v in KIND_FOLDER.items()}
SECTION_TITLE = {
    "topic": "Topics",
    "concept": "Concepts",
    "entity": "Entities",
    "project": "Projects",
    "log": "Logs",
}
SOURCE_REQUIRED_KEYS = ("Title", "Reference", "Created", "Processed", "tags")

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# generic helpers
# --------------------------------------------------------------------------- #
def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def strip_scalar(value):
    v = value.strip()
    if v == "":
        return ""
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    low = v.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def parse_scalar(value):
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [strip_scalar(x) for x in inner.split(",")]
    return strip_scalar(v)


def parse_frontmatter(text):
    """Return (data | None, body, error | None)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, "missing frontmatter"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, text, "unterminated frontmatter"
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])
    data = {}
    i = 0
    while i < len(fm_lines):
        line = fm_lines[i]
        s = line.strip()
        if not s or s.startswith("#"):
            i += 1
            continue
        if line[0] in (" ", "\t"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_]+)\s*:\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, raw_val = m.group(1), m.group(2)
        if raw_val.strip() == "":
            items = []
            j = i + 1
            while j < len(fm_lines):
                l = fm_lines[j]
                if l.strip() == "":
                    j += 1
                    continue
                mm = re.match(r"^\s*-\s+(.*)$", l)
                if mm:
                    items.append(strip_scalar(mm.group(1)))
                    j += 1
                else:
                    break
            data[key] = items
            i = j
        else:
            data[key] = parse_scalar(raw_val)
            i += 1
    return data, body, None


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    for i, line in enumerate(read_text(path).splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        try:
            rows.append(json.loads(s))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{rel(path)}:{i}: invalid JSON ({exc})")
    return rows


def norm_source(value) -> str:
    return str(value).strip().strip("`").replace("\\", "/")


def note_tag(data):
    tags = data.get("tags")
    if isinstance(tags, list) and tags:
        return str(tags[0])
    return None


def note_sources(data):
    s = data.get("sources")
    if isinstance(s, list):
        return [str(x) for x in s]
    if isinstance(s, str):
        return [s]
    return []


def summary_of(body: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(">") or s.startswith("|") or s == "---":
            continue
        s = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", s)
        s = re.sub(r"[`*_]+", "", s)
        return s.strip()
    return ""


# --------------------------------------------------------------------------- #
# collectors
# --------------------------------------------------------------------------- #
def is_generated(path: Path) -> bool:
    if path.name.lower() == "index.md":
        return True
    return path == WIKI_LOG


def collect_notes():
    notes = []
    if not WIKI.exists():
        return notes
    for path in sorted(WIKI.rglob("*.md")):
        if is_generated(path):
            continue
        data, body, err = parse_frontmatter(read_text(path))
        notes.append({
            "path": path,
            "rel": rel(path),
            "data": data or {},
            "body": body,
            "error": err,
        })
    return notes


def _iter_raw_files():
    """Yield (area, path) for every raw source file (Raw/Sources + Raw/Projects).

    Generated per-folder indexes are named exactly `index.md` (lowercase) and are
    skipped; a project's `INDEX.md` is real source material and is kept.
    """
    if RAW_SOURCES.exists():
        for path in sorted(RAW_SOURCES.rglob("*.md")):
            if path.name == "index.md":
                continue
            yield "sources", path
    if RAW_PROJECTS.exists():
        for path in sorted(RAW_PROJECTS.rglob("*.md")):
            if path.name == "index.md":
                continue
            if "packs" in rel(path).split("/"):
                continue  # packs are derived (generated on demand), not source material
            yield "projects", path


def raw_project_name(rel_path: str) -> str:
    """`Raw/Projects/<name>/...` -> `<name>`; else ''."""
    parts = str(rel_path).replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[0] == "Raw" and parts[1] == "Projects":
        return parts[2]
    return ""


def raw_project_kind(rel_path: str) -> str:
    """Derive the raw project kind from the mirrored `.context/` path.

    `Raw/Projects/<name>/INDEX.md`        -> index
    `Raw/Projects/<name>/CONTEXT.md`      -> context
    `Raw/Projects/<name>/<sub>/*.md`      -> PROJECT_SUB_KIND[<sub>] or <sub>
    Nested monorepo mirrors are also supported, e.g.:
    `Raw/Projects/<name>/<service>/domains/.../overview.md` -> domain
    `Raw/Projects/<name>/<service>/INDEX.md`                -> module
    `Raw/Projects/<name>/packs/*.md`                        -> packs (skipped)
    """
    parts = str(rel_path).replace("\\", "/").split("/")
    if len(parts) < 4 or parts[0] != "Raw" or parts[1] != "Projects":
        return ""
    rest = parts[3:]  # after Raw/Projects/<name>/
    if "packs" in rest[:-1]:
        return "packs"
    if len(rest) == 1:
        return "index" if Path(rest[0]).stem.lower() == "index" else "context"
    # Prefer the deepest known kind folder (domains/entities/layers/...).
    for part in rest[:-1]:
        if part in PROJECT_SUB_KIND:
            return PROJECT_SUB_KIND[part]
    # Service/component root under the project (e.g. auth-service/INDEX.md).
    if len(rest) == 2 and Path(rest[1]).stem.lower() == "index":
        return "module"
    if len(rest) == 2:
        return "module"
    return re.sub(r"[^a-z0-9_-]", "", rest[0].lower())


def collect_sources():
    sources = []
    for area, path in _iter_raw_files():
        data, body, err = parse_frontmatter(read_text(path))
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        except OSError:
            mtime = TODAY
        sources.append({
            "path": path,
            "rel": rel(path),
            "area": area,
            "data": data or {},
            "body": body,
            "error": err,
            "mtime": mtime,
        })
    return sources


def coverage_map(notes):
    cov = {}
    for note in notes:
        for src in note_sources(note["data"]):
            cov.setdefault(norm_source(src), []).append(note["rel"])
    return cov


def note_project(data) -> str:
    v = data.get("project")
    return "" if v is None else str(v).strip()


def note_scope(data) -> str:
    v = data.get("scope")
    return "" if v is None else str(v).strip()


def catalog_entry(note):
    data = note["data"]
    return {
        "path": note["rel"],
        "title": str(data.get("title") or data.get("Title") or note["path"].stem),
        "tag": note_tag(data),
        "topics": [str(x) for x in (data.get("topics") or [])],
        "project": note_project(data),
        "scope": note_scope(data),
        "sources": note_sources(data),
        "updated": str(data.get("updated") or data.get("Updated") or data.get("created") or ""),
    }


def update_source_processed(path: Path) -> bool:
    """Flip Processed to true in a Raw source note. Returns True if changed."""
    lines = read_text(path).splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return False
    fm = lines[1:end]
    changed = False
    for idx, l in enumerate(fm):
        m = re.match(r"^(\s*)Processed\s*:\s*(.*)$", l)
        if m:
            if strip_scalar(m.group(2)) is not True:
                fm[idx] = "Processed: true"
                changed = True
            break
    else:
        fm.append("Processed: true")
        changed = True
    if not changed:
        return False
    write_text(path, "\n".join([lines[0]] + fm + lines[end:]) + "\n")
    return True


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_doctor(args):
    errors = []
    warnings = []
    print("== wiki doctor ==")
    ver = sys.version_info
    py_ok = (ver.major, ver.minor) >= REQUIRED_PY
    print(f"python     : {ver.major}.{ver.minor}.{ver.micro} " + ("OK" if py_ok else f"too old (need >= {REQUIRED_PY[0]}.{REQUIRED_PY[1]})"))
    if not py_ok:
        errors.append("python too old")

    folders = [
        RAW, RAW_SOURCES, RAW_FILES, WIKI,
        WIKI / "Topics", WIKI / "Concepts", WIKI / "Entities", WIKI / "Projects", WIKI / "Logs",
        SCHEMA, SCHEMA / "_templates", ROOT / "scripts", ROOT / ".agents" / "skills",
    ]
    for f in folders:
        if f.is_dir():
            print(f"folder OK  : {rel(f)}")
        else:
            print(f"folder MISS: {rel(f)}")
            warnings.append(f"missing folder {rel(f)}")
    # optional intake area, created on first `project-ingest`
    if RAW_PROJECTS.is_dir():
        print(f"folder OK  : {rel(RAW_PROJECTS)}")
    else:
        print(f"folder OPT : {rel(RAW_PROJECTS)} (created by project-ingest)")

    if CATALOG.exists():
        try:
            print(f"catalog    : {len(read_jsonl(CATALOG))} entries ({rel(CATALOG)})")
        except ValueError as exc:
            print(f"catalog ERR: {exc}")
            errors.append("catalog invalid")
    else:
        print("catalog    : missing (run build)")
        warnings.append("catalog missing")

    if MANIFEST.exists():
        try:
            print(f"manifest   : {len(read_jsonl(MANIFEST))} entries ({rel(MANIFEST)})")
        except ValueError as exc:
            print(f"manifest ERR: {exc}")
            errors.append("manifest invalid")
    else:
        print("manifest   : missing (run source-scan --update)")
        warnings.append("manifest missing")

    notes = collect_notes()
    sources = collect_sources()
    counts = {k: 0 for k in ALLOWED_TAGS}
    for n in notes:
        tag = note_tag(n["data"])
        if tag in counts:
            counts[tag] += 1
    print(f"wiki notes : {len(notes)} total (" + ", ".join(f"{k}={counts[k]}" for k in ALLOWED_TAGS) + ")")
    print(f"raw sources: {len(sources)}")
    cov = coverage_map(notes)
    covered = sum(1 for s in sources if cov.get(s["rel"]))
    print(f"covered    : {covered}/{len(sources)} raw source(s) referenced by notes")

    print()
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print("doctor: FAIL")
        return 1
    print("doctor: OK" + (" (with warnings)" if warnings else ""))
    return 0


def _note_line(n, e):
    return f"- [[{e['title']}]] — {summary_of(n['body'])}".rstrip(" —")


def _project_titles(projects):
    """Ordered [(name, anchor_title)] for the project namespaces."""
    out = []
    for name in sorted(projects):
        anchor = next((e for _, e in projects[name] if e["tag"] == "project"), None)
        out.append((name, anchor["title"] if anchor else name))
    return out


def cmd_build(args):
    notes = collect_notes()
    pairs = []
    for n in sorted(notes, key=lambda x: x["rel"]):
        if n["error"]:
            print(f"SKIP {n['rel']}: {n['error']}", file=sys.stderr)
            continue
        pairs.append((n, catalog_entry(n)))

    entries = [e for _, e in pairs]
    write_jsonl(CATALOG, entries)
    print(f"catalog: wrote {len(entries)} entries -> {rel(CATALOG)}")

    global_pairs = [(n, e) for n, e in pairs if not e.get("project")]
    project_pairs = [(n, e) for n, e in pairs if e.get("project")]

    groups = {k: [] for k in ALLOWED_TAGS}
    untagged = []
    for n, e in global_pairs:
        line = _note_line(n, e)
        if e["tag"] in groups:
            groups[e["tag"]].append(line)
        else:
            untagged.append(line)

    projects = {}
    for n, e in project_pairs:
        projects.setdefault(e["project"], []).append((n, e))

    # ---- Wiki/index.md -----------------------------------------------------
    lines = [
        "# Wiki Index", "",
        "Generated by `scripts/wiki_tool.py build`. Do not edit by hand.",
        "Machine-readable catalog: [`catalog.jsonl`](catalog.jsonl).", "",
    ]
    total = 0
    for tag in ALLOWED_TAGS:
        if tag == "project":
            continue
        lines.append(f"## {SECTION_TITLE[tag]}")
        if groups[tag]:
            lines.extend(groups[tag])
            total += len(groups[tag])
        else:
            lines.append("_None yet._")
        lines.append("")
    lines.append("## Projects")
    proj_lines = list(groups["project"])
    for name, title in _project_titles(projects):
        proj_lines.append(f"- [[{title}]] — {len(projects[name])} note(s) in project `{name}`")
    if proj_lines:
        lines.extend(proj_lines)
        total += len(proj_lines)
    else:
        lines.append("_None yet._")
    lines.append("")
    if untagged:
        lines.append("## Untagged")
        lines.extend(untagged)
        lines.append("")
    write_text(WIKI_INDEX, "\n".join(lines).rstrip() + "\n")
    print(f"index  : wrote {rel(WIKI_INDEX)} ({total} listed note(s))")

    # ---- per-kind folder indexes ------------------------------------------
    for tag in ALLOWED_TAGS:
        folder = WIKI / KIND_FOLDER[tag]
        body = list(groups[tag])
        if tag == "project":
            for name, title in _project_titles(projects):
                body.append(f"- [[{title}]] — project `{name}`")
        fl = [
            f"# {SECTION_TITLE[tag]}", "",
            "Generated by `scripts/wiki_tool.py build`. Do not edit by hand.", "",
        ]
        fl.extend(body or ["_None yet._"])
        write_text(folder / "index.md", "\n".join(fl).rstrip() + "\n")
    print("index  : wrote per-folder index files (Topics, Concepts, Entities, Projects, Logs)")

    # ---- per-project indexes ----------------------------------------------
    # Skipped when a project has a compiled anchor `<name>.md`: that note is the
    # semantic hub (and a flat index.md next to it doubles the Obsidian graph hub).
    # Classic flat catalogs still live in Wiki/Projects/index.md and Wiki/index.md.
    written_proj = 0
    for name, plist in projects.items():
        anchor = WIKI_PROJECTS / name / f"{name}.md"
        if anchor.exists():
            stale = WIKI_PROJECTS / name / "index.md"
            if stale.exists():
                try:
                    stale.unlink()
                except OSError:
                    pass
            continue
        pl = [
            f"# {name}", "",
            "Generated by `scripts/wiki_tool.py build`. Do not edit by hand.", "",
        ]
        for n, e in sorted(plist, key=lambda x: (x[1]["tag"], x[1]["title"])):
            pl.append(f"- [[{e['title']}]] ({e['tag']}) — {summary_of(n['body'])}".rstrip(" —"))
        write_text(WIKI_PROJECTS / name / "index.md", "\n".join(pl).rstrip() + "\n")
        written_proj += 1
    if written_proj:
        print(f"index  : wrote {written_proj} per-project index file(s) under {rel(WIKI_PROJECTS)}/")
    elif projects:
        print("index  : skipped per-project index.md (anchor notes are the hubs)")
    return 0


def cmd_lint(args):
    notes = collect_notes()
    errors = []
    warnings = []
    for n in notes:
        r = n["rel"]
        if n["error"]:
            errors.append(f"{r}: {n['error']}")
            continue
        data = n["data"]

        tags = data.get("tags")
        if not isinstance(tags, list) or not tags:
            errors.append(f"{r}: missing/empty 'tags'")
            tag = None
        else:
            tag = str(tags[0])
            if tag not in ALLOWED_TAGS:
                errors.append(f"{r}: tag '{tag}' not allowed (use: {', '.join(ALLOWED_TAGS)})")

        project = note_project(data)
        if project:
            expected_prefix = WIKI_PROJECTS / project
            if expected_prefix not in n["path"].parents:
                errors.append(f"{r}: project '{project}' note must live under Wiki/Projects/{project}/")
            if tag not in PROJECT_COMPILED_TAGS:
                errors.append(f"{r}: project note tag '{tag}' must be one of {', '.join(PROJECT_COMPILED_TAGS)}")
            if note_scope(data) not in ("", "project", "shared"):
                errors.append(f"{r}: scope must be 'project' | 'shared'")
        else:
            expected = FOLDER_KIND.get(n["path"].parent.name)
            if tag and expected and tag != expected:
                errors.append(f"{r}: tag '{tag}' does not match folder '{n['path'].parent.name}'")

        sources = note_sources(data)
        sc = data.get("source_count")
        if not isinstance(sc, int) or isinstance(sc, bool):
            errors.append(f"{r}: 'source_count' missing or not an integer")
        elif sc != len(sources):
            errors.append(f"{r}: source_count={sc} but {len(sources)} source(s) listed")

        for s in sources:
            sp = norm_source(s)
            if not sp.startswith(SOURCE_PREFIXES):
                errors.append(f"{r}: source '{s}' is not under Raw/Sources/ or Raw/Projects/")
            elif not (ROOT / sp).exists():
                errors.append(f"{r}: source link not found: {s}")

        up = data.get("updated")
        if not up:
            errors.append(f"{r}: missing 'updated'")
        elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(up)):
            errors.append(f"{r}: 'updated' not YYYY-MM-DD: {up}")

        body = n["body"]
        if "## Connections" not in body:
            warnings.append(f"{r}: missing '## Connections' section")
        elif not re.search(r"\[\[[^\]]+\]\]", body.split("## Connections", 1)[1]):
            warnings.append(f"{r}: '## Connections' has no [[wikilink]]")
        if re.search(r"Raw/(?:Sources|Projects|Files)/", body):
            warnings.append(f"{r}: Wiki body cites Raw/ path (keep provenance in frontmatter only)")
        if re.search(r"(?m)^## Sources\s*$", body):
            warnings.append(f"{r}: unexpected '## Sources' section (use frontmatter sources: only)")

    titles = {}
    for n in notes:
        if n["error"]:
            continue
        data = n["data"]
        title = str(data.get("title") or data.get("Title") or n["path"].stem)
        names = [title] + [str(a) for a in (data.get("aliases") or [])]
        local = set()
        for nm in names:
            key = nm.lower()
            if key in local:  # a note may repeat its own title as an alias
                continue
            local.add(key)
            info = titles.setdefault(key, {"disp": nm, "where": []})
            info["where"].append(n["rel"])
    for key, info in sorted(titles.items()):
        if len(info["where"]) > 1:
            warnings.append(
                f"duplicate title/alias '{info['disp']}' (case-insensitive) across: "
                f"{', '.join(sorted(info['where']))}"
            )

    if not CATALOG.exists():
        warnings.append("catalog.jsonl missing (run build)")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"lint: {len(notes)} note(s), {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def compute_manifest(accept_covered):
    notes = collect_notes()
    cov = coverage_map(notes)
    sources = collect_sources()
    existing = {}
    if MANIFEST.exists():
        try:
            for row in read_jsonl(MANIFEST):
                existing[str(row.get("path"))] = row
        except ValueError:
            pass
    rows = []
    for s in sources:
        covered_by = sorted(set(cov.get(s["rel"], [])))
        prev = existing.get(s["rel"], {})
        if isinstance(prev.get("processed"), bool):
            base_processed = prev["processed"]
        else:
            base_processed = s["data"].get("Processed") is True
        processed = base_processed
        if accept_covered and covered_by:
            processed = True
        rows.append({
            "path": s["rel"],
            "title": str(s["data"].get("Title") or s["path"].stem),
            "processed": processed,
            "covered_by": covered_by,
            "updated": s["mtime"],
        })
    return sources, cov, rows


def cmd_source_scan(args):
    sources, cov, rows = compute_manifest(args.accept_covered)
    if not args.update:
        print(f"{len(sources)} Raw source(s):")
        for s in sources:
            covered = sorted(set(cov.get(s["rel"], [])))
            mark = "x" if covered else " "
            print(f"  [{mark}] {s['rel']}" + (f"  <- {len(covered)} cover(s)" if covered else ""))
        print("dry run: pass --update to write " + rel(MANIFEST))
        return 0

    flipped = 0
    if args.accept_covered:
        for row in rows:
            if row["processed"] and row["covered_by"]:
                if update_source_processed(ROOT / row["path"]):
                    flipped += 1
    write_jsonl(MANIFEST, rows)
    covered = sum(1 for r in rows if r["covered_by"])
    print(f"manifest: wrote {len(rows)} entries ({covered} covered) -> {rel(MANIFEST)}")
    if args.accept_covered:
        print(f"accepted coverage: {flipped} source note(s) set Processed: true")
    return 0


def cmd_source_lint(args):
    notes = collect_notes()
    cov = coverage_map(notes)
    sources = collect_sources()
    manifest = {}
    if MANIFEST.exists():
        try:
            for row in read_jsonl(MANIFEST):
                manifest[str(row.get("path"))] = row
        except ValueError as exc:
            print(f"ERROR manifest invalid: {exc}")
            print("source-lint: FAIL")
            return 1

    errors = []
    warnings = []
    for s in sources:
        r = s["rel"]
        if s["error"]:
            errors.append(f"{r}: {s['error']}")
            continue
        data = s["data"]
        for key in SOURCE_REQUIRED_KEYS:
            if key not in data:
                errors.append(f"{r}: missing required key '{key}'")
        tags = data.get("tags")
        if not isinstance(tags, list) or "source" not in [str(t) for t in tags]:
            errors.append(f"{r}: tags must include \"source\"")

        if s.get("area") == "projects":
            if not data.get("project"):
                errors.append(f"{r}: project raw note missing 'project' (run project-ingest)")
            if not valid_project_raw_kind(str(data.get("kind") or "")):
                errors.append(f"{r}: project raw note 'kind' is invalid/missing (run project-ingest)")

        processed_fm = data.get("Processed") is True
        processed_manifest = bool(manifest.get(r, {}).get("processed"))
        covered_by = sorted(set(cov.get(r, [])))
        marked = processed_fm or processed_manifest

        if marked and not covered_by:
            errors.append(f"{r}: marked processed but not covered by any Wiki note")
        if covered_by and not marked:
            warnings.append(f"{r}: covered by {len(covered_by)} note(s) but not processed (run: source-scan --update --accept-covered)")
        if r not in manifest:
            warnings.append(f"{r}: absent from source manifest")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"source-lint: {len(sources)} source(s), {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def cmd_source_delta(args):
    sources = collect_sources()
    manifest_paths = set()
    if MANIFEST.exists():
        try:
            for row in read_jsonl(MANIFEST):
                manifest_paths.add(str(row.get("path")))
        except ValueError as exc:
            print(f"ERROR manifest invalid: {exc}")
            return 1
    source_paths = {s["rel"] for s in sources}
    missing = sorted(source_paths - manifest_paths)
    extra = sorted(manifest_paths - source_paths)
    if missing:
        print(f"{len(missing)} Raw source(s) not represented in the manifest:")
        for p in missing:
            print(f"  + {p}")
    else:
        print("source-delta: no unrepresented Raw sources")
    if extra:
        print(f"{len(extra)} manifest entr(ies) with no Raw file:")
        for p in extra:
            print(f"  - {p}")
    return 0


def cmd_source_coverage(args):
    notes = collect_notes()
    cov = coverage_map(notes)
    sources = collect_sources()
    covered = 0
    for s in sources:
        by = sorted(set(cov.get(s["rel"], [])))
        if by:
            covered += 1
            print(f"[covered]   {s['rel']}")
            for b in by:
                print(f"            <- {b}")
        else:
            print(f"[uncovered] {s['rel']}")
    print(f"source-coverage: {covered}/{len(sources)} Raw source(s) covered")
    return 0


# --------------------------------------------------------------------------- #
# project-ingest: Raw/Projects (capture-normalize) -> Wiki/Projects (compile)
# --------------------------------------------------------------------------- #
def first_heading(body: str, fallback: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return fallback


def _body_without_h1(body: str) -> str:
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            if line.strip().startswith("# "):
                lines = lines[i + 1:]
            break
    return "\n".join(lines).strip()


def raw_project_sub(rel_path: str) -> str:
    """Relative folder under Wiki/Projects/<name>/ mirroring the raw tree.

    Keeps nested monorepo paths, e.g. `auth-service/domains/authentication`.
    """
    parts = str(rel_path).replace("\\", "/").split("/")
    if len(parts) < 5 or parts[0] != "Raw" or parts[1] != "Projects":
        return ""
    mid = [p for p in parts[3:-1] if p != "packs"]
    return "/".join(mid)


def _project_raw_notes(name: str):
    return [
        s for s in collect_sources()
        if s.get("area") == "projects" and raw_project_name(s["rel"]) == name
    ]


def normalize_project_raw(path: Path, rel_path: str, dry_run: bool) -> str:
    """Prepend the project source frontmatter to a raw `.context` mirror file.

    Returns one of: 'normalized' | 'ok' (already normalized) | 'warn' | 'skip'.
    """
    text = read_text(path)
    data, body, err = parse_frontmatter(text)
    if data is not None and data.get("project"):
        return "ok"
    if err != "missing frontmatter":
        return "warn"
    name = raw_project_name(rel_path)
    kind = raw_project_kind(rel_path)
    if not name or not valid_project_raw_kind(kind):
        return "skip"
    title = first_heading(body, Path(rel_path).stem) or Path(rel_path).stem
    header = (
        "---\n"
        f'Title: "{title}"\n'
        'Author: "context-builder"\n'
        f'Reference: "project:{name}"\n'
        "ContentType:\n"
        '  - "markdown"\n'
        f"Created: {TODAY}\n"
        "Processed: false\n"
        'tags:\n'
        '  - "source"\n'
        f'project: "{name}"\n'
        f'kind: "{kind}"\n'
        "---\n"
    )
    if not dry_run:
        write_text(path, header + "\n" + body.lstrip("\n"))
    return "normalized"


def _safe_title(raw_title: str, fallback: str) -> str:
    """Turn a `.context` heading into a filename-safe note title."""
    t = re.sub(r"^\s*(Domain|Entity|Layer|Contract|Tech\s*Stack)\s*[:\-—]?\s*", "",
               raw_title or "", flags=re.I)
    t = t.replace("\ufffd", "-")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r'[\\/:*?"<>|]', "-", t).strip()
    return t or fallback


def _compile_title(src) -> str:
    """Note title from the `.context` heading; fall back to the file stem for
    path-style headings (e.g. `# domains/calls — Overview`)."""
    stem = Path(src["rel"]).stem
    heading = first_heading(src["body"], stem)
    if "/" in heading or heading.lower().endswith(".md"):
        parent = Path(src["rel"]).parent.name
        if stem.lower() in ("overview", "index", "readme") and parent:
            return parent
        return stem
    return _safe_title(heading, stem)


def _one_liner(body: str) -> str:
    """Extract the '## Project one-liner' block from a `.context/INDEX.md`."""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## project one-liner"):
            out = []
            for nxt in lines[i + 1:]:
                if nxt.strip().startswith("#"):
                    break
                if nxt.strip():
                    out.append(nxt.strip())
            if out:
                return " ".join(out)
    return ""


def raw_project_component(rel_path: str) -> str:
    """Service/module folder under the project, or '' for classic flat layout.

    `Raw/Projects/kuboteka/auth-service/entities/User.md` -> `auth-service`
    `Raw/Projects/foo/domains/bar/overview.md`             -> `` (flat)
    """
    parts = str(rel_path).replace("\\", "/").split("/")
    if len(parts) < 5 or parts[0] != "Raw" or parts[1] != "Projects":
        return ""
    first = parts[3]
    if first in PROJECT_SUB_KIND or first == "packs":
        return ""
    return first


def _module_name_aliases(module_names) -> dict:
    """Map short tokens (item-info, main-site, …) → canonical module folder name."""
    aliases = {}
    for m in module_names:
        ml = m.lower()
        aliases[ml] = m
        for suf in ("-service", "-project"):
            if ml.endswith(suf):
                short = ml[: -len(suf)]
                if len(short) >= 4:
                    aliases[short] = m
    # Contract titles often use repo nicknames, not folder names.
    # Keep these specific — short tokens like "fe"/"vue" false-match narrative text.
    soft = {
        "main-site": "vue-project",
    }
    for key, target in soft.items():
        if target in module_names:
            aliases[key] = target
    return aliases


def _contract_peer_modules(src, module_names) -> list:
    """Infer peer module folders named by a contract (stem/title/body).

    Example: `item-info-brickognize.md` / «item-info ↔ brickognize»
    → ['item-info-service', 'brickognize-service'] when both modules exist.
    """
    if not module_names:
        return []
    aliases = _module_name_aliases(set(module_names))
    stem = Path(src["rel"]).stem.lower().replace("_", "-")
    title = (src.get("data") or {}).get("Title") or first_heading(src["body"], "")
    title = str(title).lower()
    # Prefer stem + title only — body narrative ("FE → item-info") false-matches soft aliases.
    blob = f"{stem} {title}".lower()
    for ch in ("↔", "→", "←", "—", "–", "<->", "->", "<-"):
        blob = blob.replace(ch, " ")
    blob = re.sub(r"[^\w\s-]+", " ", blob)
    blob_compact = re.sub(r"[\s_]+", "-", blob.strip())
    found = []
    for key in sorted(aliases, key=len, reverse=True):
        if key in stem or key in blob_compact or re.search(
            rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", blob_compact
        ):
            mod = aliases[key]
            if mod not in found:
                found.append(mod)
    owner = raw_project_component(src["rel"])
    if owner and owner in module_names and owner not in found:
        found.insert(0, owner)
    return found


def render_project_note(
    title: str,
    kind: str,
    tag: str,
    name: str,
    src,
    parent_title=None,
    parent_rel="parent",
    child_links=None,
) -> str:
    """Render a project component note with hierarchical Connections.

    Leaf notes link up to their parent (service module or project).
    Module notes link up to the project and down to architecture children.
    Contract notes also link sideways to peer services named by the boundary.
    """
    parent_title = parent_title or name
    details = _body_without_h1(src["body"])
    summary = summary_of(src["body"]) or f"{title} ({kind}) in project {name}."
    conn = [f"- [[{parent_title}]] — {parent_rel}"]
    seen_conn = {parent_title.lower()}
    for c in child_links or []:
        ct = c["title"]
        if ct.lower() in seen_conn:
            continue
        seen_conn.add(ct.lower())
        bit = f"- [[{ct}]] — {c['kind']}"
        if c.get("summary"):
            bit += f" — {c['summary']}"
        conn.append(bit)
    lines = [
        "---",
        "tags:",
        f'  - "{tag}"',
        "topics:",
        f'  - "{name}"',
        "status: seed",
        f"created: {TODAY}",
        f"updated: {TODAY}",
        "sources:",
        f'  - "{src["rel"]}"',
        "source_count: 1",
        "aliases: []",
        f'project: "{name}"',
        'scope: "project"',
        "supersedes: []",
        "---",
        "",
        f"# {title}",
        "",
        summary,
        "",
        "## Details",
        "",
        details or f"_No compiled detail yet._",
        "",
        "## Connections",
        "",
        "\n".join(conn),
        "",
    ]
    return "\n".join(lines)


def _global_note_titles():
    """Titles of global compiled notes (Concepts + Entities), keyed by lowercase."""
    out = {}
    for kind in ("Concepts", "Entities"):
        d = WIKI / kind
        if d.is_dir():
            for f in d.glob("*.md"):
                if f.name == "index.md":
                    continue
                out[f.stem.lower()] = f.stem
    return out


def _anchor_shared_links(name: str, raws) -> list:
    """Global concepts/entities mentioned (whole word, case-insensitive) in project sources."""
    blob = "\n".join(s["body"] for s in raws).lower()
    found = []
    for low, disp in sorted(_global_note_titles().items()):
        if low == name.lower():
            continue
        if re.search(r"\b" + re.escape(low) + r"\b", blob):
            found.append(disp)
    return found


def render_project_anchor(name: str, raws, anchor_raw, children, shared=()) -> str:
    """Project hub: prefer linking only to direct modules, not every leaf note."""
    conn_lines = [
        f"- [[{c['title']}]] — {c['kind']} — {c['summary']}".rstrip(" —") for c in children
    ]
    conn_lines += [f"- [[{t}]] — shared concept" for t in shared]
    sources = "\n".join(f'  - "{s["rel"]}"' for s in raws)
    one = _one_liner(anchor_raw["body"]) if anchor_raw else ""
    desc = one or (
        f"Knowledge for the **{name}** project (compiled from the project context mirror)."
    )
    if any(c.get("kind") == "module" for c in children):
        desc += (
            " Graph hub: links only to direct service/module components; "
            "architecture notes hang under each module."
        )
    lines = [
        "---",
        "tags:",
        '  - "project"',
        "topics:",
        f'  - "{name}"',
        "status: seed",
        f"created: {TODAY}",
        f"updated: {TODAY}",
        "sources:",
        sources,
        f"source_count: {len(raws)}",
        "aliases: []",
        f'project: "{name}"',
        'scope: "project"',
        "supersedes: []",
        "---",
        "",
        f"# {name}",
        "",
        desc,
        "",
        "## Connections",
        "",
        "\n".join(conn_lines) or "_No components yet._",
        "",
    ]
    return "\n".join(lines)


def _title_taken(title: str, name: str) -> bool:
    """True if `title` collides (case-insensitively) with a note outside project `name`."""
    low = title.lower()
    for p in WIKI_PROJECTS.rglob("*.md"):
        if p.stem.lower() != low:
            continue
        rel = p.relative_to(WIKI_PROJECTS)
        proj = rel.parts[0] if len(rel.parts) > 1 else ""
        if proj != name:
            return True
    for kind in ("Concepts", "Entities", "Topics"):
        d = WIKI / kind
        if d.is_dir() and any(f.stem.lower() == low for f in d.glob("*.md")):
            return True
    return False


def _unique_project_title(title: str, name: str) -> str:
    """Disambiguate a title already used (case-insensitively) by another project or a global note."""
    candidate = title
    for _ in range(5):
        if not _title_taken(candidate, name):
            return candidate
        candidate = f"{title} ({name})"
    return candidate


def compile_project(name: str, dry_run: bool):
    """Compile Raw/Projects/<name>/** into Wiki/Projects/<name>/**. Returns note count.

    Hierarchical graph links (monorepo with service modules):
      project hub  -> only module (service INDEX) notes
      module       -> project + its domains/entities/layers/contracts/tech
      leaf         -> its module (not the project hub)

    Classic flat layouts (no modules) keep the previous all-to-hub linking.
    """
    raws = _project_raw_notes(name)
    if not raws:
        return 0
    anchor_raw = next((s for s in raws if raw_project_kind(s["rel"]) == "index"), None)
    seen = {name.lower()}  # reserve the anchor title
    planned = []
    for s in raws:
        kind = raw_project_kind(s["rel"])
        if kind == "index":
            continue
        tag = PROJECT_KIND_TAG.get(kind, "concept")
        sub = raw_project_sub(s["rel"])
        component = raw_project_component(s["rel"])
        if kind == "module" and component:
            title = component
        elif kind in ("context", "module", "artifact"):
            title = Path(s["rel"]).stem
        else:
            title = _compile_title(s)
        if title.lower() in seen:
            disambig = component or Path(s["rel"]).parent.name
            # Use " - " not "/" — a slash is a path separator on Windows filenames.
            title = f"{title} ({disambig} - {kind})"
        seen.add(title.lower())
        title = _unique_project_title(title, name)
        seen.add(title.lower())
        file_title = title.replace("/", "-").replace("\\", "-")
        out_path = WIKI_PROJECTS / name / sub / f"{file_title}.md"
        planned.append({
            "title": title,
            "kind": kind,
            "tag": tag,
            "sub": sub,
            "component": component,
            "src": s,
            "out_path": out_path,
            "summary": summary_of(s["body"]),
        })

    has_modules = any(p["kind"] == "module" for p in planned)
    module_by_component = {
        p["component"]: p["title"] for p in planned if p["kind"] == "module" and p["component"]
    }
    kind_order = ("domain", "entity", "layer", "contract", "tech", "module", "context", "artifact")

    # Contract → peer service edges (both ends), for graph links between modules.
    peer_edges = {c: set() for c in module_by_component}
    for p in planned:
        if p["kind"] != "contract":
            continue
        peers = _contract_peer_modules(p["src"], module_by_component.keys())
        p["peer_modules"] = peers
        for a in peers:
            for b in peers:
                if a != b and a in peer_edges and b in module_by_component:
                    peer_edges[a].add(b)

    expected = set()
    written = 0
    for p in planned:
        expected.add(p["out_path"])
        if p["kind"] == "module" and has_modules:
            kids = [
                {
                    "title": x["title"],
                    "kind": x["kind"],
                    "summary": x["summary"],
                }
                for x in sorted(
                    (x for x in planned
                     if x["component"] == p["component"] and x["kind"] != "module"),
                    key=lambda x: (kind_order.index(x["kind"])
                                   if x["kind"] in kind_order else 99,
                                   x["title"].lower()),
                )
            ]
            for peer in sorted(peer_edges.get(p["component"], ())):
                kids.append({
                    "title": module_by_component[peer],
                    "kind": "peer",
                    "summary": "contract boundary",
                })
            body = render_project_note(
                p["title"], p["kind"], p["tag"], name, p["src"],
                parent_title=name,
                parent_rel=f"project {name}",
                child_links=kids,
            )
        elif has_modules:
            parent = module_by_component.get(p["component"], name)
            rel = (
                f"module {parent}" if parent in module_by_component.values()
                else f"project {name}"
            )
            extra = []
            if p["kind"] == "contract":
                for peer in p.get("peer_modules") or []:
                    if peer not in module_by_component:
                        continue
                    pt = module_by_component[peer]
                    if pt == parent:
                        continue
                    extra.append({
                        "title": pt,
                        "kind": "peer",
                        "summary": "contract boundary",
                    })
            body = render_project_note(
                p["title"], p["kind"], p["tag"], name, p["src"],
                parent_title=parent,
                parent_rel=rel,
                child_links=extra or None,
            )
        else:
            body = render_project_note(
                p["title"], p["kind"], p["tag"], name, p["src"],
                parent_title=name,
                parent_rel=f"project {name}",
            )
        if not dry_run:
            write_text(p["out_path"], body)
        written += 1

    if has_modules:
        anchor_children = [
            {"title": p["title"], "kind": p["kind"], "summary": p["summary"]}
            for p in planned if p["kind"] == "module"
        ]
    else:
        anchor_children = [
            {"title": p["title"], "kind": p["kind"], "summary": p["summary"]}
            for p in planned
        ]

    anchor_path = WIKI_PROJECTS / name / f"{name}.md"
    expected.add(anchor_path)
    if not dry_run:
        shared = _anchor_shared_links(name, raws)
        write_text(
            anchor_path,
            render_project_anchor(name, raws, anchor_raw, anchor_children, shared),
        )
        for p in (WIKI_PROJECTS / name).rglob("*.md"):
            if p.name == "index.md" or p in expected:
                continue
            try:
                p.unlink()
            except OSError:
                pass
    written += 1
    return written


def cmd_project_ingest(args):
    RAW_PROJECTS.mkdir(parents=True, exist_ok=True)
    all_names = sorted({
        raw_project_name(s["rel"]) for s in collect_sources()
        if s.get("area") == "projects"
    })
    names = [n for n in all_names if not args.project or n == args.project]
    if not names:
        print(f"project-ingest: no Raw/Projects/{args.project or '<name>'}/ notes found")
        return 1

    counts = {"normalized": 0, "ok": 0, "warn": 0, "skip": 0}
    compiled = 0
    for name in names:
        if not args.no_normalize:
            for s in _project_raw_notes(name):
                if not valid_project_raw_kind(raw_project_kind(s["rel"])):
                    continue
                res = normalize_project_raw(s["path"], s["rel"], args.dry_run)
                counts[res] = counts.get(res, 0) + 1
        if not args.no_compile:
            compiled += compile_project(name, args.dry_run)

    verb = "would write" if args.dry_run else "wrote"
    print(f"project-ingest: {len(names)} project(s) [{', '.join(names)}]")
    print(f"capture : normalized={counts['normalized']} ok={counts['ok']} warn={counts['warn']} skip={counts['skip']}")
    print(f"compile : {verb} {compiled} note(s) under {rel(WIKI_PROJECTS)}/")
    if args.dry_run:
        print("dry run: pass no --dry-run to apply")
    return 0


def cmd_search_catalog(args):
    query = (args.query or "").strip()
    if not query:
        print("search-catalog: empty query", file=sys.stderr)
        return 2
    if not CATALOG.exists():
        print("search-catalog: catalog missing (run build)", file=sys.stderr)
        return 1
    rows = read_jsonl(CATALOG)
    needle = query.lower()
    hits = []
    for row in rows:
        hay = " ".join([
            str(row.get("title", "")),
            str(row.get("tag", "")),
            str(row.get("project", "")),
            str(row.get("scope", "")),
            " ".join(map(str, row.get("topics") or [])),
            " ".join(map(str, row.get("sources") or [])),
            str(row.get("path", "")),
        ]).lower()
        if needle in hay:
            hits.append(row)
    if not hits:
        print(f"no notes matched '{query}'")
        return 0
    print(f"{len(hits)} note(s) matched '{query}':")
    for row in hits:
        topics = ", ".join(map(str, row.get("topics") or []))
        extra = f"  [topics: {topics}]" if topics else ""
        print(f"  {str(row.get('tag') or '?'):8} [[{row.get('title') or '?'}]]{extra}  {row.get('path', '')}")
    return 0


def cmd_log(args):
    entry = f"## [{TODAY}] {args.title}\n"
    if args.details:
        entry += f"- {args.details}\n"
    entry += "\n"
    if not WIKI_LOG.exists():
        write_text(WIKI_LOG, "# Log\n\nAppend-only. Entries: `## [YYYY-MM-DD] Title`.\n\n---\n\n")
    with WIKI_LOG.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(entry)
    print(f"log: appended to {rel(WIKI_LOG)}")
    return 0


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(
        prog="wiki_tool.py",
        description="Stdlib-only toolkit for the memory vault (LLM Wiki pattern).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="non-mutating health check")
    sub.add_parser("build", help="generate catalog + index files")
    sub.add_parser("lint", help="validate compiled Wiki notes")

    ss = sub.add_parser("source-scan", help="list Raw sources; optionally update the manifest")
    ss.add_argument("--update", action="store_true", help="write Schema/source-manifest.jsonl")
    ss.add_argument("--accept-covered", action="store_true", help="mark covered sources processed")

    sub.add_parser("source-lint", help="validate Raw source frontmatter + coverage state")
    sub.add_parser("source-delta", help="show Raw sources missing from the manifest")
    sub.add_parser("source-coverage", help="show which Raw sources are covered")

    pi = sub.add_parser("project-ingest", help="capture + compile Raw/Projects into Wiki/Projects")
    pi.add_argument("--project", default="", help="only this project name")
    pi.add_argument("--no-normalize", action="store_true", help="skip capture (frontmatter prepend)")
    pi.add_argument("--no-compile", action="store_true", help="skip compilation")
    pi.add_argument("--dry-run", action="store_true", help="report without writing")

    sc = sub.add_parser("search-catalog", help="search compiled notes via the catalog")
    sc.add_argument("--query", required=True, help="text to search")

    lg = sub.add_parser("log", help="append an entry to Wiki/log.md")
    lg.add_argument("--title", required=True, help="entry title")
    lg.add_argument("--details", default="", help="short details line")
    return p


HANDLERS = {
    "doctor": cmd_doctor,
    "build": cmd_build,
    "lint": cmd_lint,
    "source-scan": cmd_source_scan,
    "source-lint": cmd_source_lint,
    "source-delta": cmd_source_delta,
    "source-coverage": cmd_source_coverage,
    "project-ingest": cmd_project_ingest,
    "search-catalog": cmd_search_catalog,
    "log": cmd_log,
}


def main(argv=None):
    args = build_parser().parse_args(argv)
    return HANDLERS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
