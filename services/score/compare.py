"""Compare two scorers on the same cases, optionally against truth labels and reviewer findings.

    python3 services/score/compare.py --cases X.jsonl --first runs/a.jsonl --second runs/b.jsonl
        [--findings runs/findings.jsonl] [--list disputed]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score_lib  # noqa: E402


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def flat(path: Path) -> tuple[dict[str, float], dict[str, str]]:
    scores, notes = {}, {}
    for record in read(path):
        for key, value in record["scores"].items():
            scores[f"{record['id']}|{key}"] = value["score"]
            notes[f"{record['id']}|{key}"] = value["note"]
    return scores, notes


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("cases", "first", "second"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--findings", type=Path)
    parser.add_argument("--list", choices=("confirmed", "disputed", "unnatural"), help="print the strings with this verdict")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()
    cases = {case["id"]: case for case in read(args.cases)}
    (first, first_notes), (second, second_notes) = flat(args.first), flat(args.second)
    verdicts = score_lib.combine(first, second)
    print("strings scored by both:", len(verdicts), dict(Counter(verdicts.values())))
    stats = score_lib.agreement(first, second)
    print("wrong (61+): both", stats["both_wrong"], "| only first", stats["only_first"], "| only second", stats["only_second"],
          "| neither", stats["neither"], "| agreement", None if stats["observed"] is None else round(stats["observed"], 3),
          "| kappa", None if stats["kappa"] is None else round(stats["kappa"], 3))

    labels = {f"{case_id}|{key}": label == "wrong" for case_id, case in cases.items() for key, label in case["labels"].items()}
    if any(labels.values()):
        keys = sorted(verdicts)
        truth = [labels[key] for key in keys]
        for name, scores in (("first", first), ("second", second)):
            values = [scores[key] for key in keys]
            print(f"truth, {name}: AUROC", round(score_lib.auroc([v for v, t in zip(values, truth) if t],
                                                                 [v for v, t in zip(values, truth) if not t]), 4),
                  score_lib.at_threshold(values, truth, 61))
        confirmed = [verdicts[key] == "confirmed" for key in keys]
        print("truth, both agree wrong:", score_lib.at_threshold([100 if c else 0 for c in confirmed], truth, 61))
    if args.findings:
        flagged = {f"{report['id']}|{finding['key']}" for report in read(args.findings) for finding in report["findings"]}
        print("reviewer findings by verdict:", dict(Counter(verdicts[key] for key in flagged if key in verdicts)))
        print("not flagged by reviewer:", dict(Counter(value for key, value in verdicts.items() if key not in flagged)))
    if args.list:
        chosen = sorted((key for key, value in verdicts.items() if value == args.list), key=lambda key: -(first[key] + second[key]))
        for key in chosen[:args.limit]:
            case_id, name = key.rsplit("|", 1)
            case = cases[case_id]
            print(f"  {first[key]:3}/{second[key]:3} {name} | {case['source'][name][:60]!r} | {case['target'][name][:60]!r} | "
                  f"{first_notes[key]} / {second_notes[key]}")


if __name__ == "__main__":
    main()
