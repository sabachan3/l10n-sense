"""End-to-end test of the command with a fake scorer: no model, no network."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from l10n_sense import cli as l10n_lint  # noqa: E402


def project(tmp_path):
    (tmp_path / "locales").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "locales/en.json").write_text(json.dumps({"kvk": {"draw": "KvK draw", "round": "Round {n}", "seed": "Seed"},
                                                          "nav": {"flowSpawn": "Start the flow"}}))
    (tmp_path / "locales/ja.json").write_text(json.dumps({"kvk": {"draw": "KvK引き分け", "round": "ラウンド", "seed": "シード"},
                                                          "nav": {"flowSpawn": "Flow Spawn"}}, ensure_ascii=False))
    (tmp_path / "src/Bracket.tsx").write_text('const t = useTranslations("kvk");\nconst pairs = usePairings();\n<h2>{t("draw")}</h2>\n')
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
    secret.write_text('const key = "TOP-SECRET";')
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
    cache_path.write_text(json.dumps(cache))
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
    (tmp_path / "src/draw.py").write_text("pairs = draw_bracket(kingdoms)\ntitle = _('KvK draw')\n")
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
    (tmp_path / "ja.csv").write_text("a,b")
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
