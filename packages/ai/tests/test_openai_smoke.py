import os
from pathlib import Path

import pytest

from cleansolve_ai import OpenAIAnalysisClient
from cleansolve_spec.models import CandidateSpec

FIXTURE_DIR = Path("fixtures/manual/m1-image-ingestion")


@pytest.mark.skipif(
    os.getenv("RUN_OPENAI_SMOKE") != "1" or not os.getenv("OPENAI_API_KEY"),
    reason="OpenAI smoke test requires RUN_OPENAI_SMOKE=1 and OPENAI_API_KEY",
)
def test_openai_analysis_client_smoke_returns_candidate_spec():
    client = OpenAIAnalysisClient(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.getenv("OPENAI_MODEL_ANALYSIS", "gpt-5.5"),
        image_detail=os.getenv("OPENAI_ANALYSIS_IMAGE_DETAIL", "auto"),
    )

    spec = client.extract_candidate_spec(
        "job_00000000000000000000000000000000",
        problem_image_artifact_id="img_problem_smoke",
        teacher_solution_image_artifact_id="img_teacher_smoke",
        problem_image_path=FIXTURE_DIR / "problem.png",
        teacher_solution_image_path=FIXTURE_DIR / "teacher_solution.png",
    )

    assert isinstance(spec, CandidateSpec)
    assert spec.source_images == {
        "problem_image_id": "img_problem_smoke",
        "teacher_solution_image_id": "img_teacher_smoke",
    }
