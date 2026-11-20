import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import formats_lib  # noqa: E402


def test_json_nested_chrome_messages_and_arb():
    assert formats_lib.parse_json('{"a": {"b": "x"}, "c": "y", "n": 3}') == ({"a.b": "x", "c": "y"}, {})
    chrome = json.dumps({"draw": {"message": "KvK draw", "description": "Bracket draw page title"}, "ok": {"message": "OK"}})
    assert formats_lib.parse_json(chrome) == ({"draw": "KvK draw", "ok": "OK"}, {"draw": "Bracket draw page title"})
    arb = json.dumps({"@@locale": "en", "draw": "KvK draw", "@draw": {"description": "Bracket draw"}})
    assert formats_lib.parse_json(arb) == ({"draw": "KvK draw"}, {"draw": "Bracket draw"})
    with pytest.raises(formats_lib.FormatError):
        formats_lib.parse_json("[1]")


def test_xcstrings_holds_source_target_and_comments():
    catalog = json.dumps({"sourceLanguage": "en", "strings": {
        "KvK draw": {"comment": "Bracket draw title", "localizations": {"ja": {"stringUnit": {"state": "translated", "value": "KvK引き分け"}}}},
        "welcome_title": {"localizations": {"en": {"stringUnit": {"value": "Welcome"}}, "ja": {"stringUnit": {"value": "ようこそ"}}}},
        "Untranslated": {}, "Version %@": {"shouldTranslate": False}}})
    pair = formats_lib.parse_xcstrings(catalog, "ja-JP")
    assert pair["source"] == {"KvK draw": "KvK draw", "welcome_title": "Welcome", "Untranslated": "Untranslated"}
    assert pair["target"] == {"KvK draw": "KvK引き分け", "welcome_title": "ようこそ"}
    assert pair["notes"] == {"KvK draw": "Bracket draw title"}


def test_yaml_strips_the_rails_locale_key():
    pytest.importorskip("yaml")
    assert formats_lib.parse_yaml("ja:\n  kvk:\n    draw: 抽選\n  ok: OK\n") == {"kvk.draw": "抽選", "ok": "OK"}
    assert formats_lib.parse_yaml("kvk:\n  draw: Draw\n") == {"kvk.draw": "Draw"}
    assert formats_lib.parse_yaml("en-US:\n  a: b\n") == {"a": "b"}


PO = r'''
msgid ""
msgstr "Content-Type: text/plain; charset=UTF-8\n"

#. Title of the bracket draw page
#: src/kvk/draw.py:12 src/kvk/views.py:40
msgid "KvK draw"
msgstr "KvK引き分け"

#: src/a.py:3
msgctxt "verb"
msgid "Open"
msgstr "開く"

msgid "Long "
"text \"quoted\"\n"
msgstr ""
"長い"
"文"

#, fuzzy
msgid "Guess"
msgstr "推測"

msgid "%d file"
msgid_plural "%d files"
msgstr[0] "%d 個のファイル"

#~ msgid "Old"
#~ msgstr "古い"
'''


def test_po_reads_ids_context_comments_references_and_skips_header_fuzzy_obsolete():
    pair = formats_lib.parse_po(PO)
    assert pair["source"]["KvK draw"] == "KvK draw" and pair["target"]["KvK draw"] == "KvK引き分け"
    assert pair["notes"]["KvK draw"] == "Title of the bracket draw page"
    assert pair["refs"]["KvK draw"] == [("src/kvk/draw.py", 12), ("src/kvk/views.py", 40)]
    assert pair["target"]["verb\u0004Open"] == "開く" and pair["notes"]["verb\u0004Open"] == "context: verb"
    assert pair["target"]['Long text "quoted"\n'] == "長い文"
    assert pair["target"]["%d file"] == "%d 個のファイル"
    assert "Guess" not in pair["source"] and "Old" not in pair["source"] and "" not in pair["source"]
    assert len(pair["source"]) == 4


ANDROID = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <!-- Title of the bracket draw screen -->
    <string name="kvk_draw">KvK draw</string>
    <string name="app_id" translatable="false">com.example</string>
    <string name="greeting">"Hello, %1$s! It\\'s <b>you</b>"</string>
    <plurals name="files"><item quantity="one">%d file</item><item quantity="other">%d files</item></plurals>
    <string-array name="modes"><item>Fast</item><item>Slow</item></string-array>
</resources>'''


def test_android_strings_plurals_arrays_and_comments():
    strings, notes = formats_lib.parse_android(ANDROID)
    assert strings == {"kvk_draw": "KvK draw", "greeting": "Hello, %1$s! It's you", "files#one": "%d file",
                       "files#other": "%d files", "modes[0]": "Fast", "modes[1]": "Slow"}
    assert notes == {"kvk_draw": "Title of the bracket draw screen"}
    with pytest.raises(formats_lib.FormatError):
        formats_lib.parse_android("<resources><string")


def test_ios_strings_with_comments_and_escapes():
    text = '/* Bracket draw title */\n"kvk.draw" = "KvK draw";\n/* No comment provided by engineer. */\n"quote" = "Say \\"hi\\"\\n";\n'
    strings, notes = formats_lib.parse_ios_strings(text)
    assert strings == {"kvk.draw": "KvK draw", "quote": 'Say "hi"\n'}
    assert notes == {"kvk.draw": "Bracket draw title"}


def test_load_pair_by_file_type(tmp_path):
    (tmp_path / "en.json").write_text('{"a": "Save"}', encoding="utf-8")
    (tmp_path / "ja.json").write_text('{"a": "保存"}', encoding="utf-8")
    pair = formats_lib.load_pair(tmp_path / "en.json", tmp_path / "ja.json", "ja")
    assert pair["source"] == {"a": "Save"} and pair["target"] == {"a": "保存"}
    (tmp_path / "ja.po").write_text(PO, encoding="utf-8")
    assert formats_lib.load_pair(None, tmp_path / "ja.po", "ja")["target"]["KvK draw"] == "KvK引き分け"
    (tmp_path / "ja.strings").write_bytes('"a" = "保存";'.encode("utf-16"))
    (tmp_path / "en.strings").write_text('"a" = "Save";', encoding="utf-8")
    assert formats_lib.load_pair(tmp_path / "en.strings", tmp_path / "ja.strings", "ja")["target"] == {"a": "保存"}
    with pytest.raises(formats_lib.FormatError):
        formats_lib.load_pair(None, tmp_path / "ja.json", "ja")
    with pytest.raises(formats_lib.FormatError):
        formats_lib.load_pair(tmp_path / "en.json", tmp_path / "ja.strings", "ja")
    with pytest.raises(formats_lib.FormatError):
        formats_lib.kind(tmp_path / "ja.csv")
