from __future__ import annotations


def build_style_token_skeleton(
    *,
    preset_id: str,
    preset_version: str,
    core_count: int,
    extended_count: int,
) -> dict[str, object]:
    return {
        "preset_id": preset_id,
        "preset_version": preset_version,
        "schema_version": "style_tokens.v0",
        "status": "skeleton_pending_ai_calibration",
        "reference_contract": {
            "core_count": core_count,
            "extended_count": extended_count,
            "reference_set_doc": "docs/product/handwriting-style-reference-set.md",
        },
        "tokens": {
            "stroke": {
                "black_width_px": None,
                "blue_width_px": None,
                "red_width_px": None,
                "jitter_px": None,
                "opacity": None,
            },
            "text": {
                "korean_baseline_jitter_px": None,
                "letter_spacing_px": None,
                "line_height_ratio": None,
                "size_ratio_to_formula": None,
            },
            "formula": {
                "baseline_jitter_px": None,
                "fraction_bar_width_px": None,
                "symbol_slant_deg": None,
                "vertical_compactness": None,
            },
            "diagram": {
                "label_offset_px": None,
                "annotation_line_width_px": None,
                "hatching_gap_px": None,
                "hatching_angle_jitter_deg": None,
            },
            "palette": {
                "black": None,
                "blue": None,
                "red_orange": None,
            },
        },
    }
