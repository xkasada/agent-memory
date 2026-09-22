---
name: llm-wiki-project-ingest
description: Compile a project's mirrored `.context/` (Raw/Projects/<project>/) into structured knowledge under Wiki/Projects/<project>/. Use when the user says "ingest this project", "compile project context", "add project to the vault", "process Raw/Projects", "project-ingest". Compile-only (raw is already captured, e.g. by context-curator/MCP or a manual copy); routes reusable concepts per project and keeps raw immutable.
---

# llm-wiki-project-ingest — `Raw/Projects/` → `Wiki/Projects/`

Two phases, both driven by `scripts/wiki_tool.py project-ingest`: **capture**
(prepend raw frontmatter — idempotent) then **compile** (write `Wiki/Projects/`).
Raw is already present; this is mostly compile-only.

## 0. Load schema

Read `AGENTS.md` → "Project knowledge", `Schema/frontmatter-schema.md`,
`Schema/naming-conventions.md`, and `Schema/_templates/`.

## 1. Capture → `Raw/Projects/<project>/`

For each file (skip `packs/` never) the tool prepends:

```yaml
Title / Author "context-builder" / Reference "project:<name>"
ContentType ["markdown"] / Created / Processed:false / tags ["source"]
project: "<name>"
kind: "index|context|domain|entity|layer|contract|tech|module|artifact"
```

Run:
```bash
python3 scripts/wiki_tool.py project-ingest --no-compile   # capture only
```
Never hand-edit a raw project file afterwards (only `Processed` may flip to `true`).

## 2. Compile → `Wiki/Projects/<project>/`

```bash
python3 scripts/wiki_tool.py project-ingest
```

Produces:
- anchor `Wiki/Projects/<project>/<project>.md` (`kind: project`) with `[[wikilinks]]`
  to every component — this is the read-scope anchor;
- `domains/`, `entities/`, `layers/`, `contracts/`, `tech/`, `modules/`, `artifacts/`
  notes (kind `concept` / `entity`; project-specific subfolders compile as `concept`),
  each with `project:` and `scope: project`.

Rules:
- One anchor per project; component titles derived from the `.context` headings.
- Colliding titles are suffixed `Title (project)` so `[[wikilinks]]` stay unique.
- Every project note's `sources:` points at its `Raw/Projects/...` file; keep
  `source_count` equal.

## 3. Judgment (agent pass, after the tool)

The deterministic compile does not decide shared/project or resolve conflicts:

1. **Shared vs project** — if a concept/entity is reusable beyond this project,
   promote it to `Wiki/Concepts` / `Wiki/Entities` with `scope: shared`, and leave
   `[[wikilinks]]` from the project notes. Otherwise keep it project-scoped.
2. **Actualization** — new data wins, but never silently: record `supersedes:` on the
   updated note and append a `log.md` entry.
3. **Contradictions** — flag, don't overwrite silently.
4. **Connections** — add cross-links (`## Connections`, ≥1 `[[wikilink]]`).

## 4. Build, source, log

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-lint
python3 scripts/wiki_tool.py log --title "ingest: project <name>" --details "+N note(s)"
```

## Hard constraints

- `Raw/` is source material — write-once; never delete (mark `Processed` instead).
- Reusable knowledge only under `Wiki/`.
- Never invent facts the `.context` does not contain.
- Keep `[[wikilinks]]` unique (rely on the `Title (project)` suffix).
