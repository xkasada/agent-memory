---
name: llm-wiki-query
description: Answer a question from the memory vault using Wiki/ and its catalog.jsonl, with citations, and file reusable answers back as new pages. Use when the user says "ask my brain", "query my wiki", "what does my brain say about X", "search my notes for X". Searches the catalog before opening broad Raw context; never invents citations.
---

# llm-wiki-query — answer from the corpus

Answer **only** from the vault corpus (`Wiki/` + cited `Raw/`). This is not external research.

## Steps

1. Read `AGENTS.md` and `Schema/frontmatter-schema.md`.
2. **Search the catalog first** —
   `python3 scripts/wiki_tool.py search-catalog --query "<text>"` (matches `title`,
   `topics`, `tags`, `sources`, `path`). Do **not** bulk-scan `Raw/` to answer.
3. Read the matched `Wiki/` pages; traverse `[[wikilinks]]` 1–2 hops.
4. Only then open the specific `Raw/Sources/` files those pages cite, if needed to
   verify or quote. Never open broad Raw context.
5. Compose the answer, citing pages by name: *"Per [[Incremental Compilation]]…"*.
   - If pages contradict each other, present both sides — do not pick one.
   - If the corpus lacks the answer, say so; offer external research. Do **not**
     answer from general model knowledge as if it came from the vault.
6. **File reusable answers back** as a new/updated `Wiki/` note (with full frontmatter
   and `sources`), so exploration compounds. Bump `updated`.
7. Log it: `python3 scripts/wiki_tool.py log --title "query: <question-slug>"`.
8. Show the answer in chat + link to the filed page.

## Hard constraints

- **Do not invent citations, sources, quotes, or authors.** Every claim traces to a
  page and, through it, to a raw source.
- Reusable knowledge only under `Wiki/` — never leave it in chat only if it is worth keeping.
