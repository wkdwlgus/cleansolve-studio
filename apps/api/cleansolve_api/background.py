from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from pydantic import BaseModel

from cleansolve_ai import OpenAIAdapterError, OpenAIConfigurationError
from cleansolve_workflow import ProgressEvent, run_mock_workflow

from .artifacts import ImageRole, LocalArtifactStore
from .live_progress import LiveProgressStore, utc_now
from .settings import settings

SAFE_FAILURE_REASONS = {
    "configuration_error",
    "response_error",
    "internal_error",
    "progress_write_failed",
    "analysis_source_changed",
}


class JobRunRequest(BaseModel):
    job_id: str
    source_image_artifact_ids: dict[ImageRole, str]
    analysis_client_kind: str
    openai_model_analysis: str
    openai_analysis_image_detail: str
    openai_analysis_timeout_seconds: int


def safe_adapter_reason(exc: OpenAIAdapterError) -> str:
    if isinstance(exc, OpenAIConfigurationError):
        return "configuration_error"
    return "response_error"


def failed_progress_event(job_id: str) -> ProgressEvent:
    return ProgressEvent(
        event_id="evt_9999",
        job_id=job_id,
        sequence=9999,
        phase="failed",
        status="FAILED",
        message="작업이 실패했습니다.",
        attempt=0,
        max_attempts=2,
        scores=None,
        next_action="fail",
        created_at=utc_now(),
    )


def _safe_reason(reason: str) -> str:
    if reason in SAFE_FAILURE_REASONS:
        return reason
    return "internal_error"


def run_job_worker(
    request: JobRunRequest,
    *,
    store: LocalArtifactStore | None = None,
    live_progress_store: LiveProgressStore | None = None,
    openai_api_key: str | None = None,
) -> None:
    resolved_store = store or LocalArtifactStore(settings.storage_root)
    resolved_live_store = live_progress_store or LiveProgressStore(settings.storage_root)
    reason = "internal_error"
    try:
        manifest = resolved_store.get_job(request.job_id)
        if manifest.status != "RUNNING":
            return
        source_image_paths = {
            role: str(path)
            for role, path in resolved_store.latest_image_artifact_paths(request.job_id).items()
        }
        state = run_mock_workflow(
            job_id=request.job_id,
            source_image_artifact_ids=request.source_image_artifact_ids,
            source_image_paths=source_image_paths,
            analysis_client_kind=request.analysis_client_kind,
            openai_api_key=openai_api_key,
            openai_model_analysis=request.openai_model_analysis,
            openai_analysis_image_detail=request.openai_analysis_image_detail,
            openai_analysis_timeout_seconds=request.openai_analysis_timeout_seconds,
            progress_event_sink=lambda event: resolved_live_store.append(request.job_id, event),
        )
        review_correction_payload = {
            "job_id": request.job_id,
            "review_attempts": [
                attempt.model_dump(mode="json") for attempt in state.get("review_attempts", [])
            ],
            "tool_decisions": [
                decision.model_dump(mode="json")
                for decision in state.get("review_tool_decisions", [])
            ],
            "latest_gate_result": (
                state["latest_gate_result"].model_dump(mode="json")
                if state.get("latest_gate_result") is not None
                else None
            ),
            "revision_attempts": state["revision_attempts"],
        }
        resolved_store.save_analysis_outputs(
            job_id=request.job_id,
            status_value=state["status"],
            revision_attempts=state["revision_attempts"],
            review_items=list(state.get("review_items", [])),
            candidate_spec_payload=state["candidate_spec"].model_dump(mode="json"),
            validation_report_payload=state["validation_reports"][-1].model_dump(mode="json"),
            correction_plan_payload={
                "job_id": request.job_id,
                "revision_attempts": state["revision_attempts"],
                "correction_plans": state.get("correction_plans", []),
            },
            review_correction_payload=review_correction_payload,
            progress_events_payload=resolved_live_store.progress_events_payload(request.job_id),
            source_image_artifact_ids=request.source_image_artifact_ids,
        )
        return
    except OpenAIAdapterError as exc:
        reason = safe_adapter_reason(exc)
    except Exception:
        reason = "internal_error"

    try:
        resolved_live_store.append(request.job_id, failed_progress_event(request.job_id))
    except Exception:
        reason = "progress_write_failed"
    resolved_store.save_failed_background_run(
        request.job_id,
        reason=_safe_reason(reason),
        review_item={
            "type": "analysis_adapter_failed",
            "client": request.analysis_client_kind,
            "retryable": True,
            "review_reason": None,
        },
        progress_events_payload=resolved_live_store.progress_events_payload(request.job_id),
        source_image_artifact_ids=request.source_image_artifact_ids,
    )


class JobRunExecutor:
    def __init__(
        self,
        *,
        max_workers: int,
        worker: Callable[[JobRunRequest], None] | None = None,
    ):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._worker = worker or (lambda request: run_job_worker(request, openai_api_key=settings.openai_api_key))
        self._active: set[str] = set()
        self._lock = Lock()

    def submit(self, request: JobRunRequest) -> None:
        with self._lock:
            self._active.add(request.job_id)
        self._executor.submit(self._run_and_clear, request)

    def is_active(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._active

    def shutdown(self, *, wait: bool) -> None:
        self._executor.shutdown(wait=wait)

    def _run_and_clear(self, request: JobRunRequest) -> None:
        try:
            self._worker(request)
        finally:
            with self._lock:
                self._active.discard(request.job_id)
