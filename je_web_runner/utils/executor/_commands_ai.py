"""
AI 與語言模型相關函式庫的命令轉接層（第一部分）
Command adapters for the libraries around language-model features, part one: edge-case suites, the fuzz
explorer, failure tagging / narration / triage, hallucination probes, token cost, locator hardening,
screenshot questions, PR titles, prompt drift and prompt-injection grading.

No command here calls a model. Where a library wants a model client or an embedding callable, the command
takes what the model answered (or the vectors) as an argument and does the deterministic part: rendering
the prompt, parsing a reply, grading recorded answers.
"""
from __future__ import annotations

# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterator

from je_web_runner.utils.executor._command_helpers import to_plain

_DEFAULT_SAMPLE_STRINGS = ("test", "1234", "x")


def _build(factory: Callable[..., Any], data: Any, error: type[Exception], what: str) -> Any:
    """``factory(**data)``, with a wrong shape reported as the library's own ``error``."""
    if not isinstance(data, dict):
        raise error(f"{what} must be an object, got {type(data).__name__}")
    try:
        return factory(**data)
    except TypeError as failure:
        raise error(f"{what} has an unknown or missing field: {failure}") from failure


def _build_all(factory: Callable[..., Any], items: Any, error: type[Exception], what: str) -> list[Any]:
    """One ``factory`` object per entry of the list ``items``."""
    if not isinstance(items, list):
        raise error(f"{what}s must be a list, got {type(items).__name__}")
    return [_build(factory, item, error, what) for item in items]


def _member(enum_class: Callable[[str], Any], value: Any, error: type[Exception], what: str) -> Any:
    """The enum member whose value is ``value``, case-insensitively."""
    try:
        return enum_class(str(value).strip().lower())
    except ValueError as failure:
        raise error(f"unknown {what} {value!r}") from failure


# ---------- edge_case_generator ------------------------------------------

def _edge_suite(suite: Any) -> Any:
    from je_web_runner.utils.edge_case_generator.generator import (
        EdgeCase, EdgeCaseCategory, EdgeCaseGeneratorError, EdgeCaseSuite,
    )
    if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
        raise EdgeCaseGeneratorError("suite must be an object with a 'cases' list")
    cases = []
    for raw in suite["cases"]:
        if not isinstance(raw, dict):
            raise EdgeCaseGeneratorError(f"edge case must be an object, got {type(raw).__name__}")
        category = _member(EdgeCaseCategory, raw.get("category", "boundary"), EdgeCaseGeneratorError, "category")
        cases.append(_build(EdgeCase, {**raw, "category": category}, EdgeCaseGeneratorError, "edge case"))
    return EdgeCaseSuite(source_test_name=str(suite.get("source_test_name") or "<unnamed>"), cases=cases)


def edge_case_generator_categories() -> list[str]:
    """List the edge-case categories a suite may use (boundary, unicode, network, ...)."""
    from je_web_runner.utils.edge_case_generator.generator import EdgeCaseCategory
    return [member.value for member in EdgeCaseCategory]


def edge_case_generator_render_markdown(suite: dict[str, Any]) -> str:
    """
    Render an edge-case suite as a markdown table for a PR comment.

    :param suite: ``{"source_test_name": ..., "cases": [{"name", "category", "rationale", "actions",
        "expected_outcome", "severity"}, ...]}``
    """
    from je_web_runner.utils.edge_case_generator.generator import render_suite_markdown
    return render_suite_markdown(_edge_suite(suite))


def edge_case_generator_write_suite(
        suite: dict[str, Any], output_dir: str, filename_prefix: str | None = None) -> list[str]:
    """Write each case of an edge-case suite as its own action file in ``output_dir``; returns the paths."""
    from je_web_runner.utils.edge_case_generator.generator import write_suite_to_dir
    return to_plain(write_suite_to_dir(_edge_suite(suite), output_dir, filename_prefix=filename_prefix))


# ---------- exploratory_ai -----------------------------------------------

def _observation(data: Any, step: int) -> Any:
    from je_web_runner.utils.exploratory_ai.explorer import (
        ExploratoryAiError, InteractiveElement, PageObservation,
    )
    if not isinstance(data, dict):
        raise ExploratoryAiError(f"observation must be an object, got {type(data).__name__}")
    return PageObservation(
        url=str(data.get("url") or ""),
        title=str(data.get("title") or ""),
        elements=_build_all(InteractiveElement, data.get("elements") or [], ExploratoryAiError, "element"),
        console_errors=[str(message) for message in data.get("console_errors") or []],
        network_errors=list(data.get("network_errors") or []),
        step=step,
    )


def _ignore_action(_action: Any) -> None:
    """The replay performs nothing: the observations were recorded beforehand."""


def exploratory_ai_plan(
        observation: dict[str, Any], seed: int | None = None,
        sample_strings: list[str] | None = None, type_bias: float = 0.3) -> dict[str, Any]:
    """
    Pick the next fuzz step (click / type / done) for a page observation, repeatable with ``seed``.

    :param observation: ``{"url", "title", "elements": [{"selector", "tag", "text", "role", "is_visible",
        "is_enabled"}, ...]}``
    """
    from je_web_runner.utils.exploratory_ai.explorer import RandomPlanner
    planner = RandomPlanner(
        seed=seed, sample_strings=sample_strings or _DEFAULT_SAMPLE_STRINGS, type_bias=type_bias)
    return to_plain(planner.plan(_observation(observation, 0)))


def exploratory_ai_replay(observations: list[dict[str, Any]], stop_on_bugs: int = 0) -> dict[str, Any]:
    """
    Walk recorded page observations and report the bug signals in them (console and network errors).

    Each observation may add ``console_errors`` (texts) and ``network_errors`` (``{"status", "url"}``) to
    the shape ``WR_exploratory_ai_plan`` takes. Nothing is clicked. ``stop_on_bugs`` stops the walk once
    that many signals were seen (0 walks them all).
    """
    from je_web_runner.utils.exploratory_ai.explorer import (
        ActionKind, Explorer, ExploratoryAiError, PlannedAction,
    )
    if not isinstance(observations, list):
        raise ExploratoryAiError("observations must be a list")
    recorded = [_observation(item, step) for step, item in enumerate(observations)]
    next_page = PlannedAction(kind=ActionKind.SCROLL, rationale="replay of recorded observations")
    explorer = Explorer(
        observer=SimpleNamespace(observe=recorded.__getitem__),
        planner=SimpleNamespace(plan=lambda _observation: next_page),
        executor=_ignore_action,
        max_steps=len(recorded), max_repeat_loops=len(recorded), stop_on_bugs=stop_on_bugs,
    )
    report = explorer.run()
    return {
        "steps_taken": report.steps_taken, "pages_visited": list(report.pages_visited),
        "bugs": to_plain(report.bugs), "has_bugs": report.has_bugs(), "stopped_reason": report.stopped_reason,
    }


# ---------- failure_auto_tag ---------------------------------------------

def _tags(tags: Any) -> list[Any]:
    from je_web_runner.utils.failure_auto_tag.tag import FailureAutoTagError, Tag
    return _build_all(Tag, tags, FailureAutoTagError, "tag")


def failure_auto_tag_heuristic(
        exception_text: str = "", last_action: str = "", console_errors: list[str] | None = None,
        network_errors: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """
    Tag a failure (flaky-locator, timeout, network-5xx, js-error, ...) from its error text and logs.

    :param network_errors: ``[{"status": 503, "url": ...}, ...]``
    """
    from je_web_runner.utils.failure_auto_tag.tag import FailureBundle, heuristic_tags
    bundle = FailureBundle(
        exception_text=exception_text, last_action=last_action,
        console_errors=list(console_errors or []), network_errors=list(network_errors or []),
    )
    return to_plain(heuristic_tags(bundle))


def failure_auto_tag_merge(tag_lists: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Merge several tag lists (``[{"name", "confidence", "reason"}, ...]``), keeping the surest of each name."""
    from je_web_runner.utils.failure_auto_tag.tag import FailureAutoTagError, merge_tags
    if not isinstance(tag_lists, list):
        raise FailureAutoTagError("tag_lists must be a list of tag lists")
    return to_plain(merge_tags(*[_tags(stream) for stream in tag_lists]))


def failure_auto_tag_assert_tagged(tags: list[dict[str, Any]], expected: str) -> str:
    """Fail unless a tag named ``expected`` is in ``tags``."""
    from je_web_runner.utils.failure_auto_tag.tag import assert_tagged_with
    assert_tagged_with(_tags(tags), expected)
    return expected


# ---------- failure_narrator ---------------------------------------------

def failure_narrator_load_bundle(path: str) -> dict[str, Any]:
    """Read a failure-bundle directory (``meta.json``, ``dom.html``, ``console.log``, ...) as failure facts."""
    from je_web_runner.utils.failure_narrator.narrator import load_bundle_dir
    return to_plain(load_bundle_dir(path))


def failure_narrator_build_prompt(bundle: dict[str, Any]) -> str:
    """
    Render the "why did this test fail" prompt to send to a language model.

    :param bundle: failure facts, ``test_id`` required; also ``action``, ``error_message``, ``error_class``,
        ``last_url``, ``last_dom_excerpt``, ``console_errors``, ``network_errors``, ``failed_assertion``,
        ``git_commit``, ``flake_history``, ``extra_context``
    """
    from je_web_runner.utils.failure_narrator.narrator import FailureBundle, FailureNarratorError, build_prompt
    return build_prompt(_build(FailureBundle, bundle, FailureNarratorError, "bundle"))


def failure_narrator_parse_response(raw: str) -> dict[str, Any]:
    """Parse a model's failure-summary reply into summary / likely_cause / next_step / confidence / markdown."""
    from je_web_runner.utils.failure_narrator.narrator import parse_response
    report = parse_response(raw)
    return {**to_plain(report), "markdown": report.markdown()}


# ---------- failure_triage -----------------------------------------------

def failure_triage_extract_signals(
        bundle_path: str, steps: list[Any] | None = None, max_steps: int = 12) -> dict[str, Any]:
    """Read a failure-bundle zip and return what a root-cause analysis needs: error, last steps, log tails."""
    from je_web_runner.utils.failure_triage.triage import extract_signals_from_bundle
    return to_plain(extract_signals_from_bundle(bundle_path, steps=steps, max_steps=max_steps))


def failure_triage_render_markdown(report: dict[str, Any], heading_level: int = 2) -> str:
    """
    Render a root-cause report as markdown for a PR comment.

    :param report: ``{"likely_cause", "category", "evidence": [...], "next_steps": [...], "suggested_fix",
        "confidence"}``, optionally ``test_name`` and ``error_signature``
    """
    from je_web_runner.utils.failure_triage.triage import FailureTriageError, TriageReport, render_markdown
    return render_markdown(
        _build(TriageReport, report, FailureTriageError, "report"), heading_level=heading_level)


# ---------- hallucination_probe ------------------------------------------

def _probe_report(probes: Any, answers: Any) -> Any:
    from je_web_runner.utils.hallucination_probe.probe import HallucinationProbeError, Probe, run_probes
    built = _build_all(Probe, probes, HallucinationProbeError, "probe")
    if not isinstance(answers, dict):
        raise HallucinationProbeError("answers must be an object of probe name to answer text")
    missing = [probe.name for probe in built if probe.name not in answers]
    if missing:
        raise HallucinationProbeError(f"no recorded answer for probe(s): {missing}")
    pending = iter([str(answers[probe.name]) for probe in built])
    return run_probes(built, lambda _prompt: next(pending))


def hallucination_probe_evaluate(probes: list[dict[str, Any]], answers: dict[str, str]) -> dict[str, Any]:
    """
    Grade the answers a model gave to ground-truth probes and return the hallucination rate.

    :param probes: ``[{"name", "prompt", "expected_substrings", "forbidden_substrings", "expect_refusal"}]``
    :param answers: probe name to the answer text the model gave
    """
    report = _probe_report(probes, answers)
    return {"results": to_plain(report.results), "hallucination_rate": report.hallucination_rate}


def hallucination_probe_assert_rate(
        probes: list[dict[str, Any]], answers: dict[str, str], max_rate: float = 0.0) -> float:
    """Fail when more than ``max_rate`` (0 to 1) of the graded probe answers are wrong; returns the rate."""
    from je_web_runner.utils.hallucination_probe.probe import assert_hallucination_rate_under
    report = _probe_report(probes, answers)
    assert_hallucination_rate_under(report, max_rate=max_rate)
    return float(report.hallucination_rate)


# ---------- llm_token_cost_tracker ---------------------------------------

def _call_records(records: Any) -> list[Any]:
    from je_web_runner.utils.llm_token_cost_tracker.tracker import CallRecord, LlmTokenCostError
    return _build_all(CallRecord, records, LlmTokenCostError, "call record")


def llm_token_cost_tracker_tally(
        records: list[dict[str, Any]], rate_card: dict[str, dict[str, float]] | None = None) -> dict[str, Any]:
    """
    Add up tokens and dollars of recorded model calls, in total and per test.

    :param records: ``[{"model", "input_tokens", "output_tokens", "test_name"}, ...]``
    :param rate_card: extra or replacing prices, ``{model: {"input": usd_per_1k, "output": usd_per_1k}}``
    """
    from je_web_runner.utils.llm_token_cost_tracker.tracker import tally, tally_by_test
    calls = _call_records(records)
    return {
        "total": to_plain(tally(calls, rate_card_override=rate_card)),
        "by_test": to_plain(tally_by_test(calls, rate_card_override=rate_card)),
    }


def llm_token_cost_tracker_top_spenders(
        records: list[dict[str, Any]], top_n: int = 5,
        rate_card: dict[str, dict[str, float]] | None = None) -> list[dict[str, Any]]:
    """List the ``top_n`` tests that spent the most on model calls."""
    from je_web_runner.utils.llm_token_cost_tracker.tracker import tally_by_test, top_spenders
    by_test = tally_by_test(_call_records(records), rate_card_override=rate_card)
    return to_plain(top_spenders(by_test, top_n=top_n))


def llm_token_cost_tracker_assert_under_budget(
        records: list[dict[str, Any]], max_usd: float,
        rate_card: dict[str, dict[str, float]] | None = None) -> dict[str, Any]:
    """Fail when the recorded model calls cost more than ``max_usd``; returns the total."""
    from je_web_runner.utils.llm_token_cost_tracker.tracker import assert_under_budget, tally
    total = tally(_call_records(records), rate_card_override=rate_card)
    assert_under_budget(total, max_usd=max_usd)
    return to_plain(total)


# ---------- locator_hardener ---------------------------------------------

def _fragile_locator(strategy: str, value: str, test_id: str, dom_excerpt: str, failure_history: int) -> Any:
    from je_web_runner.utils.locator_hardener.hardener import (
        FragileLocator, LocatorHardenerError, LocatorStrategy,
    )
    member = _member(LocatorStrategy, str(strategy).replace("_", " "), LocatorHardenerError, "strategy")
    return FragileLocator(
        test_id=test_id, strategy=member, value=value, dom_excerpt=dom_excerpt, failure_history=failure_history)


def locator_hardener_score(
        strategy: str, value: str, test_id: str = "action", failure_history: int = 0) -> dict[str, Any]:
    """
    Score how fragile a locator is (0 to 1, with reasons); 0.5 and above is worth replacing.

    :param strategy: ``id``, ``name``, ``css selector``, ``xpath``, ``link text``, ``partial link text``,
        ``class name`` or ``tag name`` (``CSS_SELECTOR`` style spelling is accepted)
    """
    from je_web_runner.utils.locator_hardener.hardener import score_fragility
    return to_plain(score_fragility(_fragile_locator(strategy, value, test_id, "", failure_history)))


def locator_hardener_build_prompt(
        strategy: str, value: str, test_id: str = "action", dom_excerpt: str = "",
        failure_history: int = 0) -> str:
    """Render the prompt that asks a language model for sturdier replacements of a locator."""
    from je_web_runner.utils.locator_hardener.hardener import build_prompt
    return build_prompt(_fragile_locator(strategy, value, test_id, dom_excerpt, failure_history))


def locator_hardener_parse_suggestions(raw: str) -> list[dict[str, Any]]:
    """Parse a model's locator suggestions, dropping malformed ones and those that are fragile again."""
    from je_web_runner.utils.locator_hardener.hardener import parse_suggestions
    return to_plain(parse_suggestions(raw))


# ---------- multimodal_qa ------------------------------------------------

def multimodal_qa_build_request(
        image_path: str, question: str, rubric: list[str] | None = None) -> dict[str, str]:
    """Build what to send a vision model about a screenshot: the prompt and the image as base64."""
    from je_web_runner.utils.multimodal_qa.qa import MultimodalQaError, QaRequest, build_prompt
    path = Path(image_path)
    if not path.is_file():
        raise MultimodalQaError(f"image not found: {path}")
    request = QaRequest(
        image_bytes=path.read_bytes(), question=question, rubric=list(rubric or []), image_label=str(path))
    return {"prompt": build_prompt(request), "image_b64": request.b64_image(), "image_label": str(path)}


def multimodal_qa_parse_response(raw: str) -> dict[str, Any]:
    """Parse a vision model's reply into verdict (pass / fail / uncertain), confidence, rationale, issues."""
    from je_web_runner.utils.multimodal_qa.qa import parse_response
    return to_plain(parse_response(raw))


def multimodal_qa_assert_passes(raw: str, min_confidence: float = 0.6) -> dict[str, Any]:
    """Fail unless a vision model's reply is a ``pass`` with at least ``min_confidence``."""
    from je_web_runner.utils.multimodal_qa.qa import assert_passes, parse_response
    response = parse_response(raw)
    assert_passes(response, min_confidence=min_confidence)
    return to_plain(response)


# ---------- pr_title_generator -------------------------------------------

def pr_title_generator_suggest(files: list[str], commits: list[str], breaking: bool = False) -> str:
    """Suggest a Conventional Commits PR title from the changed file paths and the commit subjects."""
    from je_web_runner.utils.pr_title_generator.generate import suggest_title
    return suggest_title(files, commits, breaking=breaking)


def pr_title_generator_assert_conventional(title: str) -> str:
    """Fail unless ``title`` follows Conventional Commits (``type(scope): summary``)."""
    from je_web_runner.utils.pr_title_generator.generate import assert_conventional
    assert_conventional(title)
    return title


# ---------- prompt_drift_monitor -----------------------------------------

def prompt_drift_monitor_save_baseline(samples: list[dict[str, Any]], path: str) -> str:
    """
    Write reference answers and their embedding vectors to a baseline file; returns its path.

    :param samples: ``[{"prompt_id", "prompt", "answer", "embedding": [...], "must_include": [...],
        "must_exclude": [...]}, ...]``
    """
    from je_web_runner.utils.prompt_drift_monitor.monitor import (
        Baseline, BaselineSample, PromptDriftError, save_baseline,
    )
    built = _build_all(BaselineSample, samples, PromptDriftError, "sample")
    captured_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    return str(save_baseline(Baseline(samples=built, captured_at=captured_at), path))


def prompt_drift_monitor_load_baseline(path: str) -> dict[str, Any]:
    """Read a prompt-drift baseline file: its samples (with their prompts to ask again) and capture time."""
    from je_web_runner.utils.prompt_drift_monitor.monitor import load_baseline
    return to_plain(load_baseline(path))


def _drift_report(baseline_path: str, current: Any, similarity_threshold: float) -> Any:
    from je_web_runner.utils.prompt_drift_monitor.monitor import PromptDriftError, check_drift, load_baseline
    baseline = load_baseline(baseline_path)
    if not isinstance(current, list):
        raise PromptDriftError("current must be a list of {prompt_id, answer, embedding}")
    by_id = {str(item.get("prompt_id")): item for item in current if isinstance(item, dict)}
    missing = [sample.prompt_id for sample in baseline.samples if sample.prompt_id not in by_id]
    if missing:
        raise PromptDriftError(f"no current answer for prompt(s): {missing}")
    ordered = [by_id[sample.prompt_id] for sample in baseline.samples]
    answers = iter([str(item.get("answer") or "") for item in ordered])
    vectors: Iterator[Any] = iter([item.get("embedding") for item in ordered])
    return check_drift(
        baseline, lambda _text: next(vectors), lambda _prompt: next(answers),
        similarity_threshold=similarity_threshold,
    )


def prompt_drift_monitor_check(
        baseline_path: str, current: list[dict[str, Any]], similarity_threshold: float = 0.85) -> dict[str, Any]:
    """
    Compare today's answers with a baseline file: embedding similarity plus required / forbidden phrases.

    :param current: ``[{"prompt_id", "answer", "embedding": [...]}, ...]``, one per baseline sample
    """
    report = _drift_report(baseline_path, current, similarity_threshold)
    drifted = [finding.prompt_id for finding in report.drifted_findings()]
    return {**to_plain(report), "passed": report.passed(), "drifted": drifted}


def prompt_drift_monitor_assert_no_drift(
        baseline_path: str, current: list[dict[str, Any]], similarity_threshold: float = 0.85) -> int:
    """Fail when any current answer drifted from the baseline file; returns how many were compared."""
    from je_web_runner.utils.prompt_drift_monitor.monitor import assert_no_drift
    report = _drift_report(baseline_path, current, similarity_threshold)
    assert_no_drift(report)
    return len(report.findings)


# ---------- prompt_injection_scanner -------------------------------------

def _payloads(payloads: Any) -> list[Any]:
    from je_web_runner.utils.prompt_injection_scanner.scanner import (
        DEFAULT_PAYLOADS, Payload, PromptInjectionScannerError, Severity,
    )
    if payloads is None:
        return list(DEFAULT_PAYLOADS)
    if not isinstance(payloads, list):
        raise PromptInjectionScannerError("payloads must be a list")
    built = []
    for raw in payloads:
        if not isinstance(raw, dict):
            raise PromptInjectionScannerError(f"payload must be an object, got {type(raw).__name__}")
        fields = {
            **raw,
            "severity": _member(Severity, raw.get("severity", "medium"), PromptInjectionScannerError, "severity"),
            "leak_indicators": tuple(raw.get("leak_indicators") or ()),
            "expected_refusal_markers": tuple(raw.get("expected_refusal_markers") or ()),
        }
        built.append(_build(Payload, fields, PromptInjectionScannerError, "payload"))
    return built


def _injection_report(responses: Any, payloads: Any) -> Any:
    from je_web_runner.utils.prompt_injection_scanner.scanner import PromptInjectionScannerError, scan
    known = _payloads(payloads)
    if not isinstance(responses, dict):
        raise PromptInjectionScannerError("responses must be an object of payload name to response text")
    unknown = sorted(set(responses) - {payload.name for payload in known})
    if unknown:
        raise PromptInjectionScannerError(f"responses name unknown payload(s): {unknown}")
    graded = [payload for payload in known if payload.name in responses]
    recorded = {payload.prompt: str(responses[payload.name]) for payload in graded}
    return scan(SimpleNamespace(ask=recorded.__getitem__), payloads=graded)


def prompt_injection_scanner_payloads() -> list[dict[str, Any]]:
    """List the built-in prompt-injection payloads: the prompt to send your app and what a leak looks like."""
    from je_web_runner.utils.prompt_injection_scanner.scanner import DEFAULT_PAYLOADS
    return to_plain(DEFAULT_PAYLOADS)


def prompt_injection_scanner_grade(
        responses: dict[str, str], payloads: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """
    Grade what your app answered to prompt-injection payloads: which ones leaked, which were refused.

    :param responses: payload name to the response text
    :param payloads: your own ``[{"name", "prompt", "severity", "leak_indicators",
        "expected_refusal_markers"}, ...]`` instead of the built-in ones
    """
    report = _injection_report(responses, payloads)
    leaks = [finding.payload for finding in report.leaks()]
    return {"findings": to_plain(report.findings), "passed": report.passed(), "leaks": leaks}


def prompt_injection_scanner_assert_no_leaks(
        responses: dict[str, str], minimum_severity: str = "high",
        payloads: list[dict[str, Any]] | None = None) -> int:
    """Fail when a graded response leaked at ``minimum_severity`` or above; returns how many were graded."""
    from je_web_runner.utils.prompt_injection_scanner.scanner import (
        PromptInjectionScannerError, Severity, assert_no_leaks,
    )
    report = _injection_report(responses, payloads)
    threshold = _member(Severity, minimum_severity, PromptInjectionScannerError, "severity")
    assert_no_leaks(report, minimum_severity=threshold)
    return len(report.findings)


AI_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_edge_case_generator_categories": edge_case_generator_categories,
    "WR_edge_case_generator_render_markdown": edge_case_generator_render_markdown,
    "WR_edge_case_generator_write_suite": edge_case_generator_write_suite,
    "WR_exploratory_ai_plan": exploratory_ai_plan,
    "WR_exploratory_ai_replay": exploratory_ai_replay,
    "WR_failure_auto_tag_heuristic": failure_auto_tag_heuristic,
    "WR_failure_auto_tag_merge": failure_auto_tag_merge,
    "WR_failure_auto_tag_assert_tagged": failure_auto_tag_assert_tagged,
    "WR_failure_narrator_load_bundle": failure_narrator_load_bundle,
    "WR_failure_narrator_build_prompt": failure_narrator_build_prompt,
    "WR_failure_narrator_parse_response": failure_narrator_parse_response,
    "WR_failure_triage_extract_signals": failure_triage_extract_signals,
    "WR_failure_triage_render_markdown": failure_triage_render_markdown,
    "WR_hallucination_probe_evaluate": hallucination_probe_evaluate,
    "WR_hallucination_probe_assert_rate": hallucination_probe_assert_rate,
    "WR_llm_token_cost_tracker_tally": llm_token_cost_tracker_tally,
    "WR_llm_token_cost_tracker_top_spenders": llm_token_cost_tracker_top_spenders,
    "WR_llm_token_cost_tracker_assert_under_budget": llm_token_cost_tracker_assert_under_budget,
    "WR_locator_hardener_score": locator_hardener_score,
    "WR_locator_hardener_build_prompt": locator_hardener_build_prompt,
    "WR_locator_hardener_parse_suggestions": locator_hardener_parse_suggestions,
    "WR_multimodal_qa_build_request": multimodal_qa_build_request,
    "WR_multimodal_qa_parse_response": multimodal_qa_parse_response,
    "WR_multimodal_qa_assert_passes": multimodal_qa_assert_passes,
    "WR_pr_title_generator_suggest": pr_title_generator_suggest,
    "WR_pr_title_generator_assert_conventional": pr_title_generator_assert_conventional,
    "WR_prompt_drift_monitor_save_baseline": prompt_drift_monitor_save_baseline,
    "WR_prompt_drift_monitor_load_baseline": prompt_drift_monitor_load_baseline,
    "WR_prompt_drift_monitor_check": prompt_drift_monitor_check,
    "WR_prompt_drift_monitor_assert_no_drift": prompt_drift_monitor_assert_no_drift,
    "WR_prompt_injection_scanner_payloads": prompt_injection_scanner_payloads,
    "WR_prompt_injection_scanner_grade": prompt_injection_scanner_grade,
    "WR_prompt_injection_scanner_assert_no_leaks": prompt_injection_scanner_assert_no_leaks,
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset()
