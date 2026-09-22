#!/usr/bin/env python3
"""Resolve a narrow context_pack from domain/entity/layer keys."""

from __future__ import annotations

import argparse
from pathlib import Path


def existing(root: Path, rel: str) -> str | None:
    path = root / rel
    return rel.replace("\\", "/") if path.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve partitioned context pack")
    parser.add_argument("--path", "-p", default=".", help="Project root")
    parser.add_argument("--microtask", "-m", default="MT-00")
    parser.add_argument("--domain", "-d", required=True)
    parser.add_argument("--entity", "-e", action="append", default=[])
    parser.add_argument("--layer", "-l", action="append", default=[])
    parser.add_argument("--contract", "-c", action="append", default=[])
    parser.add_argument("--write", action="store_true", help="Write .context/packs/<id>.md")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    must: list[str] = []
    optional: list[str] = []
    missing: list[str] = []

    index = ".context/INDEX.md"
    if existing(root, index):
        must.append(index)
    else:
        missing.append(index)

    domain_rel = f".context/domains/{args.domain}/overview.md"
    if existing(root, domain_rel):
        must.append(domain_rel)
    else:
        missing.append(domain_rel)

    for entity in args.entity:
        rel = f".context/entities/{entity}.md"
        if existing(root, rel):
            must.append(rel)
        else:
            missing.append(rel)

    for layer in args.layer:
        rel = f".context/layers/{layer}.md"
        if existing(root, rel):
            must.append(rel)
        else:
            missing.append(rel)

    for contract in args.contract:
        rel = f".context/contracts/{contract}.md"
        if existing(root, rel):
            optional.append(rel)
        else:
            missing.append(rel)

    # Keep packs small
    must = must[:7]

    entities = ", ".join(args.entity) if args.entity else ""
    layers = ", ".join(args.layer) if args.layer else ""
    must_yaml = "\n".join(f"    - {item}" for item in must) or "    []"
    optional_yaml = "\n".join(f"    - {item}" for item in optional) or "    []"

    doc = f"""# Context Pack — {args.microtask}

```yaml
context_pack:
  microtask_id: {args.microtask}
  domain: {args.domain}
  entities: [{entities}]
  layers: [{layers}]
  must_read:
{must_yaml}
  optional:
{optional_yaml}
  do_not_read:
    - .context/domains/**
```

## Missing paths
"""
    if missing:
        doc += "\n".join(f"- {item}" for item in missing) + "\n"
    else:
        doc += "- none\n"

    print(doc)
    if args.write:
        out = root / ".context" / "packs" / f"{args.microtask}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc, encoding="utf-8")
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
