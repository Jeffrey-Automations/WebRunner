"""
動作檔語言的簡明指南 / The guide to the action-file language, served as ``webrunner://guide/action-language``.

Written from the behaviour of :mod:`je_web_runner.utils.flow` and the action executor; when either
changes, this text changes with it.
"""
from __future__ import annotations

GUIDE_URI = "webrunner://guide/action-language"

ACTION_LANGUAGE_GUIDE = """# Writing WebRunner action files

An action file is JSON: a list of actions that the executor runs in order against a browser.
Commands are looked up by name; nothing in a file is evaluated as code.

## Actions

```json
["WR_quit_all"]
["WR_to_url", {"url": "https://example.com"}]
["WR_to_url", ["https://example.com"]]
["WR_set_var", ["greeting"], {"value": "hello"}]
```

- `[name]` calls the command without arguments, `[name, {...}]` with keyword arguments,
  `[name, [...]]` with positional ones, `[name, [...], {...}]` with both.
- An action has 1 to 3 entries and its first is the command name, a non-empty string.
- Prefer keyword arguments: they survive a change of parameter order.
- Command names start with `WR_`. `webrunner://commands` lists every command with its signature,
  `webrunner://commands/{name}` gives one command's signature and documentation, and the tool
  `webrunner_list_commands` returns the names. Use only names found there.
- The Selenium commands (`WR_new_driver`, `WR_to_url`, `WR_find_element_by`, `WR_element_input`,
  `WR_element_click`, `WR_quit_all`) and the Playwright ones (`WR_pw_launch`, `WR_pw_to_url`,
  `WR_pw_fill`, `WR_pw_click`, `WR_pw_quit`) drive different browser sessions; write a file for one.
- Some names are legacy aliases (`WR_get_webdriver_manager`, `WR_quit`, `WR_click_element` ...);
  the linter names the current one.

## Documents

A file is either the list itself or an object with the list under `webdriver_wrapper`:

```json
{
  "meta": {"tags": ["login"]},
  "webdriver_wrapper": [
    ["WR_new_driver", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "${ENV.BASE_URL}/login"}],
    ["WR_find_element_by", {"selector": "#user"}],
    ["WR_element_input", {"input_value": "alice"}],
    ["WR_quit_all"]
  ]
}
```

The action list must not be empty. By default a failed action is recorded and the next one runs.

## Variables and `${name}`

```json
[
  ["WR_set_var", {"name": "base", "value": "${ENV.BASE_URL}"}],
  ["WR_capture", {"name": "title", "action": ["WR_get_title"]}],
  ["WR_to_url", {"url": "${base}/search?q=${title}"}]
]
```

- `WR_set_var` (`name`, `value`) stores a value. `WR_capture` (`name`, `action`) runs one action and
  stores what it returned; when that action fails, `WR_capture` fails and the variable is unchanged.
  `WR_get_var`, `WR_unset_var`, `WR_clear_vars` and `WR_list_vars` read and remove variables.
- `${name}` reads a variable, `${name.key.0}` a key of an object or an index of a list, and
  `${ENV.KEY}` an environment variable. `ENV` and `ROW` cannot be variable names; a name is an
  identifier.
- Placeholders are replaced in the arguments of an action just before its command is called. The
  command name is never replaced.
- An argument that is exactly one placeholder gets the value with its type (a number, a list);
  inside a longer string the value is inserted as text.
- A placeholder that names nothing known is left as written. A known variable whose path does not
  exist fails the action.

## Control flow

Blocks hold ordinary actions, so they nest. The first action that fails stops its block and fails
the action that holds the block.

| Command | Arguments | What it does |
| --- | --- | --- |
| `WR_if` | `condition`, `then`, `otherwise` | runs `then` when the condition holds, else `otherwise` |
| `WR_for_each` | `items`, `do`, `var`, `index_var` | runs `do` once per element of a list |
| `WR_repeat` | `times`, `do`, `index_var` | runs `do` a fixed number of times |
| `WR_while` | `condition`, `do`, `max_iterations` | runs `do` while the condition holds |
| `WR_try` | `do`, `on_error`, `always` | handles a failure of `do` |
| `WR_retry_block` | `do`, `retries`, `backoff` | starts `do` again when one of its actions fails |
| `WR_fail` | `message` | fails |
| `WR_assert_var` | `var`, `op`, `value` | fails unless the variable satisfies the operator |

- `WR_for_each`: `items` is a list or a `${name}` that holds one. The element is the variable `var`
  (`item` by default) and its position from 0 is `index_var`; both end with the loop.
- `WR_while`: `max_iterations` is required (1 to 100000); the loop fails when the condition still
  holds after that many rounds.
- `WR_try`: with `on_error`, a failure in `do` runs it with the failure text as `${error}` and the
  action passes; without it the failure stays a failure. `always` runs in every case.
- `WR_retry_block`: up to `retries` more attempts (0 to 100, default 1), waiting `backoff` seconds
  times the attempt number in between.

```json
["WR_for_each", {"items": ["/", "/pricing"], "var": "path", "do": [
  ["WR_to_url", {"url": "${base}${path}"}],
  ["WR_if", {
    "condition": {"succeeds": ["WR_wait_for_element", {"selector": "#banner", "timeout": 2}]},
    "then": [["WR_find_element_by", {"selector": "#banner button"}], ["WR_element_click"]]
  }]
]}]
```

## Conditions

A condition is a JSON object with exactly one of these keys, never an expression:

- `{"var": "name.path", "op": "eq", "value": 1}` compares a variable; placeholders in `value` are
  expanded. Operators: `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `contains`, `in`, `startswith`,
  `endswith`, `exists`, `truthy` (the default), `falsy`. A variable that is not set is false for
  `exists` and `truthy`, true for `falsy`, and an error for the comparisons.
- `{"succeeds": ["WR_command", {...}]}` runs one action and is true when it does not fail.
- `{"all": [condition, ...]}` and `{"any": [condition, ...]}` combine conditions and stop at the
  first one that decides; `{"not": condition}` negates one.
- A plain value (`true`, `"${flag}"`) is itself after expansion.

## Calling another file

```json
["WR_call_file", {"path": "login.json", "params": {"user": "alice"}}]
```

- `WR_call_file` (`path`, `params`) runs the actions of another action file in place. `params`
  become variables of the called file and end with the call; the caller's variables are visible.
- A relative `path` starts at the directory of the file making the call, or at the working
  directory when the actions do not come from a file run.
- The called file must be below the working directory or below the directory of the file the run
  started from. A file that is already running cannot be called again; calls nest at most 20 deep.
- The first action that fails stops the called file and fails the `WR_call_file` action.

## `meta` keys

| Key | Value | Effect |
| --- | --- | --- |
| `tags` | list of strings | file selection by tag (the linter notes a file without tags) |
| `depends_on` | list of file names | files this one runs after; skipped when one of them failed |
| `vars` | object | default variables: set unless a variable of that name already exists |
| `setup` | list of actions | run before the file's own actions |
| `teardown` | list of actions | run after them, also when an earlier action failed |
| `retries` | integer 0 to 100 | extra attempts for each action of this file |
| `retry_backoff` | number of seconds | wait between those attempts |
| `fail_fast` | `true` / `false` | after the first failed action, skip the rest (not `teardown`) |
| `skip` | the reason, as text | nothing runs; one note `skipped: <reason>` is recorded |
| `dataset` | file path or list of objects | the file's actions run once per row |

A `meta` key of the wrong shape is an error before any action runs.

## Datasets

```json
{
  "meta": {"dataset": [{"user": "alice"}, {"user": "bob"}]},
  "webdriver_wrapper": [
    ["WR_find_element_by", {"selector": "#user"}],
    ["WR_element_input", {"input_value": "${ROW.user}"}]
  ]
}
```

- `meta.dataset` is the rows themselves (a list of objects) or a `.csv` / `.json` file; a relative
  path starts at the action file and must stay below the allowed directories.
- The file's own actions run once per row. `${ROW.column}` reads the current row and `${ROW_INDEX}`
  its position from 0; `setup` and `teardown` run once, around all rows.
- A column the row does not have is an error. CSV values are text; JSON values keep their type.

## Locator files

```json
{
  "login_button": {"by": "css selector", "value": "#login"},
  "user_field": {"by": "id", "value": "user"}
}
```

- A locator file gives elements logical names. `WR_load_locators` (`path`, relative to the action
  file) stores every entry; `WR_save_locator` (`name`, `value`, `by`) stores one.
- `by` is a Selenium strategy (`css selector` by default, `id`, `xpath`, `link text` ...). An entry
  has only `by` and `value`.
- The recorded-name commands of both backends then take the name:
  `["WR_find_recorded_element", {"element_name": "user_field"}]`, `WR_pw_find_element`.

## Checking a file

- `webrunner_validate_action` checks the structure (shapes of actions, blocks and `meta` hooks).
- `webrunner_lint_action` (a list in the call) and `webrunner_lint_action_file` (a file on disk)
  report unknown commands, legacy names, hard-coded URLs and mistakes in blocks and variables.
- `webrunner://schema/action` is the JSON Schema of the format, for editors.
- Through this server some commands are refused (loading packages, driving the desktop, contacting
  other hosts); `webrunner_run_actions` reports them as failed actions.
"""
