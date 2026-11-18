# l10n-lint

Finds translated UI strings that are wrong **in context**.

A locale file can be complete, well-formed and fluent, and still wrong: "KvK draw" (the bracket
draw of a tournament) shipped as "KvK引き分け" (a tied result). Checks for missing keys pass.
Nothing that reads only the translation can catch it. l10n-lint reads each string together with
the code that uses it and rates how wrong the translation is, from 0 to 100.

From a real project's Japanese file (346 strings, 34 failures):

```
FAIL   landing.npm  [98]
       source: NPM
       target: 故宮
FAIL   landing.terminal  [90]
       source: terminal
       target: 端子
       fix: ターミナル
FAIL   health.running  [90]
       source: running
       target: 走っている
       fix: 実行中
```

Status: works on JSON locale files (nested or flat) and JS/TS sources. Not packaged yet.
Measurements and their limits: [docs/results.md](docs/results.md).

## Use

```bash
# rules only: free, instant, same result every time
python3 l10n_lint.py check --source locales/en.json --target locales/ja.json --lang ja --no-model

# with a model score for every string, using the code as context
python3 l10n_lint.py check --source locales/en.json --target locales/ja.json --lang ja --src src

# two independent models: a string fails only when both say it is wrong
python3 l10n_lint.py check ... --second codex
```

| verdict | meaning | default exit code |
|---|---|---|
| `fail` | a rule fired, or the score is 61 or more (with `--second`: both scorers) | 1 |
| `review` | two scorers ran and only one says wrong | 0 |
| `warn` | 41 to 60: unnatural, but the meaning survives | 0 |
| `ok` | nothing found | 0 |

`--warn`, `--fail` and `--fail-on` change the thresholds and what breaks a build. `--format json`
or `--out report.json` gives the full report.

### What it costs

Nothing is hosted and there is no API key. Model calls go through a CLI you are already logged
in to: Claude Code by default, Codex with `--scorer codex` or `--second codex`. One call covers
20 strings, so a 1,000-string file is 50 calls per scorer. Scores are cached in
`.l10n-lint-cache.json`; an unchanged string with unchanged code is never scored twice. The
number of calls is printed before they start. Calls count against your own plan's usage limit.

### What the rules catch without a model

Placeholders that differ from the source, empty or missing translations, the key's own name
used as the translation (`accountId` for "Account ID"), and text left in Latin script in a
language that does not use it.

## Layout

| path | what it is |
|---|---|
| [l10n_lint.py](l10n_lint.py) | the command: wires the services together |
| [contracts/](contracts/) | JSON Lines formats exchanged between services, with a validator |
| [services/rules/](services/rules/) | checks that need no model |
| [services/extract/](services/extract/) | finds where each key is used in the code |
| [services/score/](services/score/) | 0-100 scoring prompt, parsing, agreement between two scorers |
| [services/check/](services/check/) | verdict per string, report, exit code |
| [services/llm/](services/llm/), [services/llm_codex/](services/llm_codex/) | text completion through the local Claude Code and Codex CLIs, locked down to text in, text out |
| [services/bench/](services/bench/), [data/bench/](data/bench/) | benchmarks with known truth |
| [services/review/](services/review/), [services/judge/](services/judge/) | the earlier flag-only reviewer and a local page for judging findings by hand |

## Develop

```bash
git config core.hooksPath .githooks   # once
scripts/test.sh                       # gate tests: under 1 s, no model, also the pre-commit hook
scripts/eval.sh                       # periodic eval: real model on the known-truth benchmark
scripts/eval.sh codex                 # plus the Codex isolation check and the Codex scorer
```

Ship gate for a scorer: precision at least 0.9 at recall at least 0.7 on `data/bench/injected.ja.jsonl`.

## Limits

- No native speaker has judged the findings yet. Two models from different vendors agree on
  96% of wrong / not wrong calls on real strings, which is evidence, not proof.
- The known-truth benchmark is easy; the real-fix benchmark has incomplete labels.
- Only JSON locale files; usage lookup assumes `t("key")` style calls.
