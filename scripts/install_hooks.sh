#!/usr/bin/env sh
# Install the vault's git hooks by pointing git at the in-repo .githooks/ directory.
# Run once from the vault:  sh scripts/install_hooks.sh
set -eu

vault_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$vault_root"

git config core.hooksPath .githooks
if [ -f .githooks/pre-commit ]; then
    chmod +x .githooks/pre-commit 2>/dev/null || true
fi

echo "Installed git hooks: core.hooksPath=.githooks"
echo "Pre-commit runs: wiki_tool.py build / lint / source-lint"
