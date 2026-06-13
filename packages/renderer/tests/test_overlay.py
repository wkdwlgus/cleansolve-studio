from xml.etree import ElementTree

from cleansolve_renderer.overlay import render_overlay_svg
from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, StylePreset


def assert_xml_parseable(svg: str):
    ElementTree.fromstring(svg)


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

    assert_xml_parseable(svg)
    assert 'data-element-id="el_marker"' in svg
    assert 'data-target-anchor-start="20,80"' in svg
    assert 'data-target-anchor-end="120,40"' in svg
    assert 'data-stroke-continuity="fragmented"' in svg
    assert "<polyline" in svg
    assert 'data-stroke-id="s1"' in svg
    assert 'points="25,75 45,60 60,55"' in svg
    assert 'data-stroke-id="s2"' in svg
    assert 'points="70,52 95,45 115,42"' in svg
    assert ">1<" in svg


def test_renderer_uses_element_label_when_geometry_label_is_missing():
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
                    "visible_strokes": [],
                    "label_anchor": [65, 50],
                    "stroke_continuity": "continuous",
                },
                label="1",
            )
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert ">1<" in svg


def test_renderer_skips_malformed_visible_strokes_without_dropping_group_or_label():
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
                        None,
                        {"stroke_id": "missing_points"},
                        {"stroke_id": "bad_points", "points": "not-points"},
                        {"stroke_id": "bad_point", "points": [[25, 75], ["x", 60]]},
                        {"stroke_id": "good", "points": [[70, 52], [95, 45]]},
                    ],
                    "label": "1",
                    "label_anchor": [65, 50],
                    "stroke_continuity": "fragmented",
                },
            )
        ],
    )

    try:
        svg = render_overlay_svg(spec)
    except Exception as exc:
        raise AssertionError("renderer should skip malformed strokes without raising") from exc

    assert_xml_parseable(svg)
    assert 'data-element-id="el_marker"' in svg
    assert ">1<" in svg
    assert 'data-stroke-id="missing_points"' not in svg
    assert 'data-stroke-id="bad_points"' not in svg
    assert 'data-stroke-id="bad_point"' not in svg
    assert 'data-stroke-id="good"' in svg
    assert 'points="70,52 95,45"' in svg


def test_renderer_uses_element_color_for_label_fill():
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
                color="blue",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 120, 100]),
                bbox=[10, 10, 120, 100],
                geometry={
                    "kind": "freehand_dimension_marker",
                    "target_anchor_start": [20, 80],
                    "target_anchor_end": [120, 40],
                    "visible_strokes": [],
                    "label": "1",
                    "label_anchor": [65, 50],
                    "stroke_continuity": "continuous",
                },
            )
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert '<text x="65" y="50" fill="blue"' in svg
