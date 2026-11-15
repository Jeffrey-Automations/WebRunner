"""``meta`` of an object document: skip, vars, setup, teardown, retries."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.flow import FlowError, VariableStore
from je_web_runner.utils.flow.document import (
    apply_default_vars,
    hook_actions,
    planned_actions,
    read_meta,
    retry_settings,
    skip_reason,
)
from je_web_runner.utils.schema.action_schema import build_action_schema


class TestMetaReaders(unittest.TestCase):

    def test_documents_without_meta(self):
        self.assertEqual(read_meta([["WR_quit"]]), {})
        self.assertEqual(read_meta({"webdriver_wrapper": []}), {})
        self.assertEqual(read_meta({"webdriver_wrapper": [], "meta": None}), {})

    def test_meta_must_be_an_object(self):
        with self.assertRaises(FlowError):
            read_meta({"webdriver_wrapper": [], "meta": ["smoke"]})

    def test_skip_needs_a_reason(self):
        self.assertIsNone(skip_reason({}))
        self.assertIsNone(skip_reason({"skip": False}))
        self.assertEqual(skip_reason({"skip": " new login page "}), "new login page")
        for value in (True, "", "  ", 1):
            with self.subTest(value=value):
                with self.assertRaises(FlowError):
                    skip_reason({"skip": value})

    def test_hooks_must_be_lists(self):
        self.assertEqual(hook_actions({}, "setup"), [])
        self.assertEqual(hook_actions({"setup": [["WR_quit"]]}, "setup"), [["WR_quit"]])
        with self.assertRaises(FlowError):
            hook_actions({"teardown": "WR_quit"}, "teardown")

    def test_retry_settings(self):
        self.assertIsNone(retry_settings({}))
        self.assertEqual(retry_settings({"retries": 2}), (2, 0.0))
        self.assertEqual(retry_settings({"retries": 1, "retry_backoff": 0.5}), (1, 0.5))
        for meta in ({"retries": -1}, {"retries": 1.5}, {"retries": True}, {"retries": 1000},
                     {"retries": 1, "retry_backoff": -1}, {"retries": 1, "retry_backoff": "x"}):
            with self.subTest(meta=meta):
                with self.assertRaises(FlowError):
                    retry_settings(meta)

    def test_default_vars_do_not_replace_existing_ones(self):
        store = VariableStore()
        store.set("base", "from-cli")
        store.set("port", 8080)
        apply_default_vars({"vars": {"base": "default", "url": "${base}:${port}", "n": 1}}, store)
        self.assertEqual(store.get("base"), "from-cli")
        self.assertEqual(store.get("url"), "from-cli:8080")
        self.assertEqual(store.get("n"), 1)

    def test_scoped_default_vars_end_with_the_frame(self):
        store = VariableStore()
        with store.scope({"given": 1}):
            apply_default_vars({"vars": {"given": 9, "extra": 2}}, store, scoped=True)
            self.assertEqual((store.get("given"), store.get("extra")), (1, 2))
        self.assertFalse(store.has("extra"))

    def test_vars_must_be_an_object(self):
        with self.assertRaises(FlowError):
            apply_default_vars({"vars": ["a"]}, VariableStore())

    def test_planned_actions(self):
        store = VariableStore()
        main = [["WR_main"]]
        self.assertIs(planned_actions(main, main, store), main)
        self.assertIs(planned_actions({"webdriver_wrapper": main}, main, store), main)
        document = {"meta": {"setup": [["WR_a"]], "teardown": [["WR_z"]], "tags": ["x"]}}
        self.assertEqual(planned_actions(document, main, store), [["WR_a"], ["WR_main"], ["WR_z"]])
        skipped = planned_actions({"meta": {"skip": "later", "setup": [["WR_a"]]}}, main, store)
        self.assertEqual(skipped, [["WR_note", {"text": "skipped: later"}]])


class TestExecutorDocuments(unittest.TestCase):

    def setUp(self):
        self.executor = Executor()
        self.seen = []
        self.executor.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value
        self.executor.event_dict["WR_boom"] = self._boom
        self.failures_left = 0

    def _boom(self):
        raise ValueError("boom")

    def _flaky(self):
        if self.failures_left:
            self.failures_left -= 1
            raise ValueError("not yet")
        return "ready"

    def _run(self, document):
        with patch("builtins.print"):
            return self.executor.collect_action_results(document)

    def test_tags_only_documents_run_as_before(self):
        records, failed = self._run({"meta": {"tags": ["smoke"], "depends_on": ["login"]},
                                     "webdriver_wrapper": [["WR_probe", [1]]]})
        self.assertEqual((list(records.values()), failed), ([1], []))

    def test_setup_and_teardown_surround_the_actions(self):
        self._run({"meta": {"setup": [["WR_probe", ["setup"]]], "teardown": [["WR_probe", ["teardown"]]]},
                   "webdriver_wrapper": [["WR_probe", ["main"]]]})
        self.assertEqual(self.seen, ["setup", "main", "teardown"])

    def test_teardown_runs_after_a_failure(self):
        records, failed = self._run({"meta": {"teardown": [["WR_probe", ["teardown"]]]},
                                     "webdriver_wrapper": [["WR_boom"], ["WR_probe", ["main"]]]})
        self.assertEqual(self.seen, ["main", "teardown"])
        self.assertEqual(len(failed), 1)
        self.assertEqual(len(records), 3)

    def test_skipped_file_records_its_reason_and_runs_nothing(self):
        records, failed = self._run({"meta": {"skip": "flaky on CI", "setup": [["WR_probe", ["setup"]]]},
                                     "webdriver_wrapper": [["WR_probe", ["main"]]]})
        self.assertEqual(self.seen, [])
        self.assertEqual(failed, [])
        self.assertEqual(list(records.values()), ["skipped: flaky on CI"])

    def test_default_vars_are_available_to_the_actions(self):
        self.executor.variables.set("user", "from-outside")
        self._run({"meta": {"vars": {"user": "default", "role": "admin"}},
                   "webdriver_wrapper": [["WR_probe", ["${user}/${role}"]]]})
        self.assertEqual(self.seen, ["from-outside/admin"])

    def test_meta_retries_apply_to_the_file_and_are_restored(self):
        self.executor.event_dict["WR_flaky"] = self._flaky
        self.failures_left = 2
        self.executor.set_retry_policy(0, 0.0)
        records, failed = self._run({"meta": {"retries": 2}, "webdriver_wrapper": [["WR_flaky"]]})
        self.assertEqual((list(records.values()), failed), (["ready"], []))
        self.assertEqual(self.executor.retry_policy, {"retries": 0, "backoff": 0.0})

    def test_retries_are_restored_when_the_document_is_invalid(self):
        self.executor.set_retry_policy(1, 0.0)
        with self.assertRaises(Exception):
            self._run({"meta": {"retries": 3}, "webdriver_wrapper": "not a list"})
        self.assertEqual(self.executor.retry_policy, {"retries": 1, "backoff": 0.0})

    def test_bad_meta_fails_the_document(self):
        for meta in ({"skip": True}, {"setup": "x"}, {"vars": []}, {"retries": "many"}):
            with self.subTest(meta=meta):
                with self.assertRaises(FlowError):
                    self._run({"meta": meta, "webdriver_wrapper": [["WR_probe"]]})
        self.assertEqual(self.seen, [])

    def test_execute_action_prints_and_applies_meta(self):
        with patch("builtins.print"):
            records = self.executor.execute_action({"meta": {"setup": [["WR_probe", ["setup"]]]},
                                                    "webdriver_wrapper": [["WR_probe", ["main"]]]})
        self.assertEqual(list(records.values()), ["setup", "main"])


class TestCalledFileMeta(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        self.executor = Executor()
        self.seen = []
        self.executor.event_dict["WR_probe"] = lambda value=None: self.seen.append(value) or value

    def _write(self, name, document):
        (self.root / name).write_text(json.dumps(document), encoding="utf-8")

    def test_defaults_fill_missing_params_and_end_with_the_call(self):
        self._write("greet.json", {
            "meta": {"vars": {"greeting": "hello", "name": "world"},
                     "setup": [["WR_probe", ["setup"]]], "teardown": [["WR_probe", ["teardown"]]]},
            "webdriver_wrapper": [["WR_probe", ["${greeting} ${name}"]]],
        })
        self.executor.execute_one(["WR_call_file", {"path": "greet.json", "params": {"name": "alice"}}])
        self.assertEqual(self.seen, ["setup", "hello alice", "teardown"])
        self.assertEqual(self.executor.variables.names(), [])

    def test_a_skipped_file_called_runs_nothing(self):
        self._write("later.json", {"meta": {"skip": "not ready"}, "webdriver_wrapper": [["WR_probe", [1]]]})
        result = self.executor.execute_one(["WR_call_file", {"path": "later.json"}])
        self.assertEqual(result, ["skipped: not ready"])
        self.assertEqual(self.seen, [])


class TestSchema(unittest.TestCase):

    def test_meta_keys_are_declared(self):
        schema = build_action_schema()
        document = next(form for form in schema["oneOf"] if form.get("type") == "object")
        declared = set(document["properties"]["meta"]["properties"])
        self.assertLessEqual({"tags", "depends_on", "skip", "vars", "setup", "teardown", "retries",
                              "retry_backoff"}, declared)


if __name__ == "__main__":
    unittest.main()
