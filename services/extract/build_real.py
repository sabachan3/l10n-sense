"""Benchmark cases from a real fix: a locale file before and after someone corrected it.

    python3 services/extract/build_real.py --name omniroute-zh-CN --language zh \
        --en base.en.json --before base.zh-CN.json --after after.zh-CN.json --src repo/src \
        --about "OmniRoute: dashboard of an AI model router and gateway" --out data/bench/real.omniroute.zh.jsonl

Strings the fix changed are labelled `wrong` (with the value that shipped); the rest are `ok`.
`ok` only means "not touched by the fix", so false alarms measured on these cases are an upper
bound: some untouched strings may be wrong too.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import extract_lib  # noqa: E402
from contracts.schema import validate_case  # noqa: E402

SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte")


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("name", "language", "about"):
        parser.add_argument(f"--{name}", required=True)
    for name in ("en", "before", "after", "src", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--clean-cases", type=int, default=30, help="extra windows the fix did not touch")
    args = parser.parse_args()

    en, before, after = (extract_lib.flatten(json.loads(path.read_text(encoding="utf-8")))
                         for path in (args.en, args.before, args.after))
    keys = [key for key in en if key in before and key in after]
    changed = {key for key in keys if before[key] != after[key]}
    files = {str(path.relative_to(args.src.parent)): path.read_text(encoding="utf-8", errors="replace")
             for path in sorted(args.src.rglob("*")) if path.suffix in SOURCE_SUFFIXES and path.is_file()
             and ".test." not in path.name and "__tests__" not in path.parts}
    index = extract_lib.build_index(files)

    groups = extract_lib.windows(keys, args.window)
    touched = [group for group in groups if changed & set(group)]
    untouched = sorted((group for group in groups if not changed & set(group) and len(group) == args.window),
                       key=lambda group: hashlib.sha256(group[0].encode()).hexdigest())[:args.clean_cases]
    cases, with_usage, total = [], 0, 0
    for group in touched + untouched:
        found = {key: extract_lib.usages(key, files, index) for key in group}
        with_usage += sum(bool(value) for value in found.values())
        total += len(group)
        cases.append(validate_case({
            "id": f"real-{args.name}:{group[0]}", "language": args.language, "about": args.about,
            "source": {key: en[key] for key in group}, "target": {key: before[key] for key in group},
            "code": extract_lib.render(found),
            "labels": {key: ("wrong" if key in changed else "ok") for key in group},
            "meta": {"fixed": {key: after[key] for key in group if key in changed}},
        }))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
    wrong = sum(label == "wrong" for case in cases for label in case["labels"].values())
    print(f"{args.out}: {len(cases)} cases ({len(touched)} touched by the fix, {len(untouched)} untouched), "
          f"{total} strings, {wrong} wrong of {len(changed)} changed, usage found for {100 * with_usage / total:.0f}% "
          f"of keys, {len(files)} source files, {args.out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
