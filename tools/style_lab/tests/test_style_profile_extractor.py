from __future__ import annotations

import builtins
import json
from pathlib import Path

import pytest
from PIL import Image

from tools.style_lab.models import StyleLabInputError
from tools.style_lab.style_profile_extractor import (
    MockStyleProfileExtractor,
    OpenAIStyleProfileExtractor,
    StyleProfileExtractionInput,
    _image_to_data_url,
)
from tools.style_lab.style_profile_schema import build_mock_style_profile, validate_style_profile


class FakeOpenAIClient:
    def __init__(self, payload: dict[str, object] | str):
        self.payload = payload
        self.last_request: dict[str, object] | None = None
        self.responses = self

    def create(self, **kwargs: object) -> object:
        self.last_request = kwargs
        output_text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload, ensure_ascii=False)
        return type("FakeOpenAIResponse", (), {"output_text": output_text})()


class FailingOpenAIClient:
    def __init__(self):
        self.responses = self

    def create(self, **kwargs: object) -> object:
        raise RuntimeError("network includes secret test-key")


def create_rgb_image(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color=(255, 255, 255)).save(path)
    return path


def make_extraction_input(
    tmp_path: Path,
    *,
    omit_core_sheet: bool = False,
    metrics_summary: dict[str, object] | None = None,
    reference_root_exists: bool = True,
    reference_ids: list[str] | None = None,
    model: str = "gpt-5.5",
    image_detail: str = "original",
) -> StyleProfileExtractionInput:
    input_root = tmp_path / "style-lab"
    input_root.mkdir()
    if not omit_core_sheet:
        create_rgb_image(input_root / "core_contact_sheet.jpg")
    if metrics_summary is None:
        metrics_summary = {"max_ink_sample_id": "GT_132", "max_color_sample_id": "GT_135"}
    (input_root / "calibration_manifest.json").write_text(
        json.dumps(
            {
                "core_sample_count": 19,
                "extended_sample_count": 26,
                "metrics_summary": metrics_summary,
            }
        ),
        encoding="utf-8",
    )
    (input_root / "style_tokens.skeleton.json").write_text(
        json.dumps(
            {
                "tokens": {
                    "stroke": {"black_width_px": None},
                    "text": {"line_height_ratio": None},
                    "formula": {"baseline_jitter_px": None},
                }
            }
        ),
        encoding="utf-8",
    )

    reference_image_root = tmp_path / "references"
    if reference_root_exists:
        reference_image_root.mkdir()
        for sample_id in reference_ids or []:
            create_rgb_image(reference_image_root / f"{sample_id}.png")

    return StyleProfileExtractionInput(
        preset_id="default_pretty_handwriting",
        preset_version="v1",
        input_root=input_root,
        reference_image_root=reference_image_root,
        output_path=tmp_path / "style_profile.generated.json",
        model=model,
        image_detail=image_detail,
        max_reference_images=4,
    )


def count_request_images(request: dict[str, object] | None) -> int:
    assert request is not None
    messages = request["input"]
    assert isinstance(messages, list)
    return sum(1 for message in messages for item in message["content"] if item["type"] == "input_image")


def test_mock_extractor_returns_deterministic_valid_profile(tmp_path):
    extraction_input = make_extraction_input(tmp_path)
    profile = MockStyleProfileExtractor().extract(extraction_input)
    validate_style_profile(profile)
    assert profile["preset_id"] == "default_pretty_handwriting"
    assert profile["reference_summary"]["visual_coverage_notes"] == [
        "max_ink_sample_id=GT_132",
        "max_color_sample_id=GT_135",
    ]


def test_mock_extractor_uses_manifest_metrics_summary_notes(tmp_path):
    extraction_input = make_extraction_input(
        tmp_path,
        metrics_summary={"max_ink_sample_id": "GT_024", "max_color_sample_id": "GT_049"},
    )

    profile = MockStyleProfileExtractor().extract(extraction_input)

    assert profile["reference_summary"]["visual_coverage_notes"] == [
        "max_ink_sample_id=GT_024",
        "max_color_sample_id=GT_049",
    ]


def test_mock_extractor_reports_missing_metrics_summary(tmp_path):
    extraction_input = make_extraction_input(tmp_path, metrics_summary={})

    profile = MockStyleProfileExtractor().extract(extraction_input)

    assert profile["reference_summary"]["visual_coverage_notes"] == ["metrics_summary_unavailable"]


def test_missing_required_artifact_raises_style_lab_error(tmp_path):
    extraction_input = make_extraction_input(tmp_path, omit_core_sheet=True)
    with pytest.raises(StyleLabInputError, match="missing style lab artifacts: core_contact_sheet.jpg"):
        MockStyleProfileExtractor().extract(extraction_input)


def test_reference_image_root_can_be_absent(tmp_path):
    extraction_input = make_extraction_input(tmp_path, reference_root_exists=False)
    client = FakeOpenAIClient(build_mock_style_profile())
    OpenAIStyleProfileExtractor(api_key="test-key", client=client, timeout_seconds=90).extract(extraction_input)
    assert count_request_images(client.last_request) == 1


def test_missing_selected_reference_image_is_skipped(tmp_path):
    extraction_input = make_extraction_input(tmp_path, reference_ids=["GT_024"])
    client = FakeOpenAIClient(build_mock_style_profile())
    OpenAIStyleProfileExtractor(api_key="test-key", client=client, timeout_seconds=90).extract(extraction_input)
    assert count_request_images(client.last_request) == 2


def test_data_url_helper_encodes_png_and_jpeg(tmp_path):
    png_path = create_rgb_image(tmp_path / "sample.png")
    jpg_path = create_rgb_image(tmp_path / "sample.jpg")
    assert _image_to_data_url(png_path).startswith("data:image/png;base64,")
    assert _image_to_data_url(jpg_path).startswith("data:image/jpeg;base64,")


def test_unsupported_reference_image_type_raises(tmp_path):
    extraction_input = make_extraction_input(tmp_path, reference_ids=["GT_024"])
    (extraction_input.reference_image_root / "GT_024.png").write_text("not an image", encoding="utf-8")
    with pytest.raises(StyleLabInputError, match="unsupported style profile image type: GT_024.png"):
        OpenAIStyleProfileExtractor(
            api_key="test-key",
            client=FakeOpenAIClient(build_mock_style_profile()),
            timeout_seconds=90,
        ).extract(extraction_input)


def test_existing_non_image_reference_file_type_raises(tmp_path):
    extraction_input = make_extraction_input(tmp_path)
    (extraction_input.reference_image_root / "GT_024.txt").write_text("not an image", encoding="utf-8")
    with pytest.raises(StyleLabInputError, match="unsupported style profile image type: GT_024.txt"):
        OpenAIStyleProfileExtractor(
            api_key="test-key",
            client=FakeOpenAIClient(build_mock_style_profile()),
            timeout_seconds=90,
        ).extract(extraction_input)


def test_openai_request_contains_messages_images_and_schema(tmp_path):
    extraction_input = make_extraction_input(tmp_path, reference_ids=["GT_024", "GT_036"])
    client = FakeOpenAIClient(build_mock_style_profile())
    OpenAIStyleProfileExtractor(api_key="test-key", client=client, timeout_seconds=90).extract(extraction_input)
    request = client.last_request
    assert request is not None
    assert request["model"] == "gpt-5.5"
    assert request["text"]["format"]["name"] == "style_profile_v1"
    assert request["text"]["format"]["strict"] is True
    assert request["input"][0]["role"] == "developer"
    assert request["input"][1]["role"] == "user"
    assert request["timeout"] == 90
    assert count_request_images(request) == 3
    assert request["input"][1]["content"][1]["detail"] == "auto"


def test_openai_extractor_rejects_empty_api_key():
    with pytest.raises(StyleLabInputError, match="OpenAI API key is required for style profile extraction"):
        OpenAIStyleProfileExtractor(api_key="", client=FakeOpenAIClient(build_mock_style_profile()), timeout_seconds=90)


def test_openai_extractor_rejects_empty_model(tmp_path):
    extraction_input = make_extraction_input(tmp_path, model="")
    with pytest.raises(StyleLabInputError, match="OpenAI style profile model is required"):
        OpenAIStyleProfileExtractor(api_key="test-key", client=FakeOpenAIClient(build_mock_style_profile()), timeout_seconds=90).extract(
            extraction_input
        )


def test_openai_extractor_rejects_invalid_image_detail(tmp_path):
    extraction_input = make_extraction_input(tmp_path, image_detail="full")
    with pytest.raises(StyleLabInputError, match="image-detail must be one of low, high, auto, original"):
        OpenAIStyleProfileExtractor(api_key="test-key", client=FakeOpenAIClient(build_mock_style_profile()), timeout_seconds=90).extract(
            extraction_input
        )


def test_openai_extractor_rejects_invalid_timeout():
    with pytest.raises(StyleLabInputError, match="timeout-seconds must be greater than 0"):
        OpenAIStyleProfileExtractor(api_key="test-key", client=FakeOpenAIClient(build_mock_style_profile()), timeout_seconds=0)


def test_invalid_json_response_is_wrapped(tmp_path):
    extraction_input = make_extraction_input(tmp_path)
    with pytest.raises(StyleLabInputError, match="OpenAI style profile response was not valid JSON"):
        OpenAIStyleProfileExtractor(api_key="test-key", client=FakeOpenAIClient("not-json"), timeout_seconds=90).extract(
            extraction_input
        )


def test_empty_response_is_wrapped(tmp_path):
    extraction_input = make_extraction_input(tmp_path)
    with pytest.raises(StyleLabInputError, match="OpenAI style profile response was empty"):
        OpenAIStyleProfileExtractor(api_key="test-key", client=FakeOpenAIClient(""), timeout_seconds=90).extract(
            extraction_input
        )


def test_schema_invalid_response_is_wrapped(tmp_path):
    extraction_input = make_extraction_input(tmp_path)
    invalid_profile = build_mock_style_profile()
    del invalid_profile["tokens"]
    with pytest.raises(StyleLabInputError, match="OpenAI style profile response failed schema validation"):
        OpenAIStyleProfileExtractor(
            api_key="test-key",
            client=FakeOpenAIClient(invalid_profile),
            timeout_seconds=90,
        ).extract(extraction_input)


def test_openai_request_failure_is_wrapped_without_secret(tmp_path):
    extraction_input = make_extraction_input(tmp_path)
    with pytest.raises(StyleLabInputError) as exc_info:
        OpenAIStyleProfileExtractor(api_key="test-key", client=FailingOpenAIClient(), timeout_seconds=90).extract(
            extraction_input
        )

    assert str(exc_info.value) == "OpenAI style profile request failed"


def test_openai_sdk_import_failure_is_wrapped(tmp_path, monkeypatch):
    extraction_input = make_extraction_input(tmp_path)
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openai":
            raise ImportError("missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(StyleLabInputError, match="OpenAI SDK is not installed"):
        OpenAIStyleProfileExtractor(api_key="test-key", client=None, timeout_seconds=90).extract(extraction_input)
