命令列介面
==========

概述
----

WebRunner 可以直接從命令列使用 ``je_web_runner`` 模組執行。安裝套件時也會裝上
主控台指令 ``webrunner`` 與 ``web_runner``，旗標、輸出與結束碼都相同，所以
``webrunner -e actions.json`` 等於 ``python -m je_web_runner -e actions.json``
（也可以用 ``pipx run --spec je_web_runner webrunner``）。

指令
----

**執行單一 JSON 動作檔案：**

.. code-block:: bash

    python -m je_web_runner -e actions.json
    python -m je_web_runner --execute_file actions.json

**執行目錄中所有 JSON 檔案：**

.. code-block:: bash

    python -m je_web_runner -d ./actions/
    python -m je_web_runner --execute_dir ./actions/

**直接執行 JSON 動作字串：**

.. code-block:: bash

    python -m je_web_runner --execute_str '[["WR_get_webdriver_manager", {"webdriver_name": "chrome"}], ["WR_quit"]]'

指令參考
--------

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - 旗標
     - 簡寫
     - 說明
   * - ``--execute_file``
     - ``-e``
     - 執行單一 JSON 動作檔案
   * - ``--execute_dir``
     - ``-d``
     - 執行目錄中所有 JSON 檔案
   * - ``--execute_str``
     -
     - 直接執行 JSON 動作字串

.. note::

   在 Windows 上，``--execute_str`` 選項可能需要雙重 JSON 解析（因 shell 跳脫字元）。
   WebRunner 會自動處理此情況。

錯誤處理
--------

若未提供任何參數，WebRunner 會引發 ``WebRunnerExecuteException``。
所有錯誤會輸出到 stderr，程序以代碼 1 退出。

失敗的動作不會中止所在的清單：其餘動作會繼續執行，``-d`` 的其餘檔案也是。全部執行完之後，
只要有任何失敗，程序就以代碼 1 退出並印出 ``error: N action(s) or file(s) failed``，否則以 0 退出。

執行設定
--------

``--var NAME=VALUE`` 設定動作檔以 ``${NAME}`` 讀取的變數；可重複使用，``VALUE`` 能解析成
JSON 時就當作 JSON（``3``、``true``、``[1, 2]``），否則就是文字本身。``--env NAME`` 會在
執行前載入 ``.env.NAME``\ （位於 ``--env-dir``，預設為工作目錄），供 ``${ENV.KEY}`` 使用。

``--dataset FILE``\ （任意位置的 ``.csv`` 或 ``.json`` 檔）會讓每個沒有自己 ``meta.dataset``
的檔案對每一列執行一次，以 ``${ROW.column}`` 讀取該列。

``--fail-fast`` 會在檔案中第一個動作失敗後跳過其餘動作（``meta.teardown`` 照樣執行），
並且在 ``-d`` 執行中不再啟動第一個失敗檔案之後的檔案；沒執行的檔案數會印到 stderr。
在 thread 與 process 平行模式下，已經在跑的檔案會跑完，尚未啟動的則不再執行。
``--parallel-mode async`` 會執行每一個檔案。

宣告了 ``meta.depends_on`` 的檔案會依相依順序執行。``--parallel`` 大於 1（或
``--parallel-mode async``）時改為逐層執行：同一層的檔案只相依於前面各層的檔案，每一層
作為一批交給平行池。相依的檔案失敗時，該檔案會被跳過並算作失敗。

專案設定檔
----------

執行的預設值可以放在工作目錄的 ``webrunner.toml``，或 ``pyproject.toml`` 的
``[tool.webrunner]`` 表格裡。旗標優先於設定檔，設定檔優先於內建預設；沒有設定檔時行為完全
不變。``--config FILE`` 指定另一個檔案，``--no-config`` 則不讀取任何設定檔。

.. code-block:: toml

    # webrunner.toml (in pyproject.toml the same keys go under [tool.webrunner])
    env = "staging"                 # load .env.staging before the run
    fail_fast = true
    retries = 1
    retry_backoff = 0.5
    failure_screenshot_dir = "artifacts/failures"
    report = "reports/run"
    ledger = ".webrunner/ledger.json"
    parallel = 4
    parallel_mode = "process"
    exclude_tag = ["sub-flow"]

    [vars]
    base = "${ENV.BASE_URL}"
    user = "alice"

``vars`` 會成為變數（同名時 ``--var`` 優先）。``report``、``ledger``、``parallel``、
``parallel_mode``、``tag`` 與 ``exclude_tag`` 取代同名旗標的預設值。``env``、``env_dir``、
``fail_fast``、``retries``、``retry_backoff`` 與 ``failure_screenshot_dir`` 會在第一個動作
之前設定好執行器，``--parallel-mode process`` 的每個工作行程也一樣。未知的鍵或型別錯誤的值
會在任何動作執行之前拋出 ``ProjectConfigError``。沒有該表格、或無法解析的
``pyproject.toml`` 不算設定檔，會被忽略。

工具
----

這些旗標不執行動作檔，可以和其他旗標一起使用：

* ``--lint PATH`` 檢查一個動作檔，或目錄底下的每個 ``.json`` 檔，並印出
  ``path: severity [rule] location: message``。有 warning 時以 1 結束；info 不會。
* ``--list-commands`` 印出每個已註冊的 ``WR_*`` 指令，一行一個。
* ``--init DIR`` 把 ``utils/bootstrapper`` 的起始工作區寫進 ``DIR``；既有檔案會保留。
* ``--format PATH`` 把一個動作檔，或目錄底下的每個 ``.json`` 檔，改寫成標準排版，並印出
  有變動的檔案。加上 ``--format-check`` 時不寫入任何東西，有檔案會變動就以 1 結束。
* ``--export-schema FILE`` 寫出動作檔的 JSON schema；``--export-command-reference FILE``
  寫出所有 ``WR_*`` 指令的 Markdown 表格。兩者都反映這份安裝中已註冊的指令。

報告
----

``--report BASE`` 在執行結束後寫出 JSON、HTML、XML 與 JUnit 報告。報告由測試紀錄產生，
所以這個旗標會在執行前開啟紀錄，``--parallel-mode process`` 的工作行程也一樣；
動作檔不需要自己呼叫 ``WR_set_record_enable``。

``--report-format LIST`` 選擇要寫出哪些報告：``json``、``html``、``xml``、``junit``\ （沒有
這個旗標時就是這四種）、``allure``\ （結果檔寫在 ``BASE_allure/``）與 ``interactive``
（``BASE_interactive.html``）。

JUnit 報告中每個動作檔是一個 ``<testsuite>``，以檔案命名。步驟的 ``time`` 是距離同一檔案
前一個步驟的時間，suite 的 ``time`` 是最後一步減第一步，兩者都取自紀錄的時間戳。在任何檔案
之外記錄的步驟（``--execute_str``）歸在名為 ``webrunner``、時間為 0 的 suite。

``--merge-reports OUT BASE [BASE ...]`` 把指定基底名稱（例如每個 ``--shard`` 一個）的
``_success.json``、``_failure.json`` 與 ``_junit.xml`` 合併成 ``OUT`` 底下同樣的三個檔案。
JSON 條目依輸入順序重新編號；重複的 JUnit suite 名稱會加上該輸入的名稱。

在 TestPioneer 之下執行
-----------------------

TestPioneer 啟動 runner 時會把 ``TEST_PIONEER_ARTIFACT_DIR`` 設為該次執行的輸出目錄。
以相對名稱要求的報告（JSON、XML、HTML、JUnit、Allure、互動式 HTML，以及 ``generate_all_reports``）
會寫到該目錄底下，所需的資料夾會自動建立。絕對路徑，以及會離開該目錄的名稱，則照原樣使用。
沒有設定這個變數時，行為不變。

本機 Agent 任務
---------------

``--agent-task task.json --report results/task`` 執行可驗證的本機任務。
詳見 :doc:`../integrations/local_agent_doc`。
