"""Find where a translation key is used in source code. Standard library only, no model.

Works on next-intl / i18next style code, where a component binds a namespace
(`useTranslations("common")`) and then calls `t("noModelsFound")`. A usage is a line that holds
the key's last segment as a quoted string; files that also mention the namespace rank first.
"""

from __future__ import annotations

import re
from collections import defaultdict

QUOTED = re.compile(r"""["'`]([A-Za-z0-9_][A-Za-z0-9_.\-]*)["'`]""")
# whole string literals, for formats whose key is the source sentence (gettext, Xcode catalogs)
LITERAL = re.compile(r""""([^"\n\\]{2,160})"|'([^'\n\\]{2,160})'""")
# Android resource references: R.string.name, @string/name, R.plurals.name, R.array.name
RESOURCE = re.compile(r"(?:R\.(?:string|plurals|array)\.|@(?:string|plurals|array)/)([A-Za-z0-9_]+)")
MAX_LINE = 220


def flatten(tree: dict, prefix: str = "") -> dict[str, str]:
    """Nested locale object -> dotted key -> string. Non-string leaves are skipped."""
    out: dict[str, str] = {}
    for name, value in tree.items():
        key = f"{prefix}.{name}" if prefix else name
        if isinstance(value, dict):
            out.update(flatten(value, key))
        elif isinstance(value, str):
            out[key] = value
    return out


def build_index(files: dict[str, str]) -> dict[str, list[tuple[str, int]]]:
    """Quoted token -> [(path, line number)], for every quoted identifier in the sources."""
    index: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path in sorted(files):
        for number, line in enumerate(files[path].split("\n"), 1):
            tokens = set(QUOTED.findall(line)) | set(RESOURCE.findall(line))
            tokens.update(first or second for first, second in LITERAL.findall(line))
            for token in tokens:
                index[token].append((path, number))
    return index


def usages(key: str, files: dict[str, str], index: dict, limit: int = 2, around: int = 3) -> list[dict]:
    """Up to `limit` snippets showing the key in use, best evidence first."""
    namespace, _, rest = key.partition(".")
    leaf = key.rsplit(".", 1)[-1]
    key = key.rsplit("\u0004", 1)[-1]                 # gettext: context + EOT + msgid
    base = re.sub(r"(#\w+|\[\d+\])$", "", key)          # Android: files#one, modes[0]
    hits = list(index.get(key, [])) + [hit for hit in index.get(rest, []) if rest and rest != leaf]
    hits += index.get(leaf, [])
    if base != key:
        hits += index.get(base, [])
    seen, ranked = set(), []
    for path, number in hits:
        if (path, number) in seen:
            continue
        seen.add((path, number))
        text = files[path]
        binds_namespace = f'"{namespace}"' in text or f"'{namespace}'" in text
        ranked.append((0 if binds_namespace else 1, path, number))
    ranked.sort()
    out, used_paths = [], set()
    for _, path, number in ranked:
        if path in used_paths:
            continue  # one snippet per file: a second file tells more than a second line
        used_paths.add(path)
        lines = files[path].split("\n")
        start, end = max(0, number - 1 - around), min(len(lines), number + around)
        snippet = "\n".join(line[:MAX_LINE] for line in lines[start:end])
        out.append({"path": path, "line": number, "snippet": snippet})
        if len(out) == limit:
            break
    return out


def at_references(references: list[tuple[str, int]], files: dict[str, str], limit: int = 2, around: int = 3) -> list[dict]:
    """Snippets at locations the locale file itself records (gettext `#: path:line`)."""
    out = []
    for reference, number in references:
        path = next((name for name in sorted(files) if name == reference or name.endswith("/" + reference)
                     or reference.endswith("/" + name)), None)
        if path is None or any(item["path"] == path for item in out):
            continue
        lines = files[path].split("\n")
        centre = min(max(number, 1), len(lines))
        start, end = max(0, centre - 1 - around), min(len(lines), centre + around)
        out.append({"path": path, "line": centre, "snippet": "\n".join(line[:MAX_LINE] for line in lines[start:end])})
        if len(out) == limit:
            break
    return out


def render(key_usages: dict[str, list[dict]], notes: dict[str, str] | None = None) -> str:
    """Evidence block for a prompt: each key with its developer note and snippets, or a line
    saying that nothing was found."""
    notes = notes or {}
    blocks = []
    for key, found in key_usages.items():
        parts = [f"### {key}"]
        if notes.get(key):
            parts.append(f"developer note: {notes[key][:300]}")
        parts += [f"{item['path']}:{item['line']}\n{item['snippet']}" for item in found]
        if len(parts) == 1:
            parts.append("(no usage found in the source)")
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


def windows(keys: list[str], size: int, by_namespace: bool = True) -> list[list[str]]:
    """Consecutive groups of keys in file order. With `by_namespace`, a group never mixes
    top-level namespaces (`common.*`, `settings.*`); turn it off for formats whose keys are flat
    names or whole sentences, where splitting on dots would make one group per string."""
    groups, current, namespace = [], [], None
    for key in keys:
        top = key.split(".", 1)[0] if by_namespace and "." in key else ""
        if current and (top != namespace or len(current) == size):
            groups.append(current)
            current = []
        namespace = top
        current.append(key)
    if current:
        groups.append(current)
    return groups
