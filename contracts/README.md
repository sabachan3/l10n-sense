# Contracts (v1)

Services exchange JSON Lines files and never import each other's code. The top-level command
`l10n_lint.py` is the only place that composes them.

## Benchmark case (`data/bench/*.jsonl`)

| field | type | meaning |
|---|---|---|
| `id` | string | unique case id |
| `language` | string | target language tag, e.g. `ja` |
| `about` | string | one line on what the app is |
| `source` | object | key -> English string |
| `target` | object | key -> translation to audit |
| `code` | string | source code that uses the keys |
| `labels` | object | key -> `ok` or `wrong` (the truth; never shown to a reviewer) |

## Findings (`runs/<name>.jsonl`)

One line per case: `{"id", "mode", "findings": [{"key", "reason", "suggestion"}]}`.
A key that is not listed is judged fine.

## LLM service (`services/llm`)

    echo '{"prompt": "...", "system": "..."}' | python services/llm/llm.py
    -> {"text": "...", "seconds": 1.2}

Called as a subprocess. It runs the local Claude Code CLI with no tools, no MCP servers and no
settings, from an empty directory. No hosted API is called from this repo.

## Report (`l10n_lint.py check --out report.json`)

`{"version": 1, "meta", "thresholds": {"warn", "fail"}, "summary": {"strings", "fail", "review", "warn", "ok"}, "strings": [...]}`

Each string: `key`, `source`, `target`, `rules` (list of `{rule, message}`), `score` and
`second_score` (0-100 or null), `note`, `second_note`, `fix`, `verdict` (`fail`, `review`,
`warn`, `ok`). `meta.unscored` counts strings a scorer could not rate (for example after a
usage limit); they are reported with a null score, never silently passed as scored.
