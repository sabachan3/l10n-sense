"""Build and score the injected-error benchmark. Standard library only.

Each fixture app becomes three cases: the reviewed translation as it is, and two cases where
complementary halves of the ambiguous strings carry a wrong-sense translation. Every wrong
translation therefore appears exactly once, next to correct neighbours.
"""

from __future__ import annotations

import hashlib


def split_keys(app_name: str, keys: list[str], seed: int = 0) -> tuple[list[str], list[str]]:
    """Deterministic halves of `keys`, order decided by a hash so it does not follow file order."""
    ranked = sorted(keys, key=lambda key: hashlib.sha256(f"{seed}:{app_name}:{key}".encode()).hexdigest())
    return sorted(ranked[::2]), sorted(ranked[1::2])


def build_cases(apps: list[dict], reference: dict, wrong: dict, language: str = "ja") -> list[dict]:
    cases = []
    for app in apps:
        name = app["name"]
        good = reference[name]
        if set(good) != set(app["strings"]):
            raise ValueError(f"{name}: reference translation keys differ from the source keys")
        target_keys = [target["key"] for target in app["targets"]]
        if set(wrong[name]) != set(target_keys):
            raise ValueError(f"{name}: wrong translations must cover exactly the ambiguous keys")
        for key, text in wrong[name].items():
            if text == good[key]:
                raise ValueError(f"{name}: wrong translation of {key} equals the reference")
        half_a, half_b = split_keys(name, target_keys)
        for variant, seeded in (("clean", []), ("a", half_a), ("b", half_b)):
            cases.append({
                "id": f"injected-{language}:{name}:{variant}", "language": language, "about": app["about"],
                "source": dict(app["strings"]),
                "target": {key: (wrong[name][key] if key in seeded else good[key]) for key in app["strings"]},
                "code": app["code"],
                "labels": {key: ("wrong" if key in seeded else "ok") for key in app["strings"]},
            })
    return cases


def score(cases: list[dict], reports: list[dict]) -> dict:
    """Precision, recall and false-alarm rate over keys. A case with no report counts as
    nothing flagged, so skipping cases cannot raise precision without costing recall."""
    flagged_by_id = {report["id"]: {finding["key"] for finding in report["findings"]} for report in reports}
    tp = fp = fn = tn = unknown = 0
    misses, alarms = [], []
    for case in cases:
        flagged = flagged_by_id.get(case["id"], set())
        unknown += len(flagged - set(case["labels"]))
        for key, label in case["labels"].items():
            hit = key in flagged
            if label == "wrong" and hit:
                tp += 1
            elif label == "wrong":
                fn += 1
                misses.append(f"{case['id']}/{key}")
            elif hit:
                fp += 1
                alarms.append(f"{case['id']}/{key}")
            else:
                tn += 1
    return {"cases": len(cases), "reported_cases": sum(case["id"] in flagged_by_id for case in cases),
            "wrong": tp + fn, "ok": fp + tn, "true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
            "false_alarm_rate": fp / (fp + tn) if fp + tn else None, "unknown_keys_flagged": unknown,
            "misses": misses, "false_alarms": alarms}


def gate(summary: dict, min_precision: float = 0.9, min_recall: float = 0.7) -> bool:
    return (summary["precision"] is not None and summary["precision"] >= min_precision
            and summary["recall"] is not None and summary["recall"] >= min_recall)
