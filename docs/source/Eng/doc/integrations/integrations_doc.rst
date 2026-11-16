============
Integrations
============

Recorder
========

JS-injection recorder (no CDP, cross-browser): captures clicks, typed
values, ``<select>`` choices, checkbox and radio changes, presses of named
keys and address changes, and emits a ``WR_*`` action JSON draft with the
current command names (``WR_element_click``, ``WR_element_input``,
``WR_press_keys``, ``WR_to_url`` …). ``backend="playwright"`` (the default
of ``WR_pw_recorder_save``) writes ``WR_pw_*`` commands instead. Sensitive
fields (``type=password``, names matching password / card / cvv / ssn /
secret / token / api_key / otp / passcode, 13–19-digit values), passwords
and sensitive parameters in URLs, and typed characters other than named
keys are masked by default. The buffer lives in the page, so after a
navigation to a new document the events must be pulled and the recorder
started again.

CI / integrations
=================

* **GitHub Actions annotations** — ``emit_failure_annotations`` /
  ``emit_from_junit_xml`` produce ``::error file=…::`` lines.
* **JIRA** — ``jira_create_failure_issues`` for post-run sync.
* **Slack / generic webhook** — ``notify_run_summary``.
* **Selenium Grid 4 docker-compose** — ``docker/docker-compose.yml`` ships
  hub + Chrome + Firefox nodes.
* **IDE configs** — ``docs/ide/vscode-settings.example.json`` and
  ``docs/ide/jetbrains-jsonschemamapping.example.xml`` wire the action JSON
  schema into VS Code / JetBrains.

Desktop control (AutoControl)
=============================

``pip install je_web_runner[autocontrol]`` adds AutoControl
(``je_auto_control``), which drives the real mouse, keyboard and screen.
WebRunner imports it only when one of these commands runs:

* ``WR_ac_available``: whether ``je_auto_control`` is installed (looked up,
  not imported);
* ``WR_ac_list_commands``: the ``AC_*`` commands the bridge will run;
* ``WR_ac_run``: run one AutoControl action and return its value, for
  example ``["WR_ac_run", [["AC_write", {"write_string": "hello"}]]]``;
* ``WR_ac_run_actions``: run a list of AutoControl actions in order and
  return their values; the first failure stops it;
* ``WR_ac_fill_native_file_dialog(file_path, submit=True, wait_seconds=1)``:
  type the path (made absolute) into the operating system's open or save
  dialog, then press Enter unless ``submit`` is false;
* ``WR_ac_assert_image_on_screen(image_path, detect_threshold=None)``: fail
  unless the template image is on the screen; returns its centre ``[x, y]``;
* ``WR_ac_click_element_native(selector=None, by="css selector",
  mouse_button="mouse_left", scale=None)``: click the element (the current
  one without ``selector``) with the real mouse, a trusted click rather than
  WebDriver's. The element is scrolled to the middle of the viewport and its
  centre mapped to the screen from the window's ``screenX/Y``, outer and
  inner size and ``devicePixelRatio``; without ``scale`` the display scale is
  ``devicePixelRatio``, right at 100 % page zoom. The window must not be
  covered;
* ``WR_ac_basic_auth(username_env, password_env, url=None, submit=True,
  wait_seconds=1)``: answer the browser's HTTP basic-auth dialog with the
  credentials in two environment variables (their names, never the values).
  With ``url`` it checks that the page has the keyboard focus (AutoControl
  types into whichever window is in front) and starts opening that page
  without waiting, because a classic ``get`` of a page behind basic auth
  waits while the dialog is open;
  then it types the username, Tab, the password and Enter through
  AutoControl's ``AC_write_secret``, which types them exactly and keeps them
  out of its log, record and return value. It needs a ``je_auto_control``
  with ``AC_write_secret``; for Playwright use ``http_credentials`` in
  ``WR_pw_set_context_options``.

The native commands refuse a Selenium driver whose window is not on
this machine's screen: a headless browser, or a remote one (a grid or a
device cloud). A Playwright browser is not checked, because Playwright does
not report whether it was launched headless: launch it with
``headless=False``.

A failed AutoControl action fails its ``WR_ac_*`` action with
``AutoControlBridgeError``. The bridge refuses shell commands and programs
(``AC_shell_command``, ``AC_execute_process``), package loading
(``AC_add_package_*``), action lists and files (``AC_execute_action``,
``AC_execute_files``), ``AC_run_agent`` and calls back into WebRunner
(``AC_web_*``), anywhere in the action, including loop bodies and bodies
passed as JSON strings. The MCP server refuses every
``WR_ac_*`` command but ``WR_ac_available`` and ``WR_ac_list_commands``
unless ``WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS=1``.

AI assistance
=============

WebRunner ships **no built-in LLM client**. ``set_llm_callable(fn)``
registers any ``Callable[[str], str]`` and powers:

* ``suggest_locator(html, description)`` — last-resort locator suggestion.
* ``llm_self_heal_locator(name, html_provider)`` — pluggable hook for the
  self-healing locator flow.
* ``generate_actions_from_prompt(request)`` — natural language → action
  JSON draft.
* ``explain_failure(test_name, error_repr, console=, network=, steps=)``
  — produces a JSON RCA: ``{likely_cause, evidence, next_steps,
  confidence}``.

MCP server
==========

WebRunner ships a Model Context Protocol server so MCP-aware clients can
drive it over JSON-RPC stdio:

.. code-block:: shell

   python -m je_web_runner.mcp_server

Default tools registered (19 in total):

* Action authoring & lint: ``webrunner_lint_action``,
  ``webrunner_score_action_locators``, ``webrunner_locator_strength``,
  ``webrunner_format_actions``, ``webrunner_parse_markdown``,
  ``webrunner_render_template``,
  ``webrunner_translate_actions_to_playwright``,
  ``webrunner_translate_python_to_playwright``
* Code generation: ``webrunner_pom_from_html``
* Quality & triage: ``webrunner_a11y_diff``,
  ``webrunner_cluster_failures``, ``webrunner_compute_trend``
* Security: ``webrunner_scan_pii``, ``webrunner_redact_pii``
* Reporting & contract: ``webrunner_summary_markdown``,
  ``webrunner_validate_response``
* Sharding / infra: ``webrunner_diff_shard``,
  ``webrunner_render_k8s``, ``webrunner_partition_shard``

Custom tools register via ``McpServer.register(Tool(...))``; the server
speaks the stateless MCP ``2026-07-28`` (``server/discover`` /
``tools/list`` / ``tools/call``) and the handshake revisions ``2025-11-25``
down to ``2024-11-05`` (``initialize`` / ``notifications/initialized`` /
``tools/list`` / ``tools/call`` / ``ping``).

Action JSON LSP
===============

.. code-block:: shell

   python -m je_web_runner.action_lsp

Standard LSP 3.17-shaped server over stdio, also installed as the console
script ``webrunner-lsp``. A document is a list of actions or an object whose
``webdriver_wrapper`` holds one. Notifications the server does not know are
ignored.

* ``textDocument/completion`` depends on the cursor: command names in the
  first element of an action, the command's parameter names in its arguments
  object (those not written yet), variable names after an open ``${``
  (variables any action of the document defines, and ``meta.vars``). Actions
  inside blocks work like top-level ones. A request without a position still
  returns every command name.
* ``textDocument/hover`` on a command name returns its signature and docstring.
* ``textDocument/didOpen`` / ``didChange`` push ``publishDiagnostics`` from
  :func:`linter.action_linter.lint_action`. A finding sits on the line of the
  action or argument it is about, nested ones included, and carries the rule
  as ``code``; ``didClose`` clears them.
* ``textDocument/codeAction`` offers a quick fix for a ``legacy_name`` finding
  whose command has exactly one modern alias.
* ``textDocument/formatting`` returns one edit with the formatter's canonical
  layout for a list-form document; an object document or invalid JSON gets no
  edit.
* Messages are read and written as UTF-8 bytes through the streams' buffers,
  so ``Content-Length`` stays right with non-ASCII text on any console encoding.


Native basic-auth navigation requires HTTPS. Plain HTTP is allowed only for localhost or a literal loopback address used by local test servers. URLs with embedded credentials are refused before navigation or typing.
