"""Human judgments of reviewer findings. Standard library only.

An item is one finding (a flagged string). A judgment is one appended line
{"id", "verdict", "at"}; the last line for an id wins, so changing your mind is just judging again.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

VERDICTS = ("error", "unsure", "not_error")  # real error / cannot say / translation is fine


def load_items(cases_path: Path, findings_path: Path, notes_path: Path | None = None) -> list[dict]:
    """Findings joined with their strings, in a fixed pseudo-random order so that judging the
    first N gives a random sample of all findings."""
    cases = {case["id"]: case for case in _read(cases_path)}
    notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path and notes_path.exists() else {}
    items = []
    for report in _read(findings_path):
        case = cases[report["id"]]
        for finding in report["findings"]:
            key = finding["key"]
            item_id = f"{report['id']}|{report['mode']}|{key}"
            items.append({"id": item_id, "key": key, "source": case["source"][key], "target": case["target"][key],
                          "suggestion": finding["suggestion"], "reason": finding["reason"],
                          "reason_local": notes.get(item_id, "")})
    return sorted(items, key=lambda item: hashlib.sha256(item["id"].encode()).hexdigest())


def record(path: Path, item_id: str, verdict: str, known_ids: set[str], at: str) -> dict:
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    if item_id not in known_ids:
        raise ValueError("unknown item id")
    entry = {"id": item_id, "verdict": verdict, "at": at}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def latest(path: Path) -> dict[str, str]:
    return {entry["id"]: entry["verdict"] for entry in _read(path)} if path.exists() else {}


def summarize(verdicts: dict[str, str], total: int) -> dict:
    counts = {verdict: sum(value == verdict for value in verdicts.values()) for verdict in VERDICTS}
    judged = sum(counts.values())
    decided = counts["error"] + counts["not_error"]
    return {"total": total, "judged": judged, **counts,
            # precision with unsure left out, and the pessimistic value that counts unsure as not an error
            "precision": counts["error"] / decided if decided else None,
            "precision_strict": counts["error"] / judged if judged else None}


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def request_allowed(method: str, host: str | None, origin: str | None, content_type: str | None, port: int) -> bool:
    """Only the page this server serves may talk to it.

    Host must be this server (blocks DNS rebinding, where another site's name resolves to
    127.0.0.1). For POST the body must be declared as JSON (a cross-site form or `no-cors`
    fetch cannot send that type) and Origin, when a browser sends one, must be this server.
    """
    own_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    if host not in own_hosts:
        return False
    if method != "POST":
        return True
    if (content_type or "").split(";")[0].strip().lower() != "application/json":
        return False
    return origin is None or origin in {f"http://{name}" for name in own_hosts}
