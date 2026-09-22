# Entity: {EntityName}

## Owner domain
`{domain}` → `.context/domains/{domain}/overview.md`

## Definition
{что это за сущность, 1–2 предложения}

## Identity & lifecycle
- ID: `{field}` ({type})
- Created/updated: `{rules}`
- Deleted: `{soft/hard/forbidden}`

## Key fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | {uuid} | yes | PK |
| | | | |

## Relationships
| Related | Type | Notes |
|---------|------|-------|
| {OtherEntity} | {1:N} | owner: `{domain}` |

## Persistence
- Table/collection: `{name}`
- Repo/path: `{code path}`

## API surface (if exposed)
| Operation | Endpoint / message | Notes |
|-----------|--------------------|-------|
| create | `{METHOD /path}` | |

## Invariants
- {invariant}

## Do not confuse with
- {похожая сущность} — отличие: {…}
