"""Find where a translation key is used in source code. Standard library only, no model.

Works on next-intl / i18next style code, where a component binds a namespace
(`useTranslations("common")`) and then calls `t("noModelsFound")`. A usage is a line that holds
the key's last segment as a quoted string; files that also mention the namespace rank first.
"""

from __future__ import annotations

import re
from collections import defaultdict

QUOTED = re.compile(r"""["'`]([A-Za-z0-9_][A-Za-z0-9_.\-]*)["'`]""")
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
            for token in set(QUOTED.findall(line)):
                index[token].append((path, number))
    return index


def usages(key: str, files: dict[str, str], index: dict, limit: int = 2, around: int = 3) -> list[dict]:
    """Up to `limit` snippets showing the key in use, best evidence first."""
    namespace, _, rest = key.partition(".")
    leaf = key.rsplit(".", 1)[-1]
    hits = list(index.get(key, [])) + [hit for hit in index.get(rest, []) if rest and rest != leaf]
    hits += index.get(leaf, [])
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


def render(key_usages: dict[str, list[dict]]) -> str:
    """Evidence block for a reviewer prompt: each key with its snippets, or a note that none was found."""
    blocks = []
    for key, found in key_usages.items():
        if not found:
            blocks.append(f"### {key}\n(no usage found in the source)")
            continue
        parts = [f"### {key}"] + [f"{item['path']}:{item['line']}\n{item['snippet']}" for item in found]
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


def windows(keys: list[str], size: int) -> list[list[str]]:
    """Consecutive groups of keys from the same top-level namespace, in file order."""
    groups, current, namespace = [], [], None
    for key in keys:
        top = key.split(".", 1)[0]
        if current and (top != namespace or len(current) == size):
            groups.append(current)
            current = []
        namespace = top
        current.append(key)
    if current:
        groups.append(current)
    return groups
