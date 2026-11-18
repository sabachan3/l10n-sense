#!/usr/bin/env bash
# Gate tests: deterministic, local, no network, no model calls. Also the pre-commit hook.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
uv run --quiet --with pytest pytest -q services/llm/tests services/bench/tests services/review/tests
