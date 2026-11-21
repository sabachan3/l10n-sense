"""End-to-end test of the command with a fake scorer: no model, no network."""

import io
import json
import re
import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from l10n_sense import cli as l10n_lint  # noqa: E402


def project(tmp_path):
    (tmp_path / "locales").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "locales/en.json").write_text(json.dumps({"kvk": {"draw": "KvK draw", "round": "Round {n}", "seed": "Seed"},
                                                          "nav": {"flowSpawn": "Start the flow"}}), encoding="utf-8")
    (tmp_path / "locales/ja.json").write_text(json.dumps({"kvk": {"draw": "KvK引き分け", "round": "ラウンド", "seed": "シード"},
                                                          "nav": {"flowSpawn": "Flow Spawn"}}, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "src/Bracket.tsx").write_text('const t = useTranslations("kvk");\nconst pairs = usePairings();\n<h2>{t("draw")}</h2>\n', encoding="utf-8")
    return tmp_path


class FakeScorer:
    def __init__(self, table):
        self.table, self.prompts = table, []

    def __call__(self, service, prompt, model):
        self.prompts.append((service, prompt))
        keys = [row["key"] for row in json.loads(prompt.split("Strings:\n")[1].split("\n\nSource code")[0])]
        return json.dumps({"scores": [{"key": key, "score": self.table[service].get(key, 5), "note": "n", "fix": ""} for key in keys]})


def run(tmp_path, scorer, *extra):
    root = project(tmp_path) if not (tmp_path / "locales").exists() else tmp_path
    code = l10n_lint.main(["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"),
                           "--lang", "ja", "--src", str(root / "src"), "--cache", str(root / "cache.json"),
                           "--out", str(root / "report.json"), *extra], call=scorer)
    return json.loads((root / "report.json").read_text(encoding="utf-8")), code


def verdicts(report):
    return {entry["key"]: entry["verdict"] for entry in report["strings"]}


def test_rules_only_run_is_free_and_finds_structural_errors(tmp_path, capsys):
    scorer = FakeScorer({"claude": {}})
    report, code = run(tmp_path, scorer, "--no-model")
    assert scorer.prompts == [] and code == 1
    assert verdicts(report) == {"kvk.draw": "ok", "kvk.round": "fail", "kvk.seed": "ok", "nav.flowSpawn": "fail"}
    assert "rule placeholder" in capsys.readouterr().out


def test_model_run_sends_code_context_and_fails_the_wrong_sense(tmp_path):
    scorer = FakeScorer({"claude": {"kvk.draw": 92, "kvk.seed": 45}})
    report, code = run(tmp_path, scorer)
    assert code == 1 and verdicts(report)["kvk.draw"] == "fail" and verdicts(report)["kvk.seed"] == "warn"
    kvk_prompt = next(prompt for _, prompt in scorer.prompts if "kvk.draw" in prompt)
    assert "usePairings" in kvk_prompt and "src/Bracket.tsx:3" in kvk_prompt
    assert report["meta"]["unscored"] == 0


def test_second_run_uses_the_cache_and_makes_no_calls(tmp_path):
    scorer = FakeScorer({"claude": {"kvk.draw": 92}})
    run(tmp_path, scorer)
    calls = len(scorer.prompts)
    report, _ = run(tmp_path, scorer)
    assert len(scorer.prompts) == calls and verdicts(report)["kvk.draw"] == "fail"


def test_two_scorers_must_agree_to_fail(tmp_path):
    scorer = FakeScorer({"claude": {"kvk.draw": 92, "kvk.seed": 80}, "codex": {"kvk.draw": 75, "kvk.seed": 10}})
    report, _ = run(tmp_path, scorer, "--second", "codex")
    assert verdicts(report)["kvk.draw"] == "fail" and verdicts(report)["kvk.seed"] == "review"
    assert {service for service, _ in scorer.prompts} == {"claude", "codex"}


def test_a_scorer_that_fails_leaves_strings_unscored_but_rules_still_report(tmp_path):
    def broken(service, prompt, model):
        raise RuntimeError("usage limit")

    report, code = run(tmp_path, broken)
    assert report["meta"]["unscored"] == 4 and code == 1 and verdicts(report)["kvk.round"] == "fail"
    assert verdicts(report)["kvk.draw"] == "ok"


def test_symlinked_and_outside_files_are_never_read(tmp_path):
    root = project(tmp_path)
    secret = tmp_path / "secret.ts"
    secret.write_text('const key = "TOP-SECRET";', encoding="utf-8")
    (root / "src" / "link.ts").symlink_to(secret)
    files = l10n_lint.read_sources(root / "src")
    assert list(files) == ["src/Bracket.tsx"] and "TOP-SECRET" not in "".join(files.values())


def test_a_planted_cache_cannot_pass_a_wrong_string(tmp_path):
    scorer = FakeScorer({"claude": {"kvk.draw": 92}})
    run(tmp_path, scorer)
    cache_path = tmp_path / "cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    for entry in cache.values():       # an attacker rewrites every cached score to "fine" with a bogus shape
        for value in entry.values():
            value["score"] = -1
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    calls = len(scorer.prompts)
    report, code = run(tmp_path, scorer)
    assert len(scorer.prompts) > calls and verdicts(report)["kvk.draw"] == "fail" and code == 1


def test_default_cache_lives_outside_the_project(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    path = l10n_lint.default_cache_path(tmp_path / "project")
    assert (tmp_path / "xdg" / "l10n-sense") in path.parents and (tmp_path / "project") not in path.parents
    assert path != l10n_lint.default_cache_path(tmp_path / "other")


def test_gettext_file_needs_no_source_and_uses_its_references(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/draw.py").write_text("pairs = draw_bracket(kingdoms)\ntitle = _('KvK draw')\n", encoding="utf-8")
    (tmp_path / "ja.po").write_text('#. Bracket draw page title\n#: src/draw.py:2\nmsgid "KvK draw"\nmsgstr "KvK引き分け"\n\n'
                                    'msgid "Hello %(name)s"\nmsgstr "こんにちは"\n', encoding="utf-8")
    scorer = FakeScorer({"claude": {"KvK draw": 95}})
    code = l10n_lint.main(["check", "--target", str(tmp_path / "ja.po"), "--lang", "ja", "--src", str(tmp_path / "src"),
                           "--cache", str(tmp_path / "c.json"), "--out", str(tmp_path / "r.json")], call=scorer)
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert code == 1 and verdicts(report) == {"KvK draw": "fail", "Hello %(name)s": "fail"}
    prompt = scorer.prompts[0][1]
    assert "developer note: Bracket draw page title" in prompt and "draw_bracket(kingdoms)" in prompt


def test_unsupported_file_type_is_a_clean_error(tmp_path, capsys):
    (tmp_path / "ja.csv").write_text("a,b", encoding="utf-8")
    assert l10n_lint.main(["check", "--target", str(tmp_path / "ja.csv"), "--lang", "ja", "--no-model"]) == 2
    assert "unsupported locale file type" in capsys.readouterr().err


def test_android_strings_are_scored_in_one_call(tmp_path):
    for folder, body in (("values", '<string name="a">Charge</string><string name="b">Save</string><string name="c">Open</string>'),
                         ("values-ja", '<string name="a">請求</string><string name="b">保存</string><string name="c">開く</string>')):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "strings.xml").write_text(f"<resources>{body}</resources>", encoding="utf-8")
    scorer = FakeScorer({"claude": {"a": 90}})
    code = l10n_lint.main(["check", "--source", str(tmp_path / "values/strings.xml"), "--target", str(tmp_path / "values-ja/strings.xml"),
                           "--lang", "ja", "--cache", str(tmp_path / "c.json"), "--out", str(tmp_path / "r.json")], call=scorer)
    assert code == 1 and len(scorer.prompts) == 1


ESC, BEL, DEL, CSI, RLO = chr(0x1B), chr(0x07), chr(0x7F), chr(0x9B), chr(0x202E)


def test_scorer_error_text_cannot_drive_the_terminal(tmp_path, capsys):
    def hostile(service, prompt, model):
        raise RuntimeError(f"model said {ESC}]0;title{BEL} {CSI}31m {RLO}")

    run(tmp_path, hostile)
    err = capsys.readouterr().err
    assert "could not be scored" in err
    assert not any(char in err for char in (ESC, BEL, CSI, RLO))


def test_json_text_escapes_control_and_direction_characters_and_keeps_the_data():
    hostile = f"evil{DEL}{CSI}31m{RLO}{ESC}[2J{chr(0x2028)}{chr(0x2066)} \u65e5\u672c\u8a9e"
    report = {"strings": [{"key": hostile, "note": hostile}]}
    text = l10n_lint.json_text(report)
    assert not any(char in text for char in (ESC, DEL, CSI, RLO, chr(0x2028), chr(0x2066)))
    assert json.loads(text) == report          # valid JSON, nothing dropped
    assert "\u65e5\u672c\u8a9e" in text           # ordinary non-ASCII text stays readable


def test_json_format_goes_through_json_text(tmp_path, capsys, monkeypatch):
    root = project(tmp_path)
    monkeypatch.setattr(l10n_lint, "json_text", lambda report, ascii_only=False: "SENTINEL")
    l10n_lint.main(["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"),
                    "--lang", "ja", "--no-model", "--format", "json"])
    assert capsys.readouterr().out.strip() == "SENTINEL"


def test_error_from_the_check_is_cleaned(tmp_path, capsys, monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError(f"bad {ESC}[31m {RLO} value")

    monkeypatch.setattr(l10n_lint, "check", boom)
    code = l10n_lint.main(["check", "--target", str(tmp_path / "ja.json"), "--lang", "ja", "--no-model"])
    err = capsys.readouterr().err
    assert code == 2 and "bad" in err and ESC not in err and RLO not in err


INVISIBLE = [chr(code) for code in (0x7F, 0x9B, 0x202E, 0x2028, 0x2029, 0xE000, 0x2066, 0x200E, 0x200F, 0x061C, 0x200B, 0xFEFF, 0x00AD,
                                    0xE0001, 0xD800)]


def test_json_text_escapes_every_invisible_character_and_keeps_the_data():
    report = {"strings": [{"key": "k" + "".join(INVISIBLE), "note": "".join(INVISIBLE) + " ok"}]}
    text = l10n_lint.json_text(report)
    assert not any(char in text for char in INVISIBLE)
    assert json.loads(text) == report
    text.encode("utf-8")  # a lone surrogate would raise here


def test_out_file_is_escaped_like_stdout(tmp_path):
    root = project(tmp_path)
    source, target = root / "locales/en.json", root / "locales/ja.json"
    hostile = "x" + "".join(INVISIBLE[:-1])
    for path in (source, target):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["hostile"] = hostile
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    l10n_lint.main(["check", "--source", str(source), "--target", str(target), "--lang", "ja", "--no-model",
                    "--out", str(root / "report.json")])
    written = (root / "report.json").read_text(encoding="utf-8")
    assert not any(char in written for char in INVISIBLE[:-1])
    assert hostile in [entry["source"] for entry in json.loads(written)["strings"]]


def test_unknown_argument_is_cleaned(capsys):
    with pytest.raises(SystemExit) as exit_info:
        l10n_lint.main(["check", "--target", "x", "--lang", "ja", f"--bogus{ESC}[31m{RLO}{BEL}"])
    err = capsys.readouterr().err
    assert exit_info.value.code == 2 and "bogus" in err and not any(char in err for char in (ESC, RLO, BEL))


def test_broken_yaml_and_unwritable_out_exit_2_without_a_traceback(tmp_path, capsys):
    pytest.importorskip("yaml")
    (tmp_path / "en.yml").write_text("a: b\n", encoding="utf-8")
    (tmp_path / "ja.yml").write_text("a: [unclosed\n", encoding="utf-8")
    assert l10n_lint.main(["check", "--source", str(tmp_path / "en.yml"), "--target", str(tmp_path / "ja.yml"),
                           "--lang", "ja", "--no-model"]) == 2
    assert "not valid YAML" in capsys.readouterr().err
    (tmp_path / "p").mkdir()
    root = project(tmp_path / "p")
    (root / "outdir").mkdir()
    assert l10n_lint.main(["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"),
                           "--lang", "ja", "--no-model", "--out", str(root / "outdir")]) == 2


def test_one_scorer_alone_cannot_fail_a_string_when_two_were_asked_for(tmp_path):
    class HalfBroken(FakeScorer):
        def __call__(self, service, prompt, model):
            if service == "claude":
                raise RuntimeError("no answer")
            return super().__call__(service, prompt, model)

    report, _ = run(tmp_path, HalfBroken({"codex": {"kvk.draw": 90, "kvk.seed": 90}}), "--second", "codex")
    assert verdicts(report)["kvk.draw"] == "review" and verdicts(report)["kvk.seed"] == "review"
    assert report["meta"]["unscored"] > 0


def test_help_keeps_argparse_colours_intact(capsys, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    with pytest.raises(SystemExit) as exit_info:
        l10n_lint.main(["check", "--help"])
    out = capsys.readouterr().out
    assert exit_info.value.code == 0 and "--target" in out
    assert re.search(r"(?<!\x1b)\[\d+(;\d+)*m", out) is None  # no escape sequence with its ESC replaced


def test_unscored_counts_a_string_the_second_scorer_missed_and_text_says_so(tmp_path, capsys):
    class SecondBroken(FakeScorer):
        def __call__(self, service, prompt, model):
            if service == "codex":
                raise RuntimeError("no answer")
            return super().__call__(service, prompt, model)

    report, code = run(tmp_path, SecondBroken({"claude": {"kvk.draw": 90}}), "--second", "codex")
    assert report["meta"]["unscored"] == 4 and verdicts(report)["kvk.draw"] == "review"
    capsys.readouterr()
    l10n_lint.main(["check", "--source", str(tmp_path / "locales/en.json"), "--target", str(tmp_path / "locales/ja.json"),
                    "--lang", "ja", "--src", str(tmp_path / "src"), "--cache", str(tmp_path / "cache.json"), "--second", "codex"],
                   call=SecondBroken({"claude": {}}))
    assert "4 strings were not scored" in capsys.readouterr().out


@pytest.mark.parametrize("text", ["[]", "null", '"x"', '{"strings": []}', '{"strings": {"a": {"localizations": []}}}',
                                  '{"strings": {"a": {"localizations": {"ja": null}}}}', '{"sourceLanguage": ["en"], "strings": {"a": {}}}'])
def test_xcstrings_of_the_wrong_shape_exit_2(tmp_path, capsys, text):
    path = tmp_path / "Localizable.xcstrings"
    path.write_text(text, encoding="utf-8")
    assert l10n_lint.main(["check", "--target", str(path), "--lang", "ja", "--no-model"]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_absent_file_and_bad_src_exit_2(tmp_path):
    root = project(tmp_path)
    base = ["check", "--source", str(root / "locales/en.json"), "--lang", "ja"]
    assert l10n_lint.main([*base, "--target", str(root / "locales/absent.json"), "--no-model"]) == 2
    scorer = FakeScorer({"claude": {}})
    assert l10n_lint.main([*base, "--target", str(root / "locales/ja.json"), "--src", str(root / "nowhere"),
                           "--cache", str(root / "c.json")], call=scorer) == 2
    assert scorer.prompts == []


@pytest.mark.parametrize("option", ["--window", "--workers"])
def test_window_and_workers_below_one_are_usage_errors(option):
    with pytest.raises(SystemExit) as exit_info:
        l10n_lint.main(["check", "--target", "x.json", "--lang", "ja", option, "0"])
    assert exit_info.value.code == 2


def test_unwritable_cache_stops_before_any_model_call(tmp_path, capsys):
    root = project(tmp_path)
    (root / "cachedir").mkdir()
    scorer = FakeScorer({"claude": {}})
    code = l10n_lint.main(["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"),
                           "--lang", "ja", "--cache", str(root / "cachedir")], call=scorer)
    assert code == 2 and scorer.prompts == []


def test_a_cache_that_cannot_be_saved_does_not_lose_the_report(tmp_path, capsys):
    root = project(tmp_path)
    cache = root / "cache.json"

    class Spoiler(FakeScorer):
        def __call__(self, service, prompt, model):
            if cache.is_file():
                cache.unlink()
                cache.mkdir()
            return super().__call__(service, prompt, model)

    report, code = run(root, Spoiler({"claude": {"kvk.draw": 90}}))
    assert verdicts(report)["kvk.draw"] == "fail" and "could not save the score cache" in capsys.readouterr().err


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_stdout_that_is_not_utf8_gets_escapes_not_a_crash(tmp_path, monkeypatch, fmt):
    root = project(tmp_path)
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252", newline=""))
    code = l10n_lint.main(["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"),
                           "--lang", "ja", "--no-model", "--format", fmt])
    sys.stdout.flush()
    text = raw.getvalue().decode("cp1252")
    assert code == 1 and text
    if fmt == "json":
        assert any(entry["target"] == "KvK\u5f15\u304d\u5206\u3051" for entry in json.loads(text)["strings"])


def test_interrupt_exits_130_with_one_line(tmp_path, capsys):
    def interrupted(service, prompt, model):
        raise KeyboardInterrupt

    root = project(tmp_path)
    code = l10n_lint.main(["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"),
                           "--lang", "ja", "--cache", str(root / "cache.json"), "--workers", "1"], call=interrupted)
    err = capsys.readouterr().err
    assert code == 130 and "interrupted" in err and "Traceback" not in err


def test_out_pointing_at_a_locale_file_is_refused(tmp_path):
    root = project(tmp_path)
    before = (root / "locales/ja.json").read_bytes()
    for victim in ("locales/ja.json", "locales/en.json"):
        with pytest.raises(SystemExit) as exit_info:
            l10n_lint.main(["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"),
                            "--lang", "ja", "--no-model", "--out", str(root / victim)])
        assert exit_info.value.code == 2
    assert (root / "locales/ja.json").read_bytes() == before


def test_cache_pointing_at_a_locale_file_or_at_the_report_is_refused(tmp_path, capsys):
    root = project(tmp_path)
    before = {name: (root / name).read_bytes() for name in ("locales/ja.json", "locales/en.json")}
    base = ["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"), "--lang", "ja"]
    called = []
    for extra, message in ((["--cache", str(root / "locales/ja.json")], "--cache is one of the locale files"),
                           (["--cache", str(root / "locales/en.json")], "--cache is one of the locale files")):
        with pytest.raises(SystemExit) as exit_info:
            l10n_lint.main(base + extra, call=lambda *args: called.append(args))
        assert exit_info.value.code == 2 and message in capsys.readouterr().err
    (root / "both.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        l10n_lint.main(base + ["--cache", str(root / "both.json"), "--out", str(root / "both.json")], call=lambda *args: called.append(args))
    assert exit_info.value.code == 2 and "same file" in capsys.readouterr().err
    assert called == [] and {name: (root / name).read_bytes() for name in before} == before     # no model call, both files untouched


def test_interrupt_without_a_model_does_not_mention_a_cache(tmp_path, capsys, monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    root = project(tmp_path)
    monkeypatch.setattr(l10n_lint, "check", interrupted)
    code = l10n_lint.main(["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"),
                           "--lang", "ja", "--no-model"])
    err = capsys.readouterr().err
    assert code == 130 and err.strip() == "l10n-sense: interrupted"


def test_a_wrong_shape_source_file_is_not_blamed_on_the_target_alone(tmp_path, capsys):
    root = project(tmp_path)
    (root / "locales/deep.json").write_text('{"a":' * 5000 + "1" + "}" * 5000, encoding="utf-8")       # nests deeper than the reader follows
    code = l10n_lint.main(["check", "--source", str(root / "locales/deep.json"), "--target", str(root / "locales/ja.json"),
                           "--lang", "ja", "--no-model"])
    err = capsys.readouterr().err
    assert code == 2 and "deep.json or ja.json" in err and "Traceback" not in err


def test_one_scorer_that_answers_nothing_reports_every_string_as_unscored(tmp_path, capsys):
    root = project(tmp_path)

    def broken(service, prompt, model):
        raise RuntimeError("scorer down")

    code = l10n_lint.main(["check", "--source", str(root / "locales/en.json"), "--target", str(root / "locales/ja.json"),
                           "--lang", "ja", "--cache", str(root / "cache.json"), "--workers", "1", "--format", "json"], call=broken)
    report = json.loads(capsys.readouterr().out)
    assert code in (0, 1) and report["meta"]["unscored"] > 0
    assert report["meta"]["unscored"] == sum(1 for entry in report["strings"] if entry.get("score") is None and entry["target"].strip())
