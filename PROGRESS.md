# Progress

Updated at the end of every working session. Newest state on top.

## Current State (2026-11-20)

- Version 0.1.0, public on GitHub, not on PyPI. Installs from the repository URL.
- Gate: `scripts/test.sh` green, 129 tests, also in CI on Linux, macOS and Windows. End to end:
  `scripts/e2e.sh` green (installed wheel, rules only).
- All eight items in `features.json` have a recorded passing run on the author's machine (the
  record is local, under `.git/agent-sense/`; a fresh clone starts without one).
- `scripts/eval.sh` (Claude scorer, known-truth benchmark, 276 strings): three runs so far, precision
  0.982 to 1.000, recall 0.964 to 1.000, 0 or 1 false alarm. Ship gate met each time. Table in
  `docs/results.md`.

## Completed

History is in `git log` and, for measurements, in `docs/results.md`. In short:

- 2026-11-19: rules, code-context extractor, blind 0-100 scorer with an optional second scorer,
  benchmarks, the `check` command, packaging as `l10n-sense`, readers for JSON, YAML, gettext, Android, iOS and Xcode files.
- 2026-11-20: agent harness (`CLAUDE.md`, this file, `DECISIONS.md`, `features.json`, setup and
  end-to-end scripts, evaluator definition); three independent reviews and the fixes they led to
  (output cleaning and escaping, exit codes, two-scorer verdict, unscored count); a check on a
  real Windows machine; CI on Linux, macOS and Windows; pinned gate dependencies.
- 2026-11-22: independent review of everything since the second review (3095bbf..5187c87): PASS,
  no class A finding; gate, end-to-end check and hostile inputs rerun by the reviewer, model
  evals not run. Fixed from its notes: `--cache` naming a locale file overwrote that file (now
  refused, as `--out` already was), a wrong-shape source file was reported under the target's
  name, the interrupt message mentioned a cache in a run without a model. Those fixes are not
  reviewed.

## In Progress

Nothing.

## Known Issues

- No native speaker has judged any finding. Precision on real strings is unproven.
- The Japanese field audit by the second scorer covers 68 of 100 cases (1,360 of 2,000 strings).
- The known-truth benchmark is too easy to rank scorers; the real-fix benchmark has incomplete
  labels (`ok` there means "not touched by the fix").
- Formats other than JSON are covered by unit tests and one live Android run, not by a benchmark.
- `scripts/e2e.sh` covers the rules-only path. A model-scored run of the installed wheel is
  only exercised by hand, and never on Windows.
- XLIFF, .resx, Fluent and TOML are not read.
- Text output shows a full-width space and a zero-width joiner as ordinary spaces; JSON keeps both.
- Ship-gate runs differ by one false alarm and two misses between single runs (`docs/results.md`).
- `scripts/eval.sh` calls `python3` directly, not `uv run`; it needs Python 3.10+ on PATH.
- The gate's "under 1 s" is a habit, not a check: nothing times it.

## Next Steps

Each step says who can do it. A session working alone starts with step 1.

1. **Agent alone.** A benchmark for one non-JSON format. Take `data/bench/injected.ja.jsonl`,
   write the same strings as gettext or Android files under a new `data/bench/` entry, add a
   scenario to `services/bench/`, and report rule results first (`--no-model`, free). Scoring it
   with a model costs calls: ask before that part.
2. **Needs model calls and the owner's go-ahead** (the second scorer's account ran into its usage
   limit last time; whether that has reset is not known here). Score the remaining 32 field-audit
   cases: `python3 services/score/score.py --service codex --cases runs/audit.omniroute.ja.cases.jsonl
   --out runs/audit.omniroute.ja.scores.codex.jsonl` (the run resumes where it stopped), then
   update the table in `docs/results.md`. The inputs are under `runs/`, which is not in git: on a
   fresh clone they do not exist and have to come from the owner.
3. **Needs a person who reads Japanese natively.** Judge a sample of flags:
   `python3 services/judge/server.py --cases runs/audit.omniroute.ja.cases.jsonl --findings
   runs/audit.omniroute.ja.findings.jsonl --out runs/audit.omniroute.ja.judgments.jsonl`, then open
   `http://127.0.0.1:8765`. Who judges and how many strings is the owner's decision.
4. **Needs the owner.** Publish to PyPI, then move the install-from-GitHub command in `README.md`
   below the PyPI ones.
