"""
Faker 整合：產生隨機 email / 姓名 / 地址等假資料。
Faker integration. Provides quick helpers and a generic dispatch so action
JSON can call any faker provider without bespoke wrappers.

``faker`` is a soft dependency — imported on first use.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class FakerError(WebRunnerException):
    """Raised when faker isn't installed or a provider is unknown."""


_faker_instance: Any = None  # pylint: disable=invalid-name  # lazily created cache, not a constant


def _require_faker() -> Any:
    global _faker_instance  # pylint: disable=global-statement  # lazy module-level cache
    if _faker_instance is not None:
        return _faker_instance
    try:
        from faker import Faker  # type: ignore[import-not-found]
    except ImportError as error:
        raise FakerError(
            "faker is not installed. Install with: pip install faker"
        ) from error
    _faker_instance = Faker()
    return _faker_instance


def seed_faker(seed: int) -> None:
    """Set a deterministic seed for reproducible runs."""
    web_runner_logger.info(f"seed_faker: {seed}")
    _require_faker().seed_instance(int(seed))


def reset_faker() -> None:
    """Drop the cached Faker instance (mainly for tests)."""
    global _faker_instance  # pylint: disable=global-statement  # lazy module-level cache
    _faker_instance = None


def fake_value(method: str, *args: Any, **kwargs: Any) -> Any:
    """
    任意 faker provider 的通用呼叫器
    Generic dispatcher: ``fake_value("email")`` → ``Faker().email()``;
    ``fake_value("date_between", start_date="-30d", end_date="today")``.
    """
    fake = _require_faker()
    handler = getattr(fake, method, None)
    if handler is None or not callable(handler):
        raise FakerError(f"unknown faker provider: {method!r}")
    return handler(*args, **kwargs)


def fake_email() -> str:
    """Return a random email address from Faker."""
    return _require_faker().email()


def fake_name() -> str:
    """Return a random full name from Faker."""
    return _require_faker().name()


def fake_first_name() -> str:
    """Return a random first name from Faker."""
    return _require_faker().first_name()


def fake_last_name() -> str:
    """Return a random last name from Faker."""
    return _require_faker().last_name()


def fake_phone() -> str:
    """Return a random phone number from Faker."""
    return _require_faker().phone_number()


def fake_address() -> str:
    """Return a random postal address from Faker."""
    return _require_faker().address()


def fake_uuid() -> str:
    """Return a random UUID4 from Faker, as a string."""
    return str(_require_faker().uuid4())


def fake_credit_card() -> str:
    """Return a random credit card number from Faker."""
    return _require_faker().credit_card_number()


def fake_url() -> str:
    """Return a random URL from Faker."""
    return _require_faker().url()


def fake_user_agent() -> str:
    """Return a random browser User-Agent string from Faker."""
    return _require_faker().user_agent()


def fake_password(length: int = 12) -> str:
    """Return a random password of ``length`` characters from Faker."""
    return _require_faker().password(length=int(length))


def fake_text(max_chars: int | None = None) -> str:
    """Return random text from Faker, at most ``max_chars`` characters when that is given."""
    fake = _require_faker()
    if max_chars is None:
        return fake.text()
    return fake.text(max_nb_chars=int(max_chars))
