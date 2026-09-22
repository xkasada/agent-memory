#!/usr/bin/env python3
"""Collect lightweight project signals for partitioned .context/ scaffolding."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Optional


SKIP_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    "coverage",
    ".context",
    "workflow",
}

CODE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".java", ".cs", ".go", ".rs"}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def detect_stack(root: Path) -> dict:
    stack = {"language": "unknown", "framework": None, "package_managers": [], "db": []}

    if (root / "package.json").exists():
        stack["language"] = "javascript/typescript"
        stack["package_managers"].append("npm")
        pkg = read_text(root / "package.json").lower()
        if "nuxt" in pkg or (root / "nuxt.config.ts").exists():
            stack["framework"] = "nuxt"
        elif "vue" in pkg or (root / "vue.config.js").exists():
            stack["framework"] = "vue"
        elif "react" in pkg:
            stack["framework"] = "react"
        elif "next" in pkg:
            stack["framework"] = "next"

    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        stack["language"] = "python" if stack["language"] == "unknown" else stack["language"] + "+python"
        stack["package_managers"].append("pip/poetry")
        blob = read_text(root / "pyproject.toml") + "\n" + read_text(root / "requirements.txt")
        low = blob.lower()
        if "fastapi" in low:
            stack["framework"] = "fastapi"
        elif "django" in low:
            stack["framework"] = "django"
        elif "flask" in low:
            stack["framework"] = "flask"
        if "psycopg" in low or "asyncpg" in low or "postgres" in low:
            stack["db"].append("postgresql")
        if "redis" in low:
            stack["db"].append("redis")
        if "sqlalchemy" in low:
            stack["db"].append("sqlalchemy")

    if (root / "go.mod").exists():
        stack["language"] = "go"
    if (root / "Cargo.toml").exists():
        stack["language"] = "rust"

    compose = root / "docker-compose.yml"
    if not compose.exists():
        compose = root / "compose.yml"
    if compose.exists():
        low = read_text(compose).lower()
        if "postgres" in low and "postgresql" not in stack["db"]:
            stack["db"].append("postgresql")
        if "redis" in low and "redis" not in stack["db"]:
            stack["db"].append("redis")

    return stack


def iter_code_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in CODE_EXTS:
            yield path


def count_files(root: Path) -> int:
    return sum(1 for _ in iter_code_files(root))


def determine_size(file_count: int) -> str:
    if file_count < 10:
        return "small"
    if file_count < 50:
        return "medium"
    return "large"


def suggest_domains(root: Path, limit: int = 8) -> list[str]:
    """Heuristic domain names from top-level package folders."""
    candidates: Counter[str] = Counter()
    roots = [root / "src", root / "app", root / "backend", root / "frontend", root]
    stop = {
        "src",
        "app",
        "backend",
        "frontend",
        "lib",
        "libs",
        "tests",
        "test",
        "scripts",
        "components",
        "utils",
        "helpers",
        "common",
        "core",
        "shared",
        "internal",
        "pkg",
        "api",
        "routers",
        "services",
        "models",
        "repositories",
        "schemas",
        "static",
        "assets",
        "node_modules",
    }

    for base in roots:
        if not base.exists() or not base.is_dir():
            continue
        for child in base.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            name = child.name.lower().replace("-", "_")
            if name in stop or name in SKIP_DIRS:
                continue
            if re.fullmatch(r"[a-z][a-z0-9_]{1,24}", name):
                candidates[name] += 1

    # Prefer names that look business-like if present in paths
    for path in iter_code_files(root):
        for part in path.parts:
            p = part.lower().replace("-", "_")
            if p in {
                "auth",
                "billing",
                "payment",
                "payments",
                "users",
                "orders",
                "export",
                "reports",
                "inventory",
                "notifications",
                "admin",
            }:
                candidates[p] += 3

    return [name for name, _ in candidates.most_common(limit)]


def shallow_tree(root: Path, max_depth: int = 2) -> dict:
    def walk(dir_path: Path, depth: int) -> dict:
        if depth >= max_depth:
            return {"...": "truncated"}
        out: dict = {}
        try:
            items = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return {"[permission denied]": ""}
        for item in items:
            if item.name in SKIP_DIRS or item.name.startswith("."):
                continue
            if item.is_dir():
                out[item.name + "/"] = walk(item, depth + 1)
            else:
                out[item.name] = item.suffix
        return out

    return walk(root, 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect project signals for partitioned context")
    parser.add_argument("--path", "-p", default=".", help="Project root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    file_count = count_files(root)
    size = determine_size(file_count)
    stack = detect_stack(root)
    domains = suggest_domains(root)
    payload = {
        "project": root.name,
        "root": str(root),
        "size": size,
        "code_files": file_count,
        "stack": stack,
        "suggested_domains": domains,
        "context_root": str(root / ".context"),
        "index_path": str(root / ".context" / "INDEX.md"),
        "tree_shallow": shallow_tree(root),
        "next_step": "py -3 scripts/scaffold_context_tree.py -p . -n " + root.name,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"Project: {payload['project']}")
    print(f"Size: {size} ({file_count} code files)")
    print(f"Language: {stack['language']}")
    print(f"Framework: {stack['framework'] or 'n/a'}")
    print(f"DB signals: {', '.join(stack['db']) or 'n/a'}")
    print(f"Suggested domains: {', '.join(domains) or '(none — define manually)'}")
    print(f"INDEX target: {payload['index_path']}")
    print("Next: scaffold with scripts/scaffold_context_tree.py")


if __name__ == "__main__":
    main()
