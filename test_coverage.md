# 測試覆蓋度：WebRunner

測量日期：2026-10-28。數字來自這台 Windows 機器上的一次實測，不是估計，也不是只數檔案。

| 項目 | 內容 |
|---|---|
| 直譯器 | 3.11.9 |
| 直譯器說明 | 專案 .venv |
| 工具 | coverage 7.15.0，`coverage run --branch` |
| 測量範圍 | `je_web_runner` |
| 測試路徑 | `test` |
| 命令 | `python -m coverage run --branch --source=je_web_runner -m pytest test` |
| 敘述覆蓋 | 90.05%（30307 / 33657） |
| 分支覆蓋 | 85.6%（8925 / 10426） |
| 測試結果 | 5174 passed, 28 skipped, 67 subtests passed in 495.01s (0:08:15) |
| 耗時 | 500.5 秒 |

敘述覆蓋是執行到的敘述數除以全部敘述數。分支覆蓋是執行到的分支數除以全部分支數。兩者分開算，沒有把分支混進敘述百分比。

## 覆蓋較低的檔案

只列這次測量裡敘述覆蓋最低的檔案，最多 12 個。

| 檔案 | 敘述覆蓋 | 已覆蓋 / 敘述 |
|---|---:|---:|
| `je_web_runner/__main__.py` | 0.0% | 0 / 10 |
| `je_web_runner/action_lsp/__main__.py` | 0.0% | 0 / 8 |
| `je_web_runner/mcp_server/__main__.py` | 0.0% | 0 / 3 |
| `je_web_runner/webdriver/_wrapper_mixins/_actions_mixin.py` | 10.51% | 39 / 371 |
| `je_web_runner/element/web_element_wrapper.py` | 39.02% | 80 / 205 |
| `je_web_runner/webdriver/_wrapper_mixins/_navigation_mixin.py` | 41.35% | 110 / 266 |
| `je_web_runner/api/__init__.py` | 45.45% | 5 / 11 |
| `je_web_runner/utils/observability/otel_tracing.py` | 46.34% | 19 / 41 |
| `je_web_runner/webdriver/_wrapper_mixins/_cookie_mixin.py` | 46.67% | 42 / 90 |
| `je_web_runner/webdriver/webdriver_wrapper.py` | 48.54% | 116 / 239 |
| `je_web_runner/utils/issue_worker/sandbox.py` | 51.06% | 48 / 94 |
| `je_web_runner/utils/process_supervisor/supervisor.py` | 57.14% | 60 / 105 |
