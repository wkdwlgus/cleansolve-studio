from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cleansolve_spec.models import StylePreset


class RendererStyleError(ValueError):
    pass


@dataclass(frozen=True)
class RendererStyle:
    preset_id: str
    preset_version: str
    status: str
    palette_black: str
    palette_blue: str
    palette_red_orange: str
    generic_stroke_width_px: float
    diagram_stroke_width_px: float
    formula_font_size_px: float
    text_font_size_px: float
    label_font_size_px: float
    dimension_label_font_size_px: float
    text_letter_spacing_px: float
    text_line_height_ratio: float
    label_offset_px: float
    ink_opacity: float
    highlight_stroke_width_px: float
    highlight_opacity: float


DEFAULT_RENDERER_CALIBRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json"
)

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_DEFAULT_PRESET_ID = "default_pretty_handwriting"
_DEFAULT_PRESET_VERSION = "v1"


def load_renderer_calibration(path: Path) -> dict[str, object]:
    try:
        calibration = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RendererStyleError("invalid renderer calibration JSON") from exc

    if not isinstance(calibration, dict):
        raise RendererStyleError("renderer calibration must be a JSON object")
    if calibration.get("schema_version") != "renderer_calibration.v1":
        raise RendererStyleError("invalid renderer calibration schema_version")
    if calibration.get("preset_id") != _DEFAULT_PRESET_ID:
        raise RendererStyleError("invalid renderer calibration preset_id")
    if calibration.get("preset_version") != _DEFAULT_PRESET_VERSION:
        raise RendererStyleError("invalid renderer calibration preset_version")
    if calibration.get("status") not in {"draft_needs_review", "approved"}:
        raise RendererStyleError("invalid renderer calibration status")

    tokens = _required_mapping(calibration, "tokens")
    renderer_mapping = _required_mapping(calibration, "renderer_mapping")
    palette = _required_mapping(tokens, "palette")
    stroke = _required_mapping(tokens, "stroke")
    text = _required_mapping(tokens, "text")
    diagram = _required_mapping(tokens, "diagram")

    for key in ("black", "blue", "red_orange"):
        value = palette.get(key)
        if not isinstance(value, str) or not _HEX_COLOR_RE.fullmatch(value):
            raise RendererStyleError(f"invalid renderer calibration palette.{key}")

    positive_mapping_keys = (
        "diagram_stroke_width_px",
        "dimension_label_font_size_px",
        "formula_font_size_px",
        "generic_stroke_width_px",
        "highlight_stroke_width_px",
        "label_font_size_px",
        "text_font_size_px",
    )
    for key in positive_mapping_keys:
        _required_number(renderer_mapping, key, minimum=0, include_minimum=False)
    _required_number(renderer_mapping, "highlight_opacity", minimum=0, maximum=1)

    for key in ("black_width_px", "blue_width_px", "red_width_px"):
        _required_number(stroke, key, minimum=0, include_minimum=False)
    _required_number(stroke, "opacity", minimum=0, maximum=1)
    _required_number(text, "letter_spacing_px")
    _required_number(text, "line_height_ratio", minimum=0, include_minimum=False)
    _required_number(
        _required_mapping(tokens, "formula"),
        "fraction_bar_width_px",
        minimum=0,
        include_minimum=False,
    )
    _required_number(
        diagram,
        "annotation_line_width_px",
        minimum=0,
        include_minimum=False,
    )
    _required_number(diagram, "label_offset_px", minimum=0, include_minimum=False)

    return calibration


def renderer_style_for_preset(style_preset: StylePreset) -> RendererStyle:
    if (
        style_preset.source == "system_builtin"
        and style_preset.preset_id == _DEFAULT_PRESET_ID
        and style_preset.preset_version == _DEFAULT_PRESET_VERSION
    ):
        try:
            calibration = load_renderer_calibration(DEFAULT_RENDERER_CALIBRATION_PATH)
        except (OSError, RendererStyleError):
            return _fallback_style(style_preset)
        return _style_from_calibration(calibration)

    return _fallback_style(style_preset)


def resolve_semantic_color(color: str | None, style: RendererStyle) -> str:
    if color is None or color == "" or color == "black":
        return style.palette_black
    if color == "blue":
        return style.palette_blue
    if color in {"red", "red_orange"}:
        return style.palette_red_orange
    return color


def resolve_stroke_width(
    element_style: dict[str, Any], *, default_width: float, min_value: float = 0
) -> float:
    value = element_style.get("stroke_width")
    if _is_number(value) and value > min_value:
        return float(value)
    return default_width


def resolve_font_size(element_style: dict[str, Any], *, default_size: float) -> float:
    value = element_style.get("font_size")
    if _is_number(value) and value > 0:
        return float(value)
    return default_size


def resolve_opacity(element_style: dict[str, Any], *, default_opacity: float) -> float:
    value = element_style.get("opacity")
    if _is_number(value) and 0 <= value <= 1:
        return float(value)
    return default_opacity


def _style_from_calibration(calibration: dict[str, object]) -> RendererStyle:
    tokens = _required_mapping(calibration, "tokens")
    renderer_mapping = _required_mapping(calibration, "renderer_mapping")
    palette = _required_mapping(tokens, "palette")
    stroke = _required_mapping(tokens, "stroke")
    text = _required_mapping(tokens, "text")
    diagram = _required_mapping(tokens, "diagram")

    return RendererStyle(
        preset_id=str(calibration["preset_id"]),
        preset_version=str(calibration["preset_version"]),
        status=str(calibration["status"]),
        palette_black=str(palette["black"]),
        palette_blue=str(palette["blue"]),
        palette_red_orange=str(palette["red_orange"]),
        generic_stroke_width_px=float(renderer_mapping["generic_stroke_width_px"]),
        diagram_stroke_width_px=float(renderer_mapping["diagram_stroke_width_px"]),
        formula_font_size_px=float(renderer_mapping["formula_font_size_px"]),
        text_font_size_px=float(renderer_mapping["text_font_size_px"]),
        label_font_size_px=float(renderer_mapping["label_font_size_px"]),
        dimension_label_font_size_px=float(
            renderer_mapping["dimension_label_font_size_px"]
        ),
        text_letter_spacing_px=float(text["letter_spacing_px"]),
        text_line_height_ratio=float(text["line_height_ratio"]),
        label_offset_px=float(diagram["label_offset_px"]),
        ink_opacity=float(stroke["opacity"]),
        highlight_stroke_width_px=float(renderer_mapping["highlight_stroke_width_px"]),
        highlight_opacity=float(renderer_mapping["highlight_opacity"]),
    )


def _fallback_style(style_preset: StylePreset) -> RendererStyle:
    return RendererStyle(
        preset_id=style_preset.preset_id,
        preset_version=style_preset.preset_version,
        status="fallback",
        palette_black="black",
        palette_blue="blue",
        palette_red_orange="red",
        generic_stroke_width_px=2,
        diagram_stroke_width_px=2,
        formula_font_size_px=18,
        text_font_size_px=16,
        label_font_size_px=14,
        dimension_label_font_size_px=16,
        text_letter_spacing_px=0,
        text_line_height_ratio=1,
        label_offset_px=8,
        ink_opacity=1,
        highlight_stroke_width_px=8,
        highlight_opacity=0.35,
    )


def _required_mapping(mapping: dict[str, object], key: str) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise RendererStyleError(f"invalid renderer calibration {key}")
    return value


def _required_number(
    mapping: dict[str, object],
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    include_minimum: bool = True,
) -> float:
    value = mapping.get(key)
    if not _is_number(value):
        raise RendererStyleError(f"invalid renderer calibration {key}")
    number = float(value)
    if minimum is not None:
        if include_minimum and number < minimum:
            raise RendererStyleError(f"invalid renderer calibration {key}")
        if not include_minimum and number <= minimum:
            raise RendererStyleError(f"invalid renderer calibration {key}")
    if maximum is not None and number > maximum:
        raise RendererStyleError(f"invalid renderer calibration {key}")
    return number


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
