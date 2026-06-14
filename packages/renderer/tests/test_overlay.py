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


def test_renderer_renders_dimension_line_with_target_anchors():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_dimension_line",
                type="dimension_line",
                color="purple",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 150, 90]),
                bbox=[10, 10, 150, 90],
                geometry={
                    "kind": "dimension_line",
                    "target_anchor_start": [20, 80],
                    "target_anchor_end": [140, 80],
                    "label": "12",
                    "label_anchor": [75, 64],
                },
            )
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'data-element-id="el_dimension_line"' in svg
    assert 'data-primitive-type="dimension_line"' in svg
    assert 'data-target-anchor-start="20,80"' in svg
    assert 'data-target-anchor-end="140,80"' in svg
    assert '<line x1="20" y1="80" x2="140" y2="80" stroke="purple"' in svg
    assert ">12<" in svg


def test_renderer_renders_dimension_curve_with_control_points():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_dimension_curve",
                type="dimension_curve",
                color="green",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 150, 120]),
                bbox=[10, 10, 150, 120],
                geometry={
                    "kind": "dimension_curve",
                    "target_anchor_start": [20, 90],
                    "target_anchor_end": [140, 90],
                    "curve_control_points": [[55, 30], [105, 30]],
                    "label": "r",
                    "label_anchor": [75, 42],
                },
            )
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'data-element-id="el_dimension_curve"' in svg
    assert 'data-primitive-type="dimension_curve"' in svg
    assert '<path d="M 20,90 C 55,30 105,30 140,90" fill="none" stroke="green"' in svg
    assert ">r<" in svg


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


def test_renderer_uses_element_color_for_label_fill_and_visible_stroke():
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
                    "visible_strokes": [
                        {"stroke_id": "s1", "points": [[25, 75], [45, 60]]},
                    ],
                    "label": "1",
                    "label_anchor": [65, 50],
                    "stroke_continuity": "continuous",
                },
            )
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert '<polyline data-stroke-id="s1" points="25,75 45,60" fill="none" stroke="blue"' in svg
    assert '<text x="65" y="50" fill="blue"' in svg


def test_renderer_escapes_svg_text_and_attribute_values():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id='el_<unsafe>&"marker"',
                type="freehand_dimension_marker",
                color="green",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 120, 100]),
                bbox=[10, 10, 120, 100],
                geometry={
                    "kind": "freehand_dimension_marker",
                    "target_anchor_start": [20, 80],
                    "target_anchor_end": [120, 40],
                    "visible_strokes": [
                        {"stroke_id": 'stroke_<unsafe>&"1"', "points": [[25, 75], [45, 60]]},
                    ],
                    "label": '5 < 7 & "quoted"',
                    "label_anchor": [65, 50],
                    "stroke_continuity": "continuous",
                },
            )
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'data-element-id="el_&lt;unsafe&gt;&amp;&quot;marker&quot;"' in svg
    assert 'data-stroke-id="stroke_&lt;unsafe&gt;&amp;&quot;1&quot;"' in svg
    assert ">5 &lt; 7 &amp; &quot;quoted&quot;<" in svg
    assert 'data-element-id="el_<unsafe>&"marker""' not in svg
    assert 'data-stroke-id="stroke_<unsafe>&"1""' not in svg
    assert '>5 < 7 & "quoted"<' not in svg
