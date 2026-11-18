#!/usr/bin/env python3
"""l10n-lint: find translated UI strings that are wrong in context.

    python3 l10n_lint.py check --source locales/en.json --target locales/ja.json --lang ja --src src

Steps: (1) rules that need no model, (2) for every string, the code that uses it, (3) a 0-100
score from a model for how wrong the translation is in that context. Exit code 1 when a string
fails. `--no-model` runs only step 1 and costs nothing.

Model calls go through a CLI you are already logged in to (Claude Code, or Codex with
`--scorer codex`); this tool has no API key and no server. Scores are cached in
`.l10n-lint-cache.json`, so an unchanged string is never paid for twice.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for service in ("extract", "rules", "score", "check"):
    sys.path.insert(0, str(ROOT / "services" / service))

import check_lib  # noqa: E402
import extract_lib  # noqa: E402
import rules_lib  # noqa: E402
import score_lib  # noqa: E402

SERVICES = {"claude": ROOT / "services" / "llm" / "llm.py", "codex": ROOT / "services" / "llm_codex" / "codex.py"}
SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".svelte", ".astro")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "coverage", "__tests__"}


def call_service(service: str, prompt: str, model: str | None) -> str:
    request = {"prompt": prompt, **({"model": model} if model else {})}
    result = subprocess.run([sys.executable, str(SERVICES[service])], input=json.dumps(request), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-300:])
    return json.loads(result.stdout)["text"]


def read_sources(root: Path | None) -> dict[str, str]:
    if root is None:
        return {}
    files = {}
    for path in sorted(root.rglob("*")):
        if path.suffix in SOURCE_SUFFIXES and path.is_file() and not SKIP_DIRS & set(path.parts) and ".test." not in path.name:
            files[str(path.relative_to(root.parent))] = path.read_text(encoding="utf-8", errors="replace")
    return files


def score_strings(source: dict, target: dict, language: str, files: dict, service: str, model: str | None,
                  window: int, workers: int, cache: dict, call=call_service, log=print) -> dict:
    """Scores for every key present in both files. `cache` is read and filled in place."""
    index = extract_lib.build_index(files)
    keys = [key for key in source if key in target]
    jobs = []
    for group in extract_lib.windows(keys, window):
        case = {"language": language, "source": {key: source[key] for key in group},
                "target": {key: target[key] for key in group},
                "code": extract_lib.render({key: extract_lib.usages(key, files, index) for key in group})}
        prompt = score_lib.build_prompt(case)
        jobs.append((group, prompt, check_lib.cache_key(service, model, score_lib.PROMPT_VERSION, prompt)))
    todo = [job for job in jobs if job[2] not in cache]
    log(f"[l10n-lint] {service}: {len(jobs)} groups of up to {window} strings, {len(jobs) - len(todo)} cached, "
        f"{len(todo)} model calls to make")

    def work(job):
        group, prompt, key = job
        last = None
        for _ in range(2):
            try:
                return key, score_lib.parse_scores(call(service, prompt, model), set(group)), None
            except Exception as exc:  # a failed group must not lose the others
                last = exc
        return key, None, f"{group[0]}: {type(last).__name__}: {last}"

    errors = []
    with ThreadPoolExecutor(workers) as pool:
        for count, (key, scores, error) in enumerate(pool.map(work, todo), 1):
            if error:
                errors.append(error)
            else:
                cache[key] = scores
            if count % 10 == 0 or count == len(todo):
                log(f"[l10n-lint] {service}: {100 * count / len(todo):.0f}% done, {count}/{len(todo)} calls, errors={len(errors)}")
    out = {}
    for _, _, key in jobs:
        out.update(cache.get(key, {}))
    if errors:
        log(f"[l10n-lint] {len(errors)} groups could not be scored and are reported without a score, first: {errors[0][:200]}")
    return out


def check(args, call=call_service, log=print) -> tuple[dict, int]:
    source = extract_lib.flatten(json.loads(args.source.read_text(encoding="utf-8")))
    target = extract_lib.flatten(json.loads(args.target.read_text(encoding="utf-8")))
    rule_findings = rules_lib.check_locale(source, target, args.lang)
    scores, second = {}, {}
    if not args.no_model:
        files = read_sources(args.src)
        cache_path = args.cache
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        try:
            scores = score_strings(source, target, args.lang, files, args.scorer, args.model, args.window, args.workers, cache, call, log)
            if args.second:
                second = score_strings(source, target, args.lang, files, args.second, args.second_model, args.window,
                                       args.workers, cache, call, log)
        finally:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    meta = {"language": args.lang, "source": str(args.source), "target": str(args.target),
            "scorer": None if args.no_model else args.scorer, "second": args.second,
            "unscored": 0 if args.no_model else sum(key in target and key not in scores for key in source)}
    report = check_lib.build_report(source, target, rule_findings, scores, second, args.warn, args.fail, meta)
    return report, check_lib.exit_code(report, args.fail_on)


def main(argv: list[str] | None = None, call=call_service) -> int:
    parser = argparse.ArgumentParser(prog="l10n-lint", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("check", help="audit one locale file against its source locale")
    run.add_argument("--source", type=Path, required=True, help="source locale file (JSON, nested or flat)")
    run.add_argument("--target", type=Path, required=True, help="translated locale file to audit")
    run.add_argument("--lang", required=True, help="target language tag, e.g. ja, zh-CN, de")
    run.add_argument("--src", type=Path, help="source code directory, used as context for each string")
    run.add_argument("--no-model", action="store_true", help="rules only: free, instant, same result every time")
    run.add_argument("--scorer", choices=sorted(SERVICES), default="claude")
    run.add_argument("--model", help="model name for the scorer (default: the CLI's own)")
    run.add_argument("--second", choices=sorted(SERVICES), help="second, independent scorer; a string fails only when both agree")
    run.add_argument("--second-model")
    run.add_argument("--warn", type=int, default=41)
    run.add_argument("--fail", type=int, default=61)
    run.add_argument("--fail-on", choices=("fail", "review", "warn", "never"), default="fail", help="what makes the exit code 1")
    run.add_argument("--window", type=int, default=20, help="strings per model call")
    run.add_argument("--workers", type=int, default=6)
    run.add_argument("--cache", type=Path, default=Path(".l10n-lint-cache.json"))
    run.add_argument("--format", choices=("text", "json"), default="text")
    run.add_argument("--out", type=Path, help="also write the full JSON report here")
    args = parser.parse_args(argv)
    if args.second and args.second == args.scorer and args.second_model == args.model:
        parser.error("--second must differ from --scorer: the same model twice is not an independent opinion")

    report, code = check(args, call=call, log=lambda message: print(message, file=sys.stderr, flush=True))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1) if args.format == "json" else check_lib.format_text(report))
    return code


if __name__ == "__main__":
    sys.exit(main())
