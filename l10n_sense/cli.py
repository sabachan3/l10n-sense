"""l10n-sense: find translated UI strings that are wrong in context.

    l10n-sense check --source locales/en.json --target locales/ja.json --lang ja --src src

Steps: (1) rules that need no model, (2) for every string, the code that uses it, (3) a 0-100
score from a model for how wrong the translation is in that context. Exit code 1 when a string
fails. `--no-model` runs only step 1 and costs nothing.

Model calls go through a CLI you are already logged in to (Claude Code, or Codex with
`--scorer codex`); this tool has no API key and no server. Scores are cached per project under
the user cache directory, so an unchanged string is never paid for twice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
try:
    from l10n_sense import __version__
except ImportError:  # started as a script (python l10n_sense/cli.py): the package's parent is not on the path
    sys.path.insert(0, str(PACKAGE.parent))
    from l10n_sense import __version__
# installed: services are shipped inside the package. In the repository: the services/ directory.
SERVICES_DIR = PACKAGE / "_services" if (PACKAGE / "_services").is_dir() else PACKAGE.parent / "services"
for service in ("extract", "rules", "score", "check", "formats"):
    sys.path.insert(0, str(SERVICES_DIR / service))

import check_lib  # noqa: E402
import extract_lib  # noqa: E402
import formats_lib  # noqa: E402
import rules_lib  # noqa: E402
import score_lib  # noqa: E402

SERVICES = {"claude": SERVICES_DIR / "llm" / "llm.py", "codex": SERVICES_DIR / "llm_codex" / "codex.py"}
SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".vue", ".svelte", ".astro", ".html", ".py", ".rb", ".erb",
                   ".php", ".go", ".swift", ".kt", ".java", ".dart", ".xml")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "coverage", "__tests__", "vendor", "Pods", ".venv"}
MAX_SOURCE_BYTES = 1_000_000


# json.dumps escapes the C0 controls itself. With ensure_ascii off it leaves DEL, the C1 controls
# (0x9b starts an escape sequence on some terminals) and the direction overrides as they are.
# Everything invisible is written as an escape: controls (Cc), format characters such as direction
# marks, overrides, zero-width characters and tags (Cf), line and paragraph separators (Zl, Zp),
# lone surrogates (Cs, which cannot be encoded at all) and private use (Co).
_JSON_UNSAFE_CATEGORIES = {"Cc", "Cf", "Zl", "Zp", "Cs", "Co"}


def _json_escape(char: str) -> str:
    code = ord(char)
    if code > 0xFFFF:  # JSON escapes are UTF-16: characters outside the BMP take a surrogate pair
        code -= 0x10000
        return f"\\u{0xD800 + (code >> 10):04x}\\u{0xDC00 + (code & 0x3FF):04x}"
    return f"\\u{code:04x}"


def utf8(stream) -> bool:
    return (getattr(stream, "encoding", None) or "utf-8").lower().replace("-", "").replace("_", "") in ("utf8", "utf8sig")


def write_out(text: str) -> None:
    """Print to stdout whatever its encoding is. A redirected stdout on Windows is often a legacy
    code page that cannot hold Japanese: characters it lacks are written as backslash escapes."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, "backslashreplace").decode(encoding))


def json_text(report: dict, ascii_only: bool = False) -> str:
    """The report as JSON that is safe to print or store: same data, invisible characters as escapes.
    With `ascii_only` every non-ASCII character is an escape, for an output that is not UTF-8."""
    if ascii_only:
        return json.dumps(report, ensure_ascii=True, indent=1)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    return "".join(_json_escape(char) if char != "\n" and unicodedata.category(char) in _JSON_UNSAFE_CATEGORIES else char
                   for char in text)


class Parser(argparse.ArgumentParser):
    """argparse echoes unknown arguments as they were typed; clean them like every other message.
    Only the error text is cleaned: help and usage are argparse's own and may carry its colours."""

    def error(self, message):
        super().error(" ".join(check_lib.clean(line) for line in str(message).split("\n")))


def default_cache_path(project: Path) -> Path:
    """Per-project cache outside the project, so a cache file committed to a repository under
    review can never decide the result."""
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "l10n-sense"
    return base / (hashlib.sha256(str(project.resolve()).encode()).hexdigest()[:16] + ".json")


def call_service(service: str, prompt: str, model: str | None) -> str:
    request = {"prompt": prompt, **({"model": model} if model else {})}
    result = subprocess.run([sys.executable, str(SERVICES[service])], input=json.dumps(request), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-300:])
    return json.loads(result.stdout)["text"]


def read_sources(root: Path | None) -> dict[str, str]:
    """Source files under `root`. Symlinks are not followed and nothing outside `root` is read:
    file contents are sent to a model, so a link to a private file must not be picked up."""
    if root is None:
        return {}
    if not root.is_dir():
        raise ValueError(f"--src {root} is not a directory")
    top = root.resolve()
    files = {}
    for path in sorted(root.rglob("*")):
        if path.suffix not in SOURCE_SUFFIXES or SKIP_DIRS & set(path.parts) or ".test." in path.name:
            continue
        if path.is_symlink() or not path.is_file() or top not in path.resolve().parents:
            continue
        if path.stat().st_size > MAX_SOURCE_BYTES:
            continue
        files[path.relative_to(root.parent).as_posix()] = path.read_text(encoding="utf-8", errors="replace")
    return files


def score_strings(pair: dict, language: str, files: dict, service: str, model: str | None,
                  window: int, workers: int, cache: dict, call=call_service, log=print) -> dict:
    """Scores for every key present in both files. `cache` is read and filled in place."""
    source, target = pair["source"], pair["target"]
    index = extract_lib.build_index(files)
    keys = [key for key in source if key in target and target[key].strip()]
    jobs = []
    for group in extract_lib.windows(keys, window, by_namespace=pair.get("namespaced", False)):
        evidence = {key: (extract_lib.at_references(pair["refs"].get(key, []), files)
                          or extract_lib.usages(key, files, index)) for key in group}
        case = {"language": language, "source": {key: source[key] for key in group},
                "target": {key: target[key] for key in group}, "code": extract_lib.render(evidence, pair["notes"])}
        prompt = score_lib.build_prompt(case)
        key = check_lib.cache_key(service, model, score_lib.PROMPT_VERSION, prompt)
        checked = score_lib.validate_cached(cache.get(key), set(group))
        if checked is None:
            cache.pop(key, None)  # absent or not trustworthy: score again
        else:
            cache[key] = checked
        jobs.append((group, prompt, key))
    todo = [job for job in jobs if job[2] not in cache]
    log(f"[l10n-sense] {service}: {len(jobs)} groups of up to {window} strings, {len(jobs) - len(todo)} cached, "
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
                log(f"[l10n-sense] {service}: {100 * count / len(todo):.0f}% done, {count}/{len(todo)} calls, errors={len(errors)}")
    out = {}
    for _, _, key in jobs:
        out.update(cache.get(key, {}))
    if errors:
        log(f"[l10n-sense] {len(errors)} groups could not be scored and are reported without a score, first: {check_lib.clean(errors[0][:200])}")
    return out


def check(args, call=call_service, log=print) -> tuple[dict, int]:
    pair = formats_lib.load_pair(args.source, args.target, args.lang)
    pair["namespaced"] = formats_lib.kind(args.target) in ("json", "yaml")  # dotted keys are namespaces there
    source, target = pair["source"], pair["target"]
    rule_findings = rules_lib.check_locale(source, target, args.lang)
    scores, second = {}, {}
    if not args.no_model:
        files = read_sources(args.src)
        cache_path = args.cache or default_cache_path(Path.cwd())
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        except (OSError, ValueError):
            cache = {}
        if not isinstance(cache, dict):
            cache = {}
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("a", encoding="utf-8"):  # fail here, before any model call is paid for
            pass
        try:
            scores = score_strings(pair, args.lang, files, args.scorer, args.model, args.window, args.workers, cache, call, log)
            if args.second:
                second = score_strings(pair, args.lang, files, args.second, args.second_model, args.window,
                                       args.workers, cache, call, log)
        finally:
            try:
                cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            except (OSError, ValueError) as exc:  # the scores are in hand: report them, do not lose the run
                log(f"[l10n-sense] could not save the score cache: {check_lib.clean(exc)}")
    scorable = [key for key in source if key in target and target[key].strip()]
    meta = {"language": args.lang, "source": str(args.source) if args.source else None, "target": str(args.target),
            "scorer": None if args.no_model else args.scorer, "second": args.second,
            "unscored": 0 if args.no_model else sum(key not in scores or (bool(args.second) and key not in second)
                                                    for key in scorable)}
    report = check_lib.build_report(source, target, rule_findings, scores, second, args.warn, args.fail, meta)
    return report, check_lib.exit_code(report, args.fail_on)


def main(argv: list[str] | None = None, call=call_service) -> int:
    parser = Parser(prog="l10n-sense", description=__doc__.split("\n")[0])
    parser.add_argument("--version", action="version", version=f"l10n-sense {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("check", help="audit one locale file against its source locale")
    run.add_argument("--source", type=Path, help="source locale file; not needed for .po and .xcstrings, which hold both")
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
    run.add_argument("--cache", type=Path, help="score cache file (default: per project, under the user cache directory)")
    run.add_argument("--format", choices=("text", "json"), default="text")
    run.add_argument("--out", type=Path, help="also write the full JSON report here")
    args = parser.parse_args(argv)
    if args.window < 1 or args.workers < 1:
        parser.error("--window and --workers must be 1 or more")
    def same(first: Path | None, second: Path | None) -> bool:
        return bool(first and second and Path(first).exists() and Path(second).exists() and Path(first).samefile(second))

    if any(same(args.out, path) for path in (args.source, args.target)):
        parser.error("--out is one of the locale files: the report would overwrite it")
    if any(same(args.cache, path) for path in (args.source, args.target)):
        parser.error("--cache is one of the locale files: the score cache would overwrite it")
    if same(args.cache, args.out):
        parser.error("--cache and --out are the same file")
    if args.second and args.second == args.scorer and args.second_model == args.model:
        parser.error("--second must differ from --scorer: the same model twice is not an independent opinion")

    try:
        report, code = check(args, call=call, log=lambda message: print(message, file=sys.stderr, flush=True))
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json_text(report), encoding="utf-8")
    except (formats_lib.FormatError, OSError, ValueError) as exc:
        print(f"l10n-sense: {check_lib.clean(exc)}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        kept = "" if args.no_model else "; scores received before this are kept in the score cache"
        print(f"l10n-sense: interrupted{kept}", file=sys.stderr)
        return 130
    write_out(json_text(report, ascii_only=not utf8(sys.stdout)) if args.format == "json" else check_lib.format_text(report))
    return code


if __name__ == "__main__":
    sys.exit(main())
