from typing import Any, TypedDict


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
