"""
把動作檔翻譯成另一個 backend 的命令
Translate an action file so it runs on the other browser backend, or say exactly why it cannot.

:func:`translate_for_backend` takes a list of actions or an action document (``{"webdriver_wrapper": [...],
"meta": {"setup": [...], "teardown": [...]}}``) and returns the same shape for ``backend``
(``"playwright"`` or ``"selenium"``). It is strict: when any action cannot be translated faithfully it
raises one :class:`BackendTranslationError` that lists every such action (where it is, its command, the
reason). Nothing is passed through or dropped silently, unlike
:func:`~je_web_runner.utils.sel_to_pw.translator.translate_action_list`, which keeps producing a draft.

What happens to an action, in this order:

1. Its command has an entry in the table of :mod:`~je_web_runner.utils.sel_to_pw.backend_rules` (or is
   another name of one that has: ``WR_quit`` and ``WR_quit_all`` are the same callable): it is translated.
   Arguments are bound to the source command's signature first, so positional and keyword forms give the
   same result; the result uses keywords.
2. Its command is listed there as untranslatable: it is reported with that reason.
3. Its command drives the source backend (see :mod:`~je_web_runner.utils.sel_to_pw.backend_binding`: the
   rule is where the command is implemented, not a list of names): it is reported.
4. Anything else is backend-neutral (variables, control flow, ``WR_note``, ``WR_sleep``, reports, HTTP …)
   or already a command of the target backend, and is copied unchanged. The actions it holds are
   translated: the blocks of ``WR_if``, the loops, ``WR_try`` and ``WR_retry_block``, the action of
   ``WR_capture`` and the ``succeeds`` actions of conditions
   (:mod:`je_web_runner.utils.flow.structure` says where they are).

Some translations depend on the actions around them, and are done per list of actions:

* Selenium's ActionChains commands wait for ``WR_perform``; Playwright acts at once. A translated queued
  command (``WR_scroll``) is therefore placed where its ``WR_perform`` is. One that no ``WR_perform``
  follows in the same list is reported.
* Selenium names the HAR file when recording stops, Playwright when it starts, so the path moves between
  the two actions; they have to be in the same list.

One action can become several (``WR_find_element_by`` stores a locator and finds it by name, so the match
becomes the current element as on Selenium). Where the file holds exactly one action (``WR_capture``,
``succeeds``) such a command is reported.
"""
from __future__ import annotations

import copy
import inspect
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Mapping

from je_web_runner.utils.flow.structure import (
    ACTION_ARGUMENTS,
    BLOCK_ARGUMENTS,
    CONDITION_ARGUMENTS,
    keyword_arguments,
)
from je_web_runner.utils.sel_to_pw import backend_rules as rules
from je_web_runner.utils.sel_to_pw.backend_binding import NEUTRAL, PLAYWRIGHT, SELENIUM, backend_of, registered_command
from je_web_runner.utils.sel_to_pw.backend_rules import Action, Builder, Conversion, Rule, Untranslatable
from je_web_runner.utils.sel_to_pw.translator import SelToPwError

_VARIADIC = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
_ACTIONS_KEY = "webdriver_wrapper"
_HOOKS = ("setup", "teardown")
_EMPTY = inspect.Parameter.empty


@dataclass(frozen=True)
class TranslationProblem:
    """One action that cannot be translated: where it is, its command, and why."""

    location: str
    command: str
    reason: str

    def __str__(self) -> str:
        return f"{self.location} {self.command}: {self.reason}"


class BackendTranslationError(SelToPwError):
    """Raised by :func:`translate_for_backend`; ``problems`` lists every action that cannot be translated."""

    def __init__(self, backend: str, problems: list[TranslationProblem]) -> None:
        self.backend = backend
        self.problems = list(problems)
        lines = "\n".join(f"  {problem}" for problem in self.problems)
        super().__init__(f"{len(self.problems)} action(s) cannot be translated for {backend}:\n{lines}")


@dataclass(frozen=True)
class _Candidate:
    """A rule read in one direction: ``requires`` are source arguments that must have these values."""

    rule: Rule | Builder
    requires: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class _ListState:
    """What a list of actions has open: queued ActionChains commands and a HAR recording."""

    queued: list[Action] = field(default_factory=list)
    queued_at: list[tuple[str, str]] = field(default_factory=list)
    har: dict[str, Any] | None = None
    har_at: tuple[str, str] = ("", "")


@dataclass(frozen=True)
class _Direction:
    """Everything that differs between translating to Playwright and to Selenium."""

    source: str
    target: str
    candidates: Mapping[str, tuple[_Candidate, ...]]
    cannot: Mapping[str, str]
    sequence: Mapping[str, Callable[[dict[str, Any], _ListState], list[Action]]]


# ----- signatures --------------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _signature(name: str) -> inspect.Signature:
    command = registered_command(name)
    if command is None:
        raise Untranslatable(f"{name} is not a registered command")
    return inspect.signature(command)


def _default(name: str, parameter: str) -> Any:
    """The default of ``parameter`` of the command ``name`` (empty for a variadic one), or ``_EMPTY``."""
    found = _signature(name).parameters.get(parameter)
    if found is None:
        return _EMPTY
    if found.kind is inspect.Parameter.VAR_POSITIONAL:
        return ()
    return {} if found.kind is inspect.Parameter.VAR_KEYWORD else found.default


def _bind(action: Action) -> dict[str, Any]:
    """The arguments of ``action`` by parameter name, whether they were given by position or by keyword."""
    slots = action[1:]
    positional: Any = ()
    keywords: Any = {}
    if len(slots) == 1:
        positional, keywords = ((), slots[0]) if isinstance(slots[0], dict) else (slots[0], {})
    elif len(slots) == 2:
        positional, keywords = slots
    if len(slots) > 2 or not isinstance(positional, (list, tuple)) or not isinstance(keywords, dict):
        raise Untranslatable("its arguments are not [name], [name, {...}], [name, [...]] or [name, [...], {...}]")
    try:
        bound = _signature(action[0]).bind_partial(*positional, **keywords)
    except TypeError as error:
        raise Untranslatable(f"its arguments do not fit the command: {error}") from error
    return copy.deepcopy(dict(bound.arguments))


def _accepts(target: str, parameter: str, renamed: bool) -> bool:
    """Whether the command ``target`` takes ``parameter`` (through ``**kwargs`` only when the rule names it)."""
    parameters = _signature(target).parameters
    found = parameters.get(parameter)
    if found is not None:
        return found.kind not in _VARIADIC
    return renamed and any(item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters.values())


# ----- one action --------------------------------------------------------------------------------

def _apply_rule(source: str, rule: Rule, args: dict[str, Any]) -> Action:
    """The target action of a :class:`Rule` for the bound ``args`` of the command ``source``."""
    result: dict[str, Any] = {}
    for name, value in args.items():
        default = _default(source, name)
        if value is None and default is None:
            continue  # given as None, which is the same as not given
        target_name = rule.rename.get(name, name)
        if not _accepts(rule.target, target_name, name in rule.rename):
            if value == default:
                continue
            raise Untranslatable(f"{rule.target} has no equivalent of {name}={value!r}")
        conversion = rule.convert.get(name)
        result[target_name] = conversion.forward(value) if conversion else value
    for name, value in rule.defaults.items():
        result.setdefault(name, value)
    result.update(rule.add)
    return [rule.target, result] if result else [rule.target]


def _matches(source: str, candidate: _Candidate, args: dict[str, Any]) -> bool:
    return all(args.get(name, _default(source, name)) == value for name, value in candidate.requires.items())


def _translate_command(direction: _Direction, action: Action) -> tuple[list[Action], bool]:
    """The actions ``action`` becomes and whether they are queued until ``WR_perform``."""
    name = action[0]
    args = _bind(action)
    candidates = direction.candidates[name]
    candidate = next((item for item in candidates if _matches(name, item, args)), None)
    if candidate is None:
        wanted = " or ".join(", ".join(f"{key}={value!r}" for key, value in item.requires.items())
                             for item in candidates)
        raise Untranslatable(f"it translates only with {wanted}")
    if not isinstance(candidate.rule, Rule):
        return candidate.rule(args), False
    remaining = {key: value for key, value in args.items() if key not in candidate.requires}
    return [_apply_rule(name, candidate.rule, remaining)], name in rules.QUEUED_COMMANDS


@lru_cache(maxsize=None)
def _canonical_name(backend: str, name: str) -> str | None:
    direction = _direction(backend)
    if name in direction.candidates or name in direction.sequence:
        return name
    command = registered_command(name)
    if command is None:
        return None
    known = (*direction.candidates, *direction.sequence)
    return next((other for other in known if registered_command(other) == command), None)


def _canonical(direction: _Direction, name: str) -> str | None:
    """``name``, or the table's name for the same callable (``WR_quit`` -> ``WR_quit_all``), or None."""
    return _canonical_name(direction.target, name)


def _refusal(direction: _Direction, name: str) -> str | None:
    """Why the command ``name`` cannot be translated, or None when it is copied unchanged."""
    if name in direction.cannot:
        return direction.cannot[name]
    if backend_of(name) == direction.source:
        return f"it drives the {direction.source} backend and has no {direction.target} translation"
    return None


class _Translator:
    """One translation run: collects the problems of every list it walks."""

    def __init__(self, direction: _Direction) -> None:
        self.direction = direction
        self.problems: list[TranslationProblem] = []

    def _problem(self, location: str, command: str, reason: str) -> None:
        self.problems.append(TranslationProblem(location, command, reason))

    def actions(self, actions: list[Any], prefix: str) -> list[Any]:
        """Translate a list of actions; ``prefix`` names it in the problems (``action``, ``meta.setup`` …)."""
        state = _ListState()
        result: list[Any] = []
        for index, action in enumerate(actions):
            result.extend(self._action(action, f"{prefix}[{index}]", state))
        for location, command in state.queued_at:
            self._problem(location, command, "Selenium runs it at the next WR_perform, and none follows in this list")
        if state.har is not None:
            self._problem(*state.har_at, "the HAR recording is not stopped in this list, so its path is unknown")
        return result

    def _action(self, action: Any, location: str, state: _ListState) -> list[Any]:
        if not isinstance(action, list) or not action or not isinstance(action[0], str):
            return [copy.deepcopy(action)]  # not an action: the validator reports it
        name = _canonical(self.direction, action[0])
        if name is None:
            reason = _refusal(self.direction, action[0])
            if reason is None:
                return [self._neutral(action, location)]
            self._problem(location, action[0], reason)
            return []
        try:
            return self._translated([name, *action[1:]], (location, action[0]), state)
        except Untranslatable as error:
            self._problem(location, action[0], str(error))
            return []

    def _translated(self, action: Action, where: tuple[str, str], state: _ListState) -> list[Any]:
        """Translate ``action`` (under its table name); ``where`` is its location and the name the file uses."""
        handler = self.direction.sequence.get(action[0])
        if handler is not None:
            was_recording = state.har is not None
            produced = handler(_bind(action), state)
            if state.har is not None and not was_recording:
                state.har_at = where
            return produced
        produced, queued = _translate_command(self.direction, action)
        if not queued:
            return produced
        state.queued.extend(produced)
        state.queued_at.append(where)
        return []

    def _single(self, action: Any, location: str) -> Any:
        """Translate an action that sits where the file holds exactly one."""
        produced = self.actions([action], location)
        inside = f"{location}[0]"  # the one-action list above; the file has no index here
        self.problems = [
            TranslationProblem(location + problem.location[len(inside):], problem.command, problem.reason)
            if problem.location.startswith(inside) else problem
            for problem in self.problems
        ]
        if len(produced) == 1:
            return produced[0]
        if produced:
            self._problem(location, str(action[0]),
                          f"it becomes {len(produced)} actions, and only one action fits here")
        return copy.deepcopy(action)

    def _condition(self, condition: Any, location: str) -> Any:
        if not isinstance(condition, dict):
            return condition
        result = dict(condition)
        if "succeeds" in result:
            result["succeeds"] = self._single(result["succeeds"], f"{location}.succeeds")
        if "not" in result:
            result["not"] = self._condition(result["not"], f"{location}.not")
        for kind in ("all", "any"):
            if isinstance(result.get(kind), list):
                result[kind] = [self._condition(part, f"{location}.{kind}[{index}]")
                                for index, part in enumerate(result[kind])]
        return result

    def _neutral(self, action: Action, location: str) -> Action:
        """A copy of a backend-neutral action with the actions it holds translated."""
        result = copy.deepcopy(action)
        arguments = keyword_arguments(result)
        for key in BLOCK_ARGUMENTS.get(action[0], ()):
            if isinstance(arguments.get(key), list):
                arguments[key] = self.actions(arguments[key], f"{location}.{key}")
        for key in ACTION_ARGUMENTS.get(action[0], ()):
            if key in arguments:
                arguments[key] = self._single(arguments[key], f"{location}.{key}")
        for key in CONDITION_ARGUMENTS.get(action[0], ()):
            if key in arguments:
                arguments[key] = self._condition(arguments[key], f"{location}.{key}")
        return result


# ----- commands that depend on the actions around them -------------------------------------------

def _perform(_args: dict[str, Any], state: _ListState) -> list[Action]:
    produced, state.queued, state.queued_at = state.queued, [], []
    return produced


def _har_start_for_playwright(_args: dict[str, Any], state: _ListState) -> list[Action]:
    if state.har is not None:
        raise Untranslatable("a HAR recording is already open in this list")
    state.har = {}  # the arguments of the Playwright action; the stop that follows fills in the path
    return [[rules.PW_HAR_START, state.har]]


def _har_stop_for_playwright(args: dict[str, Any], state: _ListState) -> list[Action]:
    if state.har is None:
        raise Untranslatable(f"no {rules.HAR_START} comes before it in this list")
    if args.get("har_path") is None:
        raise Untranslatable("Playwright always writes the HAR file, so it needs har_path")
    state.har["har_path"] = args["har_path"]
    state.har = None
    return [[rules.PW_HAR_STOP]]


def _har_start_for_selenium(args: dict[str, Any], state: _ListState) -> list[Action]:
    if state.har is not None:
        raise Untranslatable("a HAR recording is already open in this list")
    if args.get("content", "omit") != "omit":
        raise Untranslatable("Selenium's HAR has no response bodies; only content='omit' translates")
    state.har = {"har_path": args.get("har_path")}
    return [[rules.HAR_START]]


def _har_stop_for_selenium(_args: dict[str, Any], state: _ListState) -> list[Action]:
    if state.har is None:
        raise Untranslatable(f"no {rules.PW_HAR_START} comes before it in this list")
    arguments, state.har = state.har, None
    return [[rules.HAR_STOP, arguments]]


# ----- the two directions ------------------------------------------------------------------------

def _inverted(name: str, rule: Rule) -> Rule | None:
    """``rule`` read from Playwright to Selenium, or None when it cannot be read backwards."""
    if not rule.inverse or any(conversion.backward is None for conversion in rule.convert.values()):
        return None
    return Rule(
        target=name,
        rename={target: source for source, target in rule.rename.items()},
        convert={rule.rename.get(source, source): Conversion(conversion.backward, conversion.forward)
                 for source, conversion in rule.convert.items() if conversion.backward is not None},
        defaults=rule.inverse_defaults,
    )


def _to_selenium_candidates() -> dict[str, tuple[_Candidate, ...]]:
    found: dict[str, list[_Candidate]] = {}
    for name, rule in rules.SELENIUM_TO_PLAYWRIGHT.items():
        inverted = _inverted(name, rule) if isinstance(rule, Rule) else None
        if inverted is not None and isinstance(rule, Rule):
            found.setdefault(rule.target, []).append(_Candidate(inverted, rule.add))
    # The rule that asks for more comes first; the first of the table is the fallback.
    return {name: tuple(sorted(items, key=lambda item: len(item.requires) == 0)) for name, items in found.items()}


@lru_cache(maxsize=1)
def _directions() -> dict[str, _Direction]:
    forward = {name: (_Candidate(rule),) for name, rule in rules.SELENIUM_TO_PLAYWRIGHT.items()}
    return {
        PLAYWRIGHT: _Direction(SELENIUM, PLAYWRIGHT, forward, rules.CANNOT_TRANSLATE, {
            rules.PERFORM: _perform,
            rules.HAR_START: _har_start_for_playwright,
            rules.HAR_STOP: _har_stop_for_playwright,
        }),
        SELENIUM: _Direction(PLAYWRIGHT, SELENIUM, _to_selenium_candidates(), {}, {
            rules.PW_HAR_START: _har_start_for_selenium,
            rules.PW_HAR_STOP: _har_stop_for_selenium,
        }),
    }


def _direction(backend: Any) -> _Direction:
    directions = _directions()
    if backend not in directions:
        raise SelToPwError(f"backend must be one of {sorted(directions)}, not {backend!r}")
    return directions[backend]


# ----- public API --------------------------------------------------------------------------------

def translate_for_backend(actions: list[Any] | dict[str, Any], backend: str = PLAYWRIGHT) -> Any:
    """
    把動作清單或動作文件翻譯成 ``backend`` 的命令
    Translate a list of actions, or an action document, into the commands of ``backend``
    (``"playwright"``: from ``WR_*``; ``"selenium"``: from ``WR_pw_*``). The input is not changed.

    :return: the same shape as ``actions``: a list, or a document with its ``webdriver_wrapper`` list and
        its ``meta.setup`` / ``meta.teardown`` lists translated.
    :raises BackendTranslationError: when at least one action cannot be translated; it names them all.
    :raises SelToPwError: when ``actions`` is neither a list nor a document, or ``backend`` is unknown.
    """
    translator = _Translator(_direction(backend))
    if isinstance(actions, list):
        result: Any = translator.actions(actions, "action")
    elif isinstance(actions, dict):
        result = _translate_document(translator, actions)
    else:
        raise SelToPwError("actions must be a list of actions or an action document (an object)")
    if translator.problems:
        raise BackendTranslationError(backend, translator.problems)
    return result


def _translate_document(translator: _Translator, document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    if isinstance(result.get(_ACTIONS_KEY), list):
        result[_ACTIONS_KEY] = translator.actions(result[_ACTIONS_KEY], "action")
    meta = result.get("meta")
    if isinstance(meta, dict):
        for hook in _HOOKS:
            if isinstance(meta.get(hook), list):
                meta[hook] = translator.actions(meta[hook], f"meta.{hook}")
    return result


def how_translated(command: str, backend: str = PLAYWRIGHT) -> tuple[str, str]:
    """
    What :func:`translate_for_backend` does with the command ``command``, without an action to translate.

    :return: ``("translated", how)`` where ``how`` names the target command(s) or describes the builder;
        ``("untranslatable", reason)``; or ``("unchanged", why)`` for a backend-neutral command and for a
        command of ``backend`` itself. A translated command can still be refused for particular arguments.
    """
    direction = _direction(backend)
    name = _canonical(direction, command)
    if name is not None and name in direction.sequence:
        return "translated", rules.SEQUENCE_COMMANDS.get(name, f"its {direction.target} twin")
    if name is not None:
        targets = [item.rule.target if isinstance(item.rule, Rule) else f"one or more {direction.target} actions"
                   for item in direction.candidates[name]]
        return "translated", " / ".join(dict.fromkeys(targets))
    reason = _refusal(direction, command)
    if reason is not None:
        return "untranslatable", reason
    kind = backend_of(command)
    return "unchanged", "backend-neutral" if kind == NEUTRAL else f"already a {kind} command"


def translatable_commands(backend: str = PLAYWRIGHT) -> list[str]:
    """The source commands the table translates for ``backend``, sorted (other names of them translate too)."""
    direction = _direction(backend)
    return sorted({*direction.candidates, *direction.sequence})


def untranslatable_commands(backend: str = PLAYWRIGHT) -> dict[str, str]:
    """The commands listed as untranslatable for ``backend``, with the reason for each."""
    return dict(_direction(backend).cannot)
