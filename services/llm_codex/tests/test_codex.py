import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import codex  # noqa: E402


def test_command_is_locked_down_and_reads_the_prompt_from_stdin():
    command = codex.build_command("/tmp/empty", "/tmp/empty/out.txt")
    assert command[:2] == ["codex", "exec"] and command[-1] == "-"
    assert command[command.index("--sandbox") + 1] == "read-only"
    for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check"):
        assert flag in command
    assert not any("dangerously" in part or part == "--approve-for-me" for part in command)
    assert command[command.index("-C") + 1] == "/tmp/empty"
    assert command[command.index("-m") + 1] == codex.DEFAULT_MODEL
    assert 'model_reasoning_effort="high"' in command


def test_model_and_effort_can_be_chosen():
    command = codex.build_command("/d", "/d/o", model="other", effort="low")
    assert command[command.index("-m") + 1] == "other" and 'model_reasoning_effort="low"' in command


def fake_run(text, code=0):
    def run(command, **kwargs):
        assert kwargs["input"] == "hello" and Path(kwargs["cwd"]).is_dir() and not list(Path(kwargs["cwd"]).iterdir())
        if text is not None:
            Path(command[command.index("-o") + 1]).write_text(text, encoding="utf-8")
        return SimpleNamespace(returncode=code, stdout="log", stderr="boom")
    return run


def test_complete_returns_the_final_message():
    assert codex.complete("hello", run=fake_run(" 回答 \n"))["text"] == "回答"


def test_failures_become_llm_errors():
    with pytest.raises(codex.LLMError):
        codex.complete("  ")
    with pytest.raises(codex.LLMError):
        codex.complete("hello", run=fake_run("x", code=2))
    with pytest.raises(codex.LLMError):
        codex.complete("hello", run=fake_run(None))

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 1)

    with pytest.raises(codex.LLMError):
        codex.complete("hello", run=timeout)


def test_every_acting_tool_is_disabled():
    command = codex.build_command("/d", "/d/o")
    disabled = {command[i + 1] for i, part in enumerate(command) if part == "--disable"}
    assert {"shell_tool", "unified_exec", "code_mode_host", "browser_use", "computer_use", "apps", "plugins"} <= disabled
    assert "--enable" not in command
