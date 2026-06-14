from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from cleansolve_workflow.graph import run_mock_workflow

router = APIRouter(prefix="/jobs", tags=["jobs"])

_jobs: dict[str, dict[str, object]] = {}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job() -> dict[str, str]:
    job_id = f"job_{uuid4().hex}"
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "CREATED",
        "revision_attempts": 0,
        "review_items": [],
    }
    return {"job_id": job_id, "status": "CREATED"}


@router.post("/{job_id}/run")
def run_job(job_id: str) -> dict[str, object]:
    _get_job(job_id)

    state = run_mock_workflow(job_id=job_id)
    job = {
        "job_id": job_id,
        "status": state["status"],
        "revision_attempts": state["revision_attempts"],
        "review_items": list(state.get("review_items", [])),
    }
    _jobs[job_id] = job
    return job


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    return _get_job(job_id)


@router.get("/{job_id}/review-items")
def get_review_items(job_id: str) -> dict[str, list[dict[str, str]]]:
    job = _get_job(job_id)
    visible_items = [
        item for item in job.get("review_items", []) if item.get("review_reason")
    ]
    return {"items": visible_items}


def _get_job(job_id: str) -> dict[str, object]:
    try:
        return _jobs[job_id]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc
