#!/usr/bin/env python3
"""Deprecated flat-context generator. Use scaffold_context_tree.py instead."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DEPRECATED: redirects to scaffold_context_tree.py (partitioned model)"
    )
    parser.add_argument("--path", "-p", default=".")
    parser.add_argument("--name", "-n", default=None)
    parser.add_argument("--db", "-d", default=None, help="Ignored (legacy)")
    args = parser.parse_args()

    script = Path(__file__).with_name("scaffold_context_tree.py")
    cmd = [sys.executable, str(script), "-p", args.path]
    if args.name:
        cmd.extend(["-n", args.name])

    print(
        "WARNING: generate_full_context.py is deprecated.\n"
        "Partitioned context uses scaffold_context_tree.py "
        "(INDEX + domains/entities/layers/contracts).\n"
    )
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
