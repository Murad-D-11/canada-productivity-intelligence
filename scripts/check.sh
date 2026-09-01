#!/usr/bin/env bash
# Run static checks across the monorepo (macOS/Linux).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "==> Typecheck"; npm run typecheck
echo "==> Lint"; npm run lint
echo "==> Format check"; npm run format:check
echo "==> All checks passed"
