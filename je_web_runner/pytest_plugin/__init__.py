"""
把 WebRunner 動作檔收集成 pytest 測試
A pytest plugin that collects WebRunner action files (``.json``) as tests, one test per file.

It does nothing until a project opts in, with the ini option ``webrunner_action_paths`` (files or
directories, relative to the rootdir) or ``--webrunner-actions PATH`` (repeatable, relative to the directory
pytest is started from)::

    [tool.pytest.ini_options]
    webrunner_action_paths = ["actions"]

Then every ``.json`` file below those paths that is an action document becomes one test:

* **What counts as an action document**: an object with a ``webdriver_wrapper`` key, or a list that passes
  ``validate_action_json``. Anything else (a dataset, which is a list of objects; a locator file, which is an
  object without ``webdriver_wrapper``) is left alone. An object that has ``webdriver_wrapper`` but is not
  valid is still collected and fails with the validation error, so a broken action file is not lost
  silently. A ``.json`` file that cannot be parsed gives a collection warning.
* **Node id**: ``<path of the file>::<file name without .json>``, e.g. ``actions/login.json::login``.
* **Running**: the file runs through the executor as ``execute_file`` runs it, so ``meta`` (setup, teardown,
  vars, dataset, fail_fast, retries) applies and ``WR_call_file`` resolves from the file; every test has its
  own variables. The test fails when an action failed, and the report lists those actions with their errors.
* **``meta.skip``** skips the test with that reason.
* **``meta.tags``** become markers: the tag itself, with every character other than a letter, a digit or
  ``_`` replaced by ``_`` (``slow-ui`` gives ``slow_ui``), and ``tag`` put in front of a result that is
  empty or starts with ``_``. Every collected file also has the marker ``webrunner``. The markers are
  registered, so ``--strict-markers`` accepts them and ``-m smoke`` selects by tag.
* **``--webrunner-fail-fast``** stops each file at its first failed action (``meta.teardown`` still runs; a
  file's own ``meta.fail_fast`` wins).

The paths are added to what pytest collects when pytest was started without paths of its own (they come
from ``testpaths`` or the current directory); ``--webrunner-actions`` paths are always added. With explicit
paths on the command line, only the action files below those paths are collected.

The hooks live in the top-level module :mod:`je_web_runner_pytest`, which the ``pytest11`` entry point
names. It imports nothing of WebRunner until an action file is found below an opted-in path, so pytest runs
of projects that merely have WebRunner installed do not pay for importing it.
"""
from je_web_runner_pytest import pytest_addoption, pytest_collect_file, pytest_configure

__all__ = ["pytest_addoption", "pytest_collect_file", "pytest_configure"]
