# Layer: {presentation|application|domain|infrastructure}

## Responsibility
{что делает слой}

## Does NOT own
- {что запрещено класть сюда}

## Typical paths
| Area | Path |
|------|------|
| {routers / components / …} | `{path}` |
| {services / use-cases / …} | `{path}` |

## Rules for agents
- Read this layer when role/task needs `{…}`
- Prefer domain overview first, then this layer filter
- Avoid loading sibling layers unless pack says so

## Patterns in this project
- {pattern}: {где}

## Anti-patterns
- {anti-pattern}
