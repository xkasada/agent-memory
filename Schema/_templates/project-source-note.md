---
Title: "{Project} — {kind}: {name}"
Author: "context-builder"
Reference: "project:{project}"
ContentType:
  - "markdown"
Created: YYYY-MM-DD
Processed: false
tags:
  - "source"
project: "{project}"
kind: "{index | context | domain | entity | layer | contract | tech | module | artifact}"
---

# {Title}

{Mirror of the project's `.context/` file. Captured from
`Raw/Projects/{project}/…` — keep the original content; `project-ingest` prepends
this frontmatter automatically, so do not hand-edit unless adding a raw file.}

> This is **source material**, not a compiled note. Raw source notes are write-once —
> never edit or delete after capture (only `Processed` may flip to `true`).
