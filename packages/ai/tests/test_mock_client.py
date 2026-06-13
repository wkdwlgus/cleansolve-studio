from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_spec.validation import validate_candidate_spec, visible_review_items


def test_mock_analysis_client_returns_dimension_marker_spec():
    spec = MockAnalysisClient().extract_candidate_spec(job_id="job_mock")

    report = validate_candidate_spec(spec)
    review_items = visible_review_items(spec)

    assert spec.style.source == "system_builtin"
    assert spec.elements[0].type == "freehand_dimension_marker"
    assert report.passed is True
    assert review_items == []
