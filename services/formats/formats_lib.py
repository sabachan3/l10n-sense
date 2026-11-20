"""Read locale files of several formats into one shape. Standard library only (YAML needs PyYAML).

    load_pair(source_path or None, target_path, language) -> Locale pair

A pair is {"source": {key: text}, "target": {key: text}, "notes": {key: text}, "refs": {key: [(path, line)]}}.
`notes` are developer comments attached to a string; `refs` are source locations recorded in the
file itself (gettext). Formats that hold source and translation together (gettext .po, Xcode
.xcstrings) need no separate source file.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path


class FormatError(ValueError):
    pass


def flatten(tree: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value in tree.items():
        key = f"{prefix}.{name}" if prefix else str(name)
        if isinstance(value, dict):
            out.update(flatten(value, key))
        elif isinstance(value, str):
            out[key] = value
    return out


# ------------------------------------------------------------------ JSON family

def parse_json(text: str) -> tuple[dict[str, str], dict[str, str]]:
    """Nested or flat JSON, Chrome-extension messages.json, Flutter ARB. Returns (strings, notes)."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise FormatError("a JSON locale file must hold an object")
    entries = [value for value in data.values() if isinstance(value, dict)]
    if entries and len(entries) == len(data) and all(isinstance(value.get("message"), str) for value in entries):
        return ({key: value["message"] for key, value in data.items()},
                {key: value["description"] for key, value in data.items() if isinstance(value.get("description"), str)})
    if any(key.startswith("@") for key in data):  # ARB: "@key" holds metadata for "key"
        strings = {key: value for key, value in data.items() if not key.startswith("@") and isinstance(value, str)}
        notes = {key[1:]: value["description"] for key, value in data.items()
                 if key.startswith("@") and isinstance(value, dict) and isinstance(value.get("description"), str)}
        return strings, notes
    return flatten(data), {}


def parse_xcstrings(text: str, language: str) -> dict:
    """Xcode String Catalog: every language in one file; the key is usually the source text."""
    data = json.loads(text)
    source_language = data.get("sourceLanguage", "en")
    source, target, notes = {}, {}, {}

    def unit(entry: dict, tag: str):
        value = entry.get("localizations", {}).get(tag, {}).get("stringUnit", {}).get("value")
        return value if isinstance(value, str) else None

    tags = [language, language.split("-")[0]]
    for key, entry in data.get("strings", {}).items():
        if not isinstance(entry, dict) or entry.get("shouldTranslate") is False:
            continue
        source[key] = unit(entry, source_language) or key
        translated = next((value for value in (unit(entry, tag) for tag in tags) if value is not None), None)
        if translated is not None:
            target[key] = translated
        if isinstance(entry.get("comment"), str):
            notes[key] = entry["comment"]
    return {"source": source, "target": target, "notes": notes, "refs": {}}


# ------------------------------------------------------------------ YAML

def parse_yaml(text: str) -> dict[str, str]:
    try:
        import yaml
    except ImportError as exc:
        raise FormatError("YAML locale files need PyYAML: pip install pyyaml") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise FormatError(f"not valid YAML: {str(exc).splitlines()[0]}") from exc
    if not isinstance(data, dict):
        raise FormatError("a YAML locale file must hold a mapping")
    if len(data) == 1:  # Rails style: one top-level key naming the locale
        (name, inner), = data.items()
        # two-letter language code, optionally with region or script: en, ja, pt-BR, zh_Hant
        if isinstance(inner, dict) and re.fullmatch(r"[A-Za-z]{2}([_-][A-Za-z0-9]{2,8})*", str(name)):
            data = inner
    return flatten(data)


# ------------------------------------------------------------------ gettext

PO_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
PO_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "r": "\r"}


def _po_unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda match: PO_ESCAPES.get(match.group(1), match.group(1)), text)


def parse_po(text: str) -> dict:
    """gettext .po: msgid is the source, msgstr the translation. Plural entries use msgstr[0].
    Obsolete (#~) and fuzzy entries are skipped: neither is shown to users."""
    source, target, notes, refs = {}, {}, {}, {}
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        fields: dict[str, str] = {}
        comments, locations, current, fuzzy = [], [], None, False
        for line in block.split("\n"):
            line = line.strip()
            if not line or line.startswith("#~"):
                continue
            if line.startswith("#."):
                comments.append(line[2:].strip())
            elif line.startswith("#:"):
                for location in line[2:].split():
                    path, _, number = location.rpartition(":")
                    if path and number.isdigit():
                        locations.append((path, int(number)))
                    else:
                        locations.append((location, 0))
            elif line.startswith("#,"):
                fuzzy = fuzzy or "fuzzy" in line
            elif line.startswith("#"):
                continue
            else:
                match = re.match(r"(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?)\s+(.*)", line)
                if match:
                    current = match.group(1)
                    fields[current] = ""
                    line = match.group(2)
                if current:
                    fields[current] += "".join(_po_unescape(part) for part in PO_STRING.findall(line))
        msgid = fields.get("msgid")
        if not msgid or fuzzy:  # the empty msgid is the header
            continue
        key = f"{fields['msgctxt']}\u0004{msgid}" if "msgctxt" in fields else msgid
        source[key] = msgid
        target[key] = fields.get("msgstr", fields.get("msgstr[0]", ""))
        note = " ".join(comments + ([f"context: {fields['msgctxt']}"] if "msgctxt" in fields else []))
        if note:
            notes[key] = note
        if locations:
            refs[key] = locations
    return {"source": source, "target": target, "notes": notes, "refs": refs}


# ------------------------------------------------------------------ Android

def _android_text(element) -> str:
    text = "".join(element.itertext())
    text = re.sub(r"\s*\n\s*", " ", text).strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return re.sub(r"\\(['\"@?n])", lambda match: "\n" if match.group(1) == "n" else match.group(1), text)


def parse_android(text: str) -> tuple[dict[str, str], dict[str, str]]:
    """Android strings.xml: <string>, <plurals> (key#quantity) and <string-array> (key[index]).
    Strings marked translatable="false" are skipped. A comment right before a string is its note."""
    class WithComments(ElementTree.TreeBuilder):
        def comment(self, data):
            self.start("!comment", {})
            self.data(data)
            self.end("!comment")

    try:
        root = ElementTree.fromstring(text, parser=ElementTree.XMLParser(target=WithComments()))
    except ElementTree.ParseError as exc:
        raise FormatError(f"not valid XML: {exc}") from exc
    strings, notes, pending = {}, {}, None
    for element in root:
        if element.tag == "!comment":
            pending = " ".join((element.text or "").split())
            continue
        name = element.get("name")
        if name and element.get("translatable") != "false":
            keys = []
            if element.tag == "string":
                strings[name] = _android_text(element)
                keys = [name]
            elif element.tag == "plurals":
                for item in element.findall("item"):
                    strings[f"{name}#{item.get('quantity')}"] = _android_text(item)
                    keys.append(f"{name}#{item.get('quantity')}")
            elif element.tag == "string-array":
                for number, item in enumerate(element.findall("item")):
                    strings[f"{name}[{number}]"] = _android_text(item)
                    keys.append(f"{name}[{number}]")
            if pending:
                notes.update({key: pending for key in keys})
        pending = None
    return strings, notes


# ------------------------------------------------------------------ iOS .strings

IOS_ENTRY = re.compile(r'(?:/\*(?P<note>.*?)\*/\s*)?"(?P<key>(?:[^"\\]|\\.)*)"\s*=\s*"(?P<value>(?:[^"\\]|\\.)*)"\s*;', re.S)


def parse_ios_strings(text: str) -> tuple[dict[str, str], dict[str, str]]:
    strings, notes = {}, {}
    for match in IOS_ENTRY.finditer(text):
        key = _po_unescape(match.group("key"))
        strings[key] = _po_unescape(match.group("value"))
        note = " ".join((match.group("note") or "").split())
        if note and note != "No comment provided by engineer.":
            notes[key] = note
    return strings, notes


def read_text(path: Path) -> str:
    raw = Path(path).read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


# ------------------------------------------------------------------ entry point

def kind(path: Path) -> str:
    suffix = Path(path).suffix.lower()
    kinds = {".json": "json", ".arb": "json", ".yml": "yaml", ".yaml": "yaml", ".po": "po", ".pot": "po",
             ".xml": "android", ".strings": "ios", ".xcstrings": "xcstrings"}
    if suffix not in kinds:
        raise FormatError(f"unsupported locale file type {suffix!r}: use one of {sorted(kinds)}")
    return kinds[suffix]


def load_pair(source_path: Path | None, target_path: Path, language: str) -> dict:
    """Source and target strings of a locale file pair. Any file that cannot be understood is a
    FormatError: valid JSON, XML or YAML of the wrong shape must not surface as a crash."""
    try:
        return _load_pair(source_path, target_path, language)
    except (AttributeError, TypeError, KeyError, IndexError, RecursionError) as exc:
        raise FormatError(f"{Path(target_path).name} is not in the shape a locale file of its kind has "
                          f"({type(exc).__name__})") from exc


def _load_pair(source_path: Path | None, target_path: Path, language: str) -> dict:
    target_kind = kind(target_path)
    if target_kind == "po":
        return parse_po(read_text(target_path))
    if target_kind == "xcstrings":
        return parse_xcstrings(read_text(target_path), language)
    if source_path is None:
        raise FormatError(f"{Path(target_path).suffix} files hold one language: give the source file with --source")
    if kind(source_path) != target_kind:
        raise FormatError("source and target must be the same kind of file")
    parse = {"json": parse_json, "android": parse_android, "ios": parse_ios_strings,
             "yaml": lambda text: (parse_yaml(text), {})}[target_kind]
    source, notes = parse(read_text(source_path))
    target, _ = parse(read_text(target_path))
    return {"source": source, "target": target, "notes": notes, "refs": {}}
