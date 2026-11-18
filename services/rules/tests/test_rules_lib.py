import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rules_lib  # noqa: E402


def rules(key, source, target, language="ja"):
    return [finding["rule"] for finding in rules_lib.check_string(key, source, target, language)]


def test_placeholders_of_every_style():
    assert rules_lib.placeholders("Hi {name}, {count, plural, one {# item} other {# items}}") == {"{name}", "{count}"}
    assert rules_lib.placeholders("{{user}} sent %1$s and %d") == {"{{user}}", "%1$s", "%d"}
    assert rules_lib.placeholders("no placeholders") == set()


def test_placeholder_mismatch_is_reported_both_ways():
    assert rules("a.round", "Round {n}", "第{n}ラウンド") == []
    assert rules("a.round", "Round {n}", "ラウンド") == ["placeholder"]
    finding = rules_lib.check_string("a.x", "Until", "{time}まで", "ja")[0]
    assert finding["rule"] == "placeholder" and "unexpected {time}" in finding["message"]
    assert rules("a.p", "{count, plural, one {# model} other {# models}}", "{count} 個のモデル") == []


def test_key_name_used_as_the_translation():
    assert rules("common.accountId", "Account ID", "accountId") == ["key_as_value"]
    assert rules("agents.flowSpawn", "2 · OmniRoute spawns local binary", "Flow Spawn") == ["key_as_value"]
    assert rules("settings.pricingSourceLiteLLM", "LiteLLM (Community)", "Pricing Source Lite Llm") == ["key_as_value"]
    assert rules("common.ok", "OK", "ok") == []          # too short to tell
    assert rules("rules.oauth", "OAuth accounts", "OAuthアカウント") == []  # a real translation that starts with the key name
    assert rules("brand.docker", "Docker", "Docker") == []  # identical to the source: a name


def test_untranslated_needs_two_words_and_a_scripted_language():
    assert rules("cache.cachedTokens", "Cache Read Tokens", "Cached Tokens") == ["key_as_value"]  # stale key-name text
    assert rules("cache.readLabel", "Cache Read Tokens", "Tokens read from cache") == ["untranslated"]
    assert rules("memory.loading", "Loading memories...", "Loading memories...") == ["untranslated"]
    assert rules("common.pin", "Pin", "Pin") == []               # one word: could be a deliberate keep
    assert rules("common.open", "Open", "open") == ["key_as_value"]
    assert rules("docs.webdav", "WebDAV URL", "WebDAV URL") == []            # names and acronyms only
    assert rules("p.cookie", "sessionKey=sk-ant-...", "sessionKey=sk-ant-...") == []
    assert rules("common.token", "API Token", "APIトークン") == []
    assert rules("common.title", "Open settings", "Einstellungen öffnen", "de") == []  # Latin-script target language
    assert rules("common.title", "Open settings", "Open settings", "de") == []       # cannot tell without a model
    assert rules("common.title", "Open settings", "Open settings", "zh-CN") == ["untranslated"]


def test_empty_and_missing():
    assert rules("a", "Save", "  ") == ["empty"]
    assert rules("a", "", "") == []
    found = rules_lib.check_locale({"a": "Save", "b": "Open file"}, {"a": "保存"}, "ja")
    assert found == [{"key": "b", "rule": "missing", "message": "the key has no translation"}]


def test_ios_ruby_and_python_placeholders():
    assert rules_lib.placeholders("%@ has %lld items, %1$@") == {"%@", "%lld", "%1$@"}
    assert rules_lib.placeholders("Hello %{name}") == {"%{name}"}
    assert rules_lib.placeholders("Hello %(name)s") == {"%(name)s"}
    assert rules("a", "Hello %{name}", "こんにちは") == ["placeholder"]
    assert rules("a", "100% sure", "100% 確実") == []


def test_a_key_that_is_the_source_text_is_never_a_key_name_finding():
    assert rules("Open", "Open", "open") == []
    assert rules("Start the flow", "Start the flow", "Start the flow") == ["untranslated"]
