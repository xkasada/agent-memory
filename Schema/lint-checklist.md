# Lint checklist

Routine wiki health check. Run on demand, and as part of the pre-commit gate
(`llm-wiki-maintain`). Report findings prioritized: **broken structure beats stale content**.

Automated: `python3 scripts/wiki_tool.py lint` (sections 0–3, 4) and
`python3 scripts/wiki_tool.py source-lint` (section 4). The remaining sections are
judgment calls for the agent.

## 0. Build checks (frontmatter)

- [ ] Every `Wiki/**/*.md` (except generated `index.md` and `Wiki/log.md`) has parseable frontmatter.
- [ ] Compiled notes carry required fields per [`frontmatter-schema.md`](frontmatter-schema.md):
      `tags`, `status`, `created`, `updated`, `sources`, `source_count` (plus optional `topics`, `aliases`).
- [ ] `tags[0]` is one of `topic | concept | entity | project | log` and matches the folder.
- [ ] Filename stem == H1 title.
- [ ] `source_count == len(sources)`.
- [ ] `status` ∈ `seed | growing | mature | stale`.
- [ ] `updated` >= `created`; both ISO `YYYY-MM-DD`.
- [ ] Source notes in `Raw/Sources/` have `tags: ["source"]` and boolean `Processed`.
- [ ] `Wiki/catalog.jsonl` is current (rebuilt after the last frontmatter change).

## 1. Orphan pages

- [ ] Every `Wiki/**/*.md` (except generated indexes and `Wiki/log.md`) appears in
      `Wiki/index.md` and `Wiki/catalog.jsonl`.
- [ ] No page is unreachable from the index.

## 2. Connection orphans

- [ ] Every page has a `## Connections` section with ≥1 `[[wikilink]]`.
- [ ] No page links only to itself.

## 3. Broken / missing links

- [ ] Every `[[wikilink]]` resolves to an existing page (or a deliberate pending stub).
- [ ] Clearly related pages are linked (else run the connect step of `llm-wiki-maintain`).

## 4. Source checks

- [ ] Every compiled note's `sources` is non-empty (a pure index/log note may be empty).
- [ ] Every `sources` path exists on disk; `source_count` matches the list length.
- [ ] Every `Raw/Sources/` source note is referenced by ≥1 compiled note, or still `Processed: false`.
- [ ] No note claims a source it does not actually use; no invented citations.
- [ ] `## Sources` in the body mirrors frontmatter `sources`.

## 5. Unprocessed raw

- [ ] Nothing in `Raw/Sources/` has been sitting unprocessed without reason.

## 6. Stale pages

- [ ] Pages whose newest source is >6 months old **and** whose topic is volatile
      (AI, tech, finance, health protocols) are flagged for refresh (`status: stale`).
- [ ] Superseded claims are marked, not silently left.

## 7. Topic gaps

- [ ] Concepts mentioned across 3+ pages without their own dedicated page are listed
      as candidate new pages.

## 8. Contradictions

- [ ] Opposing claims between pages are flagged on-page, with both sides represented.
- [ ] No silent side-picking, no unsupported synthesis.

## Output

- Prioritized list, most important first (structure → sources → content).
- For each finding: page/path, the problem, the suggested action.
- Append to `Wiki/log.md`:
  `## [YYYY-MM-DD] lint: <n> findings (<top issue>)`.
- Optionally propose new questions to investigate or sources to seek.
