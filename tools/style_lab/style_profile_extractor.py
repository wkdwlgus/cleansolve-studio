from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, UnidentifiedImageError

from tools.style_lab.manifest import write_json
from tools.style_lab.models import StyleLabInputError
from tools.style_lab.reference_set import CORE_SAMPLE_IDS
from tools.style_lab.style_profile_prompt import (
    STYLE_PROFILE_DEVELOPER_PROMPT,
    build_style_profile_user_prompt,
)
from tools.style_lab.style_profile_schema import (
    STYLE_PROFILE_SCHEMA,
    STYLE_PROFILE_SCHEMA_NAME,
    build_mock_style_profile,
    validate_style_profile,
)


_REQUIRED_ARTIFACTS = (
    "core_contact_sheet.jpg",
    "calibration_manifest.json",
    "style_tokens.skeleton.json",
)
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


@dataclass(frozen=True)
class StyleProfileExtractionInput:
    preset_id: str
    preset_version: str
    input_root: Path
    reference_image_root: Path
    output_path: Path
    model: str
    image_detail: Literal["low", "high", "auto", "original"]
    max_reference_images: int


class MockStyleProfileExtractor:
    def extract(self, input: StyleProfileExtractionInput) -> dict[str, object]:
        _, manifest, _ = _load_required_artifacts(input.input_root)
        profile = build_mock_style_profile()
        profile["reference_summary"]["visual_coverage_notes"] = _metrics_summary_notes(manifest)
        validate_style_profile(profile)
        _write_profile(profile, input.output_path)
        return profile


class OpenAIStyleProfileExtractor:
    def __init__(self, *, api_key: str, client: object | None = None, timeout_seconds: int = 90):
        if not api_key.strip():
            raise StyleLabInputError("OpenAI API key is required for style profile extraction")
        if timeout_seconds < 1:
            raise StyleLabInputError("timeout-seconds must be greater than 0")
        self._api_key = api_key
        self._client = client
        self._timeout_seconds = timeout_seconds

    def extract(self, input: StyleProfileExtractionInput) -> dict[str, object]:
        _validate_openai_input(input)
        core_contact_sheet, manifest, skeleton = _load_required_artifacts(input.input_root)
        reference_images = _selected_reference_images(input.reference_image_root, input.max_reference_images)
        user_prompt = build_style_profile_user_prompt(
            preset_id=input.preset_id,
            preset_version=input.preset_version,
            manifest=manifest,
            skeleton=skeleton,
            max_reference_images=input.max_reference_images,
        )
        api_detail = "auto" if input.image_detail == "original" else input.image_detail
        user_content = [
            {"type": "input_text", "text": user_prompt},
            {"type": "input_image", "image_url": _image_to_data_url(core_contact_sheet), "detail": api_detail},
        ]
        user_content.extend(
            {"type": "input_image", "image_url": _image_to_data_url(path), "detail": api_detail}
            for path in reference_images
        )

        client = self._get_client()
        try:
            response = client.responses.create(
                model=input.model,
                input=[
                    {
                        "role": "developer",
                        "content": [{"type": "input_text", "text": STYLE_PROFILE_DEVELOPER_PROMPT}],
                    },
                    {"role": "user", "content": user_content},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": STYLE_PROFILE_SCHEMA_NAME,
                        "schema": STYLE_PROFILE_SCHEMA,
                        "strict": True,
                    }
                },
                timeout=self._timeout_seconds,
            )
        except Exception:
            raise StyleLabInputError("OpenAI style profile request failed") from None

        output_text = _extract_output_text(response)
        if not output_text.strip():
            raise StyleLabInputError("OpenAI style profile response was empty")

        try:
            profile = json.loads(output_text)
        except json.JSONDecodeError:
            raise StyleLabInputError("OpenAI style profile response was not valid JSON") from None

        try:
            validate_style_profile(profile)
        except StyleLabInputError:
            raise StyleLabInputError("OpenAI style profile response failed schema validation") from None

        _write_profile(profile, input.output_path)
        return profile

    def _get_client(self) -> object:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise StyleLabInputError("OpenAI SDK is not installed") from exc
        return OpenAI(api_key=self._api_key)


def _load_required_artifacts(input_root: Path) -> tuple[Path, dict[str, object], dict[str, object]]:
    missing = [name for name in _REQUIRED_ARTIFACTS if not (input_root / name).is_file()]
    if missing:
        raise StyleLabInputError(f"missing style lab artifacts: {', '.join(missing)}")

    core_contact_sheet = input_root / "core_contact_sheet.jpg"
    manifest = _load_json_object(input_root / "calibration_manifest.json")
    skeleton = _load_json_object(input_root / "style_tokens.skeleton.json")
    return core_contact_sheet, manifest, skeleton


def _metrics_summary_notes(manifest: dict[str, object]) -> list[str]:
    metrics_summary = manifest.get("metrics_summary")
    if not isinstance(metrics_summary, Mapping):
        return ["metrics_summary_unavailable"]

    notes = []
    max_ink_sample_id = metrics_summary.get("max_ink_sample_id")
    if isinstance(max_ink_sample_id, str) and max_ink_sample_id:
        notes.append(f"max_ink_sample_id={max_ink_sample_id}")
    max_color_sample_id = metrics_summary.get("max_color_sample_id")
    if isinstance(max_color_sample_id, str) and max_color_sample_id:
        notes.append(f"max_color_sample_id={max_color_sample_id}")
    return notes or ["metrics_summary_unavailable"]


def _validate_openai_input(input: StyleProfileExtractionInput) -> None:
    if not input.model.strip():
        raise StyleLabInputError("OpenAI style profile model is required")
    if input.image_detail not in {"low", "high", "auto", "original"}:
        raise StyleLabInputError("image-detail must be one of low, high, auto, original")


def _image_to_data_url(path: Path) -> str:
    mime_type = _image_mime_type(path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _selected_reference_images(reference_image_root: Path, max_reference_images: int) -> list[Path]:
    if max_reference_images <= 0 or not reference_image_root.exists():
        return []

    selected: list[Path] = []
    for sample_id in CORE_SAMPLE_IDS[:max_reference_images]:
        path = _selected_image_path(reference_image_root, sample_id)
        if path is None:
            continue
        _image_mime_type(path)
        selected.append(path)
    return selected


def _extract_output_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text
    return ""


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StyleLabInputError(f"invalid style lab artifact JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise StyleLabInputError(f"invalid style lab artifact JSON: {path.name}")
    return payload


def _selected_image_path(reference_image_root: Path, sample_id: str) -> Path | None:
    for suffix in _IMAGE_SUFFIXES:
        candidate = reference_image_root / f"{sample_id}{suffix}"
        if candidate.exists():
            return candidate

    unsupported = sorted(
        path
        for path in reference_image_root.glob(f"{sample_id}.*")
        if path.is_file() and path.suffix.lower() not in _IMAGE_SUFFIXES
    )
    if unsupported:
        raise StyleLabInputError(f"unsupported style profile image type: {unsupported[0].name}")

    return None


def _image_mime_type(path: Path) -> str:
    try:
        with Image.open(path) as image:
            image.verify()
            image_format = image.format
    except (OSError, UnidentifiedImageError) as exc:
        raise StyleLabInputError(f"unsupported style profile image type: {path.name}") from exc

    if image_format == "PNG":
        return "image/png"
    if image_format == "JPEG":
        return "image/jpeg"
    raise StyleLabInputError(f"unsupported style profile image type: {path.name}")


def _write_profile(profile: dict[str, object], output_path: Path) -> None:
    try:
        write_json(profile, output_path)
    except OSError as exc:
        raise StyleLabInputError(f"failed to write output artifact {output_path}: {exc}") from exc
