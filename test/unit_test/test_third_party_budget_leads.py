"""third_party_budget: every vendor of the catalogue can be the answer for one of its hosts."""
from je_web_runner.utils.third_party_budget.budget import _VENDOR_CATALOGUE, classify_har


def _vendor_of(url: str) -> str:
    har = {"log": {"entries": [{"request": {"url": url}, "response": {}}]}}
    return classify_har(har, first_party_hostname="shop.test")[0].vendor


def test_tag_manager_is_classified_as_gtm():
    assert _vendor_of("https://www.googletagmanager.com/gtm.js?id=GTM-1") == "gtm"


def test_analytics_is_still_google_analytics():
    assert _vendor_of("https://www.google-analytics.com/analytics.js") == "google_analytics"


def test_no_host_is_listed_under_two_vendors():
    seen: dict[str, str] = {}
    for vendor, hosts in _VENDOR_CATALOGUE.items():
        for host in hosts:
            assert host not in seen, f"{host} is under {seen.get(host)} and {vendor}"
            seen[host] = vendor
