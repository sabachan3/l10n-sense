"""Score every string of every case.  python3 services/score/score.py --cases X.jsonl --out runs/X.scores.jsonl --model claude-opus-5-5

One appended line per case: {"id", "model", "scores": {key: {"score", "note"}}}. Finished cases are skipped on rerun.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score_lib  # noqa: E402

LLM = HERE.parent / "llm" / "llm.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["id"] for line in args.out.read_text(encoding="utf-8").splitlines()} if args.out.exists() else set()
    todo = [case for case in cases if case["id"] not in done]

    def work(case):
        last = None
        for _ in range(2):  # one retry: a reply that skips keys is usually complete the second time
            try:
                request = {"prompt": score_lib.build_prompt(case), "model": args.model}
                result = subprocess.run([sys.executable, str(LLM)], input=json.dumps(request), capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(result.stderr.strip()[:300])
                return {"id": case["id"], "model": args.model,
                        "scores": score_lib.parse_scores(json.loads(result.stdout)["text"], set(case["source"]))}
            except Exception as exc:
                last = exc
        return {"id": case["id"], "error": f"{type(last).__name__}: {last}"}

    started, errors = time.time(), 0
    with ThreadPoolExecutor(args.workers) as pool, args.out.open("a", encoding="utf-8") as handle:
        for count, record in enumerate(pool.map(work, todo), 1):
            if "error" in record:
                errors += 1
                print(f"[score] ERROR {record['id']}: {record['error']}", flush=True)
            else:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
            if count % 10 == 0 or count == len(todo):
                rate = count / (time.time() - started)
                print(f"[score] {100 * count / len(todo):.0f}% done, ETA {(len(todo) - count) / rate / 60:.1f}m | "
                      f"{count}/{len(todo)} cases, errors={errors}", flush=True)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
