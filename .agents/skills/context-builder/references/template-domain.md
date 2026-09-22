# Domain: {domain_name}

## Purpose
{1–3 предложения: зачем домен существует}

## In scope
- {capability}
- {capability}

## Out of scope
- {что принадлежит другим доменам}

## Key entities
| Entity | Role in domain | Path |
|--------|----------------|------|
| {Entity} | {aggregate / read model / …} | `.context/entities/{Entity}.md` |

## Code map (dense)
| Area | Path | Notes |
|------|------|-------|
| API / routes | `{path}` | |
| Services | `{path}` | |
| Persistence | `{path}` | |
| UI (if any) | `{path}` | |

## Invariants
- {бизнес-инвариант}
- {бизнес-инвариант}

## External dependencies
| Dep | Why | Contract |
|-----|-----|----------|
| {auth} | {roles for invoices} | `.context/contracts/{domain}-auth.md` |

## Edge cases (domain-local)
| Case | Expected |
|------|----------|
| {case} | {behavior} |

## Open questions / TBD
- {TBD}
