from pathlib import Path

from cleansolve_ai import OpenAIConfigurationError
from cleansolve_api import background
from cleansolve_api.artifacts import LocalArtifactStore
from cleansolve_api.background import JobRunExecutor, JobRunRequest, run_job_worker
from cleansolve_api.live_progress import LiveProgressStore


def create_running_job(tmp_path: Path):
    store = LocalArtifactStore(tmp_path / "jobs")
    manifest = store.create_job()
    ids = {"problem": "img_problem_123", "teacher_solution": "img_teacher_456"}
    manifest.latest_image_artifact_ids = ids
    manifest.status = "RUNNING"
    store.save_manifest(manifest)
    live_store = LiveProgressStore(tmp_path / "jobs")
    live_store.initialize(manifest.job_id, ids)
    return store, live_store, manifest, ids


def request_for(job_id: str, ids: dict[str, str]) -> JobRunRequest:
    return JobRunRequest(
        job_id=job_id,
        source_image_artifact_ids=ids,
        analysis_client_kind="mock",
        openai_model_analysis="gpt-5.5",
        openai_analysis_image_detail="auto",
        openai_analysis_timeout_seconds=60,
    )


def test_job_worker_success_persists_outputs_and_progress(monkeypatch, tmp_path):
    store, live_store, manifest, ids = create_running_job(tmp_path)
    image_paths = {
        "problem": tmp_path / "problem.png",
        "teacher_solution": tmp_path / "teacher.png",
    }
    monkeypatch.setattr(store, "latest_image_artifact_paths", lambda _job_id: image_paths)

    run_job_worker(
        request_for(manifest.job_id, ids),
        store=store,
        live_progress_store=live_store,
        openai_api_key=None,
    )

    updated = store.get_job(manifest.job_id)
    assert updated.status == "APPROVED"
    assert updated.latest_analysis_artifact_ids["candidate_spec"].startswith("spec_")
    assert updated.latest_analysis_artifact_ids["progress_events"].startswith("events_")
    events_payload = store.read_latest_analysis_payload(manifest.job_id, "progress_events")
    assert events_payload["events"][0]["message"] == "작업을 시작했습니다."
    assert "source_image_paths" not in str(events_payload)


def test_job_worker_openai_failure_persists_safe_failed_progress(monkeypatch, tmp_path):
    store, live_store, manifest, ids = create_running_job(tmp_path)
    image_paths = {
        "problem": tmp_path / "problem.png",
        "teacher_solution": tmp_path / "teacher.png",
    }
    monkeypatch.setattr(store, "latest_image_artifact_paths", lambda _job_id: image_paths)
    monkeypatch.setattr(
        background,
        "run_mock_workflow",
        lambda **_kwargs: (_ for _ in ()).throw(OpenAIConfigurationError("sk-secret /private/problem.png")),
    )

    run_job_worker(
        request_for(manifest.job_id, ids).model_copy(update={"analysis_client_kind": "openai"}),
        store=store,
        live_progress_store=live_store,
        openai_api_key="sk-test",
    )

    updated = store.get_job(manifest.job_id)
    payload = store.read_latest_analysis_payload(manifest.job_id, "progress_events")
    assert updated.status == "FAILED"
    assert updated.review_items[-1]["safe_reason"] == "configuration_error"
    assert payload["events"][-1]["status"] == "FAILED"
    assert payload["events"][-1]["message"] == "작업이 실패했습니다."
    assert "sk-" not in str(updated.model_dump(mode="json"))
    assert "/private" not in str(updated.model_dump(mode="json"))
    assert "sk-" not in str(payload)
    assert "/private" not in str(payload)


def test_job_run_executor_tracks_active_jobs_until_worker_finishes():
    calls = []

    def worker(request: JobRunRequest):
        calls.append(request.job_id)

    executor = JobRunExecutor(max_workers=1, worker=worker)
    request = request_for(
        "job_00000000000000000000000000000000",
        {"problem": "img_problem_123", "teacher_solution": "img_teacher_456"},
    )

    executor.submit(request)
    executor.shutdown(wait=True)

    assert calls == [request.job_id]
    assert executor.is_active(request.job_id) is False
