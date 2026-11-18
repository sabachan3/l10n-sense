"""Score reviewer findings.  python3 services/bench/score.py --cases data/bench/injected.ja.jsonl --findings runs/x.jsonl"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import bench_lib  # noqa: E402
from contracts.schema import validate_case, validate_findings  # noqa: E402


def read(path: Path, validate) -> list[dict]:
    return [validate(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


parser = argparse.ArgumentParser()
parser.add_argument("--cases", type=Path, required=True)
parser.add_argument("--findings", type=Path, nargs="+", required=True)
args = parser.parse_args()
cases = read(args.cases, validate_case)
for path in args.findings:
    reports = read(path, validate_findings)
    for mode in sorted({report["mode"] for report in reports}):
        summary = bench_lib.score(cases, [report for report in reports if report["mode"] == mode])
        verdict = "PASS" if bench_lib.gate(summary) else "FAIL"
        fmt = lambda value: "-" if value is None else f"{value:.3f}"  # noqa: E731
        print(f"{path.name} mode={mode}: precision {fmt(summary['precision'])}, recall {fmt(summary['recall'])}, "
              f"false alarms {summary['false_positives']}/{summary['ok']} ({fmt(summary['false_alarm_rate'])}), "
              f"cases {summary['reported_cases']}/{summary['cases']}  gate(0.9/0.7) {verdict}")
        for name in ("misses", "false_alarms"):
            for item in summary[name]:
                print(f"   {'miss' if name == 'misses' else 'false alarm'}: {item}")
