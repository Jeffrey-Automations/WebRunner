"""backend_log_correlator: the Loki label cannot carry LogQL."""
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.backend_log_correlator.correlator import BackendLogCorrelatorError, fetch_loki

TRACE_ID = "0af7651916cd43dd8448eb211c80319c"


@pytest.mark.parametrize("label", [
    'trace_id="x"} or {app="payments', 'a"}', "trace id", "a-b", "", "1abc", "tra{ce", None,
])
def test_a_label_that_is_not_a_label_name_is_refused(label):
    with pytest.raises(BackendLogCorrelatorError, match="label"):
        fetch_loki("http://loki.test:3100", label=label)


def test_a_plain_label_builds_the_expected_selector():
    response = MagicMock()
    response.json.return_value = {"data": {"result": []}}
    with patch("requests.get", return_value=response) as get:
        assert fetch_loki("http://loki.test:3100", label="trace_id")(TRACE_ID) == []
    assert get.call_args.kwargs["params"]["query"] == '{trace_id="' + TRACE_ID + '"}'
