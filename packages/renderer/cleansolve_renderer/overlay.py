from __future__ import annotations

from html import escape
from math import isfinite
from typing import Any

from cleansolve_spec.models import CandidateSpec, Element

from cleansolve_renderer.style import (
    RendererStyle,
    renderer_style_for_preset,
    resolve_font_size,
    resolve_opacity,
    resolve_semantic_color,
    resolve_stroke_width,
)


ARROW_MARKER_ID = "cleansolve-arrowhead"


def render_overlay_svg(spec: CandidateSpec) -> str:
    renderer_style = renderer_style_for_preset(spec.style)
    rendered_elements = [
        rendered
        for element in spec.elements
        if (rendered := _render_element(element, renderer_style))
    ]
    children = []
    if any(f'marker-end="url(#{ARROW_MARKER_ID})"' in rendered for rendered in rendered_elements):
        children.append(_render_arrow_defs())
    children.extend(rendered_elements)

    body = "\n".join(children)
    if body:
        body = f"\n{body}\n"

    width = _format_number(spec.page.width)
    height = _format_number(spec.page.height)
    attrs = {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": width,
        "height": height,
        "viewBox": f"0 0 {width} {height}",
        "data-problem-image-id": spec.source_images.get("problem_image_id"),
        "data-teacher-solution-image-id": spec.source_images.get("teacher_solution_image_id"),
        "data-style-preset-id": renderer_style.preset_id,
        "data-style-preset-version": renderer_style.preset_version,
        "data-renderer-calibration-status": renderer_style.status,
    }
    return f"<svg {_render_attrs(attrs)}>{body}</svg>"


def _render_element(element: Element, renderer_style: RendererStyle) -> str:
    if element.type == "formula_line":
        return _render_text_element(
            element,
            renderer_style,
            "formula_line",
            "serif",
            renderer_style.formula_font_size_px,
        )
    if element.type == "text_note":
        return _render_text_element(
            element,
            renderer_style,
            "text_note",
            "sans-serif",
            renderer_style.text_font_size_px,
        )
    if element.type == "highlight_line":
        return _render_highlight_line(element, renderer_style)
    if element.type == "highlight_curve":
        return _render_highlight_curve(element, renderer_style)
    if element.type == "arrow":
        return _render_arrow(element, renderer_style)
    if element.type == "box":
        return _render_box(element, renderer_style)
    if element.type == "circle":
        return _render_circle(element, renderer_style)
    if element.type == "point_label":
        return _render_point_label(element, renderer_style)
    if element.type == "segment_label":
        return _render_segment_label(element, renderer_style)
    if element.type == "dimension_line":
        return _render_dimension_line(element, renderer_style)
    if element.type == "dimension_curve":
        return _render_dimension_curve(element, renderer_style)
    if element.type == "freehand_dimension_marker":
        return _render_freehand_dimension_marker(element, renderer_style)
    return ""


def _render_text_element(
    element: Element,
    renderer_style: RendererStyle,
    text_kind: str,
    font_family: str,
    default_font_size: float,
) -> str:
    geometry = element.geometry
    anchor = geometry.get("anchor")
    text = _text_value(element)
    if not _is_point(anchor) or text is None:
        return ""

    x, y = anchor
    color = resolve_semantic_color(element.color, renderer_style)
    attrs = _group_attrs(element, renderer_style)
    text_attrs = {
        "x": _format_number(x),
        "y": _format_number(y),
        "fill": color,
        "font-family": font_family,
        "font-size": _format_number(
            resolve_font_size(element.style, default_size=default_font_size)
        ),
    }
    if text_kind == "text_note" and renderer_style.text_letter_spacing_px != 0:
        text_attrs["letter-spacing"] = _format_number(
            renderer_style.text_letter_spacing_px
        )
    text_attrs["data-text-kind"] = text_kind
    child = f"    <text {_render_attrs(text_attrs)}>{_xml_escape(text)}</text>"
    return f"  <g {_render_attrs(attrs)}>\n{child}\n  </g>"


def _render_highlight_line(element: Element, renderer_style: RendererStyle) -> str:
    geometry = element.geometry
    start = geometry.get("start")
    end = geometry.get("end")
    if not _is_point(start) or not _is_point(end):
        return ""

    x1, y1 = start
    x2, y2 = end
    color = element.color or "#ffd84d"
    attrs = _group_attrs(element)
    line_attrs = {
        "x1": _format_number(x1),
        "y1": _format_number(y1),
        "x2": _format_number(x2),
        "y2": _format_number(y2),
        "stroke": color,
        "stroke-width": _format_number(
            resolve_stroke_width(
                element.style, default_width=renderer_style.highlight_stroke_width_px
            )
        ),
        "stroke-linecap": "round",
        "opacity": _format_number(
            resolve_opacity(
                element.style, default_opacity=renderer_style.highlight_opacity
            )
        ),
    }
    child = f"    <line {_render_attrs(line_attrs)} />"
    return f"  <g {_render_attrs(attrs)}>\n{child}\n  </g>"


def _render_highlight_curve(element: Element, renderer_style: RendererStyle) -> str:
    geometry = element.geometry
    start = geometry.get("start")
    end = geometry.get("end")
    control_points = _as_sequence(geometry.get("control_points"))
    if not _is_point(start) or not _is_point(end) or not control_points:
        return ""

    first_control = control_points[0]
    if not _is_point(first_control):
        return ""

    if len(control_points) >= 2 and _is_point(control_points[1]):
        command = f"C {_format_point(first_control)} {_format_point(control_points[1])} {_format_point(end)}"
    else:
        command = f"Q {_format_point(first_control)} {_format_point(end)}"

    color = element.color or "#ffd84d"
    attrs = _group_attrs(element)
    path_attrs = {
        "d": f"M {_format_point(start)} {command}",
        "fill": "none",
        "stroke": color,
        "stroke-width": _format_number(
            resolve_stroke_width(
                element.style, default_width=renderer_style.highlight_stroke_width_px
            )
        ),
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
        "opacity": _format_number(
            resolve_opacity(
                element.style, default_opacity=renderer_style.highlight_opacity
            )
        ),
    }
    child = f"    <path {_render_attrs(path_attrs)} />"
    return f"  <g {_render_attrs(attrs)}>\n{child}\n  </g>"


def _render_arrow(element: Element, renderer_style: RendererStyle) -> str:
    geometry = element.geometry
    start = geometry.get("start")
    end = geometry.get("end")
    if not _is_point(start) or not _is_point(end):
        return ""

    x1, y1 = start
    x2, y2 = end
    color = resolve_semantic_color(element.color, renderer_style)
    attrs = _group_attrs(element)
    line_attrs = {
        "x1": _format_number(x1),
        "y1": _format_number(y1),
        "x2": _format_number(x2),
        "y2": _format_number(y2),
        "stroke": color,
        "stroke-width": _format_number(
            resolve_stroke_width(
                element.style, default_width=renderer_style.generic_stroke_width_px
            )
        ),
        "stroke-linecap": "round",
        "marker-end": f"url(#{ARROW_MARKER_ID})",
    }
    child = f"    <line {_render_attrs(line_attrs)} />"
    return f"  <g {_render_attrs(attrs)}>\n{child}\n  </g>"


def _render_box(element: Element, renderer_style: RendererStyle) -> str:
    bbox = _as_bbox(element.geometry.get("bbox")) or _as_bbox(element.bbox)
    if bbox is None:
        return ""

    x, y, width, height = bbox
    color = resolve_semantic_color(element.color, renderer_style)
    attrs = _group_attrs(element)
    rect_attrs = {
        "x": _format_number(x),
        "y": _format_number(y),
        "width": _format_number(width),
        "height": _format_number(height),
        "fill": "none",
        "stroke": color,
        "stroke-width": _format_number(
            resolve_stroke_width(
                element.style, default_width=renderer_style.generic_stroke_width_px
            )
        ),
    }
    child = f"    <rect {_render_attrs(rect_attrs)} />"
    return f"  <g {_render_attrs(attrs)}>\n{child}\n  </g>"


def _render_circle(element: Element, renderer_style: RendererStyle) -> str:
    geometry = element.geometry
    center = geometry.get("center")
    radius = geometry.get("radius")
    if _is_point(center) and _is_positive_number(radius):
        cx, cy = center
        resolved_radius = radius
    else:
        bbox = _as_bbox(geometry.get("bbox")) or _as_bbox(element.bbox)
        if bbox is None:
            return ""
        x, y, width, height = bbox
        cx = x + width / 2
        cy = y + height / 2
        resolved_radius = min(width, height) / 2

    color = resolve_semantic_color(element.color, renderer_style)
    attrs = _group_attrs(element)
    circle_attrs = {
        "cx": _format_number(cx),
        "cy": _format_number(cy),
        "r": _format_number(resolved_radius),
        "fill": "none",
        "stroke": color,
        "stroke-width": _format_number(
            resolve_stroke_width(
                element.style, default_width=renderer_style.generic_stroke_width_px
            )
        ),
    }
    child = f"    <circle {_render_attrs(circle_attrs)} />"
    return f"  <g {_render_attrs(attrs)}>\n{child}\n  </g>"


def _render_point_label(element: Element, renderer_style: RendererStyle) -> str:
    geometry = element.geometry
    point = geometry.get("point")
    text = _text_value(element)
    if not _is_point(point) or text is None:
        return ""

    point_x, point_y = point
    label_anchor = geometry.get("label_anchor")
    if _is_point(label_anchor):
        label_x, label_y = label_anchor
    else:
        label_x = point_x + renderer_style.label_offset_px
        label_y = point_y - renderer_style.label_offset_px

    color = resolve_semantic_color(element.color, renderer_style)
    attrs = _group_attrs(element)
    point_attrs = {
        "cx": _format_number(point_x),
        "cy": _format_number(point_y),
        "r": "3",
        "fill": color,
    }
    label_attrs = _text_attrs(
        label_x,
        label_y,
        color,
        "sans-serif",
        resolve_font_size(element.style, default_size=renderer_style.label_font_size_px),
    )
    children = [
        f"    <circle {_render_attrs(point_attrs)} />",
        f"    <text {_render_attrs(label_attrs)}>{_xml_escape(text)}</text>",
    ]
    return f"  <g {_render_attrs(attrs)}>\n" + "\n".join(children) + "\n  </g>"


def _render_segment_label(element: Element, renderer_style: RendererStyle) -> str:
    geometry = element.geometry
    start = geometry.get("start")
    end = geometry.get("end")
    text = _text_value(element)
    if not _is_point(start) or not _is_point(end) or text is None:
        return ""

    label_anchor = geometry.get("label_anchor")
    if _is_point(label_anchor):
        label_x, label_y = label_anchor
    else:
        label_x = (start[0] + end[0]) / 2
        label_y = (start[1] + end[1]) / 2

    color = resolve_semantic_color(element.color, renderer_style)
    attrs = _group_attrs(element)
    label_attrs = _text_attrs(
        label_x,
        label_y,
        color,
        "sans-serif",
        resolve_font_size(element.style, default_size=renderer_style.label_font_size_px),
    )
    child = f"    <text {_render_attrs(label_attrs)}>{_xml_escape(text)}</text>"
    return f"  <g {_render_attrs(attrs)}>\n{child}\n  </g>"


def _render_freehand_dimension_marker(
    element: Element, renderer_style: RendererStyle
) -> str:
    geometry = element.geometry
    color = element.color or "black"
    attrs = {
        "data-element-id": element.id,
        "data-primitive-type": element.type,
        "data-target-anchor-start": _format_point(geometry.get("target_anchor_start")),
        "data-target-anchor-end": _format_point(geometry.get("target_anchor_end")),
        "data-stroke-continuity": geometry.get("stroke_continuity"),
    }

    children = [
        rendered_stroke
        for stroke in _as_sequence(geometry.get("visible_strokes", []))
        if (rendered_stroke := _render_visible_stroke(stroke, color))
    ]
    label = _render_label(element, geometry, color)
    if label:
        children.append(label)

    inner = "\n".join(child for child in children if child)
    return f"  <g {_render_attrs(attrs)}>\n{inner}\n  </g>"


def _render_arrow_defs() -> str:
    return (
        f'  <defs><marker id="{ARROW_MARKER_ID}" markerWidth="10" markerHeight="10" '
        'refX="10" refY="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" '
        'fill="black" /></marker></defs>'
    )


def _render_dimension_line(element: Element, renderer_style: RendererStyle) -> str:
    geometry = element.geometry
    start = geometry.get("visible_start") or geometry.get("target_anchor_start")
    end = geometry.get("visible_end") or geometry.get("target_anchor_end")
    if not _is_point(start) or not _is_point(end):
        return ""

    x1, y1 = start
    x2, y2 = end
    color = element.color or "black"
    attrs = _dimension_group_attrs(element, geometry)
    line_attrs = {
        "x1": _format_number(x1),
        "y1": _format_number(y1),
        "x2": _format_number(x2),
        "y2": _format_number(y2),
        "stroke": color,
        "stroke-width": "2",
        "stroke-linecap": "round",
    }
    children = [f"    <line {_render_attrs(line_attrs)} />"]
    label = _render_label(element, geometry, color)
    if label:
        children.append(label)

    return f"  <g {_render_attrs(attrs)}>\n" + "\n".join(children) + "\n  </g>"


def _render_dimension_curve(element: Element, renderer_style: RendererStyle) -> str:
    geometry = element.geometry
    start = geometry.get("visible_start") or geometry.get("target_anchor_start")
    end = geometry.get("visible_end") or geometry.get("target_anchor_end")
    control_points = _as_sequence(geometry.get("control_points") or geometry.get("curve_control_points"))
    if not _is_point(start) or not _is_point(end) or not control_points:
        return ""

    first_control = control_points[0]
    if not _is_point(first_control):
        return ""

    color = element.color or "black"
    attrs = _dimension_group_attrs(element, geometry)
    if len(control_points) >= 2 and _is_point(control_points[1]):
        command = f"C {_format_point(first_control)} {_format_point(control_points[1])} {_format_point(end)}"
    else:
        command = f"Q {_format_point(first_control)} {_format_point(end)}"

    path_attrs = {
        "d": f"M {_format_point(start)} {command}",
        "fill": "none",
        "stroke": color,
        "stroke-width": "2",
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
    }
    children = [f"    <path {_render_attrs(path_attrs)} />"]
    label = _render_label(element, geometry, color)
    if label:
        children.append(label)

    return f"  <g {_render_attrs(attrs)}>\n" + "\n".join(children) + "\n  </g>"


def _dimension_group_attrs(element: Element, geometry: dict[str, Any]) -> dict[str, Any]:
    return {
        "data-element-id": element.id,
        "data-primitive-type": element.type,
        "data-target-anchor-start": _format_point(geometry.get("target_anchor_start")),
        "data-target-anchor-end": _format_point(geometry.get("target_anchor_end")),
    }


def _group_attrs(
    element: Element, renderer_style: RendererStyle | None = None
) -> dict[str, Any]:
    attrs = {
        "data-element-id": element.id,
        "data-primitive-type": element.type,
    }
    if renderer_style is not None:
        attrs["data-style-status"] = renderer_style.status
        attrs["data-line-height-ratio"] = _format_number(
            renderer_style.text_line_height_ratio
        )
    return attrs


def _text_attrs(x: float, y: float, color: str, font_family: str, font_size: float) -> dict[str, Any]:
    return {
        "x": _format_number(x),
        "y": _format_number(y),
        "fill": color,
        "font-family": font_family,
        "font-size": _format_number(font_size),
    }


def _render_visible_stroke(stroke: Any, color: str) -> str | None:
    if not isinstance(stroke, dict):
        return None

    points = _format_points(stroke.get("points"))
    if points is None or stroke.get("stroke_id") is None:
        return None

    attrs = {
        "data-stroke-id": stroke.get("stroke_id"),
        "points": points,
        "fill": "none",
        "stroke": color,
        "stroke-width": "2",
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
    }
    return f"    <polyline {_render_attrs(attrs)} />"


def _render_label(element: Element, geometry: dict[str, Any], color: str) -> str:
    label = geometry.get("label") or element.label
    anchor = geometry.get("label_anchor")
    if label is None or not _is_point(anchor):
        return ""

    x, y = anchor
    attrs = {
        "x": _format_number(x),
        "y": _format_number(y),
        "fill": color,
        "font-family": "sans-serif",
        "font-size": "16",
    }
    return f"    <text {_render_attrs(attrs)}>{_xml_escape(str(label))}</text>"


def _text_value(element: Element) -> str | None:
    for value in (
        element.display_text,
        element.text,
        element.geometry.get("text"),
        element.geometry.get("label"),
        element.label,
    ):
        if value is None:
            continue
        text = str(value)
        return text or None
    return None


def _render_attrs(attrs: dict[str, Any]) -> str:
    return " ".join(
        f'{name}="{_xml_escape(str(value), quote=True)}"'
        for name, value in attrs.items()
        if value is not None
    )


def _xml_escape(value: str, *, quote: bool = True) -> str:
    return escape(_xml_safe_string(value), quote=quote)


def _xml_safe_string(value: str) -> str:
    return "".join(character if _is_xml_legal_character(character) else "\ufffd" for character in value)


def _is_xml_legal_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        codepoint in (0x9, 0xA, 0xD)
        or 0x20 <= codepoint <= 0xD7FF
        or 0xE000 <= codepoint <= 0xFFFD
        or 0x10000 <= codepoint <= 0x10FFFF
    )


def _format_points(points: Any) -> str | None:
    if not isinstance(points, list | tuple) or len(points) < 2:
        return None

    formatted_points = [_format_point(point) for point in points]
    if any(point is None for point in formatted_points):
        return None

    return " ".join(formatted_points)


def _as_sequence(value: Any) -> list[Any] | tuple[Any, ...]:
    if isinstance(value, list | tuple):
        return value
    return []


def _as_bbox(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, list | tuple) or len(value) != 4:
        return None

    x, y, width, height = value
    if not all(_is_number(item) for item in value):
        return None
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def _format_point(point: Any) -> str | None:
    if not _is_point(point):
        return None

    x, y = point
    return f"{_format_number(x)},{_format_number(y)}"


def _is_point(point: Any) -> bool:
    return (
        isinstance(point, list | tuple)
        and len(point) == 2
        and all(_is_number(value) for value in point)
    )


def _is_positive_number(value: Any) -> bool:
    return _is_number(value) and value > 0


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and isfinite(value)


def _style_number(
    style: dict[str, Any],
    key: str,
    default: int | float,
    *,
    min_value: int | float | None = None,
    include_min: bool = False,
    max_value: int | float | None = None,
) -> int | float:
    value = style.get(key)
    if not _is_number(value):
        return default
    if min_value is not None and (value < min_value or (value == min_value and not include_min)):
        return default
    if max_value is not None and value > max_value:
        return default
    return value


def _format_number(value: int | float) -> str:
    if value == 0:
        return "0"
    return f"{value:.15g}"
