"""
鍵盤與滑鼠命令的翻譯
The keyboard and pointer rows of the translation table: Selenium's ActionChains commands and
``WR_press_keys``, as Playwright ``WR_pw_keyboard_*`` / ``WR_pw_mouse_*`` actions.

Selenium names a special key by a private-use character (``Keys.ENTER`` is ``"\\ue007"``) and
``WR_press_keys`` by the name of that constant; Playwright names it by its key or code (``"Enter"``).
:data:`_KEYS` maps one to the other; a key it does not list is refused. A character that is on a
keyboard key is pressed as that key, and any other text is typed.

The ActionChains commands act on the element they are given or, without one, where the pointer is and on
the element that has the focus. Only the second form translates: Playwright's mouse and keyboard act
there too, while no Playwright command takes a recorded TestObject name without making it the current
element. All of them are queued until ``WR_perform`` (:data:`QUEUED_INPUT`).
"""
from __future__ import annotations

import copy
from typing import Any

from selenium.webdriver.common.keys import Keys

from je_web_runner.utils.sel_to_pw.backend_refusals import RECORDED_NAME
from je_web_runner.utils.sel_to_pw.backend_types import SECONDS, Action, Builder, Rule, Untranslatable

# Selenium ``Keys`` constant -> Playwright key. ``Keys.ENTER`` is the numeric keypad's Enter.
_KEYS = {
    "BACKSPACE": "Backspace", "BACK_SPACE": "Backspace", "TAB": "Tab", "RETURN": "Enter", "ENTER": "NumpadEnter",
    "SHIFT": "Shift", "LEFT_SHIFT": "Shift", "CONTROL": "Control", "LEFT_CONTROL": "Control",
    "ALT": "Alt", "LEFT_ALT": "Alt", "META": "Meta", "COMMAND": "Meta",
    "ESCAPE": "Escape", "SPACE": "Space", "PAUSE": "Pause",
    "PAGE_UP": "PageUp", "PAGE_DOWN": "PageDown", "END": "End", "HOME": "Home",
    "INSERT": "Insert", "DELETE": "Delete",
    "LEFT": "ArrowLeft", "ARROW_LEFT": "ArrowLeft", "UP": "ArrowUp", "ARROW_UP": "ArrowUp",
    "RIGHT": "ArrowRight", "ARROW_RIGHT": "ArrowRight", "DOWN": "ArrowDown", "ARROW_DOWN": "ArrowDown",
    "MULTIPLY": "NumpadMultiply", "ADD": "NumpadAdd", "SUBTRACT": "NumpadSubtract",
    "DECIMAL": "NumpadDecimal", "DIVIDE": "NumpadDivide",
    **{f"F{number}": f"F{number}" for number in range(1, 13)},
    **{f"NUMPAD{number}": f"Numpad{number}" for number in range(10)},
}
_KEY_OF_CHARACTER = {getattr(Keys, name): key for name, key in _KEYS.items() if hasattr(Keys, name)}
# Names people write that Selenium's ``Keys`` spells differently (the ones ``WR_press_keys`` accepts).
_KEY_ALIASES = {"ESC": "ESCAPE", "DEL": "DELETE", "CTRL": "CONTROL", "CMD": "COMMAND", "RETURN": "ENTER"}
_PRIVATE_USE = ("", "")


def _is_special(character: str) -> bool:
    return _PRIVATE_USE[0] <= character <= _PRIVATE_USE[1]


def _playwright_key(character: str) -> str:
    """The Playwright key of one character of a Selenium key sequence."""
    if not _is_special(character):
        return character
    key = _KEY_OF_CHARACTER.get(character)
    if key is None:
        raise Untranslatable(f"Playwright has no key for Selenium's key code {character!r}")
    return key


def _is_key(character: str) -> bool:
    """Whether Playwright can press ``character`` as a key: a special key, or one on its keyboard layout."""
    # "+" joins the keys of a shortcut in Playwright's key syntax, so it is typed instead.
    return _is_special(character) or (" " <= character <= "~" and character != "+")


def _typed(characters: str) -> list[Action]:
    """
    Press and release each character in turn, as Selenium's ``send_keys`` does. A key is pressed, so a
    modifier that is held down applies to it; text that is on no keyboard key is typed.
    """
    actions: list[Action] = []
    run = ""
    for character in characters:
        if not _is_key(character):
            run += character
            continue
        if run:
            actions.append(["WR_pw_keyboard_type", {"text": run}])
            run = ""
        actions.append(["WR_pw_keyboard_press", {"key": _playwright_key(character)}])
    if run:
        actions.append(["WR_pw_keyboard_type", {"text": run}])
    return actions


def _strings(value: Any, what: str) -> list[str]:
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)) or not all(isinstance(item, str) for item in items):
        raise Untranslatable(f"{what} must be literal text or a list of text, got {value!r}")
    return list(items)


def _send_keys(args: dict[str, Any]) -> list[Action]:
    """``WR_send_keys`` types into the element that has the focus, like Playwright's keyboard."""
    return _typed("".join(_strings(args.get("keys_to_send"), "keys_to_send")))


def _named_key(name: str) -> str:
    """The character ``WR_press_keys`` sends for ``name``: itself, or the ``Keys`` constant of that name."""
    if len(name) == 1:
        return name
    upper = name.upper()
    character = getattr(Keys, _KEY_ALIASES.get(upper, upper), None)
    if not isinstance(character, str):
        raise Untranslatable(f"unknown key {name!r}")
    return character


def _press_keys(args: dict[str, Any]) -> list[Action]:
    """``WR_press_keys`` acts at once, so its translation is not queued."""
    return _typed("".join(_named_key(name) for name in _strings(args.get("keys"), "keys")))


def _held_key(command: str) -> Builder:
    """``WR_press_key`` / ``WR_release_key`` without an element: the key goes down or up where the focus is."""
    def build(args: dict[str, Any]) -> list[Action]:
        if args.get("element_name") is not None:
            raise Untranslatable(RECORDED_NAME)
        key = args.get("keycode_on_key_class")
        if not isinstance(key, str) or len(key) != 1:
            raise Untranslatable(f"the key must be one literal character or Selenium key code, got {key!r}")
        held = _playwright_key(key)
        if held == "Shift":
            raise Untranslatable(
                "while Shift is held Selenium sends the shifted character of each key and Playwright does "
                "not; send the shifted text itself with WR_send_keys")
        return [[command, {"key": held}]]
    return build


def _pointer(*actions: Action, instead: str = "") -> Builder:
    """An ActionChains pointer command without an element: it acts where the pointer is."""
    hint = f"; use WR_find_recorded_element and then {instead}" if instead else ""

    def build(args: dict[str, Any]) -> list[Action]:
        if args.get("element_name") is not None:
            raise Untranslatable(RECORDED_NAME + hint)
        return copy.deepcopy(list(actions))
    return build


_DOWN: Action = ["WR_pw_mouse_down"]
_UP: Action = ["WR_pw_mouse_up"]
_RIGHT = {"button": "right"}
_SECOND = {"click_count": 2}

INPUT_RULES: dict[str, Rule | Builder] = {
    "WR_press_keys": _press_keys,
    "WR_send_keys": _send_keys,
    "WR_press_key": _held_key("WR_pw_keyboard_down"),
    "WR_release_key": _held_key("WR_pw_keyboard_up"),
    "WR_left_click": _pointer(_DOWN, _UP, instead="WR_element_click"),
    "WR_right_click": _pointer(["WR_pw_mouse_down", _RIGHT], ["WR_pw_mouse_up", _RIGHT]),
    # A double click is two presses; the second one counts as click number two, as Playwright's own does.
    "WR_left_double_click": _pointer(_DOWN, _UP, ["WR_pw_mouse_down", _SECOND], ["WR_pw_mouse_up", _SECOND]),
    "WR_left_click_and_hold": _pointer(_DOWN),
    "WR_release": _pointer(_UP),
    "WR_pause": Rule("WR_pw_wait_for_timeout", rename={"seconds": "timeout_ms"}, convert={"seconds": SECONDS},
                     inverse=False),
    "WR_scroll": Rule("WR_pw_scroll", inverse=False),
}

# ActionChains commands: Selenium runs them at the next ``WR_perform``, so the translator places their
# translation there. ``WR_press_keys`` is not one of them.
QUEUED_INPUT = frozenset(INPUT_RULES) - {"WR_press_keys"}
