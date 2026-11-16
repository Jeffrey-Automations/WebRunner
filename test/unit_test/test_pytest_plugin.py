"""
Tests of the pytest plugin that collects WebRunner action files (``je_web_runner.pytest_plugin``).

The inner pytest runs that execute action files, and the one that checks what an inert plugin imports, are
subprocesses (``runpytest_subprocess``): the executor is one object per process, and a run inside this
process would leave its records, variables and fail-fast setting in the session that runs these tests.
Runs that only collect stay in process, since collecting reads the files and runs nothing.
"""
import json
import subprocess  # nosec B404 - runs this interpreter on a fixed script
import sys
from pathlib import Path

import pytest

import je_web_runner
from je_web_runner.pytest_plugin.nodes import document_problem, marker_name, tag_markers

pytest_plugins = ["pytester"]

PLUGIN = "je_web_runner.pytest_plugin"
PACKAGE_ROOT = Path(je_web_runner.__file__).resolve().parent.parent
PLUGIN_FILE = PACKAGE_ROOT / "je_web_runner_pytest.py"
BASE_ARGS = ("-p", PLUGIN, "-p", "no:cacheprovider")

PASSING = [
    ["WR_set_var", {"name": "user", "value": "amy"}],
    ["WR_assert_var", {"var": "user", "value": "amy", "op": "eq"}],
]
IMPORT_PROBE = """
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("webrunner_plugin_probe", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
loaded = sorted(name for name in sys.modules if name.split(".")[0] == "je_web_runner")
print("hooks:", hasattr(module, "pytest_collect_file"), "webrunner modules:", loaded)
"""


def write_json(folder: Path, name: str, content) -> Path:
    """Write ``content`` as ``folder/name`` (creating the folder) and return the path."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def document(actions: list, **meta) -> dict:
    """An object document with ``meta``."""
    return {"meta": meta, "webdriver_wrapper": actions}


@pytest.fixture(autouse=True)
def only_the_named_plugin(monkeypatch):
    """
    The runs name the plugin with ``-p``. Where the package is installed (or a build left its metadata in
    the checkout) the entry point would register the same hooks a second time, so entry points are off.
    """
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")


@pytest.fixture
def project(pytester, monkeypatch):
    """A pytester project whose subprocess runs can import this checkout of ``je_web_runner``."""
    monkeypatch.setenv("PYTHONPATH", str(PACKAGE_ROOT))
    pytester.makeini(f"[pytest]\nwebrunner_action_paths = actions\naddopts = -p {PLUGIN} -p no:cacheprovider\n")
    return pytester


def test_plugin_module_itself_imports_nothing_of_webrunner():
    completed = subprocess.run(  # nosec B603 - fixed arguments, no shell
        [sys.executable, "-c", IMPORT_PROBE, str(PLUGIN_FILE)], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "hooks: True webrunner modules: []"


def test_without_opt_in_nothing_is_collected_and_the_nodes_are_not_imported(pytester, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(PACKAGE_ROOT))
    for name in ("a.json", "b.json", "c.json"):
        write_json(pytester.path / "actions", name, PASSING)
    pytester.makepyfile(test_probe="""
        import sys

        def test_plugin_is_loaded_but_inert(pytestconfig):
            assert pytestconfig.pluginmanager.has_plugin("je_web_runner.pytest_plugin")
            assert "je_web_runner.pytest_plugin.nodes" not in sys.modules
    """)
    result = pytester.runpytest_subprocess(*BASE_ARGS, "-v")
    result.assert_outcomes(passed=1)
    assert ".json" not in result.stdout.str()


def test_without_opt_in_a_json_directory_given_as_argument_collects_nothing(pytester):
    write_json(pytester.path / "actions", "a.json", PASSING)
    result = pytester.runpytest(*BASE_ARGS, "--collect-only", "-q", "actions")
    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED
    assert "a.json" not in result.stdout.str()


def collected_ids(result) -> list:
    """The node ids a ``--collect-only -q`` run printed."""
    return [line for line in result.stdout.lines if "::" in line]


def make_mixed_tree(root: Path) -> None:
    """Action files, in an order other than the sorted one, among files that are not action documents."""
    actions = root / "actions"
    write_json(actions / "sub", "c.json", document(PASSING))
    write_json(actions, "b.json", PASSING)
    write_json(actions, "a.json", PASSING)
    write_json(actions, "rows.json", [{"name": "amy"}, {"name": "bob"}])
    write_json(actions, "locators.json", {"login_button": {"by": "id", "value": "login"}})
    write_json(actions, "empty.json", [])
    (actions / "broken.json").write_text("[[\"WR_note\"", encoding="utf-8")
    (actions / "notes.txt").write_text("not json", encoding="utf-8")
    write_json(root / "elsewhere", "z.json", PASSING)


def test_collects_only_action_documents_below_the_ini_paths_in_sorted_order(pytester):
    make_mixed_tree(pytester.path)
    pytester.makeini("[pytest]\nwebrunner_action_paths = actions\n")
    result = pytester.runpytest(*BASE_ARGS, "--collect-only", "-q")
    assert collected_ids(result) == ["actions/a.json::a", "actions/b.json::b", "actions/sub/c.json::c"]
    assert result.ret == pytest.ExitCode.OK
    result.stdout.fnmatch_lines(["*broken.json is not collected, it cannot be read as JSON*"])


def test_ini_paths_are_added_to_testpaths_but_not_to_explicit_arguments(pytester):
    make_mixed_tree(pytester.path)
    (pytester.path / "tests").mkdir()
    pytester.makeini("[pytest]\ntestpaths = tests\nwebrunner_action_paths = actions/sub actions/a.json\n")
    from_testpaths = pytester.runpytest(*BASE_ARGS, "--collect-only", "-q")
    assert collected_ids(from_testpaths) == ["actions/a.json::a", "actions/sub/c.json::c"]
    explicit = pytester.runpytest(*BASE_ARGS, "--collect-only", "-q", "elsewhere")
    assert collected_ids(explicit) == []
    narrowed = pytester.runpytest(*BASE_ARGS, "--collect-only", "-q", "actions")
    assert collected_ids(narrowed) == ["actions/a.json::a", "actions/sub/c.json::c"]


def test_command_line_paths_opt_in_and_are_always_collected(pytester):
    make_mixed_tree(pytester.path)
    (pytester.path / "tests").mkdir()
    result = pytester.runpytest(
        *BASE_ARGS, "--collect-only", "-q", "tests",
        "--webrunner-actions", "elsewhere", "--webrunner-actions", "actions/b.json")
    assert collected_ids(result) == ["actions/b.json::b", "elsewhere/z.json::z"]


def test_a_configured_path_that_does_not_exist_is_a_usage_error(pytester):
    result = pytester.runpytest(*BASE_ARGS, "--webrunner-actions", "missing_dir")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--webrunner-actions: no such file or directory: missing_dir*"])


def test_pass_fail_skip_and_invalid_files_report_readably(project):
    actions = project.path / "actions"
    write_json(actions, "passes.json", document(PASSING, vars={"greeting": "hello"}))
    write_json(actions, "fails.json", [
        ["WR_note", {"text": "before"}],
        ["WR_fail", {"message": "the first problem"}],
        ["WR_assert_var", {"var": "never_set"}],
        ["WR_sleep", {"seconds": 0}],
    ])
    write_json(actions, "skipped.json", document([["WR_fail", {"message": "must not run"}]], skip="waiting for login"))
    write_json(actions, "invalid.json", {"webdriver_wrapper": [["WR_note", "text"]]})
    result = project.runpytest_subprocess("-rs")
    result.assert_outcomes(passed=1, failed=2, skipped=1)
    text = result.stdout.str()
    result.stdout.fnmatch_lines([
        "*webrunner: actions/fails.json*",
        "actions/fails.json: 2 of 4 actions failed",
        "  1. execute: ?'WR_fail', {'message': 'the first problem'}?",
        "     FlowError('the first problem')",
        "  2. execute: ?'WR_assert_var', {'var': 'never_set'}?",
        "     *never_set is not set*",
    ])
    result.stdout.fnmatch_lines(["actions/invalid.json: not a valid action file", "*action #0*"])
    result.stdout.fnmatch_lines(["SKIPPED*waiting for login*"])
    assert "Traceback" not in text
    assert "nodes.py" not in text
    assert "must not run" not in text


def test_tags_become_registered_markers_that_select_files(project):
    actions = project.path / "actions"
    write_json(actions, "smoke_one.json", document(PASSING, tags=["smoke", "slow-ui"]))
    write_json(actions, "smoke_two.json", document(PASSING, tags=["smoke"]))
    write_json(actions, "regression.json", document(PASSING, tags=["regression"]))
    write_json(actions, "untagged.json", PASSING)
    smoke = project.runpytest_subprocess("--strict-markers", "-m", "smoke", "-v")
    smoke.assert_outcomes(passed=2, deselected=2)
    smoke.stdout.fnmatch_lines(["*smoke_one.json::smoke_one PASSED*", "*smoke_two.json::smoke_two PASSED*"])
    renamed = project.runpytest_subprocess("--strict-markers", "-m", "slow_ui or regression")
    renamed.assert_outcomes(passed=2, deselected=2)
    every = project.runpytest_subprocess("--strict-markers", "-m", "webrunner")
    every.assert_outcomes(passed=4)
    listed = project.runpytest_subprocess("--markers")
    listed.stdout.fnmatch_lines(["*@pytest.mark.webrunner: a WebRunner action file collected as a test*"])


def test_dataset_rows_setup_and_variables_of_each_file(project):
    actions = project.path / "actions"
    write_json(actions, "a_sets.json", [["WR_set_var", {"name": "leak", "value": "from a_sets"}]])
    write_json(actions, "b_after.json", [["WR_assert_var", {"var": "leak", "op": "falsy"}]])
    write_json(actions, "c_rows.json", document(
        [["WR_fail", {"message": "row ${ROW.name}"}]], dataset=[{"name": "amy"}, {"name": "bob"}]))
    write_json(actions, "d_setup.json", document(
        [["WR_assert_var", {"var": "ready", "op": "eq", "value": "yes"}]],
        setup=[["WR_set_var", {"name": "ready", "value": "${state}"}]], vars={"state": "yes"}))
    result = project.runpytest_subprocess("-v")
    result.stdout.fnmatch_lines([
        "*a_sets.json::a_sets PASSED*",
        "*b_after.json::b_after PASSED*",
        "*c_rows.json::c_rows FAILED*",
        "*d_setup.json::d_setup PASSED*",
    ])
    result.stdout.fnmatch_lines(["actions/c_rows.json: 2 of 4 actions failed", "*FlowError('row amy')*",
                                 "*FlowError('row bob')*"])
    result.assert_outcomes(passed=3, failed=1)


def test_call_file_passes_parameters_to_the_called_file(project):
    actions = project.path / "actions"
    write_json(actions, "caller.json", [["WR_call_file", {"path": "greet.json", "params": {"who": "amy"}}]])
    write_json(actions, "greet.json", document(
        [["WR_assert_var", {"var": "who", "op": "eq", "value": "amy"}]], vars={"who": "nobody"}))
    result = project.runpytest_subprocess("-v")
    result.stdout.fnmatch_lines(["*caller.json::caller PASSED*", "*greet.json::greet FAILED*"])
    result.stdout.fnmatch_lines(["actions/greet.json: 1 of 1 actions failed", "*who is 'nobody'*"])


def test_fail_fast_option_stops_a_file_at_its_first_failure(project):
    actions = project.path / "actions"
    steps = [["WR_fail", {"message": "first"}], ["WR_fail", {"message": "second"}]]
    write_json(actions, "plain.json", steps)
    write_json(actions, "keeps_going.json", document(steps, fail_fast=False))
    write_json(actions, "with_teardown.json", document(steps, teardown=[["WR_fail", {"message": "teardown ran"}]]))
    default = project.runpytest_subprocess("actions/plain.json")
    default.stdout.fnmatch_lines(["actions/plain.json: 2 of 2 actions failed", "*FlowError('second')*"])
    result = project.runpytest_subprocess("--webrunner-fail-fast")
    result.assert_outcomes(failed=3)
    text = result.stdout.str()
    plain = text[text.index("actions/plain.json: 2 of 2 actions failed"):]
    assert "skipped: an earlier action of this list failed (fail-fast)" in plain
    assert "FlowError('second')" not in plain.split("actions/with_teardown.json:")[0]
    result.stdout.fnmatch_lines(["actions/keeps_going.json: 2 of 2 actions failed", "*FlowError('second')*"])
    result.stdout.fnmatch_lines(["actions/with_teardown.json: 3 of 3 actions failed", "*FlowError('teardown ran')*"])


@pytest.mark.parametrize("tag, expected", [
    ("smoke", "smoke"), ("slow-ui", "slow_ui"), ("team a", "team_a"), ("_private", "tag_private"),
    ("", "tag"), (7, "7"), ("zh標籤", "zh__"),
])
def test_marker_name(tag, expected):
    assert marker_name(tag) == expected


def test_tag_markers_reads_only_a_list_or_one_string():
    assert tag_markers(document(PASSING, tags=["a", "b", "a"])) == ["a", "b"]
    assert tag_markers(document(PASSING, tags="solo")) == ["solo"]
    assert tag_markers(document(PASSING, tags={"a": 1})) == []
    assert tag_markers(PASSING) == []
    assert tag_markers({"meta": "text", "webdriver_wrapper": PASSING}) == []


def test_document_problem_tells_action_documents_from_other_json():
    assert document_problem(PASSING) == (True, None)
    assert document_problem(document(PASSING)) == (True, None)
    assert document_problem([{"name": "amy"}])[0] is False
    assert document_problem({"login": {"by": "id"}})[0] is False
    assert document_problem("text")[0] is False
    claimed, problem = document_problem({"webdriver_wrapper": []})
    assert claimed is True and problem
