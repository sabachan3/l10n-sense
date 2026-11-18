import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_lib  # noqa: E402

RULE = [{"rule": "placeholder", "message": "m"}]


@pytest.mark.parametrize("rules,score,second,expected", [
    (RULE, 0, None, "fail"), ([], None, None, "ok"), ([], 61, None, "fail"), ([], 60, None, "warn"),
    ([], 41, None, "warn"), ([], 40, None, "ok"), ([], 90, 80, "fail"), ([], 90, 50, "review"),
    ([], 10, 70, "review"), ([], 50, 10, "warn"), ([], 10, 20, "ok"),
])
def test_verdict(rules, score, second, expected):
    assert check_lib.verdict(rules, score, second, warn=41, fail=61) == expected


def report(second=None):
    source = {"a": "Terminal", "b": "Save", "c": "Round {n}", "d": "Created"}
    target = {"a": "端子", "b": "保存", "c": "ラウンド", "d": "作成されました"}
    rules = [{"key": "c", "rule": "placeholder", "message": "missing {n}"}]
    scores = {"a": {"score": 90, "note": "電気部品", "fix": "ターミナル"}, "b": {"score": 5, "note": "", "fix": ""},
              "c": {"score": 70, "note": "", "fix": "ラウンド{n}"}, "d": {"score": 55, "note": "完了文", "fix": "作成日時"}}
    return check_lib.build_report(source, target, rules, scores, second or {}, 41, 61, {"language": "ja"})


def test_report_summary_and_order_of_the_text_output():
    result = report()
    assert result["summary"] == {"strings": 4, "fail": 2, "review": 0, "warn": 1, "ok": 1}
    text = check_lib.format_text(result)
    assert text.index("FAIL   a") < text.index("FAIL   c") < text.index("WARN   d")
    assert "fix: ターミナル" in text and "rule placeholder: missing {n}" in text and "保存" not in text
    assert text.endswith("4 strings: 2 fail, 0 review, 1 warn, 1 ok")


def test_second_scorer_turns_a_lone_fail_into_review():
    result = report({"a": {"score": 20, "note": "問題なし", "fix": ""}})
    assert next(entry for entry in result["strings"] if entry["key"] == "a")["verdict"] == "review"
    assert "REVIEW a  [90/20]" in check_lib.format_text(result)


def test_exit_code_levels():
    result = report()
    assert check_lib.exit_code(result) == 1 and check_lib.exit_code(result, "never") == 0
    clean = check_lib.build_report({"a": "Save"}, {"a": "保存"}, [], {"a": {"score": 50, "note": "", "fix": ""}}, {}, 41, 61, {})
    assert check_lib.exit_code(clean) == 0 and check_lib.exit_code(clean, "warn") == 1


def test_cache_key_changes_with_every_input():
    base = check_lib.cache_key("claude", None, 2, "p")
    assert base == check_lib.cache_key("claude", None, 2, "p")
    assert len({base, check_lib.cache_key("codex", None, 2, "p"), check_lib.cache_key("claude", "m", 2, "p"),
                check_lib.cache_key("claude", None, 3, "p"), check_lib.cache_key("claude", None, 2, "q")}) == 5


def test_text_output_cannot_carry_terminal_control_sequences():
    evil = "\x1b[2J\x1b]0;owned\x07ok\rFAIL\nnext"
    result = check_lib.build_report({evil: evil}, {evil: evil}, [{"key": evil, "rule": "r", "message": evil}],
                                    {evil: {"score": 90, "note": evil, "fix": evil}}, {}, 41, 61, {})
    text = check_lib.format_text(result)
    assert "\x1b" not in text and "\x07" not in text and "\r" not in text
    assert len(text.split("\n")) == 7  # header, source, target, rule, note, fix, summary: no injected lines
