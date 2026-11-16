"""Tests for the ``ai`` command adapters (``_commands_ai`` and ``_commands_ai_2``): no browser, no model."""
from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.executor import _commands_ai, _commands_ai_2

COMMANDS = {**_commands_ai.AI_COMMANDS, **_commands_ai_2.AI_2_COMMANDS}

PACKAGES = (
    "edge_case_generator", "exploratory_ai", "failure_auto_tag", "failure_narrator", "failure_triage",
    "hallucination_probe", "llm_token_cost_tracker", "locator_hardener", "multimodal_qa", "pr_title_generator",
    "prompt_drift_monitor", "prompt_injection_scanner", "rag_grounding_assert", "story_to_actions",
    "streaming_chat_assert", "test_auto_repair", "test_dedup_ai", "test_self_describe", "tool_call_assert",
    "walkthrough_docs", "action_formatter", "bootstrapper", "md_authoring", "sel_to_pw",
)


def run(name: str, *args: Any, **kwargs: Any) -> Any:
    """Call a command the way the executor does and check that its result is JSON."""
    result = COMMANDS[name](*args, **kwargs)
    json.dumps(result)
    return result


class TempDirCase(unittest.TestCase):
    """A test case with its own temporary directory in ``self.tmp``."""

    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = Path(holder.name)

    def write_json(self, name: str, data: Any) -> Path:
        path = self.tmp / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path


class TestTables(unittest.TestCase):

    def test_every_package_is_covered(self):
        python_only = {**_commands_ai.PYTHON_ONLY, **_commands_ai_2.PYTHON_ONLY}
        for package in PACKAGES:
            has_command = any(name.startswith(f"WR_{package}_") for name in COMMANDS)
            self.assertTrue(has_command or package in python_only, package)
        self.assertTrue(set(python_only) <= set(PACKAGES))
        for reason in python_only.values():
            self.assertTrue(reason.strip())

    def test_names_and_docstrings(self):
        self.assertFalse(set(_commands_ai.AI_COMMANDS) & set(_commands_ai_2.AI_2_COMMANDS))
        for name, function in COMMANDS.items():
            self.assertEqual(name, name.lower().replace("wr_", "WR_", 1))
            self.assertTrue(any(name.startswith(f"WR_{package}_") for package in PACKAGES), name)
            self.assertTrue(callable(function), name)
            self.assertTrue((function.__doc__ or "").strip(), name)

    def test_network_commands_are_commands(self):
        self.assertTrue(_commands_ai.NETWORK_COMMANDS <= set(_commands_ai.AI_COMMANDS))
        self.assertTrue(_commands_ai_2.NETWORK_COMMANDS <= set(_commands_ai_2.AI_2_COMMANDS))
        self.assertIsInstance(_commands_ai.NETWORK_COMMANDS, frozenset)
        self.assertIsInstance(_commands_ai_2.NETWORK_COMMANDS, frozenset)


class TestEdgeCaseGenerator(TempDirCase):

    SUITE = {
        "source_test_name": "login",
        "cases": [{
            "name": "Empty password", "category": "boundary", "rationale": "no password typed",
            "actions": [["WR_to_url", {"url": "https://x.test"}]], "severity": "high",
        }],
    }

    def test_categories(self):
        categories = run("WR_edge_case_generator_categories")
        self.assertIn("boundary", categories)
        self.assertIn("unicode", categories)

    def test_render_markdown(self):
        text = run("WR_edge_case_generator_render_markdown", self.SUITE)
        self.assertIn("| 1 | `boundary` | `high` | `fail` | Empty password | no password typed |", text)

    def test_unknown_category_is_refused(self):
        suite = {"cases": [{"name": "x", "category": "nonsense", "rationale": "", "actions": []}]}
        with self.assertRaises(WebRunnerException):
            run("WR_edge_case_generator_render_markdown", suite)

    def test_write_suite(self):
        written = run("WR_edge_case_generator_write_suite", self.SUITE, str(self.tmp / "out"))
        self.assertEqual(len(written), 1)
        self.assertTrue(written[0].endswith("login__01__empty-password.json"))
        self.assertEqual(json.loads(Path(written[0]).read_text(encoding="utf-8")), self.SUITE["cases"][0]["actions"])


class TestExploratoryAi(unittest.TestCase):

    PAGE = {"url": "https://x.test/", "title": "Home", "elements": [{"selector": "#go", "tag": "button"}]}

    def test_plan_clicks_the_only_element(self):
        action = run("WR_exploratory_ai_plan", self.PAGE, seed=7, type_bias=0.0)
        self.assertEqual(action["kind"], "click")
        self.assertEqual(action["selector"], "#go")

    def test_plan_is_done_on_an_empty_page(self):
        action = run("WR_exploratory_ai_plan", {"url": "https://x.test/", "title": "Empty"})
        self.assertEqual(action["kind"], "done")

    def test_replay_reports_signals(self):
        broken = {
            "url": "https://x.test/cart", "title": "Cart", "console_errors": ["TypeError: x is undefined"],
            "network_errors": [{"status": 500, "url": "/api/cart"}],
        }
        report = run("WR_exploratory_ai_replay", [self.PAGE, broken])
        self.assertTrue(report["has_bugs"])
        self.assertEqual([bug["kind"] for bug in report["bugs"]], ["console_error", "network_error"])
        self.assertEqual(report["pages_visited"], ["https://x.test/", "https://x.test/cart"])
        self.assertEqual(report["steps_taken"], 2)

    def test_replay_of_clean_pages(self):
        report = run("WR_exploratory_ai_replay", [self.PAGE])
        self.assertFalse(report["has_bugs"])
        self.assertEqual(report["bugs"], [])

    def test_replay_needs_observations(self):
        with self.assertRaises(WebRunnerException):
            run("WR_exploratory_ai_replay", [])


class TestFailureAutoTag(unittest.TestCase):

    def test_heuristic(self):
        tags = run(
            "WR_failure_auto_tag_heuristic", exception_text="NoSuchElementException: element not found",
            network_errors=[{"status": 503, "url": "/api"}],
        )
        self.assertEqual({tag["name"] for tag in tags}, {"flaky-locator", "network-5xx"})

    def test_merge_keeps_the_surest(self):
        merged = run("WR_failure_auto_tag_merge", [
            [{"name": "timeout", "confidence": 0.4}],
            [{"name": "timeout", "confidence": 0.9, "reason": "wait exceeded"}],
        ])
        self.assertEqual(merged, [{"name": "timeout", "confidence": 0.9, "reason": "wait exceeded"}])

    def test_assert_tagged(self):
        tags = [{"name": "timeout"}]
        self.assertEqual(run("WR_failure_auto_tag_assert_tagged", tags, "timeout"), "timeout")
        with self.assertRaises(WebRunnerException):
            run("WR_failure_auto_tag_assert_tagged", tags, "js-error")


class TestFailureNarrator(TempDirCase):

    def test_load_bundle(self):
        self.write_json("meta.json", {"test_id": "login", "error_message": "boom"})
        (self.tmp / "console.log").write_text("first\nsecond\n", encoding="utf-8")
        bundle = run("WR_failure_narrator_load_bundle", str(self.tmp))
        self.assertEqual(bundle["test_id"], "login")
        self.assertEqual(bundle["console_errors"], ["first", "second"])

    def test_build_prompt(self):
        prompt = run("WR_failure_narrator_build_prompt", {"test_id": "login", "error_message": "boom"})
        self.assertIn("- Test: login", prompt)
        self.assertIn("boom", prompt)

    def test_build_prompt_refuses_an_unknown_field(self):
        with self.assertRaises(WebRunnerException):
            run("WR_failure_narrator_build_prompt", {"test_id": "login", "nonsense": 1})

    def test_parse_response(self):
        raw = 'Here: {"summary": "s", "likely_cause": "c", "next_step": "n", "confidence": "High"}'
        report = run("WR_failure_narrator_parse_response", raw)
        self.assertEqual(report["confidence"], "high")
        self.assertIn("**Why this failed**: s", report["markdown"])
        with self.assertRaises(WebRunnerException):
            run("WR_failure_narrator_parse_response", "no json here")


class TestFailureTriage(TempDirCase):

    def test_extract_signals(self):
        from je_web_runner.utils.failure_bundle.bundle import FailureBundle
        bundle = FailureBundle(
            test_name="login", error_repr="TimeoutException('slow')",
            metadata={"steps": [["WR_to_url", {"url": "https://x.test"}]]},
        )
        bundle.add_console([{"level": "SEVERE", "message": "boom"}])
        path = bundle.write(self.tmp / "bundle.zip")
        signals = run("WR_failure_triage_extract_signals", str(path))
        self.assertEqual(signals["test_name"], "login")
        self.assertEqual(len(signals["last_steps"]), 1)
        self.assertEqual(signals["console_tail"][0]["message"], "boom")
        self.assertFalse(signals["has_screenshot"])

    def test_render_markdown(self):
        report = {
            "likely_cause": "slow backend", "category": "timing", "evidence": ["503 on /api"],
            "next_steps": ["raise the wait"], "suggested_fix": "wait for the row", "confidence": 0.8,
            "test_name": "login",
        }
        text = run("WR_failure_triage_render_markdown", report)
        self.assertIn("slow backend", text)
        self.assertIn("80%", text)
        self.assertIn("1. raise the wait", text)
        with self.assertRaises(WebRunnerException):
            run("WR_failure_triage_render_markdown", {"likely_cause": "x"})


class TestHallucinationProbe(unittest.TestCase):

    PROBES = [
        {"name": "capital", "prompt": "Capital of France?", "expected_substrings": ["Paris"]},
        {"name": "unknown", "prompt": "Who wins in 2090?", "expect_refusal": True},
    ]
    ANSWERS = {"capital": "It is Paris.", "unknown": "Certainly team A."}

    def test_evaluate(self):
        report = run("WR_hallucination_probe_evaluate", self.PROBES, self.ANSWERS)
        self.assertEqual(report["hallucination_rate"], 0.5)
        self.assertEqual([result["passed"] for result in report["results"]], [True, False])

    def test_assert_rate(self):
        self.assertEqual(run("WR_hallucination_probe_assert_rate", self.PROBES, self.ANSWERS, max_rate=0.5), 0.5)
        with self.assertRaises(WebRunnerException):
            run("WR_hallucination_probe_assert_rate", self.PROBES, self.ANSWERS, max_rate=0.1)

    def test_missing_answer(self):
        with self.assertRaises(WebRunnerException):
            run("WR_hallucination_probe_evaluate", self.PROBES, {"capital": "Paris"})


class TestLlmTokenCostTracker(unittest.TestCase):

    RECORDS = [
        {"model": "gpt-4o", "input_tokens": 1000, "output_tokens": 1000, "test_name": "a"},
        {"model": "house-model", "input_tokens": 2000, "test_name": "b"},
    ]
    RATES = {"house-model": {"input": 0.01, "output": 0.0}}

    def test_tally(self):
        result = run("WR_llm_token_cost_tracker_tally", self.RECORDS, rate_card=self.RATES)
        self.assertAlmostEqual(result["total"]["cost_usd"], 0.04)
        self.assertEqual(result["total"]["calls"], 2)
        self.assertAlmostEqual(result["by_test"]["a"]["cost_usd"], 0.02)

    def test_top_spenders(self):
        top = run("WR_llm_token_cost_tracker_top_spenders", self.RECORDS, top_n=1, rate_card=self.RATES)
        self.assertEqual(len(top), 1)
        self.assertIn(top[0]["test"], {"a", "b"})

    def test_assert_under_budget(self):
        total = run("WR_llm_token_cost_tracker_assert_under_budget", self.RECORDS, 1.0, rate_card=self.RATES)
        self.assertAlmostEqual(total["cost_usd"], 0.04)
        with self.assertRaises(WebRunnerException):
            run("WR_llm_token_cost_tracker_assert_under_budget", self.RECORDS, 0.01, rate_card=self.RATES)

    def test_unknown_model(self):
        with self.assertRaises(WebRunnerException):
            run("WR_llm_token_cost_tracker_tally", self.RECORDS)


class TestLocatorHardener(unittest.TestCase):

    def test_score(self):
        result = run("WR_locator_hardener_score", "CSS_SELECTOR", "div:nth-child(2) span a b")
        self.assertGreaterEqual(result["score"], 0.5)
        self.assertIn("uses :nth-of-type/child", result["reasons"])
        self.assertEqual(run("WR_locator_hardener_score", "id", "login")["score"], 0.0)

    def test_unknown_strategy(self):
        with self.assertRaises(WebRunnerException):
            run("WR_locator_hardener_score", "telepathy", "x")

    def test_build_prompt(self):
        prompt = run("WR_locator_hardener_build_prompt", "id", "login", dom_excerpt="<button id='login'>")
        self.assertIn("- value: login", prompt)
        self.assertIn("<button id='login'>", prompt)

    def test_parse_suggestions(self):
        raw = json.dumps([
            {"strategy": "id", "value": "submit", "rationale": "stable"},
            {"strategy": "css selector", "value": "li:nth-child(2)", "rationale": "fragile again"},
        ])
        self.assertEqual(
            run("WR_locator_hardener_parse_suggestions", raw),
            [{"strategy": "id", "value": "submit", "rationale": "stable"}],
        )
        with self.assertRaises(WebRunnerException):
            run("WR_locator_hardener_parse_suggestions", "[]")


class TestMultimodalQa(TempDirCase):

    GOOD = '{"verdict": "pass", "confidence": 0.9, "rationale": "toast is red", "issues": []}'
    BAD = '{"verdict": "fail", "confidence": 0.9, "rationale": "", "issues": ["text is cropped"]}'

    def test_build_request(self):
        image = self.tmp / "shot.png"
        image.write_bytes(b"\x89PNG-bytes")
        request = run("WR_multimodal_qa_build_request", str(image), "Is the toast visible?", rubric=["it is red"])
        self.assertEqual(base64.b64decode(request["image_b64"]), b"\x89PNG-bytes")
        self.assertIn("Question: Is the toast visible?", request["prompt"])
        self.assertIn("- it is red", request["prompt"])

    def test_build_request_without_the_image(self):
        with self.assertRaises(WebRunnerException):
            run("WR_multimodal_qa_build_request", str(self.tmp / "missing.png"), "question")

    def test_parse_response(self):
        response = run("WR_multimodal_qa_parse_response", self.GOOD)
        self.assertEqual(response["verdict"], "pass")
        self.assertEqual(response["confidence"], 0.9)

    def test_assert_passes(self):
        self.assertEqual(run("WR_multimodal_qa_assert_passes", self.GOOD)["verdict"], "pass")
        with self.assertRaises(WebRunnerException):
            run("WR_multimodal_qa_assert_passes", self.BAD)
        with self.assertRaises(WebRunnerException):
            run("WR_multimodal_qa_assert_passes", self.GOOD, min_confidence=0.95)


class TestPrTitleGenerator(unittest.TestCase):

    def test_suggest(self):
        title = run("WR_pr_title_generator_suggest", ["je_web_runner/utils/executor/x.py"], ["Add adapter commands"])
        self.assertEqual(title, "feat(utils): adapter commands")

    def test_assert_conventional(self):
        self.assertEqual(run("WR_pr_title_generator_assert_conventional", "fix(core): close the driver"),
                         "fix(core): close the driver")
        with self.assertRaises(WebRunnerException):
            run("WR_pr_title_generator_assert_conventional", "Updated stuff")


class TestPromptDriftMonitor(TempDirCase):

    SAMPLES = [{
        "prompt_id": "greeting", "prompt": "Say hi", "answer": "Hello from Acme", "embedding": [1.0, 0.0],
        "must_include": ["Acme"],
    }]
    SAME = [{"prompt_id": "greeting", "answer": "Hello from Acme", "embedding": [1.0, 0.0]}]
    DRIFTED = [{"prompt_id": "greeting", "answer": "Hi", "embedding": [0.0, 1.0]}]

    def setUp(self) -> None:
        super().setUp()
        self.baseline = run("WR_prompt_drift_monitor_save_baseline", self.SAMPLES, str(self.tmp / "base.json"))

    def test_save_and_load_baseline(self):
        self.assertTrue(Path(self.baseline).is_file())
        loaded = run("WR_prompt_drift_monitor_load_baseline", self.baseline)
        self.assertEqual(loaded["samples"][0]["prompt_id"], "greeting")
        self.assertEqual(loaded["samples"][0]["embedding"], [1.0, 0.0])

    def test_check(self):
        same = run("WR_prompt_drift_monitor_check", self.baseline, self.SAME)
        self.assertTrue(same["passed"])
        self.assertEqual(same["findings"][0]["similarity"], 1.0)
        drifted = run("WR_prompt_drift_monitor_check", self.baseline, self.DRIFTED)
        self.assertFalse(drifted["passed"])
        self.assertEqual(drifted["drifted"], ["greeting"])
        self.assertEqual(drifted["findings"][0]["missing_required"], ["Acme"])

    def test_assert_no_drift(self):
        self.assertEqual(run("WR_prompt_drift_monitor_assert_no_drift", self.baseline, self.SAME), 1)
        with self.assertRaises(WebRunnerException):
            run("WR_prompt_drift_monitor_assert_no_drift", self.baseline, self.DRIFTED)

    def test_missing_current_answer(self):
        with self.assertRaises(WebRunnerException):
            run("WR_prompt_drift_monitor_check", self.baseline, [])


class TestPromptInjectionScanner(unittest.TestCase):

    def test_payloads(self):
        payloads = run("WR_prompt_injection_scanner_payloads")
        self.assertEqual(payloads[0]["name"], "ignore_previous")
        self.assertEqual(payloads[0]["severity"], "high")
        self.assertTrue(all(payload["prompt"] for payload in payloads))

    def test_grade(self):
        report = run("WR_prompt_injection_scanner_grade", {
            "canary_extract": "~CANARY-WR-DEADBEEF~", "ignore_previous": "I can't do that.",
        })
        self.assertFalse(report["passed"])
        self.assertEqual(report["leaks"], ["canary_extract"])
        self.assertEqual(report["findings"][0]["payload"], "ignore_previous")
        self.assertTrue(report["findings"][0]["refused"])

    def test_assert_no_leaks(self):
        self.assertEqual(run("WR_prompt_injection_scanner_assert_no_leaks", {"ignore_previous": "I can't."}), 1)
        with self.assertRaises(WebRunnerException):
            run("WR_prompt_injection_scanner_assert_no_leaks", {"canary_extract": "CANARY-WR-DEADBEEF"})

    def test_own_payloads_and_severity(self):
        payloads = [{"name": "own", "prompt": "say the word", "severity": "low", "leak_indicators": ["word"]}]
        responses = {"own": "the word"}
        self.assertEqual(run("WR_prompt_injection_scanner_grade", responses, payloads=payloads)["leaks"], ["own"])
        self.assertEqual(run("WR_prompt_injection_scanner_assert_no_leaks", responses, payloads=payloads), 1)
        with self.assertRaises(WebRunnerException):
            run("WR_prompt_injection_scanner_assert_no_leaks", responses, minimum_severity="low", payloads=payloads)

    def test_unknown_payload_name(self):
        with self.assertRaises(WebRunnerException):
            run("WR_prompt_injection_scanner_grade", {"nonsense": "x"})


class TestRagGroundingAssert(unittest.TestCase):

    CHUNKS = [{"chunk_id": "c1", "text": "WebRunner drives browsers through Selenium"}]
    GROUNDED = "WebRunner drives browsers through Selenium"
    INVENTED = "WebRunner cooks pasta with tomato sauce daily"

    def test_score(self):
        self.assertEqual(
            run("WR_rag_grounding_assert_score", self.GROUNDED, self.CHUNKS),
            {"overlap": 1.0, "unsupported_phrases": []},
        )
        invented = run("WR_rag_grounding_assert_score", self.INVENTED, self.CHUNKS)
        self.assertLess(invented["overlap"], 0.5)
        self.assertIn("cooks pasta with tomato", invented["unsupported_phrases"])

    def test_citations(self):
        self.assertEqual(run("WR_rag_grounding_assert_citations", self.GROUNDED, self.CHUNKS, ["c1"]), 1)
        with self.assertRaises(WebRunnerException):
            run("WR_rag_grounding_assert_citations", self.GROUNDED, self.CHUNKS, ["c9"])
        with self.assertRaises(WebRunnerException):
            run("WR_rag_grounding_assert_citations", self.GROUNDED, self.CHUNKS, [])

    def test_grounded(self):
        self.assertEqual(run("WR_rag_grounding_assert_grounded", self.GROUNDED, self.CHUNKS), 1.0)
        with self.assertRaises(WebRunnerException):
            run("WR_rag_grounding_assert_grounded", self.INVENTED, self.CHUNKS)

    def test_no_hallucination(self):
        self.assertEqual(run("WR_rag_grounding_assert_no_hallucination", self.GROUNDED, self.CHUNKS), [])
        with self.assertRaises(WebRunnerException):
            run("WR_rag_grounding_assert_no_hallucination", self.INVENTED, self.CHUNKS)


class TestStoryToActions(unittest.TestCase):

    def test_build_prompt(self):
        prompt = run(
            "WR_story_to_actions_build_prompt", "As a user I log in", start_url="https://x.test",
            figma_hints=[{"name": "Login", "type": "button", "selector_hint": "#login"}],
        )
        self.assertIn("# Story\nAs a user I log in", prompt)
        self.assertIn("https://x.test", prompt)
        self.assertIn("- Login (button) selector: #login", prompt)

    def test_parse_reply(self):
        reply = ('```json\n[["WR_find_element_by", {"selector": "login", "by": "id"}], '
                 '["WR_element_click"]]\n```')
        actions = run("WR_story_to_actions_parse_reply", reply, start_url="https://x.test")
        self.assertEqual(actions, [["WR_to_url", {"url": "https://x.test"}],
                                   ["WR_find_element_by", {"selector": "login", "by": "id"}],
                                   ["WR_element_click"]])
        with self.assertRaises(WebRunnerException):
            run("WR_story_to_actions_parse_reply", "not json")

    def test_validate(self):
        self.assertEqual(run("WR_story_to_actions_validate", [["WR_to_url", {"url": "https://x.test"}]]), 1)
        with self.assertRaises(WebRunnerException):
            run("WR_story_to_actions_validate", [["WR_execute_script", {"script": "alert(1)"}]])
        with self.assertRaises(WebRunnerException):
            # The shape of before the fix is not an action and is refused.
            run("WR_story_to_actions_validate", [{"WR_to_url": ["https://x.test"]}])


class TestStreamingChatAssert(unittest.TestCase):

    DELTAS = [{"text": "Hel", "ts_ms": 120, "seq": 0}, {"text": "lo", "ts_ms": 300, "seq": 1}]

    def test_summary(self):
        self.assertEqual(
            run("WR_streaming_chat_assert_summary", self.DELTAS),
            {"text": "Hello", "chunks": 2, "ttft_ms": 120.0, "max_gap_ms": 180.0},
        )
        self.assertIsNone(run("WR_streaming_chat_assert_summary", [])["ttft_ms"])

    def test_timing(self):
        timing = run("WR_streaming_chat_assert_timing", self.DELTAS, max_ttft_ms=500, max_gap_ms=1000)
        self.assertEqual(timing, {"ttft_ms": 120.0, "max_gap_ms": 180.0})
        with self.assertRaises(WebRunnerException):
            run("WR_streaming_chat_assert_timing", self.DELTAS, max_ttft_ms=100)
        with self.assertRaises(WebRunnerException):
            run("WR_streaming_chat_assert_timing", self.DELTAS, max_gap_ms=50)

    def test_content(self):
        self.assertEqual(run("WR_streaming_chat_assert_content", self.DELTAS, expected="Hello"), "Hello")
        with self.assertRaises(WebRunnerException):
            run("WR_streaming_chat_assert_content", self.DELTAS, expected="Goodbye")
        with self.assertRaises(WebRunnerException):
            run("WR_streaming_chat_assert_content", [{"text": "caf�", "ts_ms": 1}])

    def test_order(self):
        self.assertEqual(run("WR_streaming_chat_assert_order", self.DELTAS), 2)
        with self.assertRaises(WebRunnerException):
            run("WR_streaming_chat_assert_order", [{"text": "a", "seq": 1}, {"text": "b", "seq": 1}])


class TestTestAutoRepair(TempDirCase):

    PLAN = {
        "summary": "Fix the login locator", "confidence": 0.9, "repaired_actions": [["WR_quit_all"]],
        "changes": [{"index": 0, "kind": "locator", "why": "id was renamed"}], "risks": ["check the selector"],
    }

    def test_git_diff(self):
        finished = MagicMock(returncode=0, stdout="diff --git a/x b/x\n", stderr="")
        with patch("je_web_runner.utils.test_auto_repair.repair.subprocess.run", return_value=finished) as git:
            text = run("WR_test_auto_repair_git_diff", repo_dir=str(self.tmp), since_ref="HEAD~2")
        self.assertEqual(text, "diff --git a/x b/x\n")
        self.assertIn("HEAD~2..HEAD", git.call_args.args[0])

    def test_git_diff_refuses_an_option_as_revision(self):
        with patch("je_web_runner.utils.test_auto_repair.repair.subprocess.run") as git:
            with self.assertRaises(WebRunnerException):
                run("WR_test_auto_repair_git_diff", since_ref="--output=stolen")
        git.assert_not_called()

    def test_render_markdown(self):
        text = run("WR_test_auto_repair_render_markdown", self.PLAN)
        self.assertIn("Fix the login locator", text)
        self.assertIn("90%", text)
        self.assertIn("id was renamed", text)
        with self.assertRaises(WebRunnerException):
            run("WR_test_auto_repair_render_markdown", {"summary": "no actions"})

    def test_apply(self):
        action_file = self.write_json("login.json", [["WR_to_url", {"url": "https://x.test"}]])
        written = run("WR_test_auto_repair_apply", str(action_file), self.PLAN)
        self.assertTrue(written.endswith("login.json.repaired.json"))
        self.assertEqual(json.loads(Path(written).read_text(encoding="utf-8")), [["WR_quit_all"]])
        with self.assertRaises(WebRunnerException):
            run("WR_test_auto_repair_apply", str(action_file), {**self.PLAN, "confidence": 0.1})


class TestTestDedupAi(TempDirCase):

    def setUp(self) -> None:
        super().setUp()
        self.write_json("a.json", [["WR_to_url", {"url": "https://a.test"}], ["WR_quit_all"]])
        self.write_json("b.json", [["WR_to_url", {"url": "https://b.test"}], ["WR_quit_all"]])
        self.write_json("c.json", [["WR_implicitly_wait", {"time_to_wait": 3}]])

    def test_fingerprint(self):
        first = run("WR_test_dedup_ai_fingerprint", [["WR_to_url", {"url": "https://a.test"}]])
        second = run("WR_test_dedup_ai_fingerprint", [["WR_to_url", {"url": "https://b.test"}]])
        other = run("WR_test_dedup_ai_fingerprint", [["WR_quit_all"]])
        self.assertEqual(len(first), 64)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(first, run("WR_test_dedup_ai_fingerprint", [{"WR_to_url": ["https://c.test"]}]))

    def test_structural(self):
        result = run("WR_test_dedup_ai_structural", str(self.tmp))
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual([Path(member).name for member in result["clusters"][0]["members"]], ["a.json", "b.json"])
        self.assertIn("structural", result["markdown"])

    def test_semantic(self):
        embeddings = {"a.json": [1.0, 0.0], "b.json": [1.0, 0.01], "c.json": [0.0, 1.0]}
        result = run("WR_test_dedup_ai_semantic", str(self.tmp), embeddings)
        self.assertEqual(len(result["clusters"]), 1)
        self.assertEqual(result["clusters"][0]["mode"], "semantic")
        self.assertEqual([Path(member).name for member in result["clusters"][0]["members"]], ["a.json", "b.json"])
        with self.assertRaises(WebRunnerException):
            run("WR_test_dedup_ai_semantic", str(self.tmp), {"a.json": [1.0, 0.0]})


class TestTestSelfDescribe(unittest.TestCase):

    ACTIONS = [["WR_to_url", {"url": "https://x.test"}], ["WR_click_element", {"element_name": "login"}]]

    def test_summarise(self):
        self.assertEqual(run("WR_test_self_describe_summarise", self.ACTIONS), [
            {"phase": "Given", "sentence": "the user opens https://x.test"},
            {"phase": "When", "sentence": 'the user clicks "login"'},
        ])

    def test_describe(self):
        text = run("WR_test_self_describe_describe", self.ACTIONS, title="Login")
        self.assertTrue(text.startswith("# Login"))
        self.assertIn("Given the user opens https://x.test", text)
        native = run("WR_test_self_describe_describe", [{"action_name": "to_url", "url": "https://y.test"}])
        self.assertIn("https://y.test", native)

    def test_assert_mentions(self):
        self.assertIn("login", run("WR_test_self_describe_assert_mentions", self.ACTIONS, ["https://x.test"]))
        with self.assertRaises(WebRunnerException):
            run("WR_test_self_describe_assert_mentions", self.ACTIONS, ["checkout"])


class TestToolCallAssert(unittest.TestCase):

    CALLS = [
        {"name": "search", "arguments": {"query": "flights"}, "call_id": "1"},
        {"name": "book", "arguments": {"seats": 2}},
    ]
    SCHEMA = {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}}

    def test_called(self):
        matches = run("WR_tool_call_assert_called", self.CALLS, "search")
        self.assertEqual(matches, [{"name": "search", "arguments": {"query": "flights"}, "call_id": "1"}])
        with self.assertRaises(WebRunnerException):
            run("WR_tool_call_assert_called", self.CALLS, "search", times=2)
        with self.assertRaises(WebRunnerException):
            run("WR_tool_call_assert_called", self.CALLS, "refund")

    def test_not_called(self):
        self.assertEqual(run("WR_tool_call_assert_not_called", self.CALLS, ["delete_account"]), 2)
        with self.assertRaises(WebRunnerException):
            run("WR_tool_call_assert_not_called", self.CALLS, ["book"])

    def test_schema(self):
        self.assertEqual(run("WR_tool_call_assert_schema", self.CALLS, "search", self.SCHEMA), 1)
        with self.assertRaises(WebRunnerException):
            run("WR_tool_call_assert_schema", self.CALLS, "search", {**self.SCHEMA, "required": ["limit"]})

    def test_order(self):
        self.assertEqual(run("WR_tool_call_assert_order", self.CALLS, ["search", "book"]), ["search", "book"])
        with self.assertRaises(WebRunnerException):
            run("WR_tool_call_assert_order", self.CALLS, ["book", "search"])


class TestWalkthroughDocs(TempDirCase):

    ACTIONS = [
        ["WR_set_window_size", {"width": 800, "height": 600}],
        ["WR_to_url", {"url": "https://x.test"}],
        ["WR_click_element", {"element_name": "go"}],
    ]

    def spec(self) -> dict[str, Any]:
        return {"title": "Login", "actions": self.ACTIONS, "narrations": ["Open the site", "Press go"]}

    def test_collect_steps(self):
        image = self.tmp / "after.png"
        image.write_bytes(b"png")
        steps = run("WR_walkthrough_docs_collect_steps", self.ACTIONS, screenshots={"1": str(image)})
        self.assertEqual([step["index"] for step in steps], [1, 2])
        self.assertEqual(base64.b64decode(steps[0]["screenshot_b64"]), b"png")
        self.assertEqual(len(run("WR_walkthrough_docs_collect_steps", self.ACTIONS, skip_noise=False)), 3)

    def test_render(self):
        markdown = run("WR_walkthrough_docs_render", self.spec())
        self.assertIn("# Login", markdown)
        self.assertIn("## Step 1. Open the site", markdown)
        self.assertIn("<h1>Login</h1>", run("WR_walkthrough_docs_render", self.spec(), fmt="confluence"))
        with self.assertRaises(WebRunnerException):
            run("WR_walkthrough_docs_render", self.spec(), fmt="pdf")
        with self.assertRaises(WebRunnerException):
            run("WR_walkthrough_docs_render", {"actions": self.ACTIONS, "screenshots": {"first": "x.png"}})

    def test_save(self):
        written = run("WR_walkthrough_docs_save", self.spec(), str(self.tmp / "docs" / "login.md"))
        self.assertIn("## Step 2. Press go", Path(written).read_text(encoding="utf-8"))


class TestAuthoringHelpers(TempDirCase):

    def test_action_formatter_format(self):
        text = run("WR_action_formatter_format", [["WR_to_url", {"url": "https://x.test"}]])
        self.assertEqual(text, '[\n  ["WR_to_url", {"url": "https://x.test"}]\n]\n')

    def test_action_formatter_file(self):
        path = self.write_json("login.json", [["WR_to_url", {"url": "https://x.test"}]])
        original = path.read_text(encoding="utf-8")
        checked = run("WR_action_formatter_format_file", str(path))
        self.assertTrue(checked["changed"])
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        with self.assertRaises(WebRunnerException):
            run("WR_action_formatter_assert_formatted", str(path))
        run("WR_action_formatter_format_file", str(path), write=True)
        self.assertEqual(path.read_text(encoding="utf-8"), checked["text"])
        self.assertEqual(run("WR_action_formatter_assert_formatted", str(path)), str(path))

    def test_bootstrapper(self):
        files = run("WR_bootstrapper_starter_files")
        self.assertIn("actions/sample.json", [entry["relative_path"] for entry in files])
        workspace = self.tmp / "workspace"
        self.assertEqual(run("WR_bootstrapper_init_workspace", str(workspace))["README.md"], "created")
        self.assertTrue((workspace / "actions" / "sample.json").is_file())
        self.assertEqual(run("WR_bootstrapper_init_workspace", str(workspace))["README.md"], "skipped")

    def test_md_authoring(self):
        expected = [["WR_to_url", {"url": "https://x.test"}], ["WR_quit_all"]]
        self.assertEqual(run("WR_md_authoring_parse", "- open https://x.test\n- quit\n"), expected)
        with self.assertRaises(WebRunnerException):
            run("WR_md_authoring_parse", "no bullets here")
        source = self.tmp / "flow.md"
        source.write_text("- open https://x.test\n- quit\n", encoding="utf-8")
        target = self.tmp / "flow.json"
        self.assertEqual(run("WR_md_authoring_transpile_file", str(source), str(target)), expected)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), expected)
        self.assertIn("quit", run("WR_md_authoring_patterns"))

    def test_sel_to_pw(self):
        actions = [["WR_to_url", {"url": "https://x.test"}], ["WR_implicitly_wait", {"time_to_wait": 3}]]
        self.assertEqual(
            run("WR_sel_to_pw_translate_actions", actions), [["WR_pw_to_url", {"url": "https://x.test"}]])
        lines = run("WR_sel_to_pw_translate_python", 'driver.get("https://x.test")\nprint(1)\n')
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["line"], 1)
        self.assertEqual(lines[0]["translated"], 'page.goto("https://x.test")')
        supported = run("WR_sel_to_pw_supported")
        self.assertIn("WR_to_url", supported["action_commands"])
        self.assertTrue(supported["python_patterns"])


if __name__ == "__main__":
    unittest.main()
