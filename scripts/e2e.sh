#!/usr/bin/env bash
# End to end, deterministic path only: build the sdist and the wheel, check them the way an
# upload would (twine), compare their contents with the lists in pyproject.toml file by file,
# install each into its own throwaway environment, and run both installed commands on fixture
# locale files with known problems. Model scoring is not covered here (scripts/eval.sh does that).
#
#   scripts/e2e.sh          build into a temporary directory and check that
#   scripts/e2e.sh DIR      check the one sdist and one wheel already in DIR (the release
#                           workflow does this, so the files it uploads are the files checked)
#
# Takes a few seconds and needs the network for the build backend and twine. Not part of the gate.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
repo="$PWD"
work="$(mktemp -d)"
trap 'rm -r "$work"' EXIT

fail() { echo "e2e FAIL: $1" >&2; exit 1; }

if [ "$#" -ge 1 ]; then
  [ -d "$1" ] || fail "$1 is not a directory"
  dist="$(cd "$1" && pwd)"
else
  dist="$work/dist"
  uv build --quiet --out-dir "$dist"   # the wheel is built from the sdist, so the sdist is proven complete
fi
shopt -s nullglob
wheels=("$dist"/*.whl); sdists=("$dist"/*.tar.gz)
shopt -u nullglob
[ "${#wheels[@]}" -eq 1 ] && [ "${#sdists[@]}" -eq 1 ] || fail "expected one wheel and one sdist in $dist, found ${#wheels[@]} and ${#sdists[@]}"
wheel="${wheels[0]}"; sdist="${sdists[0]}"

uvx --quiet twine check --strict "$wheel" "$sdist" > "$work/twine.txt" 2>&1 || { cat "$work/twine.txt" >&2; fail "twine check"; }

uv venv --quiet "$work/venv-wheel"
uv venv --quiet "$work/venv-sdist"
python="$work/venv-wheel/bin/python"

# Contents: both archives must hold exactly the files pyproject.toml and git name. Anything else
# (run outputs, benchmark data, agent settings, caches, an untracked file) fails the check.
git ls-files l10n_sense > "$work/package-files.txt"
"$python" -I - "$repo" "$wheel" "$sdist" "$work/package-files.txt" <<'PY' || fail "archive contents or metadata differ from pyproject.toml (lines above)"
import re, sys, tarfile, zipfile
from pathlib import Path
repo, wheel, sdist, package_list = (Path(arg) for arg in sys.argv[1:5])
pyproject = (repo / "pyproject.toml").read_text(encoding="utf-8")
version = re.search(r'^version = "([^"]+)"$', pyproject, re.M).group(1)
included = dict(re.findall(r'^"(services/[^"]+)" = "(l10n_sense/_services/[^"]+)"$', pyproject, re.M))
package = set(package_list.read_text(encoding="utf-8").split())
problems = []
if len(included) < 7:
    problems.append(f"only {len(included)} force-include lines were read from pyproject.toml, expected at least 7")
for needed in ("l10n_sense/_services/llm/llm.py", "l10n_sense/_services/llm_codex/codex.py"):
    if needed not in included.values():   # started by path on a model-scored run only: nothing below would notice one missing
        problems.append(f"{needed} is not listed in force-include")
if wheel.name != f"l10n_sense-{version}-py3-none-any.whl" or sdist.name != f"l10n_sense-{version}.tar.gz":
    problems.append(f"file names {wheel.name}, {sdist.name} do not carry version {version}")

info = f"l10n_sense-{version}.dist-info/"
expected_wheel = package | set(included.values()) | {info + name for name in ("METADATA", "WHEEL", "RECORD", "entry_points.txt", "licenses/LICENSE")}
with zipfile.ZipFile(wheel) as archive:
    in_wheel = {name for name in archive.namelist() if not name.endswith("/")}
    metadata = archive.read(info + "METADATA").decode("utf-8") if info + "METADATA" in in_wheel else ""
top = f"l10n_sense-{version}/"
expected_sdist = {top + name for name in package | set(included) | {"README.md", "LICENSE", "CHANGELOG.md", "pyproject.toml", "PKG-INFO", ".gitignore"}}
with tarfile.open(sdist) as archive:
    members = archive.getmembers()
    in_sdist = {member.name for member in members if member.isfile()}
    problems += [f"sdist: {member.name} is not a regular file" for member in members if not (member.isfile() or member.isdir())]
for label, found, expected in (("wheel", in_wheel, expected_wheel), ("sdist", in_sdist, expected_sdist)):
    problems += [f"{label}: unexpected {name}" for name in sorted(found - expected)]
    problems += [f"{label}: missing {name}" for name in sorted(expected - found)]

headers, _, body = metadata.partition("\n\n")
for line in ("Name: l10n-sense", f"Version: {version}", "License-Expression: MIT", "License-File: LICENSE", "Requires-Python: >=3.10",
             "Description-Content-Type: text/markdown"):
    if line not in headers.split("\n"):
        problems.append(f"wheel metadata lacks the line {line!r}")
if any(line.startswith("Requires-Dist:") and "extra ==" not in line for line in headers.split("\n")):
    problems.append("wheel metadata declares a runtime dependency (CLAUDE.md, hard constraint 11)")
if any(re.match(r"(Author|Maintainer)(-email)?: .*@(?!users\.noreply\.github\.com)", line) for line in headers.split("\n")):
    problems.append("wheel metadata carries an author email that is not a GitHub no-reply address")
if body.strip() != (repo / "README.md").read_text(encoding="utf-8").strip():
    problems.append("the long description in the wheel metadata is not README.md")
print("\n".join(problems), file=sys.stderr, end="\n" if problems else "")
sys.exit(1 if problems else 0)
PY

uv pip install --quiet --python "$work/venv-wheel/bin/python" "$wheel"
uv pip install --quiet --python "$work/venv-sdist/bin/python" "$sdist"   # builds a wheel from the sdist alone
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml)"
fixtures="$repo/tests/e2e"
cd "$work"   # away from the repository, so only the installed package can be imported

installed_files() {   # relative paths of the installed package, bytecode aside
  "$1/bin/python" -I -c 'import importlib.util, pathlib
root = pathlib.Path(importlib.util.find_spec("l10n_sense").origin).parent
print("\n".join(sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.suffix != ".pyc")))'
}
installed_files "$work/venv-wheel" > files-wheel.txt
installed_files "$work/venv-sdist" > files-sdist.txt
cmp -s files-wheel.txt files-sdist.txt || { diff files-wheel.txt files-sdist.txt >&2 || true; fail "the sdist installs different files than the wheel"; }
[ "$(wc -l < files-wheel.txt)" -ge 10 ] || fail "only $(wc -l < files-wheel.txt) files installed, expected the package and seven services"

for kind in wheel sdist; do
  cli="$work/venv-$kind/bin/l10n-sense"

  [ "$("$cli" --version)" = "l10n-sense $version" ] || fail "$kind: --version does not print l10n-sense $version"
  "$cli" --help > help.txt || fail "$kind: --help failed"

  code=0; "$cli" check --source "$fixtures/en.json" --target "$fixtures/ja.json" --lang ja --no-model \
    --format json > broken.json || code=$?
  [ "$code" -eq 1 ] || fail "$kind, broken file: exit $code, expected 1"
  "$work/venv-$kind/bin/python" - broken.json "$fixtures/expected.json" <<'PY' || fail "$kind, broken file: report differs from tests/e2e/expected.json"
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
print("\n".join(problems), file=sys.stderr, end="\n" if problems else "")
sys.exit(1 if problems else 0)
PY

  code=0; "$cli" check --source "$fixtures/en.json" --target "$fixtures/ja.clean.json" --lang ja --no-model > clean.txt || code=$?
  [ "$code" -eq 0 ] || fail "$kind, clean file: exit $code, expected 0"

  code=0; "$cli" check --source "$fixtures/en.json" --target "$work/absent.json" --lang ja --no-model > absent.txt 2>&1 || code=$?
  [ "$code" -eq 2 ] || fail "$kind, unreadable file: exit $code, expected 2"
done

echo "e2e ok: sdist and wheel $version pass twine check and hold only the listed files; installed from each, 5 known problems found (exit 1), clean file passes (exit 0), unreadable file exits 2"
