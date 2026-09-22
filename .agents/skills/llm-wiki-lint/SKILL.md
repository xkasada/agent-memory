---
name: llm-wiki-lint
description: Health-check the memory vault wiki for orphan pages, broken wikilinks, unsourced pages, stale content, topic gaps, and contradictions. Use when the user says "lint the wiki", "health check my brain", "check the vault". Produces a prioritized findings list and appends to the log.
---

# llm-wiki-lint — wiki health check

Follow `Schema/lint-checklist.md`. Report findings prioritized: **broken structure
beats stale content**.

## Checks (structure → sources → content)

Automate the mechanical checks first:

```bash
python3 scripts/wiki_tool.py lint          # frontmatter, tags, source_count, links
python3 scripts/wiki_tool.py source-lint   # source frontmatter + coverage
```

Then apply judgment to the remaining items.

1. **Build/frontmatter** — every note has valid frontmatter per `frontmatter-schema.md`;
   `catalog.jsonl` is current.
2. **Orphan pages** — `Wiki/**/*.md` absent from `Wiki/index.md` / `catalog.jsonl`.
3. **Connection orphans** — pages with no `[[wikilink]]` / empty `## Connections`.
4. **Broken links** — `[[wikilinks]]` pointing at non-existent pages.
5. **Source checks** — every compiled note has ≥1 real `sources` path and
   `source_count == len(sources)`; every `Raw/Sources/` source is referenced or still
   `Processed: false`.
6. **Unprocessed raw** — `Raw/Sources/` files not yet compiled, without reason.
7. **Stale pages** — newest source >6 months old AND topic volatile
   (AI, tech, finance, health protocols) → mark `status: stale`.
8. **Topic gaps** — concepts mentioned in 3+ pages without their own page.
9. **Contradictions** — opposing claims not flagged on-page.
10. **Missing cross-references** — related pages left unlinked.

## Output

- Prioritized list: path · problem · suggested action.
- Log it: `python3 scripts/wiki_tool.py log --title "lint: <n> findings (<top issue>)"`.
- Optionally propose new questions to investigate or sources to seek.

## Don't

- Don't silently delete content to "fix" a finding — propose, then act on approval.
- Don't modify `Raw/` or `.obsidian/`.
