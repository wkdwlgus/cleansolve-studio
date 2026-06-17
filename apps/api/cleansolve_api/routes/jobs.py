from fastapi import APIRouter, File, UploadFile, status

from cleansolve_api.artifacts import (
    LocalArtifactStore,
    ImageRole,
    job_response,
    missing_required_images_error,
    spec_not_ready_error,
    spec_patch_rejected_error,
    spec_version_conflict_error,
)
from cleansolve_api.settings import settings
from cleansolve_api.spec_patch import SpecPatchRejected, SpecPatchRequest, apply_spec_patch
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
