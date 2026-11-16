"""
前端版面、在地化與無障礙檢查的命令轉接層（第一部分）
Command adapters for the front-end checks, part one: DST boundaries, emulated CSS media modes, number and
currency formats, OCR text, pseudo-localisation, RTL layout, screen-reader order, perceptual image
comparison, WCAG 2.2 target size and pull-to-refresh. Part two is ``_commands_frontend_2.py``.

A command that checks data takes that data as an argument, so a saved payload can be checked without a
browser; the ``..._page`` commands read the same data from the current page.
"""
# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it
from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
from typing import Any, Callable, Iterable

from je_web_runner.utils.executor._command_helpers import page_source, selenium_driver, to_plain


def _problems(checks: Iterable[Callable[[], Any]], error_type: type[Exception]) -> list[str]:
    """Run every check and return the message of each one that raised ``error_type``."""
    found: list[str] = []
    for check in checks:
        try:
            check()
        except error_type as error:
            found.append(str(error))
    return found


def _harvest(command: str, script: str, *arguments: Any) -> Any:
    """
    Run one of the libraries' constant harvest scripts in the current page and return its value. The
    ``return`` in front serves the scripts that are a bare expression; the ones that return their own
    value are unaffected by it.
    """
    return selenium_driver(command).execute_script("return " + script.strip(), *arguments)


# ---------- dst_boundary_test -------------------------------------------

def _moment(value: str) -> datetime:
    """An ISO 8601 date-time string as a ``datetime``."""
    from je_web_runner.utils.dst_boundary_test.boundary import DstBoundaryError
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise DstBoundaryError(f"not an ISO 8601 date-time: {value!r}") from error


def dst_boundary_test_find(tz_name: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
    """
    List every daylight-saving clock change of a time zone between two years (at most ten years apart).

    :param tz_name: IANA zone name, e.g. ``"America/New_York"``
    :return: ``[{"moment_utc": ISO time, "transition": "spring_forward"|"fall_back",
        "offset_before_seconds": n, "offset_after_seconds": n, "shift_seconds": n, "tz_name": str}, ...]``
    """
    from je_web_runner.utils.dst_boundary_test.boundary import find_boundaries
    return [
        {
            "moment_utc": boundary.moment_utc.isoformat(),
            "transition": boundary.transition.value,
            "offset_before_seconds": boundary.offset_before.total_seconds(),
            "offset_after_seconds": boundary.offset_after.total_seconds(),
            "shift_seconds": boundary.shift.total_seconds(),
            "tz_name": boundary.tz_name,
        }
        for boundary in find_boundaries(tz_name, start_year, end_year)
    ]


def dst_boundary_test_classify(tz_name: str, wall_clock: str) -> dict[str, bool]:
    """
    Tell whether a local clock time does not exist (spring-forward gap) or happens twice (fall-back overlap).

    :param wall_clock: local time without an offset, e.g. ``"2026-03-08T02:30:00"``
    :return: ``{"nonexistent": bool, "ambiguous": bool}``
    """
    from je_web_runner.utils.dst_boundary_test import boundary as library
    moment = _moment(wall_clock)
    try:
        nonexistent = library.is_nonexistent_local_time(tz_name, moment)
        # The library's overlap test is also true inside a gap; a time that does not exist is not ambiguous.
        ambiguous = not nonexistent and library.is_ambiguous_local_time(tz_name, moment)
    except (KeyError, ValueError) as error:
        raise library.DstBoundaryError(f"unknown timezone: {tz_name!r}") from error
    return {"nonexistent": nonexistent, "ambiguous": ambiguous}


def dst_boundary_test_assert_no_duplicate_fires(fires: list[str]) -> int:
    """
    Fail when a scheduler fired twice at the same instant.

    :param fires: ISO 8601 times with an offset, e.g. ``["2026-11-01T06:30:00+00:00", ...]``
    :return: the number of fires checked
    """
    from je_web_runner.utils.dst_boundary_test.boundary import assert_no_duplicate_fires
    assert_no_duplicate_fires([_moment(fire) for fire in fires])
    return len(fires)


def dst_boundary_test_assert_fired_around(
        fires: list[str], expected_utc: str, tolerance_seconds: float = 60.0) -> bool:
    """
    Fail unless at least one fire is within ``tolerance_seconds`` of the expected time.

    :param fires: ISO 8601 times with an offset
    :param expected_utc: ISO 8601 time with an offset
    """
    from je_web_runner.utils.dst_boundary_test.boundary import assert_fired_around
    assert_fired_around(
        [_moment(fire) for fire in fires], _moment(expected_utc), timedelta(seconds=tolerance_seconds),
    )
    return True


# ---------- forced_colors_mode ------------------------------------------

def _media_profile(name: str, values: dict[str, str]) -> Any:
    """Build the library's ``MediaProfile`` from the four media-feature values."""
    from je_web_runner.utils.forced_colors_mode import modes
    try:
        return modes.MediaProfile(
            name=name,
            color_scheme=modes.ColorScheme(values["color_scheme"]),
            reduced_motion=modes.ReducedMotion(values["reduced_motion"]),
            forced_colors=modes.ForcedColors(values["forced_colors"]),
            contrast=modes.Contrast(values["contrast"]),
        )
    except ValueError as error:
        raise modes.ForcedColorsModeError(f"unknown media value: {error}") from error


def _profile_plain(profile: Any) -> dict[str, Any]:
    """A ``MediaProfile`` with the CDP features it stands for."""
    return {**to_plain(profile), "features": profile.to_cdp_features()}


def _mode_report(snapshots_by_mode: dict[str, dict[str, dict[str, str]]], baseline_mode: str) -> Any:
    """Diff every mode's computed styles against the baseline mode."""
    from je_web_runner.utils.forced_colors_mode import modes
    if not isinstance(snapshots_by_mode, dict):
        raise modes.ForcedColorsModeError("snapshots_by_mode must be an object")
    built: dict[str, dict[str, Any]] = {}
    for mode, snapshots in snapshots_by_mode.items():
        if not isinstance(snapshots, dict):
            raise modes.ForcedColorsModeError(f"snapshots of mode {mode!r} must be an object")
        built[mode] = {
            selector: modes.StyleSnapshot(
                background_color=str(style.get("background_color") or ""),
                color=str(style.get("color") or ""),
                outline=str(style.get("outline") or ""),
                border_color=str(style.get("border_color") or ""),
                visibility=str(style.get("visibility") or "visible"),
            )
            for selector, style in snapshots.items()
        }
    return modes.audit_modes(baseline_mode, built)


def forced_colors_mode_profiles() -> list[dict[str, Any]]:
    """List the built-in media profiles (baseline, dark, reduced-motion, high-contrast, dark-high-contrast)."""
    from je_web_runner.utils.forced_colors_mode.modes import DEFAULT_PROFILES
    return [_profile_plain(profile) for profile in DEFAULT_PROFILES]


def forced_colors_mode_apply(
        profile: str | None = None,
        color_scheme: str = "light",
        reduced_motion: str = "no-preference",
        forced_colors: str = "none",
        contrast: str = "no-preference",
) -> dict[str, Any]:
    """
    Make the current page (Chromium) render under a dark / reduced-motion / forced-colors / contrast mode.

    :param profile: the name of a built-in profile (see ``WR_forced_colors_mode_profiles``); when given, the
        other arguments are ignored
    :param color_scheme: ``"light"`` or ``"dark"``
    :param reduced_motion: ``"no-preference"`` or ``"reduce"``
    :param forced_colors: ``"none"`` or ``"active"``
    :param contrast: ``"no-preference"``, ``"more"`` or ``"less"``
    :return: the profile that was applied, with its CDP ``features``
    """
    from je_web_runner.utils.forced_colors_mode import modes
    if profile is None:
        chosen = _media_profile("custom", {
            "color_scheme": color_scheme, "reduced_motion": reduced_motion,
            "forced_colors": forced_colors, "contrast": contrast,
        })
    else:
        named = {item.name: item for item in modes.DEFAULT_PROFILES}
        if profile not in named:
            raise modes.ForcedColorsModeError(f"unknown profile {profile!r}; choose one of {sorted(named)}")
        chosen = named[profile]
    driver = selenium_driver("WR_forced_colors_mode_apply")
    modes.apply_profile(
        chosen, lambda features: driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"features": features}),
    )
    return _profile_plain(chosen)


def forced_colors_mode_audit(
        snapshots_by_mode: dict[str, dict[str, dict[str, str]]], baseline_mode: str = "baseline",
) -> dict[str, Any]:
    """
    Compare the computed styles of elements across media modes and list what changed or became invisible.

    :param snapshots_by_mode: ``{mode: {selector: {"background_color": str, "color": str, "outline": str,
        "border_color": str, "visibility": str}}}``
    :return: ``{"passed": bool, "diffs": [...], "invisible_in_modes": {mode: [selector, ...]}}``
    """
    report = _mode_report(snapshots_by_mode, baseline_mode)
    return {"passed": report.passed(), **to_plain(report)}


def forced_colors_mode_assert_no_invisible(
        snapshots_by_mode: dict[str, dict[str, dict[str, str]]], baseline_mode: str = "baseline",
) -> int:
    """
    Fail when an element's text colour equals its background in a mode but not in the baseline mode.

    :param snapshots_by_mode: as for ``WR_forced_colors_mode_audit``
    :return: the number of style differences found (none of them an invisible element)
    """
    from je_web_runner.utils.forced_colors_mode.modes import assert_no_invisible
    report = _mode_report(snapshots_by_mode, baseline_mode)
    assert_no_invisible(report)
    return len(report.diffs)


# ---------- number_currency_locale --------------------------------------

def number_currency_locale_check(rendered: str, locale: str, currency: bool = False) -> dict[str, Any]:
    """
    Report whether a rendered number (and, with ``currency``, its symbol) follows a locale's format.

    :param rendered: the text on the page, e.g. ``"1.234,56 €"``
    :param locale: e.g. ``"en-US"``, ``"de-DE"``, ``"fr-FR"``, ``"ja-JP"``, ``"hi-IN"``
    :return: ``{"passed": bool, "problems": [message, ...]}``
    """
    from je_web_runner.utils.number_currency_locale import locale as library
    checks = [partial(library.assert_number_format, rendered, locale)]
    if currency:
        checks.append(partial(library.assert_currency_symbol, rendered, locale))
    problems = _problems(checks, library.NumberCurrencyLocaleError)
    return {"passed": not problems, "problems": problems}


def number_currency_locale_assert_number(rendered: str, locale: str) -> bool:
    """Fail when a rendered number uses the wrong decimal separator or digit grouping for the locale."""
    from je_web_runner.utils.number_currency_locale.locale import assert_number_format
    assert_number_format(rendered, locale)
    return True


def number_currency_locale_assert_currency(rendered: str, locale: str) -> bool:
    """Fail when a rendered amount lacks the locale's currency symbol or has it on the wrong side."""
    from je_web_runner.utils.number_currency_locale.locale import assert_currency_symbol
    assert_currency_symbol(rendered, locale)
    return True


def number_currency_locale_assert_date(rendered: str, date_format: str = "iso") -> bool:
    """
    Fail when a rendered date is not written in the expected style.

    :param date_format: ``"iso"`` (2026-05-24), ``"us"`` (5/24/2026), ``"eu"`` (24.5.2026) or ``"fr"`` (24/5/2026)
    """
    from je_web_runner.utils.number_currency_locale.locale import assert_date_format
    assert_date_format(rendered, date_format)
    return True


# ---------- ocr_assert ---------------------------------------------------

def _ocr_checked(result: Any) -> dict[str, Any]:
    """Raise the library's error for a failed OCR match, otherwise return the match as JSON."""
    result.raise_if_failed()
    return dict(to_plain(result))


def ocr_assert_extract_text(image_path: str, lang: str = "eng") -> str:
    """Read the text in an image file with Tesseract OCR (needs ``pytesseract`` and the tesseract binary)."""
    from je_web_runner.utils.ocr_assert import ocr
    return ocr.extract_text(image_path, backend=ocr.tesseract_backend(lang=lang))


def ocr_assert_contains(
        image_path: str, needle: str, case_sensitive: bool = False, lang: str = "eng") -> dict[str, Any]:
    """
    Fail unless the text recognised in an image file contains ``needle``.

    :return: ``{"matched": true, "mode": "contains", "needle": str, "haystack": str, "score": 1.0, ...}``
    """
    from je_web_runner.utils.ocr_assert import ocr
    return _ocr_checked(ocr.assert_text_contains(
        image_path, needle, backend=ocr.tesseract_backend(lang=lang), case_sensitive=case_sensitive,
    ))


def ocr_assert_fuzzy(
        image_path: str, expected: str, min_ratio: float = 0.8, lang: str = "eng") -> dict[str, Any]:
    """Fail unless the text recognised in an image file is at least ``min_ratio`` (0-1) similar to ``expected``."""
    from je_web_runner.utils.ocr_assert import ocr
    return _ocr_checked(ocr.assert_text_fuzzy(
        image_path, expected, min_ratio=min_ratio, backend=ocr.tesseract_backend(lang=lang),
    ))


def ocr_assert_any(image_path: str, candidates: list[str], lang: str = "eng") -> dict[str, Any]:
    """Fail unless the text recognised in an image file contains at least one of ``candidates``."""
    from je_web_runner.utils.ocr_assert import ocr
    return _ocr_checked(ocr.assert_text_any(
        image_path, candidates, backend=ocr.tesseract_backend(lang=lang),
    ))


def ocr_assert_page_contains(needle: str, case_sensitive: bool = False, lang: str = "eng") -> dict[str, Any]:
    """Fail unless a screenshot of the current page, read with OCR, contains ``needle`` (canvas text included)."""
    from je_web_runner.utils.ocr_assert import ocr
    screenshot = selenium_driver("WR_ocr_assert_page_contains").get_screenshot_as_png()
    return _ocr_checked(ocr.assert_text_contains(
        screenshot, needle, backend=ocr.tesseract_backend(lang=lang), case_sensitive=case_sensitive,
    ))


# ---------- pseudo_localization -----------------------------------------

def _pseudo_config(accent: bool, expansion_ratio: float, bracket: bool) -> Any:
    from je_web_runner.utils.pseudo_localization.pseudo import PseudoConfig
    return PseudoConfig(accent=accent, expansion_ratio=expansion_ratio, bracket=bracket)


def _pseudo_report(rendered_text: str, catalogue: dict[str, str], min_length: int) -> Any:
    from je_web_runner.utils.pseudo_localization.pseudo import PseudoLocalizationError, scan_for_hardcoded
    if not isinstance(catalogue, dict):
        raise PseudoLocalizationError("catalogue must be an object of key: string")
    return scan_for_hardcoded(rendered_text, catalogue=catalogue, min_length=min_length)


def _pseudo_report_plain(report: Any) -> dict[str, Any]:
    return {"passed": report.passed(), **to_plain(report)}


def pseudo_localization_text(
        text: str, accent: bool = True, expansion_ratio: float = 0.4, bracket: bool = True) -> str:
    """
    Turn a string into its pseudo-localised form (accented look-alikes, padding, brackets).

    Placeholders such as ``{name}``, ``%s`` and ``<b>`` are kept as they are.
    """
    from je_web_runner.utils.pseudo_localization.pseudo import pseudo_localize
    return pseudo_localize(text, _pseudo_config(accent, expansion_ratio, bracket))


def pseudo_localization_catalogue(
        catalogue: dict[str, str], accent: bool = True, expansion_ratio: float = 0.4, bracket: bool = True,
) -> dict[str, str]:
    """Pseudo-localise every value of a ``{key: string}`` translation catalogue."""
    from je_web_runner.utils.pseudo_localization.pseudo import pseudo_localize_dict
    return pseudo_localize_dict(catalogue, _pseudo_config(accent, expansion_ratio, bracket))


def pseudo_localization_scan(rendered_text: str, catalogue: dict[str, str], min_length: int = 3) -> dict[str, Any]:
    """
    Find source strings that still appear untranslated in text rendered under the pseudo locale.

    :param catalogue: the source-language ``{key: string}`` catalogue
    :return: ``{"passed": bool, "rendered_chars": n, "hits": [{"string": str, "occurrences": n}, ...]}``
    """
    return _pseudo_report_plain(_pseudo_report(rendered_text, catalogue, min_length))


def pseudo_localization_scan_page(catalogue: dict[str, str], min_length: int = 3) -> dict[str, Any]:
    """Find source strings that still appear untranslated in the current page's HTML."""
    rendered = page_source("WR_pseudo_localization_scan_page")
    return _pseudo_report_plain(_pseudo_report(rendered, catalogue, min_length))


def pseudo_localization_assert_no_hardcoded(
        rendered_text: str, catalogue: dict[str, str], min_length: int = 3) -> int:
    """
    Fail when a source string of the catalogue appears untranslated in the rendered text.

    :return: the number of characters scanned
    """
    from je_web_runner.utils.pseudo_localization.pseudo import PseudoLocalizationError
    report = _pseudo_report(rendered_text, catalogue, min_length)
    if not report.passed():
        sample = [hit.string for hit in report.hits[:5]]
        raise PseudoLocalizationError(f"{len(report.hits)} untranslated string(s) in rendered text: {sample}")
    return int(report.rendered_chars)


# ---------- rtl_layout_verify -------------------------------------------

def _rtl_checks(
        payload: dict[str, Any], selectors: list[str] | None, ordered_selectors: list[str] | None,
) -> tuple[Any, list[Callable[[], Any]]]:
    """Parse a harvested RTL payload and line up the library's assertions for it."""
    from je_web_runner.utils.rtl_layout_verify import verify
    snapshot = verify.parse_snapshot(payload)
    checks: list[Callable[[], Any]] = [partial(verify.assert_document_rtl, snapshot)]
    for selector in selectors or []:
        checks.append(partial(verify.assert_logical_properties, snapshot, selector))
        checks.append(partial(verify.assert_bidi_isolation, snapshot, selector))
    for selector in ordered_selectors or []:
        checks.append(partial(verify.assert_visual_order_reversed, snapshot, selector))
    return snapshot, checks


def rtl_layout_verify_check(
        payload: dict[str, Any],
        selectors: list[str] | None = None,
        ordered_selectors: list[str] | None = None,
) -> dict[str, Any]:
    """
    Report what is wrong with a right-to-left layout: document direction, physical margins, bidi leaks, order.

    :param payload: ``{"documentDir": "rtl", "items": [{"selector": str, "boxes": [{"tag": str, "text": str,
        "left": n, "right": n, "direction": "rtl", "marginLeft": "0px", "marginRight": "8px",
        "unicodeBidi": "normal"}, ...]}, ...]}``
    :param selectors: selectors of the payload checked for logical margins and bidi isolation
    :param ordered_selectors: selectors whose first box must be the right-most one
    :return: ``{"document_dir": str, "passed": bool, "problems": [message, ...]}``
    """
    from je_web_runner.utils.rtl_layout_verify.verify import RtlLayoutVerifyError
    snapshot, checks = _rtl_checks(payload, selectors, ordered_selectors)
    problems = _problems(checks, RtlLayoutVerifyError)
    return {"document_dir": snapshot.document_dir, "passed": not problems, "problems": problems}


def rtl_layout_verify_assert(
        payload: dict[str, Any],
        selectors: list[str] | None = None,
        ordered_selectors: list[str] | None = None,
) -> int:
    """
    Fail on the first right-to-left layout problem (arguments as for ``WR_rtl_layout_verify_check``).

    :return: the number of checks that passed
    """
    checks = _rtl_checks(payload, selectors, ordered_selectors)[1]
    for check in checks:
        check()
    return len(checks)


# ---------- screen_reader_runner ----------------------------------------

def screen_reader_runner_walk(tree: dict[str, Any], include_decorative: bool = False) -> dict[str, Any]:
    """
    Say what a screen reader would announce for an accessibility tree, and list the problems met on the way.

    :param tree: nested nodes ``{"role": str, "name": str, "level": n, "children": [...]}``
    :return: ``{"speech": str, "passed": bool, "utterances": [{"text", "role", "node_index"}, ...],
        "violations": [{"kind", "role", "node_index", "detail"}, ...]}``
    """
    from je_web_runner.utils.screen_reader_runner.reader import walk_tree
    transcript = walk_tree(tree, include_decorative=include_decorative)
    return {
        "speech": transcript.speech(),
        "passed": transcript.passed(),
        "utterances": to_plain(transcript.utterances),
        "violations": to_plain(transcript.violations),
    }


def screen_reader_runner_assert_no_violations(tree: dict[str, Any]) -> int:
    """
    Fail when an accessibility tree has an unnamed control, a skipped heading level, an image without alt
    text or a link called "click here".

    :return: the number of utterances
    """
    from je_web_runner.utils.screen_reader_runner import reader
    transcript = reader.walk_tree(tree)
    reader.assert_no_violations(transcript)
    return len(transcript.utterances)


def screen_reader_runner_assert_reads(tree: dict[str, Any], expected_phrase: str) -> dict[str, Any]:
    """Fail unless a screen reader walking the accessibility tree would say ``expected_phrase``."""
    from je_web_runner.utils.screen_reader_runner import reader
    return dict(to_plain(reader.assert_reads(reader.walk_tree(tree), expected_phrase)))


# ---------- visual_ai ----------------------------------------------------

def _regions(crop_box: list[int] | None, mask_boxes: list[list[int]] | None) -> dict[str, Any]:
    """The library's region keyword arguments for the JSON form of the boxes."""
    return {"crop_box": crop_box, "mask_boxes": mask_boxes}


def visual_ai_hash(
        image_path: str, kind: str = "dhash",
        crop_box: list[int] | None = None, mask_boxes: list[list[int]] | None = None,
) -> dict[str, str]:
    """
    Compute a perceptual hash of an image file.

    :param kind: ``"ahash"``, ``"dhash"`` or ``"phash"``
    :param crop_box: ``[left, top, right, bottom]`` pixels to hash instead of the whole image
    :param mask_boxes: boxes painted black before hashing (clocks, banners)
    :return: ``{"kind": str, "bits": "0101...", "hex": str}``
    """
    from je_web_runner.utils.visual_ai import perceptual
    hashers: dict[str, Callable[..., Any]] = {
        "ahash": perceptual.average_hash,
        "dhash": perceptual.difference_hash,
        "phash": perceptual.perceptual_hash,
    }
    hasher = hashers.get(str(kind).lower())
    if hasher is None:
        raise perceptual.VisualAIError(f"unknown hash kind {kind!r}; choose one of {sorted(hashers)}")
    result = hasher(image_path, **_regions(crop_box, mask_boxes))
    return {"kind": result.kind, "bits": result.bits, "hex": result.hex()}


def visual_ai_compare(
        baseline_path: str, candidate_path: str, threshold: float = 0.9,
        crop_box: list[int] | None = None, mask_boxes: list[list[int]] | None = None,
) -> dict[str, Any]:
    """
    Score how alike two image files look (three perceptual hashes and a structural score, 0-1).

    :param crop_box: ``[left, top, right, bottom]`` pixels to compare instead of the whole images
    :param mask_boxes: boxes painted black in both images first
    :return: ``{"composite": n, "passed": bool, "threshold": n, "ahash_similarity": n, ...}``
    """
    from je_web_runner.utils.visual_ai.perceptual import compare_images
    regions = _regions(crop_box, mask_boxes)
    return dict(to_plain(compare_images(baseline_path, candidate_path, threshold=threshold, **regions)))


def visual_ai_assert_similar(
        baseline_path: str, candidate_path: str, threshold: float = 0.9,
        crop_box: list[int] | None = None, mask_boxes: list[list[int]] | None = None,
) -> dict[str, Any]:
    """Fail when two image files look less alike than ``threshold`` (arguments as ``WR_visual_ai_compare``)."""
    from je_web_runner.utils.visual_ai.perceptual import assert_visual_similar
    regions = _regions(crop_box, mask_boxes)
    return dict(to_plain(assert_visual_similar(baseline_path, candidate_path, threshold=threshold, **regions)))


def visual_ai_assert_page_similar(
        baseline_path: str, threshold: float = 0.9,
        crop_box: list[int] | None = None, mask_boxes: list[list[int]] | None = None,
) -> dict[str, Any]:
    """Fail when a screenshot of the current page looks less like the baseline image than ``threshold``."""
    from je_web_runner.utils.visual_ai.perceptual import assert_visual_similar
    regions = _regions(crop_box, mask_boxes)
    screenshot = selenium_driver("WR_visual_ai_assert_page_similar").get_screenshot_as_png()
    return dict(to_plain(assert_visual_similar(baseline_path, screenshot, threshold=threshold, **regions)))


# ---------- wcag22_touch_target -----------------------------------------

def _touch_target_violations(payload: Any) -> list[Any]:
    from je_web_runner.utils.wcag22_touch_target import touch
    return touch.audit(touch.parse_targets(payload))


def _touch_target_page(command: str) -> Any:
    from je_web_runner.utils.wcag22_touch_target.touch import HARVEST_SCRIPT
    return _harvest(command, HARVEST_SCRIPT) or []


def wcag22_touch_target_audit(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    List the interactive elements smaller than 24x24 CSS pixels that no WCAG 2.2 (2.5.8) exception covers.

    :param targets: ``[{"tag": str, "label": str, "width": n, "height": n, "x": n, "y": n,
        "isInlineInText": bool, "isUserAgentControl": bool}, ...]``
    :return: ``[{"label", "tag", "width", "height", "note"}, ...]``
    """
    return list(to_plain(_touch_target_violations(targets)))


def wcag22_touch_target_audit_page() -> list[dict[str, Any]]:
    """List the too-small interactive elements (WCAG 2.2, 2.5.8) of the current page."""
    return list(to_plain(_touch_target_violations(_touch_target_page("WR_wcag22_touch_target_audit_page"))))


def wcag22_touch_target_assert(targets: list[dict[str, Any]]) -> int:
    """
    Fail when a harvested interactive element breaks the WCAG 2.2 minimum target size.

    :param targets: as for ``WR_wcag22_touch_target_audit``
    :return: the number of elements checked
    """
    from je_web_runner.utils.wcag22_touch_target.touch import assert_no_violations
    assert_no_violations(_touch_target_violations(targets))
    return len(targets)


# ---------- pull_to_refresh ---------------------------------------------

def pull_to_refresh_snapshot_page(scroller_selector: str = "body") -> dict[str, Any]:
    """
    Read the overscroll behaviour, height and ``data-pull-threshold`` of the page's scroll container.

    :return: ``{"overscroll_y": str, "scroller_height": n, "pull_threshold_attr": str}``
    """
    from je_web_runner.utils.pull_to_refresh.refresh import HARVEST_SCRIPT, PullToRefreshError
    payload = _harvest("WR_pull_to_refresh_snapshot_page", HARVEST_SCRIPT, scroller_selector)
    if not isinstance(payload, dict):
        raise PullToRefreshError("the page returned no scroller snapshot")
    return dict(to_plain(payload))


def pull_to_refresh_assert_contained(payload: dict[str, Any]) -> str:
    """
    Fail when the scroller leaves ``overscroll-behavior-y`` at ``auto`` (the browser would also reload).

    :param payload: as returned by ``WR_pull_to_refresh_snapshot_page``
    :return: the scroller's ``overscroll-behavior-y``
    """
    from je_web_runner.utils.pull_to_refresh import refresh
    snapshot = refresh.parse_snapshot(payload)
    refresh.assert_overscroll_contained(snapshot)
    return str(snapshot.overscroll_y)


def pull_to_refresh_assert_threshold(payload: dict[str, Any], min_px: float = 60, max_px: float = 160) -> float:
    """
    Fail when the scroller's ``data-pull-threshold`` is missing or outside ``[min_px, max_px]``.

    :return: the threshold in pixels
    """
    from je_web_runner.utils.pull_to_refresh import refresh
    snapshot = refresh.parse_snapshot(payload)
    refresh.assert_threshold_sensible(snapshot, min_px=min_px, max_px=max_px)
    return float(snapshot.pull_threshold_px)


def pull_to_refresh_assert_triggered(fired: bool, network_refetched: bool) -> bool:
    """Fail unless the pull gesture ran the page's refresh handler and the handler fetched from the network."""
    from je_web_runner.utils.pull_to_refresh.refresh import RefreshEvent, assert_refresh_triggered
    assert_refresh_triggered(RefreshEvent(fired=bool(fired), network_refetched=bool(network_refetched)))
    return True


FRONTEND_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_dst_boundary_test_find": dst_boundary_test_find,
    "WR_dst_boundary_test_classify": dst_boundary_test_classify,
    "WR_dst_boundary_test_assert_no_duplicate_fires": dst_boundary_test_assert_no_duplicate_fires,
    "WR_dst_boundary_test_assert_fired_around": dst_boundary_test_assert_fired_around,
    "WR_forced_colors_mode_profiles": forced_colors_mode_profiles,
    "WR_forced_colors_mode_apply": forced_colors_mode_apply,
    "WR_forced_colors_mode_audit": forced_colors_mode_audit,
    "WR_forced_colors_mode_assert_no_invisible": forced_colors_mode_assert_no_invisible,
    "WR_number_currency_locale_check": number_currency_locale_check,
    "WR_number_currency_locale_assert_number": number_currency_locale_assert_number,
    "WR_number_currency_locale_assert_currency": number_currency_locale_assert_currency,
    "WR_number_currency_locale_assert_date": number_currency_locale_assert_date,
    "WR_ocr_assert_extract_text": ocr_assert_extract_text,
    "WR_ocr_assert_contains": ocr_assert_contains,
    "WR_ocr_assert_fuzzy": ocr_assert_fuzzy,
    "WR_ocr_assert_any": ocr_assert_any,
    "WR_ocr_assert_page_contains": ocr_assert_page_contains,
    "WR_pseudo_localization_text": pseudo_localization_text,
    "WR_pseudo_localization_catalogue": pseudo_localization_catalogue,
    "WR_pseudo_localization_scan": pseudo_localization_scan,
    "WR_pseudo_localization_scan_page": pseudo_localization_scan_page,
    "WR_pseudo_localization_assert_no_hardcoded": pseudo_localization_assert_no_hardcoded,
    "WR_rtl_layout_verify_check": rtl_layout_verify_check,
    "WR_rtl_layout_verify_assert": rtl_layout_verify_assert,
    "WR_screen_reader_runner_walk": screen_reader_runner_walk,
    "WR_screen_reader_runner_assert_no_violations": screen_reader_runner_assert_no_violations,
    "WR_screen_reader_runner_assert_reads": screen_reader_runner_assert_reads,
    "WR_visual_ai_hash": visual_ai_hash,
    "WR_visual_ai_compare": visual_ai_compare,
    "WR_visual_ai_assert_similar": visual_ai_assert_similar,
    "WR_visual_ai_assert_page_similar": visual_ai_assert_page_similar,
    "WR_wcag22_touch_target_audit": wcag22_touch_target_audit,
    "WR_wcag22_touch_target_audit_page": wcag22_touch_target_audit_page,
    "WR_wcag22_touch_target_assert": wcag22_touch_target_assert,
    "WR_pull_to_refresh_snapshot_page": pull_to_refresh_snapshot_page,
    "WR_pull_to_refresh_assert_contained": pull_to_refresh_assert_contained,
    "WR_pull_to_refresh_assert_threshold": pull_to_refresh_assert_threshold,
    "WR_pull_to_refresh_assert_triggered": pull_to_refresh_assert_triggered,
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset()
