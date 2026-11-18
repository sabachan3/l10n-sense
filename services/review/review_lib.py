"""Prompt and reply handling for the reviewer. Standard library only.

Modes:
    pair  source and translation only (what quality scorers in translation platforms see)
    code  the same plus the source code that uses the strings
"""

from __future__ import annotations

import json
import re

MODES = ("pair", "code")

INSTRUCTIONS = """You audit the {language} locale file of an app. For each key you get the English source \
string and its {language} translation.

Flag a key ONLY when the translation says something different from what the English string means \
in this app: a wrong sense of an ambiguous word, a mistranslation, or a broken placeholder such as {{n}}.
Do NOT flag style, tone, politeness, spacing, or a translation that is merely not your first choice. \
A correct translation that could be nicer is not a finding. When you cannot tell which sense is meant, do not flag.

Work out what each string means from the evidence given, then judge.

Reply with one JSON object and nothing else:
{{"findings": [{{"key": "<key>", "reason": "<what the English means here and what the translation says instead>", \
"suggestion": "<corrected {language} translation>"}}]}}
Use an empty list when nothing is wrong."""

LANGUAGE_NAMES = {"ja": "Japanese", "de": "German", "fr": "French", "es": "Spanish", "zh": "Chinese", "ko": "Korean"}


def build_prompt(case: dict, mode: str) -> str:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    language = LANGUAGE_NAMES.get(case["language"], case["language"])
    rows = [{"key": key, "en": case["source"][key], case["language"]: case["target"][key]} for key in case["source"]]
    parts = [INSTRUCTIONS.format(language=language), "", "Strings:", json.dumps(rows, ensure_ascii=False, indent=1)]
    if mode == "code":
        parts += ["", "Source code that uses these keys:", case["code"]]
    return "\n".join(parts)


def parse_findings(text: str, valid_keys: set[str]) -> list[dict]:
    """Findings from a reply. Keys the case does not have are dropped: the reviewer may only
    speak about strings it was shown. Repeated keys keep the first finding."""
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("no JSON object in the reply")
    payload = json.loads(match.group(0))
    findings = payload.get("findings") if isinstance(payload, dict) else None
    if not isinstance(findings, list):
        raise ValueError("reply has no 'findings' list")
    out, seen = [], set()
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("key") not in valid_keys or finding["key"] in seen:
            continue
        seen.add(finding["key"])
        out.append({"key": finding["key"], "reason": str(finding.get("reason", "")),
                    "suggestion": str(finding.get("suggestion", ""))})
    return out
