# Architecture (legacy pointer)

> Flat `architecture.md` is deprecated for AI context.
> Use partitioned context instead:

- Router: `.context/INDEX.md`
- Business slices: `.context/domains/<domain>/overview.md`
- Cross-cutting layers: `.context/layers/{presentation,application,domain,infrastructure}.md`
- Boundaries: `.context/contracts/<a>-<b>.md`

If this file still exists in a repo, keep it as a short pointer only (< 40 lines), not a dump.

## Current system shape
{1–3 sentences}

## Where to read next
| Need | Path |
|------|------|
| Domain map | `.context/INDEX.md` |
| Specific capability | `.context/domains/<domain>/overview.md` |
| Layer rules | `.context/layers/<layer>.md` |
| Cross-domain API/events | `.context/contracts/<name>.md` |
