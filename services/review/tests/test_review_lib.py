import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import review_lib  # noqa: E402

CASE = {"id": "c1", "language": "ja", "about": "tournament", "source": {"kvk.draw": "KvK draw", "n": "Round {n}"},
        "target": {"kvk.draw": "KvK引き分け", "n": "第{n}ラウンド"}, "code": "usePairings(kingdoms)",
        "labels": {"kvk.draw": "wrong", "n": "ok"}}


def test_prompt_never_contains_the_labels():
    for mode in review_lib.MODES:
        prompt = review_lib.build_prompt(CASE, mode)
        assert '"wrong"' not in prompt and "labels" not in prompt


def test_code_appears_only_in_code_mode():
    assert "usePairings" not in review_lib.build_prompt(CASE, "pair")
    assert "usePairings" in review_lib.build_prompt(CASE, "code")
    assert "KvK引き分け" in review_lib.build_prompt(CASE, "pair") and "Japanese" in review_lib.build_prompt(CASE, "pair")
    with pytest.raises(ValueError):
        review_lib.build_prompt(CASE, "screenshot")


def test_parse_keeps_known_keys_once_and_drops_invented_ones():
    reply = ('```json\n{"findings": [{"key": "kvk.draw", "reason": "bracket draw, not a tie", "suggestion": "KvK抽選"},'
             '{"key": "kvk.draw", "reason": "again", "suggestion": "x"}, {"key": "made.up", "reason": "r", "suggestion": "s"}]}\n```')
    assert review_lib.parse_findings(reply, set(CASE["source"])) == [
        {"key": "kvk.draw", "reason": "bracket draw, not a tie", "suggestion": "KvK抽選"}]


def test_parse_accepts_an_empty_list_and_rejects_prose():
    assert review_lib.parse_findings('{"findings": []}', {"a"}) == []
    with pytest.raises(ValueError):
        review_lib.parse_findings("Looks fine to me.", {"a"})
    with pytest.raises(ValueError):
        review_lib.parse_findings('{"result": "ok"}', {"a"})
