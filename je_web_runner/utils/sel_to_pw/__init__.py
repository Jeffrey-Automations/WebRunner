"""Static translator: common Selenium API calls -> Playwright equivalents."""
from je_web_runner.utils.sel_to_pw.backend_translate import (
    BackendTranslationError,
    TranslationProblem,
    how_translated,
    translatable_commands,
    translate_for_backend,
    untranslatable_commands,
)
from je_web_runner.utils.sel_to_pw.translator import (
    SelToPwError,
    Translation,
    translate_action_list,
    translate_python_source,
)

__all__ = [
    "BackendTranslationError",
    "SelToPwError",
    "Translation",
    "TranslationProblem",
    "how_translated",
    "translatable_commands",
    "translate_action_list",
    "translate_for_backend",
    "translate_python_source",
    "untranslatable_commands",
]
