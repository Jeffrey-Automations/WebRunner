Action Executor
===============

Overview
--------

The Action Executor is a powerful engine that maps command strings to callable functions.
It allows you to define automation scripts as JSON action lists, enabling data-driven automation workflows.

The executor also registers an allowlist of Python built-in functions (``SAFE_BUILTINS``: ``print``, ``len``, ``sorted``, ``sum`` …), so you can call them from action lists; ``eval``, ``exec``, ``open`` and the like are not registered.

Action Format
-------------

Each action is a list with the command name and optional parameters:

.. code-block:: python

    ["command_name"]                        # No parameters
    ["command_name", {"key": "value"}]      # Keyword arguments
    ["command_name", [arg1, arg2]]          # Positional arguments

Basic Usage
-----------

.. code-block:: python

    from je_web_runner import execute_action

    actions = [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://www.google.com"}],
        ["WR_implicitly_wait", {"time_to_wait": 2}],
        ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
        ["WR_find_element", {"element_name": "q"}],
        ["WR_click_element"],
        ["WR_input_to_element", {"input_value": "WebRunner"}],
        ["WR_quit"]
    ]

    result = execute_action(actions)

The ``execute_action()`` function returns a dict mapping each action
(``"execute: <action>"``) to its return value. A repeated identical action
gets ``#2``, ``#3`` … appended to its key, so every step's outcome is kept.

A failed action is recorded in that dict and the next one runs. To run one action and
get its value back instead, use ``execute_one``: it goes through the same command gates,
retry policy and failure screenshots, prints nothing, and raises
``WebRunnerExecuteException`` (the original error is its ``__cause__``) when the action
fails:

.. code-block:: python

    from je_web_runner import execute_one

    url = execute_one(["WR_get_current_url"])

A failed Selenium wrapper call (``WR_to_url``, ``WR_element_click``,
``WR_element_assert`` …) is recorded and then fails its action, as the
Playwright commands do. ``executor.set_raise_wrapper_errors(False)`` (or
``WR_set_raise_wrapper_errors`` with ``[false]`` first in an action file) lets it
pass again, the behaviour before the default changed.

Available Commands
------------------

**WebDriver Manager:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_get_webdriver_manager``
     - Create a new WebDriver (params: ``webdriver_name``, ``options``)
   * - ``WR_change_index_of_webdriver``
     - Switch to a WebDriver by index
   * - ``WR_quit``
     - Quit all WebDrivers
   * - ``WR_single_quit``
     - Quit the current single WebDriver

**Navigation:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_to_url``
     - Navigate to URL (param: ``url``)
   * - ``WR_forward``
     - Go forward
   * - ``WR_back``
     - Go back
   * - ``WR_refresh``
     - Refresh the page

**Element Finding:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_find_element``
     - Find single element by saved test object name (param: ``element_name``)
   * - ``WR_find_elements``
     - Find multiple elements by saved test object name

**Wait:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_implicitly_wait``
     - Set implicit wait (param: ``time_to_wait``)
   * - ``WR_explict_wait``
     - Explicit wait with condition
   * - ``WR_set_script_timeout``
     - Set script timeout
   * - ``WR_set_page_load_timeout``
     - Set page load timeout

**Mouse Actions:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_left_click``
     - Left click (on saved test object or current position)
   * - ``WR_right_click``
     - Right click
   * - ``WR_left_double_click``
     - Double click
   * - ``WR_left_click_and_hold``
     - Click and hold
   * - ``WR_release``
     - Release held button
   * - ``WR_drag_and_drop``
     - Drag from source to target (test object names)
   * - ``WR_drag_and_drop_offset``
     - Drag to offset
   * - ``WR_move_to_element``
     - Hover over element (test object name)
   * - ``WR_move_to_element_with_offset``
     - Hover with offset
   * - ``WR_move_by_offset``
     - Move mouse by offset

**Keyboard:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_press_key``
     - Press a key
   * - ``WR_release_key``
     - Release a key
   * - ``WR_send_keys``
     - Send keys globally
   * - ``WR_send_keys_to_element``
     - Send keys to saved test object

**Action Chain:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_perform``
     - Execute queued actions
   * - ``WR_reset_actions``
     - Clear action queue
   * - ``WR_pause``
     - Pause in chain
   * - ``WR_scroll``
     - Scroll page

**Cookies:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_get_cookies``
     - Get all cookies
   * - ``WR_get_cookie``
     - Get a specific cookie
   * - ``WR_add_cookie``
     - Add a cookie
   * - ``WR_delete_cookie``
     - Delete a cookie
   * - ``WR_delete_all_cookies``
     - Delete all cookies

**JavaScript:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_execute``
     - Execute JavaScript
   * - ``WR_execute_script``
     - Execute script
   * - ``WR_execute_async_script``
     - Execute async script

**Window:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_maximize_window``
     - Maximize window
   * - ``WR_minimize_window``
     - Minimize window
   * - ``WR_fullscreen_window``
     - Full screen
   * - ``WR_set_window_size``
     - Set window size
   * - ``WR_set_window_position``
     - Set window position
   * - ``WR_get_window_position``
     - Get window position
   * - ``WR_get_window_rect``
     - Get window rect
   * - ``WR_set_window_rect``
     - Set window rect

**Screenshot & Logging:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_get_screenshot_as_png``
     - Get screenshot as PNG bytes
   * - ``WR_get_screenshot_as_base64``
     - Get screenshot as base64
   * - ``WR_get_log``
     - Get browser logs

**Element Interaction:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_click_element``
     - Click the current element
   * - ``WR_input_to_element``
     - Type text into element
   * - ``WR_element_clear``
     - Clear element content
   * - ``WR_element_submit``
     - Submit form
   * - ``WR_element_get_attribute``
     - Get element attribute
   * - ``WR_element_get_property``
     - Get element property
   * - ``WR_element_get_dom_attribute``
     - Get DOM attribute
   * - ``WR_element_is_displayed``
     - Check if element is visible
   * - ``WR_element_is_enabled``
     - Check if element is enabled
   * - ``WR_element_is_selected``
     - Check if element is selected
   * - ``WR_element_value_of_css_property``
     - Get CSS property
   * - ``WR_element_screenshot``
     - Take element screenshot
   * - ``WR_element_change_web_element``
     - Switch active element
   * - ``WR_element_check_current_web_element``
     - Validate element properties
   * - ``WR_element_get_select``
     - Get Select for dropdown

**Test Object:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_SaveTestObject``
     - Save a test object (params: ``test_object_name``, ``object_type``)
   * - ``WR_CleanTestObject``
     - Clear all saved test objects

**Report:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_generate_html``
     - Generate HTML report string
   * - ``WR_generate_html_report``
     - Save HTML report to file
   * - ``WR_generate_json``
     - Generate JSON report dicts
   * - ``WR_generate_json_report``
     - Save JSON report to file
   * - ``WR_generate_xml``
     - Generate XML report
   * - ``WR_generate_xml_report``
     - Save XML report to file

**Other:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_switch``
     - Switch context (frame, window, alert)
   * - ``WR_check_current_webdriver``
     - Validate WebDriver properties
   * - ``WR_set_record_enable``
     - Enable/disable test recording
   * - ``WR_execute_action``
     - Nested execute action list
   * - ``WR_execute_files``
     - Execute from JSON files
   * - ``WR_add_package_to_executor``
     - Add a Python package to executor
   * - ``WR_add_package_to_callback_executor``
     - Add a Python package to callback executor

Execute from JSON Files
-----------------------

.. code-block:: python

    from je_web_runner import execute_files

    # Execute actions from multiple JSON files
    results = execute_files(["actions1.json", "actions2.json"])

JSON file format:

.. code-block:: json

    [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"]
    ]

Dict Format Input
-----------------

The executor also accepts a dict with a ``"webdriver_wrapper"`` key:

.. code-block:: python

    execute_action({
        "webdriver_wrapper": [
            ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
            ["WR_quit"]
        ]
    })

Add Custom Commands
-------------------

Register your own functions as executor commands:

.. code-block:: python

    from je_web_runner import add_command_to_executor

    def my_custom_function(param1, param2):
        print(f"Custom: {param1}, {param2}")

    add_command_to_executor({"my_command": my_custom_function})

    # Now use it in action lists
    execute_action([
        ["my_command", {"param1": "hello", "param2": "world"}]
    ])

.. note::

   Only ``types.MethodType`` and ``types.FunctionType`` are accepted.
   Passing other callable types will raise ``WebRunnerAddCommandException``.

Variables
---------

An action can store a value and later actions can use it. The executor replaces
``${name}`` in the arguments of an action just before the command is called.

.. code-block:: python

    [
        ["WR_set_var", {"name": "base", "value": "${ENV.BASE_URL}"}],
        ["WR_to_url", {"url": "${base}/login"}],
        ["WR_capture", {"name": "title", "action": ["WR_get_title"]}],
        ["WR_assert_title", {"value": "${title}"}],
    ]

* ``WR_set_var`` (``name``, ``value``) stores a value. ``WR_capture`` (``name``,
  ``action``) runs one action and stores what it returned; when that action
  fails, ``WR_capture`` fails and the variable is left as it was.
  ``WR_get_var`` (``name``, ``default``), ``WR_unset_var``, ``WR_clear_vars``
  and ``WR_list_vars`` (names only) read and remove them.
* ``${name}`` reads a variable, ``${name.key.0}`` a key of a dict or an index
  of a list, ``${ENV.KEY}`` an environment variable. ``ENV`` and ``ROW`` cannot
  be variable names.
* An argument that is exactly one placeholder gets the value with its type;
  inside a longer string the value is inserted as text.
* A placeholder that names nothing known is left as it is, so ``${ROW.col}``
  of a dataset and a JavaScript template literal in a script argument still
  work. A known variable with a path that does not exist fails the action.
* The command name is never replaced, so a variable cannot choose a command the
  gates refuse. The record of an action shows it as written, not the expanded
  values; the values a Selenium wrapper call records are the expanded ones.
* ``WR_execute_action``, ``WR_run_with_dataset`` and ``WR_capture`` hold actions
  to run later: their placeholders are expanded when each nested action runs.
* Variables belong to the executor (``executor.variables``, a
  ``je_web_runner.utils.flow.VariableStore``) and stay until ``WR_clear_vars``.
  In a directory run, later files see the variables of earlier ones;
  ``--parallel-mode process`` gives each worker its own.

Control Flow
------------

Blocks decide which actions run. Their actions are ordinary actions, so blocks
nest.

.. code-block:: python

    [
        ["WR_for_each", {"items": ["/", "/pricing", "/docs"], "var": "path", "do": [
            ["WR_to_url", {"url": "${base}${path}"}],
            ["WR_if", {
                "condition": {"succeeds": ["WR_wait_for_element", {"selector": "#cookie-banner", "timeout": 2}]},
                "then": [["WR_dismiss_cookie_consent"]],
            }],
        ]}],
        ["WR_try", {
            "do": [["WR_retry_block", {"retries": 2, "backoff": 1, "do": [
                ["WR_refresh"],
                ["WR_wait_for_title", {"pattern": "Dashboard", "timeout": 5}],
            ]}]],
            "on_error": [["WR_save_screenshot", {"file_path": "dashboard_never_loaded.png"}], ["WR_fail", {"message": "${error}"}]],
            "always": [["WR_quit_all"]],
        }],
    ]

* ``WR_if`` (``condition``, ``then``, ``otherwise``) runs ``then`` when the
  condition holds and ``otherwise`` when it does not.
* ``WR_for_each`` (``items``, ``do``, ``var``, ``index_var``) runs ``do`` once per
  element of a list (or of a ``${name}`` that holds one). The element is the
  variable ``var`` (``item`` by default) and its position from 0 is
  ``index_var``; both end with the loop.
* ``WR_repeat`` (``times``, ``do``, ``index_var``) runs ``do`` a fixed number of
  times.
* ``WR_while`` (``condition``, ``do``, ``max_iterations``) runs ``do`` while the
  condition holds. ``max_iterations`` is required; the loop fails when the
  condition still holds after that many rounds.
* ``WR_try`` (``do``, ``on_error``, ``always``): with ``on_error``, a failure in
  ``do`` runs it with the failure text as ``${error}`` and the action passes;
  without it the failure stays a failure. ``always`` runs in every case.
* ``WR_retry_block`` (``do``, ``retries``, ``backoff``) starts the whole block
  again when one of its actions fails, up to ``retries`` more times.
* ``WR_fail`` (``message``) fails. ``WR_assert_var`` (``var``, ``op``, ``value``)
  fails unless the variable satisfies the operator.

A condition is a JSON object, never code:

* ``{"var": "name.path", "op": "eq", "value": 1}`` compares a variable;
  placeholders in ``value`` are expanded. Operators: ``eq``, ``ne``, ``gt``,
  ``ge``, ``lt``, ``le``, ``contains``, ``in``, ``startswith``, ``endswith``,
  ``exists``, ``truthy`` (the default), ``falsy``. A variable that is not set is
  false for ``exists`` and ``truthy``, true for ``falsy`` and an error for the
  comparisons.
* ``{"succeeds": [action]}`` runs one action and is true when it does not fail.
* ``{"all": [...]}``, ``{"any": [...]}`` and ``{"not": ...}`` combine
  conditions; ``all`` and ``any`` stop at the first condition that decides.
* A plain value (``true``, ``"${flag}"``) is itself, after expansion.

The first action that fails stops its block and fails the action that holds the
block, which is recorded once. A failure the list handles on purpose (the action
of a ``succeeds`` condition, a ``WR_try`` with ``on_error``, an attempt that
``WR_retry_block`` or the retry policy repeats) is not a failure of the run: in
the test record its error text moves to ``handled_exception`` and
``program_exception`` is ``"None"``, so reports and ``--rerun-failed`` do not
count it. Every nested action passes the same gates as a
top-level one (refused commands, the arbitrary-script gate, the MCP policy) and
the retry policy, and its placeholders are expanded when it runs, so a loop sees
the values of each round.

Calling Another Action File
---------------------------

``WR_call_file`` (``path``, ``params``) runs the actions of another action file
in place, so a shared flow is written once.

.. code-block:: python

    # flows/login.json
    [
        ["WR_to_url", {"url": "${base}/login"}],
        ["WR_find_element_by", {"selector": "#user"}],
        ["WR_element_input", {"input_value": "${user}"}],
    ]
    
    # flows/checkout.json
    [
        ["WR_call_file", {"path": "login.json", "params": {"base": "${ENV.BASE_URL}", "user": "alice"}}],
        ["WR_to_url", {"url": "${ENV.BASE_URL}/cart"}],
    ]

* ``params`` become variables of the called file and end with the call. The
  caller's other variables are visible too.
* A relative ``path`` starts at the directory of the file making the call.
  ``execute_files``, ``Executor.execute_file`` and the CLI (``-e``, ``-d``) set
  that file; for ``--execute_str``, ``execute_action``, the socket server, the
  MCP tools and ``--parallel-mode async`` there is none and the working
  directory is used.
* The called file must be below the working directory or below the directory
  of the file the run started from; ``..`` cannot reach anything else. A file
  that is already running cannot be called again, and calls nest at most 20
  deep.
* The first action that fails stops the called file and fails the
  ``WR_call_file`` action. ``WR_execute_files`` is the older command: it takes
  no parameters, resolves paths from the working directory, and records a
  failure without failing its own action.

File ``meta``
-------------

An object document carries its actions under ``webdriver_wrapper`` and settings
for its run under ``meta``. ``tags`` and ``depends_on`` are read by the CLI's
file selection; the executor reads the rest.

.. code-block:: json

    {
      "meta": {
        "tags": ["checkout"],
        "vars": {"base": "${ENV.BASE_URL}", "user": "alice"},
        "setup": [["WR_new_driver", {"webdriver_name": "chrome"}]],
        "teardown": [["WR_quit_all"]],
        "retries": 1,
        "fail_fast": true
      },
      "webdriver_wrapper": [
        ["WR_call_file", {"path": "login.json", "params": {"user": "${user}"}}],
        ["WR_to_url", {"url": "${base}/cart"}]
      ]
    }

* ``setup``: actions run before the file's own.
* ``teardown``: actions run after them, also when an earlier action failed and
  under fail-fast.
* ``vars``: default variables. Each is set unless a variable of that name
  already exists; placeholders in the value are expanded. In a file run by
  ``WR_call_file`` they fill the names ``params`` left out and end with the
  call.
* ``skip``: a reason, as text. The file's actions, ``setup`` and ``teardown``
  do not run; one ``WR_note`` action carrying ``skipped: <reason>`` is recorded
  instead. ``true`` without a reason is an error.
* ``retries`` (0 to 100) and ``retry_backoff`` (seconds): the retry policy for
  the actions of this file. The previous policy is restored afterwards.
* ``fail_fast``: ``true`` or ``false`` for this file, whatever the executor's
  setting.
* ``dataset``: a ``.csv`` or ``.json`` file (a relative path starts at the
  action file, and must stay below the working directory or the directory of
  the file the run started from), or the rows themselves as a list of objects.
  The file's own actions run once per row. Before each row the run inserts one
  ``WR_use_row`` action, which makes the row readable as ``${ROW.column}`` and
  its position from 0 as ``${ROW_INDEX}``; ``setup`` and ``teardown`` run once,
  around all rows. A column the row does not have is an error. CSV values are
  text; JSON values keep their type. The CLI's ``--dataset FILE`` gives the
  same to every file that has no ``meta.dataset`` of its own; a file run by
  ``WR_call_file`` uses only its own.

A ``meta`` key of the wrong shape raises ``FlowError`` before any action runs.

Fail-fast
---------

By default a failed action is recorded and the next one runs.
``executor.set_fail_fast(True)``, the action ``["WR_set_fail_fast"]`` (from the
next list on) or ``meta.fail_fast`` changes that: after the first failed action
of a list, the remaining ones are recorded as
``skipped: an earlier action of this list failed (fail-fast)`` and not run,
except the ``teardown`` actions. Skipped actions count as failed in the CLI's
exit status.

It applies to the actions of a list or file. A single ``execute_one`` call is
never skipped, a list run from inside an action (``WR_execute_action``) belongs
to that action, and a ``WR_try`` block that handles its failure does not trip
it. ``--parallel-mode async`` does not use it.
