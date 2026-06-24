import json
import re
import time
from collections.abc import Iterable

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ValidationError

from cleansolve_api.artifacts import (
    LocalArtifactStore,
    ImageRole,
    export_job_not_ready_error,
    export_render_not_ready_error,
    export_source_changed_error,
    export_spec_not_ready_error,
    job_response,
    job_run_submit_failed_error,
    missing_required_images_error,
    render_artifact_not_found_error,
    spec_not_ready_error,
    spec_patch_rejected_error,
    spec_version_conflict_error,
    storage_write_failed_error,
    unsupported_export_format_error,
)
from cleansolve_api.background import JobRunExecutor, JobRunRequest, failed_progress_event, run_job_worker
from cleansolve_api.live_progress import LiveProgressStore, cursor_sequence
from cleansolve_api.settings import settings
from cleansolve_api.spec_patch import SpecPatchRejected, SpecPatchRequest, apply_spec_patch
from cleansolve_renderer.export_png import render_export_png
from cleansolve_renderer.overlay import render_overlay_svg
from cleansolve_spec.models import CandidateSpec
from cleansolve_spec.validation import validate_candidate_spec
from cleansolve_workflow import ProgressEvent

router = APIRouter(prefix="/jobs", tags=["jobs"])

SSE_EVENT_ID_PATTERN = re.compile(r"^evt_\d{4,}$")
TERMINAL_SUCCESS_STATUSES = {"APPROVED", "NEEDS_REVIEW", "REVISION_REQUIRED"}
TERMINAL_STATUSES = TERMINAL_SUCCESS_STATUSES | {"FAILED", "CANCELLED"}
PROGRESS_EVENT_PUBLIC_FIELDS = (
    "event_id",
    "job_id",
    "sequence",
    "phase",
    "status",
    "message",
    "attempt",
    "max_attempts",
    "scores",
    "next_action",
    "created_at",
)

job_run_executor = JobRunExecutor(max_workers=settings.background_max_workers)


def _store() -> LocalArtifactStore:
    return LocalArtifactStore(settings.storage_root)


def _live_progress_store() -> LiveProgressStore:
    return LiveProgressStore(settings.storage_root)


def _source_image_artifact_ids_from_spec(spec: CandidateSpec) -> dict[ImageRole, str]:
    return {
        "problem": spec.source_images["problem_image_id"],
        "teacher_solution": spec.source_images["teacher_solution_image_id"],
    }


def _safe_sse_event_id(value: str) -> str | None:
    if SSE_EVENT_ID_PATTERN.fullmatch(value) is None:
        return None
    return value


def _public_progress_event(event: dict[str, object]) -> dict[str, object] | None:
    projected = {field: event.get(field) for field in PROGRESS_EVENT_PUBLIC_FIELDS}
    try:
        validated = ProgressEvent.model_validate(projected)
    except ValidationError:
        return None
    event_id = _safe_sse_event_id(validated.event_id)
    if event_id is None:
        return None
    payload = validated.model_dump(mode="json")
    payload["event_id"] = event_id
    return payload


def _sse_frame(
    *,
    event: str,
    data: dict[str, object],
    event_id: str | None = None,
) -> str:
    lines = []
    if event_id is not None:
        safe_event_id = _safe_sse_event_id(event_id)
        if safe_event_id is not None:
            lines.append(f"id: {safe_event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


def _progress_event_stream(payload: dict[str, object], after: str | None = None) -> Iterable[str]:
    events = payload.get("events")
    if not isinstance(events, list):
        events = []
    after_sequence = cursor_sequence(after)
    projected_events = [
        projected
        for event in events
        if isinstance(event, dict)
        for projected in [_public_progress_event(event)]
        if projected is not None
        and (after_sequence is None or int(projected["sequence"]) > after_sequence)
    ]
    sorted_events = sorted(projected_events, key=lambda event: event["sequence"])
    for event in sorted_events:
        yield _sse_frame(
            event="progress",
            event_id=event["event_id"],
            data=event,
        )
    yield _sse_frame(
        event="complete",
        data={
            "job_id": payload.get("job_id") if isinstance(payload.get("job_id"), str) else "",
            "status": "APPROVED",
            "event_count": len(sorted_events),
        },
    )


def _failed_terminal_reason(job_id: str) -> str:
    try:
        manifest = _store().get_job(job_id)
    except HTTPException:
        return "internal_error"
    for item in reversed(manifest.review_items):
        reason = item.get("safe_reason") if isinstance(item, dict) else None
        if reason in {
            "configuration_error",
            "response_error",
            "internal_error",
            "progress_write_failed",
            "analysis_source_changed",
        }:
            return reason
    return "internal_error"


def _terminal_sse_event(status_value: str) -> str:
    if status_value in TERMINAL_SUCCESS_STATUSES:
        return "complete"
    if status_value == "CANCELLED":
        return "cancelled"
    return "failed"


def _terminal_sse_data(job_id: str, status_value: str, event_count: int) -> dict[str, object]:
    data: dict[str, object] = {
        "job_id": job_id,
        "status": status_value,
        "event_count": event_count,
    }
    if status_value == "FAILED":
        data["reason"] = _failed_terminal_reason(job_id)
    if status_value == "CANCELLED":
        data["reason"] = "cancelled"
    return data


def _live_progress_event_stream(job_id: str, after: str | None = None) -> Iterable[str]:
    live_store = _live_progress_store()
    sent_ids: set[str] = set()
    last_heartbeat = time.monotonic()
    while True:
        manifest = _store().get_job(job_id)
        events = live_store.read_events(job_id, after=after)
        for event in events:
            event_id = event["event_id"]
            if event_id in sent_ids:
                continue
            sent_ids.add(event_id)
            yield _sse_frame(event="progress", event_id=event_id, data=event)
        if manifest.status in TERMINAL_STATUSES:
            yield _sse_frame(
                event=_terminal_sse_event(manifest.status),
                data=_terminal_sse_data(job_id, manifest.status, len(events)),
            )
            return
        if time.monotonic() - last_heartbeat >= settings.progress_heartbeat_seconds:
            last_heartbeat = time.monotonic()
            yield ": keep-alive\n\n"
        time.sleep(settings.progress_poll_interval_ms / 1000)


class ExportRequest(BaseModel):
    format: str = "png"


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job() -> dict[str, object]:
    return job_response(_store().create_job())


@router.post("/{job_id}/images/problem", status_code=status.HTTP_201_CREATED)
async def upload_problem_image(job_id: str, file: UploadFile = File(...)) -> dict[str, object]:
    manifest, artifact = await _store().save_image(job_id, "problem", file)
    return {
        "job_id": manifest.job_id,
        "role": "problem",
        "artifact": artifact.model_dump(mode="json"),
        "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
    }


@router.post("/{job_id}/images/teacher-solution", status_code=status.HTTP_201_CREATED)
async def upload_teacher_solution_image(job_id: str, file: UploadFile = File(...)) -> dict[str, object]:
    manifest, artifact = await _store().save_image(job_id, "teacher_solution", file)
    return {
        "job_id": manifest.job_id,
        "role": "teacher_solution",
        "artifact": artifact.model_dump(mode="json"),
        "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
    }


@router.post("/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
def run_job(job_id: str) -> dict[str, object]:
    store = _store()
    manifest = store.get_job(job_id)
    missing_roles = [
        role
        for role, artifact_id in manifest.latest_image_artifact_ids.items()
        if artifact_id is None
    ]
    if missing_roles:
        raise missing_required_images_error(missing_roles)

    source_image_artifact_ids = {
        "problem": manifest.latest_image_artifact_ids["problem"],
        "teacher_solution": manifest.latest_image_artifact_ids["teacher_solution"],
    }
    running_manifest = store.start_analysis_run(
        job_id,
        source_image_artifact_ids=source_image_artifact_ids,
    )
    live_store = _live_progress_store()
    try:
        live_store.initialize(job_id, source_image_artifact_ids)
        job_run_executor.submit(
            JobRunRequest(
                job_id=job_id,
                source_image_artifact_ids=source_image_artifact_ids,
                analysis_client_kind=settings.analysis_client,
                openai_model_analysis=settings.openai_model_analysis,
                openai_analysis_image_detail=settings.openai_analysis_image_detail,
                openai_analysis_timeout_seconds=settings.openai_analysis_timeout_seconds,
            )
        )
    except OSError as exc:
        failed_event = failed_progress_event(job_id)
        store.save_failed_background_run(
            job_id,
            reason="progress_write_failed",
            review_item={
                "type": "analysis_adapter_failed",
                "client": settings.analysis_client,
                "retryable": True,
                "review_reason": None,
            },
            progress_events_payload={"job_id": job_id, "events": [failed_event.model_dump(mode="json")]},
            source_image_artifact_ids=source_image_artifact_ids,
        )
        raise storage_write_failed_error() from exc
    except Exception as exc:
        failed_event = failed_progress_event(job_id)
        try:
            live_store.append(job_id, failed_event)
            progress_events_payload = live_store.progress_events_payload(job_id)
        except Exception:
            progress_events_payload = {"job_id": job_id, "events": [failed_event.model_dump(mode="json")]}
        store.save_failed_background_run(
            job_id,
            reason="internal_error",
            review_item={
                "type": "analysis_adapter_failed",
                "client": settings.analysis_client,
                "retryable": True,
                "review_reason": None,
            },
            progress_events_payload=progress_events_payload,
            source_image_artifact_ids=source_image_artifact_ids,
        )
        raise job_run_submit_failed_error(job_id) from exc
    return job_response(running_manifest)


@router.post("/{job_id}/export")
def export_job(job_id: str, request: ExportRequest | None = None) -> dict[str, object]:
    resolved_request = request or ExportRequest()
    if resolved_request.format != "png":
        raise unsupported_export_format_error(resolved_request.format)

    store = _store()
    manifest = store.get_job(job_id)
    if manifest.status != "APPROVED":
        raise export_job_not_ready_error(manifest.status)

    candidate_spec_artifact_id = manifest.latest_analysis_artifact_ids["candidate_spec"]
    if candidate_spec_artifact_id is None:
        raise export_spec_not_ready_error()
    if manifest.latest_render_artifact_id is None:
        raise export_render_not_ready_error()

    spec = CandidateSpec.model_validate(
        store.read_latest_analysis_payload(job_id, "candidate_spec")
    )
    expected_source_image_artifact_ids = _source_image_artifact_ids_from_spec(spec)
    if expected_source_image_artifact_ids != manifest.latest_image_artifact_ids:
        raise export_source_changed_error(
            {
                "source_image_artifact_ids": expected_source_image_artifact_ids,
                "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
            }
        )

    try:
        _, render_artifact, svg = store.latest_render_artifact(job_id)
    except HTTPException as exc:
        if exc.detail == render_artifact_not_found_error().detail:
            raise export_render_not_ready_error() from exc
        raise

    if render_artifact.candidate_spec_artifact_id != candidate_spec_artifact_id:
        raise export_render_not_ready_error(
            {
                "render_candidate_spec_artifact_id": render_artifact.candidate_spec_artifact_id,
                "latest_candidate_spec_artifact_id": candidate_spec_artifact_id,
            }
        )
    if render_artifact.source_image_artifact_ids != manifest.latest_image_artifact_ids:
        raise export_source_changed_error(
            {
                "render_source_image_artifact_ids": render_artifact.source_image_artifact_ids,
                "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
            }
        )

    try:
        png_bytes = render_export_png(
            width=spec.page.width,
            height=spec.page.height,
            svg=svg,
            metadata={
                "CleanSolve-Candidate-Spec-Artifact-ID": candidate_spec_artifact_id,
                "CleanSolve-Job-ID": job_id,
                "CleanSolve-Render-Artifact-ID": render_artifact.artifact_id,
            },
        )
    except ValueError as exc:
        raise export_render_not_ready_error({"reason": str(exc)}) from exc

    updated_manifest, export_artifact = store.save_export_artifact(
        job_id=job_id,
        png_bytes=png_bytes,
        candidate_spec_artifact_id=candidate_spec_artifact_id,
        render_artifact_id=render_artifact.artifact_id,
        source_image_artifact_ids=manifest.latest_image_artifact_ids,
    )
    return {
        "job_id": job_id,
        "artifact": export_artifact.model_dump(mode="json"),
        "latest_export_artifact_id": updated_manifest.latest_export_artifact_id,
    }


@router.get("/{job_id}/exports")
def get_exports(job_id: str) -> dict[str, object]:
    return _store().export_artifacts_response(job_id)


@router.get("/{job_id}/exports/latest")
def get_latest_export(job_id: str) -> dict[str, object]:
    return _store().latest_export_response(job_id)


@router.get("/{job_id}/exports/{export_id}/download")
def download_export(job_id: str, export_id: str) -> FileResponse:
    artifact, path = _store().export_download(job_id, export_id)
    return FileResponse(
        path,
        media_type=artifact.mime_type,
        filename=f"{artifact.artifact_id}.png",
    )


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    return job_response(_store().get_job(job_id))


@router.get("/{job_id}/artifacts")
def get_analysis_artifacts(job_id: str) -> dict[str, object]:
    return _store().analysis_artifacts_response(job_id)


@router.patch("/{job_id}/spec")
def patch_candidate_spec(job_id: str, request: SpecPatchRequest) -> dict[str, object]:
    store = _store()
    manifest = store.get_job(job_id)
    candidate_spec_artifact_id = manifest.latest_analysis_artifact_ids["candidate_spec"]
    if candidate_spec_artifact_id is None:
        raise spec_not_ready_error()

    spec = CandidateSpec.model_validate(
        store.read_latest_analysis_payload(job_id, "candidate_spec")
    )
    if request.client_spec_version != spec.version:
        raise spec_version_conflict_error(
            client_spec_version=request.client_spec_version,
            server_spec_version=spec.version,
        )

    try:
        patched_spec = apply_spec_patch(spec, request)
    except SpecPatchRejected as exc:
        raise spec_patch_rejected_error(exc.fields()) from exc

    validation_report = validate_candidate_spec(patched_spec)
    if not validation_report.passed:
        raise spec_patch_rejected_error(
            {
                "element_id": request.element_id,
                "reason": "validation_failed",
                "issues": [
                    issue.model_dump(mode="json") for issue in validation_report.issues
                ],
            }
        )

    updated_manifest = store.save_spec_patch_outputs(
        job_id=job_id,
        candidate_spec_payload=patched_spec.model_dump(mode="json"),
        validation_report_payload=validation_report.model_dump(mode="json"),
        source_image_artifact_ids=_source_image_artifact_ids_from_spec(patched_spec),
        expected_candidate_spec_artifact_id=candidate_spec_artifact_id,
    )
    return {
        "job_id": job_id,
        "candidate_spec": patched_spec.model_dump(mode="json"),
        "validation_report": validation_report.model_dump(mode="json"),
        "candidate_spec_artifact_id": updated_manifest.latest_analysis_artifact_ids[
            "candidate_spec"
        ],
        "validation_report_artifact_id": updated_manifest.latest_analysis_artifact_ids[
            "validation_report"
        ],
        "latest_analysis_artifact_ids": updated_manifest.latest_analysis_artifact_ids,
    }


@router.post("/{job_id}/render")
def render_job_preview(job_id: str) -> dict[str, object]:
    store = _store()
    manifest = store.get_job(job_id)
    candidate_spec_artifact_id = manifest.latest_analysis_artifact_ids["candidate_spec"]
    if candidate_spec_artifact_id is None:
        raise spec_not_ready_error()

    spec = CandidateSpec.model_validate(
        store.read_latest_analysis_payload(job_id, "candidate_spec")
    )
    svg = render_overlay_svg(spec)
    _, artifact = store.save_render_artifact(
        job_id=job_id,
        svg=svg,
        candidate_spec_artifact_id=candidate_spec_artifact_id,
        source_image_artifact_ids=_source_image_artifact_ids_from_spec(spec),
    )
    return {
        "job_id": job_id,
        "artifact": artifact.model_dump(mode="json"),
        "svg": svg,
    }


@router.get("/{job_id}/rendered-preview")
def get_rendered_preview(job_id: str) -> dict[str, object]:
    return _store().rendered_preview_response(job_id)


@router.get("/{job_id}/candidate-spec")
def get_candidate_spec(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "candidate_spec")


@router.get("/{job_id}/validation-report")
def get_validation_report(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "validation_report")


@router.get("/{job_id}/correction-plan")
def get_correction_plan(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "correction_plan")


@router.get("/{job_id}/review-correction")
def get_review_correction(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "review_correction")


@router.get("/{job_id}/progress-events")
def get_progress_events(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "progress_events")


@router.get("/{job_id}/progress-stream")
def stream_progress_events(
    job_id: str,
    after: str | None = Query(default=None),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    cursor = after or last_event_id
    store = _store()
    manifest = store.get_job(job_id)
    live_store = _live_progress_store()
    if manifest.status == "RUNNING" and live_store.exists(job_id):
        stream = _live_progress_event_stream(job_id, cursor)
    elif manifest.status in TERMINAL_STATUSES and live_store.exists(job_id):
        stream = _live_progress_event_stream(job_id, cursor)
    else:
        payload = store.read_latest_analysis_payload(job_id, "progress_events")
        stream = _progress_event_stream(payload, cursor)
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}/review-items")
def get_review_items(job_id: str) -> dict[str, list[dict[str, object]]]:
    manifest = _store().get_job(job_id)
    visible_items = [
        item for item in manifest.review_items if item.get("review_reason")
    ]
    return {"items": visible_items}
