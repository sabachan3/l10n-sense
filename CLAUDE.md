# l10n-sense: notes for coding agents

Command-line tool that finds translated UI strings that are wrong in context: deterministic
rules plus a 0-100 model score that uses the calling code as evidence. Python 3.10+, no runtime
dependencies (PyYAML only for YAML files). User-facing description: [README.md](README.md).

## Start of a session

1. Read [PROGRESS.md](PROGRESS.md) (where things stand) and [features.json](features.json)
   (what must keep working, and how each item is verified).
2. `git log -5 --stat` and `git status`.
3. Fresh clone only: `scripts/setup.sh`.

## Map

| path | role |
|---|---|
| `l10n_sense/cli.py` | the only place that composes services; argument parsing, cache, output |
| `services/formats/` | locale files (JSON, ARB, YAML, gettext, Android, iOS, Xcode) into one key -> string shape |
| `services/rules/` | checks without a model: `placeholder`, `empty`, `missing`, `key_as_value`, `untranslated` |
| `services/extract/` | where each key is used in the code |
| `services/score/` | scoring prompt, parsing, agreement of two scorers, threshold check for the eval |
| `services/check/` | verdict per string, report v1, exit code |
| `services/llm/`, `services/llm_codex/` | text completion through the local Claude Code and Codex CLIs |
| `services/bench/`, `data/bench/` | known-truth and real-fix benchmarks (see `data/bench/NOTICE.md` for licences) |
| `services/review/`, `services/judge/` | earlier flag-only reviewer; local page for judging findings by hand. Not shipped in the wheel |
| `contracts/` | JSON Lines formats and the report format; the validator covers cases and findings, not the report |
| `tests/` | command-level tests; `tests/e2e/` holds the fixtures for `scripts/e2e.sh` |
| `docs/results.md` | every measurement, with its limits |

## Commands

```bash
scripts/setup.sh     # hook path, environment, gate
scripts/test.sh      # gate: under 1 s, no model, no network; also the pre-commit hook
scripts/e2e.sh       # builds the wheel, installs it, runs the installed command on tests/e2e (rules only)
scripts/eval.sh      # periodic: real model calls on data/bench/injected.ja.jsonl, a few minutes
scripts/eval.sh codex  # plus the Codex isolation check and the Codex scorer
agent-sense features --run   # when agent-sense is installed: runs every verify command in features.json
```

## Done means

- `scripts/test.sh` is green, and `agent-sense done --run` passes when agent-sense is installed.
- The `verify` command of every feature the change touches exits 0. A feature's `state` becomes
  `passing` only after its command passed; never edit it to `passing` by hand.
- A change to rules, verdicts, the report or any other output: `scripts/e2e.sh` passes, and the
  `evaluator` subagent (`.claude/agents/evaluator.md`) returned PASS on the diff.
- A change to a prompt, to scoring, or to a model CLI call: `scripts/eval.sh` meets the ship gate.
- New measurements are written to `docs/results.md` with sample size and limits, in the same commit
  that mentions them anywhere else.
- `PROGRESS.md` is updated, a decision that someone could later undo by accident is added to
  `DECISIONS.md`, and the work is committed.

## End of a session

Gate green, no debug output or scratch files left in the tree (`runs/` and `dist/` are ignored),
`PROGRESS.md` says what changed and what is next, everything committed.

## Hard constraints

1. Services never import each other. They exchange the shapes in `contracts/README.md`.
   `l10n_sense/cli.py` composes them. The model services are started as subprocesses, which is
   their contract: `cli.py` and `score` start both, `review` starts `services/llm` only.
2. No hosted model API and no API key. Model calls go through `services/llm` (Claude Code CLI)
   or `services/llm_codex` (Codex CLI) and nothing else.
3. Both CLIs run with every acting tool off, from an empty directory. Do not loosen those
   flags. `services/llm_codex/eval_isolation.py` checks the Codex service with a canary file and
   must keep passing; the Claude service's flags are pinned by `services/llm/tests`.
4. Strings and code under review are untrusted. Text output and every message on stderr, argparse
   errors included, go through `check_lib.clean`. JSON, on stdout and in the `--out` file, goes
   through `cli.json_text`, which writes every character of category Cc, Cf, Zl, Zp, Cs or Co as an escape. Only files under `--src` are read and symlinks are not followed.
5. The default score cache stays outside the project and every cached entry is validated
   before use.
6. The gate makes no model call and no network request, and stays under 1 s.
7. A string a scorer could not rate is reported with a null score and counted in
   `meta.unscored`. It is never passed as scored.
8. Rules stay conservative: a rule that fires on brand names or one-word labels is a bug.
9. Report format changes bump `version` and update `contracts/README.md` in the same commit.
10. A runtime service added to the wheel needs its `force-include` line in `pyproject.toml`;
    `scripts/e2e.sh` checks that every `force-include` target is in the installed package.
11. No runtime dependency is added without a decision recorded in `DECISIONS.md`.
12. Benchmark data from other projects keeps its licence text and notice in `data/bench/`.
13. The ship gate (precision at least 0.9 at recall at least 0.7 on the known-truth set) is not
    lowered to make a change pass.
14. Claims in `README.md` and `docs/results.md` state what was measured, on how many items, and
    by whom judged. No native speaker has judged findings yet; do not write as if one had.
