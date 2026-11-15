==========
品質與安全
==========

* Action linter：除了舊命令名、寫死 URL、危險腳本、缺少標籤、連續重複動作之外，也會警告
  未註冊的命令（``unknown_command``）、命令不接受的關鍵字、漏填的必要參數或過多的位置參數
  （``unknown_argument``、``missing_argument``、``too_many_arguments``；依命令本身的簽章判斷，
  接受 ``**kwargs`` 的命令可帶任何關鍵字）、不是動作清單的區塊參數（``block_shape``）與沒有
  ``max_iterations`` 的 ``WR_while``\ （``while_without_limit``），並以資訊等級列出檔案內
  沒有任何動作設定的 ``${name}``\ （``undefined_variable``；呼叫端的 ``params`` 仍可能設定它）。
  區塊內與 ``meta.setup`` / ``meta.teardown`` 的動作和頂層動作一樣會被檢查；``--validate`` 與
  ``WR_validate_action_json`` 也會檢查這些巢狀動作的形狀。
* Migration helper（舊命令 → 新別名）
* 寫死密碼掃描
* HTTP 安全 headers 稽核
* axe-core 可訪問性
* Lighthouse 跑分
* Core Web Vitals 預算（``WR_assert_web_vitals``：一步斷言 LCP / CLS / INP / FCP，量目前頁面或對 URL
  跑 Lighthouse；預設為 Google 的 good 上限，超出時寫出評等與診斷，``json_path`` / ``html_path``
  寫出明細）
* Visual regression
* 文字 / DOM snapshot
* 網路節流預設集
* Arbitrary-script 開關

安全測試
========

* ``header_tampering.HeaderTampering`` — 改 cookie/referer/origin
* ``license_scanner`` — SPDX / 已知授權字樣偵測
* ``cookie_consent.ConsentDismisser`` — 自動關閉 GDPR 彈窗

PII / Visual review
===================

* ``pii_scanner.scan_text`` — email / 電話 / Luhn 驗證信用卡 / SSN /
  ROC 身分證號 / IPv4，``assert_no_pii`` 與 ``redact_text`` 配套
* ``visual_review.VisualReviewServer`` — 本機 web UI side-by-side 顯示
  baseline / current，一鍵 accept

Form auto-fill / A11y diff
==========================

* ``form_autofill.plan_fill_actions(fields, fixture)`` — 自動推斷欄位
  用途並產出 ``WR_save_test_object`` + ``WR_element_input`` 序列
* ``accessibility.a11y_diff.diff_violations`` — 比較兩次 axe-core 結果
  分出 added / resolved / persisting；``assert_no_regressions`` 為
  CI 把關
