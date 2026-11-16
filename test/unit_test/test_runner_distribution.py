"""The files a project uses to run WebRunner in CI: ``action.yml``, the runner image, the example workflow.

Text checks only: nothing is built and nothing is fetched. The YAML is read as text, like
``test_workflow_actions.py`` does, because PyYAML is not a test dependency; where it happens to be
installed the result is compared with what PyYAML reads.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from je_web_runner.utils.k8s_runner import RUNNER_IMAGE

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # PyYAML is optional: CI does not install it.
    yaml = None

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".github" / "workflows").is_dir())
_ACTION = _ROOT / "action.yml"
_CONTAINERFILE = _ROOT / "docker" / "Runner.Containerfile"
_EXAMPLES = sorted((_ROOT / "examples" / "ci").glob("*.yml"))
_WORKFLOWS = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
_ARGUMENTS = _ROOT / "je_web_runner" / "utils" / "cli" / "arguments.py"

_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
_PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
_VERSION_COMMENT = re.compile(r"^\s+#\s*v\d+(\.\d+)*\s*$")
_KEY = re.compile(r"^(\s*)(?:-\s+)?([\w-]+):(.*)$")
_FLAG = re.compile(r"(?<![\w-])(--[a-z][\w-]*|-[a-z])(?![\w-])")
_OWN_ACTION = re.compile(r"^(\./|Integration-Automation/WebRunner@)")
_EXPRESSION_IN_SCRIPT = re.compile(r"\$\{\{\s*(inputs\.|github\.event)")


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _block(lines: list[str], start: int) -> list[str]:
    """The lines nested below ``lines[start]``: every following line that is blank or indented deeper."""
    depth = _indent(lines[start])
    body = []
    for line in lines[start + 1:]:
        if line.strip() and _indent(line) <= depth:
            break
        body.append(line)
    return body


def _section(lines: list[str], name: str) -> list[str]:
    """The lines below the top-level key ``name``."""
    start = next(i for i, line in enumerate(lines) if re.match(rf"^{name}:\s*$", line))
    return _block(lines, start)


def _children(body: list[str]) -> dict[str, list[str]]:
    """``{key: its line and the lines below it}`` for the keys at the shallowest indentation of ``body``."""
    depth = min(_indent(line) for line in body if line.strip())
    found = {}
    for index, line in enumerate(body):
        match = _KEY.match(line)
        if match and _indent(line) == depth:
            found[match.group(2)] = [line, *_block(body, index)]
    return found


def _run_scripts(path: Path) -> list[str]:
    """The text of every ``run:`` in a workflow or action file, one-line and block forms alike."""
    lines = _lines(path)
    scripts = []
    for index, line in enumerate(lines):
        match = _KEY.match(line)
        if match and match.group(2) == "run":
            scripts.append("\n".join([match.group(3), *_block(lines, index)]))
    return scripts


def _uses(path: Path) -> list[tuple[str, str]]:
    """``(action reference, rest of the line)`` for every ``uses:``."""
    matches = (_USES.match(line) for line in _lines(path))
    return [(match.group(1), match.group(2)) for match in matches if match]


def _cli_flags() -> set[str]:
    """Every option string the CLI defines, read from its ``add_argument`` calls."""
    text = _ARGUMENTS.read_text(encoding="utf-8")
    return set(re.findall(r"""["'](--?[A-Za-z][\w-]*)["']""", text))


def _action_inputs() -> dict[str, list[str]]:
    return _children(_section(_lines(_ACTION), "inputs"))


# ---------- action.yml ---------------------------------------------------

def test_action_parses_as_a_composite_action():
    lines = _lines(_ACTION)
    top_level = {match.group(2) for match in map(_KEY.match, lines) if match and not match.group(1)}
    assert {"name", "description", "inputs", "outputs", "runs"} <= top_level
    assert not any("\t" in line for line in lines)
    runs = _children(_section(lines, "runs"))
    assert re.search(r"using:\s*\"?composite\"?\s*$", runs["using"][0])
    inputs = _action_inputs()
    assert {"actions-dir", "python-version", "channel", "package-version", "report", "report-format",
            "shard", "parallel", "parallel-mode", "tag", "exclude-tag", "fail-fast", "extra-args"} <= set(inputs)
    if yaml is not None:
        loaded = yaml.safe_load(_ACTION.read_text(encoding="utf-8"))
        assert list(loaded["inputs"]) == list(inputs)
        assert loaded["runs"]["using"] == "composite"


def test_every_input_and_output_is_documented():
    lines = _lines(_ACTION)
    for section in ("inputs", "outputs"):
        entries = _children(_section(lines, section))
        assert entries, section
        undocumented = [name for name, body in entries.items()
                        if not re.search(r"^\s+description:\s*\S", "\n".join(body[1:]), re.MULTILINE)]
        assert undocumented == [], section


def test_only_actions_dir_is_required():
    required = [name for name, body in _action_inputs().items()
                if re.search(r"^\s+required:\s*true\s*$", "\n".join(body), re.MULTILINE)]
    assert required == ["actions-dir"]


def test_exit_code_is_an_output_the_run_step_writes():
    outputs = _children(_section(_lines(_ACTION), "outputs"))
    assert "steps.run.outputs.exit-code" in "\n".join(outputs["exit-code"])
    text = _ACTION.read_text(encoding="utf-8")
    assert re.search(r"^\s+id:\s*run\s*$", text, re.MULTILINE)
    assert 'echo "exit-code=$status" >> "$GITHUB_OUTPUT"' in text


def test_action_pins_every_action_to_a_commit_with_its_version():
    used = _uses(_ACTION)
    assert used
    assert [ref + rest for ref, rest in used if not (_PINNED.match(ref) and _VERSION_COMMENT.match(rest))] == []


def test_action_uses_the_same_commits_as_the_workflows():
    # One version per action across the repository, as test_workflow_actions.py asks of the workflows.
    pinned = dict(ref.split("@") for workflow in _WORKFLOWS for ref, _rest in _uses(workflow) if "@" in ref)
    theirs = dict(ref.split("@") for path in (_ACTION, *_EXAMPLES)
                  for ref, _rest in _uses(path) if not _OWN_ACTION.match(ref))
    assert {action: sha for action, sha in theirs.items() if pinned.get(action, sha) != sha} == {}


@pytest.mark.parametrize("path", [_ACTION, *_EXAMPLES], ids=lambda p: p.name)
def test_no_expression_is_interpolated_into_a_script(path):
    scripts = _run_scripts(path)
    assert scripts
    assert [script for script in scripts if _EXPRESSION_IN_SCRIPT.search(script)] == []


def test_every_script_step_of_the_action_runs_in_bash():
    # A composite action must name the shell, and bash is the one Linux and Windows runners share.
    lines = _lines(_ACTION)
    steps = [[line, *_block(lines, index)] for index, line in enumerate(lines) if re.match(r"^\s+- name:", line)]
    scripted = [step for step in steps if any(re.match(r"^\s+run:", line) for line in step)]
    assert scripted
    assert all(any(re.match(r"^\s+shell:\s*bash\s*$", line) for line in step) for step in scripted)


def test_every_input_reaches_a_step():
    text = _ACTION.read_text(encoding="utf-8")
    assert [name for name in _action_inputs() if f"inputs.{name} " not in text] == []


def test_reports_are_uploaded_only_when_a_report_base_is_given():
    lines = _lines(_ACTION)
    start = next(i for i, line in enumerate(lines) if "actions/upload-artifact@" in line)
    step = "\n".join(lines[start - 2:start + 5])
    assert re.search(r"if:.*always\(\).*inputs\.report != ''", step)
    assert "path: ${{ inputs.report }}*" in step


def test_action_names_only_cli_flags_that_exist():
    text = "\n".join(line for line in _lines(_ACTION) if "pip install" not in line)
    # Long options only: the single-letter ones in the scripts belong to bash and python.
    flags = {flag for flag in _FLAG.findall(text) if flag.startswith("--")}
    assert {"--execute_dir", "--report", "--report-format", "--shard", "--parallel", "--parallel-mode",
            "--tag", "--exclude-tag", "--fail-fast"} <= flags
    assert sorted(flags - _cli_flags()) == []


# ---------- docker/Runner.Containerfile ----------------------------------

def _instructions() -> list[tuple[str, str]]:
    """``(INSTRUCTION, arguments)`` of the Containerfile, continuation lines joined, comments dropped."""
    text = re.sub(r"\\\n", " ", "\n".join(line for line in _lines(_CONTAINERFILE) if not line.startswith("#")))
    return [(match.group(1), match.group(2).strip())
            for match in re.finditer(r"^([A-Z]+)\s+(.*)$", text, re.MULTILINE)]


def _values(instruction: str) -> list[str]:
    return [arguments for name, arguments in _instructions() if name == instruction]


def test_containerfile_runs_as_a_non_root_user():
    users = _values("USER")
    assert users
    assert users[-1].split(":")[0] not in {"root", "0"}
    assert re.fullmatch(r"[1-9]\d*(:[1-9]\d*)?", users[-1])


def test_containerfile_downloads_nothing_with_add_and_holds_no_secret():
    assert [value for value in _values("ADD") if re.search(r"https?://", value)] == []
    settings = " ".join(_values("ENV") + _values("ARG"))
    assert not re.search(r"(TOKEN|PASSWORD|SECRET|API_KEY)", settings, re.IGNORECASE)


def test_containerfile_pins_its_base_image():
    bases = [value.split()[0] for value in _values("FROM")]
    assert bases
    unpinned = [base for base in bases
                if base != "scratch" and "@sha256:" not in base
                and not re.search(r":\d+\.\d+[\w.-]*$", base)]
    assert unpinned == []


def test_containerfile_installs_the_stable_package_by_default_and_starts_the_cli():
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    name = re.search(r'^name\s*=\s*"([^"]+)"', pyproject, re.MULTILINE).group(1)
    assert f"WEBRUNNER_PACKAGE={name}" in _values("ARG")
    script = re.search(r'^\[project\.scripts\]\n((?:.+\n)+)', pyproject, re.MULTILINE).group(1)
    entrypoint = _values("ENTRYPOINT")[-1]
    assert re.fullmatch(r'\["(\w+)"\]', entrypoint)
    assert re.search(rf"^{entrypoint[2:-2]}\s*=", script, re.MULTILINE)
    assert _values("WORKDIR")[-1] == "/work"


def test_containerfile_names_only_cli_flags_that_exist():
    # The usage lines in the header: what follows the image name is given to the CLI.
    usage = [match.group(1) for match in
             (re.search(r"webrunner(?:-runner)?(?::\S+)?\s+(-.*)$", line)
              for line in _lines(_CONTAINERFILE) if line.startswith("#")) if match]
    flags = {flag for line in usage for flag in _FLAG.findall(line)}
    assert {"-d", "--report", "--shard"} <= flags
    assert sorted(flags - _cli_flags()) == []


def test_runner_image_constant_is_the_image_the_containerfile_documents():
    repository = RUNNER_IMAGE.rsplit(":", 1)[0]
    assert repository.rsplit("/", 1)[-1] in _CONTAINERFILE.read_text(encoding="utf-8")
    assert repository == repository.lower() and repository.startswith("ghcr.io/")


# ---------- examples/ci --------------------------------------------------

def test_example_refers_to_the_action_in_one_way():
    assert _EXAMPLES
    own = {ref for path in _EXAMPLES for ref, _rest in _uses(path) if _OWN_ACTION.match(ref)}
    assert len(own) == 1


@pytest.mark.parametrize("path", _EXAMPLES, ids=lambda p: p.name)
def test_example_pins_the_other_actions_and_passes_known_inputs(path):
    others = [(ref, rest) for ref, rest in _uses(path) if not _OWN_ACTION.match(ref)]
    assert [ref for ref, rest in others if not (_PINNED.match(ref) and _VERSION_COMMENT.match(rest))] == []
    lines = _lines(path)
    start = next(i for i, line in enumerate(lines) if _USES.match(line) and _OWN_ACTION.match(_USES.match(line)[1]))
    given = _children(_block(lines, start + 1))
    assert given and set(given) <= set(_action_inputs())


@pytest.mark.parametrize("path", _EXAMPLES, ids=lambda p: p.name)
def test_example_runs_shards_and_merges_their_reports(path):
    text = path.read_text(encoding="utf-8")
    shards = re.search(r"^\s+shard:\s*\[([\d, ]+)\]", text, re.MULTILINE).group(1).replace(" ", "").split(",")
    merge = re.search(r"webrunner --merge-reports (\S+)((?: \S+)+)$", text, re.MULTILINE)
    assert merge.group(2).split() == [f"reports/shard-{shard}" for shard in shards]
    assert "--merge-reports" in _cli_flags()
    assert re.search(r"^\s+needs:\s*run\s*$", text, re.MULTILINE)
