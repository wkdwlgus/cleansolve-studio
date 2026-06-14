from __future__ import annotations

from html import escape
from math import isfinite
from typing import Any

from cleansolve_spec.models import CandidateSpec, Element


def render_overlay_svg(spec: CandidateSpec) -> str:
    body = "\n".join(_render_element(element) for element in spec.elements)
    if body:
        body = f"\n{body}\n"

    width = _format_number(spec.page.width)
    height = _format_number(spec.page.height)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f"{body}</svg>"
    )


def _render_element(element: Element) -> str:
    if element.type == "dimension_line":
        return _render_dimension_line(element)
    if element.type == "dimension_curve":
        return _render_dimension_curve(element)
    if element.type != "freehand_dimension_marker":
        return ""

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


def _render_dimension_line(element: Element) -> str:
    geometry = element.geometry
    start = geometry.get("target_anchor_start")
    end = geometry.get("target_anchor_end")
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


def _render_dimension_curve(element: Element) -> str:
    geometry = element.geometry
    start = geometry.get("target_anchor_start")
    end = geometry.get("target_anchor_end")
    control_points = _as_sequence(geometry.get("curve_control_points"))
    if not _is_point(start) or not _is_point(end) or len(control_points) < 2:
        return ""

    first_control, second_control = control_points[0], control_points[1]
    if not _is_point(first_control) or not _is_point(second_control):
        return ""

    color = element.color or "black"
    attrs = _dimension_group_attrs(element, geometry)
    path_attrs = {
        "d": (
            f"M {_format_point(start)} C "
            f"{_format_point(first_control)} {_format_point(second_control)} {_format_point(end)}"
        ),
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
    return f"    <text {_render_attrs(attrs)}>{escape(str(label))}</text>"


def _render_attrs(attrs: dict[str, Any]) -> str:
    return " ".join(
        f'{name}="{escape(str(value), quote=True)}"'
        for name, value in attrs.items()
        if value is not None
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


def _format_point(point: Any) -> str | None:
    if not _is_point(point):
        return None

    x, y = point
    return f"{_format_number(x)},{_format_number(y)}"


def _is_point(point: Any) -> bool:
    return (
        isinstance(point, list | tuple)
        and len(point) == 2
        and all(isinstance(value, int | float) and isfinite(value) for value in point)
    )


def _format_number(value: int | float) -> str:
    if value == 0:
        return "0"
    return f"{value:.15g}"
