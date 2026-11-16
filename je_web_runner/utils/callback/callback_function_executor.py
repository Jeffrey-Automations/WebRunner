"""Run a registered ``WR_*`` command and then call a callback with its own arguments."""

import typing
from sys import stderr

from je_web_runner.utils.exception.exception_tags import get_bad_trigger_function, get_bad_trigger_method
from je_web_runner.utils.exception.exceptions import CallbackExecutorException
from je_web_runner.utils.executor._event_table import COMMANDS
from je_web_runner.utils.executor._playwright_commands import PLAYWRIGHT_COMMANDS
from je_web_runner.utils.executor.action_executor import execute_action, execute_files

# The commands of the executor's table that a callback can be chained to. The callables come from
# the table, so the two cannot drift apart.
_TRIGGER_NAMES: tuple[str, ...] = (
    # webdriver manager
    "WR_get_webdriver_manager", "WR_change_index_of_webdriver", "WR_quit",
    # test object
    "WR_SaveTestObject", "WR_CleanTestObject",
    # webdriver wrapper
    "WR_set_driver", "WR_set_webdriver_options_capability", "WR_find_element", "WR_find_elements",
    "WR_implicitly_wait", "WR_explict_wait", "WR_to_url", "WR_forward", "WR_back", "WR_refresh", "WR_switch",
    "WR_set_script_timeout", "WR_set_page_load_timeout", "WR_get_cookies", "WR_get_cookie", "WR_add_cookie",
    "WR_delete_cookie", "WR_delete_all_cookies", "WR_execute", "WR_execute_script", "WR_execute_async_script",
    "WR_move_to_element", "WR_move_to_element_with_offset", "WR_drag_and_drop", "WR_drag_and_drop_offset",
    "WR_perform", "WR_reset_actions", "WR_left_click", "WR_left_click_and_hold", "WR_right_click",
    "WR_left_double_click", "WR_release", "WR_press_key", "WR_release_key", "WR_move_by_offset", "WR_pause",
    "WR_send_keys", "WR_send_keys_to_element", "WR_scroll", "WR_check_current_webdriver", "WR_maximize_window",
    "WR_fullscreen_window", "WR_minimize_window", "WR_set_window_size", "WR_set_window_position",
    "WR_get_window_position", "WR_get_window_rect", "WR_set_window_rect", "WR_get_screenshot_as_png",
    "WR_get_screenshot_as_base64", "WR_get_log", "WR_single_quit",
    # web element
    "WR_element_submit", "WR_element_clear", "WR_element_get_property", "WR_element_get_dom_attribute",
    "WR_element_get_attribute", "WR_element_is_selected", "WR_element_is_enabled", "WR_input_to_element",
    "WR_click_element", "WR_element_is_displayed", "WR_element_value_of_css_property", "WR_element_screenshot",
    "WR_element_change_web_element", "WR_element_check_current_web_element", "WR_element_get_select",
    # init test record
    "WR_set_record_enable",
    # generate report
    "WR_generate_html", "WR_generate_html_report", "WR_generate_json", "WR_generate_json_report", "WR_generate_xml",
    "WR_generate_xml_report",
    # execute
    "WR_execute_action", "WR_execute_files",
    # Add package
    "WR_add_package_to_executor", "WR_add_package_to_callback_executor",
    # ----- naming aliases (mirror action_executor) ----------------
    "WR_new_driver", "WR_quit_all", "WR_quit_current", "WR_explicit_wait", "WR_save_test_object",
    "WR_clear_test_objects", "WR_find_recorded_element", "WR_find_recorded_elements", "WR_element_input",
    "WR_element_click", "WR_element_assert",
    # usable Select wrappers
    "WR_element_select_by_value", "WR_element_select_by_index", "WR_element_select_by_visible_text",
)


class CallbackFunctionExecutor:
    """Maps command names to callables and runs one of them followed by a callback."""

    def __init__(self):
        # 事件字典：將字串名稱對應到實際可執行的函式
        # Event dictionary: map string keys to actual callable functions
        table = {name: COMMANDS[name] for name in _TRIGGER_NAMES}
        # the table binds these two to the executor that owns it; a callback runs the global one
        table.update(WR_execute_action=execute_action, WR_execute_files=execute_files)
        # every Playwright command, as the action executor has them
        self.event_dict: dict = {**table, **PLAYWRIGHT_COMMANDS}

    def callback_function(
            self,
            trigger_function_name: str,
            callback_function: typing.Callable,
            callback_function_param: dict | None = None,
            callback_param_method: str = "kwargs",
            **kwargs
    ):
        """
        執行指定的觸發函式，並在完成後執行回呼函式
        Execute a trigger function, then execute a callback function

        :param trigger_function_name: 要觸發的函式名稱 (必須存在於 event_dict)
                                      The function name to trigger (must exist in event_dict)
        :param callback_function: 要執行的回呼函式 / callback function to execute
        :param callback_function_param: 回呼函式的參數 (dict 或 list)
                                        Parameters for callback function (dict or list)
        :param callback_param_method: 回呼函式參數傳遞方式 ["kwargs", "args"]
                                      How to pass callback params ["kwargs", "args"]
        :param kwargs: 傳遞給觸發函式的參數 / parameters for the trigger function
        :return: 觸發函式的回傳值 / return value of the trigger function
        """
        try:
            if trigger_function_name not in self.event_dict:
                raise CallbackExecutorException(get_bad_trigger_function)

            # 執行觸發函式
            # Execute trigger function
            execute_return_value = self.event_dict[trigger_function_name](**kwargs)

            # 執行回呼函式
            # Execute callback function
            if callback_function_param is not None:
                if callback_param_method not in ["kwargs", "args"]:
                    raise CallbackExecutorException(get_bad_trigger_method)
                if callback_param_method == "kwargs":
                    callback_function(**callback_function_param)
                else:
                    callback_function(*callback_function_param)
            else:
                callback_function()

            return execute_return_value
        except Exception as error:  # pylint: disable=broad-exception-caught  # any failure is reported on stderr
            print(repr(error), file=stderr)
            return None


# 全域回呼執行器實例
# Global callback executor instance
callback_executor = CallbackFunctionExecutor()
