# Progress

Updated at the end of every working session. Newest state on top.

## Current State (2026-11-22)

- Version 0.1.0, public on GitHub, not on PyPI. Installs from the repository URL.
- Ready for a first PyPI release; the release itself is the owner's (`docs/release.md`). The name
  `l10n-sense` was free on PyPI on 2026-11-22 (HTTP 404 from `pypi.org/pypi/l10n-sense/json`).
- Gate: `scripts/test.sh` green, 140 tests, also in CI on Linux, macOS and Windows. End to end:
  `scripts/e2e.sh` green (sdist and wheel: twine check, exact contents, installed from each, rules only).
- All nine items in `features.json` have a recorded passing run on the author's machine (the
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
- 2026-11-22: release preparation. Package metadata (author by name, classifiers, project
  links, licence file); an sdist cut down to the files that build the wheel (it had carried
  benchmark builders, a data file and the judging page); `scripts/e2e.sh` now checks both archives
  with twine, compares their contents with `pyproject.toml` file by file and installs from each;
  `l10n-sense --version`; `CHANGELOG.md`; README links made absolute for the PyPI page, with a
  table of what needs a model CLI; `.github/workflows/release.yml` (trusted publishing, started
  only by a published release or by hand); actions in both workflows pinned to commits; CI also
  on Python 3.11 and 3.14; `docs/release.md` (publish steps, yanking, licences of dependencies
  and data); `tests/test_release.py`. Gate run locally on Python 3.10, 3.11, 3.12, 3.13 and 3.14.
  Audit of the tree and of the history of `main` for secrets, addresses, paths, machine and
  project names: nothing found in what is public (details went to the owner, not into this file).

## In Progress

Nothing.

## Waiting on a decision

- Publishing 0.1.0 (step 4 below). Before it: whether to rehearse on TestPyPI first, and whether
  the `pypi` environment gets a required reviewer.
- Whether a model-scored run with no usable model CLI should exit 2 instead of 0 (Known Issues).

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
- A run with a model score whose CLI is not installed exits 0 with every string unscored (it says
  so on stderr and in `meta.unscored`). A build that only reads the exit code sees a pass. Seen
  2026-11-22 with `claude` absent from PATH; whether that should exit 2 is not decided.
- `release.yml` has never run: it cannot before it is pushed. It was checked with actionlint and
  by `tests/test_release.py`, and its build and check steps are the ones `scripts/e2e.sh dist`
  runs locally. The upload step and the PyPI side of trusted publishing are untested.
- The wheel's metadata says `Metadata-Version: 2.5` (hatchling 1.33.0). `twine check --strict`
  accepts it; that PyPI accepts it on upload is not verified. The TestPyPI rehearsal in
  `docs/release.md` would show it.
- The new CI entries (Python 3.11 and 3.14 on Linux) and the pinned actions have run locally or
  been linted only; the first push shows whether CI agrees.

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
4. **Needs the owner.** Publish to PyPI: every step is in `docs/release.md` (trusted publisher on
   PyPI, `pypi` environment on GitHub, tag `v0.1.0`, GitHub release, verify with `uvx`). After
   it, "Each release" step 5 there lists the edits that make the PyPI commands the first ones in
   `README.md`; an agent can do those once the owner says the release is out.
