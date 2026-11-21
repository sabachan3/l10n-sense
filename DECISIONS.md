# Decisions

One entry per decision that a later change could undo by accident. Newest first.

## 2026-11-22: the sdist holds only what builds the wheel

- **Decision:** the sdist lists its files one by one (`only-include`): the package, the seven
  runtime service files, `README.md`, `LICENSE`, `CHANGELOG.md`, `pyproject.toml`. `scripts/e2e.sh`
  compares both archives with those lists and fails on any other file.
- **Reason:** the earlier rule took the whole of `services/` and `contracts/`, which put the
  benchmark builders, a translation data file, the judging page and tests that cannot run without
  the rest of the repository on PyPI. An exact list cannot grow by accident.
- **Rejected:** shipping the tests in the sdist (they need `tests/`, `data/bench/` and the gate
  requirements, so they would not run from the sdist alone; the repository is where they run);
  a deny-list of paths (a new directory would ship until someone remembered to add it).

## 2026-11-22: releases are uploaded by a workflow with trusted publishing, never from a machine

- **Decision:** `.github/workflows/release.yml` uploads to PyPI through OIDC from the `pypi`
  environment. It starts on a published GitHub release or by hand (uploading nowhere by default),
  never on a push. It runs the gate matrix and `scripts/e2e.sh dist` on the very files it uploads.
  A TestPyPI job exists for a rehearsal started by hand.
- **Reason:** no token exists to leak or to rotate; the files users get are the files that were checked.
- **Rejected:** `twine upload` or `uv publish` with an API token from the owner's machine (a
  long-lived secret, and the upload would skip the checks unless remembered); starting on a pushed
  tag (a tag pushed by mistake would publish; a GitHub release is a deliberate act).

## 2026-11-22: workflow actions are pinned to a commit

- **Decision:** every `uses:` line names a full commit, with the release it is in a comment.
  `tests/test_release.py` fails on any other form.
- **Reason:** a moved tag in someone else's repository would otherwise run new code with this
  repository's permissions, in the release workflow with the right to publish.
- **Rejected:** major-version tags (`@v4`), which is what the files had; a bot that opens update
  requests (a repository setting, which is the owner's to change).

## 2026-11-22: one version, written in three places and checked

- **Decision:** the version stays a literal in `pyproject.toml` and in `l10n_sense/__init__.py`,
  and the newest `CHANGELOG.md` entry names it; a gate test compares the three, `scripts/e2e.sh`
  compares the installed `--version`, and the release workflow compares the tag.
- **Rejected:** reading the version from the package at build time (`dynamic`): one place fewer
  to edit, but `uv.lock` then stops recording it and the changelog still has to be checked.

## 2026-11-22: `meta.unscored` counts a string missing either scorer; no version bump

- Decision: with `--second`, `meta.unscored` counts every string that lacks a score from either
  scorer. The report's `version` stays as it is.
- Why: the field's name and type did not change, and the old count (first scorer only) hid
  strings whose verdict rested on one opinion. The contract text was corrected in the same commit.
- Rejected: a version bump (no reader has to change); a second field (two numbers for one question).

## 2026-11-20: end-to-end check runs the installed wheel, rules only

- **Decision:** `scripts/e2e.sh` builds the wheel, installs it in a throwaway environment and
  compares the report for `tests/e2e/` with `tests/e2e/expected.json`. It is not part of the gate.
- **Reason:** unit tests import from the working tree, so a service missing from the wheel's
  `force-include` list would pass them and break installed copies. The five services imported at
  start-up fail the run directly; the two model services are only started on a model-scored run,
  so the script also checks that every `force-include` target exists in the installed package.
- **Rejected:** putting it in the gate (needs a build and the network, takes seconds, the gate
  is under 1 s); covering model scoring here (not deterministic, costs calls; `scripts/eval.sh` does it).

## 2026-11-19: the package is named l10n-sense

- **Decision:** distribution and command are `l10n-sense`.
- **Reason:** `l10n-lint` is already another project on PyPI (`docs/results.md`). "sense" was
  chosen because the tool judges sense in context.
- **Rejected:** keeping the working name `l10n-lint`.

## 2026-11-19: runtime services ship inside the package through force-include

- **Decision:** the wheel contains `l10n_sense/` plus the seven runtime service files copied to
  `l10n_sense/_services/`. Benchmarks, the reviewer and the judging page stay in the repository.
- **Reason:** keeps one directory per service in the repository and one importable package for users.
- **Rejected:** moving the services under `l10n_sense/` (loses the service boundary in the tree).

## 2026-11-19: the score cache lives outside the project and is validated

- **Decision:** default cache is a per-project file under the user cache directory; every entry
  is validated before use.
- **Reason:** a cache file committed to a repository could otherwise pass a wrong string.
- **Rejected:** a cache file next to the locale files.

## 2026-11-19: with two scorers a string fails only when both say wrong

- **Decision:** `--second` adds an independent scorer; one-sided findings get the verdict
  `review` and exit code 0 by default. One-sided includes the case where one scorer gave no
  score (it errored): the other cannot fail the string alone (fixed 2026-11-20; before that a
  single surviving scorer could).
- **Reason:** on real strings two vendors agreed on 96% of wrong / not wrong calls; the disputed
  rest is where false alarms sit.
- **Rejected:** failing when either says wrong (more false alarms in a build gate).

## 2026-11-19: model CLIs run with every acting tool off, from an empty directory

- **Decision:** `services/llm` and `services/llm_codex` disable shell, file and network tools.
  `services/llm_codex/eval_isolation.py` checks the Codex service with a canary file; the Claude
  service's flags are pinned by unit tests on its command line.
- **Reason:** the strings and code under review are untrusted and reach the model; the Codex CLI
  could read local files with its defaults.
- **Rejected:** relying on the prompt to tell the model not to act.

## 2026-11-19: 0-100 score for every string instead of flag-only review

- **Decision:** the scorer rates every string; verdict thresholds are 41 (`warn`) and 61 (`fail`).
- **Reason:** a score can be calibrated on known truth and compared between two scorers; a
  flag-only reviewer gives no way to trade precision for recall.
- **Rejected:** the earlier flag-only reviewer as the product (kept in `services/review/` for comparison).

## 2026-11-19: deterministic rules run first and need no model

- **Decision:** placeholder, empty, missing, key-as-value and untranslated checks are code.
- **Reason:** most strings the scorer rated wrong that the reviewer had not flagged were never
  translated at all, which is detectable for free with the same answer every time.
- **Rejected:** leaving them to the model.

## 2026-11-19: model calls go through local CLIs, no hosted API

- **Decision:** no API key and no hosted endpoint; Claude Code by default, Codex as an option.
- **Reason:** nothing to host or bill; users run it with a login they already have.
- **Rejected:** calling a hosted model API directly.

## 2026-11-19: ship gate for a scorer

- **Decision:** precision at least 0.9 at recall at least 0.7 on `data/bench/injected.ja.jsonl`.
- **Reason:** a build gate that cries wolf gets switched off, so precision is weighted over recall.
- **Rejected:** a gate on the real-fix benchmark (its `ok` labels are unverified).
