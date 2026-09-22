# Contract: {domain_a} ↔ {domain_b}

## Why it exists
{какой cross-domain use-case}

## Direction
`{from_domain}` → `{to_domain}` ({sync API / events / shared authz})

## Exposed surface
| Item | Type | Path / topic | Notes |
|------|------|--------------|-------|
| {GetUserRoles} | API / event | `{…}` | |

## Data exchanged
| Field | Type | Sensitivity | Notes |
|-------|------|-------------|-------|
| | | | |

## Guarantees
- {SLA / consistency / idempotency}

## Forbidden
- `{from}` must not read `{to}` internal tables/modules: `{paths}`

## Failure modes
| Failure | Handling |
|---------|----------|
| {timeout/unavailable} | {behavior} |
