from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ReviewToolName = Literal[
    "inspect_content",
    "inspect_layout",
    "inspect_style",
    "compute_visual_diff",
    "patch_candidate_spec",
    "request_handwriting_asset",
    "rerender",
    "mark_approved",
    "escalate_hitl",
]

ReviewPhase = Literal[
    "analysis",
    "validation",
    "render",
    "review_and_correct",
    "hitl",
    "approval",
    "export",
    "failed",
]

ProgressStatus = Literal[
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
    "REQUESTING_HANDWRITING_ASSET",
    "RE_RENDERING",
    "RE_INSPECTING",
    "APPROVED",
    "NEEDS_REVIEW",
    "REVISION_REQUIRED",
    "FAILED",
]

NextAction = Literal[
    "continue",
    "content_check",
    "layout_check",
    "style_check",
    "visual_diff_check",
    "spec_patch",
    "handwriting_asset",
    "rerender",
    "approve",
    "hitl",
    "fail",
]

ErrorSeverity = Literal["none", "low", "medium", "high"]


def _ensure_json_serializable(value: dict[str, Any]) -> dict[str, Any]:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("payload dict must be JSON serializable") from exc
    return value


class ReviewScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_consistency: float = Field(ge=0, le=1)
    layout_alignment: float = Field(ge=0, le=1)
    style_similarity: float = Field(ge=0, le=1)
    visual_diff: float = Field(ge=0, le=1)


class ApprovalGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_valid: bool
    content_consistency_threshold: float = Field(default=0.9, ge=0, le=1)
    layout_alignment_threshold: float = Field(default=0.85, ge=0, le=1)
    style_similarity_threshold: float = Field(default=0.7, ge=0, le=1)
    visual_diff_threshold: float = Field(default=0.25, ge=0, le=1)
    visible_review_item_budget: int = Field(default=0, ge=0)
    allowed_max_error_severity: ErrorSeverity = "low"


class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    failed_reasons: list[str]
    scores: ReviewScores
    contract_valid: bool
    visible_review_item_count: int = Field(ge=0)
    max_error_severity: ErrorSeverity


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    type: str
    severity: Literal["low", "medium", "high"]
    element_id: str | None = None
    message: str
    auto_correctable: bool
    evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("evidence")
    @classmethod
    def _evidence_must_be_json_serializable(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _ensure_json_serializable(value)


class ToolDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=0)
    tool_name: ReviewToolName
    reason_code: str
    target_element_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    arguments: dict[str, Any] = Field(default_factory=dict)

    @field_validator("arguments")
    @classmethod
    def _arguments_must_be_json_serializable(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _ensure_json_serializable(value)


class CorrectionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    type: Literal["spec_patch", "handwriting_asset_request", "rerender", "hitl", "approve"]
    element_id: str | None = None
    patch: dict[str, Any] = Field(default_factory=dict)
    asset_request: dict[str, Any] = Field(default_factory=dict)

    @field_validator("patch", "asset_request")
    @classmethod
    def _payload_dict_must_be_json_serializable(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _ensure_json_serializable(value)


class ReviewAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=0)
    tool_decisions: list[ToolDecision]
    issues: list[ReviewIssue]
    actions: list[CorrectionAction]
    scores_before: ReviewScores | None = None
    scores_after: ReviewScores | None = None
    gate_result: GateResult | None = None


class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    job_id: str
    sequence: int = Field(ge=0)
    phase: ReviewPhase
    status: ProgressStatus
    message: str
    attempt: int = Field(ge=0)
    max_attempts: int = Field(ge=0)
    scores: ReviewScores | None = None
    next_action: NextAction
    created_at: str


PROGRESS_MESSAGE_ALLOWLIST = frozenset(
    {
        "작업을 시작했습니다.",
        "기본 손글씨 스타일을 불러왔습니다.",
        "원본 문제와 선생님 손풀이를 분석하고 있습니다.",
        "candidate spec 계약을 검증하고 있습니다.",
        "deterministic renderer로 preview를 만들고 있습니다.",
        "렌더 결과의 풀이 내용을 확인하고 있습니다.",
        "렌더 결과의 위치와 치수선 정합성을 확인하고 있습니다.",
        "렌더 결과의 손글씨 스타일 일관성을 확인하고 있습니다.",
        "렌더 결과의 시각적 차이를 계산하고 있습니다.",
        "자동 수정 계획을 세우고 있습니다.",
        "candidate spec patch를 적용하고 있습니다.",
        "특정 손글씨 블록 asset 재생성이 필요합니다.",
        "수정된 spec으로 preview를 다시 렌더링하고 있습니다.",
        "자동 승인 기준을 통과했습니다.",
        "사용자 검수가 필요합니다.",
        "자동 수정 한도에 도달했습니다.",
        "작업이 실패했습니다.",
    }
)

DEFAULT_APPROVAL_GATE = ApprovalGate(contract_valid=True)

MISMATCH_SCORE_FIXTURE = ReviewScores(
    content_consistency=0.95,
    layout_alignment=0.6,
    style_similarity=0.78,
    visual_diff=0.18,
)

APPROVED_SCORE_FIXTURE = ReviewScores(
    content_consistency=0.95,
    layout_alignment=0.9,
    style_similarity=0.78,
    visual_diff=0.18,
)

CONTRACT_INVALID_SCORE_FIXTURE = ReviewScores(
    content_consistency=0.0,
    layout_alignment=0.0,
    style_similarity=0.0,
    visual_diff=1.0,
)


def append_progress_event(
    state: dict[str, Any],
    *,
    phase: ReviewPhase,
    status: ProgressStatus,
    message: str,
    next_action: NextAction,
    scores: ReviewScores | None = None,
) -> ProgressEvent:
    if message not in PROGRESS_MESSAGE_ALLOWLIST:
        raise ValueError("progress event message is not allowlisted")

    sequence = int(state["review_event_sequence"])
    event = ProgressEvent(
        event_id=f"evt_{sequence:04d}",
        job_id=state["job_id"],
        sequence=sequence,
        phase=phase,
        status=status,
        message=message,
        attempt=state["revision_attempts"],
        max_attempts=state["max_revision_attempts"],
        scores=scores,
        next_action=next_action,
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    state.setdefault("progress_events", []).append(event)
    state["review_event_sequence"] = sequence + 1
    return event


def evaluate_approval_gate(
    *,
    scores: ReviewScores,
    gate: ApprovalGate,
    contract_valid: bool,
    visible_review_item_count: int,
    max_error_severity: ErrorSeverity,
) -> GateResult:
    failed_reasons: list[str] = []
    severity_rank: dict[ErrorSeverity, int] = {
        "none": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
    }

    if gate.contract_valid and not contract_valid:
        failed_reasons.append("contract_invalid")
    if scores.content_consistency < gate.content_consistency_threshold:
        failed_reasons.append("content_consistency_below_threshold")
    if scores.layout_alignment < gate.layout_alignment_threshold:
        failed_reasons.append("layout_alignment_below_threshold")
    if scores.style_similarity < gate.style_similarity_threshold:
        failed_reasons.append("style_similarity_below_threshold")
    if scores.visual_diff > gate.visual_diff_threshold:
        failed_reasons.append("visual_diff_above_threshold")
    if visible_review_item_count > gate.visible_review_item_budget:
        failed_reasons.append("visible_review_item_budget_exceeded")
    if severity_rank[max_error_severity] > severity_rank[gate.allowed_max_error_severity]:
        failed_reasons.append("max_error_severity_exceeded")

    return GateResult(
        passed=not failed_reasons,
        failed_reasons=failed_reasons,
        scores=scores,
        contract_valid=contract_valid,
        visible_review_item_count=visible_review_item_count,
        max_error_severity=max_error_severity,
    )


def has_score_improved(previous: ReviewScores, current: ReviewScores) -> bool:
    return (
        current.content_consistency > previous.content_consistency
        or current.layout_alignment > previous.layout_alignment
        or current.style_similarity > previous.style_similarity
        or current.visual_diff < previous.visual_diff
    )
