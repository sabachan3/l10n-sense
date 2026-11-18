# l10n-sense

Finds translated UI strings that are wrong **in context**.

A locale file can be complete, well-formed and fluent, and still wrong: "KvK draw" (the bracket
draw of a tournament) shipped as "KvK引き分け" (a tied result). Checks for missing keys pass.
Nothing that reads only the translation can catch it. l10n-sense reads each string together with
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

Measurements and their limits: [docs/results.md](docs/results.md).

## Install

```bash
uvx l10n-sense --help            # run without installing (needs uv)
pipx install l10n-sense          # or install the command
pip install "l10n-sense[yaml]"   # YAML locale files need PyYAML
```

Python 3.10 or newer, no other dependencies. Not on PyPI yet; until then:

```bash
uvx --from git+https://github.com/sabachan3/l10n-sense l10n-sense --help
```

## Use

```bash
# rules only: free, instant, same result every time
l10n-sense check --source locales/en.json --target locales/ja.json --lang ja --no-model

# with a model score for every string, using the code as context
l10n-sense check --source locales/en.json --target locales/ja.json --lang ja --src src

# two independent models: a string fails only when both say it is wrong
l10n-sense check ... --second codex
```

| verdict | meaning | default exit code |
|---|---|---|
| `fail` | a rule fired, or the score is 61 or more (with `--second`: both scorers) | 1 |
| `review` | two scorers ran and only one says wrong | 0 |
| `warn` | 41 to 60: unnatural, but the meaning survives | 0 |
| `ok` | nothing found | 0 |

`--warn`, `--fail` and `--fail-on` change the thresholds and what breaks a build. `--format json`
or `--out report.json` gives the full report. Exit code 2 means the files could not be read.
A workflow to copy: [docs/github-actions.yml](docs/github-actions.yml).

### Locale file formats

| format | files | how to pass it |
|---|---|---|
| JSON, nested or flat (i18next, next-intl, vue-i18n) | `en.json`, `ja.json` | `--source` and `--target` |
| Chrome extension and Flutter ARB | `messages.json`, `app_ja.arb` | `--source` and `--target`; descriptions are used as context |
| YAML (Rails style) | `en.yml`, `ja.yml` | `--source` and `--target`; needs the `yaml` extra |
| gettext | `ja.po` | `--target` only; `#.` comments and `#:` locations are used as context |
| Android | `values/strings.xml`, `values-ja/strings.xml` | `--source` and `--target`; plurals and arrays included |
| iOS | `Localizable.strings` | `--source` and `--target` |
| Xcode String Catalog | `Localizable.xcstrings` | `--target` only, `--lang` picks the language |

Usage in code is looked up for `t("key")` style calls, whole-sentence keys in string literals,
and Android `R.string.name` / `@string/name` references, across JS/TS, Vue, Svelte, Python,
Ruby, PHP, Go, Swift, Kotlin, Java and Dart sources.

### What it costs

Nothing is hosted and there is no API key. Model calls go through a CLI you are already logged
in to: Claude Code by default, Codex with `--scorer codex` or `--second codex`. One call covers
20 strings, so a 1,000-string file is 50 calls per scorer. Scores are cached in
a per-project file under your user cache directory (`--cache` to choose another); an unchanged
string with unchanged code is never scored twice. The
number of calls is printed before they start. Calls count against your own plan's usage limit.

### What the rules catch without a model

Placeholders that differ from the source, empty or missing translations, the key's own name
used as the translation (`accountId` for "Account ID"), and text left in Latin script in a
language that does not use it.

## Layout

| path | what it is |
|---|---|
| [l10n_sense/](l10n_sense/) | the command: wires the services together |
| [services/formats/](services/formats/) | reads JSON, YAML, gettext, Android, iOS and Xcode locale files into one shape |
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

## Safety

The strings and code under review are untrusted input, and they are sent to a model.

- Model CLIs run with every acting tool off (no shell, no file access, no network tools), from an
  empty directory. `services/llm_codex/eval_isolation.py` checks that with a canary file.
- Only files under `--src` are read; symlinks are not followed.
- The score cache lives outside the project by default and every cached entry is validated
  before use, so a cache file committed to a repository cannot pass a wrong string.
- Everything printed is stripped of terminal control characters.

## Limits

- No native speaker has judged the findings yet. Two models from different vendors agree on
  96% of wrong / not wrong calls on real strings, which is evidence, not proof.
- The known-truth benchmark is easy; the real-fix benchmark has incomplete labels.
- Measured on JSON locale files with JS/TS code. The other formats are covered by unit tests
  and one live Android run, not by a benchmark.
- XLIFF, .resx, Fluent and TOML are not supported.
