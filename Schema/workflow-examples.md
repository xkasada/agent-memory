# Workflow examples

Concrete end-to-end sequences. Skills in [`.agents/skills/`](../.agents/skills/)
wrap these; this file is the canonical reference and the pre-commit contract.

---

## 1. Ingest a source (`llm-wiki-ingest`)

> Human: "Ingest this article: https://example.com/llm-wiki"

**Capture → `Raw/Sources/`**

1. Fetch and save the readable text (not just the URL).
2. Write source-note frontmatter + body:

```markdown
---
Title: "The LLM Wiki Pattern"
Author: ""
Reference: "https://example.com/llm-wiki"
ContentType:
  - "markdown"
  - "web"
Created: 2026-09-22
Processed: false
tags:
  - "source"
---

# The LLM Wiki Pattern

{cleaned article text, key author names/dates preserved inline}
```

3. Save as `Raw/Sources/article-llm-wiki-pattern.md`.

**Compile → `Wiki/`**

4. Search `Wiki/catalog.jsonl` for an existing note on the topic.
5. Merge into the best-fit note, or create one — here
   `Wiki/Concepts/Incremental Compilation.md`:

```markdown
---
tags:
  - "concept"
topics:
  - "LLM Wiki Pattern"
status: seed
created: 2026-09-22
updated: 2026-09-22
sources:
  - Raw/Sources/article-llm-wiki-pattern.md
source_count: 1
aliases: []
---

# Incremental Compilation

Compiling a source updates existing notes instead of re-deriving answers, so the
wiki compounds rather than being rebuilt per query.

## Definition

{…}

## Connections

- [[LLM Wiki Pattern]] — the pattern this mechanism enables

## Sources

- `Raw/Sources/article-llm-wiki-pattern.md` — origin of the pattern
```

6. Run `python3 scripts/wiki_tool.py build` (regenerates catalog + index files) and
   `python3 scripts/wiki_tool.py source-scan --update --accept-covered` (flips the
   source's `Processed: true`).
7. Log it: `python3 scripts/wiki_tool.py log --title "ingest: The LLM Wiki Pattern" --details "+1 note"`.

---

## 2. Query the corpus (`llm-wiki-query`)

> Human: "What does my brain say about incremental compilation?"

1. Search `Wiki/catalog.jsonl` for `title`/`topics`/`tags`/`aliases` matches →
   `Wiki/Concepts/Incremental Compilation.md`, `Wiki/Topics/LLM Wiki Pattern.md`.
2. Read those notes; traverse `[[wikilinks]]` 1–2 hops.
3. Only now open the specific `Raw/` files those notes cite — not the whole `Raw/` tree.
4. Answer with citations: *"Per [[Incremental Compilation]], …"*. If notes disagree, show both.
5. File a reusable answer back as a note (or update one); bump `updated`, then rebuild.
6. Log it: `python3 scripts/wiki_tool.py log --title "query: what-is-incremental-compilation"`.

If the catalog has no match and the answer is not in the corpus, say so — do
**not** invent a citation or answer from general knowledge as if it were the vault.

---

## 3. Maintain / pre-commit checks (`llm-wiki-maintain`)

Run **before every commit** (also enforced by `.githooks/pre-commit`):

```bash
python3 scripts/wiki_tool.py build
python3 scripts/wiki_tool.py lint
python3 scripts/wiki_tool.py source-lint
```

### build
Regenerate derived artifacts from frontmatter:

1. Rebuild `Wiki/catalog.jsonl` (one JSON line per compiled note, fixed field order).
2. Rebuild `Wiki/index.md` and per-folder indexes, grouped by kind.
3. Fail if any field violates [`frontmatter-schema.md`](frontmatter-schema.md)
   (e.g. `source_count != len(sources)`, `tags[0]` not an allowed kind).

### lint
Run [`lint-checklist.md`](lint-checklist.md). Report findings prioritized;
broken structure first. Fix structural issues, then note content issues.

### source checks
For every compiled note:

1. Every `sources` path exists on disk and `source_count` matches.
2. Every `Raw/Sources/` source is referenced by ≥1 note, or still `Processed: false`.
3. No note claims a source it does not actually use.

### Then commit

- All three checks green → commit with a message like
  `wiki: ingest "The LLM Wiki Pattern" (+1 note)`.
- Any check red → fix before committing. Never commit a stale catalog or broken links.

Log the result: `python3 scripts/wiki_tool.py log --title "maintain: build ok, lint 0, sources ok"`.

---

## 4. Health check (`llm-wiki-lint`)

> Human: "Lint the wiki"

1. Run the checklist; produce a prioritized list (path · problem · action).
2. Structural first: orphan notes, broken `[[links]]`, unsourced notes.
3. Then content: stale, topic gaps, contradictions, missing cross-references.
4. Append `## [2026-09-22] lint | 3 findings (2 broken links)`.
