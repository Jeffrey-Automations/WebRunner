"""
沒有忠實 Playwright 對應的 Selenium 命令
The Selenium commands that have no faithful Playwright translation, each with the reason an author reads
when a file that uses one is run on Playwright.

A Selenium command that is neither here nor in the translation table is refused as well, with a general
reason; this list is for the commands whose reason helps (what to write instead, or why nothing can).
"""
from __future__ import annotations

RECORDED_NAME = (
    "it acts on a recorded TestObject without making it the current element, and no Playwright command "
    "takes a recorded name that way")
_WINDOW = "Playwright controls the viewport, not the OS window (WR_set_window_size becomes the viewport size)"
_DIALOG = "Selenium answers the dialog that is open; Playwright needs WR_pw_set_dialog_policy before the " \
          "action that opens it"
_APPIUM = "Appium sessions are WebDriver sessions; Playwright has no mobile-app backend"
_HANDLE = "a window handle is Selenium's own id; Playwright counts pages (WR_pw_page_count) and switches " \
          "by index, URL or title"
_TAB_NAMES = "the WR_multi_tab_* commands keep tab names for Selenium window handles; Playwright switches " \
             "pages by index, URL or title"
_FETCH = "it drives Chromium's Fetch domain through Selenium, which would fight Playwright's own request " \
         "interception; mock responses with WR_route_mock, which translates"
_WEBAUTHN = "the virtual authenticator is set up through Selenium and returns WebRunner's own result; over " \
            "WR_pw_cdp the WebAuthn.* methods return the raw DevTools result, so a captured value differs"

CANNOT_TRANSLATE: dict[str, str] = {
    # sessions that are WebDriver's own
    "WR_start_remote_driver": "Selenium Grid speaks the WebDriver protocol, which Playwright does not",
    "WR_appium_start": _APPIUM,
    "WR_appium_quit": _APPIUM,
    "WR_set_webdriver_options_capability": "it sets a capability on Selenium's Options object; Playwright "
                                           "takes its settings as WR_pw_launch arguments",
    "WR_execute": "it sends a raw WebDriver command, a protocol Playwright does not speak",
    "WR_get_log": "it reads Selenium's driver logs; on Playwright console messages come from "
                  "WR_pw_event_capture_start and WR_pw_console_messages",
    "WR_chrome_options_with_extension":
        "it builds Selenium ChromeOptions; on Playwright an extension needs WR_pw_launch_persistent with "
        "extension_paths and a profile directory",
    # the OS window, window handles
    "WR_maximize_window": _WINDOW,
    "WR_minimize_window": _WINDOW,
    "WR_fullscreen_window": _WINDOW,
    "WR_set_window_position": _WINDOW,
    "WR_set_window_rect": _WINDOW,
    "WR_get_window_position": _WINDOW,
    "WR_get_window_rect": _WINDOW,
    "WR_get_window_handles": _HANDLE,
    "WR_get_current_window_handle": _HANDLE,
    "WR_multi_tab_register": _TAB_NAMES,
    "WR_multi_tab_open": _TAB_NAMES,
    "WR_multi_tab_switch": _TAB_NAMES,
    "WR_multi_tab_close": _TAB_NAMES,
    # dialogs
    "WR_alert_accept": _DIALOG,
    "WR_alert_dismiss": _DIALOG,
    "WR_alert_text": "Selenium reads the dialog that is open; Playwright has handled it by then "
                     "(WR_pw_last_dialog reads it afterwards)",
    # devices
    "WR_list_devices": "the device names differ: WebRunner's presets on Selenium, Playwright's descriptors there",
    "WR_clear_device_metrics": "WR_set_device_metrics becomes a Playwright viewport size, which has no "
                               "'clear'; set the size wanted with WR_set_device_metrics",
    # ActionChains on a recorded TestObject, or relative to where the pointer is
    "WR_move_to_element": f"{RECORDED_NAME}; use WR_find_recorded_element and then WR_element_hover",
    "WR_move_to_element_with_offset": RECORDED_NAME,
    "WR_drag_and_drop": "it drags one recorded TestObject onto another by name; WR_pw_drag_and_drop needs "
                        "the two selectors, which are known only when the file runs",
    "WR_drag_and_drop_offset": "it drags a recorded TestObject by name; WR_pw_drag_and_drop_offset needs the "
                               "selector, which is known only when the file runs",
    "WR_send_keys_to_element": f"{RECORDED_NAME}; use WR_find_recorded_element and then WR_element_input",
    "WR_move_by_offset": "it moves the pointer relative to where it is; WR_pw_mouse_move takes page "
                         "coordinates, and the pointer's position is known only when the file runs",
    # waits and timeouts
    "WR_implicitly_wait": "Playwright's element lookup does not wait; wait with WR_wait_for_element, which translates",
    "WR_explicit_wait": "its condition is a Python callable, which an action file cannot hold and Playwright "
                        "cannot run; wait with WR_wait_for_element or WR_wait_for_url, which translate",
    "WR_wait_for_title": "Playwright has no wait for the page title",
    "WR_set_script_timeout": "WR_pw_evaluate has no timeout",
    # cookies
    "WR_save_cookies": "the file differs: Selenium saves a cookie list, WR_pw_save_storage_state saves cookies "
                       "and localStorage, and nothing loads it into an open Playwright context",
    "WR_load_cookies": "Playwright loads saved state only when a context is created (the storage_state option)",
    # the current element
    "WR_element_get_attribute": "Selenium's get_attribute answers with the element's property when it has one "
                                "(the typed value, an absolute href); WR_pw_element_get_attribute reads the "
                                "HTML attribute only. WR_element_get_dom_attribute and WR_element_get_property "
                                "translate",
    "WR_element_get_select": "it returns Selenium's Select object; WR_element_select_by_value translates",
    "WR_element_select_by_index": "WR_pw_element_select_option takes a value only; an index needs "
                                  "WR_pw_select_option with a selector and index=",
    "WR_element_select_by_visible_text": "WR_pw_element_select_option takes a value only; a label needs "
                                         "WR_pw_select_option with a selector and label=",
    # downloads
    "WR_set_download_directory": "Playwright saves a download with WR_pw_download(selector, save_to), in one step",
    "WR_wait_for_download": "Playwright keeps a download in its own directory until WR_pw_download saves it",
    # what only Selenium's channels offer
    "WR_dom_mutations": "DOM mutation capture exists only on Selenium (BiDi)",
    "WR_bidi_backend_subscribe": "it subscribes to a Selenium BiDi event; on Playwright console messages come "
                                 "from WR_pw_event_capture_start and WR_pw_console_messages",
    "WR_cdp_tap_start": "it records the DevTools commands Selenium's driver is sent; Playwright's calls do "
                        "not pass through that driver",
    "WR_enable_fetch_interception": _FETCH,
    "WR_disable_fetch_interception": _FETCH,
    "WR_fetch_continue_request": _FETCH,
    "WR_fetch_fail_request": _FETCH,
    "WR_fetch_fulfill_request": _FETCH,
    "WR_webauthn_enable": _WEBAUTHN,
    "WR_webauthn_add_credential": _WEBAUTHN,
    "WR_webauthn_list_credentials": _WEBAUTHN,
    "WR_webauthn_remove": _WEBAUTHN,
    "WR_dismiss_cookie_consent": "it looks for consent buttons through the Selenium driver, and there is no "
                                 "Playwright command that does",
    "WR_cross_browser_capture": "it reads the title and the HTML from the Selenium driver into one result; "
                                "capture WR_get_title and WR_get_page_source, which translate",
}
