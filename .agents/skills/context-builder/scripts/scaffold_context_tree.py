#!/usr/bin/env python3
"""Scaffold partitioned .context/ tree (INDEX + domains/entities/layers/contracts)."""

from __future__ import annotations

import argparse
from pathlib import Path


LAYER_NAMES = ("presentation", "application", "domain", "infrastructure")


def write_if_missing(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return f"skip (exists): {path}"
    path.write_text(content, encoding="utf-8")
    return f"created: {path}"


def index_template(project: str, domains: list[str]) -> str:
    rows = []
    for d in domains:
        rows.append(f"| {d} | TBD | `.context/domains/{d}/overview.md` | tasks in {d} |")
    if not rows:
        rows.append("| example | TBD capabilities | `.context/domains/example/overview.md` | replace me |")
    domain_table = "\n".join(rows)
    return f"""# Context INDEX — {project}

> Always-read router. Keep under ~100 lines.

## Project one-liner
TBD: what this system does

## Stack (pointer)
See `.context/tech/techstack.md`  
Runtime: `.context/tech/runtime.md`

## Domains (primary partitions)

| Domain | Owns | Path | When to read |
|--------|------|------|--------------|
{domain_table}

## Entities → owner domain

| Entity | Owner domain | Path |
|--------|--------------|------|
| TBD | TBD | `.context/entities/TBD.md` |

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
| TBD | `.context/contracts/TBD.md` | crossing domains |

## Pack selection cheat-sheet

1. Read this INDEX
2. Pick one primary domain
3. Add 1–3 entities
4. Add layers by role
5. Add contracts only if crossing domains
6. Stop at 3–7 `must_read` files

## Do not always-read

- whole `.context/domains/**`
- unrelated DB dumps
- other domains' internals (use contracts)
"""


def domain_template(name: str) -> str:
    return f"""# Domain: {name}

## Purpose
TBD

## In scope
- TBD

## Out of scope
- TBD

## Key entities
| Entity | Role in domain | Path |
|--------|----------------|------|
| TBD | TBD | `.context/entities/TBD.md` |

## Code map (dense)
| Area | Path | Notes |
|------|------|-------|
| API / routes | TBD | |
| Services | TBD | |
| Persistence | TBD | |

## Invariants
- TBD

## External dependencies
| Dep | Why | Contract |
|-----|-----|----------|
| | | |

## Edge cases (domain-local)
| Case | Expected |
|------|----------|
| | |

## Open questions / TBD
- Fill from code and product docs; do not invent facts
"""


def entity_template(name: str = "TBD") -> str:
    return f"""# Entity: {name}

## Owner domain
`TBD` → `.context/domains/TBD/overview.md`

## Definition
TBD

## Identity & lifecycle
- ID: TBD
- Deleted: TBD

## Key fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | TBD | yes | PK |

## Relationships
| Related | Type | Notes |
|---------|------|-------|
| | | |

## Persistence
- Table/collection: TBD
- Repo/path: TBD

## Invariants
- TBD
"""


def layer_template(layer: str) -> str:
    return f"""# Layer: {layer}

## Responsibility
TBD for `{layer}`

## Does NOT own
- TBD

## Typical paths
| Area | Path |
|------|------|
| TBD | TBD |

## Rules for agents
- Read when pack/role requires `{layer}`
- Prefer domain overview first

## Patterns in this project
- TBD

## Anti-patterns
- TBD
"""


def techstack_template(project: str) -> str:
    return f"""# Tech Stack — {project}

## Languages & versions
| Component | Version | Notes |
|-----------|---------|-------|
| TBD | TBD | |

## Critical dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| | | |

## Constraints
- Forbidden: TBD
- Required: TBD

## Env vars (names only, no secrets)
| Variable | Required | Description |
|----------|----------|-------------|
| | | |
"""


def runtime_template(project: str) -> str:
    return f"""# Runtime — {project}

## How to run locally (Windows PowerShell)
```powershell
TBD
```

## Services
| Service | Port | Image/path | Healthcheck |
|---------|------|------------|-------------|
| | | | |

## Compose / CI pointers
- Compose: TBD
- CI: `.gitlab-ci.yml`

## Notes for devops pack
- Prefer this file + infrastructure layer over business entity docs
"""


def contextignore_template() -> str:
    return """# Generated / vendor
node_modules/
dist/
build/
__pycache__/
*.pyc
.venv/
vendor/
target/
coverage/

# IDE / VCS
.idea/
.vscode/
.git/
.DS_Store

# Secrets
.env
.env.*
*.pem
*.key

# Logs / local data
*.log
logs/
*.sqlite
*.db
"""


def scaffold(root: Path, project: str, domains: list[str]) -> list[str]:
    ctx = root / ".context"
    actions: list[str] = []

    if not domains:
        domains = ["example"]

    actions.append(write_if_missing(ctx / "INDEX.md", index_template(project, domains)))
    actions.append(write_if_missing(ctx / "tech" / "techstack.md", techstack_template(project)))
    actions.append(write_if_missing(ctx / "tech" / "runtime.md", runtime_template(project)))
    actions.append(write_if_missing(ctx / ".contextignore", contextignore_template()))
    actions.append(write_if_missing(ctx / "packs" / ".gitkeep", ""))

    for layer in LAYER_NAMES:
        actions.append(write_if_missing(ctx / "layers" / f"{layer}.md", layer_template(layer)))

    for domain in domains:
        actions.append(
            write_if_missing(ctx / "domains" / domain / "overview.md", domain_template(domain))
        )

    actions.append(write_if_missing(ctx / "entities" / "TBD.md", entity_template("TBD")))
    actions.append(
        write_if_missing(
            ctx / "contracts" / "TBD.md",
            """# Contract: TBD ↔ TBD

## Why it exists
TBD

## Direction
`from` → `to`

## Exposed surface
| Item | Type | Path / topic | Notes |
|------|------|--------------|-------|
| | | | |

## Forbidden
- Do not read other domain internals; use this contract
""",
        )
    )

    # Optional stub redirect for legacy root CONTEXT.md
    legacy = root / "CONTEXT.md"
    if not legacy.exists():
        actions.append(
            write_if_missing(
                legacy,
                f"""# {project} — context stub

Primary AI context router: `.context/INDEX.md`

Use partitioned packs under `.context/packs/` for microtasks.
Do not treat this file as a full dump of the system.
""",
            )
        )
    return actions


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold partitioned .context tree")
    parser.add_argument("--path", "-p", default=".", help="Project root")
    parser.add_argument("--name", "-n", default=None, help="Project name")
    parser.add_argument(
        "--domain",
        "-d",
        action="append",
        default=[],
        help="Domain partition (repeatable). Default: example",
    )
    args = parser.parse_args()

    root = Path(args.path).resolve()
    project = args.name or root.name
    domains = args.domain or []

    print(f"Scaffolding partitioned context for: {project}")
    for line in scaffold(root, project, domains):
        print(line)
    print(f"\nDone. Edit {root / '.context' / 'INDEX.md'} first, then fill domain leaves.")


if __name__ == "__main__":
    main()
