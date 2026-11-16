CLI Usage
=========

Overview
--------

WebRunner can be executed directly from the command line using the ``je_web_runner`` module.
Installing the package also installs the console scripts ``webrunner`` and
``web_runner``, which take the same flags and give the same output and exit
codes, so ``webrunner -e actions.json`` equals ``python -m je_web_runner -e
actions.json`` (``pipx run --spec je_web_runner webrunner`` works too).

Commands
--------

**Execute a single JSON action file:**

.. code-block:: bash

    python -m je_web_runner -e actions.json
    python -m je_web_runner --execute_file actions.json

**Execute all JSON files in a directory:**

.. code-block:: bash

    python -m je_web_runner -d ./actions/
    python -m je_web_runner --execute_dir ./actions/

**Execute a JSON action string directly:**

.. code-block:: bash

    python -m je_web_runner --execute_str '[["WR_get_webdriver_manager", {"webdriver_name": "chrome"}], ["WR_quit"]]'

Command Reference
-----------------

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Flag
     - Short
     - Description
   * - ``--execute_file``
     - ``-e``
     - Execute a single JSON action file
   * - ``--execute_dir``
     - ``-d``
     - Execute all JSON files in a directory
   * - ``--execute_str``
     -
     - Execute a JSON action string directly

JSON File Format
----------------

The JSON file should contain an array of action lists:

.. code-block:: json

    [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"]
    ]

.. note::

   On Windows, the ``--execute_str`` option may require double JSON parsing
   due to shell escaping. WebRunner handles this automatically.

Error Handling
--------------

If no arguments are provided, WebRunner raises a ``WebRunnerExecuteException``.
All errors are printed to stderr and the process exits with code 1.

A failed action does not stop its list: the remaining actions run, and so do the remaining files of
``-d``. Once everything has run, the process exits with code 1 and prints
``error: N action(s) or file(s) failed`` when anything failed, and with code 0 otherwise.

Run Settings
------------

``--var NAME=VALUE`` sets a variable the action files read as ``${NAME}``; it is
repeatable, and ``VALUE`` is read as JSON when it parses as JSON (``3``, ``true``,
``[1, 2]``), else it is the text. ``--env NAME`` loads ``.env.NAME`` (from
``--env-dir``, default the working directory) before the run, for ``${ENV.KEY}``.

``--dataset FILE`` (a ``.csv`` or ``.json`` file, anywhere) makes every file that
has no ``meta.dataset`` of its own run once per row, reading the row as
``${ROW.column}``.

``--locators FILE`` (repeatable) loads a locator file before the run: a JSON object of
``name: {"by": ..., "value": ...}``. Action files then find those elements by name with
the recorded-name commands of either backend. ``WR_load_locators`` does the same from
inside an action file.

``--fail-fast`` skips the actions of a file after its first failed one
(``meta.teardown`` still runs), and in a ``-d`` run does not start the files after
the first failed one; the number of files left out goes to stderr. In the thread
and process pools the files already running finish, and the ones not started are
left out. ``--parallel-mode async`` runs every file.

Files that declare ``meta.depends_on`` run in dependency order. With ``--parallel``
above 1 (or ``--parallel-mode async``) they run level by level: every file of a
level depends only on files of earlier levels, and a level is one batch for the
pool. A file whose dependency failed is skipped and counts as failed.

Project Configuration
---------------------

Defaults for a run can live in ``webrunner.toml``, or in the ``[tool.webrunner]``
table of ``pyproject.toml``, in the working directory. A flag wins over the file,
the file over the built-in default; without a file nothing changes.
``--config FILE`` names another file and ``--no-config`` reads none.

.. code-block:: toml

    # webrunner.toml (in pyproject.toml the same keys go under [tool.webrunner])
    env = "staging"                 # load .env.staging before the run
    fail_fast = true
    retries = 1
    retry_backoff = 0.5
    failure_screenshot_dir = "artifacts/failures"
    report = "reports/run"
    ledger = ".webrunner/ledger.json"
    parallel = 4
    parallel_mode = "process"
    exclude_tag = ["sub-flow"]

    [vars]
    base = "${ENV.BASE_URL}"
    user = "alice"

``vars`` become variables (``--var`` wins for the same name). ``locators`` is a list
of locator files loaded before the run (``--locators`` adds to it). ``report``,
``ledger``, ``parallel``, ``parallel_mode``, ``tag`` and ``exclude_tag`` replace
the defaults of the flags of the same name. ``env``, ``env_dir``, ``fail_fast``,
``retries``, ``retry_backoff`` and ``failure_screenshot_dir`` set the executor up
before the first action, in every worker of ``--parallel-mode process`` too. An
unknown key or a value of the wrong type raises ``ProjectConfigError`` before
anything runs. A ``pyproject.toml`` without the table, or one that cannot be
parsed, is not a configuration and is ignored.

Tools
-----

These flags run no action file and can be combined with the others:

* ``--lint PATH`` lints one action file, or every ``.json`` file below a
  directory, and prints ``path: severity [rule] location: message``. A warning
  exits 1; information does not.
* ``--list-commands`` prints every registered ``WR_*`` command, one per line.
* ``--init DIR`` writes the starter workspace of ``utils/bootstrapper`` into
  ``DIR``; existing files are kept.
* ``--format PATH`` rewrites one action file, or every ``.json`` file below a
  directory, in the canonical layout and prints the files it changed. With
  ``--format-check`` nothing is written and a file that would change exits 1.
* ``--export-schema FILE`` writes the JSON schema of action files;
  ``--export-command-reference FILE`` writes the Markdown table of every
  ``WR_*`` command. Both reflect the commands registered in this installation.

Reports
-------

``--report BASE`` writes the JSON, HTML, XML and JUnit reports after the run. They are built from the
test records, so the flag turns recording on before anything runs, in the workers of
``--parallel-mode process`` too; an action file does not need ``WR_set_record_enable``.

``--report-format LIST`` chooses which reports are written: ``json``, ``html``, ``xml``,
``junit`` (these four when the flag is absent), ``allure`` (result files in
``BASE_allure/``) and ``interactive`` (``BASE_interactive.html``).

The JUnit report has one ``<testsuite>`` per action file, named after the file. A step's
``time`` is the time since the step before it in the same file and a suite's ``time`` its
last step minus its first, both from the records' timestamps. Steps recorded outside any
file (``--execute_str``) are one suite called ``webrunner`` with time 0.

``--merge-reports OUT BASE [BASE ...]`` merges the ``_success.json``, ``_failure.json`` and
``_junit.xml`` reports of the given base names, for example one per ``--shard``, into the
same three files under ``OUT``. JSON entries are renumbered in input order; a JUnit suite
name that repeats gets the input's name appended.

Running Under TestPioneer
-------------------------

TestPioneer starts a runner with ``TEST_PIONEER_ARTIFACT_DIR`` set to the directory that run's
output belongs in. A report asked for under a relative name (JSON, XML, HTML, JUnit, Allure,
interactive HTML, and ``generate_all_reports``) is then written below that directory, and the
folders it needs are created. An absolute name, and a name that would leave the directory, are
used as given. Without the variable nothing changes.

Local agent tasks
-----------------

``--agent-task task.json --report results/task`` runs a verified local task.
See :doc:`../integrations/local_agent_doc`.
