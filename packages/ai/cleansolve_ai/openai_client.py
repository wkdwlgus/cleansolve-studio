from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from cleansolve_ai.errors import OpenAIConfigurationError, OpenAIResponseError
from cleansolve_ai.openai_schema import CANDIDATE_SPEC_RESPONSE_SCHEMA
from cleansolve_ai.prompts import ANALYSIS_DEVELOPER_PROMPT, build_analysis_user_prompt
from cleansolve_spec.models import CandidateSpec


ALLOWED_IMAGE_DETAILS = {"low", "high", "auto", "original"}


class OpenAIAnalysisClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        image_detail: str = "auto",
        timeout_seconds: int = 60,
        client: object | None = None,
    ) -> None:
        if not api_key:
            raise OpenAIConfigurationError(
                "OPENAI_API_KEY is required for openai analysis client"
            )
        if not model:
            raise OpenAIConfigurationError(
                "OPENAI_MODEL_ANALYSIS is required for openai analysis client"
            )
        if image_detail not in ALLOWED_IMAGE_DETAILS:
            raise OpenAIConfigurationError(f"Unsupported OpenAI image detail: {image_detail}")
        if timeout_seconds < 1:
            raise OpenAIConfigurationError(
                "OPENAI_ANALYSIS_TIMEOUT_SECONDS must be at least 1"
            )

        self._model = model
        self._image_detail = _responses_image_detail(image_detail)
        self._client = (
            client
            if client is not None
            else self._build_client(api_key, timeout_seconds)
        )

    def extract_candidate_spec(
        self,
        job_id: str,
        *,
        problem_image_artifact_id: str | None = None,
        teacher_solution_image_artifact_id: str | None = None,
        problem_image_path: Path | None = None,
        teacher_solution_image_path: Path | None = None,
    ) -> CandidateSpec:
        if problem_image_artifact_id is None or teacher_solution_image_artifact_id is None:
            raise OpenAIConfigurationError("source image artifact ids are required")
        if problem_image_path is None or teacher_solution_image_path is None:
            raise OpenAIConfigurationError(
                "problem_image_path and teacher_solution_image_path are required"
            )

        user_prompt = build_analysis_user_prompt(
            job_id=job_id,
            problem_image_artifact_id=problem_image_artifact_id,
            teacher_solution_image_artifact_id=teacher_solution_image_artifact_id,
        )
        response = self._client.responses.create(
            model=self._model,
            input=[
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": ANALYSIS_DEVELOPER_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                        {
                            "type": "input_image",
                            "image_url": _image_data_url(problem_image_path),
                            "detail": self._image_detail,
                        },
                        {
                            "type": "input_image",
                            "image_url": _image_data_url(teacher_solution_image_path),
                            "detail": self._image_detail,
                        },
                    ],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "candidate_spec_m7",
                    "strict": True,
                    "schema": CANDIDATE_SPEC_RESPONSE_SCHEMA,
                }
            },
        )
        payload = _extract_output_text(response)
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise OpenAIResponseError("OpenAI response was not valid JSON") from exc

        try:
            spec = CandidateSpec.model_validate(decoded)
        except Exception as exc:
            raise OpenAIResponseError("OpenAI response did not match CandidateSpec") from exc

        _validate_response_contract(
            spec=spec,
            job_id=job_id,
            problem_image_artifact_id=problem_image_artifact_id,
            teacher_solution_image_artifact_id=teacher_solution_image_artifact_id,
        )
        return spec

    @staticmethod
    def _build_client(api_key: str, timeout_seconds: int) -> object:
        from openai import OpenAI

        return OpenAI(api_key=api_key, timeout=timeout_seconds)


def _image_data_url(path: Path) -> str:
    if not path.exists():
        raise OpenAIConfigurationError("image path does not exist")

    image_bytes = path.read_bytes()
    mime_type = _detect_mime_type(image_bytes[:8])
    if mime_type is None:
        raise OpenAIConfigurationError("unsupported image type for OpenAI analysis")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _detect_mime_type(prefix: bytes) -> str | None:
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _responses_image_detail(image_detail: str) -> str:
    if image_detail == "original":
        return "auto"
    return image_detail


def _extract_output_text(response: object) -> str:
    output_text = _object_get(response, "output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    output = _object_get(response, "output")
    if isinstance(output, list):
        for item in output:
            content = _object_get(item, "content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if _object_get(content_item, "type") == "output_text":
                    text = _object_get(content_item, "text")
                    if isinstance(text, str) and text:
                        return text

    raise OpenAIResponseError("OpenAI response did not include output text")


def _object_get(value: object, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _validate_response_contract(
    *,
    spec: CandidateSpec,
    job_id: str,
    problem_image_artifact_id: str,
    teacher_solution_image_artifact_id: str,
) -> None:
    if spec.job_id != job_id:
        raise OpenAIResponseError("job_id mismatch in OpenAI response")
    if spec.version != 1:
        raise OpenAIResponseError("CandidateSpec version must be 1")
    if spec.source_images["problem_image_id"] != problem_image_artifact_id:
        raise OpenAIResponseError("problem image artifact mismatch in OpenAI response")
    if spec.source_images["teacher_solution_image_id"] != teacher_solution_image_artifact_id:
        raise OpenAIResponseError("teacher solution image artifact mismatch in OpenAI response")
