"""Checks that need no model: same input, same answer, free to run on every commit.

Each check returns a finding {"key", "rule", "message"} or nothing. They are deliberately
conservative: a rule that cries wolf on brand names and one-word labels gets switched off.
"""

from __future__ import annotations

import re

# ICU arguments ({count}, {count, plural, ...}), double braces ({{name}}), printf (%s, %1$s, %d)
ICU_ARGUMENT = re.compile(r"\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:,[^{}]*(?:\{[^{}]*\}[^{}]*)*)?\}")
DOUBLE_BRACE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}")
PRINTF = re.compile(r"%(?:\d+\$)?(?:l{0,2}[dufx]|[s@if])|%\{[A-Za-z_][A-Za-z0-9_]*\}|%\([A-Za-z_][A-Za-z0-9_]*\)[sd]")
# an ordinary word: lower case, or Capitalised. Not an acronym (URL), not mixed case (WebDAV, sessionKey).
WORD = re.compile(r"(?<![A-Za-z0-9_=\-.])[A-Z]?[a-z]{2,}(?![A-Za-z0-9_=])")

SCRIPTS = {  # languages whose text must contain characters of their own script
    "ja": re.compile(r"[぀-ヿ一-鿿]"), "zh": re.compile(r"[一-鿿]"),
    "ko": re.compile(r"[가-힯]"), "ru": re.compile(r"[Ѐ-ӿ]"), "uk": re.compile(r"[Ѐ-ӿ]"),
    "ar": re.compile(r"[؀-ۿ]"), "he": re.compile(r"[֐-׿]"), "th": re.compile(r"[฀-๿]"),
    "hi": re.compile(r"[ऀ-ॿ]"), "el": re.compile(r"[Ͱ-Ͽ]"),
}


def placeholders(text: str) -> set[str]:
    doubles = {f"{{{{{name}}}}}" for name in DOUBLE_BRACE.findall(text)}
    rest = DOUBLE_BRACE.sub(" ", text)
    printf = set(PRINTF.findall(rest))          # includes Ruby %{name} and Python %(name)s
    rest = PRINTF.sub(" ", rest)
    return doubles | {f"{{{name}}}" for name in ICU_ARGUMENT.findall(rest)} | printf


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def check_string(key: str, source: str, target: str, language: str) -> list[dict]:
    """Findings for one string. `language` is the target language tag (its first part is used)."""
    found = []

    def add(rule: str, message: str) -> None:
        found.append({"key": key, "rule": rule, "message": message})

    if not target.strip():
        if source.strip():
            add("empty", "the translation is empty")
        return found
    missing = sorted(placeholders(source) - placeholders(target))
    extra = sorted(placeholders(target) - placeholders(source))
    if missing or extra:
        parts = ([f"missing {', '.join(missing)}"] if missing else []) + ([f"unexpected {', '.join(extra)}"] if extra else [])
        add("placeholder", "placeholders differ from the source: " + "; ".join(parts))

    leaf = key.rsplit("\u0004", 1)[-1].rsplit(".", 1)[-1]
    if key == source:  # gettext and Xcode catalogs: the key is the source text, so it says nothing
        leaf = ""
    words = WORD.findall(PRINTF.sub(" ", ICU_ARGUMENT.sub(" ", source)))
    if len(squash(leaf)) >= 4 and target.isascii() and squash(target) == squash(leaf) and target != source:
        add("key_as_value", f"the translation is the key name ({target!r}), not a translation of {source!r}")
    elif (script := SCRIPTS.get(language.split("-")[0].lower())) and len(words) >= 2 and not script.search(target):
        add("untranslated", "the text is still in Latin script" if target != source else "the text is identical to the source")
    return found


def check_locale(source: dict[str, str], target: dict[str, str], language: str) -> list[dict]:
    found = []
    for key, text in source.items():
        if key not in target:
            found.append({"key": key, "rule": "missing", "message": "the key has no translation"})
        else:
            found.extend(check_string(key, text, target[key], language))
    return found
