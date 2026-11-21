"""What a release depends on, checked without building anything: one version everywhere, a
README that works as the PyPI page, an sdist list that matches the wheel's, pinned actions and a
publish workflow that a push cannot start. scripts/e2e.sh checks the built archives themselves."""

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import l10n_sense  # noqa: E402
from l10n_sense import cli  # noqa: E402

PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))


def read_workflow(path):
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return document, document[True]  # YAML 1.1 reads the key `on` as the boolean true


def test_version_flag_prints_the_one_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"l10n-sense {l10n_sense.__version__}\n"


def test_pyproject_package_and_changelog_carry_the_same_version():
    declared = re.search(r'^version = "([^"]+)"$', PYPROJECT, re.M).group(1)
    newest_entry = re.search(r"^## (\S+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M).group(1)
    assert declared == l10n_sense.__version__ == newest_entry
    assert re.fullmatch(r"\d+\.\d+\.\d+", declared)  # the release workflow expects the tag v<version>


def test_readme_has_no_relative_link_or_image():
    # PyPI renders README.md as the project page; a relative target is a dead link there.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)\s]+)", readme) + re.findall(r"""(?:src|href)=["']([^"']+)""", readme)
    assert len(targets) >= 20
    assert [target for target in targets if not target.startswith(("https://", "#"))] == []


def test_readme_offers_the_repository_install_and_marks_pypi_commands_as_not_yet_working():
    # Until the first release the PyPI commands must not read as working. docs/release.md tells
    # the owner to move them up and to update this test in the same commit.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    from_repository = readme.index("uvx --from git+https://github.com/sabachan3/l10n-sense l10n-sense")
    marker = readme.index("After the first release on PyPI these will work; today they do not:")
    assert from_repository < marker < readme.index("pip install l10n-sense")
    assert marker < readme.index("uvx l10n-sense --help") and marker < readme.index("pipx install l10n-sense")


def test_sdist_lists_every_file_the_wheel_is_built_from():
    wheel_sources = set(re.findall(r'^"(services/[^"]+)" = "l10n_sense/_services/', PYPROJECT, re.M))
    sdist = PYPROJECT.split("[tool.hatch.build.targets.sdist]")[1]
    listed = set(re.findall(r'^    "([^"]+)",$', sdist, re.M))
    assert len(wheel_sources) == 7
    assert listed == wheel_sources | {"l10n_sense", "README.md", "LICENSE", "CHANGELOG.md", "pyproject.toml"}


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda path: path.name)
def test_every_action_is_pinned_to_a_full_commit_with_its_version_noted(path):
    uses = re.findall(r"^\s*-?\s*uses:\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
    assert uses
    for line in uses:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+", line), line


def test_workflow_files_are_the_two_this_test_knows():
    assert [path.name for path in WORKFLOWS] == ["ci.yml", "release.yml"]


def test_release_workflow_cannot_be_started_by_a_push():
    _, triggers = read_workflow(ROOT / ".github/workflows/release.yml")
    assert set(triggers) == {"release", "workflow_dispatch"}
    assert triggers["release"] == {"types": ["published"]}


def test_release_workflow_publishes_only_after_the_gate_and_the_package_check():
    text = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    document, _ = read_workflow(ROOT / ".github/workflows/release.yml")
    jobs = document["jobs"]
    assert document["permissions"] == {"contents": "read"}
    publishing = {name for name, job in jobs.items()
                  if any("gh-action-pypi-publish" in step.get("uses", "") for step in job["steps"])}
    assert publishing == {"publish", "publish-testpypi"}
    for name, job in jobs.items():
        if name in publishing:
            assert set(job["needs"]) == {"gate", "build"}, name
            assert job["permissions"] == {"id-token": "write"}, name
            assert all("run" not in step and "checkout" not in step.get("uses", "") for step in job["steps"]), name
        else:
            assert "permissions" not in job, name
    assert jobs["publish"]["environment"]["name"] == "pypi"
    assert jobs["publish"]["if"] == "github.event_name == 'release' || inputs.target == 'pypi'"
    assert jobs["publish-testpypi"]["environment"]["name"] == "testpypi"
    assert jobs["publish-testpypi"]["if"] == "github.event_name == 'workflow_dispatch' && inputs.target == 'testpypi'"
    # Trusted publishing only: no token or password is handed to an upload step.
    assert "password" not in str(jobs) and "secrets." not in text
    # Started by hand, it uploads nowhere unless asked to.
    assert document[True]["workflow_dispatch"]["inputs"]["target"]["default"] == "nowhere"
    commands = {name: [step.get("run", "") for step in job["steps"]] for name, job in jobs.items()}
    assert "scripts/test.sh" in commands["gate"]
    build = commands["build"]
    assert build.index("uv build --out-dir dist") < build.index("scripts/e2e.sh dist")
    assert "upload-artifact" in jobs["build"]["steps"][-1]["uses"]  # nothing is stored before the check passed


def test_release_gate_runs_the_same_matrix_as_ci():
    release, _ = read_workflow(ROOT / ".github/workflows/release.yml")
    ci, _ = read_workflow(ROOT / ".github/workflows/ci.yml")
    assert release["jobs"]["gate"]["strategy"]["matrix"] == ci["jobs"]["gate"]["strategy"]["matrix"]
    assert release["jobs"]["gate"]["env"] == ci["jobs"]["gate"]["env"]
