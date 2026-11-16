"""
測試紀錄：每次 wrapper 呼叫的結果，供報告使用
Test records: the outcome of every wrapper call, which the reports are built from.
"""
import contextlib
import datetime
import threading
from typing import Iterator

from je_web_runner.utils.exception.exceptions import describe_error
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class TestRecord:
    """
    測試紀錄管理器
    Test record manager
    """

    # Domain class — not a pytest test container.
    __test__ = False

    def __init__(self, init_record: bool = False):
        # 儲存所有測試紀錄的清單
        # List to store all test records
        self.test_record_list: list = []

        # 是否啟用紀錄功能
        # Flag to enable/disable recording
        self.init_record: bool = init_record

    def clean_record(self) -> None:
        """
        清空所有測試紀錄
        Clear all test records
        """
        self.test_record_list = []

    def set_record_enable(self, set_enable: bool = True):
        """
        開啟或關閉紀錄功能
        Enable or disable recording

        :param set_enable: True = 開啟紀錄, False = 關閉紀錄
                           True = enable recording, False = disable recording
        """
        web_runner_logger.info(f"set_record_enable, set_enable: {set_enable}")
        self.init_record = set_enable


NO_EXCEPTION = "None"
_tracking = threading.local()


def _tracked() -> list[list[dict]]:
    if not hasattr(_tracking, "scopes"):
        _tracking.scopes = []
    return _tracking.scopes


@contextlib.contextmanager
def track_records() -> Iterator[list[dict]]:
    """
    收集這個執行緒在區塊內新增的紀錄
    Collect the records this thread adds during the ``with`` block (none while recording is off).
    """
    mine: list[dict] = []
    _tracked().append(mine)
    try:
        yield mine
    finally:
        _tracked().pop()


@contextlib.contextmanager
def record_file(path: str) -> Iterator[None]:
    """
    標記區塊內的紀錄屬於哪個動作檔
    Mark the records this thread adds during the ``with`` block as belonging to the action file
    ``path`` (their ``file`` key), so a report can group them. A block inside another keeps the
    outer file: the file a run started from, not one it called.
    """
    outermost = getattr(_tracking, "file", None) is None
    if outermost:
        _tracking.file = path
    try:
        yield
    finally:
        if outermost:
            _tracking.file = None


def mark_handled(records: list[dict]) -> int:
    """
    把已被處理的失敗標成非失敗
    Mark the failures among ``records`` as handled: something caught the failure on purpose (a
    ``succeeds`` condition, a ``WR_try`` with ``on_error``, a retry that goes on). The error text moves
    to ``handled_exception`` and ``program_exception`` becomes ``"None"``, so reports and the run's
    verdict do not count it. Return how many were marked.
    """
    marked = 0
    for record in records:
        if record.get("program_exception", NO_EXCEPTION) != NO_EXCEPTION:
            record["handled_exception"] = record["program_exception"]
            record["program_exception"] = NO_EXCEPTION
            marked += 1
    return marked


# 全域單例，用來管理測試紀錄
# Global singleton instance to manage test records
test_record_instance = TestRecord()


def record_action_to_list(function_name: str,
                          local_param: dict | None,
                          program_exception: Exception | None = None):
    """
    將一次函式呼叫紀錄到 test_record_list
    Record a function call into test_record_list

    :param function_name: 呼叫的函式名稱 / name of the function being called
    :param local_param: 呼叫時使用的參數 (dict) / parameters used in the call (dict)
    :param program_exception: 執行過程中發生的例外 (若有) / exception occurred during execution (if any)
    """
    if not test_record_instance.init_record:
        # 若未啟用紀錄，則直接跳過
        # Skip if recording is disabled
        return
    record = {
        "function_name": function_name,
        "local_param": local_param,
        "time": str(datetime.datetime.now()),
        "program_exception": describe_error(program_exception)
    }
    running_file = getattr(_tracking, "file", None)
    if running_file is not None:
        record["file"] = running_file
    test_record_instance.test_record_list.append(record)
    for scope in _tracked():
        scope.append(record)
