import re

import pytest

from cleansolve_workflow.review_contract import (
    APPROVED_SCORE_FIXTURE,
    DEFAULT_APPROVAL_GATE,
    MISMATCH_SCORE_FIXTURE,
    PROGRESS_MESSAGE_ALLOWLIST,
    ReviewScores,
    append_progress_event,
    evaluate_approval_gate,
    has_score_improved,
)
from cleansolve_workflow.review_tools import ReviewToolRejected, ensure_allowed_tool


def base_state():
    return {
        "job_id": "job_contract",
        "revision_attempts": 0,
        "max_revision_attempts": 2,
        "review_event_sequence": 0,
        "progress_events": [],
    }


def test_progress_event_rejects_unapproved_message():
    state = base_state()

    with pytest.raises(ValueError, match="progress event message is not allowlisted"):
        append_progress_event(
            state,
            phase="review_and_correct",
            status="INSPECTING_LAYOUT",
            message="모델 내부 추론을 요약하고 있습니다.",
            next_action="layout_check",
        )


def test_progress_event_sequence_is_deterministic():
    state = base_state()

    append_progress_event(
        state,
        phase="analysis",
        status="CREATED",
        message="작업을 시작했습니다.",
        next_action="continue",
    )
    append_progress_event(
        state,
        phase="validation",
        status="SPEC_VALIDATING",
        message="candidate spec 계약을 검증하고 있습니다.",
        next_action="continue",
    )

    events = state["progress_events"]
    assert [event.sequence for event in events] == [0, 1]
    assert [event.event_id for event in events] == ["evt_0000", "evt_0001"]
    assert state["review_event_sequence"] == 2
    assert events[0].message in PROGRESS_MESSAGE_ALLOWLIST
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", events[0].created_at)


def test_gate_passes_when_all_thresholds_met():
    result = evaluate_approval_gate(
        scores=APPROVED_SCORE_FIXTURE,
        gate=DEFAULT_APPROVAL_GATE,
        contract_valid=True,
        visible_review_item_count=0,
        max_error_severity="none",
    )

    assert result.passed is True
    assert result.failed_reasons == []


def test_gate_fails_for_layout_score():
    result = evaluate_approval_gate(
        scores=MISMATCH_SCORE_FIXTURE,
        gate=DEFAULT_APPROVAL_GATE,
        contract_valid=True,
        visible_review_item_count=0,
        max_error_severity="high",
    )

    assert result.passed is False
    assert "layout_alignment_below_threshold" in result.failed_reasons
    assert "max_error_severity_exceeded" in result.failed_reasons


def test_gate_fails_for_visual_diff():
    result = evaluate_approval_gate(
        scores=ReviewScores(
            content_consistency=0.95,
            layout_alignment=0.9,
            style_similarity=0.78,
            visual_diff=0.26,
        ),
        gate=DEFAULT_APPROVAL_GATE,
        contract_valid=True,
        visible_review_item_count=0,
        max_error_severity="none",
    )

    assert result.passed is False
    assert result.failed_reasons == ["visual_diff_above_threshold"]


def test_review_tool_allowlist_rejects_unknown_tool():
    assert ensure_allowed_tool("inspect_layout") == "inspect_layout"

    with pytest.raises(ReviewToolRejected, match="review tool is not allowlisted"):
        ensure_allowed_tool("read_raw_prompt")


def test_score_improvement_helper_detects_improvement():
    previous = ReviewScores(
        content_consistency=0.9,
        layout_alignment=0.6,
        style_similarity=0.7,
        visual_diff=0.3,
    )

    assert has_score_improved(
        previous,
        ReviewScores(
            content_consistency=0.9,
            layout_alignment=0.61,
            style_similarity=0.7,
            visual_diff=0.3,
        ),
    )
    assert has_score_improved(
        previous,
        ReviewScores(
            content_consistency=0.9,
            layout_alignment=0.6,
            style_similarity=0.7,
            visual_diff=0.29,
        ),
    )
    assert not has_score_improved(previous, previous)
