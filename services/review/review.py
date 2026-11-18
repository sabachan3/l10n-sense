"""Run the reviewer over benchmark cases.

    python3 services/review/review.py --cases data/bench/injected.ja.jsonl --out runs/injected.jsonl

Appends one findings line per (case, mode); finished pairs are skipped on a rerun. Labels are
never sent to the model. Model calls go through services/llm as a subprocess.
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

import review_lib  # noqa: E402

LLM = HERE.parent / "llm" / "llm.py"


def call(prompt: str, model: str | None) -> str:
    request = {"prompt": prompt, **({"model": model} if model else {})}
    result = subprocess.run([sys.executable, str(LLM)], input=json.dumps(request), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[:300])
    return json.loads(result.stdout)["text"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--modes", nargs="+", default=list(review_lib.MODES), choices=review_lib.MODES)
    parser.add_argument("--model")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    cases = [json.loads(line) for line in args.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.out.exists():
        done = {(r["id"], r["mode"]) for r in map(json.loads, args.out.read_text(encoding="utf-8").splitlines())}
    jobs = [(case, mode) for case in cases for mode in args.modes if (case["id"], mode) not in done]

    def work(job):
        case, mode = job
        try:
            findings = review_lib.parse_findings(call(review_lib.build_prompt(case, mode), args.model), set(case["source"]))
            return {"id": case["id"], "mode": mode, "findings": findings}
        except Exception as exc:
            return {"id": case["id"], "mode": mode, "error": f"{type(exc).__name__}: {exc}"}

    started = time.time()
    errors = 0
    with ThreadPoolExecutor(args.workers) as pool, args.out.open("a", encoding="utf-8") as handle:
        for count, record in enumerate(pool.map(work, jobs), 1):
            if "error" in record:
                errors += 1
                print(f"[review] ERROR {record['id']} {record['mode']}: {record['error']}", flush=True)
            else:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
            if count % 10 == 0 or count == len(jobs):
                rate = count / (time.time() - started)
                print(f"[review] {100 * count / len(jobs):.0f}% done, ETA {(len(jobs) - count) / rate / 60:.1f}m | "
                      f"{count}/{len(jobs)} calls, errors={errors}", flush=True)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
