"""Exit 1 when a scorer misses the ship gate on a benchmark with truth labels."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import score_lib  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--cases", type=Path, required=True)
parser.add_argument("--scores", type=Path, required=True)
parser.add_argument("--threshold", type=int, default=61)
parser.add_argument("--min-precision", type=float, required=True)
parser.add_argument("--min-recall", type=float, required=True)
args = parser.parse_args()
read = lambda path: [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]  # noqa: E731
cases = {case["id"]: case for case in read(args.cases)}
scored = {(record["id"], key): value["score"] for record in read(args.scores) for key, value in record["scores"].items()}
# a string with no score counts as "not flagged": skipping cases cannot pass the gate
keys = [(case_id, key) for case_id, case in cases.items() for key in case["labels"]]
values = [scored.get(key, 0) for key in keys]
truth = [cases[case_id]["labels"][key] == "wrong" for case_id, key in keys]
result = score_lib.at_threshold(values, truth, args.threshold)
passed = (result["precision"] or 0) >= args.min_precision and (result["recall"] or 0) >= args.min_recall
print(f"{args.scores.name}: precision {result['precision']}, recall {result['recall']}, false alarms {result['false_alarms']}, "
      f"scored {len(scored)}/{len(keys)} -> {'PASS' if passed else 'FAIL'}")
sys.exit(0 if passed else 1)
