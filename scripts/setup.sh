#!/usr/bin/env bash
# Cross-workspace setup for macOS/Linux.
# Installs Node workspace dependencies and creates the Python ML environment.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Installing Node workspace dependencies"
(cd "$ROOT" && npm install)

echo "==> Setting up Python ML environment"
(cd "$ROOT/ml" && python3 -m venv .venv && ./.venv/bin/python -m pip install --upgrade pip && ./.venv/bin/python -m pip install -e ".[dev]")

echo "==> Setup complete"
