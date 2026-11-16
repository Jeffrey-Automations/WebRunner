"""
WebRunner 的動作執行器，建在 je_action_core 上
The action executor, built on je_action_core's :class:`~je_action_core.ActionExecutor`.

The core runs the list, keys the records (``execute: <action>``, repeats numbered ``#2`` …), prints them and
holds the commands. WebRunner adds its dialect: ``[name, [args], {kwargs}]`` actions, refused commands and the
arbitrary-script gate (checked before the name is looked up), ``${name}`` placeholders expanded in the
arguments from :attr:`Executor.variables`, the retry policy and the action span (around
every action, through :meth:`Executor.attempt`), failure screenshots and traces in the failure record, and
:meth:`Executor.execute_one`.
"""
import contextlib
import time
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from je_action_core import (
    SAFE_BUILTINS,
    ActionExecutor,
    BoundAction,
    CommandPolicy,
    CommandRegistry,
    DuplicateKeys,
    ExecutorSettings,
    PrintReporter,
    safe_builtin_commands,
    unique_record_key,
)

from je_web_runner.utils.exception.exception_tags import add_command_exception_tag
from je_web_runner.utils.exception.exception_tags import executor_data_error, executor_list_error
from je_web_runner.utils.exception.exceptions import (
    WebRunnerAddCommandException,
    WebRunnerExecuteException,
    describe_error,
)
from je_web_runner.utils.executor._event_table import build_event_dict
from je_web_runner.utils.executor._flow_commands import DEFERRED_EXPANSION
from je_web_runner.utils.flow.dataset import load_rows, per_row_actions
from je_web_runner.utils.flow.debugger import Stepper
from je_web_runner.utils.flow.document import (
    dataset_source,
    fail_fast_setting,
    planned_actions,
    read_meta,
    retry_settings,
    skip_reason,
    teardown_count,
)
from je_web_runner.utils.flow.failfast import FailFast
from je_web_runner.utils.flow.subflow import FileStack
from je_web_runner.utils.flow.variables import VariableStore
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.package_manager.package_manager_class import package_manager
from je_web_runner.utils.test_record.test_record_class import mark_handled, track_records
from je_web_runner.utils.test_record.wrapper_failures import set_raise_wrapper_errors
from je_web_runner.webdriver import playwright_wrapper as _pw
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

# 只註冊允許清單裡的內建函式（je_action_core 的 SAFE_BUILTINS，與 MailThunder、LoadDensity 相同）
# Only the allowlisted builtins are registered: je_action_core's SAFE_BUILTINS, the list MailThunder and
# LoadDensity use too, so one action list behaves the same across the workspace's frameworks (workspace
# progress.md X-12). An allowlist, because "everything except the dangerous ones" would hand action JSON
# whatever a future Python adds to builtins. Re-exported here: ``SAFE_BUILTINS`` and ``unique_record_key``
# keep their import path in this module.
__all__ = [
    "SAFE_BUILTINS", "Executor", "add_command_to_executor", "execute_action", "execute_files", "execute_one",
    "executor", "unique_record_key",
]

_NAME_ONLY = 1
_NAME_AND_PAYLOAD = 2
_NAME_ARGS_AND_KWARGS = 3

# WR_* 命令會把整段 JavaScript 字串送進瀏覽器執行；當 action JSON 來源不可信時
# 必須能關閉。透過 ``set_allow_arbitrary_script(False)`` 切換。
# WR_* commands that hand a JS string straight to the browser. When action
# JSON comes from an untrusted source the operator should be able to disable
# them; ``set_allow_arbitrary_script(False)`` flips the gate.
_ARBITRARY_SCRIPT_COMMANDS = frozenset({
    "WR_execute_script",
    "WR_execute_async_script",
    "WR_pw_evaluate",
    "WR_cdp",
    "WR_pw_cdp",
    "WR_execute_cdp_cmd",
    "WR_add_script_to_evaluate_on_new_document",
    "WR_pw_add_init_script",
})


def _try_selenium_screenshot() -> bytes | None:
    try:
        if webdriver_wrapper_instance.current_webdriver is None:
            return None
        return webdriver_wrapper_instance.get_screenshot_as_png()
    except Exception:
        return None


def _try_playwright_screenshot() -> bytes | None:
    try:
        if not _pw.playwright_wrapper_instance._pages:
            return None
        return _pw.playwright_wrapper_instance.screenshot_bytes()
    except Exception:
        return None


@dataclass(frozen=True)
class _ActionParser:
    """
    WebRunner 的動作格式
    ``[name]``, ``[name, {kwargs}]``, ``[name, [args]]`` or ``[name, [args], {kwargs}]``. The name is looked
    up first. An unknown name, a three-element action of any other shape and a longer action raise
    :class:`WebRunnerExecuteException`; an empty action raises ``IndexError``.
    """

    def bind(self, action: Any, resolve: Callable[[Any], Callable[..., Any] | None]) -> BoundAction:
        """Bind ``action`` to the command ``resolve`` finds for its name."""
        name = action[0]
        command = resolve(name)
        if command is None:
            raise WebRunnerExecuteException(f"{executor_data_error} unknown command: {name!s}")
        if len(action) == _NAME_ONLY:
            return BoundAction(name, command)
        if len(action) == _NAME_AND_PAYLOAD:
            if isinstance(action[1], dict):
                return BoundAction(name, command, (), action[1])
            return BoundAction(name, command, action[1], {})
        if len(action) == _NAME_ARGS_AND_KWARGS:
            positional, kwargs = action[1], action[2]
            if not isinstance(positional, (list, tuple)) or not isinstance(kwargs, dict):
                raise WebRunnerExecuteException(
                    f"{executor_data_error}: 3-element action requires [cmd, [positional], {{kwargs}}]"
                )
            return BoundAction(name, command, positional, kwargs)
        raise WebRunnerExecuteException(f"{executor_data_error} {action!s}")


class _ActionList:
    """Finds the actions as :meth:`Executor.document_actions` does: an empty list runs nothing."""

    def __init__(self, owner: "Executor") -> None:
        self.owner = owner

    def extract(self, action_list: Any) -> list:
        """The list to run; raises for anything that is not a list or a dict holding one."""
        return self.owner.document_actions(action_list)


class _Reporter(PrintReporter):
    """Logs the list and each failure; prints every record's key and value (as :class:`PrintReporter`)."""

    def on_start(self, action_list: Any) -> None:
        web_runner_logger.info(f"execute_action, action_list: {action_list}")

    def on_failure(self, action: Any, error: Exception) -> None:
        web_runner_logger.error(f"execute_action, action: {action}, failed: {error!r}")


def _refuse_command(_name: str) -> WebRunnerAddCommandException:
    return WebRunnerAddCommandException(add_command_exception_tag)


class Executor(ActionExecutor):
    """
    執行 WebRunner 動作清單
    Runs WebRunner action lists: je_action_core's executor with WebRunner's action format, gates, retries,
    action spans and failure artifacts. ``event_dict`` is the live command table.
    """

    def __init__(self):
        super().__init__(
            ExecutorSettings(
                rules=_ActionList(self),
                parser=_ActionParser(),
                reporter=_Reporter(),
                read_json=read_action_json,
                prepare=self.expand_placeholders,
                failure_record=self._failure_text,
                duplicate_keys=DuplicateKeys.NUMBER,
            ),
            CommandRegistry(policy=CommandPolicy.FUNCTIONS_ONLY, rejection=_refuse_command),
        )
        # 動作清單的變數；${name} 由此展開 / The variables of the action lists; ${name} reads them.
        self._shared_variables = VariableStore()
        self._context_variables: ContextVar[VariableStore | None] = ContextVar(
            f"webrunner_variables_{id(self)}", default=None)
        # 正在執行的動作檔；WR_call_file 的相對路徑由此而來
        # The action files that are running; a relative WR_call_file path starts from the current one.
        self.files = FileStack()
        # 第一個失敗後是否跳過清單其餘動作（預設否）
        # Whether the actions after a failed one are skipped (off by default); see set_fail_fast.
        self.fail_fast = FailFast()
        # 逐步執行用的除錯器（CLI 的 --step）；None 代表沒有
        # The stepper that pauses the run for the operator (the CLI's --step); None for none.
        self.debugger: Stepper | None = None
        # 沒有 meta.dataset 的檔案所用的資料集（CLI 的 --dataset）；None 代表沒有
        # The dataset of files without a meta.dataset of their own (the CLI's --dataset); None for none.
        self.default_dataset: Any = None
        # 要把動作翻譯成哪個後端的命令 / The backend whose commands every list is translated into; None: as written.
        self.backend: str | None = None
        # 失敗時自動截圖目錄；None 代表停用
        # Output directory for auto-captured failure screenshots; None disables it.
        self.failure_screenshot_dir: str | None = None
        # 全域重試策略 (預設關閉)
        # Global retry policy. retries == 0 disables retry; backoff is in
        # seconds and is multiplied by the (1-based) attempt number.
        self.retry_policy = {"retries": 0, "backoff": 0.0}
        # A file's own policy (meta.retries) while that file runs in this context; None otherwise.
        self._file_retry_policy: ContextVar[dict | None] = ContextVar(
            f"webrunner_file_retries_{id(self)}", default=None)
        # 是否允許將任意 JS / CDP 字串透過 action 送到瀏覽器；預設 True 維持向下
        # 相容，但若 action JSON 來自不可信來源請改 False。
        # Default True for back-compat; flip to False when action JSON comes
        # from an untrusted source.
        self.allow_arbitrary_script: bool = True
        # Optional context-manager factory invoked once per action so an
        # observability stack (OpenTelemetry, custom logging, …) can wrap
        # each call without the executor depending on the SDK directly.
        self._action_span_factory: Callable[[str], Any] | None = None
        # 暫時拒絕的命令（見 restricted()）/ Commands refused for now; see restricted().
        self._denied_commands: frozenset[str] = frozenset()
        # 事件字典：將字串名稱對應到實際可執行的函式
        # Event dictionary: map string keys to actual callable functions
        self.event_dict = build_event_dict(self)

        # 只把允許清單裡的內建函式加入事件字典
        # Register only the allowlisted builtins.
        self.event_dict.update(safe_builtin_commands())

    @property
    def variables(self) -> VariableStore:
        """
        動作清單的變數
        The variables the action lists read and set: one store for the executor, or the store of
        :meth:`isolated_variables` while its block runs in this context.
        """
        return self._context_variables.get() or self._shared_variables

    @contextlib.contextmanager
    def isolated_variables(self) -> Iterator[VariableStore]:
        """
        在區塊內使用一份獨立的變數
        Give this context its own variables for the ``with`` block: a copy of the current ones, whose
        changes end with the block. The async executor runs every list in one, so concurrent lists do
        not see each other's variables.
        """
        store = self.variables.copy()
        token = self._context_variables.set(store)
        try:
            yield store
        finally:
            self._context_variables.reset(token)

    def expand_placeholders(self, action: Any) -> Any:
        """
        展開動作參數裡的 ``${name}``
        The action with the known ``${name}`` / ``${ENV.KEY}`` placeholders of its arguments replaced.
        The command name is never expanded, so a variable cannot choose the command the gates check;
        a command that holds actions to run later keeps its placeholders for when they run.
        """
        if not isinstance(action, list) or len(action) < 2 or action[0] in DEFERRED_EXPANSION:
            return action
        return [action[0], *self.variables.expand(action[1:])]

    def set_backend(self, backend: str | None) -> None:
        """
        設定要執行的後端
        Run every list on ``backend`` (``"selenium"`` or ``"playwright"``): its actions, the files it
        calls and its ``meta.setup`` / ``meta.teardown`` are translated into that backend's commands
        before they run, and a list holding a command with no faithful equivalent is refused with
        every such command named. ``None`` (the default) runs lists as written.

        :raises SelToPwError: when ``backend`` is not one of the two names.
        """
        if backend is not None:
            from je_web_runner.utils.sel_to_pw.backend_translate import translate_for_backend
            translate_for_backend([], backend)
        self.backend = backend

    def set_fail_fast(self, enabled: bool = True) -> None:
        """
        設定第一個失敗後是否跳過清單其餘動作
        Turn fail-fast on or off. On: after an action of a list fails, the actions after it are recorded
        as skipped and not run, except ``meta.teardown`` actions. Off (the default): every action runs.
        It takes effect from the next list; a file can set it for itself with ``meta.fail_fast``.
        """
        self.fail_fast.enabled = bool(enabled)

    def set_retry_policy(self, retries: int = 0, backoff: float = 0.0) -> None:
        """
        設定全域重試策略
        Configure the global retry policy. ``retries`` is the number of extra
        attempts after the first; ``backoff`` is base seconds between attempts
        (multiplied by the attempt index, so 0.5 → 0.5s, 1.0s, 1.5s …).
        """
        self.retry_policy = {"retries": max(int(retries), 0), "backoff": max(float(backoff), 0.0)}

    def set_action_span_factory(self, factory: Callable[[str], Any] | None) -> None:
        """
        登錄一個 context-manager factory，每個 action 會被它包起來
        Register an optional ``ContextManager`` factory invoked once per
        action; pass ``None`` to disable.
        """
        self._action_span_factory = factory

    def _execute_with_retry(self, action):
        """Run ``_execute_event`` honouring the global retry policy."""
        if self._action_span_factory is not None and isinstance(action, list) and action:
            with self._action_span_factory(str(action[0])):
                return self._do_with_retry(action)
        return self._do_with_retry(action)

    def attempt(self, action: Any) -> Any:
        """
        執行單一動作（含重試與 span），失敗時拋出
        Run one action under the retry policy and the action span; what every action of a list passes.
        With fail-fast on, an action of a list after a failed one raises instead of running. With a
        debugger set, the run pauses before a top-level action while the operator is stepping.
        """
        if self.debugger is not None:
            self.debugger.before(action, self.variables, nested=self.fail_fast.nested)
        with self.fail_fast.step():
            return self._execute_with_retry(action)

    def _do_with_retry(self, action):
        policy = self._file_retry_policy.get() or self.retry_policy
        retries = int(policy.get("retries", 0))
        backoff = float(policy.get("backoff", 0.0))
        for attempt in range(retries + 1):
            with track_records() as records:
                try:
                    return self._execute_event(action)
                except Exception as error:
                    if attempt >= retries:
                        raise
                    # The attempt is retried, so what it recorded is not a failure of the run.
                    mark_handled(records)
                    web_runner_logger.warning(
                        f"action {action!r} failed on attempt {attempt + 1}, retrying: {error!r}"
                    )
            if backoff > 0:
                time.sleep(backoff * (attempt + 1))
        # Unreachable: ``range(retries + 1)`` always has at least one iteration.
        raise WebRunnerExecuteException("retry loop exited without resolution")

    def set_failure_screenshot_dir(self, path: str | None) -> None:
        """
        設定 (或停用) 動作失敗時的自動截圖目錄
        Configure the directory used for auto-screenshots on action failure.
        Pass ``None`` to disable.
        """
        if path:
            Path(path).mkdir(parents=True, exist_ok=True)
        self.failure_screenshot_dir = path

    def _capture_failure_screenshot(self, action) -> str | None:
        """Best-effort screenshot save when an action raises. Returns path or None."""
        if not self.failure_screenshot_dir:
            return None
        png = _try_selenium_screenshot() or _try_playwright_screenshot()
        if not png:
            return None
        target = self._failure_artifact_path(action, ".png")
        if target is None:
            return None
        try:
            target.write_bytes(png)
            return str(target)
        except OSError as error:
            web_runner_logger.error(f"failure screenshot write failed: {error!r}")
            return None

    def _capture_failure_trace(self, action) -> str | None:
        """Save the running Playwright trace beside the failure screenshot. Returns path or None."""
        wrapper = _pw.playwright_wrapper_instance
        if not self.failure_screenshot_dir or not getattr(wrapper, "tracing_active", False):
            return None
        target = self._failure_artifact_path(action, ".trace.zip")
        if target is None:
            return None
        try:
            return wrapper.save_trace_chunk(str(target))
        except Exception as error:  # the action already failed; its trace is best effort
            web_runner_logger.error(f"failure trace save failed: {error!r}")
            return None

    def _failure_artifact_path(self, action, suffix: str) -> Path | None:
        """``<failure dir>/<timestamp>_<command><suffix>``, or None if it would leave the directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        raw_name = str(action[0] if isinstance(action, list) and action else "unknown")
        # Strip any path separators and limit to safe characters; otherwise an
        # action JSON could ship a command name like ``../../etc/passwd`` and
        # cause a path traversal write (SonarCloud S2083).
        safe_name = "".join(ch for ch in raw_name if ch.isalnum() or ch in "-_")[:64] or "unknown"
        base_dir = Path(self.failure_screenshot_dir or "").resolve()  # callers checked it is set
        target = (base_dir / f"{timestamp}_{safe_name}{suffix}").resolve()
        # Belt-and-braces: confirm the resolved path stays inside the
        # configured directory before writing.
        try:
            target.relative_to(base_dir)
        except ValueError:
            web_runner_logger.error(
                f"failure artifact path escapes configured dir: {target!r}"
            )
            return None
        return target

    def set_allow_arbitrary_script(self, enabled: bool) -> None:
        """
        切換是否允許 ``WR_execute_script`` / ``WR_pw_evaluate`` / CDP 命令
        Toggle the gate for arbitrary-script commands. Disable when action
        JSON files are not fully trusted.
        """
        self.allow_arbitrary_script = bool(enabled)

    @staticmethod
    def set_raise_wrapper_errors(enabled: bool) -> None:
        """
        設定 Selenium wrapper 失敗時是否讓動作失敗
        ``True`` (the default): a failed Selenium wrapper call (``WR_to_url``,
        ``WR_element_assert`` …) fails its action, as the Playwright commands do. ``False``:
        the call returns and the action passes, the behaviour before the default changed.
        """
        set_raise_wrapper_errors(enabled)

    @staticmethod
    def set_allow_arbitrary_packages(enabled: bool) -> None:
        """
        允許或拒絕載入允許清單以外的套件（``WR_add_package_to_executor``）
        Allow (True) or refuse (False, the default) ``WR_add_package_to_executor`` for packages
        outside the allowlist. Python only, never an action command, so an action file cannot
        open its own gate.
        """
        package_manager.set_allow_arbitrary_packages(enabled)

    @staticmethod
    def allow_packages(*packages: str) -> None:
        """
        把套件（連同子模組）加入 ``WR_add_package_to_executor`` 的允許清單
        Add packages, and their submodules, to the allowlist of ``WR_add_package_to_executor``.
        """
        package_manager.allow_packages(*packages)

    @contextlib.contextmanager
    def restricted(self, denied_commands: Iterable[str]) -> Iterator[None]:
        """
        在區塊內拒絕指定命令（包含巢狀的動作清單）
        Refuse ``denied_commands`` for the duration of the ``with`` block, including in
        action lists run from inside it (``WR_execute_action``, ``WR_execute_files`` …),
        because every action passes :meth:`_execute_event`. Blocks nest; each adds to the
        commands already refused.
        """
        previous = self._denied_commands
        self._denied_commands = previous | frozenset(denied_commands)
        try:
            yield
        finally:
            self._denied_commands = previous

    def check_allowed(self, command: str, script_commands: Iterable[str] = ()) -> None:
        """
        檢查命令是否被拒絕或被任意腳本閘門擋下
        Raise :class:`WebRunnerExecuteException` when ``command`` is refused here
        (:meth:`restricted`) or ships a script while the arbitrary-script gate is closed.
        ``script_commands`` adds script commands of another command table (the async one).
        """
        if command in self._denied_commands:
            raise WebRunnerExecuteException(f"command {command!r} is not allowed here")
        if command in (_ARBITRARY_SCRIPT_COMMANDS | frozenset(script_commands)) and not self.allow_arbitrary_script:
            raise WebRunnerExecuteException(
                f"arbitrary-script command {command!r} is disabled; "
                "call WR_set_allow_arbitrary_script(true) to enable"
            )

    def _execute_event(self, action: list):
        """
        執行單一動作一次（不重試）
        Refuse a denied or gated command, then bind ``action`` and run it once (no retry). Raises what the
        refusal, the binding (see :class:`_ActionParser`) or the command raises.
        """
        self.check_allowed(action[0])
        return super()._execute_event(action)

    def run_nested(self, actions: list) -> list:
        """
        執行一個命令自己帶的動作
        Run the actions a command holds (a block of ``WR_if``, a template …) in order and return what
        each returned. Every action passes :meth:`attempt`, so the gates, placeholder expansion, the
        retry policy and the action span apply. The first failure stops the block and is raised as it
        is, so the action that holds the block fails once and is recorded once.

        :raises WebRunnerExecuteException: when ``actions`` is not a list of actions.
        """
        if not isinstance(actions, list):
            raise WebRunnerExecuteException(f"{executor_data_error}: a block is a list of actions, got {actions!r}")
        results = []
        for action in actions:
            if not isinstance(action, list) or not action or not isinstance(action[0], str):
                raise WebRunnerExecuteException(
                    f"{executor_data_error}: an action is a list that starts with a command name, got {action!r}")
            results.append(self.attempt(action))
        return results

    def execute_one(self, action: list) -> Any:
        """
        執行單一動作並回傳結果；失敗時拋出例外，不印出任何東西
        Run one action (``["WR_name"]``, ``["WR_name", {kwargs}]``, ``["WR_name", [args]]``
        or ``["WR_name", [args], {kwargs}]``) the way :meth:`execute_action` runs each step
        (refused commands, the arbitrary-script gate, the retry policy, the action span, the
        failure screenshot and trace) and return what the command returned. Prints nothing.

        :raises WebRunnerExecuteException: when the action is malformed or fails; the message
                 names any failure screenshot or trace, and the original error is ``__cause__``.
        """
        if not isinstance(action, list) or not action or not isinstance(action[0], str):
            raise WebRunnerExecuteException(
                f"{executor_data_error}: an action is a list that starts with a command name, got {action!r}")
        web_runner_logger.info(f"execute_one, action: {action}")
        try:
            return self._execute_with_retry(action)
        except Exception as error:  # every failure leaves as one exception type, with its cause
            web_runner_logger.error(f"execute_one, action: {action}, failed: {error!r}")
            raise WebRunnerExecuteException(self._failure_text(action, error)) from error

    @staticmethod
    def action_list_of(action_list: list | dict) -> list:
        """The action list itself, or a dict's ``webdriver_wrapper`` list; raises for anything else."""
        # 如果傳入的是 dict，則嘗試取出 "webdriver_wrapper" 的動作清單；結果必須是 list
        # A dict must carry its actions under "webdriver_wrapper"; the result must be a list
        # (a string would otherwise be iterated character by character).
        actions: Any = action_list
        if type(action_list) is dict:
            actions = action_list.get("webdriver_wrapper", None)
        action_list = actions
        if not isinstance(action_list, list):
            web_runner_logger.error(
                f"execute_action, action_list: {action_list}, "
                f"failed: {WebRunnerExecuteException(executor_list_error)}")
            raise WebRunnerExecuteException(executor_list_error)
        return action_list

    def document_actions(self, action_list: list | dict, scoped: bool = False) -> list:
        """
        文件實際要執行的動作
        The actions to run for ``action_list``. A plain list, and an object without the keys below, is
        its own action list (:meth:`action_list_of`). An object's ``meta`` can add ``setup`` actions
        before and ``teardown`` actions after, set default variables (``vars``), bind a ``dataset`` (the
        file's own actions then run once per row, each row announced by a ``WR_use_row`` action), or
        name a reason to ``skip`` the file, which runs one note carrying that reason instead.
        ``scoped`` keeps the default variables and the row in the innermost frame (a called file).

        :raises FlowError: when one of those ``meta`` keys has the wrong shape.
        :raises BackendTranslationError: when :meth:`set_backend` is in force and an action has no
            equivalent on that backend.
        """
        if self.backend is not None:
            from je_web_runner.utils.sel_to_pw.backend_translate import translate_for_backend
            self.action_list_of(action_list)
            action_list = translate_for_backend(action_list, self.backend)
        actions = self.action_list_of(action_list)
        meta = read_meta(action_list)
        # A called file (scoped) takes a dataset only from its own meta, not from the run's --dataset.
        source = dataset_source(meta, None if scoped else self.default_dataset)
        if source is not None and skip_reason(meta) is None:
            actions = per_row_actions(actions, load_rows(source, self.files), scoped)
        actions = planned_actions(action_list, actions, self.variables, scoped)
        self.fail_fast.set_teardown_count(len(actions), teardown_count(action_list))
        return actions

    @contextlib.contextmanager
    def document_run(self, action_list: Any) -> Iterator[None]:
        """
        一份清單的執行期間
        The run of one list: its ``meta.retries`` / ``retry_backoff`` and fail-fast apply for the
        ``with`` block, in this context only, so files running at the same time keep their own.
        ``retry_policy`` itself is not changed.
        """
        meta = read_meta(action_list)
        settings = retry_settings(meta)
        with self.fail_fast.run(fail_fast_setting(meta)):
            if settings is None:
                yield
                return
            token = self._file_retry_policy.set({"retries": settings[0], "backoff": settings[1]})
            try:
                yield
            finally:
                self._file_retry_policy.reset(token)

    def execute_action(self, action_list: Any) -> dict:
        """
        執行動作清單並回傳紀錄
        Run every action of ``action_list`` (a list, or an object holding one under
        ``webdriver_wrapper``), print and return the records. A failed action is recorded and the
        next one runs.
        """
        with self.document_run(action_list):
            return super().execute_action(action_list)

    def collect_action_results(self, action_list: Any) -> tuple[dict, list]:
        """Run ``action_list`` like :meth:`execute_action` without printing; return ``(records, failed)``."""
        with self.document_run(action_list):
            return super().collect_action_results(action_list)

    def _failure_text(self, action, error: Exception) -> str:
        artifacts = []
        screenshot_path = self._capture_failure_screenshot(action)
        if screenshot_path:
            artifacts.append(f"failure screenshot: {screenshot_path}")
        trace_path = self._capture_failure_trace(action)
        if trace_path:
            artifacts.append(f"trace: {trace_path}")
        described = describe_error(error)
        return f"{described} ({'; '.join(artifacts)})" if artifacts else described

    def execute_files(self, execute_files_list: list) -> list:
        """
        從檔案載入並執行動作
        Run the action file at every path, in order, and return their records.
        """
        web_runner_logger.info(f"execute_files, execute_files_list: {execute_files_list}")
        return [self.execute_file(path) for path in execute_files_list]

    def execute_file(self, path: str) -> dict:
        """
        載入並執行一個動作檔
        Run the action file at ``path`` and return its records. While it runs it is the current file,
        so a ``WR_call_file`` inside it takes a relative path from its directory.
        """
        with self.files.scope(path):
            return self.execute_action(self.settings.read_json(path))


# 建立全域 Executor 實例
# Create global Executor instance
executor = Executor()
package_manager.executor = executor


def add_command_to_executor(command_dict: dict):
    """
    動態新增指令到 Executor
    Dynamically add commands to Executor

    :param command_dict: {指令名稱: 函式} / {command_name: function}
    """
    executor.add_command_to_executor(command_dict)


def execute_action(action_list: list) -> dict:
    """
    全域方法：執行動作清單
    Global method: execute action list
    """
    return executor.execute_action(action_list)


def execute_one(action: list) -> Any:
    """
    全域方法：執行單一動作，失敗時拋出
    Global method: run one action and return its value; see :meth:`Executor.execute_one`.
    """
    return executor.execute_one(action)


def execute_files(execute_files_list: list) -> list:
    """
    全域方法：執行檔案中的動作
    Global method: execute actions from files
    """
    return executor.execute_files(execute_files_list)
