from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
ALLOWED_RUN_STATUSES = {"APPROVED", "NEEDS_REVIEW", "REVISION_REQUIRED"}


@dataclass(frozen=True)
class E2EHarnessResult:
    job_id: str
    status: str
    revision_attempts: int
    visible_review_item_count: int
    correction_plan_count: int
    candidate_spec_artifact_id: str
    validation_report_artifact_id: str
    correction_plan_artifact_id: str
    render_artifact_id: str
    export_artifact_id: str
    export_size_bytes: int


def run_api_upload_to_export_e2e(
    *,
    client: TestClient,
    problem_image_path: Path,
    teacher_solution_image_path: Path,
) -> E2EHarnessResult:
    create_response = client.post("/jobs")
    create_payload = _json_response(create_response, 201)
    job_id = _required_string(create_payload, "job_id")

    _upload_image(
        client=client,
        job_id=job_id,
        path="/images/problem",
        file_path=problem_image_path,
        mime_type=_image_mime_type(problem_image_path),
    )
    _upload_image(
        client=client,
        job_id=job_id,
        path="/images/teacher-solution",
        file_path=teacher_solution_image_path,
        mime_type=_image_mime_type(teacher_solution_image_path),
    )

    run_start_payload = _json_response(client.post(f"/jobs/{job_id}/run"), 202)
    if _required_string(run_start_payload, "status") != "RUNNING":
        raise AssertionError("run start response must be RUNNING")
    _drain_progress_stream(client, job_id)
    run_payload = _json_response(client.get(f"/jobs/{job_id}"), 200)
    status = _required_string(run_payload, "status")
    if status not in ALLOWED_RUN_STATUSES:
        raise AssertionError(f"Unexpected run status: {status}")
    if status != "APPROVED":
        raise AssertionError(f"M8 manual fixture must be APPROVED, got {status}")

    candidate_payload = _json_response(client.get(f"/jobs/{job_id}/candidate-spec"), 200)
    validation_payload = _json_response(client.get(f"/jobs/{job_id}/validation-report"), 200)
    correction_payload = _json_response(client.get(f"/jobs/{job_id}/correction-plan"), 200)
    review_payload = _json_response(client.get(f"/jobs/{job_id}/review-items"), 200)
    render_payload = _json_response(client.post(f"/jobs/{job_id}/render"), 200)
    rendered_payload = _json_response(client.get(f"/jobs/{job_id}/rendered-preview"), 200)
    export_payload = _json_response(
        client.post(f"/jobs/{job_id}/export", json={"format": "png"}),
        200,
    )
    latest_export_payload = _json_response(client.get(f"/jobs/{job_id}/exports/latest"), 200)

    latest_analysis_ids = _required_dict(run_payload, "latest_analysis_artifact_ids")
    candidate_spec_artifact_id = _required_string(latest_analysis_ids, "candidate_spec")
    validation_report_artifact_id = _required_string(latest_analysis_ids, "validation_report")
    correction_plan_artifact_id = _required_string(latest_analysis_ids, "correction_plan")
    render_artifact = _required_dict(render_payload, "artifact")
    rendered_artifact = _required_dict(rendered_payload, "artifact")
    export_artifact = _required_dict(export_payload, "artifact")
    latest_export_artifact = _required_dict(latest_export_payload, "artifact")

    render_artifact_id = _required_string(render_artifact, "artifact_id")
    if _required_string(rendered_artifact, "artifact_id") != render_artifact_id:
        raise AssertionError("rendered-preview returned a different render artifact")

    export_artifact_id = _required_string(export_artifact, "artifact_id")
    if _required_string(latest_export_artifact, "artifact_id") != export_artifact_id:
        raise AssertionError("latest export returned a different export artifact")

    download_response = client.get(f"/jobs/{job_id}/exports/{export_artifact_id}/download")
    if download_response.status_code != 200:
        raise AssertionError(
            f"Expected export download status 200, got {download_response.status_code}: "
            f"{download_response.text}"
        )
    if not download_response.content.startswith(PNG_MAGIC):
        raise AssertionError("Export download did not return PNG bytes")

    review_items = review_payload.get("items")
    if not isinstance(review_items, list):
        raise AssertionError("review-items response must include list field 'items'")
    if len(review_items) > 3:
        raise AssertionError(f"review item budget exceeded: {len(review_items)}")

    correction_plans = correction_payload.get("correction_plans")
    if not isinstance(correction_plans, list):
        raise AssertionError("correction-plan response must include list field 'correction_plans'")

    if candidate_payload.get("job_id") != job_id:
        raise AssertionError("candidate spec job_id mismatch")
    if validation_payload.get("passed") is not True:
        raise AssertionError("validation report must pass for M8 manual fixture")

    return E2EHarnessResult(
        job_id=job_id,
        status=status,
        revision_attempts=_required_int(run_payload, "revision_attempts"),
        visible_review_item_count=len(review_items),
        correction_plan_count=len(correction_plans),
        candidate_spec_artifact_id=candidate_spec_artifact_id,
        validation_report_artifact_id=validation_report_artifact_id,
        correction_plan_artifact_id=correction_plan_artifact_id,
        render_artifact_id=render_artifact_id,
        export_artifact_id=export_artifact_id,
        export_size_bytes=len(download_response.content),
    )


def _drain_progress_stream(client: TestClient, job_id: str) -> str:
    response = client.get(f"/jobs/{job_id}/progress-stream")
    if response.status_code != 200:
        raise AssertionError(
            f"Expected progress stream status 200, got {response.status_code}: {response.text}"
        )
    body = response.text
    if "event: complete" not in body:
        raise AssertionError(f"Progress stream did not complete: {body}")
    return body


def _upload_image(
    *,
    client: TestClient,
    job_id: str,
    path: str,
    file_path: Path,
    mime_type: str,
) -> None:
    if not file_path.exists():
        raise AssertionError(f"Missing fixture image: {file_path}")
    response = client.post(
        f"/jobs/{job_id}{path}",
        files={"file": (file_path.name, file_path.read_bytes(), mime_type)},
    )
    _json_response(response, 201)


def _image_mime_type(file_path: Path) -> str:
    data = file_path.read_bytes()
    if data.startswith(PNG_MAGIC):
        return "image/png"
    if data.startswith(JPEG_MAGIC):
        return "image/jpeg"
    raise AssertionError(f"Unsupported fixture image bytes: {file_path}")


def _json_response(response, expected_status: int) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise AssertionError(
            f"Expected status {expected_status}, got {response.status_code}: {response.text}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise AssertionError("Expected JSON object response")
    return payload


def _required_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise AssertionError(f"Expected dict field: {key}")
    return value


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise AssertionError(f"Expected non-empty string field: {key}")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise AssertionError(f"Expected int field: {key}")
    return value
