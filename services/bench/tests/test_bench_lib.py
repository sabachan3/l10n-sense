import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import bench_lib  # noqa: E402
import fixtures  # noqa: E402
from contracts.schema import ContractError, validate_case, validate_findings  # noqa: E402

TRANSLATIONS = json.loads((HERE / "ja_translations.json").read_text(encoding="utf-8"))
CASES = bench_lib.build_cases(fixtures.APPS, TRANSLATIONS["reference"], TRANSLATIONS["wrong"])


def test_every_wrong_translation_appears_exactly_once_and_cases_are_valid():
    for case in CASES:
        validate_case(case)
    wrong = [(case["id"].split(":")[1], key) for case in CASES for key, label in case["labels"].items() if label == "wrong"]
    expected = {(app["name"], target["key"]) for app in fixtures.APPS for target in app["targets"]}
    assert len(wrong) == len(set(wrong)) == len(expected) and set(wrong) == expected
    assert sum(case["id"].endswith(":clean") for case in CASES) == len(fixtures.APPS)
    assert all(set(case["labels"].values()) == {"ok"} for case in CASES if case["id"].endswith(":clean"))


def test_committed_benchmark_file_matches_the_builder():
    committed = [json.loads(line) for line in (HERE.parents[1] / "data/bench/injected.ja.jsonl").read_text(encoding="utf-8").splitlines()]
    assert committed == CASES


def test_split_is_deterministic_and_complete():
    first, second = bench_lib.split_keys("app", ["a", "b", "c", "d", "e"])
    assert (first, second) == bench_lib.split_keys("app", ["e", "d", "c", "b", "a"])
    assert sorted(first + second) == ["a", "b", "c", "d", "e"] and abs(len(first) - len(second)) <= 1


def test_builder_rejects_a_wrong_translation_equal_to_the_reference():
    app = fixtures.APPS[0]
    same = {app["name"]: {t["key"]: TRANSLATIONS["reference"][app["name"]][t["key"]] for t in app["targets"]}}
    with pytest.raises(ValueError):
        bench_lib.build_cases([app], TRANSLATIONS["reference"], same)


def case(case_id, labels):
    return {"id": case_id, "labels": labels}


def test_score_counts_precision_recall_and_false_alarms():
    cases = [case("1", {"a": "wrong", "b": "ok", "c": "ok"}), case("2", {"a": "wrong", "b": "ok"})]
    reports = [{"id": "1", "mode": "code", "findings": [{"key": "a"}, {"key": "b"}, {"key": "zzz"}]}]
    summary = bench_lib.score(cases, reports)
    assert (summary["true_positives"], summary["false_positives"], summary["false_negatives"]) == (1, 1, 1)
    assert summary["precision"] == 0.5 and summary["recall"] == 0.5
    assert summary["false_alarm_rate"] == pytest.approx(1 / 3)
    assert summary["unknown_keys_flagged"] == 1 and summary["reported_cases"] == 1
    assert summary["misses"] == ["2/a"] and summary["false_alarms"] == ["1/b"]


def test_a_silent_reviewer_has_no_precision_and_fails_the_gate():
    summary = bench_lib.score([case("1", {"a": "wrong"})], [])
    assert summary["precision"] is None and summary["recall"] == 0.0
    assert not bench_lib.gate(summary)


def test_gate_thresholds():
    assert bench_lib.gate({"precision": 0.9, "recall": 0.7})
    assert not bench_lib.gate({"precision": 0.89, "recall": 1.0})
    assert not bench_lib.gate({"precision": 1.0, "recall": 0.69})


def test_contract_rejects_mismatched_keys_and_bad_findings():
    broken = dict(CASES[0], labels={"only": "ok"})
    with pytest.raises(ContractError):
        validate_case(broken)
    with pytest.raises(ContractError):
        validate_findings({"id": "x", "mode": "code", "findings": [{"key": "a"}]})
    validate_findings({"id": "x", "mode": "code", "findings": [{"key": "a", "reason": "r", "suggestion": "s"}]})
