"""Second local LLM service: one text completion through the Codex CLI on this machine.

Same contract as services/llm:
    echo '{"prompt": "...", "model": "..."}' | python services/llm_codex/codex.py
    -> {"text": "...", "seconds": 1.2}

It exists so that a model from a different vendor can give an independent second opinion.
No hosted API is called directly; the CLI uses the account it is logged in with.

Prompts hold text from repositories under review, which may be hostile, so the agent runs with:
    --sandbox read-only     cannot write files or reach the network
    --ignore-user-config    no MCP servers, plugins or personal settings
    --ignore-rules          no project instruction files
    --ephemeral             no session kept
    -C <empty temp dir>     nothing of ours in its working directory
    --disable <tools>       no shell, no code execution, no browser, apps, plugins or image tools

The sandbox alone is not enough: with its default tools the agent read a file outside its
working directory when a prompt asked it to (checked 2026-11-19). With the tools in
DISABLED_FEATURES off it has no way to read anything; `eval_isolation.py` re-checks this with a
canary file and must pass after every CLI upgrade.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TIMEOUT_SECONDS = 900
DEFAULT_MODEL = "gpt-6-astra"
DEFAULT_EFFORT = "high"


# Everything that lets the agent act or look outside the prompt. Text in, text out.
DISABLED_FEATURES = ("shell_tool", "unified_exec", "code_mode_host", "apps", "plugins", "hooks", "browser_use",
                     "browser_use_external", "in_app_browser", "computer_use", "image_generation", "view_image",
                     "skill_search", "tool_suggest")


class LLMError(RuntimeError):
    pass


def build_command(workdir: str, output_file: str, model: str | None = None, effort: str | None = None) -> list[str]:
    disabled = [part for feature in DISABLED_FEATURES for part in ("--disable", feature)]
    return ["codex", "exec", *disabled, "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "--ignore-rules",
            "--ignore-user-config", "--color", "never", "-C", workdir, "-o", output_file,
            "-m", model or DEFAULT_MODEL, "-c", f'model_reasoning_effort="{effort or DEFAULT_EFFORT}"', "-"]


def complete(prompt: str, model: str | None = None, effort: str | None = None, run=subprocess.run) -> dict:
    if not prompt.strip():
        raise LLMError("empty prompt")
    started = time.time()
    with tempfile.TemporaryDirectory() as empty:
        output_file = Path(empty) / "last-message.txt"
        try:
            result = run(build_command(empty, str(output_file), model, effort), input=prompt, capture_output=True,
                         text=True, timeout=TIMEOUT_SECONDS, cwd=empty)
        except subprocess.TimeoutExpired as exc:
            raise LLMError(f"timed out after {TIMEOUT_SECONDS}s") from exc
        except FileNotFoundError as exc:
            raise LLMError("the `codex` CLI is not installed or not on PATH") from exc
        if result.returncode != 0:
            raise LLMError(f"CLI exited with {result.returncode}: {(result.stderr or result.stdout)[-300:]}")
        text = output_file.read_text(encoding="utf-8").strip() if output_file.exists() else ""
    if not text:
        raise LLMError("CLI returned no final message")
    return {"text": text, "seconds": round(time.time() - started, 2)}


def main() -> int:
    try:
        request = json.load(sys.stdin)
        response = complete(request["prompt"], request.get("model"), request.get("effort"))
    except (LLMError, KeyError, json.JSONDecodeError) as exc:
        print(f"llm_codex: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    json.dump(response, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
