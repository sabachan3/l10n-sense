"""Turn rule findings and model scores into one verdict per string, and print it. Standard library only."""

from __future__ import annotations

import hashlib
import json

ORDER = {"fail": 0, "review": 1, "warn": 2, "ok": 3}


def verdict(rules: list[dict], score: int | None, second: int | None, warn: int, fail: int) -> str:
    """fail    a rule fired, or the scorer (both scorers, when two ran) rates it wrong
    review  two scorers ran and only one rates it wrong: a person should look
    warn    unnatural but the meaning survives
    ok      nothing found (also when no model ran and no rule fired)"""
    if rules:
        return "fail"
    scores = [value for value in (score, second) if value is not None]
    if not scores:
        return "ok"
    wrong = [value >= fail for value in scores]
    if all(wrong):
        return "fail"
    if any(wrong):
        return "review"
    return "warn" if any(value >= warn for value in scores) else "ok"


def build_report(source: dict, target: dict, rule_findings: list[dict], scores: dict, second_scores: dict,
                 warn: int, fail: int, meta: dict) -> dict:
    by_key: dict[str, list[dict]] = {}
    for finding in rule_findings:
        by_key.setdefault(finding["key"], []).append({"rule": finding["rule"], "message": finding["message"]})
    strings = []
    for key in source:
        first, second = scores.get(key), second_scores.get(key)
        entry = {"key": key, "source": source[key], "target": target.get(key), "rules": by_key.get(key, []),
                 "score": first["score"] if first else None, "note": first["note"] if first else "",
                 "fix": (first or {}).get("fix", "") or (second or {}).get("fix", ""),
                 "second_score": second["score"] if second else None, "second_note": second["note"] if second else ""}
        entry["verdict"] = verdict(entry["rules"], entry["score"], entry["second_score"], warn, fail)
        strings.append(entry)
    counts = {name: sum(entry["verdict"] == name for entry in strings) for name in ORDER}
    return {"version": 1, "meta": meta, "thresholds": {"warn": warn, "fail": fail},
            "summary": {"strings": len(strings), **counts}, "strings": strings}


def exit_code(report: dict, fail_on: str = "fail") -> int:
    levels = {"fail": ("fail",), "review": ("fail", "review"), "warn": ("fail", "review", "warn"), "never": ()}[fail_on]
    return 1 if any(report["summary"][level] for level in levels) else 0


def format_text(report: dict, show: tuple[str, ...] = ("fail", "review", "warn")) -> str:
    def weight(entry):
        scores = [value for value in (entry["score"], entry["second_score"]) if value is not None]
        return (ORDER[entry["verdict"]], -(max(scores) if scores else 100), entry["key"])

    lines = []
    for entry in sorted((entry for entry in report["strings"] if entry["verdict"] in show), key=weight):
        scores = "/".join(str(value) for value in (entry["score"], entry["second_score"]) if value is not None)
        lines.append(f"{entry['verdict'].upper():6} {entry['key']}" + (f"  [{scores}]" if scores else ""))
        lines.append(f"       source: {entry['source']}")
        lines.append(f"       target: {entry['target']}")
        for rule in entry["rules"]:
            lines.append(f"       rule {rule['rule']}: {rule['message']}")
        for note in (entry["note"], entry["second_note"]):
            if note:
                lines.append(f"       note: {note}")
        if entry["fix"]:
            lines.append(f"       fix: {entry['fix']}")
    summary = report["summary"]
    lines.append(f"{summary['strings']} strings: {summary['fail']} fail, {summary['review']} review, "
                 f"{summary['warn']} warn, {summary['ok']} ok")
    return "\n".join(lines)


def cache_key(service: str, model: str | None, prompt_version: int, prompt: str) -> str:
    return hashlib.sha256(json.dumps([service, model, prompt_version, prompt], ensure_ascii=False).encode()).hexdigest()
