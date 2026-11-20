#!/usr/bin/env bash
# Gate tests: deterministic, local, no network, no model calls. Also the pre-commit hook.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
uv run --quiet --with-requirements requirements-gate.txt pytest -q services/llm/tests services/bench/tests services/review/tests services/extract/tests services/judge/tests services/score/tests services/llm_codex/tests services/rules/tests services/check/tests services/formats/tests tests
