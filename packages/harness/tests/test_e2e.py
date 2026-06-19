from pathlib import Path

from fastapi.testclient import TestClient

from cleansolve_api.main import app
from cleansolve_api.routes import jobs
from cleansolve_harness.e2e import run_api_upload_to_export_e2e


FIXTURE_DIR = Path("fixtures/manual/m1-image-ingestion")


def test_api_upload_to_export_e2e_passes_with_manual_fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs.settings, "storage_root", tmp_path / "jobs")
    monkeypatch.setattr(jobs.settings, "analysis_client", "mock")
    monkeypatch.setattr(jobs.settings, "openai_api_key", None)
    client = TestClient(app)

    result = run_api_upload_to_export_e2e(
        client=client,
        problem_image_path=FIXTURE_DIR / "problem.png",
        teacher_solution_image_path=FIXTURE_DIR / "teacher_solution.png",
    )

    assert result.status == "APPROVED"
    assert result.revision_attempts >= 1
    assert result.visible_review_item_count == 0
    assert result.correction_plan_count >= 1
    assert result.candidate_spec_artifact_id.startswith("spec_")
    assert result.validation_report_artifact_id.startswith("report_")
    assert result.correction_plan_artifact_id.startswith("correction_")
    assert result.render_artifact_id.startswith("render_")
    assert result.export_artifact_id.startswith("export_")
    assert result.export_size_bytes > 0


def test_api_upload_to_export_e2e_does_not_require_openai_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CLEANSOLVE_ANALYSIS_CLIENT", raising=False)
    monkeypatch.setattr(jobs.settings, "storage_root", tmp_path / "jobs")
    monkeypatch.setattr(jobs.settings, "analysis_client", "mock")
    monkeypatch.setattr(jobs.settings, "openai_api_key", None)
    client = TestClient(app)

    result = run_api_upload_to_export_e2e(
        client=client,
        problem_image_path=FIXTURE_DIR / "problem.png",
        teacher_solution_image_path=FIXTURE_DIR / "teacher_solution.png",
    )

    assert result.status == "APPROVED"
    assert result.visible_review_item_count == 0
    assert result.export_size_bytes > 0
