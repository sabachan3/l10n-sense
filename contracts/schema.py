"""Contract v1 validation. Standard library only."""

from __future__ import annotations

CONTRACT_VERSION = 1
LABELS = ("ok", "wrong")


class ContractError(ValueError):
    pass


def _strings(value, where: str) -> dict:
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise ContractError(f"{where}: expected an object of string to string")
    return value


def validate_case(case: dict) -> dict:
    """One benchmark case: a source locale, a target locale to audit, code, and the truth."""
    for name, kind in (("id", str), ("language", str), ("about", str), ("code", str)):
        if not isinstance(case.get(name), kind):
            raise ContractError(f"case: field '{name}' missing or not {kind.__name__}")
    where = f"case {case['id']}"
    source = _strings(case.get("source"), f"{where}.source")
    target = _strings(case.get("target"), f"{where}.target")
    labels = _strings(case.get("labels"), f"{where}.labels")
    if set(source) != set(target) or set(source) != set(labels):
        raise ContractError(f"{where}: source, target and labels must have the same keys")
    bad = sorted(set(labels.values()) - set(LABELS))
    if bad:
        raise ContractError(f"{where}: unknown labels {bad}")
    return case


def validate_findings(report: dict) -> dict:
    """Reviewer output for one case: the keys it flags, each with a reason and a suggestion."""
    if not isinstance(report.get("id"), str) or not isinstance(report.get("mode"), str):
        raise ContractError("findings: 'id' and 'mode' are required strings")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ContractError(f"findings {report['id']}: 'findings' must be a list")
    for finding in findings:
        for name in ("key", "reason", "suggestion"):
            if not isinstance(finding.get(name), str):
                raise ContractError(f"findings {report['id']}: each finding needs string '{name}'")
    return report
