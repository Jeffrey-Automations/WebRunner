"""Canaries must be the same in every process: ``hash()`` of a string is salted per interpreter."""
import os
import subprocess
import sys

from je_web_runner.utils.dom_xss_taint.taint import make_canaries

_PRINT = (
    "from je_web_runner.utils.dom_xss_taint.taint import make_canaries;"
    "print('|'.join(make_canaries('checkout')))"
)


def _canaries_in_a_new_process(seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    done = subprocess.run(  # nosec B603 — fixed arguments, the test's own interpreter
        [sys.executable, "-c", _PRINT], env=env, capture_output=True, text=True, check=True, timeout=120,
    )
    return done.stdout.strip()


def test_canaries_do_not_depend_on_the_hash_seed():
    assert _canaries_in_a_new_process("1") == _canaries_in_a_new_process("2")


def test_canaries_are_two_distinct_names_per_test():
    first, second = make_canaries("checkout")
    assert first != second
    assert first.startswith("WRXSS-checkout-A-") and second.startswith("WRXSS-checkout-B-")
    assert make_canaries("login")[0] != first.replace("checkout", "login")
