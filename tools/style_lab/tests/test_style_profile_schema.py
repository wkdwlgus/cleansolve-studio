import pytest

from tools.style_lab.models import StyleLabInputError
from tools.style_lab.style_profile_schema import build_mock_style_profile, validate_style_profile


def test_valid_style_profile_passes_validation():
    profile = build_mock_style_profile()
    validate_style_profile(profile)


def test_palette_requires_hex_color():
    profile = build_mock_style_profile()
    profile["tokens"]["palette"]["blue"] = "blue"
    with pytest.raises(StyleLabInputError, match="style profile schema validation failed"):
        validate_style_profile(profile)


def test_required_top_level_field_is_enforced():
    profile = build_mock_style_profile()
    del profile["quality_gates"]
    with pytest.raises(StyleLabInputError, match="style profile schema validation failed"):
        validate_style_profile(profile)


def test_numeric_token_range_is_enforced():
    profile = build_mock_style_profile()
    profile["tokens"]["stroke"]["black_width_px"] = 99
    with pytest.raises(StyleLabInputError, match="style profile schema validation failed"):
        validate_style_profile(profile)


def test_needs_review_requires_uncertainty():
    profile = build_mock_style_profile()
    profile["status"] = "needs_review"
    profile["uncertainties"] = []
    with pytest.raises(StyleLabInputError, match="needs_review requires at least one uncertainty"):
        validate_style_profile(profile)


def test_only_style_description_strings_require_content():
    profile = build_mock_style_profile()
    profile["reference_summary"]["input_artifacts"] = [""]
    profile["reference_summary"]["visual_coverage_notes"] = [""]
    profile["renderer_recommendations"][0]["recommendation"] = ""
    profile["renderer_recommendations"][0]["reason"] = ""
    profile["quality_gates"]["notes"] = [""]
    profile["status"] = "needs_review"
    profile["uncertainties"] = [{"field": "", "reason": "", "needs_human_review": True}]

    validate_style_profile(profile)

    profile["style_description"]["overall"] = ""
    with pytest.raises(StyleLabInputError, match="style profile schema validation failed"):
        validate_style_profile(profile)
