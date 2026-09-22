# Routing Rules — which partition to open

## Decision tree

```text
Task arrives
  └─ read INDEX.md
      ├─ identify primary business domain  → domains/<d>/overview.md
      ├─ list touched entities             → entities/<E>.md (only those)
      ├─ filter by role/layer              → layers/<layer>.md
      ├─ crosses domain boundary?          → contracts/<a>-<b>.md
      └─ STOP (3–7 must_read files)
```

## Prefer domain over folder names

| Signal in task | Partition |
|----------------|-----------|
| invoice, payment, tariff | `domains/billing` |
| login, token, role, session | `domains/auth` |
| export csv/xlsx, report file | `domains/export` |
| Dockerfile, CI, health | `layers/infrastructure` + `tech/runtime` |
| Vue/React page/form | `layers/presentation` + domain overview |

## Split / merge heuristics

Split domain when:
- overview > ~300 lines
- two teams/capabilities change independently
- pack for one task keeps pulling unrelated half of overview

Merge when:
- two domains always co-read
- each leaf < ~80 lines and contract between them is noise

## Anti-patterns

- Reading all `domains/**` “to be safe”
- Putting full DB schema into INDEX
- Layer-only split without business domains on a large system
- 20 tiny files for one microtask (too many reads)
- One monolithic `CONTEXT.md` as source of truth
