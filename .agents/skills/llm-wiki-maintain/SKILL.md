---
name: llm-wiki-maintain
description: Maintain the memory vault — build the catalog and index from frontmatter, update the source manifest, run source checks, find missing wikilinks, and gate commits on build+lint+source checks. Use when the user says "maintain the wiki", "build the catalog", "rebuild index", "check sources", "connect pages", or "before commit". Never commits a stale catalog or broken links.
---

# llm-wiki-maintain — build, source checks, connect, pre-commit gate

Everything runs through `scripts/wiki_tool.py` (stdlib only); do not hand-edit the
generated files.

## 1. build

```bash
python3 scripts/wiki_tool.py build
```

Regenerates from note frontmatter:
- `Wiki/catalog.jsonl` — one JSON line per note, fixed order
  `{"path","title","tag","topics","sources","updated"}`.
- `Wiki/index.md` and per-folder `Wiki/<Kind>/index.md`, grouped by `tags[0]` kind.
- Fails/skips notes whose frontmatter violates `Schema/frontmatter-schema.md`.

## 2. source checks

```bash
python3 scripts/wiki_tool.py source-scan --update --accept-covered
python3 scripts/wiki_tool.py source-lint
python3 scripts/wiki_tool.py source-delta
python3 scripts/wiki_tool.py source-coverage
```

- `source-scan --update --accept-covered` writes `Schema/source-manifest.jsonl` and
  flips covered sources to `Processed: true`.
- `source-lint` fails when a source is marked processed but has no Wiki coverage.
- `source-delta` lists Raw sources missing from the manifest; `source-coverage`
  shows which notes cover each source.

## 3. connect

1. Build a topic map from `catalog.jsonl`.
2. For each note, find 2–5 thematically overlapping notes not yet linked.
3. Propose additions to `## Connections`; apply on approval.
4. Log: `python3 scripts/wiki_tool.py log --title "maintain: connect N links suggested"`.

## 4. lint

```bash
python3 scripts/wiki_tool.py lint
```

Full judgment checklist: `Schema/lint-checklist.md` (or the `llm-wiki-lint` skill).

## 5. pre-commit gate

Run build + lint + source-lint before every commit (also wired in `.githooks/pre-commit`):

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-lint
```

- Green → commit, e.g. `wiki: ingest "The LLM Wiki Pattern" (+1 note)`.
- Red → fix first. Never commit a stale `catalog.jsonl`, broken `[[links]]`, or
  unsourced/processed-without-coverage sources.
- Log: `python3 scripts/wiki_tool.py log --title "maintain: build ok, lint 0, sources ok"`.

## Don't

- Don't edit `Raw/` (source material) or `.obsidian/`.
- Don't hand-edit generated `index.md` / `catalog.jsonl` / `source-manifest.jsonl`.
- Don't commit when a check is failing.
