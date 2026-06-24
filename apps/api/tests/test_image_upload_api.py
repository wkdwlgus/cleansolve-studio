import asyncio
from hashlib import sha256
from threading import Event, Thread, current_thread
from time import sleep

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from cleansolve_api.artifacts import LocalArtifactStore, MAX_IMAGE_UPLOAD_BYTES
from cleansolve_api.main import app
from cleansolve_api.routes import jobs

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 16


@pytest.fixture(autouse=True)
def isolated_storage_root(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs.settings, "storage_root", tmp_path / "jobs")


def create_job(client: TestClient) -> str:
    return client.post("/jobs").json()["job_id"]


def manifest_path(job_id: str):
    return jobs.settings.storage_root / job_id / "manifest.json"


def artifact_path(job_id: str, relative_path: str):
    return jobs.settings.storage_root / job_id / relative_path


def assert_error(response, code: str):
    payload = response.json()
    assert payload["detail"]["code"] == code
    assert isinstance(payload["detail"]["message"], str)
    assert isinstance(payload["detail"]["fields"], dict)


class CloseTrackingUpload:
    def __init__(self, content_type: str, data: bytes = b""):
        self.content_type = content_type
        self._data = data
        self._was_read = False
        self.closed = False

    async def read(self, _: int) -> bytes:
        await asyncio.sleep(0)
        if self._was_read:
            return b""
        self._was_read = True
        return self._data

    async def close(self) -> None:
        self.closed = True


def test_upload_problem_png_persists_artifact_and_manifest():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("private-problem-name.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    artifact = payload["artifact"]
    assert payload["job_id"] == job_id
    assert payload["role"] == "problem"
    assert artifact["artifact_id"].startswith("img_")
    assert artifact["role"] == "problem"
    assert artifact["mime_type"] == "image/png"
    assert artifact["extension"] == "png"
    assert artifact["size_bytes"] == len(PNG_BYTES)
    assert artifact["sha256"] == sha256(PNG_BYTES).hexdigest()
    assert artifact["relative_path"].startswith("artifacts/images/problem/")
    assert artifact["relative_path"].endswith(".png")
    assert artifact_path(job_id, artifact["relative_path"]).read_bytes() == PNG_BYTES
    assert payload["latest_image_artifact_ids"]["problem"] == artifact["artifact_id"]
    assert manifest_path(job_id).exists()


def test_upload_teacher_solution_jpeg_persists_artifact_and_manifest():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/teacher-solution",
        files={"file": ("teacher.jpg", JPEG_BYTES, "image/jpeg")},
    )

    assert response.status_code == 201
    payload = response.json()
    artifact = payload["artifact"]
    assert payload["role"] == "teacher_solution"
    assert artifact["role"] == "teacher_solution"
    assert artifact["mime_type"] == "image/jpeg"
    assert artifact["extension"] == "jpg"
    assert artifact["relative_path"].startswith("artifacts/images/teacher_solution/")
    assert artifact["relative_path"].endswith(".jpg")
    assert artifact_path(job_id, artifact["relative_path"]).read_bytes() == JPEG_BYTES
    assert payload["latest_image_artifact_ids"]["teacher_solution"] == artifact["artifact_id"]


def test_reupload_same_role_appends_artifact_without_overwriting_previous_file():
    client = TestClient(app)
    job_id = create_job(client)

    first_response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("first.png", PNG_BYTES, "image/png")},
    )
    second_bytes = b"\x89PNG\r\n\x1a\n" + b"\x01" * 16
    second_response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("second.png", second_bytes, "image/png")},
    )

    first_artifact = first_response.json()["artifact"]
    second_artifact = second_response.json()["artifact"]
    job = client.get(f"/jobs/{job_id}").json()
    problem_artifacts = job["image_artifacts"]["problem"]

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert len(problem_artifacts) == 2
    assert [artifact["artifact_id"] for artifact in problem_artifacts] == [
        first_artifact["artifact_id"],
        second_artifact["artifact_id"],
    ]
    assert artifact_path(job_id, first_artifact["relative_path"]).exists()
    assert artifact_path(job_id, second_artifact["relative_path"]).exists()
    assert job["latest_image_artifact_ids"]["problem"] == second_artifact["artifact_id"]


def test_concurrent_same_role_uploads_preserve_both_manifest_records(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    second_bytes = b"\x89PNG\r\n\x1a\n" + b"\x01" * 16

    async def upload_both():
        await asyncio.gather(
            store.save_image(
                manifest.job_id,
                "problem",
                CloseTrackingUpload("image/png", PNG_BYTES),
            ),
            store.save_image(
                manifest.job_id,
                "problem",
                CloseTrackingUpload("image/png", second_bytes),
            ),
        )

    asyncio.run(upload_both())

    job = store.get_job(manifest.job_id)
    problem_artifacts = job.image_artifacts["problem"]

    assert len(problem_artifacts) == 2
    assert {artifact.sha256 for artifact in problem_artifacts} == {
        sha256(PNG_BYTES).hexdigest(),
        sha256(second_bytes).hexdigest(),
    }
    role_directory = (
        tmp_path / "jobs" / manifest.job_id / "artifacts" / "images" / "problem"
    )
    assert len(list(role_directory.glob("*.png"))) == 2


def test_run_update_does_not_overwrite_concurrent_upload_manifest_record(
    monkeypatch,
    tmp_path,
):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    asyncio.run(
        store.save_image(
            manifest.job_id,
            "problem",
            CloseTrackingUpload("image/png", PNG_BYTES),
        )
    )
    asyncio.run(
        store.save_image(
            manifest.job_id,
            "teacher_solution",
            CloseTrackingUpload("image/jpeg", JPEG_BYTES),
        )
    )
    run_read_manifest = Event()
    allow_run_save = Event()
    original_get_job = store.get_job
    errors: list[BaseException] = []

    def delayed_get_job(job_id: str):
        manifest_snapshot = original_get_job(job_id)
        if current_thread().name == "run-update":
            run_read_manifest.set()
            allow_run_save.wait(timeout=2)
        return manifest_snapshot

    monkeypatch.setattr(store, "get_job", delayed_get_job)

    def update_after_run():
        try:
            store.update_after_run(
                job_id=manifest.job_id,
                status_value="APPROVED",
                revision_attempts=1,
                review_items=[],
            )
        except BaseException as exc:
            errors.append(exc)

    def upload_problem_again():
        try:
            reupload_bytes = b"\x89PNG\r\n\x1a\n" + b"\x02" * 16
            asyncio.run(
                store.save_image(
                    manifest.job_id,
                    "problem",
                    CloseTrackingUpload("image/png", reupload_bytes),
                )
            )
        except BaseException as exc:
            errors.append(exc)

    run_thread = Thread(target=update_after_run, name="run-update")
    upload_thread = Thread(target=upload_problem_again, name="upload-problem")
    run_thread.start()
    assert run_read_manifest.wait(timeout=2)
    upload_thread.start()
    sleep(0.05)
    allow_run_save.set()
    run_thread.join(timeout=2)
    upload_thread.join(timeout=2)

    assert not run_thread.is_alive()
    assert not upload_thread.is_alive()
    assert errors == []
    assert len(original_get_job(manifest.job_id).image_artifacts["problem"]) == 2


def test_upload_unknown_job_returns_structured_404():
    client = TestClient(app)

    response = client.post(
        "/jobs/job_unknown/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")
    assert response.json()["detail"]["fields"] == {"job_id": "job_unknown"}


def test_upload_rejects_encoded_path_traversal_job_id(monkeypatch, tmp_path):
    storage_root = tmp_path / "jobs"
    storage_root.mkdir()
    monkeypatch.setattr(jobs.settings, "storage_root", storage_root)
    parent_manifest = tmp_path / "manifest.json"
    parent_manifest.write_text(
        """
{
  "job_id": "job_00000000000000000000000000000000",
  "status": "CREATED",
  "created_at": "2026-06-15T00:00:00Z",
  "updated_at": "2026-06-15T00:00:00Z",
  "revision_attempts": 0,
  "review_items": [],
  "image_artifacts": {
    "problem": [],
    "teacher_solution": []
  },
  "latest_image_artifact_ids": {
    "problem": null,
    "teacher_solution": null
  }
}
""",
        encoding="utf-8",
    )
    client = TestClient(app)

    response = client.post(
        "/jobs/%2e%2e/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")
    assert not (tmp_path / "artifacts").exists()


def test_store_closes_upload_when_job_is_unknown(tmp_path):
    upload = CloseTrackingUpload("image/png")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            LocalArtifactStore(tmp_path / "jobs").save_image(
                "job_unknown",
                "problem",
                upload,
            )
        )

    assert exc_info.value.status_code == 404
    assert upload.closed is True


def test_upload_rejects_unsupported_mime_type():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.gif", PNG_BYTES, "image/gif")},
    )

    assert response.status_code == 415
    assert_error(response, "UNSUPPORTED_IMAGE_TYPE")
    assert response.json()["detail"]["fields"] == {
        "allowed": ["image/jpeg", "image/png"],
        "received": "image/gif",
    }


def test_store_closes_upload_when_mime_type_is_unsupported(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    upload = CloseTrackingUpload("image/gif")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(store.save_image(manifest.job_id, "problem", upload))

    assert exc_info.value.status_code == 415
    assert upload.closed is True


def test_upload_rejects_mime_magic_mismatch():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.png", JPEG_BYTES, "image/png")},
    )

    assert response.status_code == 400
    assert_error(response, "INVALID_IMAGE_BYTES")
    assert response.json()["detail"]["fields"] == {"reason": "mime_magic_mismatch"}


def test_upload_rejects_empty_file():
    client = TestClient(app)
    job_id = create_job(client)

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("empty.png", b"", "image/png")},
    )

    assert response.status_code == 400
    assert_error(response, "EMPTY_IMAGE")


def test_upload_rejects_oversized_file():
    client = TestClient(app)
    job_id = create_job(client)
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_IMAGE_UPLOAD_BYTES

    response = client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("large.png", oversized, "image/png")},
    )

    assert response.status_code == 413
    assert_error(response, "IMAGE_TOO_LARGE")
    assert response.json()["detail"]["fields"] == {
        "max_size_bytes": MAX_IMAGE_UPLOAD_BYTES,
    }


def test_job_response_does_not_expose_absolute_paths_or_original_filename():
    client = TestClient(app)
    job_id = create_job(client)

    client.post(
        f"/jobs/{job_id}/images/teacher-solution",
        files={"file": ("teacher-private-name.png", PNG_BYTES, "image/png")},
    )
    payload_text = client.get(f"/jobs/{job_id}").text

    assert "/Users/" not in payload_text
    assert str(jobs.settings.storage_root) not in payload_text
    assert "teacher-private-name" not in payload_text


def test_run_requires_both_problem_and_teacher_solution_images():
    client = TestClient(app)
    job_id = create_job(client)
    client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )

    response = client.post(f"/jobs/{job_id}/run")

    assert response.status_code == 409
    assert_error(response, "MISSING_REQUIRED_IMAGES")
    assert response.json()["detail"]["fields"] == {
        "missing_roles": ["teacher_solution"],
    }


def test_run_succeeds_after_both_required_images_are_uploaded(monkeypatch):
    class CapturingExecutor:
        def __init__(self):
            self.requests = []

        def submit(self, request):
            self.requests.append(request)

        def is_active(self, job_id):
            return any(request.job_id == job_id for request in self.requests)

    executor = CapturingExecutor()
    monkeypatch.setattr(jobs, "job_run_executor", executor)
    client = TestClient(app)
    job_id = create_job(client)
    client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )
    client.post(
        f"/jobs/{job_id}/images/teacher-solution",
        files={"file": ("teacher.jpg", JPEG_BYTES, "image/jpeg")},
    )

    response = client.post(f"/jobs/{job_id}/run")

    assert response.status_code == 202
    assert response.json()["status"] == "RUNNING"
    assert len(executor.requests) == 1
    assert executor.requests[0].job_id == job_id
