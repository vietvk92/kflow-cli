from kflow.services.evidence_service import _parse_build_summary, _parse_test_summary


def test_parse_build_summary_extracts_outcome_and_counts() -> None:
    content = "BUILD FAILED\n2 warnings generated\n1 error generated\n"
    summary = _parse_build_summary(content)

    assert summary["outcome"] == "build_failed"
    assert summary["warnings"] == 2
    assert summary["errors"] == 1


def test_parse_test_summary_extracts_pytest_counts() -> None:
    content = "================ 5 passed, 1 failed, 2 skipped in 0.10s ================\n"
    summary = _parse_test_summary(content)

    assert summary["passed"] == 5
    assert summary["failed"] == 1
    assert summary["skipped"] == 2
