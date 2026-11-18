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
{{"scores": [{{"key": "<key>", "score": <0-100>, "note": "<under 15 words, in {language}>"}}]}}"""

LANGUAGE_NAMES = {"ja": "Japanese", "zh": "Chinese", "de": "German", "fr": "French", "es": "Spanish", "ko": "Korean"}


def build_prompt(case: dict) -> str:
    language = LANGUAGE_NAMES.get(case["language"], case["language"])
    rows = [{"key": key, "en": case["source"][key], case["language"]: case["target"][key]} for key in case["source"]]
    return "\n".join([INSTRUCTIONS.format(language=language), "", "Strings:",
                      json.dumps(rows, ensure_ascii=False, indent=1), "", "Source code that uses these keys:", case["code"]])


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
        out[row["key"]] = {"score": max(0, min(100, int(round(score)))), "note": str(row.get("note", ""))}
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
