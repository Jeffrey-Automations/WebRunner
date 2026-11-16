"""pr_risk_score: the reasons are ordered by what each signal adds to the score."""
from je_web_runner.utils.pr_risk_score.scorer import PrSignals, RiskWeights, score_pr


def test_reasons_are_ordered_by_contribution():
    signals = PrSignals(
        flaky_tests_touched=4, total_tests_touched=10,   # flake signal 28 %
        security_files_changed=1,                        # security signal 50 %
    )
    report = score_pr(signals, RiskWeights(flake=5.0, security=1.0))
    assert report.contributions["flake"] > report.contributions["security"]
    assert [reason.split(":")[0] for reason in report.reasons] == ["flake", "security"]
