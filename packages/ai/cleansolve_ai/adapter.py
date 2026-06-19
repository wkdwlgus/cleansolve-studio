from pathlib import Path
from typing import Protocol

from cleansolve_spec.models import CandidateSpec


class AnalysisClient(Protocol):
    def extract_candidate_spec(
        self,
        job_id: str,
        *,
        problem_image_artifact_id: str | None = None,
        teacher_solution_image_artifact_id: str | None = None,
        problem_image_path: Path | None = None,
        teacher_solution_image_path: Path | None = None,
    ) -> CandidateSpec:
        """Return a candidate rendering spec extracted from source images."""
