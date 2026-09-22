---
name: llm-wiki-ingest
description: Ingest a new source into the memory vault — capture it into Raw/Sources/, then compile it into the interlinked Wiki/. Use when the user says "ingest this", "capture this", "save this to my brain", "add this source", "compile this", "process raw notes". Preserves raw as immutable source material; writes reusable knowledge only under Wiki/, each note linked to its raw sources.
---

# llm-wiki-ingest — `Raw/Sources/` → `Wiki/`

Two phases: **capture** (raw, immutable) then **compile** (reusable, in `Wiki/`).

## 0. Load schema

Read `AGENTS.md`, `Schema/frontmatter-schema.md`,
`Schema/naming-conventions.md`, and `Schema/_templates/`.

## 1. Capture → `Raw/Sources/`

1. Detect `type` → pick the prefix: `article-`, `idea-`, `highlights-`,
   `braindump-`, `note-`, `resource-`, `tweet-`, `call-`, `meeting-`, `person-`,
   `company-`. If ambiguous, ask once.
2. If the input is a URL, fetch and save the **readable text**, not just the URL.
   Attachments go to `Raw/Files/` and are referenced by path.
3. Filename `<kind>-<kebab-topic>.md` (topic, not URL slug).
4. Source-note frontmatter (write-once):
   ```yaml
   ---
   Title: "Article or short description"
   Author: ""
   Reference: "<URL or origin>"
   ContentType:
     - "markdown"
   Created: YYYY-MM-DD
   Processed: false
   tags:
     - "source"
   ---
   ```
5. Save under `Raw/Sources/`. **Never edit/delete an existing raw file** (only flip
   `Processed` to `true` after compilation).

## 2. Compile → `Wiki/`

1. Search `Wiki/catalog.jsonl` for an existing page on the topic.
2. **Default: merge into the best-fit page.** Create a new page only when nothing fits.
   One page per concept, not per source.
3. Write/update using the matching template (`concept-note.md`, `topic-note.md`, …),
   with full frontmatter:
   - `tags[0]` is the note kind: `topic` | `concept` | `entity` | `project` | `log`.
   - `sources` MUST list the raw file(s) this note draws from (≥1); set
     `source_count` equal to the list length.
   - `status`: `seed` | `growing` | `mature` (pick honestly; default `seed`).
   - Use `[[wikilinks]]` for every related concept; `## Connections` is mandatory.
   - **Do not** write a body `## Sources` block or cite `Raw/` paths in prose —
     provenance stays in frontmatter `sources:` / `source_count` only.
4. Place in the folder matching the tag: `Topics/` | `Concepts/` | `Entities/` | `Projects/` | `Logs/`.

## 3. Build, source, log

Run from the vault root:

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py log --title "ingest: <Source Title>" --details "+N note(s)"
```

`build` regenerates `Wiki/catalog.jsonl` + `Wiki/index.md` (and per-folder indexes);
`source-scan --accept-covered` flips the source's `Processed: true` once covered.

## Hard constraints

- Treat `Raw/Sources/` as source material, **not** compiled notes.
- Reusable knowledge only under `Wiki/`.
- Every compiled note links to ≥1 raw source.
- **Do not invent citations or unsupported claims.** If the source does not support
  a statement, leave it out.
