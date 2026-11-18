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
    assert score_lib.parse_scores(reply, {"a", "b"}) == {"a": {"score": 100, "note": "端子は電気部品"}, "b": {"score": 0, "note": ""}}
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
