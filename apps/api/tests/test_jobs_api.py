from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from cleansolve_api.artifacts import ExportArtifact, LocalArtifactStore
from cleansolve_api.main import app
from cleansolve_api.routes import jobs
from cleansolve_api.routes.jobs import _progress_event_stream, _sse_frame
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


def use_inline_job_executor(monkeypatch):
    class InlineExecutor:
        def submit(self, request):
            jobs.run_job_worker(
                request,
                store=jobs._store(),
                live_progress_store=jobs._live_progress_store(),
                openai_api_key=jobs.settings.openai_api_key,
            )

        def is_active(self, job_id):
            return False

    monkeypatch.setattr(jobs, "job_run_executor", InlineExecutor())


def assert_error(response, code: str):
    payload = response.json()
    assert payload["detail"]["code"] == code
    assert isinstance(payload["detail"]["message"], str)
    assert isinstance(payload["detail"]["fields"], dict)


def source_ids():
    return {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }


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


def test_create_job_and_run_mock_workflow_after_required_images_uploaded(monkeypatch):
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

    create_response = client.post("/jobs")
    job_id = create_response.json()["job_id"]
    upload_required_images(client, job_id)
    run_response = client.post(f"/jobs/{job_id}/run")
    job_payload = client.get(f"/jobs/{job_id}").json()

    assert create_response.status_code == 201
    assert run_response.status_code == 202
    assert run_response.json()["status"] == "RUNNING"
    assert job_payload["status"] == "RUNNING"
    assert len(executor.requests) == 1
    assert executor.requests[0].job_id == job_id


def test_run_with_openai_without_key_returns_502_and_marks_job_failed(monkeypatch):
    use_inline_job_executor(monkeypatch)
    monkeypatch.setattr(jobs.settings, "analysis_client", "openai")
    monkeypatch.setattr(jobs.settings, "openai_api_key", None)
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)

    response = client.post(f"/jobs/{job_id}/run")
    job_response_payload = client.get(f"/jobs/{job_id}").json()
    review_items_payload = client.get(f"/jobs/{job_id}/review-items").json()

    assert response.status_code == 202
    assert response.json()["status"] == "RUNNING"
    assert job_response_payload["status"] == "FAILED"
    assert job_response_payload["review_items"][-1]["type"] == "analysis_adapter_failed"
    assert job_response_payload["review_items"][-1]["retryable"] is True
    assert review_items_payload == {"items": []}
    assert job_response_payload["analysis_artifacts"]["candidate_spec"] == []
    assert job_response_payload["analysis_artifacts"]["validation_report"] == []
    assert job_response_payload["analysis_artifacts"]["correction_plan"] == []
    assert job_response_payload["analysis_artifacts"]["review_correction"] == []
    assert len(job_response_payload["analysis_artifacts"]["progress_events"]) == 1
    assert job_response_payload["latest_analysis_artifact_ids"] == {
        "candidate_spec": None,
        "validation_report": None,
        "correction_plan": None,
        "review_correction": None,
        "progress_events": job_response_payload["analysis_artifacts"]["progress_events"][0]["artifact_id"],
    }
    progress_payload = client.get(f"/jobs/{job_id}/progress-events").json()
    assert progress_payload["events"][-1]["status"] == "FAILED"
    assert "jobs" not in str(job_response_payload)
    assert "sk-" not in str(job_response_payload)
    assert "sk-" not in str(progress_payload)


def test_run_with_openai_sdk_failure_returns_502_without_analysis_artifacts(monkeypatch):
    use_inline_job_executor(monkeypatch)
    class FailingResponses:
        def create(self, **kwargs):
            raise RuntimeError("401 sk-secret /private/tmp/problem.png")

    class FailingOpenAIClient:
        responses = FailingResponses()

    def build_failing_client(api_key: str, timeout_seconds: int) -> object:
        return FailingOpenAIClient()

    monkeypatch.setattr(jobs.settings, "analysis_client", "openai")
    monkeypatch.setattr(jobs.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(
        "cleansolve_ai.openai_client.OpenAIAnalysisClient._build_client",
        staticmethod(build_failing_client),
    )
    client = TestClient(app, raise_server_exceptions=False)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)

    response = client.post(f"/jobs/{job_id}/run")
    job_response_payload = client.get(f"/jobs/{job_id}").json()
    review_items_payload = client.get(f"/jobs/{job_id}/review-items").json()

    assert response.status_code == 202
    assert response.json()["status"] == "RUNNING"
    assert job_response_payload["status"] == "FAILED"
    assert job_response_payload["review_items"][-1]["type"] == "analysis_adapter_failed"
    assert job_response_payload["review_items"][-1]["retryable"] is True
    assert review_items_payload == {"items": []}
    assert job_response_payload["analysis_artifacts"]["candidate_spec"] == []
    assert job_response_payload["analysis_artifacts"]["validation_report"] == []
    assert job_response_payload["analysis_artifacts"]["correction_plan"] == []
    assert job_response_payload["analysis_artifacts"]["review_correction"] == []
    assert len(job_response_payload["analysis_artifacts"]["progress_events"]) == 1
    assert job_response_payload["latest_analysis_artifact_ids"] == {
        "candidate_spec": None,
        "validation_report": None,
        "correction_plan": None,
        "review_correction": None,
        "progress_events": job_response_payload["analysis_artifacts"]["progress_events"][0]["artifact_id"],
    }
    progress_payload = client.get(f"/jobs/{job_id}/progress-events").json()
    assert progress_payload["events"][-1]["status"] == "FAILED"
    assert "sk-" not in str(job_response_payload)
    assert "private" not in str(job_response_payload)
    assert "sk-" not in str(progress_payload)
    assert "private" not in str(progress_payload)


def test_run_with_unexpected_workflow_failure_marks_job_failed_without_leaking(monkeypatch):
    class FailingExecutor:
        def submit(self, request):
            raise RuntimeError("sk-secret /private/problem.png")

        def is_active(self, job_id):
            return False

    monkeypatch.setattr(jobs, "job_run_executor", FailingExecutor())
    client = TestClient(app, raise_server_exceptions=False)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)

    response = client.post(f"/jobs/{job_id}/run")
    job_response_payload = client.get(f"/jobs/{job_id}").json()

    assert response.status_code == 503
    assert_error(response, "JOB_RUN_SUBMIT_FAILED")
    assert job_response_payload["status"] == "FAILED"
    assert job_response_payload["review_items"][-1]["safe_reason"] == "internal_error"
    assert "sk-" not in str(response.json())
    assert "private" not in str(response.json())
    assert "sk-" not in str(job_response_payload)
    assert "private" not in str(job_response_payload)


def test_run_with_live_progress_initialize_failure_returns_storage_error(monkeypatch):
    class FailingLiveProgressStore:
        def initialize(self, job_id, source_image_artifact_ids):
            raise OSError("disk /private/tmp/jobs failed")

    class CapturingExecutor:
        def __init__(self):
            self.requests = []

        def submit(self, request):
            self.requests.append(request)

        def is_active(self, job_id):
            return False

    executor = CapturingExecutor()
    monkeypatch.setattr(jobs, "job_run_executor", executor)
    monkeypatch.setattr(jobs, "_live_progress_store", lambda: FailingLiveProgressStore())
    client = TestClient(app, raise_server_exceptions=False)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)

    response = client.post(f"/jobs/{job_id}/run")
    job_response_payload = client.get(f"/jobs/{job_id}").json()

    assert response.status_code == 500
    assert_error(response, "STORAGE_WRITE_FAILED")
    assert executor.requests == []
    assert job_response_payload["status"] == "FAILED"
    assert job_response_payload["review_items"][-1]["safe_reason"] == "progress_write_failed"
    assert "private" not in str(response.json())
    assert "disk" not in str(response.json())


def test_run_requires_required_images_with_structured_error():
    client = TestClient(app)

    job_id = client.post("/jobs").json()["job_id"]
    response = client.post(f"/jobs/{job_id}/run")

    assert response.status_code == 409
    assert_error(response, "MISSING_REQUIRED_IMAGES")
    assert response.json()["detail"]["fields"] == {
        "missing_roles": ["problem", "teacher_solution"],
    }


def test_run_rejects_duplicate_running_job(monkeypatch):
    class CapturingExecutor:
        def submit(self, request):
            return None

        def is_active(self, job_id):
            return True

    monkeypatch.setattr(jobs, "job_run_executor", CapturingExecutor())
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)

    first = client.post(f"/jobs/{job_id}/run")
    second = client.post(f"/jobs/{job_id}/run")

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "JOB_ALREADY_RUNNING"


def test_review_items_endpoint_hides_internal_needs_review_items(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)

    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")
    response = client.get(f"/jobs/{job_id}/review-items")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_run_job_persists_review_correction_and_progress_events(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job = client.post("/jobs").json()
    job_id = job["job_id"]
    upload_required_images(client, job_id)

    response = client.post(f"/jobs/{job_id}/run")

    assert response.status_code == 202
    payload = client.get(f"/jobs/{job_id}").json()
    assert payload["status"] == "APPROVED"
    assert payload["latest_analysis_artifact_ids"]["review_correction"].startswith("review_")
    assert payload["latest_analysis_artifact_ids"]["progress_events"].startswith("events_")

    review_response = client.get(f"/jobs/{job_id}/review-correction")
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["job_id"] == job_id
    assert review_payload["revision_attempts"] == 1
    assert review_payload["tool_decisions"][-1]["tool_name"] == "mark_approved"
    assert review_payload["latest_gate_result"]["passed"] is True

    events_response = client.get(f"/jobs/{job_id}/progress-events")
    assert events_response.status_code == 200
    events_payload = events_response.json()
    assert events_payload["job_id"] == job_id
    assert len(events_payload["events"]) >= 1
    assert events_payload["events"][0]["message"] == "작업을 시작했습니다."
    assert "source_image_paths" not in events_payload["events"][0]


def test_progress_events_endpoint_returns_404_before_run():
    client = TestClient(app)
    job = client.post("/jobs").json()

    response = client.get(f"/jobs/{job['job_id']}/progress-events")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"


def test_progress_stream_replays_saved_progress_events_as_sse(monkeypatch):
    use_inline_job_executor(monkeypatch)
    monkeypatch.setattr(jobs.settings, "analysis_client", "mock")
    client = TestClient(app)
    job = client.post("/jobs").json()
    job_id = job["job_id"]
    upload_required_images(client, job_id)
    run_response = client.post(f"/jobs/{job_id}/run")

    response = client.get(f"/jobs/{job_id}/progress-stream")

    assert run_response.status_code == 202
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    body = response.text
    assert "id: evt_0000\n" in body
    assert "event: progress\n" in body
    assert "data:" in body
    assert '"message":"작업을 시작했습니다."' in body
    assert "event: complete\n" in body
    assert '"event_count":' in body
    assert "source_image_paths" not in body


def test_progress_stream_reads_live_events_with_cursor(monkeypatch):
    monkeypatch.setattr(jobs.settings, "analysis_client", "mock")
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    store = LocalArtifactStore(jobs.settings.storage_root)
    manifest = store.get_job(job_id)
    ids = {
        "problem": manifest.latest_image_artifact_ids["problem"],
        "teacher_solution": manifest.latest_image_artifact_ids["teacher_solution"],
    }
    store.start_analysis_run(job_id, source_image_artifact_ids=ids)
    live_store = jobs._live_progress_store()
    live_store.initialize(job_id, ids)
    live_store.append(
        job_id,
        jobs.ProgressEvent(
            event_id="evt_0000",
            job_id=job_id,
            sequence=0,
            phase="analysis",
            status="CREATED",
            message="작업을 시작했습니다.",
            attempt=0,
            max_attempts=2,
            scores=None,
            next_action="continue",
            created_at="2026-06-23T00:00:00Z",
        ),
    )
    live_store.append(
        job_id,
        jobs.ProgressEvent(
            event_id="evt_0001",
            job_id=job_id,
            sequence=1,
            phase="analysis",
            status="SPEC_EXTRACTED",
            message="원본 문제와 선생님 손풀이를 분석하고 있습니다.",
            attempt=0,
            max_attempts=2,
            scores=None,
            next_action="continue",
            created_at="2026-06-23T00:00:01Z",
        ),
    )
    manifest = store.get_job(job_id)
    manifest.status = "APPROVED"
    store.save_manifest(manifest)

    response = client.get(f"/jobs/{job_id}/progress-stream?after=evt_0000")

    assert response.status_code == 200
    assert "id: evt_0000" not in response.text
    assert "id: evt_0001" in response.text
    assert "event: progress" in response.text
    assert "event: complete" in response.text


def test_progress_stream_returns_404_before_run():
    client = TestClient(app)
    job = client.post("/jobs").json()

    response = client.get(f"/jobs/{job['job_id']}/progress-stream")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"


def test_sse_frame_serializes_korean_without_ascii_escape():
    frame = _sse_frame(
        event="progress",
        event_id="evt_0000",
        data={"message": "작업을 시작했습니다."},
    )

    assert frame == (
        'id: evt_0000\n'
        'event: progress\n'
        'data: {"message":"작업을 시작했습니다."}\n\n'
    )
    assert "\\uc791" not in frame
    assert frame.endswith("\n\n")


def test_sse_frame_omits_unsafe_event_id():
    frame = _sse_frame(
        event="progress",
        event_id="evt_0000\nevent: injected",
        data={"message": "작업을 시작했습니다."},
    )

    assert "id:" not in frame
    assert "event: injected" not in frame
    assert frame.startswith("event: progress\n")


def test_progress_event_stream_projects_public_fields_and_skips_malformed_events():
    valid_late_event = {
        "event_id": "evt_0002",
        "job_id": "job_test",
        "sequence": 2,
        "phase": "analysis",
        "status": "SPEC_EXTRACTED",
        "message": "원본 문제와 선생님 손풀이를 분석하고 있습니다.",
        "attempt": 0,
        "max_attempts": 2,
        "scores": None,
        "next_action": "continue",
        "created_at": "2026-06-23T00:00:02Z",
        "source_image_paths": {"problem": "/private/problem.png"},
    }
    valid_first_event = {
        **valid_late_event,
        "event_id": "evt_0001",
        "sequence": 1,
        "status": "CREATED",
        "message": "작업을 시작했습니다.",
        "created_at": "2026-06-23T00:00:01Z",
    }
    payload = {
        "job_id": "job_test",
        "events": [
            valid_late_event,
            {**valid_late_event, "event_id": "evt_0003", "sequence": "bad"},
            {**valid_late_event, "event_id": "evt_0004\nevent: injected", "sequence": 4},
            valid_first_event,
        ],
    }

    body = "".join(_progress_event_stream(payload))

    assert body.index("id: evt_0001") < body.index("id: evt_0002")
    assert "evt_0003" not in body
    assert "evt_0004" not in body
    assert "event: injected" not in body
    assert "source_image_paths" not in body
    assert "/private/problem.png" not in body
    assert '"event_count":2' in body


def test_get_unknown_job_returns_structured_404():
    client = TestClient(app)

    response = client.get("/jobs/job_unknown")

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")
    assert response.json()["detail"]["fields"] == {"job_id": "job_unknown"}


def test_get_rejects_encoded_path_traversal_job_id(monkeypatch, tmp_path):
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

    response = client.get("/jobs/%2e%2e")

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")


def test_run_rejects_encoded_path_traversal_job_id(monkeypatch, tmp_path):
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

    response = client.post("/jobs/%2e%2e/run")

    assert response.status_code == 404
    assert_error(response, "JOB_NOT_FOUND")


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


def test_settings_default_to_mock_analysis_client(monkeypatch):
    monkeypatch.delenv("CLEANSOLVE_ANALYSIS_CLIENT", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_ANALYSIS", raising=False)
    monkeypatch.delenv("OPENAI_ANALYSIS_IMAGE_DETAIL", raising=False)
    monkeypatch.delenv("OPENAI_ANALYSIS_TIMEOUT_SECONDS", raising=False)

    settings = Settings()

    assert settings.analysis_client == "mock"
    assert settings.openai_model_analysis == "gpt-5.5"
    assert settings.openai_model_validation == "gpt-5.5"
    assert settings.openai_model_image == "gpt-image-2"
    assert settings.openai_analysis_image_detail == "auto"
    assert settings.openai_analysis_timeout_seconds == 60
    assert settings.background_max_workers == 1
    assert settings.progress_poll_interval_ms == 250
    assert settings.progress_heartbeat_seconds == 15


def test_settings_reject_invalid_analysis_client(monkeypatch):
    monkeypatch.setenv("CLEANSOLVE_ANALYSIS_CLIENT", "invalid")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_reject_non_integer_openai_timeout(monkeypatch):
    monkeypatch.setenv("OPENAI_ANALYSIS_TIMEOUT_SECONDS", "abc")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_reject_non_positive_openai_timeout(monkeypatch):
    monkeypatch.setenv("OPENAI_ANALYSIS_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "env_name",
    [
        "CLEANSOLVE_BACKGROUND_MAX_WORKERS",
        "CLEANSOLVE_PROGRESS_POLL_INTERVAL_MS",
        "CLEANSOLVE_PROGRESS_HEARTBEAT_SECONDS",
    ],
)
def test_settings_reject_non_integer_background_progress_values(monkeypatch, env_name):
    monkeypatch.setenv(env_name, "abc")

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "env_name",
    [
        "CLEANSOLVE_BACKGROUND_MAX_WORKERS",
        "CLEANSOLVE_PROGRESS_POLL_INTERVAL_MS",
        "CLEANSOLVE_PROGRESS_HEARTBEAT_SECONDS",
    ],
)
def test_settings_reject_non_positive_background_progress_values(monkeypatch, env_name):
    monkeypatch.setenv(env_name, "0")

    with pytest.raises(ValidationError):
        Settings()


def test_manifest_store_rejects_invalid_workflow_status(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()

    with pytest.raises(ValidationError):
        store.update_after_run(
            job_id=manifest.job_id,
            status_value="INVALID",
            revision_attempts=1,
            review_items=[],
        )

    assert store.get_job(manifest.job_id).status == "CREATED"


def test_store_start_analysis_run_marks_job_running(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    store.save_manifest(manifest)

    updated = store.start_analysis_run(
        manifest.job_id,
        source_image_artifact_ids=ids,
    )

    assert updated.status == "RUNNING"
    assert updated.latest_analysis_artifact_ids["candidate_spec"] is None
    assert updated.latest_analysis_artifact_ids["progress_events"] is None


def test_store_start_analysis_run_rejects_terminal_job(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    manifest.status = "APPROVED"
    store.save_manifest(manifest)

    with pytest.raises(HTTPException) as exc_info:
        store.start_analysis_run(
            manifest.job_id,
            source_image_artifact_ids=ids,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "JOB_RUN_NOT_RESTARTABLE"
    assert exc_info.value.detail["fields"] == {
        "job_id": manifest.job_id,
        "status": "APPROVED",
    }


def test_store_start_analysis_run_rejects_running_job(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    manifest.status = "RUNNING"
    store.save_manifest(manifest)

    with pytest.raises(HTTPException) as exc_info:
        store.start_analysis_run(
            manifest.job_id,
            source_image_artifact_ids=ids,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "JOB_ALREADY_RUNNING"
    assert exc_info.value.detail["fields"] == {"job_id": manifest.job_id}


def test_store_save_failed_background_run_persists_only_safe_progress_events(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    manifest.status = "RUNNING"
    store.save_manifest(manifest)
    failed_event = {
        "event_id": "evt_0000",
        "job_id": manifest.job_id,
        "sequence": 0,
        "phase": "failed",
        "status": "FAILED",
        "message": "작업이 실패했습니다.",
        "attempt": 0,
        "max_attempts": 2,
        "scores": None,
        "next_action": "fail",
        "created_at": "2026-06-23T00:00:00Z",
    }

    updated = store.save_failed_background_run(
        manifest.job_id,
        reason="configuration_error",
        review_item={
            "type": "analysis_adapter_failed",
            "client": "openai",
            "retryable": True,
            "review_reason": None,
            "safe_reason": "configuration_error",
        },
        progress_events_payload={
            "job_id": manifest.job_id,
            "events": [failed_event],
        },
        source_image_artifact_ids=ids,
    )

    assert updated.status == "FAILED"
    assert updated.review_items[-1]["safe_reason"] == "configuration_error"
    assert updated.latest_analysis_artifact_ids["candidate_spec"] is None
    assert updated.latest_analysis_artifact_ids["validation_report"] is None
    assert updated.latest_analysis_artifact_ids["correction_plan"] is None
    assert updated.latest_analysis_artifact_ids["review_correction"] is None
    assert updated.latest_analysis_artifact_ids["progress_events"].startswith("events_")
    payload = store.read_latest_analysis_payload(manifest.job_id, "progress_events")
    assert payload == {"job_id": manifest.job_id, "events": [failed_event]}


def test_store_save_failed_background_run_persists_only_safe_review_item_fields(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    manifest.status = "RUNNING"
    store.save_manifest(manifest)

    updated = store.save_failed_background_run(
        manifest.job_id,
        reason="sk-secret /private/problem.png",
        review_item={
            "type": "analysis_adapter_failed",
            "client": "openai",
            "retryable": True,
            "review_reason": "/private/path",
            "safe_reason": "caller_reason",
            "exception_message": "raw exception",
            "local_path": "/tmp/private/input.png",
            "prompt": "raw prompt",
            "api_key": "sk-secret",
            "source_image_paths": {"problem": "/tmp/private/problem.png"},
            "raw_model_output": "raw model output",
        },
        progress_events_payload={"job_id": manifest.job_id, "events": []},
        source_image_artifact_ids=ids,
    )

    assert updated.review_items[-1] == {
        "type": "analysis_adapter_failed",
        "client": "openai",
        "retryable": True,
        "review_reason": None,
        "safe_reason": "internal_error",
    }
    assert "sk-" not in str(updated.model_dump(mode="json"))
    assert "/private" not in str(updated.model_dump(mode="json"))
    assert "raw prompt" not in str(updated.model_dump(mode="json"))
    assert "raw model output" not in str(updated.model_dump(mode="json"))


@pytest.mark.parametrize("status_value", ["CREATED", "APPROVED"])
def test_store_save_failed_background_run_rejects_non_running_job(tmp_path, status_value):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    manifest.status = status_value
    store.save_manifest(manifest)

    with pytest.raises(HTTPException) as exc_info:
        store.save_failed_background_run(
            manifest.job_id,
            reason="configuration_error",
            review_item={
                "type": "analysis_adapter_failed",
                "client": "openai",
                "retryable": True,
                "review_reason": None,
            },
            progress_events_payload={"job_id": manifest.job_id, "events": []},
            source_image_artifact_ids=ids,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "JOB_RUN_NOT_RESTARTABLE"
    assert exc_info.value.detail["fields"] == {
        "job_id": manifest.job_id,
        "status": status_value,
    }
    assert store.get_job(manifest.job_id).status == status_value


def test_old_manifest_json_defaults_analysis_artifact_fields(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    job_id = "job_00000000000000000000000000000000"
    job_root = tmp_path / "jobs" / job_id
    job_root.mkdir(parents=True)
    (job_root / "manifest.json").write_text(
        """
{
  "job_id": "job_00000000000000000000000000000000",
  "status": "CREATED",
  "created_at": "2026-06-16T00:00:00Z",
  "updated_at": "2026-06-16T00:00:00Z",
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

    manifest = store.get_job(job_id)

    assert manifest.analysis_artifacts == {
        "candidate_spec": [],
        "validation_report": [],
        "correction_plan": [],
        "review_correction": [],
        "progress_events": [],
    }
    assert manifest.latest_analysis_artifact_ids == {
        "candidate_spec": None,
        "validation_report": None,
        "correction_plan": None,
        "review_correction": None,
        "progress_events": None,
    }
    assert manifest.render_artifacts == []
    assert manifest.latest_render_artifact_id is None
    assert manifest.export_artifacts == []
    assert manifest.latest_export_artifact_id is None


def test_old_manifest_json_normalizes_partial_analysis_artifact_fields(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    job_id = "job_00000000000000000000000000000000"
    job_root = tmp_path / "jobs" / job_id
    job_root.mkdir(parents=True)
    (job_root / "manifest.json").write_text(
        f"""
{{
  "job_id": "job_00000000000000000000000000000000",
  "status": "APPROVED",
  "created_at": "2026-06-16T00:00:00Z",
  "updated_at": "2026-06-16T00:00:00Z",
  "revision_attempts": 1,
  "review_items": [],
  "image_artifacts": {{
    "problem": [],
    "teacher_solution": []
  }},
  "latest_image_artifact_ids": {{
    "problem": null,
    "teacher_solution": null
  }},
  "analysis_artifacts": {{
    "candidate_spec": [
      {{
        "artifact_id": "spec_old",
        "type": "candidate_spec",
        "relative_path": "artifacts/specs/spec_old.json",
        "size_bytes": 2,
        "sha256": "{'a' * 64}",
        "created_at": "2026-06-16T00:00:00Z",
        "source_image_artifact_ids": {{
          "problem": "img_problem_old",
          "teacher_solution": "img_teacher_old"
        }}
      }}
    ],
    "validation_report": [],
    "correction_plan": []
  }},
  "latest_analysis_artifact_ids": {{
    "candidate_spec": "spec_old",
    "validation_report": null,
    "correction_plan": "correction_old"
  }}
}}
""",
        encoding="utf-8",
    )

    manifest = store.get_job(job_id)

    assert manifest.analysis_artifacts["candidate_spec"][0].artifact_id == "spec_old"
    assert manifest.analysis_artifacts["validation_report"] == []
    assert manifest.analysis_artifacts["correction_plan"] == []
    assert manifest.analysis_artifacts["review_correction"] == []
    assert manifest.analysis_artifacts["progress_events"] == []
    assert manifest.latest_analysis_artifact_ids == {
        "candidate_spec": "spec_old",
        "validation_report": None,
        "correction_plan": "correction_old",
        "review_correction": None,
        "progress_events": None,
    }


def test_store_saves_analysis_outputs_and_updates_manifest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    source_ids = {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }
    manifest.latest_image_artifact_ids = source_ids
    store.save_manifest(manifest)
    store.start_analysis_run(
        manifest.job_id,
        source_image_artifact_ids=source_ids,
    )

    updated = store.save_analysis_outputs(
        job_id=manifest.job_id,
        status_value="APPROVED",
        revision_attempts=1,
        review_items=[],
        candidate_spec_payload={
            "job_id": manifest.job_id,
            "version": 1,
            "source_images": {
                "problem_image_id": "img_problem_123",
                "teacher_solution_image_id": "img_teacher_456",
            },
        },
        validation_report_payload={
            "report_id": "report_1",
            "passed": True,
            "issues": [],
        },
        correction_plan_payload={
            "job_id": manifest.job_id,
            "revision_attempts": 1,
            "correction_plans": [],
        },
        source_image_artifact_ids=source_ids,
    )

    assert updated.latest_analysis_artifact_ids["candidate_spec"].startswith("spec_")
    assert updated.latest_analysis_artifact_ids["validation_report"].startswith("report_")
    assert updated.latest_analysis_artifact_ids["correction_plan"].startswith("correction_")
    assert updated.latest_analysis_artifact_ids["review_correction"] is None
    assert updated.latest_analysis_artifact_ids["progress_events"] is None

    for artifact_type in ("candidate_spec", "validation_report", "correction_plan"):
        artifacts = updated.analysis_artifacts[artifact_type]
        assert len(artifacts) == 1
        artifact = artifacts[0]
        artifact_path = tmp_path / "jobs" / manifest.job_id / artifact.relative_path
        assert artifact_path.exists()
        assert artifact.size_bytes == len(artifact_path.read_bytes())
        assert artifact.source_image_artifact_ids == source_ids
    assert updated.analysis_artifacts["review_correction"] == []
    assert updated.analysis_artifacts["progress_events"] == []


def test_read_latest_analysis_payload_rejects_path_escape_from_corrupt_manifest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    store.save_manifest(manifest)
    store.start_analysis_run(
        manifest.job_id,
        source_image_artifact_ids=ids,
    )

    updated = store.save_analysis_outputs(
        job_id=manifest.job_id,
        status_value="APPROVED",
        revision_attempts=1,
        review_items=[],
        candidate_spec_payload={"job_id": manifest.job_id, "version": 1},
        validation_report_payload={"report_id": "report_1", "passed": True, "issues": []},
        correction_plan_payload={
            "job_id": manifest.job_id,
            "revision_attempts": 1,
            "correction_plans": [],
        },
        source_image_artifact_ids=ids,
    )

    artifact = updated.analysis_artifacts["candidate_spec"][0]
    artifact.relative_path = "../escape.json"
    store.save_manifest(updated)
    (tmp_path / "jobs" / "escape.json").write_text(
        '{"escaped": true}',
        encoding="utf-8",
    )

    with pytest.raises(HTTPException) as exc_info:
        store.read_latest_analysis_payload(manifest.job_id, "candidate_spec")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"
    assert "escape.json" not in str(exc_info.value.detail)

    absolute_path = tmp_path / "escape-absolute.json"
    absolute_path.write_text('{"escaped": true}', encoding="utf-8")
    artifact.relative_path = str(absolute_path)
    store.save_manifest(updated)

    with pytest.raises(HTTPException) as exc_info:
        store.read_latest_analysis_payload(manifest.job_id, "candidate_spec")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"
    assert str(absolute_path) not in str(exc_info.value.detail)


def test_read_latest_analysis_payload_rejects_symlink_escape_from_corrupt_manifest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    manifest.latest_image_artifact_ids = ids
    store.save_manifest(manifest)
    store.start_analysis_run(
        manifest.job_id,
        source_image_artifact_ids=ids,
    )

    updated = store.save_analysis_outputs(
        job_id=manifest.job_id,
        status_value="APPROVED",
        revision_attempts=1,
        review_items=[],
        candidate_spec_payload={"job_id": manifest.job_id, "version": 1},
        validation_report_payload={"report_id": "report_1", "passed": True, "issues": []},
        correction_plan_payload={
            "job_id": manifest.job_id,
            "revision_attempts": 1,
            "correction_plans": [],
        },
        source_image_artifact_ids=ids,
    )

    outside_path = tmp_path / "outside.json"
    outside_path.write_text('{"escaped": true}', encoding="utf-8")
    link_path = (
        tmp_path
        / "jobs"
        / manifest.job_id
        / "artifacts"
        / "specs"
        / "spec_escape.json"
    )
    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        link_path.symlink_to(outside_path)
    except OSError as exc:
        pytest.skip(f"symlink creation is not available: {exc}")

    artifact = updated.analysis_artifacts["candidate_spec"][0]
    artifact.relative_path = "artifacts/specs/spec_escape.json"
    store.save_manifest(updated)

    with pytest.raises(HTTPException) as exc_info:
        store.read_latest_analysis_payload(manifest.job_id, "candidate_spec")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"
    assert "outside.json" not in str(exc_info.value.detail)


def test_store_saves_spec_patch_outputs_without_replacing_correction_plan(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    source_ids = {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }
    manifest.latest_image_artifact_ids = source_ids
    store.save_manifest(manifest)
    store.start_analysis_run(
        manifest.job_id,
        source_image_artifact_ids=source_ids,
    )
    initial = store.save_analysis_outputs(
        job_id=manifest.job_id,
        status_value="APPROVED",
        revision_attempts=1,
        review_items=[],
        candidate_spec_payload={"job_id": manifest.job_id, "version": 1},
        validation_report_payload={"report_id": "report_1", "passed": True, "issues": []},
        correction_plan_payload={
            "job_id": manifest.job_id,
            "revision_attempts": 1,
            "correction_plans": [],
        },
        source_image_artifact_ids=source_ids,
    )
    initial_correction_id = initial.latest_analysis_artifact_ids["correction_plan"]

    updated = store.save_spec_patch_outputs(
        job_id=manifest.job_id,
        candidate_spec_payload={"job_id": manifest.job_id, "version": 2},
        validation_report_payload={"report_id": "report_2", "passed": True, "issues": []},
        source_image_artifact_ids=source_ids,
        expected_candidate_spec_artifact_id=initial.latest_analysis_artifact_ids["candidate_spec"],
    )

    assert updated.latest_analysis_artifact_ids["candidate_spec"] != initial.latest_analysis_artifact_ids["candidate_spec"]
    assert updated.latest_analysis_artifact_ids["validation_report"] != initial.latest_analysis_artifact_ids["validation_report"]
    assert updated.latest_analysis_artifact_ids["correction_plan"] == initial_correction_id
    assert len(updated.analysis_artifacts["candidate_spec"]) == 2
    assert len(updated.analysis_artifacts["validation_report"]) == 2
    assert len(updated.analysis_artifacts["correction_plan"]) == 1
    assert len(updated.analysis_artifacts["review_correction"]) == 0
    assert len(updated.analysis_artifacts["progress_events"]) == 0
    assert store.read_latest_analysis_payload(manifest.job_id, "candidate_spec")["version"] == 2


def test_store_rejects_spec_patch_outputs_when_latest_inputs_changed(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    manifest.latest_image_artifact_ids = {
        "problem": "img_problem_new",
        "teacher_solution": "img_teacher_new",
    }
    store.save_manifest(manifest)

    with pytest.raises(HTTPException) as exc_info:
        store.save_spec_patch_outputs(
            job_id=manifest.job_id,
            candidate_spec_payload={"job_id": manifest.job_id, "version": 2},
            validation_report_payload={"report_id": "report_2", "passed": True, "issues": []},
            source_image_artifact_ids={
                "problem": "img_problem_old",
                "teacher_solution": "img_teacher_old",
            },
            expected_candidate_spec_artifact_id=None,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "ANALYSIS_SOURCE_CHANGED"


def test_store_rejects_spec_patch_outputs_when_candidate_spec_latest_changed(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    source_ids = {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }
    manifest.latest_image_artifact_ids = source_ids
    manifest.latest_analysis_artifact_ids["candidate_spec"] = "spec_latest"
    store.save_manifest(manifest)

    with pytest.raises(HTTPException) as exc_info:
        store.save_spec_patch_outputs(
            job_id=manifest.job_id,
            candidate_spec_payload={"job_id": manifest.job_id, "version": 2},
            validation_report_payload={"report_id": "report_2", "passed": True, "issues": []},
            source_image_artifact_ids=source_ids,
            expected_candidate_spec_artifact_id="spec_stale",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "SPEC_VERSION_CONFLICT"
    assert exc_info.value.detail["fields"] == {
        "expected_candidate_spec_artifact_id": "spec_stale",
        "latest_candidate_spec_artifact_id": "spec_latest",
    }


def test_store_saves_and_reads_rendered_preview_artifact(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    source_ids = {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }
    svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'

    updated, artifact = store.save_render_artifact(
        job_id=manifest.job_id,
        svg=svg,
        candidate_spec_artifact_id="spec_123",
        source_image_artifact_ids=source_ids,
    )
    preview = store.rendered_preview_response(manifest.job_id)

    assert artifact.artifact_id.startswith("render_")
    assert artifact.type == "overlay_svg"
    assert artifact.candidate_spec_artifact_id == "spec_123"
    assert artifact.source_image_artifact_ids == source_ids
    assert updated.latest_render_artifact_id == artifact.artifact_id
    assert len(updated.render_artifacts) == 1
    assert preview == {
        "job_id": manifest.job_id,
        "artifact": artifact.model_dump(mode="json"),
        "svg": svg,
    }


def test_render_artifact_reads_reject_path_escape_from_corrupt_manifest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = source_ids()
    _, artifact = store.save_render_artifact(
        job_id=manifest.job_id,
        svg='<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        candidate_spec_artifact_id="spec_123",
        source_image_artifact_ids=ids,
    )

    current_manifest = store.get_job(manifest.job_id)
    current_manifest.render_artifacts[0].relative_path = "../escape.svg"
    store.save_manifest(current_manifest)
    (tmp_path / "jobs" / "escape.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>escaped</text></svg>',
        encoding="utf-8",
    )

    for call in (
        lambda: store.rendered_preview_response(manifest.job_id),
        lambda: store.latest_render_artifact(manifest.job_id),
    ):
        with pytest.raises(HTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "RENDER_ARTIFACT_NOT_FOUND"
        assert "escape.svg" not in str(exc_info.value.detail)

    assert artifact.artifact_id == current_manifest.latest_render_artifact_id


def test_store_rejects_render_artifact_when_candidate_spec_is_not_latest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    manifest.latest_analysis_artifact_ids["candidate_spec"] = "spec_latest"
    store.save_manifest(manifest)

    with pytest.raises(HTTPException) as exc_info:
        store.save_render_artifact(
            job_id=manifest.job_id,
            svg="<svg></svg>",
            candidate_spec_artifact_id="spec_stale",
            source_image_artifact_ids={
                "problem": "img_problem_123",
                "teacher_solution": "img_teacher_456",
            },
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "ANALYSIS_SOURCE_CHANGED"


def test_store_saves_and_reads_export_artifact(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    source_ids = {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }
    manifest.latest_image_artifact_ids = source_ids
    manifest.latest_analysis_artifact_ids["candidate_spec"] = "spec_123"
    manifest.latest_render_artifact_id = "render_123"
    store.save_manifest(manifest)

    updated, artifact = store.save_export_artifact(
        job_id=manifest.job_id,
        png_bytes=b"\x89PNG\r\n\x1a\nexport",
        candidate_spec_artifact_id="spec_123",
        render_artifact_id="render_123",
        source_image_artifact_ids=source_ids,
    )

    assert artifact.artifact_id.startswith("export_")
    assert artifact.format == "png"
    assert artifact.mime_type == "image/png"
    assert artifact.relative_path == f"artifacts/exports/{artifact.artifact_id}.png"
    assert artifact.candidate_spec_artifact_id == "spec_123"
    assert artifact.render_artifact_id == "render_123"
    assert artifact.source_image_artifact_ids == source_ids
    assert updated.latest_export_artifact_id == artifact.artifact_id
    assert len(updated.export_artifacts) == 1
    assert store.export_artifacts_response(manifest.job_id)["latest_export_artifact_id"] == artifact.artifact_id
    assert store.latest_export_response(manifest.job_id) == {
        "job_id": manifest.job_id,
        "artifact": artifact.model_dump(mode="json"),
    }
    download_artifact, download_path = store.export_download(manifest.job_id, artifact.artifact_id)
    assert download_artifact == artifact
    assert download_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_store_rejects_export_when_candidate_or_render_or_source_changed(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    latest_source_ids = {
        "problem": "img_problem_latest",
        "teacher_solution": "img_teacher_latest",
    }
    manifest.latest_image_artifact_ids = latest_source_ids
    manifest.latest_analysis_artifact_ids["candidate_spec"] = "spec_latest"
    manifest.latest_render_artifact_id = "render_latest"
    store.save_manifest(manifest)

    stale_cases = [
        {
            "candidate_spec_artifact_id": "spec_stale",
            "render_artifact_id": "render_latest",
            "source_image_artifact_ids": latest_source_ids,
        },
        {
            "candidate_spec_artifact_id": "spec_latest",
            "render_artifact_id": "render_stale",
            "source_image_artifact_ids": latest_source_ids,
        },
        {
            "candidate_spec_artifact_id": "spec_latest",
            "render_artifact_id": "render_latest",
            "source_image_artifact_ids": {
                "problem": "img_problem_old",
                "teacher_solution": "img_teacher_latest",
            },
        },
    ]

    for stale_case in stale_cases:
        with pytest.raises(HTTPException) as exc_info:
            store.save_export_artifact(
                job_id=manifest.job_id,
                png_bytes=b"\x89PNG\r\n\x1a\nexport",
                **stale_case,
            )
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "EXPORT_SOURCE_CHANGED"


def test_store_latest_export_and_download_return_404_before_export(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()

    for call in (
        lambda: store.latest_export_response(manifest.job_id),
        lambda: store.export_download(manifest.job_id, "export_unknown"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "EXPORT_ARTIFACT_NOT_FOUND"


def test_store_rejects_export_download_path_escape_from_corrupt_manifest(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    manifest.export_artifacts = [
        ExportArtifact(
            artifact_id="export_escape",
            format="png",
            mime_type="image/png",
            relative_path="../escape.png",
            size_bytes=1,
            sha256="a" * 64,
            created_at="2026-06-17T00:00:00Z",
            candidate_spec_artifact_id="spec_123",
            render_artifact_id="render_123",
            source_image_artifact_ids={
                "problem": "img_problem_123",
                "teacher_solution": "img_teacher_456",
            },
        )
    ]
    manifest.latest_export_artifact_id = "export_escape"
    store.save_manifest(manifest)
    (tmp_path / "jobs" / "escape.png").write_bytes(b"\x89PNG\r\n\x1a\nescape")

    for call in (
        lambda: store.latest_export_response(manifest.job_id),
        lambda: store.export_download(manifest.job_id, "export_escape"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "EXPORT_ARTIFACT_NOT_FOUND"


def test_store_rejects_empty_export_bytes_without_writing_file(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    source_ids = {
        "problem": "img_problem_123",
        "teacher_solution": "img_teacher_456",
    }
    manifest.latest_image_artifact_ids = source_ids
    manifest.latest_analysis_artifact_ids["candidate_spec"] = "spec_123"
    manifest.latest_render_artifact_id = "render_123"
    store.save_manifest(manifest)

    with pytest.raises(HTTPException) as exc_info:
        store.save_export_artifact(
            job_id=manifest.job_id,
            png_bytes=b"",
            candidate_spec_artifact_id="spec_123",
            render_artifact_id="render_123",
            source_image_artifact_ids=source_ids,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["code"] == "STORAGE_WRITE_FAILED"
    assert not (tmp_path / "jobs" / manifest.job_id / "artifacts" / "exports").exists()


def test_store_rejects_analysis_outputs_when_latest_inputs_changed(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    manifest.latest_image_artifact_ids = {
        "problem": "img_problem_new",
        "teacher_solution": "img_teacher_new",
    }
    store.save_manifest(manifest)
    store.start_analysis_run(
        manifest.job_id,
        source_image_artifact_ids={
            "problem": "img_problem_new",
            "teacher_solution": "img_teacher_new",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        store.save_analysis_outputs(
            job_id=manifest.job_id,
            status_value="APPROVED",
            revision_attempts=1,
            review_items=[],
            candidate_spec_payload={"job_id": manifest.job_id},
            validation_report_payload={"passed": True},
            correction_plan_payload={"correction_plans": []},
            source_image_artifact_ids={
                "problem": "img_problem_old",
                "teacher_solution": "img_teacher_old",
            },
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "ANALYSIS_SOURCE_CHANGED"


def test_read_latest_analysis_payload_rejects_invalid_internal_artifact_type(tmp_path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()

    with pytest.raises(ValueError):
        store.read_latest_analysis_payload(manifest.job_id, "unknown_type")


def test_analysis_artifact_routes_return_structured_404_before_run():
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]

    for path, artifact_type in [
        ("candidate-spec", "candidate_spec"),
        ("validation-report", "validation_report"),
        ("correction-plan", "correction_plan"),
        ("review-correction", "review_correction"),
        ("progress-events", "progress_events"),
    ]:
        response = client.get(f"/jobs/{job_id}/{path}")

        assert response.status_code == 404
        assert_error(response, "ANALYSIS_ARTIFACT_NOT_FOUND")
        assert response.json()["detail"]["fields"] == {
            "artifact_type": artifact_type,
        }


def test_run_persists_analysis_artifacts_and_routes_return_latest_payloads(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)

    job_before_run = client.get(f"/jobs/{job_id}").json()
    expected_source_ids = job_before_run["latest_image_artifact_ids"]
    run_response = client.post(f"/jobs/{job_id}/run")
    run_payload = client.get(f"/jobs/{job_id}").json()

    assert run_response.status_code == 202
    assert run_response.json()["status"] == "RUNNING"
    assert run_payload["status"] == "APPROVED"
    assert set(run_payload["analysis_artifacts"]) == {
        "candidate_spec",
        "validation_report",
        "correction_plan",
        "review_correction",
        "progress_events",
    }
    assert all(run_payload["latest_analysis_artifact_ids"].values())
    assert len(run_payload["analysis_artifacts"]["candidate_spec"]) == 1
    assert len(run_payload["analysis_artifacts"]["validation_report"]) == 1
    assert len(run_payload["analysis_artifacts"]["correction_plan"]) == 1
    assert len(run_payload["analysis_artifacts"]["review_correction"]) == 1
    assert len(run_payload["analysis_artifacts"]["progress_events"]) == 1

    artifacts_response = client.get(f"/jobs/{job_id}/artifacts")
    candidate_response = client.get(f"/jobs/{job_id}/candidate-spec")
    validation_response = client.get(f"/jobs/{job_id}/validation-report")
    correction_response = client.get(f"/jobs/{job_id}/correction-plan")

    assert artifacts_response.status_code == 200
    assert artifacts_response.json()["latest_analysis_artifact_ids"] == run_payload[
        "latest_analysis_artifact_ids"
    ]
    assert candidate_response.status_code == 200
    assert candidate_response.json()["source_images"] == {
        "problem_image_id": expected_source_ids["problem"],
        "teacher_solution_image_id": expected_source_ids["teacher_solution"],
    }
    assert validation_response.status_code == 200
    assert validation_response.json()["passed"] is True
    assert correction_response.status_code == 200
    assert correction_response.json()["job_id"] == job_id
    assert correction_response.json()["revision_attempts"] == 1
    assert isinstance(correction_response.json()["correction_plans"], list)


def test_patch_spec_route_applies_allowed_change_and_appends_artifacts(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    run_response = client.post(f"/jobs/{job_id}/run")
    run_payload = client.get(f"/jobs/{job_id}").json()
    original_spec_id = run_payload["latest_analysis_artifact_ids"]["candidate_spec"]
    original_report_id = run_payload["latest_analysis_artifact_ids"]["validation_report"]

    response = client.patch(
        f"/jobs/{job_id}/spec",
        json={
            "client_spec_version": 1,
            "element_id": "el_freehand_dimension_001",
            "operation": "update_element",
            "changes": {"geometry.target_anchor_end": [610, 380]},
        },
    )

    assert run_response.status_code == 202
    assert response.status_code == 200
    payload = response.json()
    patched_element = next(
        element
        for element in payload["candidate_spec"]["elements"]
        if element["id"] == "el_freehand_dimension_001"
    )
    assert payload["candidate_spec"]["version"] == 2
    assert patched_element["geometry"]["target_anchor_end"] == [610, 380]
    assert patched_element["revision_history"][-1]["source"] == "user_patch"
    assert payload["candidate_spec_artifact_id"] != original_spec_id
    assert payload["validation_report_artifact_id"] != original_report_id
    assert payload["latest_analysis_artifact_ids"]["correction_plan"] == run_payload[
        "latest_analysis_artifact_ids"
    ]["correction_plan"]
    artifacts = client.get(f"/jobs/{job_id}/artifacts").json()["analysis_artifacts"]
    assert len(artifacts["candidate_spec"]) == 2
    assert len(artifacts["validation_report"]) == 2
    assert len(artifacts["correction_plan"]) == 1


def test_patch_spec_route_rejects_stale_client_version(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")

    response = client.patch(
        f"/jobs/{job_id}/spec",
        json={
            "client_spec_version": 0,
            "element_id": "el_freehand_dimension_001",
            "operation": "update_element",
            "changes": {"geometry.target_anchor_end": [610, 380]},
        },
    )

    assert response.status_code == 422


def test_patch_spec_route_reports_version_conflict_without_changing_latest_spec(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")
    first_patch = client.patch(
        f"/jobs/{job_id}/spec",
        json={
            "client_spec_version": 1,
            "element_id": "el_freehand_dimension_001",
            "operation": "update_element",
            "changes": {"geometry.target_anchor_end": [610, 380]},
        },
    )
    latest_before_conflict = client.get(f"/jobs/{job_id}/candidate-spec").json()

    response = client.patch(
        f"/jobs/{job_id}/spec",
        json={
            "client_spec_version": 1,
            "element_id": "el_freehand_dimension_001",
            "operation": "update_element",
            "changes": {"geometry.target_anchor_end": [620, 390]},
        },
    )

    assert first_patch.status_code == 200
    assert response.status_code == 409
    assert_error(response, "SPEC_VERSION_CONFLICT")
    assert response.json()["detail"]["fields"] == {
        "client_spec_version": 1,
        "server_spec_version": 2,
    }
    assert client.get(f"/jobs/{job_id}/candidate-spec").json() == latest_before_conflict


def test_patch_spec_route_rejects_disallowed_path_without_changing_latest_spec(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")
    latest_before_rejection = client.get(f"/jobs/{job_id}/candidate-spec").json()

    response = client.patch(
        f"/jobs/{job_id}/spec",
        json={
            "client_spec_version": 1,
            "element_id": "el_freehand_dimension_001",
            "operation": "update_element",
            "changes": {"geometry.visible_strokes": []},
        },
    )

    assert response.status_code == 400
    assert_error(response, "SPEC_PATCH_REJECTED")
    assert response.json()["detail"]["fields"]["reason"] == "path_not_allowed"
    assert client.get(f"/jobs/{job_id}/candidate-spec").json() == latest_before_rejection


def test_patch_spec_route_returns_spec_not_ready_before_run():
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]

    response = client.patch(
        f"/jobs/{job_id}/spec",
        json={
            "client_spec_version": 1,
            "element_id": "el_freehand_dimension_001",
            "operation": "update_element",
            "changes": {"geometry.target_anchor_end": [610, 380]},
        },
    )

    assert response.status_code == 409
    assert_error(response, "SPEC_NOT_READY")


def test_render_route_saves_svg_artifact_and_rendered_preview_returns_latest(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")

    response = client.post(f"/jobs/{job_id}/render")
    preview_response = client.get(f"/jobs/{job_id}/rendered-preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact"]["artifact_id"].startswith("render_")
    assert payload["artifact"]["type"] == "overlay_svg"
    assert payload["svg"].startswith("<svg ")
    assert preview_response.status_code == 200
    assert preview_response.json() == payload
    job_payload = client.get(f"/jobs/{job_id}").json()
    assert job_payload["latest_render_artifact_id"] == payload["artifact"]["artifact_id"]


def test_rendered_preview_route_returns_404_before_render():
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]

    response = client.get(f"/jobs/{job_id}/rendered-preview")

    assert response.status_code == 404
    assert_error(response, "RENDER_ARTIFACT_NOT_FOUND")


def run_and_render_job(client: TestClient) -> tuple[str, dict[str, object], dict[str, object]]:
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    run_response = client.post(f"/jobs/{job_id}/run")
    assert run_response.status_code == 202
    run_payload = client.get(f"/jobs/{job_id}").json()
    render_payload = client.post(f"/jobs/{job_id}/render").json()
    return job_id, run_payload, render_payload


def test_export_route_requires_approved_job():
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]

    response = client.post(f"/jobs/{job_id}/export", json={"format": "png"})

    assert response.status_code == 409
    assert_error(response, "EXPORT_JOB_NOT_READY")


def test_export_route_requires_latest_render_artifact(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)
    client.post(f"/jobs/{job_id}/run")

    response = client.post(f"/jobs/{job_id}/export", json={"format": "png"})

    assert response.status_code == 409
    assert_error(response, "EXPORT_RENDER_NOT_READY")


def test_export_route_rejects_unsupported_format(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id, _, _ = run_and_render_job(client)

    response = client.post(f"/jobs/{job_id}/export", json={"format": "pdf"})

    assert response.status_code == 400
    assert_error(response, "UNSUPPORTED_EXPORT_FORMAT")
    assert response.json()["detail"]["fields"] == {
        "allowed": ["png"],
        "received": "pdf",
    }


def test_export_route_saves_png_artifact_and_downloads_it(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id, run_payload, render_payload = run_and_render_job(client)

    response = client.post(f"/jobs/{job_id}/export", json={"format": "png"})

    assert response.status_code == 200
    payload = response.json()
    artifact = payload["artifact"]
    assert artifact["artifact_id"].startswith("export_")
    assert artifact["format"] == "png"
    assert artifact["mime_type"] == "image/png"
    assert artifact["relative_path"] == f"artifacts/exports/{artifact['artifact_id']}.png"
    assert artifact["candidate_spec_artifact_id"] == run_payload["latest_analysis_artifact_ids"]["candidate_spec"]
    assert artifact["render_artifact_id"] == render_payload["artifact"]["artifact_id"]
    assert artifact["source_image_artifact_ids"] == run_payload["latest_image_artifact_ids"]
    assert payload["latest_export_artifact_id"] == artifact["artifact_id"]

    exports_response = client.get(f"/jobs/{job_id}/exports")
    latest_response = client.get(f"/jobs/{job_id}/exports/latest")
    download_response = client.get(f"/jobs/{job_id}/exports/{artifact['artifact_id']}/download")

    assert exports_response.status_code == 200
    assert exports_response.json()["latest_export_artifact_id"] == artifact["artifact_id"]
    assert exports_response.json()["export_artifacts"] == [artifact]
    assert latest_response.status_code == 200
    assert latest_response.json() == {"job_id": job_id, "artifact": artifact}
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "image/png"
    assert download_response.headers["content-disposition"] == (
        f'attachment; filename="{artifact["artifact_id"]}.png"'
    )
    assert download_response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_latest_export_route_returns_404_before_export(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id, _, _ = run_and_render_job(client)

    response = client.get(f"/jobs/{job_id}/exports/latest")

    assert response.status_code == 404
    assert_error(response, "EXPORT_ARTIFACT_NOT_FOUND")


def test_export_download_returns_404_for_unknown_export_id(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id, _, _ = run_and_render_job(client)

    response = client.get(f"/jobs/{job_id}/exports/export_unknown/download")

    assert response.status_code == 404
    assert_error(response, "EXPORT_ARTIFACT_NOT_FOUND")


def test_export_route_rejects_stale_render_candidate_spec(monkeypatch):
    use_inline_job_executor(monkeypatch)
    client = TestClient(app)
    job_id, _, _ = run_and_render_job(client)
    patch_response = client.patch(
        f"/jobs/{job_id}/spec",
        json={
            "client_spec_version": 1,
            "element_id": "el_freehand_dimension_001",
            "operation": "update_element",
            "changes": {"geometry.target_anchor_end": [610, 380]},
        },
    )

    response = client.post(f"/jobs/{job_id}/export", json={"format": "png"})

    assert patch_response.status_code == 200
    assert response.status_code == 409
    assert_error(response, "EXPORT_RENDER_NOT_READY")
