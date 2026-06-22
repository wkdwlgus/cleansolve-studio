from xml.etree import ElementTree

from cleansolve_renderer.overlay import render_overlay_svg
from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, StylePreset


def assert_xml_parseable(svg: str):
    ElementTree.fromstring(svg)


def parse_svg(svg: str):
    return ElementTree.fromstring(svg)


def find_children(element, tag_name: str):
    return [child for child in element.iter() if child.tag.endswith(f"}}{tag_name}")]


def test_renderer_preserves_source_image_metadata():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "problem_v1", "teacher_solution_image_id": "solution_v1"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'data-problem-image-id="problem_v1"' in svg
    assert 'data-teacher-solution-image-id="solution_v1"' in svg
    assert 'data-style-preset-id="default_pretty_handwriting"' in svg
    assert 'data-style-preset-version="v1"' in svg
    assert 'data-renderer-calibration-status="draft_needs_review"' in svg


def test_renderer_renders_formula_line_and_text_note():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_formula",
                type="formula_line",
                color="navy",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
                bbox=[10, 10, 100, 40],
                geometry={"anchor": [30, 40]},
                style={"font_size": 20},
                display_text="x < y",
            ),
            Element(
                id="el_note",
                type="text_note",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 50, 120, 40]),
                bbox=[40, 50, 120, 40],
                geometry={"anchor": [50, 70], "text": "check & solve"},
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'data-primitive-type="formula_line"' in svg
    assert (
        '<text x="30" y="40" fill="navy" font-family="serif" '
        'font-size="20" data-text-kind="formula_line">x &lt; y</text>'
    ) in svg
    assert 'data-primitive-type="text_note"' in svg
    assert (
        '<text x="50" y="70" fill="#222222" font-family="sans-serif" '
        'font-size="16" letter-spacing="0.25" data-text-kind="text_note">check &amp; solve</text>'
    ) in svg
    assert 'data-line-height-ratio="1.32"' in svg


def test_renderer_uses_calibrated_semantic_palette_and_strokes():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_arrow",
                type="arrow",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 80, 20]),
                bbox=[10, 10, 80, 20],
                geometry={"start": [10, 20], "end": [90, 20]},
            ),
            Element(
                id="el_box",
                type="box",
                color="red",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[20, 30, 100, 50]),
                bbox=[20, 30, 100, 50],
            ),
            Element(
                id="el_circle",
                type="circle",
                color="black",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[100, 120, 40, 60]),
                bbox=[100, 120, 40, 60],
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert '<line x1="10" y1="20" x2="90" y2="20" stroke="#34309A" stroke-width="2"' in svg
    assert '<rect x="20" y="30" width="100" height="50" fill="none" stroke="#E1583E" stroke-width="2"' in svg
    assert '<circle cx="120" cy="150" r="20" fill="none" stroke="#222222" stroke-width="2"' in svg


def test_renderer_inline_style_overrides_calibration():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_arrow",
                type="arrow",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 80, 20]),
                bbox=[10, 10, 80, 20],
                geometry={"start": [10, 20], "end": [90, 20]},
                style={"stroke_width": 3.5},
            ),
            Element(
                id="el_note",
                type="text_note",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 50, 120, 40]),
                bbox=[40, 50, 120, 40],
                geometry={"anchor": [50, 70], "text": "note"},
                style={"font_size": 21},
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'stroke="#34309A" stroke-width="3.5"' in svg
    assert 'font-size="21" letter-spacing="0.25" data-text-kind="text_note">note</text>' in svg


def test_renderer_ignores_invalid_inline_style_values():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_arrow",
                type="arrow",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 80, 20]),
                bbox=[10, 10, 80, 20],
                geometry={"start": [10, 20], "end": [90, 20]},
                style={"stroke_width": True},
            ),
            Element(
                id="el_note",
                type="text_note",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 50, 120, 40]),
                bbox=[40, 50, 120, 40],
                geometry={"anchor": [50, 70], "text": "note"},
                style={"font_size": False},
            ),
            Element(
                id="el_highlight",
                type="highlight_line",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 90, 90, 20]),
                bbox=[10, 90, 90, 20],
                geometry={"start": [10, 100], "end": [100, 100]},
                style={"opacity": False},
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'stroke="#34309A" stroke-width="2"' in svg
    assert 'font-size="16" letter-spacing="0.25" data-text-kind="text_note">note</text>' in svg
    assert 'opacity="0.35"' in svg


def test_renderer_renders_highlights_and_arrow():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_highlight_line",
                type="highlight_line",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 20, 100, 10]),
                bbox=[10, 20, 100, 10],
                geometry={"start": [10, 20], "end": [110, 20]},
            ),
            Element(
                id="el_highlight_curve",
                type="highlight_curve",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[20, 40, 100, 50]),
                bbox=[20, 40, 100, 50],
                geometry={"start": [20, 80], "end": [120, 80], "control_points": [[70, 40]]},
            ),
            Element(
                id="el_arrow",
                type="arrow",
                color="purple",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[15, 15, 75, 30]),
                bbox=[15, 15, 75, 30],
                geometry={"start": [15, 15], "end": [90, 45]},
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert '<defs><marker id="cleansolve-arrowhead"' in svg
    assert (
        '<line x1="10" y1="20" x2="110" y2="20" stroke="#ffd84d" '
        'stroke-width="8" stroke-linecap="round" opacity="0.35"'
    ) in svg
    assert '<path d="M 20,80 Q 70,40 120,80" fill="none" stroke="#ffd84d"' in svg
    assert 'marker-end="url(#cleansolve-arrowhead)"' in svg
    assert '<line x1="15" y1="15" x2="90" y2="45" stroke="purple"' in svg

    root = parse_svg(svg)
    defs = find_children(root, "defs")
    markers = find_children(root, "marker")
    marker_paths = find_children(root, "path")
    arrow_lines = [
        line
        for line in find_children(root, "line")
        if line.attrib.get("marker-end") == "url(#cleansolve-arrowhead)"
    ]
    assert len(defs) == 1
    assert len(markers) == 1
    assert markers[0].attrib["id"] == "cleansolve-arrowhead"
    assert any(path.attrib.get("d") == "M 0 0 L 10 5 L 0 10 z" and path.attrib.get("fill") == "black" for path in marker_paths)
    assert len(arrow_lines) == 1


def test_renderer_renders_box_circle_point_and_segment_labels():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_box",
                type="box",
                color="red",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[20, 30, 100, 50]),
                bbox=[20, 30, 100, 50],
            ),
            Element(
                id="el_circle",
                type="circle",
                color="green",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[100, 120, 40, 60]),
                bbox=[100, 120, 40, 60],
            ),
            Element(
                id="el_point",
                type="point_label",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 20, 30, 20]),
                bbox=[10, 20, 30, 20],
                geometry={"point": [15, 25]},
                label="A",
            ),
            Element(
                id="el_segment",
                type="segment_label",
                color="black",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[30, 80, 100, 20]),
                bbox=[30, 80, 100, 20],
                geometry={"start": [30, 90], "end": [130, 90]},
                label="BC",
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert '<rect x="20" y="30" width="100" height="50" fill="none" stroke="#E1583E"' in svg
    assert '<circle cx="120" cy="150" r="20" fill="none" stroke="green"' in svg
    assert '<circle cx="15" cy="25" r="3" fill="#34309A" />' in svg
    assert '<text x="22" y="18" fill="#34309A" font-family="sans-serif" font-size="14">A</text>' in svg
    assert '<text x="80" y="90" fill="#222222" font-family="sans-serif" font-size="14">BC</text>' in svg


def test_renderer_skips_malformed_and_unsupported_primitives_without_crashing():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_bad_formula",
                type="formula_line",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
                bbox=[10, 10, 100, 40],
                text="missing anchor",
            ),
            Element(
                id="el_bad_curve",
                type="highlight_curve",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[20, 40, 100, 50]),
                bbox=[20, 40, 100, 50],
                geometry={"start": [20, 80], "end": [120, 80], "control_points": [["bad", 40]]},
            ),
            Element(
                id="el_angle",
                type="angle_mark",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[20, 40, 100, 50]),
                bbox=[20, 40, 100, 50],
            ),
        ],
    )

    try:
        svg = render_overlay_svg(spec)
    except Exception as exc:
        raise AssertionError("renderer should skip malformed primitives without raising") from exc

    assert_xml_parseable(svg)
    assert "el_bad_formula" not in svg
    assert "el_bad_curve" not in svg
    assert "el_angle" not in svg
    assert "<defs>" not in svg


def test_renderer_treats_empty_high_priority_text_as_skip():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_empty_formula",
                type="formula_line",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
                bbox=[10, 10, 100, 40],
                geometry={"anchor": [30, 40]},
                display_text="",
                text="fallback must not render",
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert "el_empty_formula" not in svg
    assert "fallback must not render" not in svg


def test_renderer_accepts_zero_opacity_highlights():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_hidden_highlight",
                type="highlight_line",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 20, 100, 10]),
                bbox=[10, 20, 100, 10],
                geometry={"start": [10, 20], "end": [110, 20]},
                style={"opacity": 0},
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'data-element-id="el_hidden_highlight"' in svg
    assert 'opacity="0"' in svg
    assert 'opacity="0.35"' not in svg


def test_renderer_sanitizes_xml_illegal_control_characters():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "problem\x00id", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el\x00formula",
                type="formula_line",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
                bbox=[10, 10, 100, 40],
                geometry={"anchor": [30, 40]},
                display_text="bad\x00text",
            ),
            Element(
                id="el_marker",
                type="freehand_dimension_marker",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 120, 100]),
                bbox=[10, 10, 120, 100],
                geometry={
                    "visible_strokes": [{"stroke_id": "stroke\x001", "points": [[25, 75], [45, 60]]}],
                    "label": "label\x00value",
                    "label_anchor": [65, 50],
                },
            ),
        ],
    )

    root = parse_svg(render_overlay_svg(spec))

    assert root.attrib["data-problem-image-id"] == "problem\ufffdid"
    assert any(group.attrib.get("data-element-id") == "el\ufffdformula" for group in find_children(root, "g"))
    assert any(text.text == "bad\ufffdtext" for text in find_children(root, "text"))
    assert any(polyline.attrib.get("data-stroke-id") == "stroke\ufffd1" for polyline in find_children(root, "polyline"))
    assert any(text.text == "label\ufffdvalue" for text in find_children(root, "text"))


def test_renderer_rejects_boolean_geometry_and_style_values():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_bool_point",
                type="highlight_line",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 20, 100, 10]),
                bbox=[10, 20, 100, 10],
                geometry={"start": [True, 20], "end": [110, 20]},
            ),
            Element(
                id="el_bool_bbox",
                type="box",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 20, 100, 10]),
                bbox=[10, 20, 100, 0],
                geometry={"bbox": [10, 20, 100, True]},
            ),
            Element(
                id="el_bool_style",
                type="highlight_line",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 40, 100, 10]),
                bbox=[10, 40, 100, 10],
                geometry={"start": [10, 40], "end": [110, 40]},
                style={"stroke_width": True, "opacity": False},
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert "el_bool_point" not in svg
    assert "el_bool_bbox" not in svg
    assert 'data-element-id="el_bool_style"' in svg
    assert 'stroke-width="8"' in svg
    assert 'opacity="0.35"' in svg
    assert 'stroke-width="1"' not in svg
    assert 'opacity="0"' not in svg


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


def test_renderer_uses_calibrated_dimension_stroke_width():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=400, height=300),
        elements=[
            Element(
                id="el_dimension_line",
                type="dimension_line",
                color="red_orange",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 50, 140, 30]),
                bbox=[40, 50, 140, 30],
                geometry={
                    "target_anchor_start": [40, 60],
                    "target_anchor_end": [180, 60],
                    "visible_start": [45, 70],
                    "visible_end": [175, 70],
                    "label_anchor": [100, 55],
                    "label": "5",
                },
            ),
            Element(
                id="el_dimension_curve",
                type="dimension_curve",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 100, 140, 60]),
                bbox=[40, 100, 140, 60],
                geometry={
                    "target_anchor_start": [40, 140],
                    "target_anchor_end": [180, 140],
                    "visible_start": [45, 145],
                    "visible_end": [175, 145],
                    "control_points": [[100, 90]],
                    "label_anchor": [102, 120],
                    "label": "arc",
                },
            ),
            Element(
                id="el_freehand",
                type="freehand_dimension_marker",
                color="black",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 180, 140, 60]),
                bbox=[40, 180, 140, 60],
                geometry={
                    "target_anchor_start": [40, 220],
                    "target_anchor_end": [180, 220],
                    "visible_strokes": [
                        {"stroke_id": "stroke_a", "points": [[45, 215], [90, 205], [175, 216]]}
                    ],
                    "label_anchor": [100, 195],
                    "label": "free",
                },
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert '<line x1="45" y1="70" x2="175" y2="70" stroke="#E1583E" stroke-width="1.9"' in svg
    assert '<path d="M 45,145 Q 100,90 175,145" fill="none" stroke="#34309A" stroke-width="1.9"' in svg
    assert '<polyline data-stroke-id="stroke_a" points="45,215 90,205 175,216" fill="none" stroke="#222222" stroke-width="1.9"' in svg
    assert '<text x="100" y="55" fill="#E1583E" font-family="sans-serif" font-size="16">5</text>' in svg
    assert '<text x="102" y="120" fill="#34309A" font-family="sans-serif" font-size="16">arc</text>' in svg
    assert '<text x="100" y="195" fill="#222222" font-family="sans-serif" font-size="16">free</text>' in svg


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


def test_renderer_renders_sot_dimension_curve_shape():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_sot_dimension_curve",
                type="dimension_curve",
                color="green",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 150, 120]),
                bbox=[10, 10, 150, 120],
                geometry={
                    "kind": "dimension_curve",
                    "target_anchor_start": [20, 90],
                    "target_anchor_end": [140, 90],
                    "visible_start": [20, 102],
                    "visible_end": [140, 102],
                    "control_points": [[80, 138]],
                    "label": "arc",
                    "label_anchor": [78, 150],
                },
            )
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'data-element-id="el_sot_dimension_curve"' in svg
    assert 'data-target-anchor-start="20,90"' in svg
    assert 'data-target-anchor-end="140,90"' in svg
    assert '<path d="M 20,102 Q 80,138 140,102" fill="none" stroke="green"' in svg
    assert ">arc<" in svg


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
    assert '<polyline data-stroke-id="s1" points="25,75 45,60" fill="none" stroke="#34309A"' in svg
    assert '<text x="65" y="50" fill="#34309A"' in svg


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
