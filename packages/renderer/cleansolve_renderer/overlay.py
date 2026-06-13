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
    if element.type != "freehand_dimension_marker":
        return ""

    geometry = element.geometry
    color = element.color or "red"
    attrs = {
        "data-element-id": element.id,
        "data-target-anchor-start": _format_point(geometry.get("target_anchor_start")),
        "data-target-anchor-end": _format_point(geometry.get("target_anchor_end")),
        "data-stroke-continuity": geometry.get("stroke_continuity"),
    }

    children = [
        _render_visible_stroke(stroke, color)
        for stroke in geometry.get("visible_strokes", [])
    ]
    label = _render_label(geometry)
    if label:
        children.append(label)

    inner = "\n".join(child for child in children if child)
    return f"  <g {_render_attrs(attrs)}>\n{inner}\n  </g>"


def _render_visible_stroke(stroke: dict[str, Any], color: str) -> str:
    attrs = {
        "data-stroke-id": stroke.get("stroke_id"),
        "points": _format_points(stroke.get("points", [])),
        "fill": "none",
        "stroke": color,
        "stroke-width": "2",
        "stroke-linecap": "round",
        "stroke-linejoin": "round",
    }
    return f"    <polyline {_render_attrs(attrs)} />"


def _render_label(geometry: dict[str, Any]) -> str:
    label = geometry.get("label")
    anchor = geometry.get("label_anchor")
    if label is None or not _is_point(anchor):
        return ""

    x, y = anchor
    attrs = {
        "x": _format_number(x),
        "y": _format_number(y),
        "fill": "red",
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


def _format_points(points: list[Any]) -> str:
    return " ".join(_format_point(point) for point in points if _is_point(point))


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
