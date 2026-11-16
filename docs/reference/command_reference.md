# WebRunner command reference

Auto-generated from the executor's event_dict (1201 commands).

| Command | Signature | Summary |
| --- | --- | --- |
| `WR__note` | `(text: 'str' = '') -> 'str'` | 不做任何事的註記 |
| `WR_a11y_load_axe` | `(path: 'str') -> 'str'` | 讀取本地 axe-core JS 原始碼檔案 / Read a local axe-core source file. |
| `WR_a11y_run_audit` | `(axe_source: 'str', options: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | 在當前 Selenium 頁面執行 axe.run，回傳結果 dict |
| `WR_a11y_summarise` | `(results: 'dict[str, Any]') -> 'list[dict[str, Any]]'` | 將 axe 結果壓縮成只含 ``id`` / ``impact`` / ``help`` / ``nodes`` 數量的清單 |
| `WR_a11y_trend_aggregate` | `(history: 'list[dict[str, Any]] | None' = None, history_path: 'str | None' = None) -> 'list[dict[str, Any]]'` | Count accessibility violations per day and impact over a history of axe runs. |
| `WR_a11y_trend_write_dashboard` | `(output_path: 'str', history: 'list[dict[str, Any]] | None' = None, history_path: 'str | None' = None, title: 'str' = 'A11y trend') -> 'str'` | Write the accessibility trend of a history of axe runs as an HTML page; returns the file path. |
| `WR_ac_assert_image_on_screen` | `(image_path: 'str', detect_threshold: 'float | None' = None) -> 'list[int]'` | 斷言螢幕上看得到指定圖片，回傳其中心座標 |
| `WR_ac_available` | `() -> 'bool'` | AutoControl 是否已安裝（不 import） |
| `WR_ac_basic_auth` | `(username_env: 'str', password_env: 'str', url: 'str | None' = None, submit: 'bool' = True, wait_seconds: 'float' = 1.0) -> 'None'` | 在瀏覽器的 HTTP 基本認證對話框輸入帳密（從環境變數讀取，不經過動作檔、log 或紀錄） |
| `WR_ac_click_element_native` | `(selector: 'str | None' = None, by: 'str' = 'css selector', mouse_button: 'str' = 'mouse_left', scale: 'float | None' = None) -> 'list[int]'` | 用真正的滑鼠點擊元素（不是 WebDriver 的合成點擊） |
| `WR_ac_fill_native_file_dialog` | `(file_path: 'str', submit: 'bool' = True, wait_seconds: 'float' = 1.0) -> 'str'` | 在已開啟的系統檔案對話框輸入路徑並按 Enter |
| `WR_ac_list_commands` | `() -> 'list[str]'` | 列出可經橋接執行的 AutoControl 命令 |
| `WR_ac_run` | `(action: 'list') -> 'Any'` | 執行一個 AutoControl 動作並回傳結果 |
| `WR_ac_run_actions` | `(actions: 'list') -> 'list[Any]'` | 依序執行 AutoControl 動作並回傳各自的結果；第一個失敗就拋出 |
| `WR_action_formatter_assert_formatted` | `(path: 'str', indent: 'int' = 2) -> 'str'` | Fail when an action file is not in the canonical format; the file is left as it is. |
| `WR_action_formatter_format` | `(actions: 'list[Any]', indent: 'int' = 2) -> 'str'` | Format an action list as canonical JSON text: one action per line, arguments in a fixed order. |
| `WR_action_formatter_format_file` | `(path: 'str', write: 'bool' = False, indent: 'int' = 2) -> 'dict[str, Any]'` | Format an action file; returns the formatted ``text`` and whether it ``changed``. |
| `WR_action_refactor_suggester_analyze` | `(actions: 'list[dict[str, Any]]') -> 'Any'` | Find refactor smells in a list of step objects: hard sleeps, positional XPath, repeated locators. |
| `WR_action_refactor_suggester_assert_clean` | `(actions: 'list[dict[str, Any]]') -> 'Any'` | Fail when a list of step objects has a warning or error level refactor suggestion. |
| `WR_action_refactor_suggester_markdown` | `(actions: 'list[dict[str, Any]]') -> 'str'` | Render the refactor suggestions for a list of step objects as markdown. |
| `WR_adaptive_retry_assert_retryable` | `(error_text: 'str', attempt: 'int' = 1, policy: 'dict[str, Any] | None' = None, ledger_path: 'str | None' = None, file_path: 'str | None' = None) -> 'dict[str, Any]'` | Fail unless the adaptive retry policy would retry this error at this attempt. |
| `WR_adaptive_retry_backoff` | `(attempts: 'int' = 5, policy: 'dict[str, Any] | None' = None) -> 'list[float]'` | The seconds the adaptive retry policy sleeps after each of the first ``attempts`` failed attempts. |
| `WR_adaptive_retry_decide` | `(error_text: 'str', attempt: 'int' = 1, policy: 'dict[str, Any] | None' = None, ledger_path: 'str | None' = None, file_path: 'str | None' = None) -> 'dict[str, Any]'` | Classify an error text and say whether the adaptive retry policy would retry it. |
| `WR_add_cookie` | `(cookie_dict: 'dict') -> 'None'` | 新增 cookie 到當前頁面 |
| `WR_add_package_to_callback_executor` | `(package)` | 將套件的成員加入到 callback_executor 的 event_dict |
| `WR_add_package_to_executor` | `(package)` | 將套件的成員加入到 executor 的 event_dict |
| `WR_add_script_to_evaluate_on_new_document` | `(source: 'str') -> 'str | None'` | 在每次新文件載入前注入一段 JavaScript (常用於 anti-bot / stealth)。 |
| `WR_alert_accept` | `(prompt_text: 'str | None' = None) -> 'None'` | Accept the open alert / confirm / prompt, typing ``prompt_text`` into a prompt first. |
| `WR_alert_dismiss` | `() -> 'None'` | Dismiss the open alert / confirm / prompt. |
| `WR_alert_text` | `() -> 'str'` | The message of the open dialog. |
| `WR_api_mock_attach` | `() -> 'bool'` | Serve the registered mock routes (also ones registered later) on the current Playwright page. |
| `WR_api_mock_calls` | `() -> 'list[list[str]]'` | List the ``[method, url]`` pairs the mock router was asked for, in order. |
| `WR_api_mock_match` | `(method: 'str', url: 'str') -> 'dict[str, Any] | None'` | Ask the mock router what it answers to ``method`` ``url``: ``{"status", "headers", "body"}`` or ``null`` |
| `WR_api_mock_register` | `(method: 'str', url_pattern: 'str', body: 'Any' = '', status: 'int' = 200, times: 'int | None' = None) -> 'dict[str, Any]'` | Register a mocked HTTP route for the Playwright page. |
| `WR_api_mock_reset` | `() -> 'bool'` | Remove every registered mock route and forget the recorded calls. |
| `WR_api_version_compat_assert_matrix` | `(rows: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Fail when any client/server combination of the matrix did not pass; returns the summary. |
| `WR_api_version_compat_assert_request` | `(endpoint: 'str', request_fields: 'list[dict[str, Any]]', server_required_fields: 'list[str]') -> 'bool'` | Fail when the new server requires a request field the old client never sends. |
| `WR_api_version_compat_assert_response` | `(endpoint: 'str', response_fields: 'list[dict[str, Any]]', response: 'dict[str, Any]') -> 'bool'` | Fail when a new server's response drops or retypes a field the old client reads. |
| `WR_api_version_compat_check_response` | `(endpoint: 'str', response_fields: 'list[dict[str, Any]]', response: 'dict[str, Any]') -> 'dict[str, Any]'` | Check a new server's response against the fields an old client reads, without failing the run. |
| `WR_api_version_compat_matrix` | `(rows: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Summarise client/server rows (``client_version``, ``server_version``, ``passed``, ``notes``). |
| `WR_appium_android_caps` | `(app: 'str', device_name: 'str' = 'Android Emulator', platform_version: 'str' = '13', automation_name: 'str' = 'UiAutomator2', extra: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | Convenience: build a capabilities dict for Android. |
| `WR_appium_ios_caps` | `(app: 'str', device_name: 'str' = 'iPhone 15', platform_version: 'str' = '17', automation_name: 'str' = 'XCUITest', extra: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` |  |
| `WR_appium_quit` | `() -> 'None'` | Quit whatever driver is currently registered on the WebRunner wrapper. |
| `WR_appium_start` | `(server_url: 'str', capabilities: 'dict[str, Any]', register: 'bool' = True) -> 'Any'` | 建立 Appium WebDriver 並註冊到 ``webdriver_wrapper_instance`` |
| `WR_apw_assert_text` | `(selector: 'str', expected: 'str') -> 'str'` | Fail unless the element's text contains ``expected``; returns the text. |
| `WR_apw_assert_title` | `(expected: 'str') -> 'str'` | Fail unless the page title contains ``expected``; returns the title. |
| `WR_apw_click` | `(selector: 'str') -> 'None'` | Click the element ``selector`` matches (Playwright waits until it is actionable). |
| `WR_apw_close_page` | `() -> 'int'` | Close the current page; returns how many stay open. |
| `WR_apw_evaluate` | `(script: 'str', arg: 'Any' = None) -> 'Any'` | Evaluate JavaScript in the page (behind the arbitrary-script gate). |
| `WR_apw_fill` | `(selector: 'str', value: 'str') -> 'None'` | Fill an input. |
| `WR_apw_goto` | `(url: 'str', wait_until: 'str' = 'load') -> 'str'` | Navigate the current page (opening one first if none is open); returns the final URL. |
| `WR_apw_new_page` | `(url: 'str | None' = None) -> 'int'` | Open a page (another tab of the same user), make it current, optionally load ``url``; returns its index. |
| `WR_apw_press` | `(selector: 'str', key: 'str') -> 'None'` | Press ``key`` (``Enter``, ``Control+A`` …) in the element. |
| `WR_apw_screenshot` | `(path: 'str', full_page: 'bool' = False) -> 'str'` | Save a PNG of the current page; returns the path. |
| `WR_apw_sleep` | `(seconds: 'float') -> 'None'` | Pause this action list only; the others keep running. |
| `WR_apw_switch_to_page` | `(index: 'int') -> 'str'` | Make page ``index`` current; returns its URL. |
| `WR_apw_text` | `(selector: 'str') -> 'str'` | The element's inner text. |
| `WR_apw_title` | `() -> 'str'` | The current page's title. |
| `WR_apw_url` | `() -> 'str'` | The current page's URL. |
| `WR_apw_wait_for_selector` | `(selector: 'str', state: 'str' = 'visible', timeout: 'float' = 10.0) -> 'None'` | Wait until ``selector`` is ``attached`` / ``detached`` / ``visible`` / ``hidden`` (``timeout`` in seconds). |
| `WR_apw_wait_for_websocket_message` | `(contains: 'str', timeout: 'float' = 10.0) -> 'dict[str, Any]'` | Wait until a received WebSocket frame contains ``contains``; returns it. |
| `WR_apw_websocket_messages` | `(direction: 'str | None' = None) -> 'list[dict[str, Any]]'` | Every WebSocket frame the session's pages sent or received: ``{url, direction, payload}``. |
| `WR_assert_no_4xx_or_5xx` | `() -> 'None'` |  |
| `WR_assert_no_5xx` | `() -> 'None'` |  |
| `WR_assert_no_console_errors` | `() -> 'None'` |  |
| `WR_assert_no_secrets` | `(data: 'Any') -> 'None'` | 掃描並在有發現時拋例外 / Scan and raise ``SecretsFound`` on any hit. |
| `WR_assert_title` | `(value: 'str') -> 'str'` | 斷言目前頁面標題等於 ``value`` |
| `WR_assert_var` | `(var: 'str', op: 'str' = 'truthy', value: 'Any' = None) -> 'bool'` | 斷言變數符合條件 |
| `WR_assert_web_vitals` | `(budgets: 'dict[str, float] | None' = None, observe_ms: 'int' = 1000, source: 'str' = 'page', url: 'str | None' = None, json_path: 'str | None' = None, html_path: 'str | None' = None, lighthouse_path: 'str' = 'lighthouse') -> 'dict[str, Any]'` | 斷言 LCP / CLS / INP / FCP 都在預算內 |
| `WR_attach_to_existing_browser` | `(debugger_address: 'str', webdriver_name: 'str' = 'chrome', options: 'list[str] | None' = None, experimental_options: 'dict | None' = None, **kwargs)` | 附加到一個已啟動且開啟 remote debugging 埠的 Chrome / Edge 實例。 |
| `WR_audit_security_headers` | `(headers: 'dict[str, str]', required: 'list[dict[str, Any]] | None' = None) -> 'list[dict[str, Any]]'` | 對 headers dict 套用規則表，回傳所有違反項目 |
| `WR_audit_security_headers_url` | `(url: 'str', timeout: 'int' = 30, required: 'list[dict[str, Any]] | None' = None) -> 'list[dict[str, Any]]'` | GET ``url`` 並稽核回應 headers |
| `WR_back` | `() -> 'None'` | 返回上一頁 / Navigate back |
| `WR_backend_log_correlator_attach` | `(bundle_dir: 'str', logs: 'list[dict[str, Any]]', filename: 'str' = 'backend_logs.json') -> 'str'` | Write correlated log lines (as the fetch commands return them) into a failure-bundle directory. |
| `WR_backend_log_correlator_elasticsearch` | `(trace: 'str', base_url: 'str', index: 'str', trace_field: 'str' = 'trace_id', size: 'int' = 500) -> 'list[dict[str, Any]]'` | Fetch the log lines of a trace from an Elasticsearch ``index`` at ``base_url`` (sends an HTTP request). |
| `WR_backend_log_correlator_file` | `(trace: 'str', log_path: 'str', trace_field: 'str' = 'trace_id', fallback_to_substring: 'bool' = True) -> 'list[dict[str, Any]]'` | List the lines of a backend log file that belong to a trace. |
| `WR_backend_log_correlator_loki` | `(trace: 'str', base_url: 'str', label: 'str' = 'trace_id', limit: 'int' = 1000, timeout: 'float' = 15.0) -> 'list[dict[str, Any]]'` | Fetch the log lines of a trace from Grafana Loki at ``base_url`` (sends an HTTP request). |
| `WR_backend_log_correlator_trace_id` | `(trace: 'str') -> 'str'` | Return the 32-hex trace id of a W3C ``traceparent`` header value (or check a bare trace id). |
| `WR_background_sync_assert_check` | `(payload: 'dict[str, Any]', tag: 'str', at_least: 'int' = 1, require_retry: 'bool' = False, forbid_last_chance: 'bool' = False) -> 'dict[str, Any]'` | Fail unless the harvested log shows sync ``tag`` registered and fired ``at_least`` times (0 = registration |
| `WR_background_sync_assert_harvest` | `() -> 'dict[str, Any]'` | Read and empty the Background Sync recorder: ``{"registered": [tags], "fired": [{tag, lastChance, ts}]}``. |
| `WR_background_sync_assert_install` | `() -> 'bool'` | Install the Background Sync recorder on the current page; run it before the page registers a sync. |
| `WR_bidi_backend_events` | `(clear: 'bool' = False) -> 'list[dict[str, Any]]'` | List the BiDi events collected so far, each as ``{"name": ..., "payload": {...}}``. |
| `WR_bidi_backend_reset` | `() -> 'int'` | Stop every BiDi subscription and forget the collected events; return how many were stopped. |
| `WR_bidi_backend_subscribe` | `(event: 'str' = 'console') -> 'dict[str, Any]'` | Start collecting a BiDi event of the current browser; read them with ``WR_bidi_backend_events``. |
| `WR_block_urls` | `(patterns: 'list[str]') -> 'None'` | 透過 CDP ``Network.setBlockedURLs`` 阻擋符合任一 pattern 的請求。 |
| `WR_bootstrapper_init_workspace` | `(directory: 'str', overwrite: 'bool' = False) -> 'dict[str, str]'` | Create a starter workspace in ``directory``; returns each file as ``created`` or ``skipped``. |
| `WR_bootstrapper_starter_files` | `() -> 'list[dict[str, str]]'` | List the files a new WebRunner workspace starts with (relative path and content). |
| `WR_breakpoint` | `(message: 'str' = '') -> 'bool'` | 在逐步執行時暫停 |
| `WR_bring_to_front` | `() -> 'None'` | 將瀏覽器視窗叫到最上層 (透過 CDP ``Page.bringToFront``)。 |
| `WR_bug_repro_stability_assert_deterministic` | `(outcomes: 'list[Any]') -> 'Any'` | Fail unless every recorded attempt failed (the bug reproduces every time). |
| `WR_bug_repro_stability_assert_min_repro_pct` | `(outcomes: 'list[Any]', minimum: 'float') -> 'Any'` | Fail when fewer than ``minimum`` percent of the recorded attempts failed. |
| `WR_bug_repro_stability_markdown` | `(outcomes: 'list[Any]') -> 'str'` | Render the repro-stability summary of recorded attempts as markdown. |
| `WR_bug_repro_stability_summarize` | `(outcomes: 'list[Any]') -> 'Any'` | Classify recorded attempts of one test as deterministic, flaky or non_reproducible. |
| `WR_build_action_schema` | `() -> 'dict[str, Any]'` | 產生一份描述 action JSON 結構的 Draft 2020-12 Schema |
| `WR_build_command_reference` | `(title: 'str' = 'WebRunner command reference') -> 'str'` | 產生整份命令參考（Markdown 字串） |
| `WR_build_dependency_graph` | `(paths: 'Sequence[str]', *, allow_invalid: 'bool' = False) -> 'dict[str, list[str]]'` | 依基本檔名建立 ``{path: [dep_path, ...]}`` 圖 |
| `WR_build_replay_html` | `(records: 'list[dict[str, Any]] | None' = None, screenshot_dir: 'str | None' = None, title: 'str' = 'WebRunner replay') -> 'str'` | 產生 self-contained HTML 報告字串 |
| `WR_bundle_budget_assert` | `(har: 'Any', budgets: 'dict[str, int] | None' = None, biggest_n: 'int' = 10) -> 'dict[str, Any]'` | Fail (``BundleBudgetError``) when a HAR passes a size budget; see ``WR_bundle_budget_evaluate``. |
| `WR_bundle_budget_evaluate` | `(har: 'Any', budgets: 'dict[str, int] | None' = None, biggest_n: 'int' = 10) -> 'dict[str, Any]'` | Add up a HAR's bytes per asset kind and compare them with size budgets. |
| `WR_bundle_budget_markdown` | `(har: 'Any', budgets: 'dict[str, int] | None' = None, biggest_n: 'int' = 10) -> 'str'` | Render a HAR's bundle-budget result as a Markdown table; arguments as ``WR_bundle_budget_evaluate``. |
| `WR_bundle_diff_pr_assert_growth` | `(base_har: 'Any', head_har: 'Any', max_growth_bytes: 'int' = 0) -> 'dict[str, Any]'` | Fail (``BundleDiffPrError``) when the head HAR outgrows the base HAR by more than ``max_growth_bytes``. |
| `WR_bundle_diff_pr_diff` | `(base_har: 'Any', head_har: 'Any') -> 'dict[str, Any]'` | Compare the asset sizes of two HARs (base branch and pull-request head). |
| `WR_bundle_diff_pr_markdown` | `(base_har: 'Any', head_har: 'Any', top_n: 'int' = 10, min_bytes: 'int' = 1024) -> 'str'` | Render the size difference of two HARs as Markdown for a pull-request comment. |
| `WR_call_file` | `(path: 'str', params: 'dict[str, Any] | None' = None) -> 'list'` | 執行另一個動作檔的動作 |
| `WR_capture` | `(name: 'str', action: 'list') -> 'Any'` | 執行一個動作並把回傳值存成變數 |
| `WR_cdp` | `(method: 'str', params: 'dict[str, Any] | None' = None) -> 'Any'` | 在當前 Selenium driver 執行 CDP 命令 |
| `WR_cdp_tap_load` | `(path: 'str') -> 'list[dict[str, Any]]'` | Read a CDP recording file written by ``WR_cdp_tap_stop``. |
| `WR_cdp_tap_records` | `() -> 'list[dict[str, Any]]'` | List the CDP calls recorded so far (``timestamp``, ``method``, ``params``, ``return_value``, ``error``). |
| `WR_cdp_tap_start` | `(output_path: 'str') -> 'bool'` | Start recording every CDP command the current browser is sent, with its result. |
| `WR_cdp_tap_stop` | `() -> 'dict[str, Any]'` | Stop the CDP recording and write it to the file given to ``WR_cdp_tap_start``. |
| `WR_change_index_of_webdriver` | `(index_of_webdriver: int) -> None` | 切換當前 WebDriver |
| `WR_chaos_hooks_fault_types` | `() -> 'list[str]'` | The fault names ``WR_chaos_hooks_plan`` can schedule. |
| `WR_chaos_hooks_plan` | `(step_names: 'list[str]', faults: 'list[str] | None' = None, fault_rate: 'float' = 0.2, max_events: 'int | None' = None, skip_first: 'int' = 1, skip_last: 'int' = 0, seed: 'int | None' = None) -> 'dict[str, Any]'` | Decide, reproducibly, which steps of a flow get which fault (offline, slow network, reload...). |
| `WR_check_current_webdriver` | `(check_dict: 'dict') -> 'None'` | 驗證當前 WebDriver 狀態，若不符合會拋出例外 |
| `WR_chrome_options_with_extension` | `(crx_or_dir: 'str', options: 'ChromeOptions | None' = None) -> 'ChromeOptions'` | 回傳已掛上擴充功能的 ChromeOptions |
| `WR_chrome_profile_cleanup_locks` | `(profile_dir: 'str') -> 'list[str]'` | Remove the Singleton lock files a crashed Chrome leaves in a profile directory. |
| `WR_chrome_profile_options` | `(profile_dir: 'str', flags: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | The Chrome arguments and experimental options for a persistent profile with stealth settings. |
| `WR_chrome_profile_snapshot` | `(profile_dir: 'str', snapshot_dir: 'str', full_copy: 'bool' = False) -> 'str'` | Copy a Chrome profile into a disposable snapshot directory, leaving out caches and lock files. |
| `WR_chrome_profile_sync_back` | `(snapshot_dir: 'str', profile_dir: 'str') -> 'list[str]'` | Copy the login state (cookies, login data, preferences) from a snapshot back into the profile. |
| `WR_classify_error` | `(error_repr: 'str') -> 'str | None'` | 依錯誤字串嘗試判定 transient / environment；無法判定回傳 None |
| `WR_classify_failure` | `(error_repr: 'str', ledger_path: 'str | None' = None, file_path: 'str | None' = None) -> 'str'` | 綜合錯誤字串與 ledger 歷史回傳分類 |
| `WR_classify_failures` | `(failures: 'Iterable[dict[str, Any]]', ledger_path: 'str | None' = None) -> 'dict[str, str]'` | 對 ``[{function_name, exception, file_path?}, ...]`` 各分類 |
| `WR_CleanTestObject` | `() -> None` | 清空所有測試物件紀錄 |
| `WR_clear_device_metrics` | `() -> 'None'` | 清除 ``set_device_metrics`` 設定。 |
| `WR_clear_fallback_locators` | `() -> 'None'` |  |
| `WR_clear_geolocation_override` | `() -> 'None'` | 清除 ``set_geolocation`` 設定。 |
| `WR_clear_origin_storage` | `(origin: 'str') -> 'None'` | 透過 CDP ``Storage.clearDataForOrigin`` 一次清掉指定 origin 的所有儲存 |
| `WR_clear_permissions` | `() -> 'None'` | Reset every granted permission. |
| `WR_clear_test_objects` | `() -> None` | 清空所有測試物件紀錄 |
| `WR_clear_vars` | `() -> 'None'` | 清除所有變數 |
| `WR_click_element` | `() -> 'None'` | 點擊 WebElement |
| `WR_clickjacking_audit_assert_protected` | `(target_url: 'str', headers: 'Any', probe_status: 'str | None' = None) -> 'dict[str, Any]'` | Fail unless the headers forbid third-party framing (and the probe, when given, was blocked). |
| `WR_clickjacking_audit_headers` | `(target_url: 'str', headers: 'Any', probe_status: 'str | None' = None) -> 'dict[str, Any]'` | Classify a response's X-Frame-Options / CSP frame-ancestors headers against clickjacking. |
| `WR_clickjacking_audit_probe_page` | `(target_url: 'str') -> 'str'` | Return the HTML of a probe page that tries to embed ``target_url`` in an iframe. |
| `WR_clock_freeze` | `(moment: 'str | int | float', advance_ms_per_real_second: 'float' = 0.0) -> 'None'` | 凍結頁面時間 |
| `WR_close_window` | `() -> 'None'` | 關閉當前 tab / window (不會結束整個 driver；要結束請用 ``quit``) |
| `WR_commit_msg_trigger_assert_no_skip` | `(message: 'str') -> 'Any'` | Fail when the commit message asks to skip CI. |
| `WR_commit_msg_trigger_assigned_shard` | `(message: 'str', total_shards: 'int') -> 'int | None'` | The 0-based shard the commit message asks for out of ``total_shards``, or ``null`` when it names none. |
| `WR_commit_msg_trigger_parse` | `(message: 'str') -> 'Any'` | Read the CI directives of a commit message: skip, buckets, labels, shard and linked tickets. |
| `WR_commit_msg_trigger_should_run_job` | `(message: 'str', job_name: 'str') -> 'bool'` | Whether the commit message lets the CI job ``job_name`` run. |
| `WR_compression_streams_assert_ratio` | `(original_size: 'int', compressed_size: 'int', max_ratio: 'float') -> 'float'` | Fail when the compressed size is more than ``max_ratio`` (0 to 1) of the original size; returns the ratio. |
| `WR_compression_streams_assert_round_trip` | `(original_text: 'str', compressed_base64: 'str', algorithm: 'str' = 'gzip') -> 'bool'` | Fail unless the base64 ``compressed_base64`` decompresses back to ``original_text`` (as UTF-8). |
| `WR_compression_streams_compress` | `(text: 'str', algorithm: 'str' = 'gzip') -> 'str'` | Compress ``text`` with the current page's ``CompressionStream`` and return the bytes as base64. |
| `WR_compression_streams_decompress` | `(compressed_base64: 'str', algorithm: 'str' = 'gzip') -> 'dict[str, Any]'` | Decompress base64 bytes (``gzip`` / ``deflate`` / ``deflate-raw`` / ``br``): ``{"text": ..., "size": n}``. |
| `WR_compute_pressure_assert` | `(payload: 'dict[str, Any]', level: 'str' = 'critical', name: 'str | None' = None, only_if_fired: 'bool' = False, require_disconnect: 'bool' = False) -> 'dict[str, Any]'` | Fail unless the log ``{"reactions": [{name, level, ts}], "fires": [levels], "disconnectCount": n}`` has a |
| `WR_consent_audit_assert_passes` | `(before_consent: 'list[dict[str, Any]] | None' = None, after_consent: 'list[dict[str, Any]] | None' = None, user_rejected: 'bool' = False, extra_rules: 'list[dict[str, Any]] | None' = None) -> 'dict[str, Any]'` | Fail when a non-essential cookie exists before consent or comes back after a reject. |
| `WR_consent_audit_check` | `(before_consent: 'list[dict[str, Any]]', after_consent: 'list[dict[str, Any]] | None' = None, user_rejected: 'bool' = False, extra_rules: 'list[dict[str, Any]] | None' = None) -> 'dict[str, Any]'` | Report non-essential cookies set before consent and, with ``user_rejected``, those set after a reject. |
| `WR_consent_audit_classify` | `(cookies: 'list[dict[str, Any]]', extra_rules: 'list[dict[str, Any]] | None' = None) -> 'list[dict[str, Any]]'` | Classify cookies as necessary / preferences / analytics / marketing / social / unknown. |
| `WR_consent_audit_classify_page` | `(extra_rules: 'list[dict[str, Any]] | None' = None) -> 'list[dict[str, Any]]'` | Classify the cookies the running browser holds right now. |
| `WR_console_error_budget_assert` | `(messages: 'list[dict[str, Any]] | None' = None, budget: 'dict[str, Any] | None' = None, source: 'str' = 'plain') -> 'dict[str, Any]'` | Fail when console errors or warnings pass the budget; ``messages`` omitted means the browser's log. |
| `WR_console_error_budget_evaluate` | `(messages: 'list[dict[str, Any]]', budget: 'dict[str, Any] | None' = None, source: 'str' = 'plain') -> 'dict[str, Any]'` | Count console errors and warnings against a budget. |
| `WR_console_error_budget_page` | `(budget: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | Count the current browser's console errors against a budget (see ``WR_console_error_budget_evaluate``). |
| `WR_console_messages` | `() -> 'list[dict[str, Any]]'` | ``{type, text, location}`` per console message or JavaScript error collected. |
| `WR_contract_testing_assert` | `(response_body: 'Any', schema: 'dict[str, Any]') -> 'bool'` | Fail when a response body does not match the JSON schema. |
| `WR_contract_testing_validate` | `(response_body: 'Any', schema: 'dict[str, Any]') -> 'dict[str, Any]'` | Validate a response body against a JSON schema subset; returns ``{"valid", "errors"}``. |
| `WR_contract_testing_validate_openapi` | `(response_body: 'Any', path: 'str', method: 'str', status: 'int', openapi_doc: 'dict[str, Any] | None' = None, openapi_path: 'str | None' = None) -> 'dict[str, Any]'` | Validate a response body against the schema an OpenAPI 3 document (the object, or the path of its JSON |
| `WR_cookie_chips_audit_assert_no_errors` | `(page_url: 'str', har: 'dict[str, Any] | None' = None, set_cookie_headers: 'list[str] | None' = None, cookie_url: 'str' = '') -> 'list[dict[str, Any]]'` | Fail when a HAR and / or a list of ``Set-Cookie`` values holds an error-level CHIPS finding. |
| `WR_cookie_chips_audit_har` | `(har: 'dict[str, Any]', page_url: 'str') -> 'list[dict[str, Any]]'` | Audit every ``Set-Cookie`` response header of a HAR object for CHIPS compliance. |
| `WR_cookie_chips_audit_headers` | `(set_cookie_headers: 'list[str]', page_url: 'str', cookie_url: 'str') -> 'list[dict[str, Any]]'` | Audit ``Set-Cookie`` header values for CHIPS (``Partitioned``) compliance. |
| `WR_cookie_scope_abuse_assert_no_errors` | `(cookies: 'list[dict[str, Any]]', page_host: 'str') -> 'list[dict[str, Any]]'` | Fail when a session-like cookie misses HttpOnly, Secure or a Strict / Lax SameSite. |
| `WR_cookie_scope_abuse_audit` | `(cookies: 'list[dict[str, Any]]', page_host: 'str') -> 'list[dict[str, Any]]'` | Find session-like cookies that are scoped too widely or lack HttpOnly / Secure / SameSite. |
| `WR_cookie_scope_abuse_audit_page` | `() -> 'list[dict[str, Any]]'` | Audit the cookies of the running browser against the host of the current page. |
| `WR_cookie_store_api_assert` | `(cookies: 'list[dict[str, Any]]', present: 'str | None' = None, value: 'str | None' = None, absent: 'str | None' = None, secure_only: 'bool' = False) -> 'list[dict[str, Any]]'` | Check a cookie list: ``present`` names a cookie that must exist (with ``value`` when given), ``absent`` one |
| `WR_cookie_store_api_assert_change` | `(events: 'list[dict[str, Any]]', name: 'str') -> 'dict[str, Any]'` | Fail unless one recorded change event changed or deleted the cookie ``name``; returns that event. |
| `WR_cookie_store_api_changes` | `() -> 'list[dict[str, Any]]'` | The cookie change events recorded so far: ``[{"changed": [cookies], "deleted": [names], "timestamp_ms"}]``. |
| `WR_cookie_store_api_harvest` | `() -> 'list[dict[str, Any]]'` | Read the current page's cookies through ``cookieStore.getAll()`` (empty where the API is missing). |
| `WR_cookie_store_api_install_listener` | `() -> 'bool'` | Start recording the current page's cookie ``change`` events for ``WR_cookie_store_api_changes``. |
| `WR_coop_coep_audit_assert_isolated` | `(page_url: 'str', page_headers: 'Any', har: 'dict[str, Any] | str | None' = None) -> 'dict[str, Any]'` | Fail unless the page is cross-origin isolated and no resource in ``har`` violates COEP. |
| `WR_coop_coep_audit_isolation` | `(page_url: 'str', page_headers: 'Any', har: 'dict[str, Any] | str | None' = None) -> 'dict[str, Any]'` | Report whether a page's COOP / COEP headers make it cross-origin isolated. |
| `WR_cors_matrix_assert_credentials_origin` | `(responses: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Fail when a credentialed request was answered with ``Access-Control-Allow-Origin: *``. |
| `WR_cors_matrix_assert_origin_blocked` | `(responses: 'list[dict[str, Any]]', origin: 'str') -> 'list[dict[str, Any]]'` | Fail when any recorded response lets ``origin`` through. |
| `WR_cors_matrix_build` | `(verbs: 'list[str] | None' = None, origins: 'list[str] | None' = None, credentials_modes: 'list[bool] | None' = None) -> 'list[dict[str, Any]]'` | List the ``verb`` x ``origin`` x ``with_credentials`` cases of a CORS test matrix. |
| `WR_cors_matrix_classify` | `(responses: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Decide for recorded CORS responses whether the browser would allow each request. |
| `WR_coverage_map_assert_covered` | `(directory: 'str', declared_routes: 'list[str]', glob: 'str' = '**/*.json', normalise_params: 'bool' = True) -> 'dict[str, list[str]]'` | Fail when one of ``declared_routes`` has no action file navigating to it. |
| `WR_coverage_map_build` | `(directory: 'str', glob: 'str' = '**/*.json', normalise_params: 'bool' = True) -> 'dict[str, Any]'` | Index the action files under a directory by the URL routes they navigate to. |
| `WR_coverage_map_markdown` | `(directory: 'str', declared_routes: 'list[str] | None' = None, glob: 'str' = '**/*.json', normalise_params: 'bool' = True) -> 'str'` | A Markdown table of route, test count and files; for ``declared_routes`` or every route found. |
| `WR_coverage_map_uncovered` | `(directory: 'str', declared_routes: 'list[str]', glob: 'str' = '**/*.json', normalise_params: 'bool' = True) -> 'list[str]'` | The ``declared_routes`` that no action file under ``directory`` navigates to. |
| `WR_credential_management_assert` | `(payload: 'dict[str, Any]', stored_id: 'str | None' = None, prevent_silent_access: 'int' = 0, mediation: 'str | None' = None, forbid_password: 'bool' = False) -> 'dict[str, Any]'` | Check a harvested credentials log: ``stored_id`` was passed to ``credentials.store``, |
| `WR_credential_management_harvest` | `() -> 'dict[str, Any]'` | Read and empty the credentials mock's log: ``{"stored": [...], "gets": [...], "preventCount": n}``. |
| `WR_credential_management_install` | `(credentials: 'list[dict[str, Any]] | None' = None) -> 'bool'` | Replace the page's ``navigator.credentials`` with a recording mock that answers ``get`` with the first of |
| `WR_critical_css_audit_analyse` | `(html: 'str') -> 'dict[str, Any]'` | Report an HTML document's critical CSS: inline blocks and bytes, blocking and preloaded stylesheets. |
| `WR_critical_css_audit_assert` | `(html: 'str | None' = None, max_inline_bytes: 'int' = 14336, require_inline: 'bool' = True, require_preload: 'bool' = True) -> 'dict[str, Any]'` | Fail when a document breaks the critical-CSS rules; ``html`` omitted means the current page. |
| `WR_critical_css_audit_page` | `() -> 'dict[str, Any]'` | Report the critical-CSS facts of the current page (see ``WR_critical_css_audit_analyse``). |
| `WR_cross_browser_assert_parity` | `(runs: 'list[dict[str, Any]]', reference_browser: 'str | None' = None, allow_fields: 'list[str] | None' = None, only_major: 'bool' = True) -> 'bool'` | Fail when a browser's run differs from the reference (arguments as ``WR_cross_browser_diff``). |
| `WR_cross_browser_capture` | `(browser: 'str') -> 'dict[str, Any]'` | Record the current page as one browser's run: ``{"browser": str, "title": str, "dom_text": html}``. |
| `WR_cross_browser_diff` | `(runs: 'list[dict[str, Any]]', reference_browser: 'str | None' = None) -> 'dict[str, Any]'` | Compare what several browsers produced for the same page against a reference run (default: the first). |
| `WR_csp_reporter_assert_no_violations` | `(allow_directives: 'list[str] | None' = None) -> 'bool'` | Fail when the current page recorded a CSP violation of a directive not in ``allow_directives``. |
| `WR_csp_reporter_collect` | `() -> 'list[dict[str, Any]]'` | Return the CSP violations recorded on the current page since ``WR_csp_reporter_install``. |
| `WR_csp_reporter_install` | `() -> 'bool'` | Start recording the Content-Security-Policy violations the current page fires. |
| `WR_csp_violation_parser_assert_no_enforced` | `(reports: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Fail when a report is an enforced violation (report-only ones are returned, not failed). |
| `WR_csp_violation_parser_parse` | `(reports: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Normalise CSP ``report-uri`` / ``report-to`` payloads into one violation record each. |
| `WR_csp_violation_parser_summary` | `(reports: 'list[dict[str, Any]]', top_n: 'int' = 5, distinct_hosts_threshold: 'int' = 5) -> 'dict[str, Any]'` | Summarise CSP violation reports: count per directive, most blocked hosts, probable reconnaissance. |
| `WR_dashboard_start` | `(host: 'str' = '127.0.0.1', port: 'int' = 0) -> 'str'` |  |
| `WR_dashboard_stop` | `() -> 'None'` |  |
| `WR_db_assert_count` | `(connection_url: 'str', sql: 'str', expected: 'int', params: 'dict[str, Any] | None' = None) -> 'None'` | 斷言 SQL 回傳列數等於 ``expected``。 |
| `WR_db_assert_empty` | `(connection_url: 'str', sql: 'str', params: 'dict[str, Any] | None' = None) -> 'None'` | 斷言查詢沒有任何結果。 |
| `WR_db_assert_exists` | `(connection_url: 'str', sql: 'str', params: 'dict[str, Any] | None' = None) -> 'None'` | 斷言查詢回傳至少一列。 |
| `WR_db_assert_value` | `(connection_url: 'str', sql: 'str', column: 'str', expected: 'Any', row_index: 'int' = 0, params: 'dict[str, Any] | None' = None) -> 'None'` | 斷言指定列、指定欄位的值等於 ``expected``。 |
| `WR_db_query` | `(connection_url: 'str', sql: 'str', params: 'dict[str, Any] | None' = None) -> 'list[dict[str, Any]]'` | 對 ``connection_url`` 執行帶 bound params 的 SQL，回傳結果（list of dict） |
| `WR_delete_all_cookies` | `() -> 'None'` | 刪除當前頁面的所有 cookies |
| `WR_delete_cookie` | `(name: 'str') -> 'None'` | 刪除指定名稱的 cookie |
| `WR_delete_snapshot` | `(name: 'str', snapshot_dir: 'str' = 'snapshots') -> 'bool'` | Remove a snapshot file; returns True if it existed. |
| `WR_diff_ab_records` | `(records_a: 'list[dict[str, Any]]', records_b: 'list[dict[str, Any]]') -> 'dict[str, Any]'` | 比對兩側的 record 序列；回傳每步的差異 |
| `WR_diff_har` | `(left: 'Any', right: 'Any') -> 'dict[str, list[dict[str, Any]]]'` | 比對兩份 HAR；回傳 ``{added, removed, changed}`` |
| `WR_diff_har_files` | `(left_path: 'str', right_path: 'str') -> 'dict[str, list[dict[str, Any]]]'` | 讀取兩個 HAR 檔並比對 / Read two HAR files from disk and diff them. |
| `WR_disable_fetch_interception` | `() -> 'None'` | 停止 Fetch 攔截 / Disable Fetch interception. |
| `WR_dismiss_cookie_consent` | `(timeout_per_selector: 'float' = 0.5) -> 'str | None'` | 點掉常見的 cookie 同意橫幅 |
| `WR_dom_mutations` | `() -> 'list[dict[str, Any]]'` | ``{type, target, added, removed, attribute}`` per DOM mutation collected. |
| `WR_dom_xss_taint_assert_no_taint` | `(findings: 'list[dict[str, Any]] | None' = None, allowed_sinks: 'list[str] | None' = None) -> 'list[dict[str, Any]]'` | Fail when a canary reached a DOM sink; with ``allowed_sinks``, only when it reached another sink. |
| `WR_dom_xss_taint_canaries` | `(test_name: 'str') -> 'list[str]'` | Return two sentinel strings to inject as untrusted input (URL hash, query, postMessage payload). |
| `WR_dom_xss_taint_drain` | `() -> 'list[dict[str, Any]]'` | Return, and clear, the canary writes the page's watched sinks saw since the last drain. |
| `WR_dom_xss_taint_install` | `(canaries: 'list[str]') -> 'int'` | Watch the current page's DOM sinks (innerHTML, document.write, eval...) for the given canaries. |
| `WR_download_verify_assert` | `(path: 'str', checks: 'dict[str, Any]') -> 'bool'` | Fail unless a downloaded file passes every check given. |
| `WR_download_verify_assert_csv_rows` | `(path: 'str', minimum: 'int | None' = None, maximum: 'int | None' = None) -> 'int'` | Fail unless a downloaded CSV has between ``minimum`` and ``maximum`` data rows; returns the count. |
| `WR_download_verify_read` | `(path: 'str', kind: 'str | None' = None, sheet: 'str | int | None' = None) -> 'Any'` | Read a downloaded CSV, JSON, PDF or Excel file as JSON values. |
| `WR_download_verify_sha256` | `(path: 'str') -> 'str'` | The SHA-256 of a downloaded file, as lower-case hex. |
| `WR_download_verify_wait` | `(download_dir: 'str', pattern: 'str' = '.+', timeout: 'float' = 30.0, poll_interval: 'float' = 0.5, stable_for: 'float' = 0.5) -> 'str'` | Wait for a finished download whose file name matches the regular expression ``pattern``. |
| `WR_drag_and_drop` | `(element_name: 'str', target_element_name: 'str') -> 'None'` | 使用 TestObjectRecord 中的元素名稱，拖曳元素到另一個元素上 |
| `WR_drag_and_drop_offset` | `(element_name: 'str', offset_x: 'int', offset_y: 'int') -> 'None'` | 使用 TestObjectRecord 中的元素名稱，拖曳元素到指定偏移位置 |
| `WR_driver_pin_install` | `(pin_file: 'str', browser: 'str', cache_dir: 'str' = '.webrunner/drivers') -> 'str | None'` | Make sure the driver a pin file names for ``browser`` is in the cache, downloading it when missing. |
| `WR_driver_pin_load` | `(pin_file: 'str') -> 'list[dict[str, Any]]'` | Read and validate a driver pin file (``.webrunner/drivers.json``). |
| `WR_driver_pin_platform` | `() -> 'str'` | This machine's platform marker in a pin file: win, mac-arm64, mac-x64, linux or linux-arm64. |
| `WR_dst_boundary_test_assert_fired_around` | `(fires: 'list[str]', expected_utc: 'str', tolerance_seconds: 'float' = 60.0) -> 'bool'` | Fail unless at least one fire is within ``tolerance_seconds`` of the expected time. |
| `WR_dst_boundary_test_assert_no_duplicate_fires` | `(fires: 'list[str]') -> 'int'` | Fail when a scheduler fired twice at the same instant. |
| `WR_dst_boundary_test_classify` | `(tz_name: 'str', wall_clock: 'str') -> 'dict[str, bool]'` | Tell whether a local clock time does not exist (spring-forward gap) or happens twice (fall-back overlap). |
| `WR_dst_boundary_test_find` | `(tz_name: 'str', start_year: 'int', end_year: 'int') -> 'list[dict[str, Any]]'` | List every daylight-saving clock change of a time zone between two years (at most ten years apart). |
| `WR_edge_case_generator_categories` | `() -> 'list[str]'` | List the edge-case categories a suite may use (boundary, unicode, network, ...). |
| `WR_edge_case_generator_render_markdown` | `(suite: 'dict[str, Any]') -> 'str'` | Render an edge-case suite as a markdown table for a PR comment. |
| `WR_edge_case_generator_write_suite` | `(suite: 'dict[str, Any]', output_dir: 'str', filename_prefix: 'str | None' = None) -> 'list[str]'` | Write each case of an edge-case suite as its own action file in ``output_dir``; returns the paths. |
| `WR_element_assert` | `(check_dict: 'dict') -> 'None'` | 檢查當前 WebElement 是否符合指定條件 |
| `WR_element_change_web_element` | `(element_index: 'int') -> 'None'` | 切換當前 WebElement |
| `WR_element_check` | `() -> 'None'` | Tick the current checkbox or radio button; nothing happens if it is already selected. |
| `WR_element_check_current_web_element` | `(check_dict: 'dict') -> 'None'` | 檢查當前 WebElement 是否符合指定條件 |
| `WR_element_clear` | `() -> 'None'` | 清除當前 WebElement 的內容 |
| `WR_element_click` | `() -> 'None'` | 點擊 WebElement |
| `WR_element_get_attribute` | `(name: 'str') -> 'str | None'` | 取得 WebElement 的屬性 |
| `WR_element_get_dom_attribute` | `(name: 'str') -> 'str | None'` | 取得 DOM 屬性 |
| `WR_element_get_property` | `(name: 'str') -> 'None | str | bool | WebElement | dict'` | 取得 WebElement 的屬性 |
| `WR_element_get_select` | `() -> 'Select | None'` | 取得 Select 物件 (用於操作下拉選單) |
| `WR_element_hover` | `() -> 'None'` | Move the mouse over the current element now (``WR_move_to_element`` waits for ``WR_perform``). |
| `WR_element_inner_html` | `() -> 'str | None'` | The HTML inside the current element. |
| `WR_element_inner_text` | `() -> 'str'` | The rendered text of the current element. |
| `WR_element_input` | `(input_value: 'str') -> 'None'` | 輸入文字到 WebElement |
| `WR_element_is_displayed` | `() -> 'bool | None'` | 檢查 WebElement 是否顯示 |
| `WR_element_is_enabled` | `() -> 'bool | None'` | 檢查 WebElement 是否可用 |
| `WR_element_is_selected` | `() -> 'bool | None'` | 檢查 WebElement 是否被選取 |
| `WR_element_screenshot` | `(filename: 'str') -> 'bool | None'` | 對 WebElement 截圖並存檔 |
| `WR_element_select_by_index` | `(index: 'int') -> 'None'` | 以索引選取 <select> 選項 |
| `WR_element_select_by_value` | `(value: 'str') -> 'None'` | 以 value 屬性選取 <select> 選項 |
| `WR_element_select_by_visible_text` | `(text: 'str') -> 'None'` | 以可見文字選取 <select> 選項 |
| `WR_element_submit` | `() -> 'None'` | 提交當前 WebElement |
| `WR_element_uncheck` | `() -> 'None'` | Untick the current checkbox; nothing happens if it is not selected. |
| `WR_element_value_of_css_property` | `(property_name: 'str') -> 'str | None'` | 取得 CSS 屬性值 |
| `WR_email_deliverability_assert` | `(raw: 'str', checks: 'list[str] | None' = None, expected_policy: 'str' = '') -> 'list[str]'` | Fail when a raw delivered e-mail does not pass the named ``checks`` (default spf, dkim, dmarc; also |
| `WR_email_deliverability_audit` | `(raw: 'str', expected_policy: 'str' = '') -> 'dict[str, dict[str, Any]]'` | Check a raw delivered e-mail for SPF, DKIM, DMARC, one-click List-Unsubscribe and a leaked Bcc header. |
| `WR_email_deliverability_parse` | `(raw: 'str') -> 'dict[str, list[str]]'` | Parse the headers of a raw e-mail message into ``{lower-case name: [values]}``. |
| `WR_email_render_assert_subject` | `(email: 'dict[str, Any]', needle: 'str') -> 'bool'` | Fail when the subject of a captured ``email`` (as the load / fetch commands return it) lacks ``needle``. |
| `WR_email_render_fetch` | `(base_url: 'str', provider: 'str' = 'mailhog', timeout: 'float' = 10.0, limit: 'int' = 50) -> 'list[dict[str, Any]]'` | Fetch the captured mail of a MailHog or Mailpit server (``provider``) at ``base_url``. |
| `WR_email_render_load_eml` | `(path: 'str') -> 'list[dict[str, Any]]'` | Read captured mail from an ``.eml`` file, or from every ``.eml`` file of a directory. |
| `WR_email_render_screenshots` | `(email: 'dict[str, Any]', output_dir: 'str', viewports: 'list[dict[str, Any]] | None' = None) -> 'list[dict[str, Any]]'` | Open a captured e-mail's HTML body in the running browser at several sizes and save a screenshot of each. |
| `WR_emulate_device` | `(name: 'str') -> 'None'` | 套用具名裝置（``utils/device_emulation`` 預設） |
| `WR_enable_fetch_interception` | `(patterns: 'list | None' = None, handle_auth: 'bool' = False) -> 'None'` | 啟動 CDP ``Fetch.enable`` 開始攔截請求。 |
| `WR_event_bus_poll` | `(log_path: 'str', offset: 'int' = 0, topics: 'list[str] | None' = None) -> 'dict[str, Any]'` | Read the events of a file event bus from a byte offset on. |
| `WR_event_bus_publish` | `(log_path: 'str', topic: 'str', payload: 'dict[str, Any] | None' = None, sender: 'str | None' = None) -> 'dict[str, Any]'` | Append an event to a file event bus, for other shards or processes to read. |
| `WR_event_bus_wait_for` | `(log_path: 'str', topic: 'str', offset: 'int' = 0, timeout: 'float' = 30.0, match: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | Wait until an event of ``topic`` is on a file event bus and return it. |
| `WR_event_capture_clear` | `() -> 'None'` | Forget what was collected. |
| `WR_event_capture_start` | `(dom_mutations: 'bool' = False) -> 'None'` | 開始收集 console、JavaScript 錯誤與網路回應（可選 DOM 變動） |
| `WR_event_capture_stop` | `() -> 'None'` | Stop collecting; what was collected stays until :meth:`clear_event_capture`. |
| `WR_execute` | `(driver_command: 'str', params: 'dict | None' = None) -> 'dict | None'` | 執行 Selenium WebDriver 的底層命令 |
| `WR_execute_action` | `(action_list: Any) -> dict` | 執行動作清單並回傳紀錄 |
| `WR_execute_async_script` | `(script: 'str', *args)` | 執行非同步 JavaScript |
| `WR_execute_cdp_cmd` | `(cmd: 'str', cmd_args: 'dict | None' = None)` | 在當前 driver 上執行 Chrome DevTools Protocol 命令 (僅 Chromium 系)。 |
| `WR_execute_files` | `(execute_files_list: list) -> list` | 從檔案載入並執行動作 |
| `WR_execute_script` | `(script: 'str', *args)` | 在當前頁面執行 JavaScript，回傳 JS 的回傳值。 |
| `WR_expand_env_in_action` | `(data: 'Any') -> 'Any'` | 遞迴展開 ``${ENV.KEY}`` 占位符 |
| `WR_expand_with_row` | `(data: 'Any', row: 'dict[str, Any]') -> 'Any'` | 遞迴展開 ``${ROW.col}`` 占位符 |
| `WR_explicit_wait` | `(wait_time: 'int', method: 'typing.Callable | None' = None, until_type: 'bool' = True)` | Selenium 顯式等待 |
| `WR_explict_wait` | `(wait_time: 'int', method: 'typing.Callable | None' = None, until_type: 'bool' = True)` | Selenium 顯式等待 |
| `WR_exploratory_ai_plan` | `(observation: 'dict[str, Any]', seed: 'int | None' = None, sample_strings: 'list[str] | None' = None, type_bias: 'float' = 0.3) -> 'dict[str, Any]'` | Pick the next fuzz step (click / type / done) for a page observation, repeatable with ``seed``. |
| `WR_exploratory_ai_replay` | `(observations: 'list[dict[str, Any]]', stop_on_bugs: 'int' = 0) -> 'dict[str, Any]'` | Walk recorded page observations and report the bug signals in them (console and network errors). |
| `WR_export_action_schema` | `(path: 'str') -> 'str'` | 將 Schema 寫到 ``path`` 並回傳寫出的路徑 |
| `WR_export_command_reference` | `(path: 'str', title: 'str | None' = None) -> 'str'` | Write the Markdown reference to ``path`` and return the resolved path. |
| `WR_export_replay_studio` | `(output_path: 'str', records: 'list[dict[str, Any]] | None' = None, screenshot_dir: 'str | None' = None, title: 'str' = 'WebRunner replay') -> 'str'` | Write the studio to ``output_path`` and return the resolved path. |
| `WR_extension_harness_chrome_arguments` | `(extensions: 'list[str]') -> 'list[str]'` | Return the Chrome command-line arguments that load the unpacked extension directories. |
| `WR_extension_harness_info` | `(manifest: 'str | dict[str, Any]') -> 'dict[str, Any]'` | Read a browser extension's manifest (a directory, a ``manifest.json`` path or the parsed object). |
| `WR_extension_harness_playwright_args` | `(extensions: 'list[str]', user_data_dir: 'str', headless: 'bool' = False) -> 'dict[str, Any]'` | Return the ``launch_persistent_context`` arguments that load the unpacked extension directories. |
| `WR_fail` | `(message: 'str' = 'WR_fail') -> 'None'` | 讓這個動作失敗 |
| `WR_failure_auto_tag_assert_tagged` | `(tags: 'list[dict[str, Any]]', expected: 'str') -> 'str'` | Fail unless a tag named ``expected`` is in ``tags``. |
| `WR_failure_auto_tag_heuristic` | `(exception_text: 'str' = '', last_action: 'str' = '', console_errors: 'list[str] | None' = None, network_errors: 'list[dict[str, Any]] | None' = None) -> 'list[dict[str, Any]]'` | Tag a failure (flaky-locator, timeout, network-5xx, js-error, ...) from its error text and logs. |
| `WR_failure_auto_tag_merge` | `(tag_lists: 'list[list[dict[str, Any]]]') -> 'list[dict[str, Any]]'` | Merge several tag lists (``[{"name", "confidence", "reason"}, ...]``), keeping the surest of each name. |
| `WR_failure_bundle_capture` | `(output_path: 'str', test_name: 'str', error_repr: 'str', metadata: 'dict[str, Any] | None' = None, artifacts: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | Write a failure bundle holding the current page's screenshot and HTML; see ``WR_failure_bundle_write``. |
| `WR_failure_bundle_read` | `(zip_path: 'str', include_text: 'bool' = False) -> 'dict[str, Any]'` | Read a failure bundle's manifest and file names. |
| `WR_failure_bundle_write` | `(output_path: 'str', test_name: 'str', error_repr: 'str', metadata: 'dict[str, Any] | None' = None, artifacts: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | Zip the material of a failed test into one failure bundle with a manifest. |
| `WR_failure_cluster_cluster` | `(failures: 'list[dict[str, Any]]', top_n: 'int | None' = None) -> 'Any'` | Group failures that share an error signature, largest group first. |
| `WR_failure_cluster_dbscan_assert_root_causes_at_most` | `(records: 'list[dict[str, Any]]', max_clusters: 'int', eps: 'float' = 0.3, min_samples: 'int' = 2) -> 'int'` | Fail when the failures form more than ``max_clusters`` groups of two or more; returns the group count. |
| `WR_failure_cluster_dbscan_cluster` | `(records: 'list[dict[str, Any]]', eps: 'float' = 0.3, min_samples: 'int' = 2) -> 'Any'` | Group failures whose messages are near-identical, largest group first. |
| `WR_failure_cluster_normalise` | `(message: 'str') -> 'str'` | Strip timestamps, addresses, paths, numbers and quoted text from an error message. |
| `WR_failure_narrator_build_prompt` | `(bundle: 'dict[str, Any]') -> 'str'` | Render the "why did this test fail" prompt to send to a language model. |
| `WR_failure_narrator_load_bundle` | `(path: 'str') -> 'dict[str, Any]'` | Read a failure-bundle directory (``meta.json``, ``dom.html``, ``console.log``, ...) as failure facts. |
| `WR_failure_narrator_parse_response` | `(raw: 'str') -> 'dict[str, Any]'` | Parse a model's failure-summary reply into summary / likely_cause / next_step / confidence / markdown. |
| `WR_failure_triage_extract_signals` | `(bundle_path: 'str', steps: 'list[Any] | None' = None, max_steps: 'int' = 12) -> 'dict[str, Any]'` | Read a failure-bundle zip and return what a root-cause analysis needs: error, last steps, log tails. |
| `WR_failure_triage_render_markdown` | `(report: 'dict[str, Any]', heading_level: 'int' = 2) -> 'str'` | Render a root-cause report as markdown for a PR comment. |
| `WR_faker` | `(method: 'str', *args: 'Any', **kwargs: 'Any') -> 'Any'` | 任意 faker provider 的通用呼叫器 |
| `WR_faker_address` | `() -> 'str'` |  |
| `WR_faker_credit_card` | `() -> 'str'` |  |
| `WR_faker_email` | `() -> 'str'` |  |
| `WR_faker_first_name` | `() -> 'str'` |  |
| `WR_faker_last_name` | `() -> 'str'` |  |
| `WR_faker_name` | `() -> 'str'` |  |
| `WR_faker_password` | `(length: 'int' = 12) -> 'str'` |  |
| `WR_faker_phone` | `() -> 'str'` |  |
| `WR_faker_seed` | `(seed: 'int') -> 'None'` | Set a deterministic seed for reproducible runs. |
| `WR_faker_text` | `(max_chars: 'int | None' = None) -> 'str'` |  |
| `WR_faker_url` | `() -> 'str'` |  |
| `WR_faker_user_agent` | `() -> 'str'` |  |
| `WR_faker_uuid` | `() -> 'str'` |  |
| `WR_fetch_continue_request` | `(request_id: 'str', url: 'str | None' = None, method: 'str | None' = None, post_data=None, headers=None) -> 'None'` | 放行 (或改寫後放行) 一個被 ``Fetch.requestPaused`` 暫停的請求。 |
| `WR_fetch_fail_request` | `(request_id: 'str', error_reason: 'str' = 'Aborted') -> 'None'` | 以指定錯誤理由讓被攔截的請求失敗 (用於阻擋 / 模擬網路錯誤)。 |
| `WR_fetch_fulfill_request` | `(request_id: 'str', response_code: 'int', body=None, response_headers=None, response_phrase: 'str | None' = None) -> 'None'` | 以指定 response 回應一個被攔截的請求 (不再送出到原伺服器)。 |
| `WR_file_system_access_assert` | `(writes: 'list[dict[str, Any]]', file_name: 'str | None' = None, contains: 'str | None' = None, no_writes: 'bool' = False) -> 'dict[str, Any]'` | Fail unless one write matches ``file_name`` and/or has ``contains`` in its data; with ``no_writes`` fail |
| `WR_file_system_access_harvest` | `() -> 'list[dict[str, Any]]'` | The writes the page made to a mocked save file: ``[{"file_name", "sequence", "data"}]``. |
| `WR_file_system_access_install` | `(open_files: 'list[dict[str, Any]] | None' = None, save_suggested_name: 'str | None' = None) -> 'bool'` | Replace the page's file pickers with mocks: ``showOpenFilePicker`` returns ``open_files`` |
| `WR_filter_paths` | `(paths: 'Iterable[str]', include: 'Sequence[str] | None' = None, exclude: 'Sequence[str] | None' = None) -> 'list[str]'` | 篩選 action 檔路徑清單 |
| `WR_find_element` | `(element_name: 'str') -> 'WebElement | None'` | 使用已儲存的 TestObjectRecord 尋找單一元素 |
| `WR_find_element_by` | `(selector: 'str', by: 'str' = 'css selector') -> 'Any'` | Find by a raw selector (no saved ``TestObject``) and make it the current element. |
| `WR_find_elements` | `(element_name: 'str') -> 'list[WebElement] | None'` | 使用已儲存的 TestObjectRecord 尋找多個元素 |
| `WR_find_elements_by` | `(selector: 'str', by: 'str' = 'css selector') -> 'list[Any]'` | Find every match of a raw selector; they become the current element list. |
| `WR_find_recorded_element` | `(element_name: 'str') -> 'WebElement | None'` | 使用已儲存的 TestObjectRecord 尋找單一元素 |
| `WR_find_recorded_elements` | `(element_name: 'str') -> 'list[WebElement] | None'` | 使用已儲存的 TestObjectRecord 尋找多個元素 |
| `WR_find_with_healing` | `(name: 'str')` | 依序嘗試 primary + fallback locator，回傳第一個命中的 WebElement |
| `WR_flag_matrix_assert_all_passed` | `(results: 'list[dict[str, Any]]') -> 'dict[str, Any]'` | Fail when any flag combination in ``results`` did not pass, naming the flag values behind the failures. |
| `WR_flag_matrix_build` | `(flags: 'dict[str, list[Any]]', forbid: 'list[Any] | None' = None, require: 'list[Any] | None' = None, pinned: 'list[dict[str, Any]] | None' = None, sample_size: 'int | None' = None, seed: 'int | None' = None) -> 'dict[str, Any]'` | Build the feature-flag combinations to test from ``{flag: [variants]}``. |
| `WR_flag_matrix_summarise` | `(results: 'list[dict[str, Any]]') -> 'dict[str, Any]'` | Roll up the outcome of each flag combination and name the flag values that explain the failures. |
| `WR_flake_detector_assert_not_quarantined` | `(registry_path: 'str', test_id: 'str') -> 'None'` | Fail when ``test_id`` is in the quarantine registry file. |
| `WR_flake_detector_flaky_paths` | `(ledger_path: 'str', half_life_days: 'float' = 7.0, min_runs: 'int' = 3, threshold: 'float' = 0.25) -> 'list[str]'` | List the tests of a run ledger that are flaky, worst first. |
| `WR_flake_detector_quarantine_flaky` | `(ledger_path: 'str', registry_path: 'str', half_life_days: 'float' = 7.0, min_runs: 'int' = 3, threshold: 'float' = 0.25) -> 'list[str]'` | Add the newly flaky tests of a run ledger to the quarantine registry file; returns the added ids. |
| `WR_flake_detector_quarantine_list` | `(registry_path: 'str') -> 'Any'` | List the entries of a quarantine registry file, highest flake score first. |
| `WR_flake_detector_release_if_stable` | `(ledger_path: 'str', registry_path: 'str', half_life_days: 'float' = 7.0, release_threshold: 'float' = 0.05, min_runs_since: 'int' = 5) -> 'list[str]'` | Remove from the quarantine registry file the tests that turned stable; returns the released ids. |
| `WR_flake_detector_scores` | `(ledger_path: 'str | None' = None, runs: 'list[dict[str, Any]] | None' = None, half_life_days: 'float' = 7.0, min_runs: 'int' = 3, threshold: 'float' = 0.25) -> 'Any'` | Score every test of a run ledger for flakiness, recent failures weighing more. |
| `WR_flakiness_graveyard_assert_none_due` | `(path: 'str', days: 'int' = 30, today: 'str | None' = None) -> 'None'` | Fail when a quarantined test of the graveyard registry file is due for burial. |
| `WR_flakiness_graveyard_bury` | `(path: 'str', test_name: 'str') -> 'Any'` | Mark a quarantined test of the graveyard registry file as buried; returns its entry. |
| `WR_flakiness_graveyard_due_for_burial` | `(path: 'str', days: 'int' = 30, today: 'str | None' = None) -> 'Any'` | List the quarantined tests of the graveyard registry file that have not flaked for ``days`` days. |
| `WR_flakiness_graveyard_list` | `(path: 'str') -> 'Any'` | List the entries of the graveyard registry file. |
| `WR_flakiness_graveyard_register_flake` | `(path: 'str', test_name: 'str', owner: 'str' = '', ticket_url: 'str' = '', today: 'str | None' = None) -> 'Any'` | Record a flake of ``test_name`` in the graveyard registry file (created when missing). |
| `WR_flakiness_graveyard_revive` | `(path: 'str', test_name: 'str') -> 'Any'` | Mark a quarantined test of the graveyard registry file as revived; returns its entry. |
| `WR_flakiness_stats` | `(ledger_path: 'str', min_runs: 'int' = 3) -> 'dict[str, dict[str, int]]'` | 從 ledger 算出每個檔案的 ``{runs, passes, fails, flaky}`` 統計 |
| `WR_flaky_paths` | `(ledger_path: 'str', min_runs: 'int' = 3, min_fail_rate: 'float' = 0.0) -> 'list[str]'` | 回傳被判為 flaky 的檔案 |
| `WR_font_loading_strategy_assert` | `(css: 'str | None' = None, strategy: 'str | None' = None, fallback_family: 'str | None' = None) -> 'list[dict[str, Any]]'` | Fail when ``@font-face`` blocks have no ``font-display``; ``css`` omitted means the current page's HTML. |
| `WR_font_loading_strategy_page` | `() -> 'list[dict[str, Any]]'` | List the ``@font-face`` blocks inlined in the current page's HTML (linked stylesheets are not read). |
| `WR_font_loading_strategy_parse` | `(css: 'str') -> 'list[dict[str, Any]]'` | List the ``@font-face`` blocks of a stylesheet's text, each with its ``display`` and ``size_adjust``. |
| `WR_for_each` | `(items: 'Any', do: 'list', var: 'str' = 'item', index_var: 'str | None' = None) -> 'int'` | 對清單的每個項目執行一次 ``do`` |
| `WR_forced_colors_mode_apply` | `(profile: 'str | None' = None, color_scheme: 'str' = 'light', reduced_motion: 'str' = 'no-preference', forced_colors: 'str' = 'none', contrast: 'str' = 'no-preference') -> 'dict[str, Any]'` | Make the current page (Chromium) render under a dark / reduced-motion / forced-colors / contrast mode. |
| `WR_forced_colors_mode_assert_no_invisible` | `(snapshots_by_mode: 'dict[str, dict[str, dict[str, str]]]', baseline_mode: 'str' = 'baseline') -> 'int'` | Fail when an element's text colour equals its background in a mode but not in the baseline mode. |
| `WR_forced_colors_mode_audit` | `(snapshots_by_mode: 'dict[str, dict[str, dict[str, str]]]', baseline_mode: 'str' = 'baseline') -> 'dict[str, Any]'` | Compare the computed styles of elements across media modes and list what changed or became invisible. |
| `WR_forced_colors_mode_profiles` | `() -> 'list[dict[str, Any]]'` | List the built-in media profiles (baseline, dark, reduced-motion, high-contrast, dark-high-contrast). |
| `WR_form_autofill_assert_all_matched` | `(fields: 'list[dict[str, Any]]', fixture: 'dict[str, Any]') -> 'int'` | Fail when a form field gets no value from the fixture; returns the number of fields matched. |
| `WR_form_autofill_match` | `(fields: 'list[dict[str, Any]]', fixture: 'dict[str, Any]') -> 'list[dict[str, Any]]'` | Match form fields to the values of a fixture by their id, name, placeholder, label or type. |
| `WR_form_autofill_plan` | `(fields: 'list[dict[str, Any]]', fixture: 'dict[str, Any]', submit_locator: 'dict[str, str] | None' = None) -> 'list[list[Any]]'` | Build the action list that fills the matched fields (arguments as ``WR_form_autofill_match``). |
| `WR_forward` | `() -> 'None'` | 前進到下一頁 / Navigate forward |
| `WR_fullscreen_window` | `() -> 'None'` | 全螢幕顯示當前視窗 |
| `WR_generate_all_reports` | `(base_name: 'str', allure_dir: 'str | None' = None, write_manifest: 'bool' = True) -> 'dict[str, Any]'` | 依預設慣例產出所有報告；回傳 ``{format: [paths produced]}`` 與 manifest 路徑 |
| `WR_generate_allure` | `() -> 'list[dict[str, Any]]'` | 將目前的 record list 包成單一 Allure test case |
| `WR_generate_allure_report` | `(output_dir: 'str' = 'allure-results') -> 'list[str]'` | 把 test cases 寫成 ``<uuid>-result.json`` |
| `WR_generate_html` | `() -> str` | 產生完整 HTML 報告字串 |
| `WR_generate_html_report` | `(html_name: str = 'default_name')` | 產生並輸出 HTML 報告檔案 |
| `WR_generate_interactive_html_report` | `(html_name: 'str' = 'default_name', screenshot_dir: 'str | None' = None, har_path: 'str | None' = None, a11y_results: 'dict[str, Any] | str | None' = None) -> 'str'` | 產生並寫出互動式 HTML 報告 |
| `WR_generate_json` | `()` | 產生測試結果的 JSON 結構 |
| `WR_generate_json_report` | `(json_file_name: str = 'default_name')` | 產生並輸出 JSON 測試報告 |
| `WR_generate_junit_xml` | `() -> str` | 產生 JUnit 格式 XML 字串 |
| `WR_generate_junit_xml_report` | `(junit_file_name: str = 'default_name') -> None` | 產生並輸出 JUnit XML 測試報告 |
| `WR_generate_pom_from_html` | `(html: 'str', class_name: 'str') -> 'str'` | Convenience: parse HTML and render the POM class in one call. |
| `WR_generate_pom_from_url` | `(url: 'str', class_name: 'str', timeout: 'int' = 30) -> 'str'` | 從 URL 下載 HTML 並產生 POM 類別 |
| `WR_generate_xml` | `()` | 產生 XML 結構字串 |
| `WR_generate_xml_report` | `(xml_file_name: str = 'default_name')` | 產生並輸出 XML 測試報告 |
| `WR_geo_locale_apply` | `(latitude: 'float | None' = None, longitude: 'float | None' = None, timezone: 'str | None' = None, locale: 'str | None' = None, accuracy_meters: 'float' = 50.0) -> 'list[str]'` | Override the location, timezone and locale of the running browser (Chromium); returns the CDP methods. |
| `WR_geo_locale_payloads` | `(latitude: 'float | None' = None, longitude: 'float | None' = None, timezone: 'str | None' = None, locale: 'str | None' = None, accuracy_meters: 'float' = 50.0) -> 'dict[str, Any]'` | Build the CDP commands and the Playwright context arguments of a location / timezone / locale override. |
| `WR_get_cookie` | `(name: 'str') -> 'dict | None'` | 取得指定名稱的 cookie |
| `WR_get_cookies` | `() -> 'list[dict] | None'` | 取得當前頁面的所有 cookies |
| `WR_get_current_url` | `() -> 'str | None'` | 取得當前頁面的 URL |
| `WR_get_current_window_handle` | `() -> 'str | None'` | 取得當前 driver 操作的視窗 handle |
| `WR_get_env` | `(key: 'str', default: 'str | None' = None) -> 'str | None'` | Return ``os.environ[key]`` with an optional default. |
| `WR_get_log` | `(log_type: 'str')` | 取得 WebDriver 日誌（``log_type`` 為必填） |
| `WR_get_page_source` | `() -> 'str | None'` | 取得當前頁面 HTML 原始碼 |
| `WR_get_screenshot_as_base64` | `() -> 'str | None'` | 取得當前頁面截圖 (Base64 字串) |
| `WR_get_screenshot_as_png` | `() -> 'bytes | None'` | 取得當前頁面截圖 (PNG 格式) |
| `WR_get_title` | `() -> 'str | None'` | 取得當前頁面的 <title> |
| `WR_get_var` | `(name: 'str', default: 'Any' = None) -> 'Any'` | 讀取變數 |
| `WR_get_webdriver_manager` | `(webdriver_name: str, options: list[str] | None = None, **kwargs) -> None` | 建立新的 WebDriver 實例 |
| `WR_get_window_handles` | `() -> 'list[str] | None'` | 取得所有開啟中的視窗 / tab handle |
| `WR_get_window_position` | `(window_handle='current') -> 'dict | None'` | 取得視窗位置 |
| `WR_get_window_rect` | `() -> 'dict | None'` | 取得視窗矩形資訊 (位置與大小) |
| `WR_gh_emit_failures` | `(stream: 'IO[str] | None' = None, file: 'str | None' = None) -> 'list[str]'` | 對 ``test_record_instance`` 內每個失敗紀錄輸出一行 annotation |
| `WR_gh_emit_from_junit_xml` | `(junit_path: 'str', stream: 'IO[str] | None' = None) -> 'list[str]'` | 讀取 JUnit XML 並對其中每個 ``<failure>`` 輸出一行 annotation |
| `WR_gh_format_error` | `(message: 'str', file: 'str | None' = None, line: 'int | None' = None, col: 'int | None' = None, title: 'str | None' = None) -> 'str'` | 產出 ``::error file=...::message`` 行 |
| `WR_git_bisect_flake_bisect` | `(commit_order: 'list[str]', test_id: 'str', ledger_path: 'str | None' = None, entries: 'list[dict[str, Any]] | None' = None) -> 'Any'` | Find the commit where ``test_id`` went from passing to failing, from recorded runs only. |
| `WR_git_bisect_flake_markdown` | `(commit_order: 'list[str]', test_id: 'str', ledger_path: 'str | None' = None, entries: 'list[dict[str, Any]] | None' = None) -> 'str'` | Render the recorded-runs bisect of ``test_id`` as markdown. |
| `WR_grant_permissions` | `(permissions: 'list[str]', origin: 'str | None' = None) -> 'None'` | 授予瀏覽器權限（Chromium，CDP） |
| `WR_graphql_assert_field` | `(payload: 'dict[str, Any]', path: 'str', expected: 'Any') -> 'Any'` | Fail when the value at ``path`` of a GraphQL response's ``data`` is not ``expected``. |
| `WR_graphql_execute` | `(endpoint: 'str', query: 'str', variables: 'dict[str, Any] | None' = None, operation_name: 'str | None' = None, headers: 'dict[str, str] | None' = None, timeout: 'float' = 10.0) -> 'dict[str, Any]'` | Send a GraphQL query or mutation to ``endpoint`` and return the response envelope. |
| `WR_graphql_extract_field` | `(payload: 'dict[str, Any]', path: 'str') -> 'Any'` | Read a value from a GraphQL response's ``data`` with a path such as ``user.posts[0].title``. |
| `WR_graphql_introspect_types` | `(endpoint: 'str', headers: 'dict[str, str] | None' = None, timeout: 'float' = 10.0) -> 'list[str]'` | Run the introspection query on ``endpoint`` and return the names of the schema's types. |
| `WR_graphql_n_plus_1_assert` | `(rows: 'list[dict[str, Any]]', threshold: 'int' = 5) -> 'list[dict[str, Any]]'` | Fail when the query rows contain an error-level N+1 pattern; returns the findings otherwise. |
| `WR_graphql_n_plus_1_detect` | `(rows: 'list[dict[str, Any]]', threshold: 'int' = 5, include_cartesian: 'bool' = True) -> 'list[dict[str, Any]]'` | Find N+1 query patterns in the backend queries of one GraphQL request. |
| `WR_graphql_n_plus_1_report` | `(rows: 'list[dict[str, Any]]', threshold: 'int' = 5) -> 'str'` | Render the N+1 findings of the query rows as a Markdown section. |
| `WR_grpc_streaming_assert_frames` | `(record: 'dict[str, Any]', min_count: 'int' = 0, max_count: 'int | None' = None, max_bytes: 'int | None' = None, direction: 'str' = 'in') -> 'int'` | Fail when the number of frames in ``direction`` is outside ``min_count``..``max_count`` or a frame is |
| `WR_grpc_streaming_assert_half_close` | `(record: 'dict[str, Any]') -> 'bool'` | Fail when a bidi stream's client did not half-close before the server's last frame. |
| `WR_grpc_streaming_assert_order` | `(record: 'dict[str, Any]', key: 'str', expected: 'list[Any]', direction: 'str' = 'in') -> 'bool'` | Fail when the ``key`` of the frame bodies, in arrival order, is not the ``expected`` list. |
| `WR_grpc_streaming_assert_parse` | `(record: 'dict[str, Any]') -> 'dict[str, Any]'` | Normalise a captured gRPC stream record. |
| `WR_grpc_streaming_assert_status` | `(record: 'dict[str, Any]', expected: 'str' = 'OK') -> 'bool'` | Fail when the stream did not end with the ``expected`` status (for example OK or CANCELLED). |
| `WR_grpc_tester_assert_call` | `(call: 'dict[str, Any]', expected_status: 'str' = 'OK') -> 'dict[str, Any]'` | Fail when the observed gRPC ``call`` did not end with ``expected_status``. |
| `WR_grpc_tester_assert_called` | `(method: 'str', minimum: 'int' = 1) -> 'int'` | Fail when fewer than ``minimum`` recorded calls went to ``method``; returns how many did. |
| `WR_grpc_tester_decode_message` | `(framed_base64: 'str') -> 'list[dict[str, Any]]'` | Split a base64 gRPC-Web body into its frames. |
| `WR_grpc_tester_encode_message` | `(payload_base64: 'str') -> 'str'` | Frame a base64 message as a gRPC-Web body (flag byte and length prefix); returns base64. |
| `WR_grpc_tester_record` | `(call: 'dict[str, Any]') -> 'dict[str, Any]'` | Add one observed gRPC call to the recorder that ``WR_grpc_tester_assert_called`` reads. |
| `WR_grpc_tester_reset` | `() -> 'int'` | Forget the recorded gRPC calls; returns how many were dropped. |
| `WR_hallucination_probe_assert_rate` | `(probes: 'list[dict[str, Any]]', answers: 'dict[str, str]', max_rate: 'float' = 0.0) -> 'float'` | Fail when more than ``max_rate`` (0 to 1) of the graded probe answers are wrong; returns the rate. |
| `WR_hallucination_probe_evaluate` | `(probes: 'list[dict[str, Any]]', answers: 'dict[str, str]') -> 'dict[str, Any]'` | Grade the answers a model gave to ground-truth probes and return the hallucination rate. |
| `WR_har_replay_calls` | `() -> 'list[list[str]]'` | List the ``[method, path]`` pairs the HAR replay server was asked for, in order. |
| `WR_har_replay_load` | `(har_path: 'str') -> 'list[dict[str, Any]]'` | Read a HAR file and list the responses it can replay (method, path, status, headers, body). |
| `WR_har_replay_start` | `(har_path: 'str', port: 'int' = 0, not_found_status: 'int' = 404) -> 'dict[str, Any]'` | Start a local server on 127.0.0.1 that answers requests with the responses recorded in a HAR file. |
| `WR_har_replay_stop` | `() -> 'list[list[str]]'` | Stop the HAR replay server; returns the ``[method, path]`` pairs it was asked for. |
| `WR_har_to_openapi_assert_coverage` | `(min_paths: 'int', har: 'dict[str, Any] | None' = None, har_path: 'str | None' = None) -> 'int'` | Fail when the HAR yields fewer than ``min_paths`` API paths; returns the number of paths. |
| `WR_har_to_openapi_convert` | `(har: 'dict[str, Any] | None' = None, har_path: 'str | None' = None) -> 'dict[str, Any]'` | Draft an OpenAPI 3.1 document from a HAR (the object itself, or the path of a ``.har`` file). |
| `WR_header_tampering_apply` | `(headers: 'dict[str, str]', url: 'str', rules: 'list[dict[str, Any]]') -> 'dict[str, str]'` | Return request headers with tampering rules applied, to send with an HTTP command. |
| `WR_hsts_preload_audit_assert_preload_ready` | `(header: 'str', scheme: 'str | None' = None) -> 'dict[str, Any]'` | Fail unless an HSTS header qualifies for the browser preload list. |
| `WR_hsts_preload_audit_parse` | `(header: 'str') -> 'dict[str, Any]'` | Parse a ``Strict-Transport-Security`` value into ``max_age``, ``include_subdomains``, ``preload``. |
| `WR_http_assert_json_contains` | `(key: 'str', expected: 'Any') -> 'None'` | 斷言上一次 JSON 回應於 ``key`` 的值等於 ``expected`` |
| `WR_http_assert_status` | `(expected: 'int') -> 'None'` | 斷言上一次回應的 HTTP 狀態碼 |
| `WR_http_delete` | `(url: 'str', **kwargs: 'Any') -> 'dict[str, Any]'` |  |
| `WR_http_get` | `(url: 'str', **kwargs: 'Any') -> 'dict[str, Any]'` |  |
| `WR_http_patch` | `(url: 'str', **kwargs: 'Any') -> 'dict[str, Any]'` |  |
| `WR_http_post` | `(url: 'str', **kwargs: 'Any') -> 'dict[str, Any]'` |  |
| `WR_http_put` | `(url: 'str', **kwargs: 'Any') -> 'dict[str, Any]'` |  |
| `WR_http_request` | `(method: 'str', url: 'str', timeout: 'int' = 30, headers: 'dict[str, str] | None' = None, params: 'dict[str, Any] | None' = None, json_body: 'Any' = None, data: 'Any' = None, **request_kwargs: 'Any') -> 'dict[str, Any]'` | 通用 HTTP 請求；其他 ``http_*`` 命令皆呼叫此函式 |
| `WR_hydration_check_assert` | `(server_html: 'str | None' = None, client_html: 'str | None' = None, console_messages: 'list[str] | None' = None) -> 'dict[str, Any]'` | Fail (``HydrationCheckError``) on a hydration mismatch; arguments as ``WR_hydration_check_audit``. |
| `WR_hydration_check_audit` | `(server_html: 'str | None' = None, client_html: 'str | None' = None, console_messages: 'list[str] | None' = None) -> 'dict[str, Any]'` | Look for SSR hydration mismatches in a server/client HTML pair and in console lines. |
| `WR_hydration_check_page` | `(server_html: 'str', console_messages: 'list[str] | None' = None) -> 'dict[str, Any]'` | Compare the server's HTML with the current page's HTML (see ``WR_hydration_check_audit``). |
| `WR_hydration_streaming_assert` | `(payload: 'dict[str, Any] | None' = None, boundary: 'str | None' = None, max_arrival_ms: 'float | None' = None, max_interactive_ms: 'float | None' = None, expected_order: 'list[str] | None' = None) -> 'dict[str, Any]'` | Fail when a streaming boundary never arrived; ``payload`` omitted means the current page's log. |
| `WR_hydration_streaming_install` | `() -> 'bool'` | Start recording streaming-SSR boundary arrivals in the current page (run right after navigating). |
| `WR_hydration_streaming_page` | `() -> 'dict[str, Any]'` | Read the boundary timings recorded in the current page since ``WR_hydration_streaming_install``. |
| `WR_hydration_streaming_parse` | `(payload: 'dict[str, Any]') -> 'dict[str, Any]'` | Turn a harvested boundary log ``{"boundaries": {id: {placeholder, arrived, interactive}}}`` into timings. |
| `WR_idempotency_check_assert` | `(first: 'dict[str, Any]', second: 'dict[str, Any]', allow_status_change_to: 'list[int] | None' = None, ignore_body_keys: 'list[str] | None' = None) -> 'dict[str, Any]'` | Fail when the repeated request's response differs from the first one; returns the report. |
| `WR_idempotency_check_compare` | `(first: 'dict[str, Any]', second: 'dict[str, Any]', allow_status_change_to: 'list[int] | None' = None, ignore_body_keys: 'list[str] | None' = None) -> 'dict[str, Any]'` | Compare the responses of the same request sent twice. |
| `WR_idempotency_check_key` | `(parts: 'list[Any]') -> 'str'` | Build a stable ``Idempotency-Key`` value (SHA-256 hex) from ``parts`` such as user id and amount. |
| `WR_if` | `(condition: 'Any', then: 'list | None' = None, otherwise: 'list | None' = None) -> 'list'` | 條件成立時執行 ``then``，否則執行 ``otherwise`` |
| `WR_iframe_back_to_default` | `() -> 'None'` | Return Selenium focus to the top-level frame. |
| `WR_iframe_switch_chain` | `(selectors: 'Sequence[str]') -> 'None'` | 依序切換進入多層 iframe（每層用 CSS selector 指定） |
| `WR_impact_analysis_affected` | `(directory: 'str', locators: 'list[str] | None' = None, urls: 'list[str] | None' = None, templates: 'list[str] | None' = None, commands: 'list[str] | None' = None) -> 'list[str]'` | The action files under a directory that use any of the changed names. |
| `WR_impact_analysis_index` | `(directory: 'str', glob: 'str' = '**/*.json', cache_path: 'str | None' = None) -> 'dict[str, Any]'` | Index the action files under a directory by the locators, URLs, templates and commands they use. |
| `WR_impact_analysis_select` | `(files: 'list[str]', directory: 'str', affected_by: 'list[str]', cache_path: 'str | None' = None) -> 'list[str]'` | Keep, in their order, the ``files`` that the ``affected_by`` names reach. |
| `WR_implicitly_wait` | `(time_to_wait: 'int') -> 'None'` | 設定 Selenium 的隱式等待時間 |
| `WR_inbox_render_outlook_assert` | `(html: 'str', clients: 'list[str] | None' = None) -> 'list[dict[str, Any]]'` | Fail when the HTML e-mail body has an error-level finding; returns the findings otherwise. |
| `WR_inbox_render_outlook_audit` | `(html: 'str', clients: 'list[str] | None' = None) -> 'list[dict[str, Any]]'` | Audit an HTML e-mail body for things mail clients render badly. |
| `WR_inbox_render_outlook_audit_page` | `(clients: 'list[str] | None' = None) -> 'list[dict[str, Any]]'` | Audit the current page's HTML as an e-mail body (for a page that previews the e-mail). |
| `WR_indexed_db_drop` | `(db_name: 'str') -> 'None'` | Drop an IndexedDB database by name. Best-effort (Promise resolution skipped). |
| `WR_indexed_db_explorer_assert` | `(snapshot: 'dict[str, Any]', store: 'str | None' = None, minimum: 'int' = 0, maximum: 'int | None' = None) -> 'dict[str, Any]'` | Fail unless the snapshot's database exists and, with ``store``, that store is there and holds between |
| `WR_indexed_db_explorer_assert_record` | `(snapshot: 'dict[str, Any]', store: 'str', key: 'Any' = None, index: 'str | None' = None, record: 'dict[str, Any] | None' = None) -> 'Any'` | Fail unless ``store`` has the key ``key``, the index ``index`` and a record with every field of |
| `WR_indexed_db_explorer_diff` | `(before: 'dict[str, Any]', after: 'dict[str, Any]') -> 'dict[str, Any]'` | Compare two IndexedDB snapshots: stores added, stores removed and the record counts that changed. |
| `WR_indexed_db_explorer_harvest` | `(db_name: 'str') -> 'dict[str, Any]'` | Snapshot the IndexedDB database ``db_name`` of the current page: its stores, keys, indexes and records. |
| `WR_inp_tracker_assert` | `(payload: 'list[dict[str, Any]] | None' = None, max_ms: 'float' = 200.0, forbid_poor: 'bool' = False) -> 'dict[str, Any]'` | Fail when the INP passes ``max_ms``; ``payload`` omitted means the current page's log. |
| `WR_inp_tracker_install` | `() -> 'bool'` | Start recording interaction timings (Interaction to Next Paint) in the current page. |
| `WR_inp_tracker_page` | `() -> 'dict[str, Any]'` | Summarise the interactions recorded in the current page since ``WR_inp_tracker_install``. |
| `WR_inp_tracker_report` | `(payload: 'list[dict[str, Any]]') -> 'dict[str, Any]'` | Summarise a harvested interaction log (objects with ``name``, ``interactionId``, ``duration_ms``). |
| `WR_input_to_element` | `(input_value: 'str') -> 'None'` | 輸入文字到 WebElement |
| `WR_jira_create_failure_issues` | `(base_url: 'str', email: 'str', api_token: 'str', project_key: 'str', issue_type: 'str' = 'Bug', build_url: 'str | None' = None) -> 'list[dict[str, Any]]'` | 對 ``test_record_instance`` 內每個失敗紀錄建立一個 issue |
| `WR_jira_create_issue` | `(base_url: 'str', email: 'str', api_token: 'str', project_key: 'str', summary: 'str', description: 'str' = '', issue_type: 'str' = 'Bug', extra_fields: 'dict[str, Any] | None' = None, timeout: 'int' = 30) -> 'dict[str, Any]'` | 建立 JIRA issue |
| `WR_k8s_runner_render_manifests` | `(config: 'dict[str, Any]') -> 'list[dict[str, Any]]'` | Render one Kubernetes ``batch/v1`` Job per shard, each running ``--shard i/N`` of an action directory. |
| `WR_k8s_runner_render_yaml` | `(config: 'dict[str, Any]') -> 'str'` | The shard Jobs of ``WR_k8s_runner_render_manifests`` as one multi-document YAML text. |
| `WR_lcp_image_audit_assert` | `(candidate: 'Any', html: 'str | None' = None, link_header_urls: 'list[str] | None' = None, checks: 'list[str] | None' = None) -> 'dict[str, Any]'` | Fail when the LCP image is not preloaded, is lazy-loaded or lacks ``fetchpriority="high"``. |
| `WR_lcp_image_audit_check` | `(candidate: 'Any', html: 'str | None' = None, link_header_urls: 'list[str] | None' = None) -> 'dict[str, Any]'` | Check how the Largest Contentful Paint image is loaded; ``html`` omitted means the current page. |
| `WR_ledger_clear` | `(ledger_path: 'str') -> 'None'` | Delete the ledger file (no-op if missing). |
| `WR_ledger_failed_files` | `(ledger_path: 'str') -> 'list[str]'` | Return paths whose most recent run was a failure. |
| `WR_ledger_passed_files` | `(ledger_path: 'str') -> 'list[str]'` | Return paths whose most recent run was a pass. |
| `WR_ledger_record_run` | `(ledger_path: 'str', file_path: 'str', passed: 'bool') -> 'None'` | Append one run record to the ledger. |
| `WR_left_click` | `(element_name: 'str | None' = None) -> 'None'` | 使用 TestObject 名稱找到元素並左鍵點擊 |
| `WR_left_click_and_hold` | `(element_name: 'str | None' = None) -> 'None'` | 使用 TestObject 名稱找到元素並左鍵按住 |
| `WR_left_double_click` | `(element_name: 'str | None' = None) -> 'None'` | 使用 TestObject 名稱找到元素並左鍵雙擊 |
| `WR_license_scanner_assert_allowed` | `(allow: 'list[str]', text: 'str | None' = None, path: 'str | None' = None, deny: 'list[str] | None' = None) -> 'dict[str, Any]'` | Fail when bundle text (``text`` or the file at ``path``) names a license outside ``allow`` or in ``deny``. |
| `WR_license_scanner_scan_file` | `(path: 'str') -> 'dict[str, Any]'` | Find SPDX identifiers and well-known license texts in the JS / CSS bundle file at ``path``. |
| `WR_license_scanner_scan_text` | `(text: 'str') -> 'dict[str, Any]'` | Find SPDX identifiers and well-known license texts (MIT, Apache, GPL, AGPL...) in bundle text. |
| `WR_lighthouse_assert_scores` | `(result: 'dict[str, Any]', thresholds: 'dict[str, float]') -> 'None'` | 斷言所有指定分數皆達門檻 |
| `WR_lighthouse_regression_assert` | `(head: 'Any', baseline: 'Any' = None, threshold_points: 'float' = 5, metric_budgets: 'dict[str, float] | None' = None) -> 'dict[str, Any]'` | Fail when a Lighthouse score dropped against a baseline or a metric passes its budget. |
| `WR_lighthouse_regression_diff` | `(baseline: 'Any', head: 'Any') -> 'dict[str, Any]'` | Compare two Lighthouse results (each as in ``WR_lighthouse_regression_parse``). |
| `WR_lighthouse_regression_parse` | `(report: 'Any') -> 'dict[str, Any]'` | Extract the category scores (0-100) and Core Web Vitals metrics of a Lighthouse JSON result. |
| `WR_lighthouse_run` | `(url: 'str', output_path: 'str | None' = None, lighthouse_path: 'str' = 'lighthouse', chrome_flags: 'list[str] | None' = None, extra_args: 'list[str] | None' = None, timeout: 'int' = 180) -> 'dict[str, Any]'` | 執行 Lighthouse 並回傳 ``{scores, report_path, raw}`` |
| `WR_lint_action` | `(data: 'Any') -> 'list[dict[str, Any]]'` | Walk an action structure and return the findings list. |
| `WR_lint_action_file` | `(path: 'str') -> 'list[dict[str, Any]]'` | Read ``path`` (UTF-8 JSON) and lint the contents. |
| `WR_lint_severity_counts` | `(findings: 'list[dict[str, Any]]') -> 'dict[str, int]'` | Aggregate ``{warning: N, info: M}`` for reporting. |
| `WR_list_commands` | `() -> 'list[str]'` | Just the command names (handy for shell completion). |
| `WR_list_devices` | `() -> 'list[str]'` | The device preset names :meth:`emulate_device` accepts. |
| `WR_list_new_downloads` | `(directory: 'str', before: 'list[str]') -> 'list[str]'` | 回傳 ``directory`` 內目前存在但不在 ``before`` 清單中的檔案 |
| `WR_list_vars` | `() -> 'list[str]'` | 列出變數名稱 |
| `WR_live_dashboard_summary` | `(ledger_path: 'str | None' = None, quarantine_path: 'str | None' = None, locator_findings_path: 'str | None' = None) -> 'dict[str, Any]'` | The counts the live dashboard's overview shows, read from the files given. |
| `WR_live_dashboard_trend` | `(ledger_path: 'str') -> 'dict[str, Any]'` | Per-day pass and fail counts of a run ledger, as the live dashboard charts them: ``{daily, totals}``. |
| `WR_llm_generate_actions` | `(request: 'str', context: 'str | None' = None) -> 'list[Any]'` | 把自然語言敘述轉成 WR_* action JSON 草稿 |
| `WR_llm_has_callable` | `() -> 'bool'` |  |
| `WR_llm_self_heal_locator` | `(name: 'str', html_provider: 'Callable[[], str]') -> 'dict[str, str]'` | 當既有 fallback locator 都失敗時，呼叫 LLM 提供新的選擇器 |
| `WR_llm_set_callable` | `(callable_obj: 'Callable[[str], str] | None') -> 'None'` | 登錄一個 ``Callable[[str], str]`` 用於後續所有 prompt。 |
| `WR_llm_suggest_locator` | `(html: 'str', description: 'str') -> 'dict[str, str]'` | 讓 LLM 從 HTML 推斷一個合理的 locator |
| `WR_llm_token_cost_tracker_assert_under_budget` | `(records: 'list[dict[str, Any]]', max_usd: 'float', rate_card: 'dict[str, dict[str, float]] | None' = None) -> 'dict[str, Any]'` | Fail when the recorded model calls cost more than ``max_usd``; returns the total. |
| `WR_llm_token_cost_tracker_tally` | `(records: 'list[dict[str, Any]]', rate_card: 'dict[str, dict[str, float]] | None' = None) -> 'dict[str, Any]'` | Add up tokens and dollars of recorded model calls, in total and per test. |
| `WR_llm_token_cost_tracker_top_spenders` | `(records: 'list[dict[str, Any]]', top_n: 'int' = 5, rate_card: 'dict[str, dict[str, float]] | None' = None) -> 'list[dict[str, Any]]'` | List the ``top_n`` tests that spent the most on model calls. |
| `WR_load_cookies` | `(file_path: 'str') -> 'int'` | 從 JSON 檔讀回 cookies 並逐筆套用 (恢復先前的登入態)。 |
| `WR_load_dataset_csv` | `(path: 'str', encoding: 'str' = 'utf-8') -> 'list[dict[str, str]]'` | 讀取 CSV 為 list of dict（首列為欄位名） |
| `WR_load_dataset_json` | `(path: 'str', encoding: 'str' = 'utf-8') -> 'list[dict[str, Any]]'` | 讀取 JSON 為 list of dict |
| `WR_load_env` | `(env_name: 'str | None' = None, env_dir: 'str' = '.', override: 'bool' = False) -> 'str'` | 載入指定環境的 ``.env`` 檔 |
| `WR_load_locators` | `(path: 'str') -> 'list'` | 載入共用的定位器檔 |
| `WR_local_storage_all` | `() -> 'dict'` |  |
| `WR_local_storage_clear` | `() -> 'None'` |  |
| `WR_local_storage_get` | `(key: 'str') -> 'str | None'` |  |
| `WR_local_storage_remove` | `(key: 'str') -> 'None'` |  |
| `WR_local_storage_set` | `(key: 'str', value: 'str') -> 'None'` |  |
| `WR_locator_hardener_build_prompt` | `(strategy: 'str', value: 'str', test_id: 'str' = 'action', dom_excerpt: 'str' = '', failure_history: 'int' = 0) -> 'str'` | Render the prompt that asks a language model for sturdier replacements of a locator. |
| `WR_locator_hardener_parse_suggestions` | `(raw: 'str') -> 'list[dict[str, Any]]'` | Parse a model's locator suggestions, dropping malformed ones and those that are fragile again. |
| `WR_locator_hardener_score` | `(strategy: 'str', value: 'str', test_id: 'str' = 'action', failure_history: 'int' = 0) -> 'dict[str, Any]'` | Score how fragile a locator is (0 to 1, with reasons); 0.5 and above is worth replacing. |
| `WR_locator_health_assert` | `(path: 'str', pattern: 'str' = '**/*.json', threshold: 'int' = 60, max_weak: 'int' = 0) -> 'dict[str, Any]'` | Fail when more than ``max_weak`` locators of a file or directory score under ``threshold``. |
| `WR_locator_health_markdown` | `(path: 'str', pattern: 'str' = '**/*.json', threshold: 'int' = 60, weakest_limit: 'int' = 10) -> 'str'` | The locator health report of a file or directory as Markdown, ready for a pull-request comment. |
| `WR_locator_health_scan` | `(path: 'str', pattern: 'str' = '**/*.json', threshold: 'int' = 60, weakest_limit: 'int' = 10) -> 'dict[str, Any]'` | Score every locator in an action file, or in the action files under a directory. |
| `WR_locator_health_suggest` | `(path: 'str', pattern: 'str' = '**/*.json', only_below: 'int | None' = None) -> 'list[dict[str, Any]]'` | Suggest stabler locators for an action file or directory (an XPath on ``@id`` becomes ``ID``...). |
| `WR_locust_build_user_class` | `(actions: 'list[dict[str, Any]]', wait_min: 'float' = 1.0, wait_max: 'float' = 3.0) -> 'type'` | 依 actions 動態建立一個 ``HttpUser`` 子類別 |
| `WR_locust_run` | `(host: 'str', actions: 'list[dict[str, Any]]', num_users: 'int' = 10, spawn_rate: 'float' = 2.0, run_seconds: 'float' = 60.0, wait_min: 'float' = 1.0, wait_max: 'float' = 3.0) -> 'dict[str, Any]'` | 無頭模式跑 Locust 並回傳統計 |
| `WR_long_animation_frame_assert` | `(payload: 'list[dict[str, Any]] | None' = None, max_frame_ms: 'float | None' = None, max_total_blocking_ms: 'float | None' = None) -> 'dict[str, Any]'` | Fail when a long animation frame or the total blocking time passes a limit. |
| `WR_long_animation_frame_install` | `() -> 'bool'` | Start recording long animation frames (Chromium's LoAF API) in the current page. |
| `WR_long_animation_frame_page` | `(top_n: 'int' = 5) -> 'dict[str, Any]'` | Summarise the long frames recorded in the current page since ``WR_long_animation_frame_install``. |
| `WR_long_animation_frame_report` | `(payload: 'list[dict[str, Any]]', top_n: 'int' = 5) -> 'dict[str, Any]'` | Summarise a harvested long-animation-frame log (objects with ``duration_ms``, ``scripts`` ...). |
| `WR_match_snapshot` | `(name: 'str', value: 'str', snapshot_dir: 'str' = 'snapshots') -> 'str'` | 比對快照；首次執行會建立基準。 |
| `WR_maximize_window` | `() -> 'None'` | 最大化當前視窗 |
| `WR_md_authoring_parse` | `(text: 'str') -> 'list[list[Any]]'` | Turn Markdown bullets (``- open <url>``, ``- click <selector>``, ...) into an action list. |
| `WR_md_authoring_patterns` | `() -> 'list[str]'` | List the bullet sentences the Markdown authoring understands. |
| `WR_md_authoring_transpile_file` | `(md_path: 'str', output_path: 'str | None' = None) -> 'list[list[Any]]'` | Turn a Markdown file into an action list, written as an action file when ``output_path`` is given. |
| `WR_memory_leak_sample` | `() -> 'int'` | Return the current page's used JavaScript heap in bytes (Chromium only). |
| `WR_memory_leak_trend` | `(samples: 'list[int]', max_bytes_per_iter: 'int | None' = None) -> 'dict[str, Any]'` | Fit a line through heap sizes sampled after each round of a repeated action. |
| `WR_memory_pressure_emulate_apply` | `(profile: 'Any') -> 'list[dict[str, Any]]'` | Put the current Chromium browser under a low-resource profile (see ``WR_memory_pressure_emulate_payloads``). |
| `WR_memory_pressure_emulate_payloads` | `(profile: 'Any') -> 'list[dict[str, Any]]'` | List the CDP commands that put a browser under a low-resource profile. |
| `WR_memory_pressure_emulate_profiles` | `() -> 'list[dict[str, Any]]'` | List the built-in low-resource profiles (``low_end_phone``, ``critical_pressure``, ``single_core``). |
| `WR_memory_pressure_emulate_restore` | `() -> 'bool'` | Take the current Chromium browser back to normal CPU, core count and memory pressure. |
| `WR_migrate_action` | `(data: 'Any') -> 'tuple[Any, list[dict[str, Any]]]'` | 將 action 結構內所有舊命令名改寫為新名 |
| `WR_migrate_action_file` | `(path: 'str', dry_run: 'bool' = True) -> 'dict[str, Any]'` | Read ``path``, rewrite legacy names, optionally write back when |
| `WR_migrate_directory` | `(directory: 'str', dry_run: 'bool' = True) -> 'list[dict[str, Any]]'` | 遍歷目錄內所有 ``.json`` 檔做遷移 |
| `WR_minimize_window` | `() -> 'None'` | 最小化當前視窗 |
| `WR_mixed_content_audit_assert_clean` | `(har: 'dict[str, Any] | str | None' = None, messages: 'list[str] | None' = None, page_url: 'str | None' = None, allow_passive: 'bool' = False) -> 'dict[str, Any]'` | Fail when a HAR and / or console messages show mixed content. |
| `WR_mixed_content_audit_console` | `(messages: 'list[str]', page_url: 'str' = '') -> 'dict[str, Any]'` | Find mixed-content warnings in a list of browser console messages. |
| `WR_mixed_content_audit_har` | `(har: 'dict[str, Any] | str', page_url: 'str | None' = None) -> 'dict[str, Any]'` | Find ``http://`` requests made by an ``https://`` page in a HAR (object or JSON text). |
| `WR_mock_services_captured` | `() -> 'dict[str, Any]'` | Return what the mock services saw so far: ``oauth_tokens`` issued and ``smtp_messages`` captured. |
| `WR_mock_services_start_oauth` | `(port: 'int' = 0) -> 'dict[str, Any]'` | Start a mock OAuth server on 127.0.0.1 whose ``POST /token`` issues a fake bearer token. |
| `WR_mock_services_start_smtp` | `(port: 'int' = 0) -> 'dict[str, Any]'` | Start a capture-only SMTP server on 127.0.0.1 for the application under test to send mail to. |
| `WR_mock_services_stop` | `() -> 'dict[str, Any]'` | Stop the mock OAuth and SMTP servers; returns what they saw. |
| `WR_move_by_offset` | `(offset_x: 'int', offset_y: 'int') -> 'None'` | 滑鼠移動指定偏移量 |
| `WR_move_to_element` | `(element_name: 'str')` | 使用 TestObjectRecord 中的元素名稱，將滑鼠移動到指定元素 |
| `WR_move_to_element_with_offset` | `(element_name: 'str', offset_x: 'int', offset_y: 'int') -> 'None'` | 使用 TestObjectRecord 中的元素名稱，將滑鼠移動到指定元素並加上偏移量 |
| `WR_mq_assert_idempotent` | `(messages: 'list[dict[str, Any]]', key: 'str') -> 'bool'` | Fail when more than one consumed queue message carries the idempotency ``key``. |
| `WR_mq_assert_no_message` | `(messages: 'list[dict[str, Any]]', topic: 'str | None' = None, body_contains: 'dict[str, Any] | None' = None) -> 'bool'` | Fail when a consumed queue message on ``topic`` (any topic when ``null``) has the given body fields. |
| `WR_mq_assert_ordered` | `(messages: 'list[dict[str, Any]]', key: 'str', expected_order: 'list[str]') -> 'bool'` | Fail when the body ``type`` of the messages with ``key`` did not arrive in ``expected_order``. |
| `WR_mq_assert_published` | `(messages: 'list[dict[str, Any]]', body_contains: 'dict[str, Any] | None' = None, key_matches: 'str | None' = None, header_equals: 'dict[str, str] | None' = None) -> 'dict[str, Any]'` | Fail when none of the consumed queue ``messages`` (``{"topic", "body", "key", "headers"}`` each) has the |
| `WR_multi_tab_close` | `(alias: 'str') -> 'list[str]'` | Close the tab named ``alias``; returns the names still known. |
| `WR_multi_tab_open` | `(alias: 'str') -> 'dict[str, Any]'` | Open a blank tab, switch to it and name it ``alias`` (follow with ``WR_to_url`` to load a page). |
| `WR_multi_tab_register` | `(alias: 'str') -> 'dict[str, Any]'` | Give the current browser tab a name, so later commands can switch back to it. |
| `WR_multi_tab_reset` | `() -> 'list[str]'` | Forget every tab name (tabs stay open); returns the names that were known. |
| `WR_multi_tab_switch` | `(alias: 'str') -> 'dict[str, Any]'` | Switch the browser to the tab named ``alias``. |
| `WR_multimodal_qa_assert_passes` | `(raw: 'str', min_confidence: 'float' = 0.6) -> 'dict[str, Any]'` | Fail unless a vision model's reply is a ``pass`` with at least ``min_confidence``. |
| `WR_multimodal_qa_build_request` | `(image_path: 'str', question: 'str', rubric: 'list[str] | None' = None) -> 'dict[str, str]'` | Build what to send a vision model about a screenshot: the prompt and the image as base64. |
| `WR_multimodal_qa_parse_response` | `(raw: 'str') -> 'dict[str, Any]'` | Parse a vision model's reply into verdict (pass / fail / uncertain), confidence, rationale, issues. |
| `WR_mutation_testing_apply` | `(actions: 'list[Any]', mutation: 'dict[str, Any]') -> 'Any'` | Return a copy of an action list with one mutation (as ``WR_mutation_testing_generate`` returns) applied. |
| `WR_mutation_testing_assert_min_score` | `(killed: 'int', total: 'int', minimum: 'float' = 0.8) -> 'float'` | Fail when ``killed / total`` mutations is below ``minimum``; returns the mutation score. |
| `WR_mutation_testing_generate` | `(actions: 'list[Any]', types: 'list[str] | None' = None, seed: 'int | None' = None, max_per_type: 'int | None' = None) -> 'Any'` | List the mutations that can sabotage an action list (locator swap, timeout shrink, removal, ...). |
| `WR_network_responses` | `() -> 'list[dict[str, Any]]'` | ``{url, status, method, ok}`` per response collected. |
| `WR_new_driver` | `(webdriver_name: str, options: list[str] | None = None, **kwargs) -> None` | 建立新的 WebDriver 實例 |
| `WR_new_window` | `(type_hint: 'str' = 'tab') -> 'None'` | 開啟新的 tab 或 window，並自動切換到該視窗 |
| `WR_note` | `(text: 'str' = '') -> 'str'` | 不做任何事的註記 |
| `WR_notifications_audit_assert` | `(payload: 'dict[str, Any]', require_gesture: 'bool' = True, min_page_age_ms: 'float | None' = None, no_spam_after_deny: 'bool' = True, unique_tags: 'bool' = False) -> 'dict[str, Any]'` | Check a notifications log for policy violations: a permission prompt without a user gesture, a prompt |
| `WR_notifications_audit_assert_shown` | `(payload: 'dict[str, Any]', title_contains: 'str | None' = None, body_contains: 'str | None' = None, tag: 'str | None' = None) -> 'dict[str, Any]'` | Fail unless the log has a notification matching the given title text, body text and/or tag; returns it. |
| `WR_notifications_audit_harvest` | `() -> 'dict[str, Any]'` | The notifications log recorded so far: ``{"permission_requests": [...], "notifications": [...]}``. |
| `WR_notifications_audit_install` | `() -> 'bool'` | Start recording the current page's ``Notification.requestPermission`` calls and shown notifications. |
| `WR_notify_run_summary` | `(webhook_url: 'str', header: 'str' = 'WebRunner Run Summary') -> 'int'` | 一鍵：取摘要 → Slack 格式 → 送出 |
| `WR_notify_slack` | `(webhook_url: 'str', summary: 'dict[str, Any] | None' = None, header: 'str' = 'WebRunner Run Summary') -> 'int'` | 將摘要包成 Slack incoming-webhook 格式並送出 |
| `WR_notify_webhook` | `(url: 'str', payload: 'dict[str, Any]', timeout: 'int' = 10, headers: 'dict[str, str] | None' = None) -> 'int'` | POST 任意 JSON payload 到 webhook，回傳 HTTP 狀態碼 |
| `WR_number_currency_locale_assert_currency` | `(rendered: 'str', locale: 'str') -> 'bool'` | Fail when a rendered amount lacks the locale's currency symbol or has it on the wrong side. |
| `WR_number_currency_locale_assert_date` | `(rendered: 'str', date_format: 'str' = 'iso') -> 'bool'` | Fail when a rendered date is not written in the expected style. |
| `WR_number_currency_locale_assert_number` | `(rendered: 'str', locale: 'str') -> 'bool'` | Fail when a rendered number uses the wrong decimal separator or digit grouping for the locale. |
| `WR_number_currency_locale_check` | `(rendered: 'str', locale: 'str', currency: 'bool' = False) -> 'dict[str, Any]'` | Report whether a rendered number (and, with ``currency``, its symbol) follows a locale's format. |
| `WR_oauth_bearer_header` | `(access_token: 'str') -> 'dict[str, str]'` | Convenience: build the Authorization header for HTTP commands. |
| `WR_oauth_clear_cache` | `() -> 'None'` |  |
| `WR_oauth_client_credentials` | `(token_url: 'str', client_id: 'str', client_secret: 'str', scope: 'str | None' = None, cache_key: 'str | None' = None, timeout: 'int' = 30) -> 'dict[str, Any]'` | OAuth2 client-credentials 流程 |
| `WR_oauth_get_cached` | `(cache_key: 'str') -> 'dict[str, Any] | None'` |  |
| `WR_oauth_password_grant` | `(token_url: 'str', client_id: 'str', client_secret: 'str', username: 'str', password: 'str', scope: 'str | None' = None, cache_key: 'str | None' = None, timeout: 'int' = 30) -> 'dict[str, Any]'` | OAuth2 password grant（多數 IdP 已棄用，僅 legacy 系統用） |
| `WR_oauth_pkce_replay_assert_all_rejected` | `(responses: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Fail when any recorded replay answer carries an ``access_token`` (or when no answer is given). |
| `WR_oauth_pkce_replay_challenge` | `(verifier: 'str') -> 'str'` | Return the S256 ``code_challenge`` of a PKCE ``code_verifier``. |
| `WR_oauth_pkce_replay_classify` | `(responses: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Classify recorded token-endpoint answers to replayed OAuth values as rejected / accepted / ambiguous. |
| `WR_oauth_pkce_replay_verifier` | `(length: 'int' = 64) -> 'dict[str, str]'` | Make a fresh PKCE ``code_verifier`` (43 to 128 characters) and its S256 ``code_challenge``. |
| `WR_oauth_refresh_token` | `(token_url: 'str', client_id: 'str', client_secret: 'str', refresh_token: 'str', cache_key: 'str | None' = None, timeout: 'int' = 30) -> 'dict[str, Any]'` |  |
| `WR_ocr_assert_any` | `(image_path: 'str', candidates: 'list[str]', lang: 'str' = 'eng') -> 'dict[str, Any]'` | Fail unless the text recognised in an image file contains at least one of ``candidates``. |
| `WR_ocr_assert_contains` | `(image_path: 'str', needle: 'str', case_sensitive: 'bool' = False, lang: 'str' = 'eng') -> 'dict[str, Any]'` | Fail unless the text recognised in an image file contains ``needle``. |
| `WR_ocr_assert_extract_text` | `(image_path: 'str', lang: 'str' = 'eng') -> 'str'` | Read the text in an image file with Tesseract OCR (needs ``pytesseract`` and the tesseract binary). |
| `WR_ocr_assert_fuzzy` | `(image_path: 'str', expected: 'str', min_ratio: 'float' = 0.8, lang: 'str' = 'eng') -> 'dict[str, Any]'` | Fail unless the text recognised in an image file is at least ``min_ratio`` (0-1) similar to ``expected``. |
| `WR_ocr_assert_page_contains` | `(needle: 'str', case_sensitive: 'bool' = False, lang: 'str' = 'eng') -> 'dict[str, Any]'` | Fail unless a screenshot of the current page, read with OCR, contains ``needle`` (canvas text included). |
| `WR_open_redirect_detector_assert_safe` | `(responses: 'list[dict[str, Any]]', legitimate_host: 'str') -> 'dict[str, Any]'` | Fail when any recorded answer redirects to another host or to a ``javascript:`` / ``data:`` URL. |
| `WR_open_redirect_detector_classify` | `(responses: 'list[dict[str, Any]]', legitimate_host: 'str') -> 'dict[str, Any]'` | Decide from recorded answers whether a redirect parameter sends users off ``legitimate_host``. |
| `WR_open_redirect_detector_payloads` | `(attacker_host: 'str' = 'evil.example') -> 'list[dict[str, Any]]'` | List the values to try in a ``?redirect=`` / ``?next=`` parameter when testing for an open redirect. |
| `WR_openapi_drift_assert` | `(observations: 'list[dict[str, Any]]', spec: 'dict[str, Any] | None' = None, spec_path: 'str | None' = None, max_zombies: 'int | None' = None) -> 'dict[str, Any]'` | Fail when the traffic used an endpoint or method the OpenAPI document does not declare, and, when |
| `WR_openapi_drift_diff` | `(observations: 'list[dict[str, Any]]', spec: 'dict[str, Any] | None' = None, spec_path: 'str | None' = None) -> 'dict[str, Any]'` | Compare observed API traffic with an OpenAPI document (the object, or the path of its JSON file). |
| `WR_openapi_to_e2e_generate` | `(spec: 'dict[str, Any] | None' = None, spec_path: 'str | None' = None, include_negative: 'bool' = True, method_filter: 'list[str] | None' = None, path_prefix_filter: 'str | None' = None) -> 'dict[str, Any]'` | Generate ``WR_http_*`` action lists from an OpenAPI 3 / Swagger 2 document. |
| `WR_openapi_to_e2e_write` | `(output_dir: 'str', spec: 'dict[str, Any] | None' = None, spec_path: 'str | None' = None, include_negative: 'bool' = True, method_filter: 'list[str] | None' = None, path_prefix_filter: 'str | None' = None) -> 'list[str]'` | Generate the tests of an OpenAPI document and write one action file per test into ``output_dir``. |
| `WR_order_factory` | `(default_currency: 'str' = 'USD') -> 'Factory'` |  |
| `WR_otel_bridge_clear` | `() -> 'bool'` | Stop sending the trace headers ``WR_otel_bridge_inject`` added. |
| `WR_otel_bridge_inject` | `(traceparent: 'str | None' = None, tracestate: 'str | None' = None) -> 'dict[str, Any]'` | Send a ``traceparent`` header with every request of the current Chromium browser. |
| `WR_otel_bridge_new_context` | `(sampled: 'bool' = True) -> 'dict[str, Any]'` | Make a fresh W3C trace context. |
| `WR_otel_bridge_parse` | `(traceparent: 'str') -> 'dict[str, Any]'` | Split a ``traceparent`` header value into its fields (as ``WR_otel_bridge_new_context`` returns). |
| `WR_otel_bridge_trace_link` | `(traceparent: 'str', jaeger_base: 'str | None' = None, tempo_base: 'str | None' = None) -> 'str | None'` | Build the Jaeger or Grafana Tempo URL of a trace; ``None`` when neither base URL is given. |
| `WR_otp_interceptor_extract` | `(text: 'str', pattern: 'str | None' = None) -> 'str | None'` | Pull a one-time code out of ``text``: the first 4-8 digit number, or the first match (first group) of |
| `WR_otp_interceptor_messages` | `(base_url: 'str', provider: 'str' = 'mailhog', recipient: 'str | None' = None, limit: 'int' = 25) -> 'list[dict[str, Any]]'` | List the newest messages of a test inbox at ``base_url``, optionally only those to ``recipient``. |
| `WR_otp_interceptor_wait` | `(base_url: 'str', recipient: 'str', provider: 'str' = 'mailhog', pattern: 'str | None' = None, timeout: 'float' = 30.0, subject_contains: 'str | None' = None, lookback_seconds: 'float' = 0.0) -> 'str'` | Wait for a one-time code sent to ``recipient`` to reach the test inbox at ``base_url`` and return it. |
| `WR_pagination_audit_assert` | `(pages: 'list[dict[str, Any]]', key: 'str | None' = 'id', expected_total: 'int | None' = None, sorted_by_key: 'bool' = False, reverse: 'bool' = False) -> 'dict[str, Any]'` | Fail when the recorded pages repeat an item or a cursor, when the number of distinct items is not |
| `WR_pagination_audit_walk` | `(pages: 'list[dict[str, Any]]', key: 'str | None' = 'id', max_pages: 'int' = 1000) -> 'dict[str, Any]'` | Audit recorded API pages for duplicates, empty pages and a repeated cursor. |
| `WR_parse_shard_spec` | `(spec: 'str') -> 'tuple[int, int]'` | 把 ``"1/4"`` 解析為 ``(1, 4)`` |
| `WR_partition` | `(paths: 'Sequence[str]', index: 'int', total: 'int') -> 'list[str]'` | 回傳該 shard 應該執行的檔案路徑（依檔名 SHA-1 對 ``total`` 取模） |
| `WR_partition_with_spec` | `(paths: 'Sequence[str]', spec: 'str') -> 'list[str]'` | Convenience: parse the spec then partition. |
| `WR_pause` | `(seconds: 'int') -> 'None'` | 暫停指定秒數 (注意：可能導致 Selenium 拋出例外) |
| `WR_payment_request_assert_check` | `(payload: 'dict[str, Any]', method: 'str | None' = None, currency: 'str | None' = None, completed: 'str | None' = None, shipping_required: 'bool' = False) -> 'dict[str, Any]'` | Check a harvested payment log: a request offered payment ``method``, every total is in ``currency``, |
| `WR_payment_request_assert_harvest` | `() -> 'dict[str, Any]'` | Read and empty the PaymentRequest recorder: ``{"constructed": [...], "completed": [{status}]}``. |
| `WR_payment_request_assert_install` | `(canned: 'dict[str, Any] | None' = None) -> 'bool'` | Replace the page's ``PaymentRequest`` with a recorder whose ``show()`` answers at once with ``canned`` |
| `WR_perf_assert_within` | `(metrics: 'dict[str, Any]', thresholds: 'dict[str, float]') -> 'None'` | 斷言所有指標都不超過上限 |
| `WR_perf_collect` | `(observe_ms: 'int' = 1000) -> 'dict[str, Any]'` | 透過 ``execute_async_script`` 抓取效能指標 |
| `WR_perf_drift_assert_no_regression` | `(metrics: 'dict[str, list[float]]', baseline_window: 'int' = 20, recent_window: 'int' = 5, tolerance: 'float' = 0.1, higher_is_better: 'list[str] | None' = None) -> 'None'` | Fail when the recent P95 of a metric is worse than its baseline by ``tolerance`` or more. |
| `WR_perf_drift_detect` | `(metrics: 'dict[str, list[float]]', baseline_window: 'int' = 20, recent_window: 'int' = 5, tolerance: 'float' = 0.1, higher_is_better: 'list[str] | None' = None) -> 'dict[str, Any]'` | Compare the recent P95 of each metric with the P95 of the runs before them. |
| `WR_perf_drift_percentile` | `(values: 'list[float]', pct: 'float' = 95.0) -> 'float'` | The ``pct``-th percentile of a list of measurements. |
| `WR_perform` | `() -> 'None'` | 執行累積的 ActionChains 動作 |
| `WR_persona_runner_assert_all_passed` | `(results: 'list[dict[str, Any]]') -> 'dict[str, Any]'` | Fail when any persona / file pair in ``results`` did not pass. |
| `WR_persona_runner_summarise` | `(results: 'list[dict[str, Any]]') -> 'dict[str, Any]'` | Roll up a persona-by-file run: which personas fail alone, which files fail for everyone. |
| `WR_pii_in_screenshot_assert_clean` | `(paths: 'list[str] | None' = None, text: 'str | None' = None) -> 'dict[str, Any]'` | Fail when image files, or text already read from an image, show PII. |
| `WR_pii_in_screenshot_scan_images` | `(paths: 'list[str]') -> 'dict[str, Any]'` | OCR the image files at ``paths`` and scan their text for PII (needs pytesseract and Pillow). |
| `WR_pii_in_screenshot_scan_page` | `() -> 'dict[str, Any]'` | Screenshot the current page, OCR it and scan the text for PII (needs pytesseract and Pillow). |
| `WR_pii_in_screenshot_scan_text` | `(text: 'str', image_label: 'str' = '') -> 'dict[str, Any]'` | Scan text already read from an image (OCR output) for e-mail, phone, card, SSN, ID, IBAN and IPv4. |
| `WR_pii_scanner_assert_no_pii` | `(text: 'str | None' = None, categories: 'list[str] | None' = None, allow_categories: 'list[str] | None' = None) -> 'bool'` | Fail when text holds personal data of a category not in ``allow_categories``. |
| `WR_pii_scanner_redact_text` | `(text: 'str', replacement: 'str' = '[REDACTED]', categories: 'list[str] | None' = None) -> 'str'` | Return ``text`` with every piece of personal data replaced by ``replacement``. |
| `WR_pii_scanner_scan_page` | `(categories: 'list[str] | None' = None) -> 'dict[str, Any]'` | Find personal data in the HTML of the current page. |
| `WR_pii_scanner_scan_text` | `(text: 'str', categories: 'list[str] | None' = None) -> 'dict[str, Any]'` | Find personal data in text: ``email``, ``phone_e164``, ``credit_card``, ``ssn_us``, ``taiwan_id``, ``ipv4``. |
| `WR_pip_assert_check` | `(payload: 'list[dict[str, Any]]', mode: 'str' = 'video', entered: 'bool' = True, exited_cleanly: 'bool' = False, min_size: 'list[int] | None' = None) -> 'dict[str, Any]'` | Check harvested Picture-in-Picture events for ``mode`` (``video`` / ``document``): it was ``entered``, |
| `WR_pip_assert_harvest` | `() -> 'list[dict[str, Any]]'` | Read and empty the Picture-in-Picture recorder: ``[{"kind", "mode", "ts", "width", "height"}]``. |
| `WR_pip_assert_install` | `() -> 'bool'` | Start recording the current page's Picture-in-Picture enter and exit calls (video and document). |
| `WR_pipeline_assert_all_passed` | `(results: 'list[dict[str, Any]]') -> 'int'` | Fail when any pipeline stage in ``results`` has a status other than ``passed``. |
| `WR_pipeline_load` | `(source: 'Any') -> 'dict[str, Any]'` | Read and validate a multi-stage pipeline definition. |
| `WR_pom_codegen_render` | `(html: 'str', class_name: 'str' = 'WebRunnerPage') -> 'dict[str, Any]'` | Generate a Python page-object class from the ``data-testid`` / ``id`` / ``name`` elements of some HTML. |
| `WR_pom_codegen_render_page` | `(class_name: 'str' = 'WebRunnerPage') -> 'dict[str, Any]'` | Generate a Python page-object class from the current page (result as ``WR_pom_codegen_render``). |
| `WR_popover_assert_check` | `(snapshot: 'list[dict[str, Any]]', open_id: 'str | None' = None, closed_id: 'str | None' = None, only_one_modal: 'bool' = True, none_open: 'bool' = False) -> 'list[dict[str, Any]]'` | Check a popover / dialog snapshot: the element ``open_id`` is open, ``closed_id`` is not, at most one |
| `WR_popover_assert_harvest` | `() -> 'list[dict[str, Any]]'` | Describe every ``<dialog>`` and ``[popover]`` element of the current page: kind, id, open, modal, invoker. |
| `WR_popover_assert_invoker` | `(snapshot: 'list[dict[str, Any]]', popover_id: 'str', invoker_id: 'str') -> 'bool'` | Fail unless the popover ``popover_id`` names ``invoker_id`` as its invoker (its ``data-invoker-id``). |
| `WR_pr_comment_build_markdown` | `(summary: 'dict[str, Any]', run_url: 'str | None' = None) -> 'str'` | Render the Markdown of a test-summary comment for a pull request. |
| `WR_pr_comment_post` | `(repo: 'str', pr_number: 'int', body: 'str') -> 'dict[str, Any]'` | Create the WebRunner summary comment on a GitHub pull request, or update it when it already exists. |
| `WR_pr_risk_score_aggregate` | `(per_file: 'list[dict[str, Any]]') -> 'Any'` | Sum per-file signal objects into the one signals object ``WR_pr_risk_score_score`` takes. |
| `WR_pr_risk_score_assert_below` | `(signals: 'dict[str, Any]', block_at: 'float' = 75.0, weights: 'dict[str, float] | None' = None) -> 'Any'` | Fail when the risk score of a pull request's signals reaches ``block_at``. |
| `WR_pr_risk_score_markdown` | `(signals: 'dict[str, Any]', weights: 'dict[str, float] | None' = None) -> 'str'` | Render the risk score of a pull request's signals as markdown. |
| `WR_pr_risk_score_score` | `(signals: 'dict[str, Any]', weights: 'dict[str, float] | None' = None) -> 'Any'` | Turn the signals of a pull request into a 0-100 risk score with a level and reasons. |
| `WR_pr_title_generator_assert_conventional` | `(title: 'str') -> 'str'` | Fail unless ``title`` follows Conventional Commits (``type(scope): summary``). |
| `WR_pr_title_generator_suggest` | `(files: 'list[str]', commits: 'list[str]', breaking: 'bool' = False) -> 'str'` | Suggest a Conventional Commits PR title from the changed file paths and the commit subjects. |
| `WR_pre_merge_gate_dsl_assert_passes` | `(rules: 'list[dict[str, Any]]', facts: 'dict[str, Any]') -> 'Any'` | Fail when a pull request's facts break a pre-merge rule. |
| `WR_pre_merge_gate_dsl_evaluate` | `(rules: 'list[dict[str, Any]]', facts: 'dict[str, Any]') -> 'Any'` | Check a pull request's facts against pre-merge rules; returns ``passed`` and the ``failures``. |
| `WR_press_key` | `(keycode_on_key_class, element_name: 'str | None' = None) -> 'None'` | 使用 TestObject 名稱找到元素並按下鍵盤按鍵 |
| `WR_press_keys` | `(keys: 'str | Sequence[str]') -> 'None'` | 對目前聚焦的元素按下並放開按鍵 |
| `WR_print_page` | `(file_path: 'str', print_options=None) -> 'bool'` | 將當前頁面列印為 PDF 並存檔 (Selenium 4 內建 ``print_page``)。 |
| `WR_process_supervisor_list_orphans` | `(names: 'list[str] | None' = None) -> 'list[dict[str, Any]]'` | List the running WebDriver processes (chromedriver, geckodriver, msedgedriver, IEDriverServer). |
| `WR_product_factory` | `() -> 'Factory'` |  |
| `WR_prompt_drift_monitor_assert_no_drift` | `(baseline_path: 'str', current: 'list[dict[str, Any]]', similarity_threshold: 'float' = 0.85) -> 'int'` | Fail when any current answer drifted from the baseline file; returns how many were compared. |
| `WR_prompt_drift_monitor_check` | `(baseline_path: 'str', current: 'list[dict[str, Any]]', similarity_threshold: 'float' = 0.85) -> 'dict[str, Any]'` | Compare today's answers with a baseline file: embedding similarity plus required / forbidden phrases. |
| `WR_prompt_drift_monitor_load_baseline` | `(path: 'str') -> 'dict[str, Any]'` | Read a prompt-drift baseline file: its samples (with their prompts to ask again) and capture time. |
| `WR_prompt_drift_monitor_save_baseline` | `(samples: 'list[dict[str, Any]]', path: 'str') -> 'str'` | Write reference answers and their embedding vectors to a baseline file; returns its path. |
| `WR_prompt_injection_scanner_assert_no_leaks` | `(responses: 'dict[str, str]', minimum_severity: 'str' = 'high', payloads: 'list[dict[str, Any]] | None' = None) -> 'int'` | Fail when a graded response leaked at ``minimum_severity`` or above; returns how many were graded. |
| `WR_prompt_injection_scanner_grade` | `(responses: 'dict[str, str]', payloads: 'list[dict[str, Any]] | None' = None) -> 'dict[str, Any]'` | Grade what your app answered to prompt-injection payloads: which ones leaked, which were refused. |
| `WR_prompt_injection_scanner_payloads` | `() -> 'list[dict[str, Any]]'` | List the built-in prompt-injection payloads: the prompt to send your app and what a leak looks like. |
| `WR_pseudo_localization_assert_no_hardcoded` | `(rendered_text: 'str', catalogue: 'dict[str, str]', min_length: 'int' = 3) -> 'int'` | Fail when a source string of the catalogue appears untranslated in the rendered text. |
| `WR_pseudo_localization_catalogue` | `(catalogue: 'dict[str, str]', accent: 'bool' = True, expansion_ratio: 'float' = 0.4, bracket: 'bool' = True) -> 'dict[str, str]'` | Pseudo-localise every value of a ``{key: string}`` translation catalogue. |
| `WR_pseudo_localization_scan` | `(rendered_text: 'str', catalogue: 'dict[str, str]', min_length: 'int' = 3) -> 'dict[str, Any]'` | Find source strings that still appear untranslated in text rendered under the pseudo locale. |
| `WR_pseudo_localization_scan_page` | `(catalogue: 'dict[str, str]', min_length: 'int' = 3) -> 'dict[str, Any]'` | Find source strings that still appear untranslated in the current page's HTML. |
| `WR_pseudo_localization_text` | `(text: 'str', accent: 'bool' = True, expansion_ratio: 'float' = 0.4, bracket: 'bool' = True) -> 'str'` | Turn a string into its pseudo-localised form (accented look-alikes, padding, brackets). |
| `WR_pull_to_refresh_assert_contained` | `(payload: 'dict[str, Any]') -> 'str'` | Fail when the scroller leaves ``overscroll-behavior-y`` at ``auto`` (the browser would also reload). |
| `WR_pull_to_refresh_assert_threshold` | `(payload: 'dict[str, Any]', min_px: 'float' = 60, max_px: 'float' = 160) -> 'float'` | Fail when the scroller's ``data-pull-threshold`` is missing or outside ``[min_px, max_px]``. |
| `WR_pull_to_refresh_assert_triggered` | `(fired: 'bool', network_refetched: 'bool') -> 'bool'` | Fail unless the pull gesture ran the page's refresh handler and the handler fetched from the network. |
| `WR_pull_to_refresh_snapshot_page` | `(scroller_selector: 'str' = 'body') -> 'dict[str, Any]'` | Read the overscroll behaviour, height and ``data-pull-threshold`` of the page's scroll container. |
| `WR_push_delivery_assert` | `(payload: 'dict[str, Any]', provider: 'str | None' = None, collapse: 'bool' = False) -> 'str'` | Fail when a server-side push payload is invalid for FCM / APNs; returns the provider it was checked as. |
| `WR_push_delivery_check` | `(payload: 'dict[str, Any]', provider: 'str | None' = None, collapse: 'bool' = False) -> 'dict[str, Any]'` | Validate a server-side push payload (FCM v1 ``{"message": ...}`` or APNs ``{"aps": ...}``) without |
| `WR_pw_a11y_run_audit` | `(axe_source: 'str', options: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | 在當前 Playwright 頁面執行 axe.run，回傳結果 dict |
| `WR_pw_add_cookies` | `(cookies: 'list[dict]') -> 'None'` |  |
| `WR_pw_add_init_script` | `(source: 'str') -> 'None'` |  |
| `WR_pw_assert_no_4xx_or_5xx` | `() -> 'None'` |  |
| `WR_pw_assert_no_5xx` | `() -> 'None'` |  |
| `WR_pw_assert_no_console_errors` | `() -> 'None'` |  |
| `WR_pw_back` | `() -> 'None'` |  |
| `WR_pw_block_urls` | `(patterns: 'list[str]') -> 'None'` |  |
| `WR_pw_bring_to_front` | `() -> 'None'` |  |
| `WR_pw_browser_count` | `() -> 'int'` |  |
| `WR_pw_cdp` | `(method: 'str', params: 'dict[str, Any] | None' = None) -> 'Any'` | 在當前 Playwright page 執行 CDP 命令 |
| `WR_pw_cdp_reset_sessions` | `() -> 'None'` | Drop cached Playwright CDP sessions (e.g. after browser restart). |
| `WR_pw_check` | `(selector: 'str', **options: 'Any') -> 'None'` |  |
| `WR_pw_check_current_page` | `(check_dict: 'dict') -> 'None'` |  |
| `WR_pw_clear_cookies` | `() -> 'None'` |  |
| `WR_pw_clear_geolocation` | `() -> 'None'` |  |
| `WR_pw_clear_permissions` | `() -> 'None'` |  |
| `WR_pw_click` | `(selector: 'str', **options: 'Any') -> 'None'` |  |
| `WR_pw_clock_install` | `(fake_now_ms: 'float | None' = None) -> 'None'` |  |
| `WR_pw_clock_run_for` | `(duration_ms: 'float') -> 'None'` |  |
| `WR_pw_clock_set_time` | `(time_ms: 'float') -> 'None'` |  |
| `WR_pw_close_browser` | `() -> 'None'` |  |
| `WR_pw_close_page` | `(index: 'int | None' = None) -> 'None'` |  |
| `WR_pw_connect` | `(ws_endpoint: 'str', browser: 'str' = 'chromium', context_options: 'dict | None' = None) -> 'None'` |  |
| `WR_pw_connect_over_cdp` | `(endpoint_url: 'str') -> 'None'` |  |
| `WR_pw_console_messages` | `() -> 'list[dict[str, Any]]'` |  |
| `WR_pw_content` | `() -> 'str'` |  |
| `WR_pw_dblclick` | `(selector: 'str', **options: 'Any') -> 'None'` |  |
| `WR_pw_delete_cookie` | `(name: 'str') -> 'None'` |  |
| `WR_pw_download` | `(selector: 'str', save_to: 'str') -> 'str'` |  |
| `WR_pw_drag_and_drop` | `(source_selector: 'str', target_selector: 'str', **options: 'Any') -> 'None'` |  |
| `WR_pw_drag_and_drop_offset` | `(selector: 'str', target_x: 'float', target_y: 'float') -> 'None'` |  |
| `WR_pw_element_assert` | `(check_dict: 'dict') -> 'None'` | 斷言目前元素的欄位；不符時拋出例外 |
| `WR_pw_element_change` | `(element_index: 'int') -> 'None'` | Switch ``current_element`` to ``current_element_list[element_index]``. |
| `WR_pw_element_check` | `() -> 'None'` |  |
| `WR_pw_element_clear` | `() -> 'None'` | Clear the value (Playwright equivalent of fill('')) . |
| `WR_pw_element_click` | `() -> 'None'` |  |
| `WR_pw_element_dblclick` | `() -> 'None'` |  |
| `WR_pw_element_fill` | `(input_value: 'str') -> 'None'` | Fill (replace) the element's value. |
| `WR_pw_element_get_attribute` | `(name: 'str') -> 'str | None'` |  |
| `WR_pw_element_get_property` | `(name: 'str')` | Read a JS property via the element handle. |
| `WR_pw_element_hover` | `() -> 'None'` |  |
| `WR_pw_element_inner_html` | `() -> 'str | None'` |  |
| `WR_pw_element_inner_text` | `() -> 'str | None'` |  |
| `WR_pw_element_is_checked` | `() -> 'bool'` |  |
| `WR_pw_element_is_enabled` | `() -> 'bool'` |  |
| `WR_pw_element_is_visible` | `() -> 'bool'` |  |
| `WR_pw_element_press` | `(key: 'str') -> 'None'` |  |
| `WR_pw_element_screenshot` | `(filename: 'str') -> 'str | None'` |  |
| `WR_pw_element_scroll_into_view` | `() -> 'None'` |  |
| `WR_pw_element_select_option` | `(value: 'str | list | dict') -> 'list[str]'` |  |
| `WR_pw_element_submit` | `() -> 'None'` | 送出目前元素所在的表單（元素本身是表單時送出它） |
| `WR_pw_element_type_text` | `(input_value: 'str', delay: 'float' = 0) -> 'None'` | Type text key-by-key (analogue of Selenium ``send_keys``). |
| `WR_pw_element_uncheck` | `() -> 'None'` |  |
| `WR_pw_element_value_of_css_property` | `(property_name: 'str') -> 'str | None'` | The computed value of CSS ``property_name`` on the current element. |
| `WR_pw_emulate` | `(device_name: 'str') -> 'None'` |  |
| `WR_pw_evaluate` | `(expression: 'str', arg: 'Any' = None)` |  |
| `WR_pw_event_capture_clear` | `() -> 'None'` |  |
| `WR_pw_event_capture_start` | `() -> 'None'` | Attach the singleton EventCapture to the active Playwright page. |
| `WR_pw_event_capture_stop` | `() -> 'None'` |  |
| `WR_pw_extension_args` | `(extension_dir: 'str') -> 'list[str]'` | 回傳給 ``pw_launch(args=...)`` 用的旗標清單（Chromium only） |
| `WR_pw_fill` | `(selector: 'str', value: 'str', **options: 'Any') -> 'None'` |  |
| `WR_pw_find_by` | `(by: 'str', value: 'str', wait: 'bool' = True, **options: 'Any')` |  |
| `WR_pw_find_element` | `(selector: 'str')` |  |
| `WR_pw_find_element_with_test_object_record` | `(element_name: 'str')` |  |
| `WR_pw_find_elements` | `(selector: 'str') -> 'list[Any]'` |  |
| `WR_pw_find_elements_with_test_object_record` | `(element_name: 'str')` |  |
| `WR_pw_find_with_healing` | `(name: 'str')` | Playwright 版自我修復定位 |
| `WR_pw_forward` | `() -> 'None'` |  |
| `WR_pw_frame_locator_chain` | `(selectors: 'Sequence[str]') -> 'Any'` | 依序連結 ``page.frame_locator(selector)`` 形成深層 frame locator |
| `WR_pw_get_cookie` | `(name: 'str') -> 'dict | None'` |  |
| `WR_pw_get_cookies` | `() -> 'list[dict]'` |  |
| `WR_pw_grant_permissions` | `(permissions: 'list[str]', origin: 'str | None' = None) -> 'None'` |  |
| `WR_pw_hover` | `(selector: 'str', **options: 'Any') -> 'None'` |  |
| `WR_pw_indexed_db_drop` | `(db_name: 'str') -> 'None'` |  |
| `WR_pw_keyboard_down` | `(key: 'str') -> 'None'` |  |
| `WR_pw_keyboard_press` | `(key: 'str') -> 'None'` |  |
| `WR_pw_keyboard_type` | `(text: 'str', delay: 'float' = 0) -> 'None'` |  |
| `WR_pw_keyboard_up` | `(key: 'str') -> 'None'` |  |
| `WR_pw_last_dialog` | `() -> 'dict | None'` |  |
| `WR_pw_launch` | `(browser: 'str' = 'chromium', headless: 'bool' = True, **options: 'Any') -> 'None'` |  |
| `WR_pw_launch_persistent` | `(user_data_dir: 'str', browser: 'str' = 'chromium', headless: 'bool' = True, extension_paths: 'list[str] | None' = None, **context_options: 'Any') -> 'None'` |  |
| `WR_pw_list_devices` | `() -> 'list[str]'` |  |
| `WR_pw_local_storage_all` | `() -> 'dict'` |  |
| `WR_pw_local_storage_clear` | `() -> 'None'` |  |
| `WR_pw_local_storage_get` | `(key: 'str') -> 'str | None'` |  |
| `WR_pw_local_storage_remove` | `(key: 'str') -> 'None'` |  |
| `WR_pw_local_storage_set` | `(key: 'str', value: 'str') -> 'None'` |  |
| `WR_pw_mouse_click` | `(x: 'float', y: 'float', button: 'str' = 'left', click_count: 'int' = 1) -> 'None'` |  |
| `WR_pw_mouse_down` | `(button: 'str' = 'left', click_count: 'int' = 1) -> 'None'` |  |
| `WR_pw_mouse_move` | `(x: 'float', y: 'float', steps: 'int' = 1) -> 'None'` |  |
| `WR_pw_mouse_up` | `(button: 'str' = 'left', click_count: 'int' = 1) -> 'None'` |  |
| `WR_pw_network_responses` | `() -> 'list[dict[str, Any]]'` |  |
| `WR_pw_new_browser` | `(browser: 'str' = 'chromium', headless: 'bool' = True, **launch_kwargs: 'Any') -> 'int'` |  |
| `WR_pw_new_page` | `() -> 'int'` |  |
| `WR_pw_page_count` | `() -> 'int'` |  |
| `WR_pw_perf_collect` | `(observe_ms: 'int' = 1000) -> 'dict[str, Any]'` | 透過 ``page.evaluate`` 抓取效能指標 |
| `WR_pw_press` | `(selector: 'str', key: 'str', **options: 'Any') -> 'None'` |  |
| `WR_pw_print_page` | `(file_path: 'str') -> 'str'` |  |
| `WR_pw_quit` | `() -> 'None'` |  |
| `WR_pw_recorder_pull_events` | `()` |  |
| `WR_pw_recorder_save` | `(output_path, raw_events_path=None, backend='playwright')` |  |
| `WR_pw_recorder_start` | `()` |  |
| `WR_pw_recorder_stop` | `()` |  |
| `WR_pw_refresh` | `() -> 'None'` |  |
| `WR_pw_route_clear` | `() -> 'None'` |  |
| `WR_pw_route_mock` | `(url_pattern: 'str', response: 'dict') -> 'None'` |  |
| `WR_pw_route_mock_json` | `(url_pattern: 'str', json_data: 'Any', status: 'int' = 200) -> 'None'` |  |
| `WR_pw_route_unmock` | `(url_pattern: 'str') -> 'None'` |  |
| `WR_pw_save_storage_state` | `(path: 'str') -> 'str'` |  |
| `WR_pw_save_test_object_to_selector` | `(test_object_name: 'str', object_type: 'str' = 'CSS_SELECTOR') -> 'str'` | 把 TestObject 存進 ``test_object_record`` 並回傳對應的 Playwright selector |
| `WR_pw_screenshot` | `(path: 'str', full_page: 'bool' = False) -> 'str'` |  |
| `WR_pw_screenshot_base64` | `(full_page: 'bool' = False) -> 'str'` |  |
| `WR_pw_screenshot_bytes` | `(full_page: 'bool' = False) -> 'bytes'` |  |
| `WR_pw_scroll` | `(scroll_x: 'float', scroll_y: 'float') -> 'None'` |  |
| `WR_pw_scroll_to_bottom` | `() -> 'None'` |  |
| `WR_pw_scroll_to_top` | `() -> 'None'` |  |
| `WR_pw_select_option` | `(selector: 'str', value: 'Any', **options: 'Any') -> 'list[str]'` |  |
| `WR_pw_session_storage_clear` | `() -> 'None'` |  |
| `WR_pw_session_storage_get` | `(key: 'str') -> 'str | None'` |  |
| `WR_pw_session_storage_set` | `(key: 'str', value: 'str') -> 'None'` |  |
| `WR_pw_set_cache_disabled` | `(disabled: 'bool' = True) -> 'None'` |  |
| `WR_pw_set_context_options` | `(**options: 'Any') -> 'None'` |  |
| `WR_pw_set_default_navigation_timeout` | `(timeout_ms: 'float') -> 'None'` |  |
| `WR_pw_set_default_timeout` | `(timeout_ms: 'float') -> 'None'` |  |
| `WR_pw_set_dialog_policy` | `(action: 'str' = 'accept', prompt_text: 'str | None' = None) -> 'None'` |  |
| `WR_pw_set_extra_http_headers` | `(headers: 'dict[str, str]') -> 'None'` |  |
| `WR_pw_set_geolocation` | `(latitude: 'float', longitude: 'float', accuracy: 'float | None' = None) -> 'None'` |  |
| `WR_pw_set_locale` | `(locale: 'str', accept_language: 'str | None' = None) -> 'None'` |  |
| `WR_pw_set_timezone` | `(timezone_id: 'str') -> 'None'` |  |
| `WR_pw_set_user_agent` | `(user_agent: 'str') -> 'None'` |  |
| `WR_pw_set_viewport_size` | `(width: 'int', height: 'int') -> 'None'` |  |
| `WR_pw_shadow_query` | `(host_chain: 'Sequence[str]', inner_selector: 'str')` | Resolve the pierce selector against the active Playwright page. |
| `WR_pw_shadow_selector` | `(host_chain: 'Sequence[str]', inner_selector: 'str') -> 'str'` | 把 host 鏈與內層 selector 組成 Playwright ``>>>`` (pierce) 選擇器 |
| `WR_pw_start_har_recording` | `(har_path: 'str', content: 'str' = 'omit') -> 'None'` |  |
| `WR_pw_stop_emulate` | `() -> 'None'` |  |
| `WR_pw_stop_har_recording` | `() -> 'None'` |  |
| `WR_pw_sw_bypass` | `(bypass: 'bool' = True) -> 'None'` | Bypass the service worker via CDP on the active Playwright page. |
| `WR_pw_sw_clear_caches` | `() -> 'list[str]'` |  |
| `WR_pw_sw_unregister` | `() -> 'list[bool]'` |  |
| `WR_pw_switch_browser` | `(index: 'int') -> 'None'` |  |
| `WR_pw_switch_to_frame` | `(selectors: 'str | list[str]') -> 'None'` |  |
| `WR_pw_switch_to_main_frame` | `() -> 'None'` |  |
| `WR_pw_switch_to_page` | `(index: 'int') -> 'None'` |  |
| `WR_pw_switch_to_page_by_title` | `(pattern: 'str') -> 'bool'` |  |
| `WR_pw_switch_to_page_by_url` | `(pattern: 'str') -> 'bool'` |  |
| `WR_pw_switch_to_parent_frame` | `() -> 'None'` |  |
| `WR_pw_throttle` | `(preset: 'str') -> 'Any'` | Apply ``preset`` via the active Playwright page's CDP session. |
| `WR_pw_throttle_clear` | `() -> 'Any'` |  |
| `WR_pw_title` | `() -> 'str'` |  |
| `WR_pw_to_url` | `(url: 'str', **goto_options: 'Any') -> 'None'` |  |
| `WR_pw_tracing_save_chunk` | `(path: 'str') -> 'str'` |  |
| `WR_pw_tracing_start` | `(screenshots: 'bool' = True, snapshots: 'bool' = True, sources: 'bool' = False) -> 'None'` |  |
| `WR_pw_tracing_stop` | `(path: 'str') -> 'str'` |  |
| `WR_pw_type_text` | `(selector: 'str', value: 'str', delay: 'float' = 0, **options: 'Any') -> 'None'` |  |
| `WR_pw_unblock_urls` | `() -> 'None'` |  |
| `WR_pw_uncheck` | `(selector: 'str', **options: 'Any') -> 'None'` |  |
| `WR_pw_upload_file` | `(input_selector: 'str', file_path: 'str') -> 'None'` | 對指定的 file input 送入檔案（Playwright） |
| `WR_pw_url` | `() -> 'str'` |  |
| `WR_pw_video_start` | `(video_dir: 'str', width: 'int | None' = None, height: 'int | None' = None) -> 'None'` |  |
| `WR_pw_video_stop` | `() -> 'list[str]'` |  |
| `WR_pw_viewport_size` | `() -> 'dict | None'` |  |
| `WR_pw_visual_capture_baseline` | `(baseline_path: 'str') -> 'str'` | :func:`capture_baseline` for the current Playwright page. |
| `WR_pw_visual_compare` | `(baseline_path: 'str', diff_path: 'str | None' = None, current_path: 'str | None' = None, threshold: 'int' = 0) -> 'dict'` | :func:`compare_with_baseline` for the current Playwright page. |
| `WR_pw_wait_for_load_state` | `(state: 'str' = 'load', timeout: 'float | None' = None) -> 'None'` |  |
| `WR_pw_wait_for_selector` | `(selector: 'str', timeout: 'float | None' = None, state: 'str' = 'visible')` |  |
| `WR_pw_wait_for_timeout` | `(timeout_ms: 'float') -> 'None'` |  |
| `WR_pw_wait_for_url` | `(url: 'str', timeout: 'float | None' = None) -> 'None'` |  |
| `WR_quarantine_age_report_assert_no_abandoned` | `(registry_path: 'str | None' = None, entries: 'list[dict[str, Any]] | None' = None, now: 'str | None' = None) -> 'Any'` | Fail when a test has been quarantined for 90 days or more. |
| `WR_quarantine_age_report_build` | `(registry_path: 'str | None' = None, entries: 'list[dict[str, Any]] | None' = None, now: 'str | None' = None) -> 'Any'` | Report how long each quarantined test has been parked: fresh, lingering, stale or abandoned. |
| `WR_quarantine_age_report_markdown` | `(registry_path: 'str | None' = None, entries: 'list[dict[str, Any]] | None' = None, now: 'str | None' = None, top_n: 'int' = 10) -> 'str'` | Render the quarantine age report as markdown. |
| `WR_quit` | `() -> None` | 關閉並退出所有 WebDriver |
| `WR_quit_all` | `() -> None` | 關閉並退出所有 WebDriver |
| `WR_quit_current` | `() -> 'None'` | 關閉並退出 WebDriver |
| `WR_rag_grounding_assert_citations` | `(answer: 'str', chunks: 'list[dict[str, str]]', cited_chunk_ids: 'list[str]', minimum: 'int' = 1) -> 'int'` | Fail when the answer cites a chunk that was not retrieved, or fewer than ``minimum`` chunks. |
| `WR_rag_grounding_assert_grounded` | `(answer: 'str', chunks: 'list[dict[str, str]]', min_overlap: 'float' = 0.5) -> 'float'` | Fail when less than ``min_overlap`` of the answer's words appear in the retrieved chunks. |
| `WR_rag_grounding_assert_no_hallucination` | `(answer: 'str', chunks: 'list[dict[str, str]]', max_unsupported_phrases: 'int' = 0, min_phrase_len: 'int' = 4) -> 'list[str]'` | Fail when the answer has more than ``max_unsupported_phrases`` word runs found in no retrieved chunk. |
| `WR_rag_grounding_assert_score` | `(answer: 'str', chunks: 'list[dict[str, str]]', min_phrase_len: 'int' = 4) -> 'dict[str, Any]'` | Measure how well a RAG answer is covered by the retrieved chunks. |
| `WR_rate_limit_assert_burst` | `(responses: 'list[dict[str, Any]]', after: 'int', require_retry_after: 'bool' = True) -> 'dict[str, Any]'` | Fail when no 429 follows the first ``after`` responses of a burst, when ``X-RateLimit-Remaining`` goes |
| `WR_rate_limit_assert_recovery` | `(before: 'dict[str, Any]', after: 'dict[str, Any]') -> 'bool'` | Fail when the request sent after waiting out a 429's ``Retry-After`` is answered with 429 again. |
| `WR_rate_limit_assert_summary` | `(responses: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Read the rate-limit signals of a burst of responses (``{"status_code", "headers"}`` each): whether it |
| `WR_read_depends_on` | `(path: 'str') -> 'list[str]'` | 讀取單一檔案的 ``meta.depends_on`` 清單（以 basename 表示）。 |
| `WR_read_metadata` | `(path: 'str') -> 'dict[str, Any]'` | 讀取 action 檔的 ``meta`` 區塊；若檔案不是 dict 或沒有 meta，回傳空 dict |
| `WR_recorder_pull_events` | `()` |  |
| `WR_recorder_save` | `(output_path, raw_events_path=None, backend='selenium')` |  |
| `WR_recorder_start` | `()` |  |
| `WR_recorder_stop` | `()` |  |
| `WR_refresh` | `() -> 'None'` | 重新整理頁面 / Refresh current page |
| `WR_register_fallback_locator` | `(name: 'str', strategy: 'str', value: 'str') -> 'None'` | Public helper for use as a WR_* command. |
| `WR_register_fallback_locators` | `(name: 'str', fallbacks: 'list[Any]') -> 'None'` | Public helper for use as a WR_* command. |
| `WR_release` | `(element_name: 'str | None' = None) -> 'None'` | 使用 TestObject 名稱找到元素並釋放滑鼠 |
| `WR_release_key` | `(keycode_on_key_class, element_name: 'str | None' = None) -> 'None'` | 使用 TestObject 名稱找到元素並釋放鍵盤按鍵 |
| `WR_reload` | `(ignore_cache: 'bool' = False) -> 'None'` | 重新整理頁面，可選擇是否旁路快取 (透過 CDP ``Page.reload``)。 |
| `WR_render_template` | `(template: 'str', parameters: 'dict[str, Any] | None' = None) -> 'list'` | 套用參數後執行一個動作範本 |
| `WR_repeat` | `(times: 'Any', do: 'list', index_var: 'str | None' = None) -> 'int'` | 把 ``do`` 執行 ``times`` 次 |
| `WR_report_expected_paths` | `(base_name: 'str', allure_dir: 'str | None' = None) -> 'dict[str, list[str]]'` | 回傳每個格式預期寫出的路徑（實際是否存在由 manifest 確認） |
| `WR_reset_actions` | `() -> 'None'` | 清除目前累積的 ActionChains 動作（搭配 ``WR_perform`` 使用） |
| `WR_reset_scheduler` | `() -> 'None'` | Drop all registered jobs and counts (mainly for tests). |
| `WR_resource_hints_audit_assert` | `(html: 'str | None' = None, used_urls: 'list[str] | None' = None, origins: 'list[str] | None' = None) -> 'list[dict[str, Any]]'` | Fail when a ``preload`` has no ``as=``; ``html`` omitted means the current page. |
| `WR_resource_hints_audit_page` | `() -> 'list[dict[str, Any]]'` | List the resource hints of the current page (see ``WR_resource_hints_audit_parse``). |
| `WR_resource_hints_audit_parse` | `(html: 'str') -> 'list[dict[str, Any]]'` | List a document's resource hints (preload, prefetch, preconnect ...) with ``kind``, ``href``, ``as_``. |
| `WR_resource_hints_audit_unused` | `(used_urls: 'list[str]', html: 'str | None' = None) -> 'list[dict[str, Any]]'` | List the preload / prefetch hints whose URL is not among the URLs the page fetched. |
| `WR_retry_block` | `(do: 'list', retries: 'Any' = 1, backoff: 'float' = 0.0) -> 'int'` | 整個區塊失敗時從頭重跑 |
| `WR_right_click` | `(element_name: 'str | None' = None) -> 'None'` | 使用 TestObject 名稱找到元素並右鍵點擊 |
| `WR_route_clear` | `() -> 'None'` | Remove every mock and stop intercepting. |
| `WR_route_mock` | `(url_pattern: 'str | dict[str, str]', response: 'dict[str, Any]') -> 'None'` | 以固定回應回答符合 pattern 的請求 |
| `WR_route_mock_json` | `(url_pattern: 'str | dict[str, str]', json_data: 'Any', status: 'int' = 200) -> 'None'` | A :meth:`route_mock` answering with ``json_data`` as JSON. |
| `WR_route_unmock` | `(url_pattern: 'str | dict[str, str]') -> 'None'` | Remove the mocks registered for ``url_pattern``. |
| `WR_rtl_layout_verify_assert` | `(payload: 'dict[str, Any]', selectors: 'list[str] | None' = None, ordered_selectors: 'list[str] | None' = None) -> 'int'` | Fail on the first right-to-left layout problem (arguments as for ``WR_rtl_layout_verify_check``). |
| `WR_rtl_layout_verify_check` | `(payload: 'dict[str, Any]', selectors: 'list[str] | None' = None, ordered_selectors: 'list[str] | None' = None) -> 'dict[str, Any]'` | Report what is wrong with a right-to-left layout: document direction, physical margins, bidi leaks, order. |
| `WR_run_ab` | `(action_data: 'Any', setup_a: 'Callable[[], Any] | None' = None, setup_b: 'Callable[[], Any] | None' = None, runner: 'Callable[[Any], Any] | None' = None) -> 'dict[str, Any]'` | 對兩個環境跑同一份 action 並回傳比對結果 |
| `WR_run_for_users` | `(action_data: 'Any', user_setups: 'list[tuple[str, Callable[[], Any] | None]]', runner: 'Callable[[Any], Any] | None' = None) -> 'dict[str, Any]'` | 對每位使用者執行一次 ``action_data``，回傳記錄與差異 |
| `WR_run_scheduler_for` | `(seconds: 'float') -> 'None'` |  |
| `WR_run_scheduler_forever` | `() -> 'None'` |  |
| `WR_run_with_dataset` | `(action_data, rows)` |  |
| `WR_save_cookies` | `(file_path: 'str') -> 'bool'` | 將當前頁面的 cookies 序列化為 JSON 並寫入檔案 (用於 session reuse)。 |
| `WR_save_full_page_screenshot` | `(file_path: 'str') -> 'bool'` | 將整個頁面 (含可視範圍外) 截圖儲存為 PNG，透過 CDP |
| `WR_save_locator` | `(name: 'str', value: 'str', by: 'str' = 'CSS_SELECTOR') -> 'str'` | 以邏輯名稱儲存定位器 |
| `WR_save_screenshot` | `(file_path: 'str') -> 'bool'` | 將當前頁面截圖儲存至指定路徑 (PNG) |
| `WR_save_test_object` | `(test_object_name: str, object_type: str | None = None, **kwargs) -> None` | 儲存新的測試物件 |
| `WR_SaveTestObject` | `(test_object_name: str, object_type: str | None = None, **kwargs) -> None` | 儲存新的測試物件 |
| `WR_sbom_diff_assert_acceptable` | `(base: 'dict[str, Any] | str', head: 'dict[str, Any] | str', disallowed_licenses: 'list[str] | None' = None) -> 'dict[str, Any]'` | Fail when ``head`` adds a vulnerable component or, with ``disallowed_licenses``, one of those licenses. |
| `WR_sbom_diff_compare` | `(base: 'dict[str, Any] | str', head: 'dict[str, Any] | str') -> 'dict[str, Any]'` | Compare two CycloneDX SBOMs: components added, removed, upgraded, downgraded, new licenses. |
| `WR_sbom_diff_markdown` | `(base: 'dict[str, Any] | str', head: 'dict[str, Any] | str') -> 'str'` | Return the difference of two CycloneDX SBOMs as Markdown, ready for a PR comment. |
| `WR_scan_secrets` | `(data: 'Any') -> 'list[dict[str, Any]]'` | 掃描 action 結構，回傳所有疑似秘密的位置 |
| `WR_scan_secrets_file` | `(path: 'str') -> 'list[dict[str, Any]]'` | 讀取 action JSON 檔並掃描 / Load an action JSON file and scan it. |
| `WR_schedule` | `(name: 'str', interval_seconds: 'float', callback: 'Callable[[], Any]') -> 'None'` |  |
| `WR_scheduler_counts` | `() -> 'dict[str, int]'` |  |
| `WR_screen_reader_runner_assert_no_violations` | `(tree: 'dict[str, Any]') -> 'int'` | Fail when an accessibility tree has an unnamed control, a skipped heading level, an image without alt |
| `WR_screen_reader_runner_assert_reads` | `(tree: 'dict[str, Any]', expected_phrase: 'str') -> 'dict[str, Any]'` | Fail unless a screen reader walking the accessibility tree would say ``expected_phrase``. |
| `WR_screen_reader_runner_walk` | `(tree: 'dict[str, Any]', include_decorative: 'bool' = False) -> 'dict[str, Any]'` | Say what a screen reader would announce for an accessibility tree, and list the problems met on the way. |
| `WR_scroll` | `(scroll_x: 'int', scroll_y: 'int') -> 'None'` | 滾動頁面 |
| `WR_scroll_to_bottom` | `() -> 'None'` | 捲動到頁面最下方 / Scroll to the bottom of the page |
| `WR_scroll_to_top` | `() -> 'None'` | 捲動到頁面最上方 / Scroll to the top of the page |
| `WR_sel_to_pw_supported` | `() -> 'dict[str, list[str]]'` | List what the Selenium to Playwright translator covers: action commands and Python patterns. |
| `WR_sel_to_pw_translate_actions` | `(actions: 'list[Any]') -> 'list[list[Any]]'` | Rewrite the Selenium commands of an action list to their ``WR_pw_*`` Playwright commands. |
| `WR_sel_to_pw_translate_for_backend` | `(actions: 'list[Any] | dict[str, Any]', backend: 'str' = 'playwright') -> 'Any'` | Translate an action list or document to the commands of ``backend`` (``"playwright"`` from ``WR_*``, |
| `WR_sel_to_pw_translate_python` | `(source: 'str') -> 'list[dict[str, Any]]'` | Translate Selenium Python source line by line; returns each changed line with its Playwright draft. |
| `WR_send_keys` | `(keys_to_send) -> 'None'` | 發送鍵盤按鍵 (按下並釋放) |
| `WR_send_keys_to_element` | `(element_name: 'str', keys_to_send) -> 'None'` | 使用 TestObject 名稱找到元素並發送鍵盤按鍵 |
| `WR_session_storage_clear` | `() -> 'None'` |  |
| `WR_session_storage_get` | `(key: 'str') -> 'str | None'` |  |
| `WR_session_storage_set` | `(key: 'str', value: 'str') -> 'None'` |  |
| `WR_session_to_test_convert` | `(events: 'Any') -> 'dict[str, Any]'` | Turn a recorded user session into WebRunner actions. |
| `WR_session_to_test_write` | `(events: 'Any', output_path: 'str') -> 'dict[str, Any]'` | Convert a recorded session like ``WR_session_to_test_convert`` and write the actions to a JSON file. |
| `WR_set_action_span_factory` | `(factory: Optional[Callable[[str], Any]]) -> None` | 登錄一個 context-manager factory，每個 action 會被它包起來 |
| `WR_set_allow_arbitrary_script` | `(enabled: bool) -> None` | 切換是否允許 ``WR_execute_script`` / ``WR_pw_evaluate`` / CDP 命令 |
| `WR_set_cache_disabled` | `(disabled: 'bool' = True) -> 'None'` | 透過 CDP ``Network.setCacheDisabled`` 切換 HTTP 快取。 |
| `WR_set_device_metrics` | `(width: 'int', height: 'int', device_scale_factor: 'float' = 1, mobile: 'bool' = False) -> 'None'` | 以 CDP ``Emulation.setDeviceMetricsOverride`` 覆寫裝置外觀 (viewport / DPR / mobile)。 |
| `WR_set_download_directory` | `(download_path: 'str', behavior: 'str' = 'allow') -> 'None'` | 透過 CDP ``Browser.setDownloadBehavior`` 指定下載資料夾 (headless 必備)。 |
| `WR_set_driver` | `(webdriver_name: 'str', webdriver_manager_option_dict: 'dict | None' = None, options: 'list[str] | None' = None, experimental_options: 'dict | None' = None, extension_paths: 'list[str] | None' = None, enable_bidi: 'bool' = False, install_driver: 'bool' = True, **kwargs) -> 'webdriver.Chrome | webdriver.Firefox | webdriver.Edge | webdriver.Ie | webdriver.Safari'` | 啟動一個新的 WebDriver |
| `WR_set_extra_http_headers` | `(headers: 'dict') -> 'None'` | 以 CDP ``Network.setExtraHTTPHeaders`` 為所有後續請求附加 header。 |
| `WR_set_fail_fast` | `(enabled: bool = True) -> None` | 設定第一個失敗後是否跳過清單其餘動作 |
| `WR_set_failure_screenshot_dir` | `(path: str | None) -> None` | 設定 (或停用) 動作失敗時的自動截圖目錄 |
| `WR_set_geolocation` | `(latitude: 'float', longitude: 'float', accuracy: 'float' = 100) -> 'None'` | 以 CDP ``Emulation.setGeolocationOverride`` 覆寫地理位置。 |
| `WR_set_locale` | `(locale: 'str') -> 'None'` | 以 CDP ``Emulation.setLocaleOverride`` 覆寫語系。 |
| `WR_set_network_conditions` | `(offline: 'bool' = False, latency: 'float' = 0, download_throughput: 'float' = -1, upload_throughput: 'float' = -1) -> 'None'` | 以 CDP ``Network.emulateNetworkConditions`` 模擬網路條件 (離線、節流)。 |
| `WR_set_page_load_timeout` | `(time_to_wait: 'int') -> 'None'` | 設定頁面載入最大等待時間 / Set max page load wait time |
| `WR_set_raise_wrapper_errors` | `(enabled: bool) -> None` | 設定 Selenium wrapper 失敗時是否讓動作失敗 |
| `WR_set_record_enable` | `(set_enable: bool = True)` | 開啟或關閉紀錄功能 |
| `WR_set_retry_policy` | `(retries: int = 0, backoff: float = 0.0) -> None` | 設定全域重試策略 |
| `WR_set_script_timeout` | `(time_to_wait: 'int') -> 'None'` | 設定 script 最大執行時間 / Set max script execution time |
| `WR_set_timezone` | `(timezone_id: 'str') -> 'None'` | 以 CDP ``Emulation.setTimezoneOverride`` 覆寫時區。 |
| `WR_set_user_agent` | `(user_agent: 'str') -> 'None'` | 以 CDP ``Network.setUserAgentOverride`` 動態覆寫 User-Agent。 |
| `WR_set_var` | `(name: 'str', value: 'Any' = None, local: 'bool' = False) -> 'Any'` | 設定變數 |
| `WR_set_webdriver_options_capability` | `(key_and_vale_dict: 'dict') -> 'Options | None'` | 設定 WebDriver 的 capabilities |
| `WR_set_window_position` | `(x: 'int', y: 'int', window_handle: 'str' = 'current') -> 'dict | None'` | 設定視窗位置 |
| `WR_set_window_rect` | `(x: 'int | None' = None, y: 'int | None' = None, width: 'int | None' = None, height: 'int | None' = None) -> 'dict | None'` | 設定視窗矩形 (位置與大小)，僅支援 W3C 相容瀏覽器 |
| `WR_set_window_size` | `(width: 'int', height: 'int', window_handle: 'str' = 'current') -> 'None'` | 設定視窗大小 |
| `WR_shadow_query` | `(host_chain: 'Sequence[str]', inner_selector: 'str') -> 'Any'` | 在巢狀 Shadow DOM 中查詢 |
| `WR_single_quit` | `() -> 'None'` | 關閉並退出 WebDriver |
| `WR_skip_dependents_of_failed` | `(graph: 'dict[str, list[str]]', failed: 'Iterable[str]') -> 'list[str]'` | 回傳因為上游失敗而應該跳過的檔案 |
| `WR_sla_tracker_assert_meets` | `(runs: 'list[dict[str, Any]] | str', max_duration_seconds: 'float', target_pass_pct: 'float', suite: 'str | None' = None) -> 'Any'` | Fail when fewer than ``target_pass_pct`` percent of suite runs finished within the duration. |
| `WR_sla_tracker_compute` | `(runs: 'list[dict[str, Any]] | str', max_duration_seconds: 'float', target_pass_pct: 'float', bucket: 'str' = 'week', suite: 'str | None' = None) -> 'Any'` | Compute the share of suite runs that finished within ``max_duration_seconds``, per week or day. |
| `WR_sla_tracker_markdown` | `(runs: 'list[dict[str, Any]] | str', max_duration_seconds: 'float', target_pass_pct: 'float', bucket: 'str' = 'week', suite: 'str | None' = None) -> 'str'` | Render the SLA report of suite runs (rows, or the path of a ledger file) as markdown. |
| `WR_slack_digest_payload` | `(digest: 'dict[str, Any]', channel: 'str | None' = None) -> 'dict[str, Any]'` | Render a test digest as a Slack ``chat.postMessage`` payload (Block Kit); nothing is sent. |
| `WR_slack_digest_teams_card` | `(digest: 'dict[str, Any]') -> 'dict[str, Any]'` | Render a test digest (same ``digest`` as ``WR_slack_digest_payload``) as a Microsoft Teams Adaptive Card. |
| `WR_slack_digest_text` | `(digest: 'dict[str, Any]') -> 'str'` | Render a test digest (same ``digest`` as ``WR_slack_digest_payload``) as plain text. |
| `WR_sleep` | `(seconds: 'int | float' = 1) -> 'float'` | 阻塞當前執行緒指定秒數，回傳實際睡眠的秒數。 |
| `WR_smart_wait_fetch_idle` | `(quiet_for: 'float' = 0.5, timeout: 'float' = 10.0, poll: 'float' = 0.1) -> 'bool'` | Wait until the page has had no fetch / XHR request in flight for ``quiet_for`` seconds. |
| `WR_smart_wait_install_hooks` | `() -> 'bool'` | Install the fetch / XHR counter and the history-change hook in the current page. |
| `WR_smart_wait_route_stable` | `(quiet_for: 'float' = 0.4, timeout: 'float' = 10.0, poll: 'float' = 0.1) -> 'bool'` | Wait until a single-page app has not changed its route for ``quiet_for`` seconds. |
| `WR_snapshot_diff_approval_approve` | `(path: 'str', name: 'str', reviewer: 'str') -> 'Any'` | Promote the pending snapshot ``name`` of the registry file to baseline; returns its entry. |
| `WR_snapshot_diff_approval_assert_no_pending` | `(path: 'str') -> 'None'` | Fail when a snapshot of the registry file waits for review. |
| `WR_snapshot_diff_approval_capture` | `(path: 'str', name: 'str', text: 'str | None' = None, payload_path: 'str | None' = None) -> 'dict[str, Any]'` | Compare a snapshot with its approved baseline in the registry file at ``path`` and record a mismatch. |
| `WR_snapshot_diff_approval_list_pending` | `(path: 'str') -> 'Any'` | List the snapshots of the registry file that wait for review. |
| `WR_snapshot_diff_approval_reject` | `(path: 'str', name: 'str', reviewer: 'str', note: 'str' = '') -> 'Any'` | Mark the snapshot ``name`` of the registry file as rejected; returns its entry. |
| `WR_snapshot_directory` | `(directory: 'str') -> 'list[str]'` | Take a snapshot of resolved file paths under ``directory``. |
| `WR_speculation_rules_assert` | `(payload: 'dict[str, Any]', activated: 'bool' = True, no_double_fire: 'list[str] | None' = None, fire_counts: 'dict[str, int] | None' = None) -> 'dict[str, Any]'` | Check a prerender log: the page was ``activated`` after prerendering, none of the ``no_double_fire`` event |
| `WR_speculation_rules_build_tag` | `(prefetch: 'list[dict[str, Any]] | None' = None, prerender: 'list[dict[str, Any]] | None' = None) -> 'str'` | Render a ``<script type="speculationrules">`` tag from rules ``[{"source": "list", "urls": [...], |
| `WR_speculation_rules_harvest` | `() -> 'dict[str, Any]'` | The prerender log recorded so far: ``{"events": [...], "fires": {name: count}}``. |
| `WR_speculation_rules_install` | `() -> 'bool'` | Start recording the page's ``prerenderingchange`` events; the page counts events with ``__wr_spec_fire__``. |
| `WR_speech_api_assert_check` | `(utterances: 'list[dict[str, Any]]', text_contains: 'str | None' = None, lang: 'str | None' = None, no_speech: 'bool' = False, volume_range: 'list[float] | None' = None) -> 'list[dict[str, Any]]'` | Check recorded utterances: one contains ``text_contains``, all that name a language use ``lang``, all |
| `WR_speech_api_assert_harvest` | `() -> 'list[dict[str, Any]]'` | Read and empty the recorded utterances: ``[{"text", "lang", "rate", "pitch", "volume"}]``. |
| `WR_speech_api_assert_install` | `() -> 'bool'` | Record the page's ``speechSynthesis.speak`` calls and replace ``SpeechRecognition`` with a scripted mock. |
| `WR_speech_api_assert_push_transcript` | `(text: 'str') -> 'bool'` | Queue ``text`` as what the mocked ``SpeechRecognition`` hears on its next ``start()``. |
| `WR_sri_verify_assert_all_ok` | `(html: 'str | None' = None, require_crossorigin: 'bool' = True, resource_files: 'dict[str, str] | None' = None) -> 'list[dict[str, Any]]'` | Fail when a script or stylesheet lacks a valid, strong ``integrity`` attribute. |
| `WR_sri_verify_compute` | `(path: 'str', algorithm: 'str' = 'sha384') -> 'str'` | Return the ``integrity`` value (``sha384-...``) for the file at ``path``. |
| `WR_sri_verify_html` | `(html: 'str', require_crossorigin: 'bool' = True, resource_files: 'dict[str, str] | None' = None) -> 'list[dict[str, Any]]'` | Check every ``<script src>`` and stylesheet ``<link>`` in ``html`` for Subresource Integrity. |
| `WR_sri_verify_page` | `(require_crossorigin: 'bool' = True) -> 'list[dict[str, Any]]'` | Check the scripts and stylesheets of the current page for Subresource Integrity. |
| `WR_sse_assert_count` | `(text: 'str | None' = None, event_type: 'str | None' = None, minimum: 'int' = 1, maximum: 'int | None' = None) -> 'int'` | Fail unless the number of events (of ``event_type``, when given) is between ``minimum`` and ``maximum``. |
| `WR_sse_assert_data` | `(text: 'str | None' = None, event_type: 'str | None' = None, contains: 'str | None' = None, json_keys: 'list[str] | None' = None, increasing_ids: 'bool' = False) -> 'dict[str, Any] | None'` | Fail unless an event's data has the text ``contains``, an event's JSON data has every key of |
| `WR_sse_assert_events` | `(event_type: 'str | None' = None) -> 'list[dict[str, Any]]'` | The events the recorder holds, optionally only those of ``event_type``. |
| `WR_sse_assert_feed` | `(chunk: 'str') -> 'dict[str, int]'` | Add a chunk of an SSE stream to the recorder; an event counts once its closing blank line arrives. |
| `WR_sse_assert_parse` | `(text: 'str') -> 'list[dict[str, Any]]'` | Parse Server-Sent Events wire text into ``[{"event", "data", "id", "retry", "timestamp"}]``. |
| `WR_sse_assert_reset` | `() -> 'bool'` | Empty the SSE recorder, including a half-received event. |
| `WR_start_har_recording` | `() -> 'None'` | Start recording every request and response of the driver into a HAR log. |
| `WR_start_remote_driver` | `(hub_url: 'str', capabilities: 'dict[str, Any]', register: 'bool' = True) -> 'WebDriver'` | 啟動 Remote WebDriver；預設將其註冊到 ``webdriver_wrapper_instance`` |
| `WR_state_diff_assert_no_change` | `(before: 'dict[str, Any]', after: 'dict[str, Any]', allow_keys: 'list[str] | None' = None) -> 'bool'` | Fail when a cookie or storage key outside ``allow_keys`` differs between two snapshots. |
| `WR_state_diff_capture` | `() -> 'dict[str, Any]'` | Snapshot the cookies, localStorage and sessionStorage of the current page. |
| `WR_state_diff_compare` | `(before: 'dict[str, Any]', after: 'dict[str, Any]') -> 'dict[str, Any]'` | List what was added, removed or changed between two snapshots from ``WR_state_diff_capture``. |
| `WR_stop_har_recording` | `(har_path: 'str | None') -> 'str | None'` | Stop recording and write the HAR 1.2 log to ``har_path`` (nothing is written for None). |
| `WR_stop_scheduler` | `() -> 'None'` |  |
| `WR_storage_buckets_assert` | `(snapshot: 'dict[str, Any]', supported: 'bool' = True, bucket: 'str | None' = None, durability: 'str | None' = None, allowed: 'list[str] | None' = None) -> 'dict[str, Any]'` | Check a storage-buckets snapshot: the API is ``supported``, ``bucket`` exists (with ``durability`` |
| `WR_storage_buckets_assert_isolated` | `(snapshot: 'dict[str, Any]', db_name: 'str', expected_bucket: 'str') -> 'bool'` | Fail unless the IndexedDB database ``db_name`` lives in ``expected_bucket`` and in no other bucket. |
| `WR_storage_buckets_harvest` | `() -> 'dict[str, Any]'` | Snapshot the current page's storage buckets: ``{"supported": bool, "buckets": [{name, idb_databases, ...}]}``. |
| `WR_story_to_actions_build_prompt` | `(story: 'str', start_url: 'str | None' = None, figma_hints: 'list[dict[str, Any]] | None' = None, style_notes: 'list[str] | None' = None) -> 'str'` | Render the prompt that asks a language model to turn a user story into an action list. |
| `WR_story_to_actions_parse_reply` | `(reply: 'str', start_url: 'str | None' = None) -> 'list[dict[str, Any]]'` | Parse and validate the action list a model replied with (a JSON array, optionally in a code fence). |
| `WR_story_to_actions_validate` | `(actions: 'list[dict[str, Any]]') -> 'int'` | Fail when a ``{"WR_command": [arguments]}`` list uses a command or arguments a story may not produce. |
| `WR_storybook_discover` | `(source: 'str | dict[str, Any]', skip_examples: 'bool' = True, title_prefix: 'str | None' = None) -> 'list[dict[str, Any]]'` | List the stories of a Storybook ``index.json`` / ``stories.json`` (a file path or the parsed object). |
| `WR_storybook_plan_actions` | `(source: 'str | dict[str, Any]', base_url: 'str', run_a11y: 'bool' = True, capture_screenshot: 'bool' = True, title_prefix: 'str | None' = None) -> 'list[list[Any]]'` | Build an action list that opens every story under ``base_url``, audits it and takes a screenshot. |
| `WR_streaming_chat_assert_content` | `(deltas: 'list[dict[str, Any]]', expected: 'str' = '') -> 'str'` | Fail when the assembled stream has a broken UTF-8 character or lacks ``expected``; returns the text. |
| `WR_streaming_chat_assert_order` | `(deltas: 'list[dict[str, Any]]') -> 'int'` | Fail when numbered chunks (``seq``) arrived twice or out of order; returns how many were numbered. |
| `WR_streaming_chat_assert_summary` | `(deltas: 'list[dict[str, Any]]') -> 'dict[str, Any]'` | Summarise a recorded chat stream: the assembled text, time to first token, longest gap. |
| `WR_streaming_chat_assert_timing` | `(deltas: 'list[dict[str, Any]]', max_ttft_ms: 'float | None' = None, max_gap_ms: 'float | None' = None) -> 'dict[str, Any]'` | Fail when the first token came later than ``max_ttft_ms`` or two tokens were over ``max_gap_ms`` apart. |
| `WR_summarise_run` | `() -> 'dict[str, Any]'` | 從 ``test_record_instance`` 產生 pass/fail 統計 |
| `WR_sw_bypass` | `(bypass: 'bool' = True) -> 'None'` | 透過 CDP 設定 ServiceWorker bypass（僅 Chromium 系） |
| `WR_sw_clear_caches` | `() -> 'list[str]'` | 清空 Cache Storage |
| `WR_sw_unregister` | `() -> 'list[bool]'` | 解除註冊當前頁面所有 Service Worker |
| `WR_switch` | `(switch_type: 'str', switch_target_name: 'str | None' = None)` | 切換 WebDriver 的上下文 (frame, window, alert...) |
| `WR_switch_to_window_by_title` | `(pattern: 'str') -> 'bool'` | 遍歷所有 window handle，切換到第一個 title 含 ``pattern`` 子字串的視窗。 |
| `WR_switch_to_window_by_url` | `(pattern: 'str') -> 'bool'` | 遍歷所有 window handle，切換到第一個 URL 含 ``pattern`` 子字串的視窗。 |
| `WR_tc_cleanup_all` | `() -> 'None'` | Stop every container started by this module. |
| `WR_tc_generic` | `(image: 'str', ports: 'dict[int, int] | None' = None) -> 'Any'` | 啟動任意 Docker image |
| `WR_tc_postgres` | `(image: 'str' = 'postgres:16-alpine', username: 'str' = 'test', password: 'str' = 'test', dbname: 'str' = 'test') -> 'Any'` | 啟動暫存 Postgres，回傳 container 實例（含 ``get_connection_url()``） |
| `WR_tc_redis` | `(image: 'str' = 'redis:7-alpine') -> 'Any'` |  |
| `WR_tc_started_count` | `() -> 'int'` | How many containers are tracked as live by this module. |
| `WR_tc_stop` | `(container: 'Any') -> 'None'` | Stop a single container started by this module. |
| `WR_test_auto_repair_apply` | `(action_path: 'str', plan: 'dict[str, Any]', output_path: 'str | None' = None, min_confidence: 'float' = 0.5) -> 'str'` | Write a repair plan's action list next to the action file (``<file>.repaired.json``) or to ``output_path``. |
| `WR_test_auto_repair_git_diff` | `(repo_dir: 'str' = '.', since_ref: 'str' = 'HEAD~1', paths: 'list[str] | None' = None, max_chars: 'int' = 6000) -> 'str'` | Read ``git diff <since_ref>..HEAD`` of a repository, cut to ``max_chars``; empty when git fails. |
| `WR_test_auto_repair_render_markdown` | `(plan: 'dict[str, Any]', heading_level: 'int' = 2) -> 'str'` | Render a test repair plan as markdown for a PR comment. |
| `WR_test_blame_owner_assert_has_owner` | `(test_path: 'str', codeowners_text: 'str | None' = None, codeowners_path: 'str | None' = None, blame: 'list[dict[str, Any]] | None' = None, head_author: 'str' = '', default: 'str' = '') -> 'str'` | Fail when no owner can be found for ``test_path``; returns the primary owner. |
| `WR_test_blame_owner_codeowners` | `(test_path: 'str', codeowners_text: 'str | None' = None, codeowners_path: 'str | None' = None) -> 'list[str]'` | List the owners a CODEOWNERS body (given as text or as a file path) names for ``test_path``. |
| `WR_test_blame_owner_resolve` | `(test_path: 'str', codeowners_text: 'str | None' = None, codeowners_path: 'str | None' = None, blame: 'list[dict[str, Any]] | None' = None, head_author: 'str' = '', default: 'str' = '') -> 'Any'` | Decide who to ping for a failing test: CODEOWNERS, then blame, then the last committer, then a default. |
| `WR_test_categorizer_categorize` | `(actions: 'list[Any]') -> 'list[str]'` | Tag an action list by what it does: smoke, regression, perf, a11y, security, payment, visual, api. |
| `WR_test_categorizer_categorize_dir` | `(directory: 'str') -> 'dict[str, Any]'` | Tag every ``*.json`` action file of a directory; returns the ``assignments`` and the tag ``distribution``. |
| `WR_test_categorizer_categorize_file` | `(path: 'str') -> 'Any'` | Tag the action file at ``path``; returns its ``tags`` and ``action_count``. |
| `WR_test_cost_estimator_estimate` | `(ledger_path: 'str | None' = None, runs: 'list[dict[str, Any]] | None' = None, rate_cards: 'list[dict[str, Any]] | None' = None) -> 'Any'` | Estimate billed minutes, cost and CO2 of recorded test runs, per runner and per test. |
| `WR_test_cost_estimator_markdown` | `(ledger_path: 'str | None' = None, runs: 'list[dict[str, Any]] | None' = None, rate_cards: 'list[dict[str, Any]] | None' = None, top_tests: 'int' = 5) -> 'str'` | Render the cost estimate of recorded test runs as markdown. |
| `WR_test_debt_dashboard_assert_under_age_limit` | `(root: 'str', max_days: 'float', codeowners_path: 'str | None' = None) -> 'int'` | Fail when deferred test work under a directory is ``max_days`` old or more; returns the item count. |
| `WR_test_debt_dashboard_markdown` | `(root: 'str') -> 'str'` | Render the count of deferred test work under a directory, per kind, as markdown. |
| `WR_test_debt_dashboard_scan` | `(root: 'str', codeowners_path: 'str | None' = None) -> 'dict[str, Any]'` | List the deferred test work under a directory: skip / xfail marks, TODO comments, ``"_skip"`` steps. |
| `WR_test_debt_dashboard_scan_file` | `(path: 'str', codeowners_path: 'str | None' = None) -> 'Any'` | List the deferred test work in one file: a ``*.json`` action file or a Python test file. |
| `WR_test_dedup_ai_fingerprint` | `(actions: 'list[Any]') -> 'str'` | Hash the structure of an action list (commands and argument kinds, not the test data). |
| `WR_test_dedup_ai_semantic` | `(directory: 'str', embeddings: 'dict[str, list[float]]', similarity_threshold: 'float' = 0.92) -> 'dict[str, Any]'` | Group the action files of a directory whose embedding vectors are close (cosine similarity). |
| `WR_test_dedup_ai_structural` | `(directory: 'str') -> 'dict[str, Any]'` | Group the action files (``*.json``) of a directory that have the same structure; returns the clusters. |
| `WR_test_dup_dry_assert_no_duplicates` | `(specs: 'list[dict[str, Any]]') -> 'None'` | Fail when two tests walk the same steps. |
| `WR_test_dup_dry_find_duplicates` | `(specs: 'list[dict[str, Any]]') -> 'Any'` | Find tests that walk the same steps. |
| `WR_test_dup_dry_find_prefix_overlap` | `(specs: 'list[dict[str, Any]]', min_prefix: 'int' = 5) -> 'Any'` | Find pairs of tests that start with the same ``min_prefix`` or more steps, longest overlap first. |
| `WR_test_naming_lint_assert_clean` | `(names: 'list[str]', convention: 'str' = 'snake_case_should_when', max_length: 'int' = 100) -> 'None'` | Fail when a test function name breaks the naming convention. |
| `WR_test_naming_lint_lint` | `(names: 'list[str]', convention: 'str' = 'snake_case_should_when', max_length: 'int' = 100) -> 'Any'` | Check test function names against a naming convention; returns the findings. |
| `WR_test_owners_map_assert_no_unowned` | `(test_ids: 'list[str]', codeowners_text: 'str | None' = None, codeowners_path: 'str | None' = None, overrides: 'dict[str, list[str]] | None' = None) -> 'None'` | Fail when a test has no owner. |
| `WR_test_owners_map_audit` | `(test_ids: 'list[str]', codeowners_text: 'str | None' = None, codeowners_path: 'str | None' = None, overrides: 'dict[str, list[str]] | None' = None) -> 'dict[str, Any]'` | Count tests per owner and list the ``unowned`` ones; ``passed`` is true when every test has an owner. |
| `WR_test_owners_map_owners_for` | `(test_id: 'str', codeowners_text: 'str | None' = None, codeowners_path: 'str | None' = None, overrides: 'dict[str, list[str]] | None' = None) -> 'list[str]'` | List the owners of a test: its entry in ``overrides`` (test id to owners), else the CODEOWNERS match. |
| `WR_test_roi_scorer_removal_candidates` | `(metrics: 'list[dict[str, Any]]', max_score: 'float' = 0.3, weights: 'dict[str, float] | None' = None) -> 'Any'` | List the tests whose return-on-investment score is ``max_score`` or lower. |
| `WR_test_roi_scorer_score` | `(metrics: 'list[dict[str, Any]]', weights: 'dict[str, float] | None' = None) -> 'Any'` | Score tests 0..1 for return on investment, best first, with a keep / review / consider-removing verdict. |
| `WR_test_scheduler_candidates_from_ledger` | `(ledger_path: 'str', default_duration_seconds: 'float' = 60.0, cloud_tests: 'list[str] | None' = None) -> 'Any'` | Build one scheduling candidate per test of a run ledger: average duration, fail rate, last-run age. |
| `WR_test_scheduler_markdown` | `(candidates: 'list[dict[str, Any]]', time_budget_seconds: 'float', cloud_slot_budget: 'int | None' = None, pinned_test_ids: 'list[str] | None' = None) -> 'str'` | Render the schedule that fits the budgets as markdown. |
| `WR_test_scheduler_schedule` | `(candidates: 'list[dict[str, Any]]', time_budget_seconds: 'float', cloud_slot_budget: 'int | None' = None, pinned_test_ids: 'list[str] | None' = None) -> 'Any'` | Pick the tests worth most per second that fit a time budget (and a cloud-session budget). |
| `WR_test_self_describe_assert_mentions` | `(actions: 'list[Any]', needles: 'list[str]', title: 'str' = '') -> 'str'` | Fail when the description of an action list lacks one of ``needles``; returns the description. |
| `WR_test_self_describe_describe` | `(actions: 'list[Any]', title: 'str' = '') -> 'str'` | Describe an action list as a Gherkin-style paragraph, under ``# title`` when one is given. |
| `WR_test_self_describe_summarise` | `(actions: 'list[Any]') -> 'list[dict[str, str]]'` | Describe each step of an action list as a ``Given`` / ``When`` / ``Then`` sentence. |
| `WR_third_party_block_test_assert` | `(outcomes: 'list[dict[str, Any]]', vendors: 'list[str]') -> 'list[dict[str, Any]]'` | Fail when the flow broke while one of ``vendors`` was blocked. |
| `WR_third_party_block_test_block` | `(vendors: 'list[Any]') -> 'dict[str, Any]'` | Block third-party vendors in the current Chromium browser, to see whether the flow survives without them. |
| `WR_third_party_block_test_unblock` | `() -> 'bool'` | Stop blocking the vendors ``WR_third_party_block_test_block`` blocked. |
| `WR_third_party_block_test_vendors` | `() -> 'list[dict[str, Any]]'` | List the built-in third-party vendors with the URL patterns that block them. |
| `WR_third_party_budget_assert` | `(har: 'Any', first_party_hostname: 'str', budget: 'dict[str, Any] | None' = None, extra_vendors: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | Fail (``ThirdPartyBudgetError``) over budget; arguments as ``WR_third_party_budget_evaluate``. |
| `WR_third_party_budget_classify` | `(har: 'Any', first_party_hostname: 'str', extra_vendors: 'dict[str, Any] | None' = None) -> 'list[dict[str, Any]]'` | List a HAR's requests to hosts other than the site's own, each with its vendor. |
| `WR_third_party_budget_evaluate` | `(har: 'Any', first_party_hostname: 'str', budget: 'dict[str, Any] | None' = None, extra_vendors: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'` | Add up a HAR's third-party requests and compare them with a budget. |
| `WR_three_d_secure_flow_assert` | `(flow: 'dict[str, Any]', expected: 'str | None' = None, error_contains: 'str' = '') -> 'str'` | Fail when a 3-D Secure checkout finalised a rejected card, skipped part of the challenge, did not end in |
| `WR_three_d_secure_flow_classify` | `(flow: 'dict[str, Any]') -> 'str'` | Name the branch a 3-D Secure checkout took: frictionless_ok, challenge_ok, rejected, fallback, incomplete. |
| `WR_throttle` | `(preset: 'str') -> 'Any'` | Apply ``preset`` via the active Selenium driver's CDP channel. |
| `WR_throttle_clear` | `() -> 'Any'` | Convenience for the ``no_throttling`` preset. |
| `WR_throttle_presets` | `() -> 'list'` | Return all registered preset names. |
| `WR_throttler_acquire` | `(name: 'str', timeout: 'float' = 30.0) -> 'str'` | Take one slot of a configured service, waiting up to ``timeout`` seconds for a free one. |
| `WR_throttler_configure` | `(name: 'str', capacity: 'int', base_dir: 'str | None' = None, stale_after: 'float' = 600.0) -> 'dict[str, Any]'` | Declare a service that at most ``capacity`` runs (shards, processes) may use at the same time. |
| `WR_throttler_release` | `(name: 'str', slot: 'str') -> 'bool'` | Give back a slot ``WR_throttler_acquire`` returned for the service ``name``. |
| `WR_throttler_reset` | `() -> 'bool'` | Forget every service ``WR_throttler_configure`` declared (slot files already taken are kept). |
| `WR_tls_cipher_audit_assert_host` | `(host: 'str', port: 'int' = 443, timeout: 'float' = 10.0, banned_tokens: 'list[str] | None' = None, subject_contains: 'str | None' = None) -> 'dict[str, Any]'` | Connect to ``host`` and fail unless it negotiates TLS 1.2 or 1.3 with a cipher that is not weak. |
| `WR_tls_cipher_audit_assert_report` | `(report: 'dict[str, Any]', banned_tokens: 'list[str] | None' = None, subject_contains: 'str | None' = None) -> 'dict[str, Any]'` | Fail unless a recorded handshake report shows TLS 1.2 or 1.3 and a cipher that is not weak. |
| `WR_tls_cipher_audit_handshake` | `(host: 'str', port: 'int' = 443, timeout: 'float' = 10.0) -> 'dict[str, Any]'` | Connect to ``host``:``port`` over TLS and return the negotiated version, cipher and certificate subject. |
| `WR_to_url` | `(url: 'str') -> 'None'` | 導航到指定 URL |
| `WR_token_leak_detector_assert_no_leaks` | `(text: 'str | None' = None, har: 'dict[str, Any] | str | None' = None, lines: 'list[str] | None' = None, minimum_severity: 'str' = 'low') -> 'list[dict[str, Any]]'` | Fail when text, a HAR or log lines hold a token or key at or above ``minimum_severity``. |
| `WR_token_leak_detector_scan_har` | `(har: 'dict[str, Any] | str', minimum_severity: 'str | None' = None) -> 'list[dict[str, Any]]'` | Scan the request and response bodies of a HAR (object or JSON text) for leaked tokens and keys. |
| `WR_token_leak_detector_scan_log` | `(lines: 'list[str] | None' = None, path: 'str | None' = None, minimum_severity: 'str | None' = None) -> 'list[dict[str, Any]]'` | Scan log lines, given as a list or as the path of a log file, for leaked tokens and keys. |
| `WR_token_leak_detector_scan_page` | `(minimum_severity: 'str | None' = None) -> 'list[dict[str, Any]]'` | Scan the HTML of the current page for leaked tokens and keys. |
| `WR_token_leak_detector_scan_text` | `(text: 'str', source: 'str' = 'text', location: 'str' = '', minimum_severity: 'str | None' = None) -> 'list[dict[str, Any]]'` | Scan text for leaked JWTs, cloud and API keys, bearer and session tokens. |
| `WR_tool_call_assert_called` | `(calls: 'list[dict[str, Any]]', name: 'str', times: 'int | None' = None, min_times: 'int | None' = None, max_times: 'int | None' = None) -> 'list[dict[str, Any]]'` | Fail unless the model called tool ``name`` the expected number of times; returns those calls. |
| `WR_tool_call_assert_not_called` | `(calls: 'list[dict[str, Any]]', denylist: 'list[str]') -> 'int'` | Fail when the model called any tool named in ``denylist``; returns how many calls were checked. |
| `WR_tool_call_assert_order` | `(calls: 'list[dict[str, Any]]', expected: 'list[str]') -> 'list[str]'` | Fail unless the tools were called exactly in the ``expected`` order of names. |
| `WR_tool_call_assert_schema` | `(calls: 'list[dict[str, Any]]', name: 'str', schema: 'dict[str, Any]') -> 'int'` | Fail unless tool ``name`` was called and every such call's arguments match the JSON Schema. |
| `WR_topological_order` | `(graph: 'dict[str, list[str]]') -> 'list[str]'` | Kahn 演算法拓樸排序；偵測環時拋例外 |
| `WR_touch_gesture_assert_received` | `(events: 'list[dict[str, Any]]', event_type: 'str' = 'touchstart', two_finger: 'bool' = False) -> 'int'` | Fail unless the page recorded a touch event of ``event_type`` (and, with ``two_finger``, a two-finger one). |
| `WR_touch_gesture_dispatch` | `(frames: 'list[dict[str, Any]]') -> 'int'` | Send touch frames built by the ``WR_touch_gesture_*`` commands to the current page (Chromium). |
| `WR_touch_gesture_pinch` | `(center_x: 'float', center_y: 'float', start_radius: 'float', end_radius: 'float', steps: 'int' = 8) -> 'list[dict[str, Any]]'` | Build the touch frames of a two-finger pinch around a point (spread when ``end_radius`` is larger). |
| `WR_touch_gesture_swipe` | `(start_x: 'float', start_y: 'float', end_x: 'float', end_y: 'float', steps: 'int' = 8) -> 'dict[str, Any]'` | Build the touch frames of a one-finger swipe. |
| `WR_touch_gesture_tap` | `(point_x: 'float', point_y: 'float', hold_ms: 'int' = 0) -> 'list[dict[str, Any]]'` | Build the touch frames of a tap, or of a long press when ``hold_ms`` is 500 or more. |
| `WR_trend_dashboard_compute` | `(ledger_path: 'str | None' = None, runs: 'list[dict[str, Any]] | None' = None) -> 'Any'` | Compute pass rate and average duration per day from recorded runs. |
| `WR_trend_dashboard_write` | `(output_path: 'str', ledger_path: 'str | None' = None, runs: 'list[dict[str, Any]] | None' = None, title: 'str' = 'WebRunner trend') -> 'str'` | Write the pass-rate trend of recorded runs as an HTML page; returns the file path. |
| `WR_try` | `(do: 'list', on_error: 'list | None' = None, always: 'list | None' = None) -> 'dict'` | 執行 ``do``；失敗時執行 ``on_error``，最後一定執行 ``always`` |
| `WR_unblock_urls` | `() -> 'None'` | 清空 ``block_urls`` 列表。 |
| `WR_unset_var` | `(name: 'str') -> 'bool'` | 移除變數 |
| `WR_update_snapshot` | `(name: 'str', value: 'str', snapshot_dir: 'str' = 'snapshots') -> 'str'` | 強制覆蓋基準 |
| `WR_upload_file` | `(input_selector: 'str', file_path: 'str') -> 'None'` | 對 ``<input type="file">`` 送入檔案路徑（Selenium） |
| `WR_use_row` | `(row: 'dict[str, Any]', index: 'int' = 0, local: 'bool' = False) -> 'dict'` | 把資料列設為目前的 ``${ROW}`` |
| `WR_user_factory` | `(prefix: 'str' = 'user') -> 'Factory'` | Default user shape: id / name / email / password. |
| `WR_validate_action_file` | `(json_file_path: 'str') -> 'bool'` | 讀取並驗證動作 JSON 檔案 |
| `WR_validate_action_json` | `(data: 'list | dict') -> 'bool'` | 驗證動作 JSON 是否符合執行器格式 |
| `WR_view_transitions_assert` | `(log: 'list[dict[str, Any]]', max_duration_ms: 'float | None' = None, max_cls: 'float' = 0.1, max_single_shift: 'float' = 0.05, group: 'str | None' = None) -> 'list[dict[str, Any]]'` | Fail when a recorded view transition did not finish, ran longer than ``max_duration_ms``, shifted the |
| `WR_view_transitions_harvest` | `() -> 'list[dict[str, Any]]'` | Read the raw log of the view transitions the current page recorded. |
| `WR_view_transitions_install` | `() -> 'bool'` | Start recording every ``document.startViewTransition`` call of the current page. |
| `WR_viewport_audit_assert_meta` | `(html: 'str', notch_aware: 'bool' = False) -> 'str'` | Fail when an HTML document has no viewport meta tag, a fixed width or disabled pinch-zoom. |
| `WR_viewport_audit_assert_safe_area` | `(payload: 'dict[str, Any]') -> 'bool'` | Fail when the body has no padding on any side, so a notch would cover the content. |
| `WR_viewport_audit_check` | `(html: 'str', notch_aware: 'bool' = False) -> 'dict[str, Any]'` | Report what is wrong with the ``<meta name="viewport">`` of an HTML document. |
| `WR_viewport_audit_check_page` | `(notch_aware: 'bool' = False) -> 'dict[str, Any]'` | Report what is wrong with the viewport meta tag of the current page. |
| `WR_viewport_audit_safe_area_page` | `() -> 'dict[str, Any]'` | Read the four computed paddings of the current page's ``<body>`` (for the safe-area check). |
| `WR_virtual_keyboard_assert_focused_visible` | `(after: 'dict[str, Any]', focused: 'dict[str, Any]') -> 'bool'` | Fail when the focused element sits behind the on-screen keyboard. |
| `WR_virtual_keyboard_assert_inset_set` | `(snapshot: 'dict[str, Any]') -> 'str'` | Fail when the page did not mirror the keyboard height into ``--keyboard-inset-height``. |
| `WR_virtual_keyboard_assert_shrunk` | `(before: 'dict[str, Any]', after: 'dict[str, Any]', min_height_delta_px: 'float' = 100) -> 'float'` | Fail unless the visual viewport became at least ``min_height_delta_px`` shorter when the keyboard showed. |
| `WR_virtual_keyboard_snapshot_page` | `() -> 'dict[str, Any]'` | Read the visual viewport of the current page; take one before and one after the keyboard shows. |
| `WR_visual_ai_assert_page_similar` | `(baseline_path: 'str', threshold: 'float' = 0.9, crop_box: 'list[int] | None' = None, mask_boxes: 'list[list[int]] | None' = None) -> 'dict[str, Any]'` | Fail when a screenshot of the current page looks less like the baseline image than ``threshold``. |
| `WR_visual_ai_assert_similar` | `(baseline_path: 'str', candidate_path: 'str', threshold: 'float' = 0.9, crop_box: 'list[int] | None' = None, mask_boxes: 'list[list[int]] | None' = None) -> 'dict[str, Any]'` | Fail when two image files look less alike than ``threshold`` (arguments as ``WR_visual_ai_compare``). |
| `WR_visual_ai_compare` | `(baseline_path: 'str', candidate_path: 'str', threshold: 'float' = 0.9, crop_box: 'list[int] | None' = None, mask_boxes: 'list[list[int]] | None' = None) -> 'dict[str, Any]'` | Score how alike two image files look (three perceptual hashes and a structural score, 0-1). |
| `WR_visual_ai_hash` | `(image_path: 'str', kind: 'str' = 'dhash', crop_box: 'list[int] | None' = None, mask_boxes: 'list[list[int]] | None' = None) -> 'dict[str, str]'` | Compute a perceptual hash of an image file. |
| `WR_visual_capture_baseline` | `(baseline_path: 'str', screenshot: 'Callable[[], bytes | None]' = <function _selenium_png at 0x000001540EA1D9E0>) -> 'str'` | 擷取當前頁面並儲存為基準圖 |
| `WR_visual_compare` | `(baseline_path: 'str', diff_path: 'str | None' = None, current_path: 'str | None' = None, threshold: 'int' = 0, screenshot: 'Callable[[], bytes | None]' = <function _selenium_png at 0x000001540EA1D9E0>) -> 'dict'` | 擷取目前頁面並與基準圖比較 |
| `WR_visual_review_accept` | `(baseline_dir: 'str', current_dir: 'str', name: 'str') -> 'str'` | Accept a changed screenshot: copy ``current_dir/name`` over the baseline; returns the baseline path. |
| `WR_visual_review_assert_no_diffs` | `(baseline_dir: 'str', current_dir: 'str') -> 'int'` | Fail when a screenshot differs from, or is missing on either side of, its baseline; returns the count. |
| `WR_visual_review_list` | `(baseline_dir: 'str', current_dir: 'str') -> 'list[dict[str, str]]'` | Pair the PNG files of a baseline and a current directory by name and say how each pair stands. |
| `WR_wait_for_download` | `(directory: 'str', timeout: 'float' = 60.0, suffix: 'str | None' = None, poll_seconds: 'float' = 0.5) -> 'str'` | 等待 ``directory`` 內出現新檔案（會跳過 ``.crdownload`` / ``.part``） |
| `WR_wait_for_element` | `(selector: 'str', by: 'str' = 'css selector', timeout: 'float' = 10.0, state: 'str' = 'visible') -> 'Any'` | 等元素出現（``present`` / ``visible`` / ``clickable``）或消失（``hidden``） |
| `WR_wait_for_ready_state` | `(timeout: 'float' = 30.0) -> 'bool'` | Wait until ``document.readyState`` is ``complete``. |
| `WR_wait_for_title` | `(pattern: 'str', timeout: 'float' = 10.0) -> 'bool'` | Wait until the page title contains ``pattern``. |
| `WR_wait_for_url` | `(pattern: 'str', timeout: 'float' = 10.0) -> 'bool'` | Wait until the current URL contains ``pattern``. |
| `WR_wake_lock_assert_check` | `(events: 'list[dict[str, Any]]', released_by_app: 'bool' = False, re_acquired: 'bool' = False) -> 'dict[str, Any]'` | Fail when the page never took a wake lock or never released one; returns the acquire and release counts. |
| `WR_wake_lock_assert_harvest` | `() -> 'list[dict[str, Any]]'` | Take the wake-lock events the current page recorded (this empties the page's list). |
| `WR_wake_lock_assert_install` | `() -> 'bool'` | Start recording the current page's ``navigator.wakeLock`` requests and releases. |
| `WR_walkthrough_docs_collect_steps` | `(actions: 'list[Any]', screenshots: 'dict[str, str] | None' = None, skip_noise: 'bool' = True) -> 'list[dict[str, Any]]'` | List the steps of an action list worth documenting (waits, setup and teardown are skipped). |
| `WR_walkthrough_docs_render` | `(walkthrough: 'dict[str, Any]', fmt: 'str' = 'markdown', embed_images: 'bool' = True) -> 'str'` | Render a step-by-step document from an action list, as ``markdown`` or ``confluence`` storage XHTML. |
| `WR_walkthrough_docs_save` | `(walkthrough: 'dict[str, Any]', output_path: 'str', fmt: 'str' = 'markdown') -> 'str'` | Write the document ``WR_walkthrough_docs_render`` produces to ``output_path``; returns the path. |
| `WR_watch_mode_diff` | `(previous: 'dict[str, Any]', current: 'dict[str, Any]') -> 'dict[str, Any]'` | Compare two ``WR_watch_mode_snapshot`` results. |
| `WR_watch_mode_snapshot` | `(directory: 'str', glob: 'str' = '**/*.json') -> 'dict[str, list[Any]]'` | Record the modification time and size of every file matching ``glob`` under a directory. |
| `WR_wcag22_touch_target_assert` | `(targets: 'list[dict[str, Any]]') -> 'int'` | Fail when a harvested interactive element breaks the WCAG 2.2 minimum target size. |
| `WR_wcag22_touch_target_audit` | `(targets: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | List the interactive elements smaller than 24x24 CSS pixels that no WCAG 2.2 (2.5.8) exception covers. |
| `WR_wcag22_touch_target_audit_page` | `() -> 'list[dict[str, Any]]'` | List the too-small interactive elements (WCAG 2.2, 2.5.8) of the current page. |
| `WR_web_locks_assert` | `(log: 'list[dict[str, Any]]', name: 'str | None' = None, expected_acquired: 'int | None' = None, if_available_refused: 'bool' = False) -> 'list[dict[str, Any]]'` | Fail when a recorded lock was never released, or the lock ``name`` was held twice at once, was not |
| `WR_web_locks_harvest` | `() -> 'list[dict[str, Any]]'` | Read the raw Web Locks log the current page recorded. |
| `WR_web_locks_install` | `() -> 'bool'` | Start recording the current page's ``navigator.locks.request`` calls. |
| `WR_web_push_assert_check` | `(log: 'dict[str, Any]', vapid_public_key: 'str' = '', require_notification: 'bool' = False, body_contains: 'str' = '') -> 'dict[str, Any]'` | Fail when a push subscription is not user-visible-only, used another key than ``vapid_public_key``, or |
| `WR_web_push_assert_harvest` | `() -> 'dict[str, Any]'` | Take the push subscriptions and notifications the current page recorded (this empties its lists). |
| `WR_web_push_assert_install` | `() -> 'bool'` | Start recording the current page's push subscriptions and the notifications it shows. |
| `WR_web_share_assert_check` | `(log: 'dict[str, Any]', expected_origin: 'str' = '', field: 'str' = '', fallback: 'bool' = False) -> 'dict[str, Any]'` | Fail when the page never shared (with ``fallback``: never showed its fallback UI), shared a URL of |
| `WR_web_share_assert_harvest` | `() -> 'dict[str, Any]'` | Take the share calls and fallback marks the current page recorded (this empties its lists). |
| `WR_web_share_assert_install` | `(reject: 'bool' = False, can_share: 'bool' = True, can_share_files: 'bool' = True) -> 'bool'` | Replace the current page's ``navigator.share`` with a recorder; ``reject`` makes every share fail as if |
| `WR_webauthn_add_credential` | `(authenticator_id: 'str', credential: 'dict[str, Any]') -> 'bool'` | Put a credential into a virtual authenticator. |
| `WR_webauthn_enable` | `(protocol: 'str' = 'ctap2', transport: 'str' = 'internal', has_resident_key: 'bool' = True, has_user_verification: 'bool' = True, is_user_verified: 'bool' = True) -> 'dict[str, Any]'` | Add a virtual passkey authenticator to the running browser (Chromium), so sign-in needs no hardware. |
| `WR_webauthn_list_credentials` | `(authenticator_id: 'str') -> 'list[dict[str, Any]]'` | List the credentials a virtual authenticator holds (the page's registrations included). |
| `WR_webauthn_mock_assert` | `(log: 'dict[str, Any]', registered: 'bool' = True, signed_in: 'bool' = False, user_verification: 'str | None' = None) -> 'dict[str, int]'` | Fail when the page did not start a registration (``registered``) or a sign-in (``signed_in``), or a |
| `WR_webauthn_mock_build_credential` | `(user_handle: 'str', rp_id: 'str', sign_count: 'int' = 0) -> 'dict[str, Any]'` | Make a passkey record for a test user of the site ``rp_id``, as ``WR_webauthn_mock_install`` takes. |
| `WR_webauthn_mock_harvest` | `() -> 'dict[str, Any]'` | Take the registration and sign-in ceremonies the current page started (this empties its lists). |
| `WR_webauthn_mock_install` | `(credentials: 'list[dict[str, Any]]') -> 'int'` | Replace the current page's ``navigator.credentials`` with an authenticator that answers with these |
| `WR_webauthn_remove` | `(authenticator_id: 'str') -> 'bool'` | Remove a virtual authenticator from the running browser. |
| `WR_webcodecs_assert_check` | `(chunks: 'list[dict[str, Any]]', codec: 'str | None' = None, resolution: 'list[int] | None' = None, max_keyframe_gap: 'int | None' = None, min_fps: 'float | None' = None) -> 'dict[str, Any]'` | Fail when encoded chunks miss the expected codec, ``resolution`` ([width, height]), key-frame spacing or |
| `WR_webcodecs_assert_harvest` | `(kind: 'str' = 'video') -> 'list[dict[str, Any]]'` | Take the encoded ``video`` or ``audio`` chunks the current page recorded (this empties that list). |
| `WR_webcodecs_assert_install` | `() -> 'bool'` | Add ``window.__wr_codec__`` to the current page; the page's encoder output callback has to call |
| `WR_webgpu_pixel_verify_assert` | `(frame: 'dict[str, Any]', channel: 'str | None' = None, min_value: 'float' = 0.0, max_value: 'float' = 255.0, allow_solid_color: 'bool' = False) -> 'dict[str, Any]'` | Fail when a captured frame is fully transparent, one solid colour (unless ``allow_solid_color``), or |
| `WR_webgpu_pixel_verify_assert_similar` | `(frame: 'dict[str, Any]', reference: 'dict[str, Any]', max_diff: 'float' = 0.05) -> 'float'` | Fail when a captured frame differs from a reference frame by more than ``max_diff`` (0 to 1). |
| `WR_webgpu_pixel_verify_capture` | `(selector: 'str') -> 'dict[str, Any]'` | Read the pixels of the WebGPU ``<canvas>`` matching a CSS selector in the current page, as the frame |
| `WR_webhid_mock_assert_output` | `(reports: 'list[dict[str, Any]]', expected_count: 'int | None' = None, contains: 'list[int] | None' = None) -> 'list[dict[str, Any]]'` | Fail when the page did not send ``expected_count`` output reports, or none contains the byte sequence |
| `WR_webhid_mock_harvest` | `() -> 'list[dict[str, Any]]'` | Take the output reports the current page sent to the fake HID devices (this empties the list). |
| `WR_webhid_mock_install` | `(devices: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Replace the current page's ``navigator.hid`` with fake devices; returns them. |
| `WR_webhid_mock_push_report` | `(report_id: 'int', data: 'list[int]', device_index: 'int' = 0) -> 'bool'` | Send an input report (byte values 0-255) from a fake HID device to the current page; False when the |
| `WR_webhook_receiver_assert_header` | `(header: 'str', value: 'str') -> 'dict[str, Any]'` | Fail when no received webhook request has ``header`` equal to ``value``; returns the first that does. |
| `WR_webhook_receiver_assert_json` | `(contains: 'dict[str, Any]') -> 'dict[str, Any]'` | Fail when no received webhook request has a JSON object body with every field of ``contains``; returns |
| `WR_webhook_receiver_assert_path` | `(path: 'str', method: 'str | None' = None, minimum: 'int' = 1) -> 'int'` | Fail when fewer than ``minimum`` webhook requests hit ``path``; returns how many did. |
| `WR_webhook_receiver_clear` | `() -> 'int'` | Forget the webhook requests received so far; returns how many were dropped. |
| `WR_webhook_receiver_received` | `(path: 'str | None' = None, method: 'str | None' = None) -> 'list[dict[str, Any]]'` | List the webhook requests received so far, optionally only those to ``path`` with ``method``. |
| `WR_webhook_receiver_start` | `(port: 'int | None' = None) -> 'dict[str, Any]'` | Start a local server on 127.0.0.1 that records the webhooks the application under test sends. |
| `WR_webhook_receiver_stop` | `() -> 'list[dict[str, Any]]'` | Stop the webhook receiver; returns the requests it received. |
| `WR_webhook_receiver_wait` | `(path: 'str', method: 'str | None' = None, timeout: 'float' = 5.0) -> 'dict[str, Any]'` | Wait up to ``timeout`` seconds for a webhook request to ``path`` and return it; fail when none arrives. |
| `WR_webhook_signature_verify_assert_valid` | `(scheme: 'str', headers: 'dict[str, str]', body: 'str', secret: 'str', tolerance_seconds: 'int' = 300) -> 'dict[str, Any]'` | Fail unless a captured webhook's signature matches its body and the shared secret. |
| `WR_webhook_signature_verify_check` | `(scheme: 'str', headers: 'dict[str, str]', body: 'str', secret: 'str', tolerance_seconds: 'int' = 300) -> 'dict[str, Any]'` | Say whether a captured webhook's signature matches its body and the shared secret. |
| `WR_webhook_signature_verify_sign` | `(scheme: 'str', body: 'str', secret: 'str', timestamp: 'int | None' = None) -> 'dict[str, str]'` | Return the signature headers a ``github``, ``stripe`` or ``slack`` webhook with this body would carry. |
| `WR_webrtc_assert_connected` | `(snapshot: 'dict[str, Any]', track_kind: 'str | None' = None, track_side: 'str' = 'remote', codec: 'str | None' = None, codec_side: 'str' = 'local') -> 'dict[str, Any]'` | Fail when an ``RTCPeerConnection`` snapshot is not connected, has no live ``track_kind`` (audio, video) |
| `WR_webrtc_assert_stats` | `(stats_report: 'list[dict[str, Any]]', direction: 'str | None' = None, max_loss_ratio: 'float' = 0.01, kind: 'str | None' = None, min_bytes: 'int | None' = None) -> 'list[dict[str, Any]]'` | Fail when a ``getStats()`` report shows more packet loss than ``max_loss_ratio`` (0 to 1), or fewer than |
| `WR_webserial_mock_assert_lines` | `(chunks: 'list[list[int]]', expected: 'list[str]', newline: 'str' = '\n') -> 'bool'` | Fail when the lines the page wrote to the serial port (lists of byte values) are not ``expected``. |
| `WR_webserial_mock_harvest` | `() -> 'list[list[int]]'` | Take the byte chunks the current page wrote to the fake serial port (this empties the list). |
| `WR_webserial_mock_install` | `(vendor_id: 'int | None' = None, product_id: 'int | None' = None) -> 'dict[str, Any]'` | Replace the current page's ``navigator.serial`` with one fake serial port; returns the port's ids. |
| `WR_webserial_mock_push_lines` | `(lines: 'list[str]', newline: 'str' = '\n') -> 'bool'` | Make the fake serial port deliver text lines to the current page; False when it is not installed. |
| `WR_websocket_assert_frame_count` | `(minimum: 'int' = 1, maximum: 'int | None' = None, direction: 'str | None' = None, url_match: 'str | None' = None) -> 'int'` | Fail when the number of recorded WebSocket frames is outside ``minimum``..``maximum``; returns it. |
| `WR_websocket_assert_frames` | `(direction: 'str | None' = None, url_match: 'str | None' = None) -> 'list[dict[str, Any]]'` | List the recorded WebSocket frames, optionally one direction or URLs matching a regular expression. |
| `WR_websocket_assert_json_shape` | `(required_keys: 'list[str]', direction: 'str | None' = 'received') -> 'dict[str, Any]'` | Fail when no recorded WebSocket frame is a JSON object with all of ``required_keys``. |
| `WR_websocket_assert_payload_contains` | `(needle: 'str', direction: 'str | None' = None) -> 'dict[str, Any]'` | Fail when no recorded WebSocket frame's text contains ``needle``; returns the first that does. |
| `WR_websocket_assert_pubsub` | `(subscribe_contains: 'str', publish_contains: 'str') -> 'bool'` | Fail unless a sent frame containing ``subscribe_contains`` came before the first received frame |
| `WR_websocket_assert_record` | `(frames: 'list[dict[str, Any]]') -> 'int'` | Add WebSocket frames to the recorder; returns how many it now holds. |
| `WR_websocket_assert_reset` | `() -> 'bool'` | Forget every recorded WebSocket frame. |
| `WR_webtransport_assert_datagram_count` | `(minimum: 'int' = 1, maximum: 'int | None' = None, direction: 'str | None' = None) -> 'int'` | Fail when the number of recorded datagrams is outside ``minimum``..``maximum``; returns it. |
| `WR_webtransport_assert_frames` | `(direction: 'str | None' = None, channel: 'str | None' = None, stream_id: 'int | None' = None) -> 'list[dict[str, Any]]'` | List the recorded WebTransport frames, optionally only one direction, channel or stream. |
| `WR_webtransport_assert_payload_contains` | `(needle: 'str', direction: 'str | None' = None, channel: 'str | None' = None) -> 'dict[str, Any]'` | Fail when no recorded WebTransport frame contains the text ``needle``; returns the first that does. |
| `WR_webtransport_assert_record` | `(frames: 'list[dict[str, Any]]') -> 'int'` | Add WebTransport datagrams and stream chunks to the recorder; returns how many it now holds. |
| `WR_webtransport_assert_reset` | `() -> 'bool'` | Forget every recorded WebTransport frame. |
| `WR_webtransport_assert_stream_complete` | `(stream_id: 'int', direction: 'str' = 'received') -> 'str'` | Fail when a recorded stream has no chunks or did not end with FIN; returns the stream's text. |
| `WR_webusb_mock_assert_out` | `(calls: 'list[dict[str, Any]]', endpoint: 'int | None' = None, contains: 'list[int] | None' = None, request: 'int | None' = None) -> 'dict[str, Any]'` | Fail when the page made no ``transferOut`` on ``endpoint`` (holding the bytes ``contains``) or, with no |
| `WR_webusb_mock_harvest` | `() -> 'list[dict[str, Any]]'` | Take the OUT transfers the current page sent to the fake USB device (this empties the list). |
| `WR_webusb_mock_install` | `(devices: 'list[dict[str, Any]]') -> 'list[dict[str, Any]]'` | Replace the current page's ``navigator.usb`` with fake devices; returns them. |
| `WR_webusb_mock_queue_in` | `(data: 'list[int]', endpoint: 'int | None' = None) -> 'bool'` | Queue the bytes (0-255) the fake USB device answers to the page's next ``transferIn`` on ``endpoint``, |
| `WR_while` | `(condition: 'Any', do: 'list', max_iterations: 'Any') -> 'int'` | 條件成立時重複執行 ``do`` |
| `WR_workspace_lock_assert_current` | `(path: 'str', check_python_version: 'bool' = True) -> 'dict[str, Any]'` | Fail when this interpreter's packages differ from the Python packages a lock file pins. |
| `WR_workspace_lock_build` | `(drivers: 'list[dict[str, Any]] | None' = None, playwright_versions: 'dict[str, str] | None' = None, allow_distributions: 'list[str] | None' = None) -> 'dict[str, Any]'` | Describe this interpreter's installed packages plus the driver and Playwright versions given. |
| `WR_workspace_lock_diff` | `(before_path: 'str', after_path: 'str') -> 'dict[str, Any]'` | Compare two workspace lock files. |
| `WR_workspace_lock_write` | `(path: 'str', drivers: 'list[dict[str, Any]] | None' = None, playwright_versions: 'dict[str, str] | None' = None, allow_distributions: 'list[str] | None' = None) -> 'str'` | Write the lock of ``WR_workspace_lock_build`` to ``path`` as JSON; returns the path written. |
| `WR_write_pom_to_file` | `(source: 'str', output_path: 'str') -> 'str'` | Write generated source to ``output_path``; returns the path written. |
