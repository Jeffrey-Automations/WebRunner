"""
AI 與語言模型相關函式庫的命令轉接層（第二部分）
Command adapters for the libraries around language-model features, part two: RAG grounding, story
prompts, streamed chat, test repair plans, duplicate tests, test descriptions, tool calls, walkthrough
documents, and the authoring helpers (formatter, workspace starter, Markdown, Selenium to Playwright).

No command here calls a model: a model's reply, recorded chunks, tool calls and embedding vectors are
arguments.
"""
from __future__ import annotations

# pylint: disable=import-outside-toplevel  # each library is imported by the command that uses it
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from je_web_runner.utils.executor._command_helpers import to_plain


def _split_action(action: Any) -> tuple[str, list[Any], dict[str, Any]] | None:
    """Command, positional and keyword arguments of an ``["WR_x", {...}]`` action; None for another shape."""
    if not isinstance(action, list) or not action or not isinstance(action[0], str):
        return None
    positional: list[Any] = []
    kwargs: dict[str, Any] = {}
    for part in action[1:3]:
        if isinstance(part, dict):
            kwargs = part
        elif isinstance(part, list):
            positional = part
    return action[0], positional, kwargs


# ---------- rag_grounding_assert -----------------------------------------

def _rag_inputs(answer: str, chunks: Any, cited_chunk_ids: Any = None) -> tuple[Any, list[Any]]:
    from je_web_runner.utils.rag_grounding_assert.grounding import Chunk, RagAnswer, RagGroundingError
    if not isinstance(chunks, list) or not all(isinstance(item, dict) for item in chunks):
        raise RagGroundingError("chunks must be a list of {chunk_id, text}")
    retrieved = [
        Chunk(chunk_id=str(item.get("chunk_id") or ""), text=str(item.get("text") or "")) for item in chunks
    ]
    cited = [str(chunk_id) for chunk_id in cited_chunk_ids or []]
    return RagAnswer(text=answer, cited_chunk_ids=cited), retrieved


def rag_grounding_assert_score(
        answer: str, chunks: list[dict[str, str]], min_phrase_len: int = 4) -> dict[str, Any]:
    """
    Measure how well a RAG answer is covered by the retrieved chunks.

    :param chunks: ``[{"chunk_id", "text"}, ...]``
    :return: ``overlap`` (share of the answer's words found in the chunks) and ``unsupported_phrases``
        (runs of ``min_phrase_len`` words that are in no chunk)
    """
    from je_web_runner.utils.rag_grounding_assert.grounding import find_unsupported_claims, lexical_overlap_score
    rag_answer, retrieved = _rag_inputs(answer, chunks)
    return {
        "overlap": lexical_overlap_score(rag_answer, retrieved),
        "unsupported_phrases": find_unsupported_claims(rag_answer, retrieved, min_phrase_len=min_phrase_len),
    }


def rag_grounding_assert_citations(
        answer: str, chunks: list[dict[str, str]], cited_chunk_ids: list[str], minimum: int = 1) -> int:
    """Fail when the answer cites a chunk that was not retrieved, or fewer than ``minimum`` chunks."""
    from je_web_runner.utils.rag_grounding_assert.grounding import (
        assert_citations_in_retrieved, assert_min_citations,
    )
    rag_answer, retrieved = _rag_inputs(answer, chunks, cited_chunk_ids)
    assert_citations_in_retrieved(rag_answer, retrieved)
    assert_min_citations(rag_answer, minimum=minimum)
    return len(rag_answer.cited_chunk_ids)


def rag_grounding_assert_grounded(answer: str, chunks: list[dict[str, str]], min_overlap: float = 0.5) -> float:
    """Fail when less than ``min_overlap`` of the answer's words appear in the retrieved chunks."""
    from je_web_runner.utils.rag_grounding_assert.grounding import assert_grounded, lexical_overlap_score
    rag_answer, retrieved = _rag_inputs(answer, chunks)
    assert_grounded(rag_answer, retrieved, min_overlap=min_overlap)
    return float(lexical_overlap_score(rag_answer, retrieved))


def rag_grounding_assert_no_hallucination(
        answer: str, chunks: list[dict[str, str]], max_unsupported_phrases: int = 0,
        min_phrase_len: int = 4) -> list[str]:
    """Fail when the answer has more than ``max_unsupported_phrases`` word runs found in no retrieved chunk."""
    from je_web_runner.utils.rag_grounding_assert.grounding import (
        assert_no_hallucination, find_unsupported_claims,
    )
    rag_answer, retrieved = _rag_inputs(answer, chunks)
    assert_no_hallucination(
        rag_answer, retrieved, max_unsupported_phrases=max_unsupported_phrases, min_phrase_len=min_phrase_len)
    return find_unsupported_claims(rag_answer, retrieved, min_phrase_len=min_phrase_len)


# ---------- story_to_actions ---------------------------------------------

def story_to_actions_build_prompt(
        story: str, start_url: str | None = None, figma_hints: list[dict[str, Any]] | None = None,
        style_notes: list[str] | None = None) -> str:
    """
    Render the prompt that asks a language model to turn a user story into an action list.

    :param figma_hints: ``[{"name", "type", "selector_hint", "text"}, ...]``
    """
    from je_web_runner.utils.story_to_actions.generator import (
        FigmaHint, StoryPrompt, StoryToActionsError, build_prompt_text,
    )
    hints = []
    for raw in figma_hints or []:
        if not isinstance(raw, dict):
            raise StoryToActionsError(f"figma hint must be an object, got {type(raw).__name__}")
        hints.append(FigmaHint(
            name=str(raw.get("name") or ""), type=str(raw.get("type") or ""),
            selector_hint=raw.get("selector_hint"), text=raw.get("text"),
        ))
    prompt = StoryPrompt(story=story, start_url=start_url, figma_hints=hints, style_notes=list(style_notes or []))
    return build_prompt_text(prompt)


def story_to_actions_parse_reply(reply: str, start_url: str | None = None) -> list[dict[str, Any]]:
    """
    Parse and validate the action list a model replied with (a JSON array, optionally in a code fence).

    The entries are in the reply format ``{"WR_command": [arguments]}``. With ``start_url``, a
    ``WR_to_url`` to it is put first unless the reply already opens with one.
    """
    from je_web_runner.utils.story_to_actions.generator import StoryPrompt, generate_actions
    prompt = StoryPrompt(story="reply given as text", start_url=start_url)
    return generate_actions(prompt, SimpleNamespace(generate=lambda _prompt: reply))


def story_to_actions_validate(actions: list[dict[str, Any]]) -> int:
    """Fail when a ``{"WR_command": [arguments]}`` list uses a command or arguments a story may not produce."""
    from je_web_runner.utils.story_to_actions.generator import validate_actions
    validate_actions(actions)
    return len(actions)


# ---------- streaming_chat_assert ----------------------------------------

def _deltas(deltas: Any) -> list[Any]:
    from je_web_runner.utils.streaming_chat_assert.stream import parse_deltas
    return parse_deltas(deltas)


def streaming_chat_assert_summary(deltas: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Summarise a recorded chat stream: the assembled text, time to first token, longest gap.

    :param deltas: ``[{"text", "ts_ms", "seq"}, ...]`` in arrival order, ``ts_ms`` counted from the request
    """
    from je_web_runner.utils.streaming_chat_assert.stream import (
        assemble, max_inter_token_gap_ms, time_to_first_token,
    )
    parsed = _deltas(deltas)
    text = assemble(parsed)
    return {
        "text": text,
        "chunks": len(parsed),
        "ttft_ms": time_to_first_token(parsed) if text else None,
        "max_gap_ms": max_inter_token_gap_ms(parsed),
    }


def streaming_chat_assert_timing(
        deltas: list[dict[str, Any]], max_ttft_ms: float | None = None,
        max_gap_ms: float | None = None) -> dict[str, Any]:
    """Fail when the first token came later than ``max_ttft_ms`` or two tokens were over ``max_gap_ms`` apart."""
    from je_web_runner.utils.streaming_chat_assert.stream import assert_no_stall, assert_ttft_under
    parsed = _deltas(deltas)
    if max_ttft_ms is not None:
        assert_ttft_under(parsed, max_ms=max_ttft_ms)
    if max_gap_ms is not None:
        assert_no_stall(parsed, max_gap_ms=max_gap_ms)
    summary = streaming_chat_assert_summary(deltas)
    return {"ttft_ms": summary["ttft_ms"], "max_gap_ms": summary["max_gap_ms"]}


def streaming_chat_assert_content(deltas: list[dict[str, Any]], expected: str = "") -> str:
    """Fail when the assembled stream has a broken UTF-8 character or lacks ``expected``; returns the text."""
    from je_web_runner.utils.streaming_chat_assert.stream import (
        assemble, assert_assembled_contains, assert_utf8_clean,
    )
    parsed = _deltas(deltas)
    assert_utf8_clean(parsed)
    if expected:
        assert_assembled_contains(parsed, expected=expected)
    return assemble(parsed)


def streaming_chat_assert_order(deltas: list[dict[str, Any]]) -> int:
    """Fail when numbered chunks (``seq``) arrived twice or out of order; returns how many were numbered."""
    from je_web_runner.utils.streaming_chat_assert.stream import assert_no_dup_or_oos
    parsed = _deltas(deltas)
    assert_no_dup_or_oos(parsed)
    return sum(1 for delta in parsed if delta.seq is not None)


# ---------- test_auto_repair ---------------------------------------------

def _repair_plan(plan: Any) -> Any:
    from je_web_runner.utils.test_auto_repair.repair import RepairPlan, TestAutoRepairError
    if not isinstance(plan, dict) or not isinstance(plan.get("repaired_actions"), list):
        raise TestAutoRepairError("plan must be an object with a 'repaired_actions' list")
    try:
        confidence = float(plan.get("confidence") or 0.0)
    except (TypeError, ValueError) as failure:
        raise TestAutoRepairError(f"plan confidence must be a number: {failure}") from failure
    return RepairPlan(
        summary=str(plan.get("summary") or ""), confidence=confidence,
        repaired_actions=plan["repaired_actions"],
        changes=[change for change in plan.get("changes") or [] if isinstance(change, dict)],
        risks=[str(risk) for risk in plan.get("risks") or []],
    )


def test_auto_repair_git_diff(
        repo_dir: str = ".", since_ref: str = "HEAD~1", paths: list[str] | None = None,
        max_chars: int = 6000) -> str:
    """Read ``git diff <since_ref>..HEAD`` of a repository, cut to ``max_chars``; empty when git fails."""
    from je_web_runner.utils.test_auto_repair.repair import TestAutoRepairError, collect_git_diff
    if not isinstance(since_ref, str) or not since_ref or since_ref.startswith("-"):
        raise TestAutoRepairError(f"since_ref must be a git revision, got {since_ref!r}")
    return collect_git_diff(repo_dir, since_ref=since_ref, paths=paths, max_chars=max_chars)


def test_auto_repair_render_markdown(plan: dict[str, Any], heading_level: int = 2) -> str:
    """
    Render a test repair plan as markdown for a PR comment.

    :param plan: ``{"summary", "confidence", "repaired_actions": [...], "changes": [{"index", "kind",
        "why"}, ...], "risks": [...]}``
    """
    from je_web_runner.utils.test_auto_repair.repair import render_repair_markdown
    return render_repair_markdown(_repair_plan(plan), heading_level=heading_level)


def test_auto_repair_apply(
        action_path: str, plan: dict[str, Any], output_path: str | None = None,
        min_confidence: float = 0.5) -> str:
    """
    Write a repair plan's action list next to the action file (``<file>.repaired.json``) or to ``output_path``.

    Fails when the plan's confidence is below ``min_confidence``; returns the written path.
    """
    from je_web_runner.utils.test_auto_repair.repair import apply_repair
    written = apply_repair(
        action_path, _repair_plan(plan), output_path=output_path, min_confidence=min_confidence)
    return str(written)


# ---------- test_dedup_ai ------------------------------------------------

def _dedup_action(action: Any) -> Any:
    """An ``["WR_x", {...}]`` action in the ``{"WR_x": [arguments]}`` shape the dedup library reads."""
    split = _split_action(action)
    if split is None:
        return action
    command, positional, kwargs = split
    return {command: [*positional, *[kwargs[key] for key in sorted(kwargs)]]}


def _dedup_files(directory: str) -> list[Any]:
    from je_web_runner.utils.test_dedup_ai.dedup import ActionFile, TestDedupError, stable_fingerprint
    folder = Path(directory)
    if not folder.is_dir():
        raise TestDedupError(f"not a directory: {folder}")
    files = []
    for child in sorted(folder.glob("*.json")):
        try:
            data = json.loads(child.read_text(encoding="utf-8"))
        except ValueError as failure:
            raise TestDedupError(f"action file {child} is not JSON: {failure}") from failure
        if not isinstance(data, list):
            raise TestDedupError(f"action file {child} must contain a JSON list")
        actions = [_dedup_action(action) for action in data]
        files.append(ActionFile(path=str(child), actions=actions, fingerprint=stable_fingerprint(actions)))
    return files


def _cluster_result(clusters: list[Any]) -> dict[str, Any]:
    from je_web_runner.utils.test_dedup_ai.dedup import clusters_markdown
    return {"clusters": to_plain(clusters), "markdown": clusters_markdown(clusters)}


def test_dedup_ai_fingerprint(actions: list[Any]) -> str:
    """Hash the structure of an action list (commands and argument kinds, not the test data)."""
    from je_web_runner.utils.test_dedup_ai.dedup import stable_fingerprint
    return stable_fingerprint([_dedup_action(action) for action in actions])


def test_dedup_ai_structural(directory: str) -> dict[str, Any]:
    """Group the action files (``*.json``) of a directory that have the same structure; returns the clusters."""
    from je_web_runner.utils.test_dedup_ai.dedup import structural_clusters
    return _cluster_result(structural_clusters(_dedup_files(directory)))


def test_dedup_ai_semantic(
        directory: str, embeddings: dict[str, list[float]], similarity_threshold: float = 0.92) -> dict[str, Any]:
    """
    Group the action files of a directory whose embedding vectors are close (cosine similarity).

    :param embeddings: file name (``login.json``) to the vector you computed for that file
    """
    from je_web_runner.utils.test_dedup_ai.dedup import TestDedupError, semantic_clusters
    files = _dedup_files(directory)
    if not isinstance(embeddings, dict):
        raise TestDedupError("embeddings must be an object of file name to vector")
    missing = [Path(file.path).name for file in files if Path(file.path).name not in embeddings]
    if missing:
        raise TestDedupError(f"no embedding for file(s): {missing}")
    vectors = iter([embeddings[Path(file.path).name] for file in files])
    clusters = semantic_clusters(files, lambda _text: next(vectors), similarity_threshold=similarity_threshold)
    return _cluster_result(clusters)


# ---------- test_self_describe -------------------------------------------

def _describe_actions(actions: Any) -> Any:
    """``["WR_to_url", {"url": ...}]`` actions as the ``{"action_name": "to_url", ...}`` the library reads."""
    if not isinstance(actions, list):
        return actions
    converted = []
    for action in actions:
        split = _split_action(action)
        converted.append(action if split is None else {**split[2], "action_name": split[0].removeprefix("WR_")})
    return converted


def test_self_describe_summarise(actions: list[Any]) -> list[dict[str, str]]:
    """Describe each step of an action list as a ``Given`` / ``When`` / ``Then`` sentence."""
    from je_web_runner.utils.test_self_describe.describe import summarise
    return to_plain(summarise(_describe_actions(actions)))


def test_self_describe_describe(actions: list[Any], title: str = "") -> str:
    """Describe an action list as a Gherkin-style paragraph, under ``# title`` when one is given."""
    from je_web_runner.utils.test_self_describe.describe import describe
    return describe(_describe_actions(actions), title=title)


def test_self_describe_assert_mentions(actions: list[Any], needles: list[str], title: str = "") -> str:
    """Fail when the description of an action list lacks one of ``needles``; returns the description."""
    from je_web_runner.utils.test_self_describe.describe import assert_mentions, describe
    description = describe(_describe_actions(actions), title=title)
    assert_mentions(description, *needles)
    return description


# ---------- tool_call_assert ---------------------------------------------

def _tool_calls(calls: Any) -> list[Any]:
    from je_web_runner.utils.tool_call_assert.tool import parse_calls
    return parse_calls(calls)


def tool_call_assert_called(
        calls: list[dict[str, Any]], name: str, times: int | None = None,
        min_times: int | None = None, max_times: int | None = None) -> list[dict[str, Any]]:
    """
    Fail unless the model called tool ``name`` the expected number of times; returns those calls.

    :param calls: the recorded tool calls, ``[{"name", "arguments": {...}, "call_id"}, ...]``
    """
    from je_web_runner.utils.tool_call_assert.tool import assert_called
    if times is None and min_times is None and max_times is None:
        min_times = 1
    matches = assert_called(_tool_calls(calls), name=name, times=times, min_times=min_times, max_times=max_times)
    return to_plain(matches)


def tool_call_assert_not_called(calls: list[dict[str, Any]], denylist: list[str]) -> int:
    """Fail when the model called any tool named in ``denylist``; returns how many calls were checked."""
    from je_web_runner.utils.tool_call_assert.tool import assert_not_called
    parsed = _tool_calls(calls)
    assert_not_called(parsed, denylist=denylist)
    return len(parsed)


def tool_call_assert_schema(calls: list[dict[str, Any]], name: str, schema: dict[str, Any]) -> int:
    """
    Fail unless tool ``name`` was called and every such call's arguments match the JSON Schema.

    The check covers ``type``, ``required``, ``properties``, ``enum`` and ``additionalProperties: false``.
    """
    from je_web_runner.utils.tool_call_assert.tool import assert_args_match_schema, assert_called
    matches = assert_called(_tool_calls(calls), name=name, min_times=1)
    for call in matches:
        assert_args_match_schema(call, schema)
    return len(matches)


def tool_call_assert_order(calls: list[dict[str, Any]], expected: list[str]) -> list[str]:
    """Fail unless the tools were called exactly in the ``expected`` order of names."""
    from je_web_runner.utils.tool_call_assert.tool import assert_call_order
    assert_call_order(_tool_calls(calls), expected=expected)
    return list(expected)


# ---------- walkthrough_docs ---------------------------------------------

def _screenshots(screenshots: Any) -> dict[int, str | Path | bytes]:
    from je_web_runner.utils.walkthrough_docs.generator import WalkthroughError
    if screenshots is None:
        return {}
    if not isinstance(screenshots, dict):
        raise WalkthroughError("screenshots must be an object of action index to image path")
    try:
        return {int(index): str(path) for index, path in screenshots.items()}
    except ValueError as failure:
        raise WalkthroughError(f"screenshots keys must be action indexes: {failure}") from failure


def _walkthrough(spec: Any) -> Any:
    from je_web_runner.utils.walkthrough_docs.generator import Walkthrough, WalkthroughError, collect_steps
    if not isinstance(spec, dict):
        raise WalkthroughError(f"walkthrough must be an object, got {type(spec).__name__}")
    steps = collect_steps(spec.get("actions") or [], screenshots=_screenshots(spec.get("screenshots")))
    for step, narration in zip(steps, spec.get("narrations") or [], strict=False):
        step.narration = str(narration or "").strip()
    return Walkthrough(
        title=str(spec.get("title") or "Walkthrough"), description=str(spec.get("description") or ""),
        steps=steps, audience=str(spec.get("audience") or "end-user"),
    )


def walkthrough_docs_collect_steps(
        actions: list[Any], screenshots: dict[str, str] | None = None,
        skip_noise: bool = True) -> list[dict[str, Any]]:
    """
    List the steps of an action list worth documenting (waits, setup and teardown are skipped).

    :param screenshots: action index to the image file taken after that action
    """
    from je_web_runner.utils.walkthrough_docs.generator import collect_steps
    return to_plain(collect_steps(actions, screenshots=_screenshots(screenshots), skip_noise=skip_noise))


def walkthrough_docs_render(walkthrough: dict[str, Any], fmt: str = "markdown", embed_images: bool = True) -> str:
    """
    Render a step-by-step document from an action list, as ``markdown`` or ``confluence`` storage XHTML.

    :param walkthrough: ``{"title", "actions": [...], "narrations": [one sentence per documented step],
        "description", "audience", "screenshots": {action index: image path}}``; only ``actions`` is needed
    """
    from je_web_runner.utils.walkthrough_docs.generator import (
        WalkthroughError, render_confluence, render_markdown,
    )
    built = _walkthrough(walkthrough)
    if fmt == "markdown":
        return render_markdown(built, embed_images=embed_images)
    if fmt == "confluence":
        return render_confluence(built)
    raise WalkthroughError(f"unsupported fmt {fmt!r}")


def walkthrough_docs_save(walkthrough: dict[str, Any], output_path: str, fmt: str = "markdown") -> str:
    """Write the document ``WR_walkthrough_docs_render`` produces to ``output_path``; returns the path."""
    from je_web_runner.utils.walkthrough_docs.generator import save_walkthrough
    return str(save_walkthrough(_walkthrough(walkthrough), output_path, fmt=fmt))


# ---------- action_formatter ---------------------------------------------

def action_formatter_format(actions: list[Any], indent: int = 2) -> str:
    """Format an action list as canonical JSON text: one action per line, arguments in a fixed order."""
    from je_web_runner.utils.action_formatter.formatter import format_actions
    return format_actions(actions, indent=indent)


def action_formatter_format_file(path: str, write: bool = False, indent: int = 2) -> dict[str, Any]:
    """
    Format an action file; returns the formatted ``text`` and whether it ``changed``.

    The file is rewritten only with ``write`` true (and only when it changed).
    """
    from je_web_runner.utils.action_formatter.formatter import format_file
    text, changed = format_file(path, write=write, indent=indent)
    return {"text": text, "changed": changed}


def action_formatter_assert_formatted(path: str, indent: int = 2) -> str:
    """Fail when an action file is not in the canonical format; the file is left as it is."""
    from je_web_runner.utils.action_formatter.formatter import ActionFormatterError, format_file
    changed = format_file(path, write=False, indent=indent)[1]
    if changed:
        raise ActionFormatterError(f"action file is not formatted: {path}")
    return path


# ---------- bootstrapper -------------------------------------------------

def bootstrapper_starter_files() -> list[dict[str, str]]:
    """List the files a new WebRunner workspace starts with (relative path and content)."""
    from je_web_runner.utils.bootstrapper.bootstrapper import starter_files
    return to_plain(starter_files())


def bootstrapper_init_workspace(directory: str, overwrite: bool = False) -> dict[str, str]:
    """Create a starter workspace in ``directory``; returns each file as ``created`` or ``skipped``."""
    from je_web_runner.utils.bootstrapper.bootstrapper import init_workspace
    return init_workspace(directory, overwrite=overwrite)


# ---------- md_authoring -------------------------------------------------

def md_authoring_parse(text: str) -> list[list[Any]]:
    """Turn Markdown bullets (``- open <url>``, ``- click <selector>``, ...) into an action list."""
    from je_web_runner.utils.md_authoring.markdown_to_actions import parse_markdown
    return parse_markdown(text)


def md_authoring_transpile_file(md_path: str, output_path: str | None = None) -> list[list[Any]]:
    """Turn a Markdown file into an action list, written as an action file when ``output_path`` is given."""
    from je_web_runner.utils.md_authoring.markdown_to_actions import transpile_file
    return transpile_file(md_path, output_path)


def md_authoring_patterns() -> list[str]:
    """List the bullet sentences the Markdown authoring understands."""
    from je_web_runner.utils.md_authoring.markdown_to_actions import supported_bullet_patterns
    return supported_bullet_patterns()


# ---------- sel_to_pw ----------------------------------------------------

def sel_to_pw_translate_actions(actions: list[Any]) -> list[list[Any]]:
    """Rewrite the Selenium commands of an action list to their ``WR_pw_*`` Playwright commands."""
    from je_web_runner.utils.sel_to_pw.translator import translate_action_list
    return translate_action_list(actions)


def sel_to_pw_translate_for_backend(actions: list[Any] | dict[str, Any], backend: str = "playwright") -> Any:
    """
    Translate an action list or document to the commands of ``backend`` (``"playwright"`` from ``WR_*``,
    ``"selenium"`` from ``WR_pw_*``) and return it in the same shape. Unlike
    ``WR_sel_to_pw_translate_actions`` it converts arguments, walks blocks and ``meta``, and fails naming
    every command that has no faithful equivalent instead of passing it through.
    """
    from je_web_runner.utils.sel_to_pw.backend_translate import translate_for_backend
    return translate_for_backend(actions, backend)


def sel_to_pw_translate_python(source: str) -> list[dict[str, Any]]:
    """Translate Selenium Python source line by line; returns each changed line with its Playwright draft."""
    from je_web_runner.utils.sel_to_pw.translator import translate_python_source
    return to_plain(translate_python_source(source))


def sel_to_pw_supported() -> dict[str, list[str]]:
    """List what the Selenium to Playwright translator covers: action commands and Python patterns."""
    from je_web_runner.utils.sel_to_pw.translator import supported_action_commands, supported_python_patterns
    return {"action_commands": supported_action_commands(), "python_patterns": supported_python_patterns()}


AI_2_COMMANDS: dict[str, Callable[..., Any]] = {
    "WR_rag_grounding_assert_score": rag_grounding_assert_score,
    "WR_rag_grounding_assert_citations": rag_grounding_assert_citations,
    "WR_rag_grounding_assert_grounded": rag_grounding_assert_grounded,
    "WR_rag_grounding_assert_no_hallucination": rag_grounding_assert_no_hallucination,
    "WR_story_to_actions_build_prompt": story_to_actions_build_prompt,
    "WR_story_to_actions_parse_reply": story_to_actions_parse_reply,
    "WR_story_to_actions_validate": story_to_actions_validate,
    "WR_streaming_chat_assert_summary": streaming_chat_assert_summary,
    "WR_streaming_chat_assert_timing": streaming_chat_assert_timing,
    "WR_streaming_chat_assert_content": streaming_chat_assert_content,
    "WR_streaming_chat_assert_order": streaming_chat_assert_order,
    "WR_test_auto_repair_git_diff": test_auto_repair_git_diff,
    "WR_test_auto_repair_render_markdown": test_auto_repair_render_markdown,
    "WR_test_auto_repair_apply": test_auto_repair_apply,
    "WR_test_dedup_ai_fingerprint": test_dedup_ai_fingerprint,
    "WR_test_dedup_ai_structural": test_dedup_ai_structural,
    "WR_test_dedup_ai_semantic": test_dedup_ai_semantic,
    "WR_test_self_describe_summarise": test_self_describe_summarise,
    "WR_test_self_describe_describe": test_self_describe_describe,
    "WR_test_self_describe_assert_mentions": test_self_describe_assert_mentions,
    "WR_tool_call_assert_called": tool_call_assert_called,
    "WR_tool_call_assert_not_called": tool_call_assert_not_called,
    "WR_tool_call_assert_schema": tool_call_assert_schema,
    "WR_tool_call_assert_order": tool_call_assert_order,
    "WR_walkthrough_docs_collect_steps": walkthrough_docs_collect_steps,
    "WR_walkthrough_docs_render": walkthrough_docs_render,
    "WR_walkthrough_docs_save": walkthrough_docs_save,
    "WR_action_formatter_format": action_formatter_format,
    "WR_action_formatter_format_file": action_formatter_format_file,
    "WR_action_formatter_assert_formatted": action_formatter_assert_formatted,
    "WR_bootstrapper_starter_files": bootstrapper_starter_files,
    "WR_bootstrapper_init_workspace": bootstrapper_init_workspace,
    "WR_md_authoring_parse": md_authoring_parse,
    "WR_md_authoring_transpile_file": md_authoring_transpile_file,
    "WR_md_authoring_patterns": md_authoring_patterns,
    "WR_sel_to_pw_translate_actions": sel_to_pw_translate_actions,
    "WR_sel_to_pw_translate_for_backend": sel_to_pw_translate_for_backend,
    "WR_sel_to_pw_translate_python": sel_to_pw_translate_python,
    "WR_sel_to_pw_supported": sel_to_pw_supported,
}

PYTHON_ONLY: dict[str, str] = {}

NETWORK_COMMANDS: frozenset[str] = frozenset()
