動作執行器
==========

概述
----

動作執行器是一個強大的引擎，將指令字串對應到可呼叫的函式。
它允許您將自動化腳本定義為 JSON 動作列表，實現資料驅動的自動化工作流程。

執行器還註冊了一份 Python 內建函式允許清單（``SAFE_BUILTINS``：``print``、``len``、``sorted``、``sum`` …），因此可以在動作列表中呼叫它們；``eval``、``exec``、``open`` 這類函式不會註冊。

動作格式
--------

每個動作是一個包含指令名稱和可選參數的列表：

.. code-block:: python

    ["command_name"]                        # 無參數
    ["command_name", {"key": "value"}]      # 關鍵字參數
    ["command_name", [arg1, arg2]]          # 位置參數

基本用法
--------

.. code-block:: python

    from je_web_runner import execute_action

    actions = [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://www.google.com"}],
        ["WR_implicitly_wait", {"time_to_wait": 2}],
        ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
        ["WR_find_element", {"element_name": "q"}],
        ["WR_click_element"],
        ["WR_input_to_element", {"input_value": "WebRunner"}],
        ["WR_quit"]
    ]

    result = execute_action(actions)

``execute_action()`` 回傳一個字典，將每個動作（``"execute: <action>"``）對應到其回傳值。
完全相同的動作重複出現時，鍵會加上 ``#2``、``#3``……，每個步驟的結果都會保留。

失敗的動作會記在這個字典裡，然後繼續執行下一個。若要執行單一動作並拿回它的值，
改用 ``execute_one``：它經過同樣的命令閘門、重試策略與失敗截圖，不印出任何東西，
動作失敗時拋出 ``WebRunnerExecuteException``\ （原本的錯誤是它的 ``__cause__``）：

.. code-block:: python

    from je_web_runner import execute_one

    url = execute_one(["WR_get_current_url"])

Selenium wrapper 呼叫失敗時（``WR_to_url``、``WR_element_click``、
``WR_element_assert``……）會被記錄，然後讓動作失敗，與 Playwright 命令相同。
``executor.set_raise_wrapper_errors(False)``\ （或在動作檔第一步放
``WR_set_raise_wrapper_errors`` 並帶 ``[false]``）會讓它再次通過，也就是預設
改變之前的行為。

可用指令
--------

完整的指令列表請參閱英文文件的 Action Executor 頁面。

主要指令分類：

* **WebDriver 管理**：``WR_get_webdriver_manager``, ``WR_change_index_of_webdriver``, ``WR_quit``
* **導航**：``WR_to_url``, ``WR_forward``, ``WR_back``, ``WR_refresh``
* **元素尋找**：``WR_find_element``, ``WR_find_elements``
* **等待**：``WR_implicitly_wait``, ``WR_explict_wait``, ``WR_set_script_timeout``, ``WR_set_page_load_timeout``
* **滑鼠**：``WR_left_click``, ``WR_right_click``, ``WR_left_double_click``, ``WR_drag_and_drop``
* **鍵盤**：``WR_press_key``, ``WR_release_key``, ``WR_send_keys``, ``WR_send_keys_to_element``
* **Cookie**：``WR_get_cookies``, ``WR_add_cookie``, ``WR_delete_cookie``, ``WR_delete_all_cookies``
* **JavaScript**：``WR_execute``, ``WR_execute_script``, ``WR_execute_async_script``
* **視窗**：``WR_maximize_window``, ``WR_minimize_window``, ``WR_set_window_size``
* **截圖**：``WR_get_screenshot_as_png``, ``WR_get_screenshot_as_base64``
* **元素操作**：``WR_click_element``, ``WR_input_to_element``, ``WR_element_clear``, ``WR_element_submit``
* **測試物件**：``WR_SaveTestObject``, ``WR_CleanTestObject``
* **報告**：``WR_generate_html_report``, ``WR_generate_json_report``, ``WR_generate_xml_report``
* **套件**：``WR_add_package_to_executor``, ``WR_add_package_to_callback_executor``

從 JSON 檔案執行
-----------------

.. code-block:: python

    from je_web_runner import execute_files

    results = execute_files(["actions1.json", "actions2.json"])

新增自訂指令
------------

.. code-block:: python

    from je_web_runner import add_command_to_executor

    def my_custom_function(param1, param2):
        print(f"自訂: {param1}, {param2}")

    add_command_to_executor({"my_command": my_custom_function})

    # 在動作列表中使用
    execute_action([
        ["my_command", {"param1": "hello", "param2": "world"}]
    ])

.. note::

   僅接受 ``types.MethodType`` 和 ``types.FunctionType``。
   傳入其他可呼叫類型會引發 ``WebRunnerAddCommandException``。

變數
----

動作可以存下一個值，讓後面的動作使用。執行器會在呼叫指令之前，把動作參數裡的
``${name}`` 換成實際的值。

.. code-block:: python

    [
        ["WR_set_var", {"name": "base", "value": "${ENV.BASE_URL}"}],
        ["WR_to_url", {"url": "${base}/login"}],
        ["WR_capture", {"name": "title", "action": ["WR_get_title"]}],
        ["WR_assert_title", {"value": "${title}"}],
    ]

* ``WR_set_var``\ （``name``、``value``）存下一個值。``WR_capture``\ （``name``、
  ``action``）執行一個動作並存下它的回傳值；該動作失敗時 ``WR_capture`` 也失敗，
  變數維持原狀。``WR_get_var``\ （``name``、``default``）、``WR_unset_var``、
  ``WR_clear_vars`` 與 ``WR_list_vars``\ （只列名稱）用來讀取與移除。
* ``${name}`` 讀取變數，``${name.key.0}`` 讀取 dict 的鍵或 list 的索引，
  ``${ENV.KEY}`` 讀取環境變數。``ENV`` 與 ``ROW`` 不能當變數名稱。
* 參數剛好是一個佔位符時，會得到保留型別的值；佔位符在較長的字串裡時，值會以
  文字插入。
* 指向未知名稱的佔位符會原樣保留，所以資料集的 ``${ROW.col}`` 與腳本參數裡的
  JavaScript 樣板字面值照常運作。變數存在但路徑不存在時，該動作失敗。
* 指令名稱永遠不會被替換，所以變數無法選到被閘門拒絕的指令。動作的紀錄顯示的是
  原本寫的內容，不是展開後的值；Selenium wrapper 呼叫所記錄的則是展開後的值。
* ``WR_execute_action``、``WR_run_with_dataset`` 與 ``WR_capture`` 內含稍後才執行
  的動作：它們的佔位符會在每個內層動作執行時才展開。
* 變數屬於執行器（``executor.variables``，一個
  ``je_web_runner.utils.flow.VariableStore``），會一直保留到 ``WR_clear_vars``。
  以目錄執行時，後面的檔案看得到前面檔案的變數；``--parallel-mode process``
  讓每個工作行程各有一份。

流程控制
--------

區塊決定哪些動作會執行。區塊裡的動作就是一般的動作，所以區塊可以巢狀。

.. code-block:: python

    [
        ["WR_for_each", {"items": ["/", "/pricing", "/docs"], "var": "path", "do": [
            ["WR_to_url", {"url": "${base}${path}"}],
            ["WR_if", {
                "condition": {"succeeds": ["WR_wait_for_element", {"selector": "#cookie-banner", "timeout": 2}]},
                "then": [["WR_dismiss_cookie_consent"]],
            }],
        ]}],
        ["WR_try", {
            "do": [["WR_retry_block", {"retries": 2, "backoff": 1, "do": [
                ["WR_refresh"],
                ["WR_wait_for_title", {"pattern": "Dashboard", "timeout": 5}],
            ]}]],
            "on_error": [["WR_save_screenshot", {"file_path": "dashboard_never_loaded.png"}], ["WR_fail", {"message": "${error}"}]],
            "always": [["WR_quit_all"]],
        }],
    ]

* ``WR_if``\ （``condition``、``then``、``otherwise``）條件成立時執行 ``then``，
  不成立時執行 ``otherwise``。
* ``WR_for_each``\ （``items``、``do``、``var``、``index_var``）對清單（或存放清單的
  ``${name}``）的每個項目執行一次 ``do``。項目是變數 ``var``\ （預設 ``item``），
  從 0 起算的位置是 ``index_var``；兩者在迴圈結束時消失。
* ``WR_repeat``\ （``times``、``do``、``index_var``）把 ``do`` 執行固定次數。
* ``WR_while``\ （``condition``、``do``、``max_iterations``）條件成立時重複執行
  ``do``。``max_iterations`` 必填；執行這麼多輪後條件仍成立，迴圈就失敗。
* ``WR_try``\ （``do``、``on_error``、``always``）：有 ``on_error`` 時，``do`` 失敗會
  執行它，失敗訊息為 ``${error}``，該動作算通過；沒有時失敗仍是失敗。
  ``always`` 一定會執行。
* ``WR_retry_block``\ （``do``、``retries``、``backoff``）區塊內任一動作失敗時，整個
  區塊從頭重跑，最多再跑 ``retries`` 次。
* ``WR_fail``\ （``message``）直接失敗。``WR_assert_var``\ （``var``、``op``、
  ``value``）在變數不符合運算子時失敗。

條件是 JSON 物件，絕不是程式碼：

* ``{"var": "name.path", "op": "eq", "value": 1}`` 比較變數；``value`` 裡的佔位符
  會展開。運算子：``eq``、``ne``、``gt``、``ge``、``lt``、``le``、``contains``、
  ``in``、``startswith``、``endswith``、``exists``、``truthy``\ （預設）、``falsy``。
  未設定的變數對 ``exists`` 與 ``truthy`` 為假，對 ``falsy`` 為真，用於比較則是錯誤。
* ``{"succeeds": [action]}`` 執行一個動作，該動作沒有失敗時為真。
* ``{"all": [...]}``、``{"any": [...]}`` 與 ``{"not": ...}`` 組合條件；``all`` 與
  ``any`` 在第一個能決定結果的條件就停止。
* 單純的值（``true``、``"${flag}"``）展開後即為其本身。

第一個失敗的動作會中止所在的區塊，並讓持有該區塊的動作失敗，只記錄一次。每個巢狀動作
都要通過與頂層動作相同的閘門（被拒絕的指令、任意腳本閘門、MCP 政策）與重試策略，
佔位符在動作執行時才展開，所以迴圈每一輪看到的都是當輪的值。

呼叫另一個動作檔
----------------

``WR_call_file``\ （``path``、``params``）在原處執行另一個動作檔的動作，共用的流程
只要寫一次。

.. code-block:: python

    # flows/login.json
    [
        ["WR_to_url", {"url": "${base}/login"}],
        ["WR_find_element_by", {"selector": "#user"}],
        ["WR_element_input", {"input_value": "${user}"}],
    ]
    
    # flows/checkout.json
    [
        ["WR_call_file", {"path": "login.json", "params": {"base": "${ENV.BASE_URL}", "user": "alice"}}],
        ["WR_to_url", {"url": "${ENV.BASE_URL}/cart"}],
    ]

* ``params`` 會成為被呼叫檔案的變數，呼叫結束即消失。呼叫端的其他變數也看得到。
* 相對的 ``path`` 從發出呼叫的檔案所在目錄算起。``execute_files``、
  ``Executor.execute_file`` 與 CLI（``-e``、``-d``）會設定這個檔案；
  ``--execute_str``、``execute_action``、socket server、MCP 工具與
  ``--parallel-mode async`` 沒有檔案可依據，改用工作目錄。
* 被呼叫的檔案必須在工作目錄之下，或在這次執行起始檔案的目錄之下；``..`` 到不了
  其他地方。正在執行的檔案不能再被呼叫，呼叫最多巢狀 20 層。
* 第一個失敗的動作會中止被呼叫的檔案，並讓 ``WR_call_file`` 這個動作失敗。
  ``WR_execute_files`` 是較舊的指令：不接受參數、路徑從工作目錄算起，而且只記錄
  失敗、自己不會失敗。

檔案的 ``meta``
---------------

物件形式的文件把動作放在 ``webdriver_wrapper``，把這次執行的設定放在 ``meta``。
``tags`` 與 ``depends_on`` 由 CLI 的檔案選取讀取；其餘由執行器讀取。

.. code-block:: json

    {
      "meta": {
        "tags": ["checkout"],
        "vars": {"base": "${ENV.BASE_URL}", "user": "alice"},
        "setup": [["WR_new_driver", {"webdriver_name": "chrome"}]],
        "teardown": [["WR_quit_all"]],
        "retries": 1,
        "fail_fast": true
      },
      "webdriver_wrapper": [
        ["WR_call_file", {"path": "login.json", "params": {"user": "${user}"}}],
        ["WR_to_url", {"url": "${base}/cart"}]
      ]
    }

* ``setup``：在檔案本身的動作之前執行的動作。
* ``teardown``：在其後執行的動作；前面有動作失敗時、以及 fail-fast 之下也照樣執行。
* ``vars``：預設變數。同名變數尚未存在時才設定；值裡的佔位符會展開。由
  ``WR_call_file`` 執行的檔案裡，它們補上 ``params`` 沒給的名稱，並在呼叫結束時消失。
* ``skip``：文字形式的原因。檔案的動作、``setup`` 與 ``teardown`` 都不執行；改為記錄
  一個帶有 ``skipped: <原因>`` 的 ``WR_note`` 動作。只寫 ``true`` 而沒有原因是錯誤。
* ``retries``\ （0 到 100）與 ``retry_backoff``\ （秒）：這個檔案的動作所用的重試策略。
  結束後恢復原本的策略。
* ``fail_fast``：這個檔案用 ``true`` 或 ``false``，不論執行器的設定為何。

``meta`` 的鍵形狀不對時，會在任何動作執行之前拋出 ``FlowError``。

Fail-fast
---------

預設情況下，失敗的動作會被記錄，然後繼續執行下一個。``executor.set_fail_fast(True)``、
動作 ``["WR_set_fail_fast"]``\ （從下一份清單起生效）或 ``meta.fail_fast`` 可以改變這點：
清單中第一個動作失敗之後，其餘動作會被記錄為
``skipped: an earlier action of this list failed (fail-fast)`` 而不執行，``teardown``
的動作除外。被跳過的動作在 CLI 的結束狀態中算作失敗。

它作用於一份清單或一個檔案的動作。單次的 ``execute_one`` 呼叫永遠不會被跳過；從動作
內部執行的清單（``WR_execute_action``）屬於那個動作；自行處理失敗的 ``WR_try`` 區塊
不會觸發它。``--parallel-mode async`` 不使用它。
