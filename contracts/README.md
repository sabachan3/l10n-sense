# Contracts (v1)

Services exchange JSON Lines files and never import each other's code.

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
