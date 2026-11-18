"""Write data/bench/injected.ja.jsonl from the fixtures.  python3 services/bench/build_injected.py"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import bench_lib  # noqa: E402
import fixtures  # noqa: E402
from contracts.schema import validate_case  # noqa: E402

translations = json.loads((HERE / "ja_translations.json").read_text(encoding="utf-8"))
cases = [validate_case(case) for case in bench_lib.build_cases(fixtures.APPS, translations["reference"], translations["wrong"])]
out = HERE.parents[1] / "data" / "bench" / "injected.ja.jsonl"
out.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
labels = [label for case in cases for label in case["labels"].values()]
print(f"{out}: {len(cases)} cases, {len(labels)} strings, {labels.count('wrong')} wrong")
