import json
from pathlib import Path

from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_spec.models import CandidateSpec
from cleansolve_spec.validation import validate_candidate_spec, visible_review_items

FIXTURE_DIR = Path("fixtures/samples/dimension_marker_basic")


def test_mock_analysis_client_returns_dimension_marker_spec():
    spec = MockAnalysisClient().extract_candidate_spec(job_id="job_mock")

    report = validate_candidate_spec(spec)
    review_items = visible_review_items(spec)

    assert spec.style.source == "system_builtin"
    assert spec.elements[0].type == "freehand_dimension_marker"
    assert report.passed is True
    assert review_items == []


def test_dimension_marker_partial_spec_matches_mock_client_output():
    expected_spec = CandidateSpec.model_validate_json(
        (FIXTURE_DIR / "expected_partial_spec.json").read_text()
    )
    actual_spec = MockAnalysisClient().extract_candidate_spec("fixture_dimension_marker_basic")

    assert expected_spec.model_dump(mode="json") == actual_spec.model_dump(mode="json")


def test_dimension_marker_correction_plan_issue_contract_is_explicit():
    correction_plan = json.loads((FIXTURE_DIR / "expected_correction_plan.json").read_text())
    issue = correction_plan["issues"][0]

    assert issue["expected"] == "freehand dimension marker should represent target range from O to S"
    assert issue["actual"] == "visible marker appears to cover only partial range"
    assert issue["correction_action"] == "patch_candidate_spec_geometry"
    assert issue["auto_correctable"] is True
