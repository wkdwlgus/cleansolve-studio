from fastapi import APIRouter, File, UploadFile, status

from cleansolve_api.artifacts import (
    LocalArtifactStore,
    job_response,
    missing_required_images_error,
)
from cleansolve_api.settings import settings
from cleansolve_workflow.graph import run_mock_workflow

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _store() -> LocalArtifactStore:
    return LocalArtifactStore(settings.storage_root)


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
