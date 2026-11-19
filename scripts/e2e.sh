#!/usr/bin/env bash
# End to end, deterministic path only: build the wheel, install it into a throwaway
# environment, run the installed command on fixture locale files with known problems and
# compare exit codes and findings. Model scoring is not covered here (scripts/eval.sh does that).
# Takes a few seconds and needs the network once for the build backend. Not part of the gate.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
work="$(mktemp -d)"
trap 'rm -r "$work"' EXIT
uv build --quiet --wheel --out-dir "$work/dist"
uv venv --quiet "$work/venv"
uv pip install --quiet --python "$work/venv/bin/python" "$work"/dist/*.whl
cli="$work/venv/bin/l10n-sense"
fixtures="$PWD/tests/e2e"
cd "$work"   # away from the repository, so only the installed package can be imported

fail() { echo "e2e FAIL: $1" >&2; exit 1; }

code=0; "$cli" check --source "$fixtures/en.json" --target "$fixtures/ja.json" --lang ja --no-model \
  --format json > broken.json || code=$?
[ "$code" -eq 1 ] || fail "broken file: exit $code, expected 1"
"$work/venv/bin/python" - broken.json "$fixtures/expected.json" <<'PY' || fail "broken file: report differs from tests/e2e/expected.json"
import json, sys
report, expected = (json.load(open(path, encoding="utf-8")) for path in sys.argv[1:3])
rules = {item["key"]: [rule["rule"] for rule in item["rules"]] for item in report["strings"]}
problems = []
if report["version"] != 1:
    problems.append(f"version {report['version']}")
if report["summary"] != expected["summary"]:
    problems.append(f"summary {report['summary']}")
if rules != expected["rules"]:
    problems.append(f"rules {rules}")
print("\n".join(problems), file=sys.stderr)
sys.exit(1 if problems else 0)
PY

code=0; "$cli" check --source "$fixtures/en.json" --target "$fixtures/ja.clean.json" --lang ja --no-model > clean.txt || code=$?
[ "$code" -eq 0 ] || fail "clean file: exit $code, expected 0"

code=0; "$cli" check --source "$fixtures/en.json" --target "$work/absent.json" --lang ja --no-model > absent.txt 2>&1 || code=$?
[ "$code" -eq 2 ] || fail "unreadable file: exit $code, expected 2"

echo "e2e ok: installed wheel, 5 known problems found (exit 1), clean file passes (exit 0), unreadable file exits 2"
