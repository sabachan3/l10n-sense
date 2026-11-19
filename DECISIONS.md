# Decisions

One entry per decision that a later change could undo by accident. Newest first.

## 2026-11-20: end-to-end check runs the installed wheel, rules only

- **Decision:** `scripts/e2e.sh` builds the wheel, installs it in a throwaway environment and
  compares the report for `tests/e2e/` with `tests/e2e/expected.json`. It is not part of the gate.
- **Reason:** unit tests import from the working tree, so a service missing from the wheel's
  `force-include` list would pass them and break every installed copy.
- **Rejected:** putting it in the gate (needs a build and the network, takes seconds, the gate
  is about 1 s); covering model scoring here (not deterministic, costs calls; `scripts/eval.sh` does it).

## 2026-11-19: the package is named l10n-sense

- **Decision:** distribution and command are `l10n-sense`.
- **Reason:** the tool judges sense in context; "lint" suggests the structural checks other
  tools already do.
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
  `review` and exit code 0 by default.
- **Reason:** on real strings two vendors agreed on 96% of wrong / not wrong calls; the disputed
  rest is where false alarms sit.
- **Rejected:** failing when either says wrong (more false alarms in a build gate).

## 2026-11-19: model CLIs run with every acting tool off, from an empty directory

- **Decision:** `services/llm` and `services/llm_codex` disable shell, file and network tools,
  and `services/llm_codex/eval_isolation.py` checks it with a canary file.
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
