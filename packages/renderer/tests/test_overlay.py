from cleansolve_renderer.overlay import render_overlay_svg
from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, StylePreset


def test_renderer_preserves_dimension_target_and_visible_strokes():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_marker",
                type="freehand_dimension_marker",
                color="red",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 120, 100]),
                bbox=[10, 10, 120, 100],
                geometry={
                    "kind": "freehand_dimension_marker",
                    "target_anchor_start": [20, 80],
                    "target_anchor_end": [120, 40],
                    "visible_strokes": [
                        {"stroke_id": "s1", "points": [[25, 75], [45, 60], [60, 55]]},
                        {"stroke_id": "s2", "points": [[70, 52], [95, 45], [115, 42]]}
                    ],
                    "label": "1",
                    "label_anchor": [65, 50],
                    "stroke_continuity": "fragmented"
                },
            )
        ],
    )

    svg = render_overlay_svg(spec)

    assert 'data-element-id="el_marker"' in svg
    assert 'data-target-anchor-start="20,80"' in svg
    assert 'data-target-anchor-end="120,40"' in svg
    assert 'data-stroke-continuity="fragmented"' in svg
    assert ">1<" in svg
