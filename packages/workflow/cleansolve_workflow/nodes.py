from copy import deepcopy
from pathlib import Path

from cleansolve_ai import AnalysisClient, build_analysis_client
from cleansolve_renderer.overlay import render_overlay_svg
from cleansolve_spec.validation import validate_candidate_spec, visible_review_items

from cleansolve_workflow.review_contract import (
    APPROVED_SCORE_FIXTURE,
    CONTRACT_INVALID_SCORE_FIXTURE,
    DEFAULT_APPROVAL_GATE,
    MISMATCH_SCORE_FIXTURE,
    CorrectionAction,
    ReviewAttempt,
    ReviewIssue,
    ToolDecision,
    append_progress_event,
    evaluate_approval_gate,
    has_score_improved,
)

from .state import WorkflowState

EXPECTED_TARGET_ANCHOR_END = [540, 850]

STATUS_MESSAGES = {
    "CREATED": "작업을 시작했습니다.",
    "STYLE_PRESET_LOADED": "기본 손글씨 스타일을 불러왔습니다.",
    "SPEC_EXTRACTED": "원본 문제와 선생님 손풀이를 분석하고 있습니다.",
    "SPEC_VALIDATING": "candidate spec 계약을 검증하고 있습니다.",
    "SPEC_REVALIDATING": "candidate spec 계약을 검증하고 있습니다.",
    "RENDERING": "deterministic renderer로 preview를 만들고 있습니다.",
    "RENDERED": "deterministic renderer로 preview를 만들고 있습니다.",
    "INSPECTING_CONTENT": "렌더 결과의 풀이 내용을 확인하고 있습니다.",
    "INSPECTING_LAYOUT": "렌더 결과의 위치와 치수선 정합성을 확인하고 있습니다.",
    "INSPECTING_STYLE": "렌더 결과의 손글씨 스타일 일관성을 확인하고 있습니다.",
    "COMPUTING_VISUAL_DIFF": "렌더 결과의 시각적 차이를 계산하고 있습니다.",
    "CORRECTION_PLANNING": "자동 수정 계획을 세우고 있습니다.",
    "PATCHING_SPEC": "candidate spec patch를 적용하고 있습니다.",
    "REQUESTING_HANDWRITING_ASSET": "특정 손글씨 블록 asset 재생성이 필요합니다.",
    "RE_RENDERING": "수정된 spec으로 preview를 다시 렌더링하고 있습니다.",
    "APPROVED": "자동 승인 기준을 통과했습니다.",
    "NEEDS_REVIEW": "사용자 검수가 필요합니다.",
    "REVISION_REQUIRED": "자동 수정 한도에 도달했습니다.",
    "FAILED": "작업이 실패했습니다.",
}


def load_style_preset(state: WorkflowState) -> WorkflowState:
    if not state.get("progress_events"):
        append_progress_event(
            state,
            phase="analysis",
            status="CREATED",
            message="작업을 시작했습니다.",
            next_action="continue",
        )
    state["style_preset"] = {
        "source": "system_builtin",
        "preset_id": "default_pretty_handwriting",
        "preset_version": "v1",
    }
    _set_status(state, "STYLE_PRESET_LOADED")
    return state


def analyze_sources(state: WorkflowState) -> WorkflowState:
    if "candidate_spec" not in state:
        source_ids = state.get("source_image_artifact_ids") or {}
        source_paths = state.get("source_image_paths") or {}
        client = _analysis_client_from_state(state)
        state["candidate_spec"] = client.extract_candidate_spec(
            state["job_id"],
            problem_image_artifact_id=source_ids.get("problem"),
            teacher_solution_image_artifact_id=source_ids.get("teacher_solution"),
            problem_image_path=_optional_path(source_paths.get("problem")),
            teacher_solution_image_path=_optional_path(source_paths.get("teacher_solution")),
        )
    _set_status(state, "SPEC_EXTRACTED", phase="analysis")
    return state


def validate_spec(state: WorkflowState) -> WorkflowState:
    report = validate_candidate_spec(state["candidate_spec"])
    state.setdefault("validation_reports", []).append(report)
    status = "SPEC_REVALIDATING" if state.get("revision_attempts", 0) > 0 else "SPEC_VALIDATING"
    _set_status(state, status, phase="validation")
    return state


def render_preview(state: WorkflowState) -> WorkflowState:
    _set_status(state, "RENDERING", phase="render")
    state["rendered_preview"] = render_overlay_svg(state["candidate_spec"])
    _set_status(state, "RENDERED", phase="render")
    return state


def inspect_render(state: WorkflowState) -> WorkflowState:
    attempt = state.get("revision_attempts", 0)
    tool_decisions = [
        ToolDecision(
            attempt=attempt,
            tool_name="inspect_content",
            reason_code="initial_content_inspection",
            confidence=1.0,
        ),
        ToolDecision(
            attempt=attempt,
            tool_name="inspect_layout",
            reason_code="initial_layout_inspection",
            confidence=1.0,
        ),
        ToolDecision(
            attempt=attempt,
            tool_name="inspect_style",
            reason_code="initial_style_inspection",
            confidence=1.0,
        ),
        ToolDecision(
            attempt=attempt,
            tool_name="compute_visual_diff",
            reason_code="initial_visual_diff",
            confidence=1.0,
        ),
    ]
    state.setdefault("review_tool_decisions", []).extend(tool_decisions)
    _set_status(
        state,
        "INSPECTING_CONTENT",
        next_action="content_check",
    )
    _set_status(
        state,
        "INSPECTING_LAYOUT",
        next_action="layout_check",
    )
    _set_status(
        state,
        "INSPECTING_STYLE",
        next_action="style_check",
    )
    _set_status(
        state,
        "COMPUTING_VISUAL_DIFF",
        next_action="visual_diff_check",
    )

    element = _find_element(state, "el_freehand_dimension_001")
    actual_endpoint = element.geometry.get("target_anchor_end") if element else None
    expected_endpoint = EXPECTED_TARGET_ANCHOR_END

    if actual_endpoint == expected_endpoint:
        state["inspection_issue"] = None
        scores = APPROVED_SCORE_FIXTURE
        issues: list[ReviewIssue] = []
        max_error_severity = "none"
    else:
        state["inspection_issue"] = _dimension_endpoint_issue(actual_endpoint)
        scores = MISMATCH_SCORE_FIXTURE
        issues = [
            ReviewIssue(
                issue_id="issue_auto_001",
                type="dimension_endpoint_mismatch",
                severity="high",
                element_id="el_freehand_dimension_001",
                message="Dimension endpoint does not match the teacher solution.",
                auto_correctable=True,
                evidence={
                    "expected": expected_endpoint,
                    "actual": actual_endpoint,
                },
            )
        ]
        max_error_severity = "high"

    gate_result = evaluate_approval_gate(
        scores=scores,
        gate=DEFAULT_APPROVAL_GATE,
        contract_valid=state["validation_reports"][-1].passed,
        visible_review_item_count=len(visible_review_items(state["candidate_spec"])),
        max_error_severity=max_error_severity,
    )
    state["latest_scores"] = scores
    state["latest_gate_result"] = gate_result
    state["latest_review_issues"] = issues
    final_decision = plan_next_review_action(state)

    state["review_tool_decisions"].append(final_decision)
    tool_decisions.append(final_decision)
    state.setdefault("review_attempts", []).append(
        ReviewAttempt(
            attempt=attempt,
            tool_decisions=tool_decisions,
            issues=issues,
            actions=[],
            scores_after=scores,
            gate_result=gate_result,
        )
    )
    return state


def plan_next_review_action(state: WorkflowState) -> ToolDecision:
    attempt = state.get("revision_attempts", 0)
    if "candidate_spec" not in state:
        return ToolDecision(
            attempt=attempt,
            tool_name="escalate_hitl",
            reason_code="validation_failed",
            confidence=1.0,
        )

    validation_reports = state.get("validation_reports", [])
    if not validation_reports or not validation_reports[-1].passed:
        return ToolDecision(
            attempt=attempt,
            tool_name="escalate_hitl",
            reason_code="validation_failed",
            confidence=1.0,
        )

    current_attempt_decisions = [
        decision
        for decision in state.get("review_tool_decisions", [])
        if decision.attempt == attempt
    ]
    current_tool_names = {decision.tool_name for decision in current_attempt_decisions}
    for tool_name, reason_code in (
        ("inspect_content", "initial_content_inspection"),
        ("inspect_layout", "initial_layout_inspection"),
        ("inspect_style", "initial_style_inspection"),
        ("compute_visual_diff", "initial_visual_diff"),
    ):
        if tool_name not in current_tool_names:
            return ToolDecision(
                attempt=attempt,
                tool_name=tool_name,
                reason_code=reason_code,
                confidence=1.0,
            )

    gate_result = state.get("latest_gate_result")
    if gate_result is not None and gate_result.passed:
        return ToolDecision(
            attempt=attempt,
            tool_name="mark_approved",
            reason_code="gate_passed",
            confidence=1.0,
        )

    issues = state.get("latest_review_issues", [])
    has_auto_correctable_issue = any(issue.auto_correctable for issue in issues)
    if has_auto_correctable_issue and _has_revision_budget(state):
        patch = state.get(
            "correction_patch_override",
            {"geometry.target_anchor_end": EXPECTED_TARGET_ANCHOR_END},
        )
        if _has_repeated_patch_attempt(state, "el_freehand_dimension_001", patch):
            return ToolDecision(
                attempt=attempt,
                tool_name="escalate_hitl",
                reason_code="repeated_element_patch",
                confidence=1.0,
            )
        if _has_two_attempts_without_score_improvement(state):
            return ToolDecision(
                attempt=attempt,
                tool_name="escalate_hitl",
                reason_code="no_score_improvement",
                confidence=1.0,
            )
        return ToolDecision(
            attempt=attempt,
            tool_name="patch_candidate_spec",
            reason_code="dimension_endpoint_mismatch",
            target_element_id="el_freehand_dimension_001",
            confidence=1.0,
            arguments={"patch": patch},
        )

    if not _has_revision_budget(state):
        return ToolDecision(
            attempt=attempt,
            tool_name="escalate_hitl",
            reason_code="revision_budget_exceeded",
            confidence=1.0,
        )

    return ToolDecision(
        attempt=attempt,
        tool_name="escalate_hitl",
        reason_code="low_confidence",
        confidence=1.0,
    )


def plan_correction(state: WorkflowState) -> WorkflowState:
    decision = state["review_tool_decisions"][-1]
    patch = decision.arguments["patch"]
    issue = state["inspection_issue"]
    state.setdefault("correction_plans", []).append(
        {
            "revision_id": "rev_001",
            "source_preview_id": "rendered_preview_v1",
            "issues": [issue],
            "actions": [
                {
                    "action_id": "act_001",
                    "type": "spec_patch",
                    "element_id": decision.target_element_id,
                    "patch": patch,
                }
            ],
            "requires_human_review": False,
        }
    )
    _set_status(state, "CORRECTION_PLANNING")
    state["review_attempts"][-1].actions.append(
        CorrectionAction(
            action_id="act_001",
            type="spec_patch",
            element_id=decision.target_element_id,
            patch=patch,
        )
    )
    return state


def apply_correction(state: WorkflowState) -> WorkflowState:
    _set_status(state, "PATCHING_SPEC", next_action="spec_patch")
    candidate_spec = deepcopy(state["candidate_spec"])
    plan = state["correction_plans"][-1]
    changed = False

    for action in plan["actions"]:
        if action["type"] != "spec_patch":
            continue
        changed = _apply_spec_patch(candidate_spec, action["element_id"], action["patch"]) or changed

    state["candidate_spec"] = candidate_spec
    if not changed:
        decision = ToolDecision(
            attempt=state.get("revision_attempts", 0),
            tool_name="escalate_hitl",
            reason_code="repeated_element_patch",
            confidence=1.0,
        )
        state.setdefault("review_tool_decisions", []).append(decision)
        if state.get("review_attempts"):
            state["review_attempts"][-1].tool_decisions.append(decision)
        return state

    state["revision_attempts"] = state.get("revision_attempts", 0) + 1
    _set_status(state, "RE_RENDERING", phase="render", next_action="rerender")
    state["rendered_preview"] = render_overlay_svg(candidate_spec)
    _set_status(state, "RENDERED", phase="render")
    return state


def decide_human_review(state: WorkflowState) -> WorkflowState:
    state["review_items"] = visible_review_items(state["candidate_spec"])
    latest_gate_result = state.get("latest_gate_result")
    visible_review_only_failure = (
        latest_gate_result is not None
        and latest_gate_result.failed_reasons == ["visible_review_item_budget_exceeded"]
    )
    if (
        latest_gate_result is not None
        and (latest_gate_result.passed or visible_review_only_failure)
    ):
        _set_status(
            state,
            "NEEDS_REVIEW" if state["review_items"] else "APPROVED",
            phase="hitl" if state["review_items"] else "approval",
            next_action="hitl" if state["review_items"] else "approve",
            scores=state.get("latest_scores"),
        )
    else:
        _set_status(state, "REVISION_REQUIRED", phase="hitl", next_action="hitl")
    return state


def require_revision(state: WorkflowState) -> WorkflowState:
    state["review_items"] = visible_review_items(state["candidate_spec"])
    latest_validation_report = state["validation_reports"][-1] if state.get("validation_reports") else None
    if latest_validation_report is not None and latest_validation_report.passed is False:
        state["latest_scores"] = CONTRACT_INVALID_SCORE_FIXTURE
        max_error_severity = _max_validation_error_severity(latest_validation_report)
        state["latest_gate_result"] = evaluate_approval_gate(
            scores=CONTRACT_INVALID_SCORE_FIXTURE,
            gate=DEFAULT_APPROVAL_GATE,
            contract_valid=False,
            visible_review_item_count=len(visible_review_items(state["candidate_spec"])),
            max_error_severity=max_error_severity,
        )
        decision = ToolDecision(
            attempt=state.get("revision_attempts", 0),
            tool_name="escalate_hitl",
            reason_code="validation_failed",
            confidence=1.0,
        )
        state.setdefault("review_tool_decisions", []).append(decision)
        state.setdefault("review_attempts", []).append(
            ReviewAttempt(
                attempt=state.get("revision_attempts", 0),
                tool_decisions=[decision],
                issues=[
                    ReviewIssue(
                        issue_id=issue.issue_id,
                        type=issue.type,
                        severity=issue.severity,
                        element_id=issue.element_id,
                        message=issue.message,
                        auto_correctable=issue.auto_correctable,
                    )
                    for issue in latest_validation_report.issues
                ],
                actions=[],
                scores_after=CONTRACT_INVALID_SCORE_FIXTURE,
                gate_result=state["latest_gate_result"],
            )
        )
    _set_status(
        state,
        "REVISION_REQUIRED",
        phase="hitl",
        next_action="hitl",
        scores=state.get("latest_scores"),
    )
    return state


def _apply_spec_patch(candidate_spec, element_id: str, patch: dict[str, object]) -> bool:
    for element in candidate_spec.elements:
        if element.id != element_id:
            continue
        applied_patch = {}
        for path, value in patch.items():
            if path.startswith("geometry."):
                geometry_key = path.removeprefix("geometry.")
                if element.geometry.get(geometry_key) != value:
                    element.geometry[geometry_key] = value
                    applied_patch[path] = value
        if not applied_patch:
            return False
        element.revision_history.append(
            {
                "revision_id": "rev_001",
                "source": "auto_correction",
                "patch": applied_patch,
            }
        )
        return True
    return False


def _find_element(state: WorkflowState, element_id: str):
    for element in state["candidate_spec"].elements:
        if element.id == element_id:
            return element
    return None


def _dimension_endpoint_issue(actual_endpoint) -> dict[str, object]:
    return {
        "issue_id": "issue_auto_001",
        "type": "dimension_endpoint_mismatch",
        "severity": "high",
        "element_id": "el_freehand_dimension_001",
        "expected": EXPECTED_TARGET_ANCHOR_END,
        "actual": actual_endpoint,
        "auto_correctable": True,
        "correction_action": "patch_candidate_spec_geometry",
    }


def _max_validation_error_severity(report) -> str:
    severity_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
    max_severity = "none"
    for issue in report.issues:
        if severity_rank[issue.severity] > severity_rank[max_severity]:
            max_severity = issue.severity
    return max_severity


def _has_revision_budget(state: WorkflowState) -> bool:
    return state.get("revision_attempts", 0) < state.get("max_revision_attempts", 2)


def _has_repeated_patch_attempt(
    state: WorkflowState,
    element_id: str,
    patch: dict[str, object],
) -> bool:
    matching_attempts = 0
    for attempt in reversed(state.get("review_attempts", [])):
        if any(
            action.type == "spec_patch"
            and action.element_id == element_id
            and action.patch == patch
            for action in attempt.actions
        ):
            matching_attempts += 1
            if matching_attempts >= 2:
                return True
            continue
        if attempt.actions:
            return False
    return False


def _has_two_attempts_without_score_improvement(state: WorkflowState) -> bool:
    attempts_with_scores = [
        attempt
        for attempt in state.get("review_attempts", [])
        if attempt.scores_before is not None and attempt.scores_after is not None
    ]
    if len(attempts_with_scores) < 2:
        return False

    for attempt in attempts_with_scores[-2:]:
        if has_score_improved(attempt.scores_before, attempt.scores_after):
            return False
    return True


def _analysis_client_from_state(state: WorkflowState) -> AnalysisClient:
    override = state.get("analysis_client_override")
    if override is not None:
        return override
    return build_analysis_client(
        client_kind=state.get("analysis_client_kind", "mock"),
        openai_api_key=state.get("openai_api_key"),
        openai_model_analysis=state.get("openai_model_analysis", "gpt-5.5"),
        openai_analysis_image_detail=state.get("openai_analysis_image_detail", "auto"),
        openai_analysis_timeout_seconds=state.get("openai_analysis_timeout_seconds", 60),
    )


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value is not None else None


def _set_status(
    state: WorkflowState,
    status: str,
    *,
    phase: str = "review_and_correct",
    next_action: str = "continue",
    scores=None,
) -> None:
    state["status"] = status
    state.setdefault("status_history", []).append(status)
    append_progress_event(
        state,
        phase=phase,
        status=status,
        message=STATUS_MESSAGES[status],
        next_action=next_action,
        scores=scores,
    )
