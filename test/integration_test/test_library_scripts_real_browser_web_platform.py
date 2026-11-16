"""
The page scripts of the web-platform and performance libraries, run in a real headless Chromium and
fed back to the libraries' own parsers and assertions.

Each script is run the way the command adapters run it: as a Selenium ``execute_script`` body
(``arguments[i]``, an explicit ``return``). Skips when Playwright or its Chromium is not available.
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from je_web_runner.utils.background_sync_assert import sync as background_sync
from je_web_runner.utils.compression_streams import streams as compression
from je_web_runner.utils.compute_pressure import pressure as compute_pressure
from je_web_runner.utils.console_error_budget import budget as console_budget
from je_web_runner.utils.cookie_store_api import store as cookie_store
from je_web_runner.utils.credential_management import credentials as credential_management
from je_web_runner.utils.indexed_db_explorer import explorer as indexed_db
from je_web_runner.utils.memory_pressure_emulate import emulate as memory_pressure
from je_web_runner.utils.payment_request_assert import payment as payment_request
from je_web_runner.utils.pip_assert import pip as pip_assert
from je_web_runner.utils.popover_assert import popover as popover_assert
from je_web_runner.utils.storage_buckets import buckets as storage_buckets
from je_web_runner.utils.view_transitions import transitions as view_transitions
from je_web_runner.utils.wake_lock_assert import lock as wake_lock
from je_web_runner.utils.web_locks import locks as web_locks
from je_web_runner.utils.web_push_assert import push as web_push
from je_web_runner.utils.webcodecs_assert import assertions as webcodecs
from je_web_runner.utils.webusb_mock import mock as webusb

sync_api = pytest.importorskip("playwright.sync_api")

_PAGE = b"""<!doctype html><html><head><title>library scripts</title>
<style>#box{view-transition-name: hero; width: 50px; height: 50px; background: red}</style></head>
<body><div id="box"></div><dialog id="d" open>hi</dialog><div id="p" popover>pop</div></body></html>"""
_APP_JS = b"function shout() { console.error('boom', 42); }\nshout();\n"
_SERVICE_WORKER = (
    "self.addEventListener('install', () => self.skipWaiting());\n"
    "self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));\n"
    + background_sync.SERVICE_WORKER_RELAY_SCRIPT
).encode("utf-8")
_FILES = {"/sw.js": (_SERVICE_WORKER, "text/javascript"), "/app.js": (_APP_JS, "text/javascript")}
# Selenium's execute_script: the script is a function body that gets ``arguments`` and returns its value.
_EXECUTE_SCRIPT = "([body, args]) => (new Function(body)).apply(null, args)"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — http.server naming
        body, kind = _FILES.get(self.path, (_PAGE, "text/html"))
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def execute_script(page, script, *args):
    return page.evaluate(_EXECUTE_SCRIPT, [script, list(args)])


@pytest.fixture(scope="module")
def site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"  # NOSONAR S5332 — local test server
    server.shutdown()


@pytest.fixture(scope="module")
def playwright_driver():
    with sync_api.sync_playwright() as driver:
        yield driver


@pytest.fixture(scope="module")
def browser(playwright_driver):
    try:
        launched = playwright_driver.chromium.launch(headless=True)
    except Exception as error:  # no Chromium for Playwright here
        pytest.skip(f"Chromium cannot launch: {error!r}")
    yield launched
    launched.close()


@pytest.fixture
def context(browser):
    opened = browser.new_context()
    yield opened
    opened.close()


@pytest.fixture
def page(context, site):
    opened = context.new_page()
    opened.goto(site + "/")
    return opened


def _register_service_worker(page):
    page.evaluate("async () => { await navigator.serviceWorker.register('/sw.js');"
                  " await navigator.serviceWorker.ready; }")


# ---------- web_platform_b ---------------------------------------------------------------------------------

def test_view_transitions_records_the_animated_groups(page):
    execute_script(page, view_transitions.build_instrumentation_script())
    page.evaluate("""async () => { const transition = document.startViewTransition(() => {
        document.getElementById('box').style.background = 'blue'; }); await transition.finished; }""")
    runs = view_transitions.parse_log(execute_script(page, "return window.__wr_vt_log__ || [];"))
    assert len(runs) == 1
    assert sorted(runs[0].groups) == ["hero", "root"]
    view_transitions.assert_all_finished(runs)
    view_transitions.assert_group_present(runs, "hero")
    with pytest.raises(view_transitions.ViewTransitionsError):
        view_transitions.assert_group_present(runs, "sidebar")


def test_web_locks_if_available_request_that_got_null(page):
    execute_script(page, web_locks.INSTALL_LISTENER_SCRIPT)
    page.evaluate("""async () => {
        let release; const held = new Promise((resolve) => { release = resolve; });
        const first = navigator.locks.request('cart', () => held);
        await new Promise((resolve) => setTimeout(resolve, 50));
        await navigator.locks.request('cart', {ifAvailable: true}, (lock) => lock === null);
        release(); await first; }""")
    events = web_locks.parse_log(execute_script(page, web_locks.HARVEST_LOG_SCRIPT))
    refused = web_locks.assert_if_available_unavailable(events, name="cart")
    assert refused.if_available is True
    web_locks.assert_no_deadlock(events)
    web_locks.assert_serialised(events, name="cart")
    web_locks.assert_acquired_count(events, name="cart", expected=1)


def test_web_push_records_the_endpoint_the_push_service_returned(page):
    _register_service_worker(page)
    # Headless Chromium has no push service ("Registration failed - permission denied"): answer in its place.
    page.evaluate("""() => { PushManager.prototype.subscribe = async function (options) {
        return {endpoint: 'https://fcm.googleapis.com/fcm/send/abc', options: options}; }; }""")
    execute_script(page, web_push.INSTALL_SCRIPT)
    page.wait_for_timeout(100)
    endpoint = page.evaluate("""async () => { const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.subscribe(
          {userVisibleOnly: true, applicationServerKey: 'QUJD'});
        return subscription.endpoint; }""")
    payload = execute_script(page, "const hook = window.__wr_push__;"
                                   " return {subscriptions: hook.drainSubs(), notifications: hook.drainShown()};")
    log = web_push.parse_log(payload)
    assert endpoint == "https://fcm.googleapis.com/fcm/send/abc"
    assert [sub.endpoint for sub in log.subscriptions] == [endpoint]
    web_push.assert_endpoint_recognised(log)
    web_push.assert_user_visible_only(log)
    web_push.assert_subscribed_with_vapid(log, vapid_public_key="QUJD")


@pytest.mark.parametrize("where", ["secure", "data"])
def test_webusb_fake_device_is_what_the_page_gets(page, where):
    if where == "data":
        page.goto("data:text/html,<p>no WebUSB here</p>")
    specs = [webusb.build_mock_device(1155, 22336, product_name="Probe", serial_number="A1").to_dict()]
    execute_script(page, webusb.INSTALL_SCRIPT, specs)
    device = page.evaluate("""async () => { const device = await navigator.usb.requestDevice({filters: []});
        await device.open(); await device.transferOut(2, new Uint8Array([1, 2, 3]));
        return {vendorId: device.vendorId, productId: device.productId, productName: device.productName,
                serialNumber: device.serialNumber}; }""")
    assert device == {"vendorId": 1155, "productId": 22336, "productName": "Probe", "serialNumber": "A1"}
    listed = execute_script(page, "return window.__wr_usb__.listDevices();")
    assert listed == [{"vendorId": 1155, "productId": 22336, "opened": True}]
    calls = webusb.parse_outgoing(execute_script(page, "return window.__wr_usb__.drainOutgoing();"))
    assert webusb.assert_transfer_out(calls, endpoint=2, contains=[2, 3]).data == [1, 2, 3]


def test_wake_lock_logs_one_release_for_one_release(playwright_driver, site):
    try:  # the headless shell refuses wake locks; the full Chromium in headless mode grants them
        full = playwright_driver.chromium.launch(headless=True, channel="chromium")
    except Exception as error:
        pytest.skip(f"full Chromium cannot launch: {error!r}")
    try:
        page = full.new_page()
        page.goto(site + "/")
        execute_script(page, wake_lock.INSTALL_SCRIPT)
        outcome = page.evaluate("""async () => { try { const sentinel = await navigator.wakeLock.request('screen');
            await sentinel.release(); await new Promise((resolve) => setTimeout(resolve, 100)); return 'ok'; }
            catch (error) { return String(error); } }""")
        if outcome != "ok":
            pytest.skip(f"this Chromium refuses a wake lock: {outcome}")
        events = execute_script(page, "return window.__wr_wakelock__.drain();")
    finally:
        full.close()
    log = wake_lock.parse_log(events)
    assert [(event.kind, event.by) for event in log.events] == [("acquire", ""), ("release", "app")]
    wake_lock.assert_no_leak(log)
    wake_lock.assert_released_by_app(log)
    wake_lock.assert_re_acquired_after_visibility(log)


def test_webcodecs_install_script_installs_the_recorder(page):
    assert execute_script(page, webcodecs.INSTALL_SCRIPT) is None
    execute_script(page, "window.__wr_codec__.record('video', {type: 'key', timestamp: 0, duration: 33333,"
                         " byteLength: 10}, {codec: 'avc1.42001f', width: 640, height: 480});")
    chunks = webcodecs.parse_chunks(execute_script(page, "return window.__wr_codec__.drain('video');"))
    webcodecs.assert_codec(chunks, "avc1.42001f")


# ---------- performance ------------------------------------------------------------------------------------

def test_memory_pressure_payloads_are_accepted_by_chromium(page, context):
    session = context.new_cdp_session(page)
    cores = page.evaluate("navigator.hardwareConcurrency")
    assert memory_pressure.original_hardware_concurrency(session.send) == cores
    for profile in memory_pressure.DEFAULT_PROFILES:
        for command in memory_pressure.cdp_payloads(profile):
            session.send(command["method"], command["params"])  # raises on a protocol error
        assert page.evaluate("navigator.hardwareConcurrency") == profile.hardware_concurrency
    for command in memory_pressure.restore_payloads(cores):
        session.send(command["method"], command["params"])
    assert page.evaluate("navigator.hardwareConcurrency") == cores


def test_memory_pressure_run_restores_the_core_count(page, context):
    session = context.new_cdp_session(page)
    cores = page.evaluate("navigator.hardwareConcurrency")
    profile = memory_pressure.EmulationProfile(
        name="one core", hardware_concurrency=1 if cores != 1 else 2, cpu_throttle_rate=2.0,
        pressure_level=memory_pressure.PressureLevel.SERIOUS)
    seen = []
    outcome = memory_pressure.run_under_profile(
        profile, session.send, lambda: seen.append(page.evaluate("navigator.hardwareConcurrency")))
    memory_pressure.assert_passed_under_pressure(outcome)
    assert seen == [profile.hardware_concurrency]
    assert page.evaluate("navigator.hardwareConcurrency") == cores


def test_console_event_url_and_line_come_from_the_call_frame(page, context, site):
    session = context.new_cdp_session(page)
    events = []
    session.on("Runtime.consoleAPICalled", lambda event: events.append(event))
    session.send("Runtime.enable")
    page.add_script_tag(url=site + "/app.js")
    page.wait_for_function("typeof shout === 'function'")
    page.wait_for_timeout(200)
    messages = [m for m in console_budget.from_cdp_console_events(events) if m.text == "boom 42"]
    assert len(messages) == 1
    assert messages[0].severity == "error"
    assert messages[0].url == site + "/app.js"
    assert messages[0].line == 0


# ---------- web_platform_a ---------------------------------------------------------------------------------

def test_background_sync_fired_is_filled_from_the_service_worker(page, context, site):
    _register_service_worker(page)
    execute_script(page, background_sync.INSTALL_SCRIPT)
    session = context.new_cdp_session(page)
    registrations = []
    session.on("ServiceWorker.workerRegistrationUpdated",
               lambda event: registrations.extend(event["registrations"]))
    session.send("ServiceWorker.enable")
    page.wait_for_timeout(300)
    assert registrations, "the service worker registration was not reported"
    # Headless Chromium answers register() with "Background Sync is disabled", so the real ``sync``
    # event is dispatched to the worker the way DevTools does it.
    for last_chance in (False, True):
        session.send("ServiceWorker.dispatchSyncEvent", {
            "origin": site, "registrationId": registrations[-1]["registrationId"],
            "tag": "outbox", "lastChance": last_chance})
    page.wait_for_function("window.__wr_bg_sync__ !== undefined")
    page.wait_for_timeout(800)
    payload = execute_script(page, "const hook = window.__wr_bg_sync__;"
                                   " return {registered: hook.drainRegistered(), fired: hook.drainFired()};")
    log = background_sync.parse_log(payload)
    assert [(fire.tag, fire.last_chance) for fire in log.fired] == [("outbox", False), ("outbox", True)]
    background_sync.assert_fired(log, tag="outbox", at_least=2)
    background_sync.assert_retry_happened(log, tag="outbox")
    with pytest.raises(background_sync.BackgroundSyncAssertError):
        background_sync.assert_no_quota_exhaustion(log, tag="outbox")


def test_compute_pressure_log_matches_parse_log(page):
    execute_script(page, compute_pressure.INSTALL_SCRIPT)
    page.evaluate("""() => { const observer = new PressureObserver((records) => {
          if (records[0].state === 'critical') window.__wr_cp__.recordReaction('pause-video'); });
        observer.observe('cpu'); window.__observer = observer; }""")
    assert execute_script(page, "return window.__wr_cp__.fire('fair');") is True
    assert execute_script(page, "return window.__wr_cp__.fire('critical');") is True
    page.evaluate("() => window.__observer.disconnect()")
    log = compute_pressure.parse_log(execute_script(page, "return window.__wr_cp__.drainLog();"))
    assert log.fires == [compute_pressure.PressureLevel.FAIR, compute_pressure.PressureLevel.CRITICAL]
    assert log.disconnect_count == 1
    reaction = compute_pressure.assert_reaction_to(log, level=compute_pressure.PressureLevel.CRITICAL)
    assert (reaction.name, reaction.level) == ("pause-video", compute_pressure.PressureLevel.CRITICAL)
    compute_pressure.assert_throttled_at_or_above(log, level=compute_pressure.PressureLevel.SERIOUS)
    compute_pressure.assert_observer_disconnected(log)
    assert execute_script(page, "return window.__wr_cp__.drainLog();") == {
        "reactions": [], "fires": [], "disconnectCount": 0}


def test_document_pip_exit_is_recorded(page):
    if not page.evaluate("'documentPictureInPicture' in window"):
        pytest.skip("this Chromium has no Document Picture-in-Picture")
    execute_script(page, pip_assert.INSTALL_SCRIPT)
    page.evaluate("""() => { window.__outcome = null; document.addEventListener('click', () => {
        documentPictureInPicture.requestWindow({width: 320, height: 240}).then((pipWindow) => {
          setTimeout(() => { pipWindow.close(); setTimeout(() => { window.__outcome = 'closed'; }, 300); }, 100);
        }, (error) => { window.__outcome = String(error); }); }, {once: true}); }""")
    page.mouse.click(30, 30)  # requestWindow needs a user gesture
    page.wait_for_function("window.__outcome !== null", timeout=10000)
    if page.evaluate("window.__outcome") != "closed":
        pytest.skip(f"this Chromium refuses a PiP window: {page.evaluate('window.__outcome')}")
    log = pip_assert.parse_log(execute_script(page, "return window.__wr_pip__.drain();"))
    assert [(event.kind, event.mode) for event in log.events] == [
        ("enter", pip_assert.Mode.DOCUMENT), ("exit", pip_assert.Mode.DOCUMENT)]
    pip_assert.assert_entered(log, mode=pip_assert.Mode.DOCUMENT)
    pip_assert.assert_exited_cleanly(log, mode=pip_assert.Mode.DOCUMENT)
    pip_assert.assert_size_at_least(log, min_width=320, min_height=240)


def test_credential_store_does_not_put_the_password_in_the_log(page):
    seed = credential_management.build_seed([credential_management.SeedCredential(id="alice", password="s3cret")])
    execute_script(page, credential_management.INSTALL_SCRIPT, seed)
    seeded = page.evaluate("""async () => {
        await navigator.credentials.store({id: 'alice', type: 'password', password: 'hunter2'});
        const credential = await navigator.credentials.get({password: true, mediation: 'required'});
        return credential.password; }""")
    assert seeded == "s3cret"
    payload = execute_script(page, "const hook = window.__wr_cm__; return {stored: hook.drainStored(),"
                                   " gets: hook.drainGets(), preventCount: hook.preventCount()};")
    assert "hunter2" not in str(payload)
    log = credential_management.parse_log(payload)
    assert credential_management.assert_stored(log, credential_id="alice").has_password is True
    credential_management.assert_no_password_in_clear(log)
    credential_management.assert_get_requested_mediation(log, mediation="required")


def test_compression_harvest_round_trips_and_brotli_is_not_a_stream_format(page):
    import base64
    script = "return (" + compression.HARVEST_SCRIPT.strip().rstrip(";") + ")(arguments[0], arguments[1]);"
    text = "hello hello hello hello"
    for algorithm in (compression.Algorithm.GZIP, compression.Algorithm.DEFLATE, compression.Algorithm.DEFLATE_RAW):
        compressed = base64.b64decode(execute_script(page, script, algorithm.value, text))
        compression.assert_round_trip(original=text.encode("utf-8"), compressed=compressed, algorithm=algorithm)
    with pytest.raises(sync_api.Error, match="Unsupported compression format"):
        execute_script(page, script, compression.Algorithm.BROTLI.value, text)


def test_expression_scripts_need_return_as_an_execute_script_body(page):
    page.evaluate("document.cookie = 'a=1'")
    page.evaluate("""() => new Promise((resolve) => { const request = indexedDB.open('shop', 1);
        request.onupgradeneeded = () => request.result.createObjectStore('cart', {keyPath: 'id'});
        request.onsuccess = () => { const db = request.result;
          const tx = db.transaction('cart', 'readwrite'); tx.objectStore('cart').put({id: 1, qty: 2});
          tx.oncomplete = () => { db.close(); resolve(null); }; }; })""")
    scripts = {
        "cookies": cookie_store.GET_ALL_SCRIPT,
        "popovers": popover_assert.HARVEST_SCRIPT,
        "buckets": storage_buckets.HARVEST_SCRIPT,
        "idb": indexed_db.build_harvest_script("shop"),
    }
    for name, script in scripts.items():
        assert execute_script(page, script) is None, name
    found = {name: execute_script(page, "return " + script) for name, script in scripts.items()}
    assert found == {name: page.evaluate(script) for name, script in scripts.items()}
    assert [cookie.name for cookie in cookie_store.parse_cookies(found["cookies"])] == ["a"]
    assert [(state.id, state.open) for state in popover_assert.parse_snapshot(found["popovers"])] == [
        ("d", True), ("p", False)]
    assert storage_buckets.parse_snapshot(found["buckets"]).supported is True
    snapshot = indexed_db.IdbSnapshot.from_dict(found["idb"])
    assert snapshot.stores["cart"].records == [{"id": 1, "qty": 2}]


def test_payment_request_log_from_the_shim(page):
    execute_script(page, payment_request.INSTALL_SCRIPT, {})
    page.evaluate("""async () => { const request = new PaymentRequest([{supportedMethods: 'basic-card'}],
        {total: {label: 't', amount: {currency: 'USD', value: '1.00'}}});
        const response = await request.show(); await response.complete('success'); }""")
    payload = execute_script(page, "const hook = window.__wr_payment__; return {constructed:"
                                   " hook.drainConstructed(), completed: hook.drainCompleted()};")
    log = payment_request.parse_log(payload)
    payment_request.assert_supports(log, method="basic-card")
    payment_request.assert_total_currency(log, currency="USD")
    payment_request.assert_completed(log)
    with pytest.raises(payment_request.PaymentRequestAssertError, match="requestShipping"):
        payment_request.assert_shipping_required(log)
    empty = payment_request.parse_log(execute_script(
        page, "const hook = window.__wr_payment__; return {constructed: hook.drainConstructed(),"
              " completed: hook.drainCompleted()};"))
    with pytest.raises(payment_request.PaymentRequestAssertError, match="never constructed"):
        payment_request.assert_shipping_required(empty)
