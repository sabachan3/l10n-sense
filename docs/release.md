# Releasing to PyPI

Steps for the owner. Nothing here is run by an agent (CLAUDE.md, "Ask the owner first").
The upload itself is done by `.github/workflows/release.yml` with PyPI trusted publishing: no
token or password exists, on GitHub or on any machine.

What the workflow does, in order: the gate on the same systems and Python versions as CI; a
build of the sdist and the wheel; `scripts/e2e.sh dist` on exactly those two files (twine check,
contents compared with `pyproject.toml` file by file, install from each, run the installed
command); then the upload. A failure anywhere before the upload uploads nothing.

It starts when a GitHub release is published, or by hand. A push never starts it. Started by
hand it uploads nowhere unless told to (`-f target=testpypi` or `-f target=pypi`).

## Once, before the first release

1. PyPI account with two-factor sign-in: <https://pypi.org/account/register/>.
2. Check the name is still free (a pending publisher does not reserve it); `404` means free:

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://pypi.org/pypi/l10n-sense/json
   ```

3. Add a pending trusted publisher at <https://pypi.org/manage/account/publishing/>
   ("Add a new pending publisher", GitHub tab), with exactly these values:

   | field | value |
   |---|---|
   | PyPI Project Name | `l10n-sense` |
   | Owner | `sabachan3` |
   | Repository name | `l10n-sense` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. On GitHub, repository Settings, Environments, "New environment", name `pypi`. Recommended:
   add yourself under "Required reviewers", so every upload waits for one click of approval.
5. Optional rehearsal on TestPyPI (a separate site with separate accounts). Repeat steps 1, 3 and
   4 on <https://test.pypi.org/manage/account/publishing/> with environment name `testpypi`, then:

   ```bash
   gh workflow run release.yml -f target=testpypi
   gh run watch
   uvx --index-url https://test.pypi.org/simple/ l10n-sense --version   # l10n-sense 0.1.0
   ```

   The same version cannot be uploaded to TestPyPI twice either.

A run that builds and checks but uploads nowhere needs none of the above:

```bash
gh workflow run release.yml && gh run watch
```

## Each release

1. `main` holds what is to be released, is pushed, and CI is green on that commit:

   ```bash
   git switch main && git pull --ff-only && git status --short   # prints nothing
   gh run list --workflow ci.yml --branch main --limit 1
   scripts/test.sh && scripts/e2e.sh
   ```

2. The version is the same in `pyproject.toml`, `l10n_sense/__init__.py` and the newest entry of
   `CHANGELOG.md` (the gate fails otherwise). For a release after 0.1.0: change all three, run
   `uv lock`, commit, push.
3. Tag and publish the GitHub release. The tag must be `v` plus the version; the workflow stops
   before the upload when it is not.

   ```bash
   version="$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml)"
   git tag -a "v$version" -m "l10n-sense $version"
   git push origin "v$version"
   awk -v v="$version" '/^## /{on = ($2 == v)} on' CHANGELOG.md | tail -n +3 > /tmp/l10n-sense-notes.md
   gh release create "v$version" --verify-tag --title "l10n-sense $version" --notes-file /tmp/l10n-sense-notes.md
   gh run watch   # approve the `pypi` environment when it asks
   ```

4. Verify from PyPI, outside the repository:

   ```bash
   cd "$(mktemp -d)"
   uvx --refresh l10n-sense --version    # l10n-sense <version>
   uvx l10n-sense --help
   pipx run l10n-sense --version
   ```

   Then read <https://pypi.org/project/l10n-sense/> once: the page is `README.md`.

5. After the first release only, in one commit:
   - `README.md`, "Install": put the PyPI commands first, the install-from-GitHub command below
     them, and delete the sentence "After the first release on PyPI these will work; today they do not:"
     and "Not on PyPI yet".
   - `tests/test_release.py`: `test_readme_offers_the_repository_install_and_marks_pypi_commands_as_not_yet_working`
     describes the state before the release. Replace it with one that expects the PyPI commands first.
   - `docs/github-actions.yml`: delete the two comment lines that start at "Until l10n-sense is on PyPI".
   - `CLAUDE.md` and `PROGRESS.md`: "not on PyPI" is no longer true.

## When the upload fails

Before the upload step nothing has left GitHub: fix, and for a release that already exists
start the workflow by hand from the tag (`gh workflow run release.yml --ref v0.1.0 -f target=pypi`).
PyPI never accepts the same file name twice. If the upload stopped after one of the two files,
or the files are wrong, do not try to replace them: raise the version (0.1.1) and release that.

## Taking a bad release back

Yank it; do not delete it.

1. <https://pypi.org/manage/project/l10n-sense/releases/>, the release's "Options", "Yank", and
   give a reason (it is shown to users).
2. A yanked version is skipped by `pip install l10n-sense`, `uvx l10n-sense` and `pipx`, and still
   installs for someone who pinned it exactly (`l10n-sense==0.1.0`), with the reason as a warning.
   Yanking can be undone in the same place.
3. Release the fix under a new version. A version number is used up for good, yanked or deleted.
4. Edit the GitHub release notes to say the version was yanked and why.

Deleting is only for a file that must not stay downloadable (a secret inside it). Yanking does
not remove the files. Delete the release on the same page, and treat the secret as leaked anyway.

## Licences (checked 2026-11-22)

The project is MIT (`LICENSE`, `license = "MIT"` in `pyproject.toml`).

| what | role | licence | conflict with MIT |
|---|---|---|---|
| (none) | runtime dependency | | the wheel declares none; the shipped files import the standard library only |
| PyYAML 6 | optional, the `yaml` extra; installed separately, not bundled | MIT | no |
| hatchling | build backend; not shipped | MIT | no |
| pytest 9.2.0 and what it pulls in (pluggy, iniconfig: MIT; packaging: Apache-2.0 or BSD-2-Clause; pygments: BSD-2-Clause; on some systems colorama: BSD-3-Clause, exceptiongroup: MIT, tomli: MIT, typing-extensions: PSF-2.0) | gate only; not shipped | as listed | no |
| twine | package check in `scripts/e2e.sh`; not shipped | Apache-2.0 | no |
| Claude Code CLI, Codex CLI | started as separate programs when a model score is asked for; installed by the user, not shipped, not linked | their own terms | no: nothing of theirs is distributed |

Data files. The sdist and the wheel contain no data file at all (`scripts/e2e.sh` fails on any
file outside the lists in `pyproject.toml`). In the repository only:

| file | origin | licence |
|---|---|---|
| `data/bench/real.omniroute.zh.jsonl`, strings quoted in `docs/audit-omniroute-ja-sample.md` | OmniRoute, commits named in `data/bench/NOTICE.md` | MIT; full text in `data/bench/LICENSE.OmniRoute` |
| `data/bench/injected.ja.jsonl`, `services/bench/ja_translations.json`, `tests/e2e/*.json` | written for this project | MIT, as the project |
