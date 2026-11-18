import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import score_lib  # noqa: E402

CASE = {"id": "c", "language": "ja", "source": {"a": "Terminal", "b": "Save"}, "target": {"a": "端子", "b": "保存"},
        "code": "<Terminal/>", "labels": {"a": "wrong", "b": "ok"}, "meta": {"fixed": {"a": "ターミナル"}}}


def test_prompt_is_blind_to_labels_and_fixes():
    prompt = score_lib.build_prompt(CASE)
    assert "端子" in prompt and "<Terminal/>" in prompt and "Japanese" in prompt
    assert "ターミナル" not in prompt and '"wrong"' not in prompt and "labels" not in prompt


def test_parse_clamps_scores_and_requires_every_key():
    reply = '{"scores": [{"key": "a", "score": 130, "note": "端子は電気部品"}, {"key": "b", "score": -5}, {"key": "zzz", "score": 50}]}'
    assert score_lib.parse_scores(reply, {"a", "b"}) == {"a": {"score": 100, "note": "端子は電気部品", "fix": ""},
                                                         "b": {"score": 0, "note": "", "fix": ""}}
    with_fix = '{"scores": [{"key": "a", "score": 90, "note": "n", "fix": "ターミナル"}]}'
    assert score_lib.parse_scores(with_fix, {"a"})["a"]["fix"] == "ターミナル"
    with pytest.raises(ValueError):
        score_lib.parse_scores('{"scores": [{"key": "a", "score": 10}]}', {"a", "b"})
    with pytest.raises(ValueError):
        score_lib.parse_scores('{"scores": [{"key": "a", "score": "high"}]}', {"a"})
    with pytest.raises(ValueError):
        score_lib.parse_scores("fine", {"a"})


def test_auroc():
    assert score_lib.auroc([90, 80], [10, 20]) == 1.0
    assert score_lib.auroc([10], [90]) == 0.0
    assert score_lib.auroc([50], [50]) == 0.5
    assert score_lib.auroc([], [1]) is None


def test_threshold_counts():
    result = score_lib.at_threshold([90, 70, 65, 10], [True, True, False, False], 61)
    assert (result["flagged"], result["false_alarms"]) == (3, 1)
    assert result["precision"] == pytest.approx(2 / 3) and result["recall"] == 1.0
    assert score_lib.at_threshold([10], [True], 61)["precision"] is None


def test_band_edges():
    assert [score_lib.band(s) for s in (0, 40, 41, 60, 61, 100)] == ["fine", "fine", "unnatural", "unnatural", "wrong", "wrong"]


def test_combine_needs_both_scorers_to_confirm():
    first = {"a": 90, "b": 90, "c": 50, "d": 10, "only_first": 99}
    second = {"a": 70, "b": 30, "c": 10, "d": 20}
    assert score_lib.combine(first, second) == {"a": "confirmed", "b": "disputed", "c": "unnatural", "d": "fine"}


def test_agreement_counts_and_kappa():
    first = {"a": 90, "b": 90, "c": 10, "d": 10}
    assert score_lib.agreement(first, dict(first))["kappa"] == 1.0
    opposite = {"a": 10, "b": 10, "c": 90, "d": 90}
    result = score_lib.agreement(first, opposite)
    assert (result["both_wrong"], result["only_first"], result["only_second"], result["neither"]) == (0, 2, 2, 0)
    assert result["observed"] == 0.0 and result["kappa"] == -1.0
    assert score_lib.agreement({}, {})["kappa"] is None
    assert score_lib.agreement({"a": 0}, {"a": 0})["kappa"] is None  # no wrong strings at all: kappa undefined


def test_notes_are_bounded_single_line_text():
    assert score_lib.clean_note("line one\nline two\x1b[31m\tend") == "line one line two [31m end"
    assert len(score_lib.clean_note("あ" * 500)) == score_lib.NOTE_LIMIT
    assert score_lib.clean_note(None) == "None"
    reply = '{"scores": [{"key": "a", "score": 5, "note": "' + "x" * 300 + '"}]}'
    assert len(score_lib.parse_scores(reply, {"a"})["a"]["note"]) == score_lib.NOTE_LIMIT
