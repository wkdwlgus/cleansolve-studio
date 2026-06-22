import json
from pathlib import Path

import pytest
from cleansolve_spec.models import StylePreset

from cleansolve_renderer import style as style_module
from cleansolve_renderer.style import (
    RendererStyle,
    RendererStyleError,
    load_renderer_calibration,
    renderer_style_for_preset,
    resolve_font_size,
    resolve_opacity,
    resolve_semantic_color,
    resolve_stroke_width,
)


CALIBRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json"
)


def default_style() -> RendererStyle:
    return RendererStyle(
        preset_id="default_pretty_handwriting",
        preset_version="v1",
        status="draft_needs_review",
        palette_black="#222222",
        palette_blue="#34309A",
        palette_red_orange="#E1583E",
        generic_stroke_width_px=2.0,
        diagram_stroke_width_px=1.9,
        formula_font_size_px=18,
        text_font_size_px=16,
        label_font_size_px=14,
        dimension_label_font_size_px=16,
        text_letter_spacing_px=0.25,
        text_line_height_ratio=1.32,
        label_offset_px=7.0,
        ink_opacity=0.94,
        highlight_stroke_width_px=8,
        highlight_opacity=0.35,
    )


def default_preset() -> StylePreset:
    return StylePreset(
        source="system_builtin",
        preset_id="default_pretty_handwriting",
        preset_version="v1",
    )


def test_load_renderer_calibration_returns_contract() -> None:
    calibration = load_renderer_calibration(CALIBRATION_PATH)

    assert calibration["schema_version"] == "renderer_calibration.v1"
    assert calibration["preset_id"] == "default_pretty_handwriting"
    assert calibration["preset_version"] == "v1"
    assert calibration["status"] == "draft_needs_review"

    tokens = calibration["tokens"]
    assert isinstance(tokens, dict)
    palette = tokens["palette"]
    assert isinstance(palette, dict)
    assert palette["blue"] == "#34309A"

    renderer_mapping = calibration["renderer_mapping"]
    assert isinstance(renderer_mapping, dict)
    assert renderer_mapping["generic_stroke_width_px"] == 2.0
    assert renderer_mapping["diagram_stroke_width_px"] == 1.9
    assert renderer_mapping["highlight_opacity"] == 0.35


def test_renderer_style_for_default_preset_uses_calibration() -> None:
    renderer_style = renderer_style_for_preset(default_preset())

    assert renderer_style.status == "draft_needs_review"
    assert renderer_style.palette_blue == "#34309A"
    assert renderer_style.palette_red_orange == "#E1583E"
    assert renderer_style.generic_stroke_width_px == 2.0
    assert renderer_style.diagram_stroke_width_px == 1.9
    assert renderer_style.text_letter_spacing_px == 0.25
    assert renderer_style.text_line_height_ratio == 1.32


def test_renderer_style_for_unknown_preset_uses_fallback() -> None:
    renderer_style = renderer_style_for_preset(
        StylePreset(source="system_builtin", preset_id="unknown", preset_version="v9")
    )

    assert renderer_style.status == "fallback"
    assert renderer_style.preset_id == "unknown"
    assert renderer_style.preset_version == "v9"
    assert renderer_style.palette_black == "black"
    assert renderer_style.generic_stroke_width_px == 2


@pytest.mark.parametrize(
    ("color", "expected"),
    [
        (None, "#222222"),
        ("", "#222222"),
        ("black", "#222222"),
        ("blue", "#34309A"),
        ("red", "#E1583E"),
        ("red_orange", "#E1583E"),
        ("purple", "purple"),
    ],
)
def test_resolve_semantic_color_maps_only_known_semantics(
    color: str | None, expected: str
) -> None:
    assert resolve_semantic_color(color, default_style()) == expected


def test_numeric_resolvers_accept_valid_values() -> None:
    assert resolve_stroke_width({"stroke_width": 3.5}, default_width=2) == 3.5
    assert resolve_font_size({"font_size": 21}, default_size=16) == 21
    assert resolve_opacity({"opacity": 0.45}, default_opacity=1) == 0.45
    assert resolve_opacity({"opacity": 0}, default_opacity=1) == 0
    assert resolve_opacity({"opacity": 1}, default_opacity=0.5) == 1


@pytest.mark.parametrize(
    ("resolver", "element_style", "kwargs", "expected"),
    [
        (resolve_stroke_width, {"stroke_width": True}, {"default_width": 2}, 2),
        (resolve_stroke_width, {"stroke_width": 0}, {"default_width": 2}, 2),
        (resolve_stroke_width, {"stroke_width": -1}, {"default_width": 2}, 2),
        (resolve_font_size, {"font_size": False}, {"default_size": 16}, 16),
        (resolve_font_size, {"font_size": 0}, {"default_size": 16}, 16),
        (resolve_font_size, {"font_size": -1}, {"default_size": 16}, 16),
        (resolve_opacity, {"opacity": True}, {"default_opacity": 0.5}, 0.5),
        (resolve_opacity, {"opacity": -0.1}, {"default_opacity": 0.5}, 0.5),
        (resolve_opacity, {"opacity": 1.1}, {"default_opacity": 0.5}, 0.5),
    ],
)
def test_numeric_resolvers_reject_invalid_values(
    resolver: object, element_style: dict[str, object], kwargs: dict[str, float], expected: float
) -> None:
    assert resolver(element_style, **kwargs) == expected


def test_invalid_calibration_schema_version_raises_style_error(tmp_path: Path) -> None:
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    calibration["schema_version"] = "wrong"
    invalid_path = tmp_path / "renderer_calibration.v1.json"
    invalid_path.write_text(json.dumps(calibration), encoding="utf-8")

    with pytest.raises(
        RendererStyleError, match="invalid renderer calibration schema_version"
    ):
        load_renderer_calibration(invalid_path)


def test_renderer_style_for_default_preset_falls_back_for_broken_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken_path = tmp_path / "broken.json"
    broken_path.write_text("{", encoding="utf-8")
    monkeypatch.setattr(style_module, "DEFAULT_RENDERER_CALIBRATION_PATH", broken_path)

    renderer_style = renderer_style_for_preset(default_preset())

    assert renderer_style.status == "fallback"
    assert renderer_style.preset_id == "default_pretty_handwriting"
    assert renderer_style.preset_version == "v1"
