# Frontmatter schema

Every source note in `Raw/Sources/` and every compiled note in `Wiki/` starts with a
YAML frontmatter block delimited by `---`. Frontmatter is the **single source of
truth** for the catalog: `build` derives `Wiki/index.md` and `Wiki/catalog.jsonl`
from it. A stale catalog is a lint finding.

Two frontmatter shapes, matching the two layers: **source notes** (raw, write-once)
and **compiled notes** (wiki, agent-maintained). Templates live in
[`_templates/`](_templates/).

---

## Source notes — `Raw/Sources/`

```yaml
---
Title: ""
Author: ""
Reference: ""
ContentType:
  - "markdown"
Created: YYYY-MM-DD
Processed: false
tags:
  - "source"
---
```

| Field | Required | Rules |
|---|---|---|
| `Title` | ✅ | Human title of the source. |
| `Author` | — | Author / speaker / originator. Empty if unknown — never invented. |
| `Reference` | — | URL, citation, or `"call with X on YYYY-MM-DD"`; empty if none. |
| `ContentType` | ✅ | List; one or more of `markdown`, `pdf`, `image`, `audio`, `video`, `web`, `transcript`. |
| `Created` | ✅ | ISO `YYYY-MM-DD` — date captured. |
| `Processed` | ✅ | `false` until compiled into ≥1 wiki note; `true` after. |
| `tags` | ✅ | Always contains `"source"`. |

- **Write-once.** Never edit or delete a source note after capture (only `Processed`
  may flip to `true`).
- Keys here are Capitalized exactly as above; `tags` is lowercase.

## Project source notes — `Raw/Projects/<project>/`

A project's `.context/` is mirrored here (same names/structure). Capture
(`wiki_tool.py project-ingest`) prepends the source frontmatter above plus two keys:

| Field | Required | Rules |
|---|---|---|
| `project` | ✅ | Project name (matches the `Raw/Projects/<project>/` folder). |
| `kind` | ✅ | One of `index`, `context`, `domain`, `entity`, `layer`, `contract`, `tech`, `module`, `artifact` (or any project subfolder name). |

`packs/` are derived artifacts and are **not** captured. `Processed` flips to `true`
once compiled into `Wiki/Projects/`, exactly like `Raw/Sources/`.

## Compiled notes — `Wiki/`

```yaml
---
tags:
  - "concept"
topics: []
status: seed
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: []
source_count: 0
aliases: []
project: ""       # optional, project-scoped note
scope: ""         # optional: project | shared
supersedes: []    # optional, actualized prior note(s)
---
```

| Field | Required | Rules |
|---|---|---|
| `tags` | ✅ | First tag is the note kind — one of `topic`, `concept`, `entity`, `project`, `log`. Extra tags allowed. |
| `topics` | — | List of related topic names. |
| `status` | ✅ | Lifecycle: `seed` → `growing` → `mature` → `stale`. Default `seed`. |
| `created` | ✅ | ISO `YYYY-MM-DD`. |
| `updated` | ✅ | ISO `YYYY-MM-DD`; bump on every content change. |
| `sources` | ✅ | List of `Raw/Sources/` or `Raw/Projects/` paths this note is built from. Empty only for a pure index/log note; otherwise ≥1. |
| `source_count` | ✅ | Integer; MUST equal `len(sources)`. |
| `aliases` | — | Alternative titles that resolve to this note via `[[links]]`. |
| `project` | — | Project name. When set, the note MUST live under `Wiki/Projects/<project>/` and its `tags[0]` may be `project`, `concept`, or `entity` (the folder-match rule is relaxed). |
| `scope` | — | `project` or `shared`. `shared` notes are promoted to global `Wiki/Concepts`/`Wiki/Entities`. |
| `supersedes` | — | Prior note(s) this one actualizes (project knowledge; keeps history without deleting). |

### Allowed compiled note tags

`topic` · `concept` · `entity` · `project` · `log`

The first `tags` entry determines the note kind and the target folder:

| Tag | Folder |
|---|---|
| `topic` | `Wiki/Topics/` |
| `concept` | `Wiki/Concepts/` |
| `entity` | `Wiki/Entities/` |
| `project` | `Wiki/Projects/` |
| `log` | `Wiki/Logs/` |

The note `title` is its filename stem and its H1 (Title Case).

---

## catalog.jsonl (generated)

One JSON object per line, one line per compiled note — produced by `build`, never
hand-edited. Fixed field order for stable diffs:

```json
{"path":"Wiki/Concepts/Incremental Compilation.md","title":"Incremental Compilation","tag":"concept","topics":["Knowledge Management"],"project":"","scope":"","sources":["Raw/Sources/llm-wiki.md"],"updated":"2026-09-22"}
```

- `query` searches this file (by `title`, `topics`, `tags`, `aliases`) **before**
  reading any `Raw/` content.
- `build` must be re-run whenever frontmatter changes.

## Validation rules (enforced by `build` + `lint`)

1. Frontmatter present and parseable on every `Wiki/**/*.md` (except generated `index.md` and `Wiki/log.md`).
2. `tags[0]` is one of the allowed compiled note tags and matches the folder — **unless** the note has `project:`, in which case it must live under `Wiki/Projects/<project>/` and `tags[0]` is `project` | `concept` | `entity`.
3. `source_count == len(sources)`.
4. Every `sources` path exists on disk (under `Raw/Sources/` or `Raw/Projects/`).
5. `updated` >= `created`; both ISO `YYYY-MM-DD`.
6. `status` in `seed | growing | mature | stale`; `scope`, when present, in `project | shared`.
7. No duplicate `title` / `aliases` across notes.
8. Source notes: `tags` contains `"source"`, `Processed` is boolean; project source notes also carry `project` and a valid `kind`.
