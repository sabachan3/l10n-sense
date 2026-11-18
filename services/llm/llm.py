"""Local LLM service: one text completion through the Claude Code CLI on this machine.

Contract (contracts/README.md, "LLM service"):
    echo '{"prompt": "...", "system": "..."}' | python services/llm/llm.py
    -> {"text": "...", "seconds": 1.2}

No hosted API is called from this repo; every model call goes through here.
The CLI runs with no tools, no MCP servers, no user settings and from an empty directory,
so it can only return text.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time

TIMEOUT_SECONDS = 600


class LLMError(RuntimeError):
    pass


def build_command(prompt: str, system: str | None = None, model: str | None = None) -> list[str]:
    # Text in, text out. Prompts contain text from repositories under review, which may be hostile,
    # so the model gets nothing it could act with:
    #   --tools ""            no built-in tools
    #   --strict-mcp-config   no MCP servers (none are passed), so no connector tools
    #   --setting-sources ""  no user/project settings, hooks or plugins
    command = ["claude", "-p", prompt, "--output-format", "json", "--tools", "", "--strict-mcp-config",
               "--setting-sources", "", "--no-session-persistence"]
    if system:
        command += ["--system-prompt", system]
    if model:
        command += ["--model", model]
    return command


def parse_output(stdout: str) -> str:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise LLMError(f"CLI did not return JSON: {stdout[:200]!r}") from exc
    if not isinstance(payload, dict) or payload.get("is_error") or not isinstance(payload.get("result"), str):
        raise LLMError(f"CLI reported an error: {str(payload)[:300]}")
    return payload["result"]


def complete(prompt: str, system: str | None = None, model: str | None = None, run=subprocess.run) -> dict:
    if not prompt.strip():
        raise LLMError("empty prompt")
    started = time.time()
    with tempfile.TemporaryDirectory() as empty:
        try:
            result = run(build_command(prompt, system, model), capture_output=True, text=True,
                         timeout=TIMEOUT_SECONDS, cwd=empty, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired as exc:
            raise LLMError(f"timed out after {TIMEOUT_SECONDS}s") from exc
        except FileNotFoundError as exc:
            raise LLMError("the `claude` CLI is not installed or not on PATH") from exc
    if result.returncode != 0:
        raise LLMError(f"CLI exited with {result.returncode}: {(result.stderr or result.stdout)[:300]}")
    return {"text": parse_output(result.stdout), "seconds": round(time.time() - started, 2)}


def main() -> int:
    try:
        request = json.load(sys.stdin)
        response = complete(request["prompt"], request.get("system"), request.get("model"))
    except (LLMError, KeyError, json.JSONDecodeError) as exc:
        print(f"llm: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    json.dump(response, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
