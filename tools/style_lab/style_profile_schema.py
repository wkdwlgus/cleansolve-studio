from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from tools.style_lab.models import StyleLabInputError


STYLE_PROFILE_SCHEMA_NAME = "style_profile_v1"

_NON_EMPTY_STRING = {"type": "string", "minLength": 1}
_STRING = {"type": "string"}
_HEX_COLOR = {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}
_RATIO = {"type": "number", "minimum": 0.5, "maximum": 2}
_WIDTH = {"type": "number", "minimum": 0.5, "maximum": 8}
_JITTER = {"type": "number", "minimum": 0, "maximum": 12}
_UNIT_INTERVAL = {"type": "number", "minimum": 0, "maximum": 1}
_ANGLE = {"type": "number", "minimum": -20, "maximum": 20}

STYLE_PROFILE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "preset_id",
        "preset_version",
        "schema_version",
        "status",
        "source",
        "reference_summary",
        "style_description",
        "tokens",
        "renderer_recommendations",
        "quality_gates",
        "uncertainties",
    ],
    "properties": {
        "preset_id": {"const": "default_pretty_handwriting"},
        "preset_version": {"const": "v1"},
        "schema_version": {"const": "style_profile.v1"},
        "status": {"enum": ["generated", "needs_review"]},
        "source": {"const": "gpt-5.5_style_profile_extraction"},
        "reference_summary": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "core_sample_count",
                "extended_sample_count",
                "input_artifacts",
                "visual_coverage_notes",
            ],
            "properties": {
                "core_sample_count": {"type": "integer", "const": 19},
                "extended_sample_count": {"type": "integer", "const": 26},
                "input_artifacts": {"type": "array", "items": _STRING},
                "visual_coverage_notes": {"type": "array", "items": _STRING},
            },
        },
        "style_description": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "overall",
                "korean_text",
                "formula",
                "diagram_annotations",
                "color_usage",
                "spacing_and_layout",
            ],
            "properties": {
                "overall": _NON_EMPTY_STRING,
                "korean_text": _NON_EMPTY_STRING,
                "formula": _NON_EMPTY_STRING,
                "diagram_annotations": _NON_EMPTY_STRING,
                "color_usage": _NON_EMPTY_STRING,
                "spacing_and_layout": _NON_EMPTY_STRING,
            },
        },
        "tokens": {
            "type": "object",
            "additionalProperties": False,
            "required": ["stroke", "text", "formula", "diagram", "palette"],
            "properties": {
                "stroke": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "black_width_px",
                        "blue_width_px",
                        "red_width_px",
                        "jitter_px",
                        "opacity",
                    ],
                    "properties": {
                        "black_width_px": _WIDTH,
                        "blue_width_px": _WIDTH,
                        "red_width_px": _WIDTH,
                        "jitter_px": _JITTER,
                        "opacity": {"type": "number", "minimum": 0.1, "maximum": 1},
                    },
                },
                "text": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "korean_baseline_jitter_px",
                        "letter_spacing_px",
                        "line_height_ratio",
                        "size_ratio_to_formula",
                    ],
                    "properties": {
                        "korean_baseline_jitter_px": _JITTER,
                        "letter_spacing_px": {"type": "number"},
                        "line_height_ratio": _RATIO,
                        "size_ratio_to_formula": _RATIO,
                    },
                },
                "formula": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "baseline_jitter_px",
                        "fraction_bar_width_px",
                        "symbol_slant_deg",
                        "vertical_compactness",
                    ],
                    "properties": {
                        "baseline_jitter_px": _JITTER,
                        "fraction_bar_width_px": _WIDTH,
                        "symbol_slant_deg": _ANGLE,
                        "vertical_compactness": _RATIO,
                    },
                },
                "diagram": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "label_offset_px",
                        "annotation_line_width_px",
                        "hatching_gap_px",
                        "hatching_angle_jitter_deg",
                    ],
                    "properties": {
                        "label_offset_px": {"type": "number", "minimum": 0},
                        "annotation_line_width_px": _WIDTH,
                        "hatching_gap_px": {"type": "number", "minimum": 2, "maximum": 40},
                        "hatching_angle_jitter_deg": _ANGLE,
                    },
                },
                "palette": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["black", "blue", "red_orange"],
                    "properties": {
                        "black": _HEX_COLOR,
                        "blue": _HEX_COLOR,
                        "red_orange": _HEX_COLOR,
                    },
                },
            },
        },
        "renderer_recommendations": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["target", "recommendation", "reason", "priority"],
                "properties": {
                    "target": {"enum": ["stroke", "text", "formula", "diagram", "palette", "layout"]},
                    "recommendation": _STRING,
                    "reason": _STRING,
                    "priority": {"enum": ["high", "medium", "low"]},
                },
            },
        },
        "quality_gates": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "style_similarity_threshold",
                "max_visual_diff_ratio",
                "requires_human_review_if_below",
                "notes",
            ],
            "properties": {
                "style_similarity_threshold": _UNIT_INTERVAL,
                "max_visual_diff_ratio": _UNIT_INTERVAL,
                "requires_human_review_if_below": _UNIT_INTERVAL,
                "notes": {"type": "array", "items": _STRING},
            },
        },
        "uncertainties": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["field", "reason", "needs_human_review"],
                "properties": {
                    "field": _STRING,
                    "reason": _STRING,
                    "needs_human_review": {"type": "boolean"},
                },
            },
        },
    },
}

_STYLE_PROFILE_VALIDATOR = Draft202012Validator(STYLE_PROFILE_SCHEMA)


def build_mock_style_profile() -> dict[str, object]:
    return {
        "preset_id": "default_pretty_handwriting",
        "preset_version": "v1",
        "schema_version": "style_profile.v1",
        "status": "generated",
        "source": "gpt-5.5_style_profile_extraction",
        "reference_summary": {
            "core_sample_count": 19,
            "extended_sample_count": 26,
            "input_artifacts": [
                "core_contact_sheet.jpg",
                "calibration_manifest.json",
                "style_tokens.skeleton.json",
            ],
            "visual_coverage_notes": ["max_ink_sample_id=GT_132", "max_color_sample_id=GT_135"],
        },
        "style_description": {
            "overall": "균일한 검정 필기와 제한된 빨강/파랑 보조선을 사용하는 풀이 스타일",
            "korean_text": "한글 설명은 작고 촘촘하되 수식 baseline과 붙지 않는다",
            "formula": "분수선과 등호는 얇고 일정하며 기호 기울기는 작다",
            "diagram_annotations": "도형 라벨은 선과 겹치지 않게 짧은 offset을 둔다",
            "color_usage": "빨강은 강조, 파랑은 보조선과 선택 구간에 사용한다",
            "spacing_and_layout": "풀이 블록은 문제 여백을 침범하지 않고 줄 간격을 일정하게 둔다",
        },
        "tokens": {
            "stroke": {
                "black_width_px": 1.8,
                "blue_width_px": 2.2,
                "red_width_px": 2.2,
                "jitter_px": 1.5,
                "opacity": 0.96,
            },
            "text": {
                "korean_baseline_jitter_px": 1.0,
                "letter_spacing_px": 0.0,
                "line_height_ratio": 1.18,
                "size_ratio_to_formula": 0.92,
            },
            "formula": {
                "baseline_jitter_px": 1.0,
                "fraction_bar_width_px": 1.4,
                "symbol_slant_deg": -2.0,
                "vertical_compactness": 0.94,
            },
            "diagram": {
                "label_offset_px": 6.0,
                "annotation_line_width_px": 1.8,
                "hatching_gap_px": 10.0,
                "hatching_angle_jitter_deg": 3.0,
            },
            "palette": {"black": "#222222", "blue": "#3448b8", "red_orange": "#d85a3a"},
        },
        "renderer_recommendations": [
            {
                "target": "stroke",
                "recommendation": "검정 stroke를 2px 이하로 유지한다",
                "reason": "core sheet의 검정 필기가 얇다",
                "priority": "high",
            }
        ],
        "quality_gates": {
            "style_similarity_threshold": 0.78,
            "max_visual_diff_ratio": 0.22,
            "requires_human_review_if_below": 0.72,
            "notes": ["첫 버전은 사람 검수를 전제로 한다"],
        },
        "uncertainties": [],
    }


def validate_style_profile(profile: dict[str, object]) -> None:
    try:
        _STYLE_PROFILE_VALIDATOR.validate(profile)
    except ValidationError as exc:
        raise StyleLabInputError("style profile schema validation failed") from exc

    if profile["status"] == "needs_review" and profile["uncertainties"] == []:
        raise StyleLabInputError("needs_review requires at least one uncertainty")
