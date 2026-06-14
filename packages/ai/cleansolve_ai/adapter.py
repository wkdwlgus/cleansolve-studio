from typing import Protocol

from cleansolve_spec.models import CandidateSpec


class AnalysisClient(Protocol):
    def extract_candidate_spec(self, job_id: str) -> CandidateSpec:
        """Return a candidate rendering spec extracted from source images."""
