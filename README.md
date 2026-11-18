# l10n-lint

Finds translated UI strings that are wrong **in context**.

A locale file can be complete, well-formed and fluent, and still wrong: "KvK draw" (the bracket
draw of a tournament) shipped as "KvK引き分け" (a tied result). Nothing that reads only the
translation can catch that. This project gathers the evidence around each string (key name,
neighbouring strings, the code that uses it) and asks a model to judge the translation against
what the string means in the app. Checks that need no model (placeholders, missing keys) stay
deterministic.

Status: early. The reviewer is being measured before anything is packaged. See
[docs/results.md](docs/results.md).

## Layout

| path | what it is |
|---|---|
| [contracts/](contracts/) | JSON Lines formats exchanged between services, with a validator |
| [services/bench/](services/bench/) | Benchmark cases with known truth, and the scorer |
| [services/review/](services/review/) | The reviewer: prompt, reply parsing, runner |
| [services/llm/](services/llm/) | Text completion through the local Claude Code CLI (no hosted API) |

## Commands

```bash
scripts/test.sh                                   # gate tests, under 1 s, also the pre-commit hook
python3 services/bench/build_injected.py          # rebuild data/bench/injected.ja.jsonl
python3 services/review/review.py --cases data/bench/injected.ja.jsonl --out runs/injected.jsonl
python3 services/bench/score.py --cases data/bench/injected.ja.jsonl --findings runs/injected.jsonl
```

After cloning: `git config core.hooksPath .githooks`.

The ship gate for the reviewer: precision at least 0.9 at recall at least 0.7, counted per string.
