#!/usr/bin/env bash
# One-time (and repeatable) setup after cloning: commit hook, tool check, then the gate.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
command -v uv >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
git config core.hooksPath .githooks
uv sync --quiet --extra yaml
scripts/test.sh
echo "setup ok: hook path set, environment synced, gate green"
