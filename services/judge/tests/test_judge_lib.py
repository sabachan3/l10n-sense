import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import judge_lib  # noqa: E402


def write(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def make_items(tmp_path):
    write(tmp_path / "cases.jsonl", [{"id": "c1", "source": {"a": "Terminal", "b": "Health"}, "target": {"a": "端子", "b": "健康"}}])
    write(tmp_path / "findings.jsonl", [{"id": "c1", "mode": "code", "findings": [
        {"key": "a", "reason": "console", "suggestion": "ターミナル"}, {"key": "b", "reason": "system", "suggestion": "稼働状態"}]}])
    (tmp_path / "notes.json").write_text(json.dumps({"c1|code|a": "コマンド画面のこと"}, ensure_ascii=False), encoding="utf-8")
    return judge_lib.load_items(tmp_path / "cases.jsonl", tmp_path / "findings.jsonl", tmp_path / "notes.json")


def test_items_join_strings_and_keep_a_stable_order(tmp_path):
    items = make_items(tmp_path)
    assert {item["id"] for item in items} == {"c1|code|a", "c1|code|b"}
    first = next(item for item in items if item["key"] == "a")
    assert (first["source"], first["target"], first["suggestion"], first["reason_local"]) == ("Terminal", "端子", "ターミナル", "コマンド画面のこと")
    assert [item["id"] for item in items] == [item["id"] for item in make_items(tmp_path)]


def test_last_judgment_wins_and_bad_input_is_refused(tmp_path):
    out = tmp_path / "runs" / "j.jsonl"
    known = {"x", "y"}
    judge_lib.record(out, "x", "not_error", known, "t1")
    judge_lib.record(out, "x", "error", known, "t2")
    judge_lib.record(out, "y", "unsure", known, "t3")
    assert judge_lib.latest(out) == {"x": "error", "y": "unsure"}
    with pytest.raises(ValueError):
        judge_lib.record(out, "x", "maybe", known, "t")
    with pytest.raises(ValueError):
        judge_lib.record(out, "zzz", "error", known, "t")
    assert judge_lib.latest(tmp_path / "missing.jsonl") == {}


def test_summary_reports_both_precisions():
    summary = judge_lib.summarize({"a": "error", "b": "error", "c": "not_error", "d": "unsure"}, total=10)
    assert (summary["judged"], summary["error"], summary["unsure"], summary["not_error"]) == (4, 2, 1, 1)
    assert summary["precision"] == pytest.approx(2 / 3) and summary["precision_strict"] == 0.5
    assert judge_lib.summarize({}, 10)["precision"] is None
