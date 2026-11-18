#!/usr/bin/env bash
# Periodic evals: uses model calls, takes a few minutes. Run before a release and after
# changing a prompt or upgrading a CLI. Fails when a threshold is missed.
#   scripts/eval.sh            # Claude scorer on the known-truth benchmark
#   scripts/eval.sh codex      # also the Codex isolation check and the Codex scorer
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p runs/eval
run_scorer() {  # $1 = service
  local out="runs/eval/injected.ja.$1.jsonl"
  rm -f "$out"
  python3 services/score/score.py --service "$1" --cases data/bench/injected.ja.jsonl --out "$out" | tail -1
  python3 services/score/check_thresholds.py --cases data/bench/injected.ja.jsonl --scores "$out" --min-precision 0.9 --min-recall 0.7
}
run_scorer claude
if [ "${1:-}" = "codex" ]; then
  python3 services/llm_codex/eval_isolation.py
  run_scorer codex
fi
