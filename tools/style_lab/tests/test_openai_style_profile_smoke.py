from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools.style_lab.style_profile_extractor import (
    OpenAIStyleProfileExtractor,
    StyleProfileExtractionInput,
)
from tools.style_lab.style_profile_schema import validate_style_profile


def test_openai_style_profile_smoke_generates_valid_profile():
    if os.environ.get("CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE") != "1":
        pytest.skip("set CLEANSOLVE_RUN_OPENAI_STYLE_SMOKE=1 to run OpenAI style smoke")
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required")

    input_root = Path("image/style-lab/default_pretty_handwriting/v1")
    required = ["core_contact_sheet.jpg", "calibration_manifest.json", "style_tokens.skeleton.json"]
    missing = [name for name in required if not (input_root / name).exists()]
    if missing:
        pytest.skip(f"missing local style lab artifacts: {', '.join(missing)}")

    output_path = input_root / "style_profile.generated.json"
    extraction_input = StyleProfileExtractionInput(
        preset_id="default_pretty_handwriting",
        preset_version="v1",
        input_root=input_root,
        reference_image_root=Path("image/clean_solutions"),
        output_path=output_path,
        model=os.environ.get("OPENAI_MODEL_ANALYSIS", "gpt-5.5"),
        image_detail=os.environ.get("OPENAI_STYLE_PROFILE_IMAGE_DETAIL", "auto"),
        max_reference_images=0,
    )
    extractor = OpenAIStyleProfileExtractor(
        api_key=os.environ["OPENAI_API_KEY"],
        client=None,
        timeout_seconds=int(os.environ.get("OPENAI_STYLE_PROFILE_TIMEOUT_SECONDS", "90")),
    )

    profile = extractor.extract(extraction_input)

    validate_style_profile(profile)
    assert output_path.exists()
    assert profile["preset_id"] == "default_pretty_handwriting"
    assert profile["preset_version"] == "v1"
