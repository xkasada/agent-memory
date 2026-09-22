# Context INDEX — {project_name}

> Always-read router. Keep under ~100 lines. Do not dump full architecture here.

## Project one-liner
{что это за система, 1–2 предложения}

## Stack (pointer)
See `.context/tech/techstack.md`  
Runtime: `.context/tech/runtime.md`

## Domains (primary partitions)

| Domain | Owns | Path | When to read |
|--------|------|------|--------------|
| {auth} | {login, tokens, sessions} | `.context/domains/auth/overview.md` | auth/session/permission tasks |
| {billing} | {invoices, payments} | `.context/domains/billing/overview.md` | billing/payment tasks |

## Entities → owner domain

| Entity | Owner domain | Path |
|--------|--------------|------|
| {User} | {auth} | `.context/entities/User.md` |
| {Invoice} | {billing} | `.context/entities/Invoice.md` |

## Layers (secondary filter)

| Layer | Path | Typical roles |
|-------|------|---------------|
| presentation | `.context/layers/presentation.md` | frontend |
| application | `.context/layers/application.md` | backend, analyst |
| domain | `.context/layers/domain.md` | backend, analyst |
| infrastructure | `.context/layers/infrastructure.md` | backend, devops |

## Contracts (cross-domain only)

| Contract | Path | Use when |
|----------|------|----------|
| {billing-auth} | `.context/contracts/billing-auth.md` | billing needs identity/roles |

## Pack selection cheat-sheet

1. Read this INDEX
2. Pick **one** primary domain row
3. Add 1–3 entities
4. Add layers by role
5. Add contracts only if crossing domains
6. Stop at 3–7 files in `must_read`

## Do not always-read

- whole `.context/domains/**`
- full DB dumps unrelated to current domain
- other domains' internals (use contracts)
