from typing import Any, NotRequired, TypedDict


class WorkflowState(TypedDict, total=False):
    job_id: str
    status: str
    candidate_spec: Any
    validation_reports: list[Any]
    correction_plans: list[dict[str, Any]]
    revision_attempts: int
    max_revision_attempts: int
    review_items: list[dict[str, str]]
    rendered_preview: str
    style_preset: dict[str, str]
    inspection_issue: dict[str, Any] | None
    status_history: list[str]
    correction_patch_override: dict[str, Any]
    review_attempts: list[Any]
    progress_events: list[Any]
    latest_scores: Any
    latest_gate_result: Any
    latest_review_issues: list[Any]
    review_tool_decisions: list[Any]
    review_event_sequence: int
    source_image_artifact_ids: NotRequired[dict[str, str | None]]
    source_image_paths: NotRequired[dict[str, str]]
    analysis_client_kind: str
    openai_api_key: str | None
    openai_model_analysis: str
    openai_analysis_image_detail: str
    openai_analysis_timeout_seconds: int
    analysis_client_override: object
