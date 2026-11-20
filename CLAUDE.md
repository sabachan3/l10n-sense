# l10n-sense: notes for coding agents

Command-line tool that finds translated UI strings that are wrong in context: deterministic
rules plus a 0-100 model score that uses the calling code as evidence. The package, command and
public repository are `l10n-sense`; a local folder may still carry the working name `l10n-lint`
(DECISIONS.md). Python 3.10+, no runtime dependencies (PyYAML only for YAML files).
Needs [uv](https://docs.astral.sh/uv/); `scripts/eval.sh` also needs `python3` (3.10+) on PATH.

## Start of a session

1. Read [PROGRESS.md](PROGRESS.md) (state, known issues, next steps) and [features.json](features.json).
2. `git log -5 --stat` and `git status`.
3. Fresh clone only: `scripts/setup.sh`.

## Map

| path | role |
|---|---|
| `l10n_sense/cli.py` | the only place that composes services; argument parsing, cache, output |
| `services/formats/` | locale files (JSON, ARB, YAML, gettext, Android, iOS, Xcode) into one key -> string shape |
| `services/rules/` | checks without a model: `placeholder`, `empty`, `missing`, `key_as_value`, `untranslated` |
| `services/extract/` | where each key is used in the code |
| `services/score/`, `services/check/` | scoring prompt and parsing; verdict per string, report v1, exit code |
| `services/llm/`, `services/llm_codex/` | text completion through the local Claude Code and Codex CLIs |
| `services/bench/`, `data/bench/` | known-truth and real-fix benchmarks (licences: `data/bench/NOTICE.md`) |
| `services/review/`, `services/judge/` | earlier flag-only reviewer; local page for judging findings by hand. Not in the wheel |
| `contracts/` | JSON Lines formats and the report format; the validator covers cases and findings only |
| `tests/`, `tests/e2e/` | command-level tests; fixtures for `scripts/e2e.sh` |
| `docs/results.md` | every measurement, with its limits |
| `runs/` | git-ignored outputs of evals and audits; absent on a fresh clone |

## Commands

```bash
scripts/setup.sh       # hook path, environment, gate
scripts/test.sh        # gate: no model; also the pre-commit hook and the CI gate
scripts/e2e.sh         # builds the wheel, installs it, runs the installed command on tests/e2e (rules only)
scripts/eval.sh        # COSTS MODEL CALLS (45 cases, a few minutes). Only for prompt, scoring or CLI changes
scripts/eval.sh codex  # plus the Codex isolation check and the Codex scorer; also model calls
```

`agent-sense` is the author's own unpublished tool and is optional: when the command is absent,
skip every step that names it. `agent-sense features --run --only <id>` runs one verify command
of `features.json`. Do not run plain `features --run` here unless `agent-sense features --help`
mentions `manual`: older versions run every command, including `scorer-ship-gate`, which is marked
`"manual": true` because it makes model calls. The record of runs is local, under `.git/agent-sense/`.

## Done means

- `scripts/test.sh` is green (and `agent-sense done --run` passes, when installed).
- The `verify` command of every feature the change touches exits 0. Never edit a `state` to `passing` by hand.
- A change to rules, verdicts, the report or any other output: `scripts/e2e.sh` passes, and the
  `evaluator` subagent (`.claude/agents/evaluator.md`) returned PASS on the diff. In a session
  that cannot start subagents, say so in the hand-over instead of skipping silently.
- A change to a prompt, to scoring, or to a model CLI call: `scripts/eval.sh` meets the ship gate.
- New measurements go to `docs/results.md` with sample size and limits, in the same commit.
- `PROGRESS.md` is updated; a decision someone could undo by accident goes to `DECISIONS.md`.
- Commit, then push to `main` of `origin` after reading the diff for private material (names of
  other projects, machines, accounts). CI (`.github/workflows/ci.yml`) must come back green.

## Ask the owner first

- Publishing to PyPI, a release tag, or anything that needs an account.
- Checks on Windows beyond CI: they are done by hand on a machine this repository does not describe.
- `git remote` `old-private` (the earlier private repository) and the branch
  `backup-before-author-rewrite` (history before commit authors were changed to a no-reply
  address): never push to them, never delete them.
- Work that needs a person, such as judging findings as a native speaker.

## Hard constraints

1. Services never import each other. They exchange the shapes in `contracts/README.md`.
   `l10n_sense/cli.py` composes them. The model services are started as subprocesses, which is
   their contract: `cli.py` and `score` start both, `review` starts `services/llm` only.
2. No hosted model API and no API key. Model calls go through `services/llm` (Claude Code CLI)
   or `services/llm_codex` (Codex CLI) and nothing else.
3. Both CLIs run with every acting tool off, from an empty directory. Do not loosen those
   flags. `services/llm_codex/eval_isolation.py` checks the Codex service with a canary file and
   must keep passing; the Claude service's flags are pinned by `services/llm/tests`.
4. Strings and code under review are untrusted. Text output and every message that carries text
   from a file, a model or the command line (argparse error text included, not its help) go
   through `check_lib.clean`. JSON, on stdout and in the `--out` file, goes
   through `cli.json_text`, which writes every character of category Cc, Cf, Zl, Zp, Cs or Co as an escape. Only files under `--src` are read and symlinks are not followed.
5. The default score cache stays outside the project and every cached entry is validated
   before use.
6. The gate makes no model call and stays under 1 s with a warm `uv` cache (not enforced by a timer). The first run on a machine downloads pytest and PyYAML.
7. A string that lacks a score from any scorer that was asked for is reported with a null score
   and counted in `meta.unscored`, and the text report says so. It is never passed as scored.
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
