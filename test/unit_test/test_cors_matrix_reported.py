"""Every method outside GET, HEAD and POST is preflighted, so it must be in Access-Control-Allow-Methods."""
import pytest

from je_web_runner.utils.cors_matrix.matrix import CorsCase, CorsOutcome, CorsResponse, classify

ORIGIN = "https://app.example"


@pytest.mark.parametrize("verb", ["OPTIONS", "PROPFIND", "put"])
def test_a_non_safelisted_verb_needs_the_method_allowed(verb):
    case = CorsCase(verb=verb, origin=ORIGIN, with_credentials=False)
    assert case.needs_preflight() is True
    blocked = classify(case, CorsResponse(status_code=200, allow_origin=ORIGIN, allow_methods=("GET",)))
    assert blocked.outcome == CorsOutcome.BLOCKED
    allowed = classify(case, CorsResponse(status_code=200, allow_origin=ORIGIN, allow_methods=(verb.upper(),)))
    assert allowed.outcome == CorsOutcome.ALLOWED


@pytest.mark.parametrize("verb", ["GET", "HEAD", "POST"])
def test_safelisted_verbs_are_not_preflighted(verb):
    case = CorsCase(verb=verb, origin=ORIGIN, with_credentials=False)
    assert case.needs_preflight() is False
    assert classify(case, CorsResponse(status_code=200, allow_origin=ORIGIN)).outcome == CorsOutcome.ALLOWED
