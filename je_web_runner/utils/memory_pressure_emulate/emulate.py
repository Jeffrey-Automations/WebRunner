"""
透過 CDP 降低硬體並發數 / 注入 memory-pressure 訊號,讓 suite 在低資源
條件下重跑,確認 UX 退化、不會崩潰、worker 收到 critical-memory 時釋
放快取。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from je_web_runner.utils.exception.exceptions import WebRunnerException


_LOGGER = logging.getLogger(__name__)


class MemoryPressureError(WebRunnerException):
    """Raised on bad config or CDP integration failure."""


# pylint: disable=duplicate-code  # not the Compute Pressure API's scale, though it shares its four names
class PressureLevel(str, Enum):
    """Memory pressure levels, from ``nominal`` to ``critical``."""
    NOMINAL = "nominal"
    FAIR = "fair"
    SERIOUS = "serious"
    CRITICAL = "critical"
# pylint: enable=duplicate-code


# ---------- emulation profile ------------------------------------------

# ``Memory.simulatePressureNotification`` knows two levels, ``moderate`` and ``critical`` (Chromium's
# MemoryPressureLevel); anything else is answered "Invalid memory pressure level". ``nominal`` is the
# absence of a notification.
_CDP_PRESSURE_LEVEL = {
    PressureLevel.FAIR: "moderate",
    PressureLevel.SERIOUS: "moderate",
    PressureLevel.CRITICAL: "critical",
}


@dataclass(frozen=True)
class EmulationProfile:
    """One memory + CPU emulation combo.

    ``js_heap_limit_bytes`` describes the profile only: Chromium has no CDP command that limits the JS
    heap of a running page, so ``cdp_payloads`` sends nothing for it. A heap limit is a launch argument
    (``--js-flags=--max-old-space-size=<megabytes>``).
    """

    name: str
    hardware_concurrency: int = 2
    pressure_level: PressureLevel = PressureLevel.FAIR
    cpu_throttle_rate: float = 1.0  # 1.0 = normal, 4.0 = 4x slower
    js_heap_limit_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.hardware_concurrency <= 0:
            raise MemoryPressureError("hardware_concurrency must be > 0")
        if self.cpu_throttle_rate < 1.0:
            raise MemoryPressureError("cpu_throttle_rate must be >= 1.0")
        if self.js_heap_limit_bytes is not None and self.js_heap_limit_bytes <= 0:
            raise MemoryPressureError("js_heap_limit_bytes must be > 0")


DEFAULT_PROFILES = (
    EmulationProfile(name="low_end_phone",
                     hardware_concurrency=2, cpu_throttle_rate=4.0,
                     pressure_level=PressureLevel.SERIOUS,
                     js_heap_limit_bytes=128 * 1024 * 1024),
    EmulationProfile(name="critical_pressure",
                     hardware_concurrency=4, cpu_throttle_rate=1.0,
                     pressure_level=PressureLevel.CRITICAL),
    EmulationProfile(name="single_core",
                     hardware_concurrency=1, cpu_throttle_rate=2.0,
                     pressure_level=PressureLevel.FAIR),
)


# ---------- CDP commands ------------------------------------------------

def cdp_payloads(profile: EmulationProfile) -> list[dict[str, Any]]:
    """
    Render the CDP commands a user's CDP-send callable should execute.
    Each entry is ``{"method": ..., "params": ...}``.

    The memory-pressure notification is sent as Chromium's level: ``fair`` and ``serious`` as
    ``moderate``, ``critical`` as ``critical``, and none for ``nominal``.
    """
    if not isinstance(profile, EmulationProfile):
        raise MemoryPressureError("profile must be EmulationProfile")
    commands: list[dict[str, Any]] = [
        {"method": "Emulation.setHardwareConcurrencyOverride",
         "params": {"hardwareConcurrency": profile.hardware_concurrency}},
        {"method": "Emulation.setCPUThrottlingRate",
         "params": {"rate": profile.cpu_throttle_rate}},
    ]
    level = _CDP_PRESSURE_LEVEL.get(profile.pressure_level)
    if level is not None:
        # ``Memory.simulatePressureNotification`` is an experimental Chrome endpoint.
        commands.append({"method": "Memory.simulatePressureNotification", "params": {"level": level}})
    return commands


def restore_payloads(hardware_concurrency: int | None = None) -> list[dict[str, Any]]:
    """
    Render the CDP commands that undo a profile.

    The CPU throttle goes back to 1. Chromium has no command that clears the core-count override (it
    refuses 0), so the override is set to ``hardware_concurrency``, the value the page had before the
    profile (``original_hardware_concurrency`` reads it); without it the override is left in place. A
    memory-pressure notification is a single signal and has nothing to undo.
    """
    commands: list[dict[str, Any]] = [
        {"method": "Emulation.setCPUThrottlingRate", "params": {"rate": 1}},
    ]
    if hardware_concurrency is not None:
        if isinstance(hardware_concurrency, bool) or not isinstance(hardware_concurrency, int) \
                or hardware_concurrency <= 0:
            raise MemoryPressureError("hardware_concurrency must be a positive integer")
        commands.append({"method": "Emulation.setHardwareConcurrencyOverride",
                         "params": {"hardwareConcurrency": hardware_concurrency}})
    return commands


def original_hardware_concurrency(cdp_send: Callable[[str, dict[str, Any]], Any]) -> int | None:
    """
    Ask the page for ``navigator.hardwareConcurrency`` through ``cdp_send`` (``Runtime.evaluate``).
    Call it before a profile is applied. Returns None when ``cdp_send`` does not return the answer.
    """
    try:
        answer = cdp_send("Runtime.evaluate", {
            "expression": "navigator.hardwareConcurrency", "returnByValue": True,
        })
    except Exception as error:  # pylint: disable=broad-exception-caught  # best-effort read, logged
        _LOGGER.warning("reading navigator.hardwareConcurrency failed: %r", error)
        return None
    result = answer.get("result") if isinstance(answer, dict) else None
    value = result.get("value") if isinstance(result, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


# ---------- runner ------------------------------------------------------

@dataclass
class PressureRunOutcome:
    """Whether a test passed under one pressure profile, how long it took and its error."""
    profile: str
    passed: bool
    duration_seconds: float = 0.0
    error: str | None = None


def _restore(cdp_send: Callable[[str, dict[str, Any]], Any], original_cores: int | None) -> None:
    """Best-effort restore: a failure is logged, so it neither masks nor downgrades the test result."""
    if original_cores is None:
        _LOGGER.warning("core count before the profile is unknown; its override stays in place")
    try:
        for cmd in restore_payloads(original_cores):
            cdp_send(cmd["method"], cmd["params"])
    except Exception as restore_err:  # pylint: disable=broad-exception-caught  # best-effort restore, logged
        _LOGGER.warning("CDP pressure restore failed: %r", restore_err)


def run_under_profile(
    profile: EmulationProfile,
    cdp_send: Callable[[str, dict[str, Any]], Any],
    test_callable: Callable[[], None],
) -> PressureRunOutcome:
    """
    Apply ``profile`` via ``cdp_send``, run ``test_callable()``, restore
    defaults, return outcome.

    ``cdp_send(method, params)`` must return the CDP result (as Selenium's ``execute_cdp_cmd`` and
    Playwright's ``CDPSession.send`` do) for the core count to be restored: it is read from the page
    before the profile is applied, see ``restore_payloads``.
    """
    if not callable(cdp_send):
        raise MemoryPressureError("cdp_send must be callable")
    if not callable(test_callable):
        raise MemoryPressureError("test_callable must be callable")
    import time
    original_cores = original_hardware_concurrency(cdp_send)
    try:
        for cmd in cdp_payloads(profile):
            cdp_send(cmd["method"], cmd["params"])
    except Exception as error:
        raise MemoryPressureError(f"CDP apply failed: {error!r}") from error
    started = time.monotonic()
    passed = True
    error_msg: str | None = None
    try:
        test_callable()
    except Exception as exc:  # pylint: disable=broad-exception-caught  # any test failure is recorded in the outcome
        passed = False
        error_msg = repr(exc)
    duration = round(time.monotonic() - started, 4)
    _restore(cdp_send, original_cores)
    return PressureRunOutcome(
        profile=profile.name,
        passed=passed,
        duration_seconds=duration,
        error=error_msg,
    )


# ---------- assertion ---------------------------------------------------

def assert_passed_under_pressure(outcome: PressureRunOutcome) -> None:
    """Raise MemoryPressureError when the run under the profile did not pass."""
    if not isinstance(outcome, PressureRunOutcome):
        raise MemoryPressureError("expects PressureRunOutcome")
    if not outcome.passed:
        raise MemoryPressureError(
            f"test failed under pressure profile {outcome.profile!r}: {outcome.error}"
        )
