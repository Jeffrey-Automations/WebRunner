"""AsyncExecutor with a fake browser pool: order, threads, gates, sessions, concurrency."""
import asyncio
import threading
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.async_executor import commands, executor as async_module
from je_web_runner.utils.async_executor.executor import AsyncExecutor
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import Executor


class _FakeSession:
    def __init__(self, name):
        self.name = name
        self.closed = False
        self.calls = []

    async def close(self):
        self.closed = True


class _FakePool:
    def __init__(self):
        self.sessions = []

    async def open_session(self, **options):
        session = _FakeSession(f"user{len(self.sessions)}")
        session.options = options
        self.sessions.append(session)
        return session

    async def close(self):
        self.closed = True


async def _echo(session, value=None):
    session.calls.append(value)
    return f"{session.name}:{value}"


async def _boom(session):
    raise commands.AsyncCommandError("title is 'Home', expected it to contain 'Cart'")


class TestAsyncExecutor(unittest.TestCase):

    def setUp(self):
        self.sync = Executor()
        self.sync_threads = []
        self.sync.event_dict["WR_probe"] = self._probe
        self.runner = AsyncExecutor(sync=self.sync)
        self.runner.pool = _FakePool()
        patcher = patch.dict(async_module.ASYNC_COMMANDS, {"WR_apw_echo": _echo, "WR_apw_boom": _boom})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _probe(self):
        self.sync_threads.append(threading.get_ident())
        return "sync"

    def _run(self, coroutine):
        return asyncio.run(coroutine)

    def test_runs_in_order_with_sync_commands_in_a_worker_thread(self):
        record, failed = self._run(self.runner.run([
            ["WR_apw_echo", {"value": 1}], ["WR_probe"], ["WR_apw_echo", [2]], ["len", [[1, 2, 3]]]]))
        self.assertEqual(failed, [])
        self.assertEqual(list(record.values()), ["user0:1", "sync", "user0:2", 3])
        self.assertNotEqual(self.sync_threads, [threading.get_ident()])
        [session] = self.runner.pool.sessions
        self.assertEqual(session.calls, [1, 2])
        self.assertTrue(session.closed)

    def test_concurrent_lists_have_their_own_variables(self):
        self.sync.variables.set("shared", "from-run")
        lists = [[["WR_set_var", ["who", name]], ["WR_apw_echo", ["${who}/${shared}"]]] for name in "abcdef"]
        results = self._run(self.runner.run_many(lists, concurrency=6))
        answers = [list(record.values())[1].split(":")[1] for record, _failed in results]
        self.assertEqual(answers, [f"{name}/from-run" for name in "abcdef"])
        self.assertFalse(self.sync.variables.has("who"))
        self.assertEqual(self.sync.variables.get("shared"), "from-run")

    def test_fail_fast_skips_the_rest_of_an_async_list_but_not_teardown(self):
        document = {
            "meta": {"fail_fast": True, "teardown": [["WR_apw_echo", ["teardown"]]]},
            "webdriver_wrapper": [["WR_apw_boom"], ["WR_apw_echo", ["skipped"]], ["WR_probe"]],
        }
        record, failed = self._run(self.runner.run(document))
        self.assertEqual(len(failed), 3)
        self.assertEqual(self.sync_threads, [])
        self.assertEqual(self.runner.pool.sessions[0].calls, ["teardown"])
        self.assertIn("fail-fast", list(record.values())[1])

    def test_meta_retries_apply_to_the_sync_commands_of_that_list_only(self):
        attempts = {"flaky": 0, "plain": 0}

        def fail_twice(name):
            attempts[name] += 1
            if attempts[name] < 3:
                raise ValueError("not yet")
            return "ready"

        self.sync.event_dict["WR_fail_twice"] = fail_twice
        retried = {"meta": {"retries": 2}, "webdriver_wrapper": [["WR_fail_twice", ["flaky"]]]}
        plain = [["WR_fail_twice", ["plain"]]]
        results = self._run(self.runner.run_many([retried, plain], concurrency=2))
        self.assertEqual([len(failed) for _record, failed in results], [0, 1])
        self.assertEqual(attempts, {"flaky": 3, "plain": 1})
        self.assertEqual(self.sync.retry_policy, {"retries": 0, "backoff": 0.0})

    def test_fail_fast_is_per_list(self):
        failing = {"meta": {"fail_fast": True}, "webdriver_wrapper": [["WR_apw_boom"], ["WR_apw_echo", [1]]]}
        passing = [["WR_apw_echo", [2]], ["WR_apw_echo", [3]]]
        results = self._run(self.runner.run_many([failing, passing], concurrency=2))
        self.assertEqual([len(failed) for _record, failed in results], [2, 0])

    def test_the_file_of_a_list_is_its_calling_file_and_marks_its_records(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        from je_web_runner.utils.test_record.test_record_class import record_action_to_list, test_record_instance
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name).resolve()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(root)
        (root / "suite").mkdir()
        (root / "suite" / "part.json").write_text(json.dumps([["WR_recorded"]]), encoding="utf-8")
        self.sync.event_dict["WR_recorded"] = lambda: record_action_to_list("recorded", None)
        self.addCleanup(test_record_instance.set_record_enable, test_record_instance.init_record)
        self.addCleanup(setattr, test_record_instance, "test_record_list", test_record_instance.test_record_list)
        test_record_instance.test_record_list = []
        test_record_instance.set_record_enable(True)
        main_file = str(root / "suite" / "main.json")
        _record, failed = self._run(self.runner.run([["WR_call_file", {"path": "part.json"}]], file=main_file))
        self.assertEqual(failed, [])
        self.assertEqual([entry.get("file") for entry in test_record_instance.test_record_list], [main_file])
        self.assertIsNone(self.sync.files.current)

    def test_files_must_match_the_lists(self):
        with self.assertRaises(WebRunnerExecuteException):
            self._run(self.runner.run_many([[], []], files=["only-one.json"]))

    def test_variables_reach_async_commands(self):
        record, failed = self._run(self.runner.run([
            ["WR_set_var", {"name": "who", "value": "alice"}],
            ["WR_apw_echo", {"value": "hello ${who}"}],
            ["WR_apw_echo", ["${who}"]],
        ]))
        self.assertEqual(failed, [])
        self.assertEqual(list(record.values()), ["alice", "user0:hello alice", "user0:alice"])
        self.assertIn("execute: ['WR_apw_echo', {'value': 'hello ${who}'}]", record)

    def test_failures_are_recorded_and_the_list_goes_on(self):
        self.sync.event_dict["WR_sync_fail"] = MagicMock(side_effect=ValueError("bad value"))
        record, failed = self._run(self.runner.run([["WR_apw_boom"], ["WR_sync_fail"], ["WR_apw_echo", [3]]]))
        self.assertEqual(len(failed), 2)
        values = list(record.values())
        self.assertIn("expected it to contain 'Cart'", values[0])
        self.assertEqual(values[1], "ValueError('bad value')")
        self.assertEqual(values[2], "user0:3")

    def test_no_browser_session_for_sync_only_lists(self):
        self._run(self.runner.run([["WR_probe"]]))
        self.assertEqual(self.runner.pool.sessions, [])

    def test_gates_apply_to_async_commands(self):
        with self.sync.restricted({"WR_apw_echo"}):
            _record, failed = self._run(self.runner.run([["WR_apw_echo", [1]]]))
        self.assertEqual(len(failed), 1)
        self.sync.set_allow_arbitrary_script(False)
        record, failed = self._run(self.runner.run([["WR_apw_evaluate", {"script": "1"}]]))
        self.assertIn("arbitrary-script", record[failed[0]])
        self.assertEqual(self.runner.pool.sessions, [])

    def test_malformed_actions_and_lists(self):
        _record, failed = self._run(self.runner.run([[], ["WR_apw_echo", "not args"]]))
        self.assertEqual(len(failed), 2)
        with self.assertRaises(WebRunnerExecuteException):
            self._run(self.runner.run("not a list"))

    def test_run_many_keeps_order_isolates_sessions_and_limits_concurrency(self):
        active = {"now": 0, "most": 0}

        async def slow(session, value):
            active["now"] += 1
            active["most"] = max(active["most"], active["now"])
            await asyncio.sleep(0.05)
            active["now"] -= 1
            return f"{session.name}:{value}"
        with patch.dict(async_module.ASYNC_COMMANDS, {"WR_apw_slow": slow}):
            results = self._run(self.runner.run_many(
                [[["WR_apw_slow", [n]]] for n in range(5)], concurrency=2, context_options={"locale": "zh-TW"}))
        self.assertEqual([list(record.values())[0].split(":")[1] for record, _failed in results],
                         ["0", "1", "2", "3", "4"])
        self.assertEqual(active["most"], 2)
        self.assertEqual(len(self.runner.pool.sessions), 5)
        self.assertEqual(self.runner.pool.sessions[0].options, {"locale": "zh-TW"})
        with self.assertRaises(WebRunnerExecuteException):
            self._run(self.runner.run_many([], concurrency=0))


class TestSessionPages(unittest.TestCase):

    def test_no_page_and_switching(self):
        from je_web_runner.utils.async_executor.session import AsyncSession, AsyncSessionError
        session = AsyncSession(MagicMock())
        with self.assertRaises(AsyncSessionError):
            _ = session.page
        session.pages = ["first", "second"]
        self.assertEqual(session.switch_to(0), "first")
        with self.assertRaises(AsyncSessionError):
            session.switch_to(5)

    def test_unknown_browser(self):
        from je_web_runner.utils.async_executor.session import AsyncBrowserPool, AsyncSessionError
        with self.assertRaises(AsyncSessionError):
            AsyncBrowserPool("netscape")


class TestSyncTableKnowsAsyncCommands(unittest.TestCase):

    def test_validation_passes_and_running_synchronously_explains_where_it_runs(self):
        import json
        import tempfile
        from pathlib import Path

        from je_web_runner.utils.executor.action_executor import executor
        from je_web_runner.utils.json.json_validator import validate_action_file

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journey.json"
            path.write_text(json.dumps([["WR_apw_goto", {"url": "https://x.test/"}],
                                        ["WR_apw_click", {"selector": "#buy"}]]), encoding="utf-8")
            validate_action_file(str(path))
        record, failed = executor.collect_action_results([["WR_apw_click", {"selector": "#buy"}]])
        self.assertIn("runs only in the async executor", record[failed[0]])


if __name__ == "__main__":
    unittest.main()
