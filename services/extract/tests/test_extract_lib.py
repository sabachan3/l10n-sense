import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import extract_lib  # noqa: E402

FILES = {
    "src/Bracket.tsx": 'const t = useTranslations("kvk");\nexport function Bracket() {\n  const pairs = usePairings();\n'
                       '  return <h2>{t("draw")}</h2>;\n}\n',
    "src/Canvas.tsx": 'const t = useTranslations("tool");\nconst label = t("draw");\n',
    "src/Other.tsx": "const x = 1;\n",
}
INDEX = extract_lib.build_index(FILES)


def test_flatten_nested_locale_and_skip_non_strings():
    assert extract_lib.flatten({"a": {"b": "x", "c": {"d": "y"}}, "e": "z", "n": 3}) == {"a.b": "x", "a.c.d": "y", "e": "z"}


def test_usage_prefers_the_file_that_binds_the_namespace():
    found = extract_lib.usages("kvk.draw", FILES, INDEX, limit=1)
    assert found[0]["path"] == "src/Bracket.tsx" and found[0]["line"] == 4
    assert "usePairings" in found[0]["snippet"]
    assert extract_lib.usages("tool.draw", FILES, INDEX, limit=1)[0]["path"] == "src/Canvas.tsx"


def test_usage_returns_one_snippet_per_file_up_to_the_limit():
    assert [item["path"] for item in extract_lib.usages("kvk.draw", FILES, INDEX, limit=5)] == ["src/Bracket.tsx", "src/Canvas.tsx"]


def test_unknown_key_has_no_usage_and_render_says_so():
    assert extract_lib.usages("kvk.missing", FILES, INDEX) == []
    text = extract_lib.render({"kvk.draw": extract_lib.usages("kvk.draw", FILES, INDEX, limit=1), "kvk.missing": []})
    assert "### kvk.draw\nsrc/Bracket.tsx:4" in text and "### kvk.missing\n(no usage found in the source)" in text


def test_long_lines_are_cut():
    files = {"a.tsx": 't("k")' + "x" * 1000}
    snippet = extract_lib.usages("ns.k", files, extract_lib.build_index(files))[0]["snippet"]
    assert len(snippet) == extract_lib.MAX_LINE


def test_windows_keep_file_order_and_never_mix_namespaces():
    keys = ["a.1", "a.2", "a.3", "b.1", "b.2", "a.4"]
    assert extract_lib.windows(keys, 2) == [["a.1", "a.2"], ["a.3"], ["b.1", "b.2"], ["a.4"]]


def test_sentence_keys_android_resources_and_gettext_context_are_found():
    files = {"app/Main.kt": 'title = getString(R.string.kvk_draw)\ncount = resources.getQuantityString(R.plurals.files, n)\n',
             "app/View.swift": 'Text("KvK draw")\n', "src/a.py": 'label = _("Open")\n'}
    index = extract_lib.build_index(files)
    assert extract_lib.usages("kvk_draw", files, index)[0]["path"] == "app/Main.kt"
    assert extract_lib.usages("files#one", files, index)[0]["line"] == 2
    assert extract_lib.usages("KvK draw", files, index)[0]["path"] == "app/View.swift"
    assert extract_lib.usages("verb\u0004Open", files, index)[0]["path"] == "src/a.py"


def test_references_from_the_locale_file_are_resolved_by_path_suffix():
    files = {"proj/src/kvk/draw.py": "a\nb\ntitle = _('KvK draw')\nd\n"}
    found = extract_lib.at_references([("src/kvk/draw.py", 3), ("missing.py", 1)], files, around=0)
    assert found == [{"path": "proj/src/kvk/draw.py", "line": 3, "snippet": "title = _('KvK draw')"}]
    assert extract_lib.at_references([("src/kvk/draw.py", 999)], files, around=0)[0]["line"] == 5


def test_render_shows_developer_notes():
    text = extract_lib.render({"a": [], "b": []}, {"a": "Bracket draw title"})
    assert "### a\ndeveloper note: Bracket draw title" in text and "### b\n(no usage found in the source)" in text


def test_flat_keys_share_groups_and_sentence_keys_ignore_their_dots():
    assert extract_lib.windows(["kvk_draw", "greeting", "charge"], 20) == [["kvk_draw", "greeting", "charge"]]
    sentences = ["Saved. Open it?", "Done.", "a.b"]
    assert extract_lib.windows(sentences, 20, by_namespace=False) == [sentences]
    assert extract_lib.windows(["a", "b", "c"], 2) == [["a", "b"], ["c"]]
