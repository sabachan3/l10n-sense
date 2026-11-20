# Progress

Updated at the end of every working session. Newest state on top.

## Current State (2026-11-20)

- Version 0.1.0, public on GitHub, not on PyPI. Installs from the repository URL.
- Gate: `scripts/test.sh` green. End to end: `scripts/e2e.sh` green (installed wheel, rules only).
- All eight items in `features.json` have a recorded passing run of their command on this machine
  (`agent-sense features`; the record is local, a fresh clone starts without one).
- `scripts/eval.sh` (Claude scorer, known-truth benchmark, 276 strings): three runs so far, precision
  0.982 to 1.000, recall 0.964 to 1.000, 0 or 1 false alarm. Ship gate met each time. Table in
  `docs/results.md`.

## Completed

- 2026-11-19: reviewer for in-context errors, injected-error benchmark (Japanese, 276 strings).
- 2026-11-19: code-usage extractor, real-fix benchmark (Chinese, 3,846 strings), Japanese field audit sample.
- 2026-11-19: local page for judging findings by hand, restricted to requests from its own page.
- 2026-11-19: blind 0-100 scorer, second scorer from another vendor, agreement analysis, deterministic rules.
- 2026-11-19: Codex service locked down (it could read local files), canary isolation check.
- 2026-11-19: one `check` command with cache and optional second scorer; packaged as `l10n-sense`;
  YAML, gettext, Android, iOS and Xcode readers; upstream licence text for the benchmark data.
- 2026-11-20: agent harness: `CLAUDE.md`, this file, `DECISIONS.md`, `features.json`,
  `scripts/setup.sh`, `scripts/e2e.sh`, evaluator subagent, optional agent-sense Stop hook.

- 2026-11-20: corrections after an independent review of the harness change. Scorer error text
  and file errors on stderr are cleaned, JSON output writes control and direction characters as
  escapes (`cli.json_text`), `scripts/e2e.sh` checks that every `force-include` target is in the
  installed package, and statements in `CLAUDE.md` and `DECISIONS.md` were corrected.

## In Progress

Nothing.

## Known Issues

- No native speaker has judged any finding. Precision on real strings is unproven.
- The Japanese field audit by the second scorer covers 68 of 100 cases (1,360 of 2,000 strings).
- The known-truth benchmark is too easy to rank scorers; the real-fix benchmark has incomplete
  labels (`ok` there means "not touched by the fix").
- Formats other than JSON are covered by unit tests and one live Android run, not by a benchmark.
- `scripts/e2e.sh` covers the rules-only path. A model-scored run of the installed wheel is
  only exercised by hand.
- XLIFF, .resx, Fluent and TOML are not read.

## Next Steps

1. Get a sample of flags judged by a native speaker (the page in `services/judge/` exists for this).
2. Score the remaining 32 field-audit cases with the second scorer and update `docs/results.md`.
3. Publish to PyPI, then remove the install-from-GitHub note in `README.md`.
4. A benchmark for at least one non-JSON format.
