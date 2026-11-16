"""memory_pressure_emulate: only CDP commands and values Chromium accepts (checked on Chromium 148)."""
from je_web_runner.utils.memory_pressure_emulate.emulate import (
    DEFAULT_PROFILES, EmulationProfile, PressureLevel, cdp_payloads, restore_payloads, run_under_profile,
)

# What Chromium 148 answered through a CDP session: these methods exist ...
ACCEPTED_METHODS = {
    "Emulation.setHardwareConcurrencyOverride", "Emulation.setCPUThrottlingRate",
    "Memory.simulatePressureNotification",
}
# ... and Memory.simulatePressureNotification takes only these levels.
ACCEPTED_LEVELS = {"moderate", "critical"}


def _levels(commands):
    return [c["params"]["level"] for c in commands if c["method"] == "Memory.simulatePressureNotification"]


def test_every_default_profile_sends_only_what_chromium_accepts():
    for profile in DEFAULT_PROFILES:
        commands = cdp_payloads(profile)
        assert {c["method"] for c in commands} <= ACCEPTED_METHODS, profile.name
        assert set(_levels(commands)) <= ACCEPTED_LEVELS, profile.name


def test_levels_map_to_chromium_levels():
    def level_of(level):
        return _levels(cdp_payloads(EmulationProfile(name="x", pressure_level=level)))

    assert level_of(PressureLevel.NOMINAL) == []
    assert level_of(PressureLevel.FAIR) == ["moderate"]
    assert level_of(PressureLevel.SERIOUS) == ["moderate"]
    assert level_of(PressureLevel.CRITICAL) == ["critical"]


def test_heap_limit_sends_no_cdp_command():
    with_limit = cdp_payloads(EmulationProfile(name="x", js_heap_limit_bytes=1024))
    assert with_limit == cdp_payloads(EmulationProfile(name="x"))


def test_restore_payloads():
    assert restore_payloads(12) == [
        {"method": "Emulation.setCPUThrottlingRate", "params": {"rate": 1}},
        {"method": "Emulation.setHardwareConcurrencyOverride", "params": {"hardwareConcurrency": 12}},
    ]
    assert restore_payloads(None) == [{"method": "Emulation.setCPUThrottlingRate", "params": {"rate": 1}}]


def test_run_restores_the_core_count_it_read_and_nothing_chromium_refuses():
    sent = []

    def cdp(method, params):
        sent.append((method, params))
        if method == "Runtime.evaluate":
            return {"result": {"type": "number", "value": 12, "description": "12"}}
        return {}

    outcome = run_under_profile(EmulationProfile(name="x", hardware_concurrency=2), cdp, lambda: None)
    assert outcome.passed
    assert sent[0][0] == "Runtime.evaluate"
    concurrency = [p["hardwareConcurrency"] for m, p in sent if m == "Emulation.setHardwareConcurrencyOverride"]
    assert concurrency == [2, 12]
    assert 0 not in concurrency
    assert [p["level"] for m, p in sent if m == "Memory.simulatePressureNotification"] == ["moderate"]


def test_run_without_a_readable_core_count_still_runs():
    sent = []
    outcome = run_under_profile(EmulationProfile(name="x"), lambda m, p: sent.append((m, p)), lambda: None)
    assert outcome.passed
    assert [p["hardwareConcurrency"] for m, p in sent if m == "Emulation.setHardwareConcurrencyOverride"] == [2]
    assert sent[-1] == ("Emulation.setCPUThrottlingRate", {"rate": 1})
