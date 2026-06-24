from copy import deepcopy
from pathlib import Path

import pytest

from cleansolve_ai.errors import OpenAIResponseError
from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_spec.models import Element, Evidence

from cleansolve_workflow.graph import run_mock_workflow


class RecordingAnalysisClient:
    def __init__(self):
        self.calls = []

    def extract_candidate_spec(self, job_id, **kwargs):
        self.calls.append({"job_id": job_id, **kwargs})
        return MockAnalysisClient().extract_candidate_spec(
            job_id,
            problem_image_artifact_id=kwargs["problem_image_artifact_id"],
            teacher_solution_image_artifact_id=kwargs["teacher_solution_image_artifact_id"],
        )


class FailingAnalysisClient:
    def extract_candidate_spec(self, job_id, **kwargs):
        raise OpenAIResponseError("model output rejected")


def test_workflow_auto_revises_before_human_review():
    state = run_mock_workflow(job_id="job_workflow")

    assert state["status"] == "APPROVED"
    assert state["status_history"] == [
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
    assert state["revision_attempts"] == 1
    assert state["max_revision_attempts"] == 2
    assert state["candidate_spec"].elements[0].needs_review is True
    assert state["candidate_spec"].elements[0].requires_human_review is False
    assert state["review_items"] == []
    assert all(
        not item["element_id"].startswith("el_freehand_dimension")
        for item in state["review_items"]
    )
    assert state["correction_plans"][0]["actions"][0]["type"] == "spec_patch"
    assert state["correction_plans"][0]["issues"][0]["expected"] == [540, 850]
    assert state["correction_plans"][0]["issues"][0]["actual"] == [520, 470]
    assert (
        state["correction_plans"][0]["issues"][0]["correction_action"]
        == "patch_candidate_spec_geometry"
    )
    assert state["correction_plans"][0]["issues"][0]["auto_correctable"] is True


def test_mock_workflow_passes_source_image_artifact_ids_to_candidate_spec():
    state = run_mock_workflow(
        "job_abc",
        source_image_artifact_ids={
            "problem": "img_problem_123",
            "teacher_solution": "img_teacher_456",
        },
    )

    assert state["candidate_spec"].source_images == {
        "problem_image_id": "img_problem_123",
        "teacher_solution_image_id": "img_teacher_456",
    }


def test_workflow_passes_source_ids_and_paths_to_analysis_client(tmp_path):
    client = RecordingAnalysisClient()
    problem_path = tmp_path / "problem.png"
    teacher_path = tmp_path / "teacher.jpg"

    state = run_mock_workflow(
        "job_openai",
        source_image_artifact_ids={
            "problem": "img_problem_123",
            "teacher_solution": "img_teacher_456",
        },
        source_image_paths={
            "problem": str(problem_path),
            "teacher_solution": str(teacher_path),
        },
        analysis_client_override=client,
    )

    assert state["status"] == "APPROVED"
    assert client.calls == [
        {
            "job_id": "job_openai",
            "problem_image_artifact_id": "img_problem_123",
            "teacher_solution_image_artifact_id": "img_teacher_456",
            "problem_image_path": Path(problem_path),
            "teacher_solution_image_path": Path(teacher_path),
        }
    ]


def test_workflow_propagates_analysis_adapter_error():
    with pytest.raises(OpenAIResponseError, match="model output rejected"):
        run_mock_workflow(
            "job_openai",
            source_image_artifact_ids={
                "problem": "img_problem_123",
                "teacher_solution": "img_teacher_456",
            },
            analysis_client_override=FailingAnalysisClient(),
        )


def test_run_mock_workflow_calls_progress_event_sink():
    events = []

    state = run_mock_workflow(
        "job_sink_test",
        source_image_artifact_ids={
            "problem": "img_problem_123",
            "teacher_solution": "img_teacher_456",
        },
        progress_event_sink=events.append,
    )

    assert len(events) == len(state["progress_events"])
    assert [event.event_id for event in events] == [
        event.event_id for event in state["progress_events"]
    ]
    assert events[0].message == "작업을 시작했습니다."


def test_run_mock_workflow_fails_when_progress_event_sink_fails():
    def failing_sink(_event):
        raise RuntimeError("progress sink failed")

    with pytest.raises(RuntimeError, match="progress sink failed"):
        run_mock_workflow(
            "job_sink_failure",
            source_image_artifact_ids={
                "problem": "img_problem_123",
                "teacher_solution": "img_teacher_456",
            },
            progress_event_sink=failing_sink,
        )


def test_workflow_does_not_approve_invalid_candidate_spec():
    candidate_spec = MockAnalysisClient().extract_candidate_spec("job_invalid")
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
        job_id="job_invalid",
        candidate_spec_override=candidate_spec,
    )

    assert state["status"] == "REVISION_REQUIRED"
    assert state["validation_reports"][0].passed is False
    assert state["validation_reports"][0].issues[0].type == "missing_dimension_target_anchor"


def test_workflow_enforces_zero_revision_budget():
    state = run_mock_workflow(job_id="job_no_revision", max_revision_attempts=0)

    assert state["status"] == "REVISION_REQUIRED"
    assert state["revision_attempts"] == 0
    assert state["correction_plans"] == []
    assert state["candidate_spec"].elements[0].revision_history == []


def test_workflow_revalidates_after_auto_revision_before_approval():
    state = run_mock_workflow(job_id="job_revalidate")

    assert state["status"] == "APPROVED"
    assert len(state["validation_reports"]) >= 2
    assert state["validation_reports"][-1].passed is True
    assert state["inspection_issue"] is None
    assert state["status_history"][-4:] == [
        "INSPECTING_LAYOUT",
        "INSPECTING_STYLE",
        "COMPUTING_VISUAL_DIFF",
        "APPROVED",
    ]


def test_workflow_auto_correction_changes_candidate_spec_geometry():
    original_spec = MockAnalysisClient().extract_candidate_spec("job_patch")
    original_endpoint = deepcopy(original_spec.elements[0].geometry["target_anchor_end"])

    state = run_mock_workflow(
        job_id="job_patch",
        candidate_spec_override=original_spec,
    )
    element = state["candidate_spec"].elements[0]

    assert element.geometry["target_anchor_end"] != original_endpoint
    assert element.geometry["target_anchor_end"] == [540, 850]
    assert element.revision_history == [
        {
            "revision_id": "rev_001",
            "source": "auto_correction",
            "patch": {"geometry.target_anchor_end": [540, 850]},
        }
    ]


def test_workflow_does_not_approve_unrelated_patch_when_endpoint_mismatch_remains():
    state = run_mock_workflow(
        job_id="job_unrelated_patch",
        correction_patch_override={"geometry.label_anchor": [300, 620]},
    )

    assert state["status"] == "REVISION_REQUIRED"
    assert state["revision_attempts"] == 1
    assert state["review_tool_decisions"][-1].reason_code == "repeated_element_patch"
    assert state["inspection_issue"]["type"] == "dimension_endpoint_mismatch"
    assert state["candidate_spec"].elements[0].geometry["target_anchor_end"] != [540, 850]
    assert state["correction_plans"][-1]["actions"][0]["patch"] == {
        "geometry.label_anchor": [300, 620]
    }


def test_revision_required_preserves_visible_human_review_items():
    candidate_spec = MockAnalysisClient().extract_candidate_spec("job_human_review")
    candidate_spec.elements[0].requires_human_review = True
    candidate_spec.elements[0].review_reason = "Endpoint needs operator review."

    state = run_mock_workflow(
        job_id="job_human_review",
        candidate_spec_override=candidate_spec,
        max_revision_attempts=0,
    )

    assert state["status"] == "REVISION_REQUIRED"
    assert state["revision_attempts"] == 0
    assert state["review_items"] == [
        {
            "element_id": "el_freehand_dimension_001",
            "type": "freehand_dimension_marker",
            "review_reason": "Endpoint needs operator review.",
        }
    ]
