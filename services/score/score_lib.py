"""Blind 0-100 "how wrong does this translation feel" scoring by a second model. Standard library only.

The scorer sees the English, the translation and the code, never the reviewer's findings or the
labels, so its scores are an independent second opinion that can be checked against known truth.
"""

from __future__ import annotations

import json
import re

BANDS = "0-20 fine, 21-40 slightly off, 41-60 unnatural but the meaning survives, 61-80 wrong or misleading, 81-100 clearly wrong"

INSTRUCTIONS = """You are a native {language} speaker and a senior localisation reviewer. For every key below, \
rate how wrong the {language} translation feels to a user of this app, from 0 to 100.

  0-20   correct and natural for this place in the UI
  21-40  correct, slightly stiff or not the usual wording
  41-60  understandable but unnatural (translationese, odd register, awkward form for a label or button)
  61-80  wrong or misleading in this context: wrong sense of a word, meaning changed, content dropped or added
  81-100 clearly wrong: a different meaning altogether, untranslated or placeholder text, garbled text, \
a translated identifier or code value, a broken placeholder

Judge against what the English means in this app; use the code to decide that. Rate every key.

Reply with one JSON object and nothing else:
{{"scores": [{{"key": "<key>", "score": <0-100>, "note": "<under 15 words, in {language}>", \
"fix": "<corrected translation when the score is 41 or more, otherwise an empty string>"}}]}}"""

LANGUAGE_NAMES = {"ja": "Japanese", "zh": "Chinese", "de": "German", "fr": "French", "es": "Spanish", "ko": "Korean"}


def build_prompt(case: dict) -> str:
    language = LANGUAGE_NAMES.get(case["language"], case["language"])
    rows = [{"key": key, "en": case["source"][key], case["language"]: case["target"][key]} for key in case["source"]]
    return "\n".join([INSTRUCTIONS.format(language=language), "", "Strings:",
                      json.dumps(rows, ensure_ascii=False, indent=1), "", "Source code that uses these keys:", case["code"]])


NOTE_LIMIT = 120


FIX_LIMIT = 2000
PROMPT_VERSION = 2  # bump when INSTRUCTIONS change, so cached scores are not reused across prompts


def clean_note(note, limit: int = NOTE_LIMIT) -> str:
    """Model-written text is untrusted: one line, no control characters, bounded length."""
    text = "".join(char if char.isprintable() else " " for char in str(note))
    return " ".join(text.split())[:limit]


def parse_scores(text: str, valid_keys: set[str]) -> dict[str, dict]:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("no JSON object in the reply")
    payload = json.loads(match.group(0))
    rows = payload.get("scores") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("reply has no 'scores' list")
    out = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("key") not in valid_keys or row["key"] in out:
            continue
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            continue
        out[row["key"]] = {"score": max(0, min(100, int(round(score)))), "note": clean_note(row.get("note", "")),
                           "fix": clean_note(row.get("fix") or "", FIX_LIMIT)}
    missing = valid_keys - set(out)
    if missing:
        raise ValueError(f"{len(missing)} keys were not scored, e.g. {sorted(missing)[0]}")
    return out


def auroc(positives: list[float], negatives: list[float]) -> float | None:
    """Chance that a wrong string scores above a fine one (ties count half)."""
    if not positives or not negatives:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


def at_threshold(scores: list[float], labels: list[bool], threshold: float) -> dict:
    flagged = [score >= threshold for score in scores]
    tp = sum(f and l for f, l in zip(flagged, labels))
    fp = sum(f and not l for f, l in zip(flagged, labels))
    fn = sum(l and not f for f, l in zip(flagged, labels))
    return {"threshold": threshold, "flagged": tp + fp, "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None, "false_alarms": fp}


def band(score: float, warn: int = 41, fail: int = 61) -> str:
    return "wrong" if score >= fail else "unnatural" if score >= warn else "fine"


def combine(first: dict[str, float], second: dict[str, float], warn: int = 41, fail: int = 61) -> dict[str, str]:
    """Verdict per string from two independent scorers.

    confirmed  both rate it wrong            -> safe to fail a CI run on
    disputed   exactly one rates it wrong    -> needs a person
    unnatural  neither says wrong, at least one says unnatural -> warning
    fine       both rate it fine
    Strings scored by only one scorer are left out.
    """
    verdicts = {}
    for key in first.keys() & second.keys():
        bands = (band(first[key], warn, fail), band(second[key], warn, fail))
        if bands == ("wrong", "wrong"):
            verdicts[key] = "confirmed"
        elif "wrong" in bands:
            verdicts[key] = "disputed"
        elif "unnatural" in bands:
            verdicts[key] = "unnatural"
        else:
            verdicts[key] = "fine"
    return verdicts


def agreement(first: dict[str, float], second: dict[str, float], fail: int = 61) -> dict:
    """How often two scorers agree on wrong / not wrong, with Cohen's kappa (chance-corrected)."""
    keys = sorted(first.keys() & second.keys())
    a = [first[key] >= fail for key in keys]
    b = [second[key] >= fail for key in keys]
    total = len(keys)
    if not total:
        return {"strings": 0, "both_wrong": 0, "only_first": 0, "only_second": 0, "neither": 0, "observed": None, "kappa": None}
    both = sum(x and y for x, y in zip(a, b))
    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    neither = total - both - only_a - only_b
    observed = (both + neither) / total
    expected = (sum(a) / total) * (sum(b) / total) + (1 - sum(a) / total) * (1 - sum(b) / total)
    kappa = (observed - expected) / (1 - expected) if expected < 1 else None
    return {"strings": total, "both_wrong": both, "only_first": only_a, "only_second": only_b, "neither": neither,
            "observed": observed, "kappa": kappa}


def validate_cached(entry, keys: set[str]) -> dict | None:
    """A cache file is untrusted input (it can be edited or committed by someone else). An entry
    is used only if it covers exactly the expected keys with in-range integer scores; its text is
    cleaned again. Anything else is treated as not cached."""
    if not isinstance(entry, dict) or set(entry) != keys:
        return None
    out = {}
    for key, value in entry.items():
        score = value.get("score") if isinstance(value, dict) else None
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
            return None
        out[key] = {"score": score, "note": clean_note(value.get("note", "")), "fix": clean_note(value.get("fix") or "", FIX_LIMIT)}
    return out
