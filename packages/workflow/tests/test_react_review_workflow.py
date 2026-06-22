from copy import deepcopy

from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_spec.models import Element, Evidence

from cleansolve_workflow.graph import run_mock_workflow


EXPECTED_HAPPY_PATH_STATUSES = [
    "CREATED",
    "STYLE_PRESET_LOADED",
    "SPEC_EXTRACTED",
    "SPEC_VALIDATING",
    "RENDERING",
    "RENDERED",
    "INSPECTING_CONTENT",
    "INSPECTING_LAYOUT",
    "INSPECTING_STYLE",
    "COMPUTING_VISUAL_DIFF",
    "CORRECTION_PLANNING",
    "PATCHING_SPEC",
    "RE_RENDERING",
    "RENDERED",
    "SPEC_REVALIDATING",
    "INSPECTING_CONTENT",
    "INSPECTING_LAYOUT",
    "INSPECTING_STYLE",
    "COMPUTING_VISUAL_DIFF",
    "APPROVED",
]


def dumped_progress_events(state):
    return [event.model_dump(mode="json") for event in state["progress_events"]]


def test_react_workflow_auto_revises_with_progress_events():
    state = run_mock_workflow(job_id="job_react")

    assert state["status"] == "APPROVED"
    assert state["status_history"] == EXPECTED_HAPPY_PATH_STATUSES
    assert [event.status for event in state["progress_events"]] == EXPECTED_HAPPY_PATH_STATUSES
    assert len(state["review_attempts"]) >= 2
    assert state["review_attempts"][0].gate_result.failed_reasons == [
        "layout_alignment_below_threshold",
        "max_error_severity_exceeded",
    ]
    assert state["review_attempts"][-1].gate_result.passed is True
    assert dumped_progress_events(state)[0]["message"] == "작업을 시작했습니다."
    assert "source_image_paths" not in dumped_progress_events(state)[0]


def test_react_workflow_records_tool_decisions():
    state = run_mock_workflow(job_id="job_react_decisions")

    decisions = [decision.tool_name for decision in state["review_tool_decisions"]]

    assert "inspect_content" in decisions
    assert "inspect_layout" in decisions
    assert "inspect_style" in decisions
    assert "compute_visual_diff" in decisions
    assert "patch_candidate_spec" in decisions
    assert decisions[-1] == "mark_approved"


def test_react_workflow_zero_revision_budget_escalates():
    state = run_mock_workflow(job_id="job_react_zero_budget", max_revision_attempts=0)

    assert state["status"] == "REVISION_REQUIRED"
    assert state["revision_attempts"] == 0
    assert state["progress_events"][-1].status == "REVISION_REQUIRED"
    assert state["review_tool_decisions"][-1].reason_code == "revision_budget_exceeded"
    assert state["candidate_spec"].elements[0].revision_history == []


def test_react_workflow_rejects_repeated_unhelpful_patch():
    state = run_mock_workflow(
        job_id="job_react_unhelpful_patch",
        correction_patch_override={"geometry.label_anchor": [300, 620]},
    )

    assert state["status"] == "REVISION_REQUIRED"
    assert state["revision_attempts"] == 1
    assert state["review_tool_decisions"][-1].reason_code in {
        "repeated_element_patch",
        "revision_budget_exceeded",
    }
    assert state["candidate_spec"].elements[0].geometry["target_anchor_end"] != [540, 850]


def test_react_workflow_unsupported_patch_does_not_count_as_revision():
    state = run_mock_workflow(
        job_id="job_react_unsupported_patch",
        correction_patch_override={"style.color": "blue"},
    )

    assert state["status"] == "REVISION_REQUIRED"
    assert state["revision_attempts"] == 0
    assert state["candidate_spec"].elements[0].revision_history == []
    assert state["review_tool_decisions"][-1].reason_code == "repeated_element_patch"


def test_react_workflow_validation_failure_has_contract_invalid_gate():
    candidate_spec = MockAnalysisClient().extract_candidate_spec("job_react_invalid")
    candidate_spec.elements = [
        Element(
            id="el_invalid_dimension",
            type="dimension_curve",
            color="red",
            confidence=0.85,
            needs_review=True,
            requires_human_review=False,
            auto_correctable=False,
            evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 100]),
            bbox=[10, 10, 100, 100],
            geometry={"kind": "dimension_curve", "label": "1", "label_anchor": [50, 50]},
        )
    ]

    state = run_mock_workflow(
        job_id="job_react_invalid",
        candidate_spec_override=candidate_spec,
    )

    assert state["status"] == "REVISION_REQUIRED"
    assert state["latest_gate_result"].passed is False
    assert "contract_invalid" in state["latest_gate_result"].failed_reasons
    assert state["latest_scores"].visual_diff == 1.0


def test_react_workflow_auto_correction_changes_candidate_spec_geometry():
    original_spec = MockAnalysisClient().extract_candidate_spec("job_react_patch")
    original_endpoint = deepcopy(original_spec.elements[0].geometry["target_anchor_end"])

    state = run_mock_workflow(
        job_id="job_react_patch",
        candidate_spec_override=original_spec,
    )

    element = state["candidate_spec"].elements[0]
    assert element.geometry["target_anchor_end"] != original_endpoint
    assert element.geometry["target_anchor_end"] == [540, 850]
