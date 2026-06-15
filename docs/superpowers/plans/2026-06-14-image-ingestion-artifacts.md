# M1 Image Ingestion & Artifact Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local filesystem image artifact ingestion for problem and teacher-solution images, including immutable artifact storage, manifest persistence, structured errors, workflow run preconditions, tests, and Korean docs.

**Architecture:** The API moves from an in-memory `_jobs` dict to a local manifest-backed `LocalArtifactStore` in `apps/api/cleansolve_api/artifacts.py`. `routes/jobs.py` remains the only FastAPI route module and delegates job/artifact persistence to the store. M1 does not change workflow internals, renderer packages, AI packages, or web code.

**Tech Stack:** Python 3.13, FastAPI `UploadFile`/`File`, Pydantic, local filesystem storage via `pathlib`, pytest, FastAPI `TestClient`, `python-multipart`.

---

## Source Documents

- Design spec: `docs/superpowers/specs/2026-06-14-image-ingestion-artifacts-design.md`
- Roadmap: `docs/product/mvp-roadmap.md`
- Current route file: `apps/api/cleansolve_api/routes/jobs.py`
- Current settings file: `apps/api/cleansolve_api/settings.py`

## File Structure

Create:

- `apps/api/cleansolve_api/artifacts.py`
  - Owns image artifact models, manifest model, local store, upload validation, structured API errors, and job response conversion.
- `apps/api/tests/test_image_upload_api.py`
  - Owns all image upload, persistence, validation, response sanitization, and run precondition tests.

Modify:

- `apps/api/cleansolve_api/routes/jobs.py`
  - Removes `_jobs` in-memory state.
  - Uses `LocalArtifactStore(settings.storage_root)`.
  - Adds image upload endpoints.
  - Adds run precondition that requires both required image roles.
- `apps/api/tests/test_jobs_api.py`
  - Stops importing `_jobs`.
  - Uses isolated temp storage.
  - Updates run tests to upload both images before calling `/run`.
  - Updates unknown-job assertions to structured `JOB_NOT_FOUND`.
- `pyproject.toml`
  - Adds `python-multipart`.
- `README.md`
  - Adds Korean local image upload flow.
- `docs/product/mvp-roadmap.md`
  - Updates M1 status after implementation from `Not Started` to `Done`.

Do not modify:

- `packages/ai/**`
- `packages/workflow/**`
- `packages/renderer/**`
- `apps/web/**`

## Constants And Shapes

Use these exact constants in `apps/api/cleansolve_api/artifacts.py`:

```python
ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024
```

Use these exact roles:

```python
ImageRole = Literal["problem", "teacher_solution"]
```

Use this exact structured error shape:

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "한국어 오류 메시지",
    "fields": {}
  }
}
```

Use these exact error messages:

```python
ERROR_MESSAGES = {
    "JOB_NOT_FOUND": "작업을 찾을 수 없습니다.",
    "UNSUPPORTED_IMAGE_TYPE": "지원하지 않는 이미지 형식입니다.",
    "INVALID_IMAGE_BYTES": "이미지 파일 내용이 MIME 형식과 일치하지 않습니다.",
    "EMPTY_IMAGE": "빈 이미지 파일은 업로드할 수 없습니다.",
    "IMAGE_TOO_LARGE": "이미지 파일 크기가 허용 범위를 초과했습니다.",
    "MISSING_REQUIRED_IMAGES": "workflow 실행에 필요한 이미지가 아직 업로드되지 않았습니다.",
    "STORAGE_WRITE_FAILED": "이미지 artifact 저장에 실패했습니다.",
}
```

## Task 1: Artifact Models And Manifest Store

**Files:**

- Create: `apps/api/cleansolve_api/artifacts.py`
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
- Modify: `apps/api/tests/test_jobs_api.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add multipart dependency**

Edit `pyproject.toml` and add `python-multipart` to `[project].dependencies`:

```toml
dependencies = [
  "fastapi",
  "langgraph",
  "pydantic",
  "pytest",
  "python-multipart",
]
```

- [ ] **Step 2: Install multipart dependency in the local test environment**

Run:

```bash
python -m pip install python-multipart
```

Expected:

- Command exits 0.
- `python -c "import multipart"` exits 0.

- [ ] **Step 3: Write failing job persistence tests**

Replace `apps/api/tests/test_jobs_api.py` with this exact file:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cleansolve_api.main import app
from cleansolve_api.routes import jobs
from cleansolve_api.settings import Settings

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 16


@pytest.fixture(autouse=True)
def isolated_storage_root(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs.settings, "storage_root", tmp_path / "jobs")


def upload_required_images(client: TestClient, job_id: str):
    client.post(
        f"/jobs/{job_id}/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )
    client.post(
        f"/jobs/{job_id}/images/teacher-solution",
        files={"file": ("teacher.jpg", JPEG_BYTES, "image/jpeg")},
    )


def assert_error(response, code: str):
    payload = response.json()
    assert payload["detail"]["code"] == code
    assert isinstance(payload["detail"]["message"], str)
    assert isinstance(payload["detail"]["fields"], dict)


def test_create_job_initializes_manifest_backed_response():
    client = TestClient(app)

    response = client.post("/jobs")

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_id"].startswith("job_")
    assert payload["status"] == "CREATED"
    assert payload["revision_attempts"] == 0
    assert payload["review_items"] == []
    assert payload["latest_image_artifact_ids"] == {
        "problem": None,
        "teacher_solution": None,
    }
    assert payload["image_artifacts"] == {
        "problem": [],
        "teacher_solution": [],
    }
    assert (jobs.settings.storage_root / payload["job_id"] / "manifest.json").exists()


def test_create_job_and_run_mock_workflow_after_required_images_uploaded():
    client = TestClient(app)

    create_response = client.post("/jobs")
    job_id = create_response.json()["job_id"]
    upload_required_images(client, job_id)
    run_response = client.post(f"/jobs/{job_id}/run")

    assert create_response.status_code == 201
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "APPROVED"
    assert run_response.json()["revision_attempts"] == 1


def test_review_items_endpoint_hides_internal_needs_review_items():
    client = TestClient(app)

    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")
    response = client.get(f"/jobs/{job_id}/review-items")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_get_unknown_job_returns_structured_404():
    client = TestClient(app)

    response = client.get("/jobs/job_unknown")

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")
    assert response.json()["detail"]["fields"] == {"job_id": "job_unknown"}


def test_run_unknown_job_returns_structured_404():
    client = TestClient(app)

    response = client.post("/jobs/job_unknown/run")

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")


def test_get_unknown_job_review_items_returns_structured_404():
    client = TestClient(app)

    response = client.get("/jobs/job_unknown/review-items")

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")


def test_review_items_endpoint_is_empty_before_running_workflow():
    client = TestClient(app)

    job_id = client.post("/jobs").json()["job_id"]
    response = client.get(f"/jobs/{job_id}/review-items")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_settings_use_cleansolve_storage_root(monkeypatch):
    monkeypatch.delenv("STORAGE_ROOT", raising=False)
    monkeypatch.setenv("CLEANSOLVE_STORAGE_ROOT", "var/custom-jobs")

    settings = Settings()

    assert settings.storage_root == Path("var/custom-jobs")


def test_settings_load_apps_api_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / "api.env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-from-env-file",
                "OPENAI_MODEL_ANALYSIS=gpt-analysis-file",
                "CLEANSOLVE_STORAGE_ROOT=var/env-file-jobs",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_ANALYSIS", raising=False)
    monkeypatch.delenv("CLEANSOLVE_STORAGE_ROOT", raising=False)
    monkeypatch.setenv("CLEANSOLVE_API_ENV_FILE", str(env_file))

    settings = Settings()

    assert settings.openai_api_key == "sk-from-env-file"
    assert settings.openai_model_analysis == "gpt-analysis-file"
    assert settings.storage_root == Path("var/env-file-jobs")
```

- [ ] **Step 4: Run job tests and verify RED**

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

Expected:

- Failures because `jobs.settings` does not exist yet.
- Failures because image upload endpoints do not exist yet.
- Failures because unknown job still returns string detail.

- [ ] **Step 5: Create `artifacts.py` with manifest models, helpers, and job persistence**

Create `apps/api/cleansolve_api/artifacts.py` with this exact implementation:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

ImageRole = Literal["problem", "teacher_solution"]
ImageMimeType = Literal["image/png", "image/jpeg"]
ImageExtension = Literal["png", "jpg"]
JobStatus = Literal["CREATED", "APPROVED", "NEEDS_REVIEW", "FAILED"]

ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024

ERROR_MESSAGES = {
    "JOB_NOT_FOUND": "작업을 찾을 수 없습니다.",
    "UNSUPPORTED_IMAGE_TYPE": "지원하지 않는 이미지 형식입니다.",
    "INVALID_IMAGE_BYTES": "이미지 파일 내용이 MIME 형식과 일치하지 않습니다.",
    "EMPTY_IMAGE": "빈 이미지 파일은 업로드할 수 없습니다.",
    "IMAGE_TOO_LARGE": "이미지 파일 크기가 허용 범위를 초과했습니다.",
    "MISSING_REQUIRED_IMAGES": "workflow 실행에 필요한 이미지가 아직 업로드되지 않았습니다.",
    "STORAGE_WRITE_FAILED": "이미지 artifact 저장에 실패했습니다.",
}


class ImageArtifact(BaseModel):
    artifact_id: str
    role: ImageRole
    mime_type: ImageMimeType
    extension: ImageExtension
    size_bytes: int = Field(ge=1, le=MAX_IMAGE_UPLOAD_BYTES)
    sha256: str = Field(min_length=64, max_length=64)
    relative_path: str
    created_at: str


class JobManifest(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    revision_attempts: int = Field(ge=0)
    review_items: list[dict[str, Any]]
    image_artifacts: dict[ImageRole, list[ImageArtifact]]
    latest_image_artifact_ids: dict[ImageRole, str | None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_job_id() -> str:
    return f"job_{uuid4().hex}"


def _new_artifact_id() -> str:
    return f"img_{uuid4().hex}"


def _error(code: str, status_code: int, fields: dict[str, Any] | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": ERROR_MESSAGES[code],
            "fields": fields or {},
        },
    )


def job_not_found_error(job_id: str) -> HTTPException:
    return _error("JOB_NOT_FOUND", status.HTTP_404_NOT_FOUND, {"job_id": job_id})


def missing_required_images_error(missing_roles: list[ImageRole]) -> HTTPException:
    return _error(
        "MISSING_REQUIRED_IMAGES",
        status.HTTP_409_CONFLICT,
        {"missing_roles": missing_roles},
    )


def job_response(manifest: JobManifest) -> dict[str, Any]:
    return {
        "job_id": manifest.job_id,
        "status": manifest.status,
        "revision_attempts": manifest.revision_attempts,
        "review_items": manifest.review_items,
        "latest_image_artifact_ids": manifest.latest_image_artifact_ids,
        "image_artifacts": {
            role: [artifact.model_dump(mode="json") for artifact in artifacts]
            for role, artifacts in manifest.image_artifacts.items()
        },
    }


class LocalArtifactStore:
    def __init__(self, storage_root: Path):
        self.storage_root = storage_root

    def create_job(self, job_id: str | None = None) -> JobManifest:
        resolved_job_id = job_id or _new_job_id()
        now = _utc_now()
        manifest = JobManifest(
            job_id=resolved_job_id,
            status="CREATED",
            created_at=now,
            updated_at=now,
            revision_attempts=0,
            review_items=[],
            image_artifacts={"problem": [], "teacher_solution": []},
            latest_image_artifact_ids={"problem": None, "teacher_solution": None},
        )
        self.save_manifest(manifest)
        return manifest

    def get_job(self, job_id: str) -> JobManifest:
        manifest_path = self._manifest_path(job_id)
        if not manifest_path.exists():
            raise job_not_found_error(job_id)
        return JobManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    def save_manifest(self, manifest: JobManifest) -> None:
        job_root = self._job_root(manifest.job_id)
        try:
            job_root.mkdir(parents=True, exist_ok=True)
            manifest_path = self._manifest_path(manifest.job_id)
            temp_path = manifest_path.with_name("manifest.json.tmp")
            payload = json.dumps(
                manifest.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            temp_path.write_text(payload, encoding="utf-8")
            temp_path.replace(manifest_path)
        except OSError as exc:
            raise _error("STORAGE_WRITE_FAILED", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc

    def update_after_run(
        self,
        job_id: str,
        status_value: str,
        revision_attempts: int,
        review_items: list[dict[str, Any]],
    ) -> JobManifest:
        manifest = self.get_job(job_id)
        manifest.status = status_value
        manifest.revision_attempts = revision_attempts
        manifest.review_items = review_items
        manifest.updated_at = _utc_now()
        self.save_manifest(manifest)
        return manifest

    def _job_root(self, job_id: str) -> Path:
        return self.storage_root / job_id

    def _manifest_path(self, job_id: str) -> Path:
        return self._job_root(job_id) / "manifest.json"

    def _role_directory(self, job_id: str, role: ImageRole) -> Path:
        return self._job_root(job_id) / "artifacts" / "images" / role
```

- [ ] **Step 6: Update `routes/jobs.py` to use manifest-backed jobs**

Replace `apps/api/cleansolve_api/routes/jobs.py` with this exact implementation for Task 1:

```python
from fastapi import APIRouter, status

from cleansolve_api.artifacts import LocalArtifactStore, job_response, missing_required_images_error
from cleansolve_api.settings import settings
from cleansolve_workflow.graph import run_mock_workflow

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _store() -> LocalArtifactStore:
    return LocalArtifactStore(settings.storage_root)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job() -> dict[str, object]:
    return job_response(_store().create_job())


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

    state = run_mock_workflow(job_id=job_id)
    updated_manifest = store.update_after_run(
        job_id=job_id,
        status_value=state["status"],
        revision_attempts=state["revision_attempts"],
        review_items=list(state.get("review_items", [])),
    )
    return job_response(updated_manifest)


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    return job_response(_store().get_job(job_id))


@router.get("/{job_id}/review-items")
def get_review_items(job_id: str) -> dict[str, list[dict[str, object]]]:
    manifest = _store().get_job(job_id)
    visible_items = [
        item for item in manifest.review_items if item.get("review_reason")
    ]
    return {"items": visible_items}
```

This intentionally does not add upload endpoints yet. They are Task 2.

- [ ] **Step 7: Run job tests and verify partial GREEN/expected RED**

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

Expected:

- `test_create_job_initializes_manifest_backed_response` passes.
- unknown job tests pass.
- run tests fail because upload endpoints are not implemented and required images cannot be uploaded yet.

- [ ] **Step 8: Commit Task 1**

Run:

```bash
git add pyproject.toml apps/api/cleansolve_api/artifacts.py apps/api/cleansolve_api/routes/jobs.py apps/api/tests/test_jobs_api.py
git commit -m "feat(api): add manifest-backed job store"
```

## Task 2: Image Upload Persistence And Validation

**Files:**

- Modify: `apps/api/cleansolve_api/artifacts.py`
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
- Create: `apps/api/tests/test_image_upload_api.py`
- Test: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Write failing image upload tests**

Create `apps/api/tests/test_image_upload_api.py` with this exact file:

```python
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from cleansolve_api.main import app
from cleansolve_api.routes import jobs

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 16
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024


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


def test_upload_unknown_job_returns_structured_404():
    client = TestClient(app)

    response = client.post(
        "/jobs/job_unknown/images/problem",
        files={"file": ("problem.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")
    assert response.json()["detail"]["fields"] == {"job_id": "job_unknown"}


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


def test_run_succeeds_after_both_required_images_are_uploaded():
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

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert response.json()["revision_attempts"] == 1
```

- [ ] **Step 2: Run image upload tests and verify RED**

Run:

```bash
python -m pytest apps/api/tests/test_image_upload_api.py -q
```

Expected:

- Failures because `/jobs/{job_id}/images/problem` and `/jobs/{job_id}/images/teacher-solution` do not exist.
- If Task 1 was not completed, collection may fail because `python-multipart` is missing; stop and complete Task 1 first.

- [ ] **Step 3: Implement upload validation and persistence in `artifacts.py`**

Append these imports at the top of `apps/api/cleansolve_api/artifacts.py`:

```python
import hashlib
from fastapi import UploadFile
```

Add this helper below `_new_artifact_id()`:

```python
def _detect_magic_type(data_prefix: bytes) -> str | None:
    if data_prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data_prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None
```

Add this method inside `LocalArtifactStore`:

```python
    async def save_image(self, job_id: str, role: ImageRole, upload: UploadFile) -> tuple[JobManifest, ImageArtifact]:
        manifest = self.get_job(job_id)
        content_type = upload.content_type
        if content_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise _error(
                "UNSUPPORTED_IMAGE_TYPE",
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                {
                    "allowed": sorted(ALLOWED_IMAGE_MIME_TYPES),
                    "received": content_type,
                },
            )

        artifact_id = _new_artifact_id()
        extension: ImageExtension = "png" if content_type == "image/png" else "jpg"
        role_directory = self._role_directory(job_id, role)
        relative_path = f"artifacts/images/{role}/{artifact_id}.{extension}"
        final_path = self._job_root(job_id) / relative_path
        temp_path = final_path.with_name(f"{artifact_id}.{extension}.tmp")
        digest = hashlib.sha256()
        size_bytes = 0
        first_chunk = b""

        try:
            role_directory.mkdir(parents=True, exist_ok=True)
            with temp_path.open("wb") as output:
                while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                    if not first_chunk:
                        first_chunk = chunk
                    size_bytes += len(chunk)
                    if size_bytes > MAX_IMAGE_UPLOAD_BYTES:
                        output.close()
                        temp_path.unlink(missing_ok=True)
                        raise _error(
                            "IMAGE_TOO_LARGE",
                            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            {"max_size_bytes": MAX_IMAGE_UPLOAD_BYTES},
                        )
                    digest.update(chunk)
                    output.write(chunk)

            if size_bytes == 0:
                temp_path.unlink(missing_ok=True)
                raise _error("EMPTY_IMAGE", status.HTTP_400_BAD_REQUEST)

            if _detect_magic_type(first_chunk) != content_type:
                temp_path.unlink(missing_ok=True)
                raise _error(
                    "INVALID_IMAGE_BYTES",
                    status.HTTP_400_BAD_REQUEST,
                    {"reason": "mime_magic_mismatch"},
                )

            artifact = ImageArtifact(
                artifact_id=artifact_id,
                role=role,
                mime_type=content_type,
                extension=extension,
                size_bytes=size_bytes,
                sha256=digest.hexdigest(),
                relative_path=relative_path,
                created_at=_utc_now(),
            )
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.replace(final_path)
            manifest.image_artifacts[role].append(artifact)
            manifest.latest_image_artifact_ids[role] = artifact.artifact_id
            manifest.updated_at = _utc_now()
            self.save_manifest(manifest)
            return manifest, artifact
        except HTTPException:
            raise
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise _error("STORAGE_WRITE_FAILED", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc
        finally:
            await upload.close()
```

- [ ] **Step 4: Add upload endpoints in `routes/jobs.py`**

Update imports in `apps/api/cleansolve_api/routes/jobs.py`:

```python
from fastapi import APIRouter, File, UploadFile, status
```

Add these endpoint functions after `create_job()` and before `run_job()`:

```python
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
```

- [ ] **Step 5: Run API tests and verify GREEN**

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py apps/api/tests/test_image_upload_api.py -q
```

Expected:

- All tests in both files pass.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add apps/api/cleansolve_api/artifacts.py apps/api/cleansolve_api/routes/jobs.py apps/api/tests/test_image_upload_api.py apps/api/tests/test_jobs_api.py
git commit -m "feat(api): persist uploaded image artifacts"
```

## Task 3: Documentation And Roadmap Update

**Files:**

- Modify: `README.md`
- Modify: `docs/product/mvp-roadmap.md`

- [ ] **Step 1: Update README with local image upload flow**

In `README.md`, add this section after the `OpenAI API Key` section and before `로컬 검증`:

```markdown
## 로컬 이미지 업로드 흐름

1. `POST /jobs`로 job을 만듭니다.
2. `POST /jobs/{job_id}/images/problem`에 multipart field `file`로 원본 문제 이미지를 업로드합니다.
3. `POST /jobs/{job_id}/images/teacher-solution`에 multipart field `file`로 선생님 손풀이 이미지를 업로드합니다.
4. 두 이미지가 모두 업로드된 뒤 `POST /jobs/{job_id}/run`을 호출합니다.

업로드된 원본 이미지는 job artifact로 저장되며 같은 role을 다시 업로드해도 기존 artifact를 덮어쓰지 않습니다. API 응답에는 local absolute path와 원본 파일명을 노출하지 않습니다.
```

- [ ] **Step 2: Update roadmap M1 status**

In `docs/product/mvp-roadmap.md`, update the M1 section only:

Change:

```markdown
상태: Not Started
```

To:

```markdown
상태: Done
```

Add this line below the detailed design link:

```markdown
구현 결과: local filesystem artifact store, problem/teacher-solution image upload API, manifest persistence, run precondition이 구현됨.
```

Do not change M2 status.

- [ ] **Step 3: Check docs are Korean**

Run:

```bash
sed -n '1,180p' README.md
sed -n '52,100p' docs/product/mvp-roadmap.md
```

Expected:

- Added README section is Korean.
- M1 roadmap status is `Done`.
- M2 remains `Partial`.

- [ ] **Step 4: Commit Task 3**

Run:

```bash
git add README.md docs/product/mvp-roadmap.md
git commit -m "docs: document image artifact ingestion"
```

## Task 4: Final Verification

**Files:**

- No code changes unless verification exposes a defect.

- [ ] **Step 1: Run full Python test suite**

Run:

```bash
python -m pytest -q
```

Expected:

- All Python tests pass.
- Expected count should be previous `41` plus new upload tests, unless plan execution adds extra tests.

- [ ] **Step 2: Run git diff checks**

Run:

```bash
git diff --check
git status -sb
```

Expected:

- `git diff --check` exits 0.
- `git status -sb` shows no uncommitted changes.

- [ ] **Step 3: Verify dependency and no forbidden files**

Run:

```bash
rg '"python-multipart"' pyproject.toml
git check-ignore apps/api/.env apps/web/.env .env
find var -maxdepth 2 -type f 2>/dev/null | head
```

Expected:

- `pyproject.toml` includes `python-multipart`.
- `.env` files are ignored.
- `find var...` prints nothing relevant to tracked files; `var/` remains ignored.

- [ ] **Step 4: Summarize next milestone and needed user files**

In the final implementation response, include:

```text
M1 완료.
다음 추천 milestone: M2 Candidate Spec Pipeline.
다음 구현 전 있으면 좋은 파일:
- 원본 문제 이미지 1장
- 같은 문제의 선생님 손풀이 이미지 1장
없으면 synthetic fixture로 계속 진행 가능.
```

Do not start M2 in the same turn unless the user explicitly approves.

## Plan Self-Review Checklist

- Spec coverage:
  - Image upload endpoints: Task 2.
  - Manifest schema and local storage: Task 1 and Task 2.
  - Structured errors: Task 1 and Task 2.
  - Run precondition: Task 1 and Task 2 tests.
  - Tests: Task 1 and Task 2.
  - Docs: Task 3.
  - Full verification: Task 4.
- Ambiguity scan:
  - The plan must not contain unresolved markers or vague implementation instructions.
- Scope check:
  - No web UI, workflow internals, renderer, AI adapter, or export changes are included.
