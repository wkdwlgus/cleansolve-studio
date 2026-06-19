from pathlib import Path

from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, Region, StylePreset


class MockAnalysisClient:
    def extract_candidate_spec(
        self,
        job_id: str,
        *,
        problem_image_artifact_id: str | None = None,
        teacher_solution_image_artifact_id: str | None = None,
        problem_image_path: Path | None = None,
        teacher_solution_image_path: Path | None = None,
    ) -> CandidateSpec:
        return CandidateSpec(
            job_id=job_id,
            version=1,
            source_images={
                "problem_image_id": problem_image_artifact_id or f"{job_id}_problem",
                "teacher_solution_image_id": (
                    teacher_solution_image_artifact_id or f"{job_id}_teacher_solution"
                ),
            },
            style=StylePreset(
                source="system_builtin",
                preset_id="default_pretty_handwriting",
                preset_version="v1",
                description="Default operator-managed handwriting style preset.",
            ),
            page=Page(width=1080, height=1920),
            regions=[
                Region(
                    id="region_diagram",
                    type="diagram",
                    bbox=[120, 420, 960, 980],
                    preserve_original=True,
                ),
                Region(
                    id="region_solution",
                    type="solution_area",
                    bbox=[80, 1080, 1000, 1800],
                    preserve_original=False,
                ),
            ],
            elements=[
                Element(
                    id="el_freehand_dimension_001",
                    type="freehand_dimension_marker",
                    color="red",
                    confidence=0.82,
                    needs_review=True,
                    requires_human_review=False,
                    auto_correctable=True,
                    evidence=Evidence(source="teacher_solution_image", bbox=[160, 430, 540, 850]),
                    bbox=[160, 430, 540, 850],
                    geometry={
                        "kind": "freehand_dimension_marker",
                        "target_anchor_start": [180, 820],
                        "target_anchor_end": [520, 470],
                        "visible_strokes": [
                            {"stroke_id": "s1", "points": [[190, 805], [210, 720], [250, 650]]},
                            {"stroke_id": "s2", "points": [[305, 580], [370, 510], [500, 455]]},
                        ],
                        "label": "1",
                        "label_anchor": [280, 610],
                        "offset_side": "left",
                        "stroke_continuity": "fragmented",
                    },
                    interaction={
                        "allowed": [
                            "drag_target_anchor_start",
                            "drag_target_anchor_end",
                            "drag_visible_stroke",
                            "drag_label",
                        ]
                    },
                )
            ],
            uncertainties=[
                {
                    "id": "unc_001",
                    "element_id": "el_freehand_dimension_001",
                    "type": "dimension_endpoint_uncertain",
                    "review_ui": "drag_dimension_endpoint",
                    "user_visible_by_default": False,
                }
            ],
        )
