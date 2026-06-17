from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from cleansolve_api.artifacts import (
    LocalArtifactStore,
    ImageRole,
    export_job_not_ready_error,
    export_render_not_ready_error,
    export_source_changed_error,
    export_spec_not_ready_error,
    job_response,
    missing_required_images_error,
    render_artifact_not_found_error,
    spec_not_ready_error,
    spec_patch_rejected_error,
    spec_version_conflict_error,
    unsupported_export_format_error,
)
from cleansolve_api.settings import settings
from cleansolve_api.spec_patch import SpecPatchRejected, SpecPatchRequest, apply_spec_patch
from cleansolve_renderer.export_png import render_export_png
from cleansolve_renderer.overlay import render_overlay_svg
from cleansolve_spec.models import CandidateSpec
from cleansolve_spec.validation import validate_candidate_spec
from cleansolve_workflow.graph import run_mock_workflow

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _store() -> LocalArtifactStore:
    return LocalArtifactStore(settings.storage_root)


def _source_image_artifact_ids_from_spec(spec: CandidateSpec) -> dict[ImageRole, str]:
    return {
        "problem": spec.source_images["problem_image_id"],
        "teacher_solution": spec.source_images["teacher_solution_image_id"],
    }


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


@router.post("/{job_id}/run")
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
    state = run_mock_workflow(
        job_id=job_id,
        source_image_artifact_ids=source_image_artifact_ids,
    )
    updated_manifest = store.save_analysis_outputs(
        job_id=job_id,
        status_value=state["status"],
        revision_attempts=state["revision_attempts"],
        review_items=list(state.get("review_items", [])),
        candidate_spec_payload=state["candidate_spec"].model_dump(mode="json"),
        validation_report_payload=state["validation_reports"][-1].model_dump(mode="json"),
        correction_plan_payload={
            "job_id": job_id,
            "revision_attempts": state["revision_attempts"],
            "correction_plans": state.get("correction_plans", []),
        },
        source_image_artifact_ids=source_image_artifact_ids,
    )
    return job_response(updated_manifest)


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


@router.get("/{job_id}/review-items")
def get_review_items(job_id: str) -> dict[str, list[dict[str, object]]]:
    manifest = _store().get_job(job_id)
    visible_items = [
        item for item in manifest.review_items if item.get("review_reason")
    ]
    return {"items": visible_items}
