# M7 OpenAI Adapter Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in OpenAI Responses API analysis adapter that shares the mock adapter contract, keeps mock as the default path, and records safe failed job state when the adapter fails.

**Architecture:** `packages/ai` owns OpenAI client construction, prompt/schema payload building, response parsing, and adapter selection. `packages/workflow` receives adapter settings in state and calls the selected analysis client through the common protocol. `apps/api` passes settings and image artifact paths to the workflow, converts adapter failures to structured 502 responses, and stores a safe retryable `FAILED` manifest state.

**Tech Stack:** Python 3.13, Pydantic, FastAPI, LangGraph, OpenAI Python SDK, pytest, Vitest for unchanged web verification.

---

## File Structure

- Create: `packages/ai/cleansolve_ai/errors.py`
  - Owns adapter exception classes.
- Create: `packages/ai/cleansolve_ai/prompts.py`
  - Owns M7 analysis developer prompt and user prompt builder.
- Create: `packages/ai/cleansolve_ai/openai_schema.py`
  - Owns the explicit M7 Structured Outputs schema dict.
- Create: `packages/ai/cleansolve_ai/openai_client.py`
  - Owns OpenAI Responses API payload creation, image data URL encoding, response parsing, and `CandidateSpec` validation.
- Create: `packages/ai/cleansolve_ai/client_factory.py`
  - Owns `mock|openai` adapter selection.
- Modify: `packages/ai/cleansolve_ai/adapter.py`
  - Extends protocol signature with optional image paths.
- Modify: `packages/ai/cleansolve_ai/mock_client.py`
  - Accepts the protocol image path parameters while ignoring them.
- Modify: `packages/ai/cleansolve_ai/__init__.py`
  - Exports new adapter types and factory.
- Modify: `packages/workflow/cleansolve_workflow/graph.py`
  - Adds adapter settings and optional test override to `run_mock_workflow()`.
- Modify: `packages/workflow/cleansolve_workflow/nodes.py`
  - Uses the selected analysis client instead of direct `MockAnalysisClient()`.
- Modify: `packages/workflow/cleansolve_workflow/state.py`
  - Adds optional state keys for adapter settings, image paths, and test override.
- Modify: `apps/api/cleansolve_api/settings.py`
  - Adds analysis client settings and model defaults.
- Modify: `apps/api/cleansolve_api/artifacts.py`
  - Adds `ANALYSIS_ADAPTER_FAILED`, `analysis_adapter_failed_error()`, `save_failed_analysis_run()`, and `latest_image_artifact_paths()`.
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
  - Passes settings/image paths into workflow and handles adapter failures.
- Modify: `pyproject.toml`
  - Adds `openai` dependency.
- Modify: `apps/api/.env.example`
  - Documents new adapter env settings.
- Modify: `README.md`
  - Adds Korean OpenAI real adapter setup and smoke test instructions.
- Modify: `docs/product/mvp-roadmap.md`
  - Marks M7 Done only after implementation and verification.
- Test: `packages/ai/tests/test_openai_client.py`
- Test: `packages/ai/tests/test_client_factory.py`
- Test: `packages/ai/tests/test_openai_smoke.py`
- Test: `packages/workflow/tests/test_graph.py`
- Test: `apps/api/tests/test_jobs_api.py`

## Task 1: Adapter Protocol, Errors, Settings, and Factory

**Files:**
- Create: `packages/ai/cleansolve_ai/errors.py`
- Create: `packages/ai/cleansolve_ai/client_factory.py`
- Modify: `packages/ai/cleansolve_ai/adapter.py`
- Modify: `packages/ai/cleansolve_ai/mock_client.py`
- Modify: `packages/ai/cleansolve_ai/__init__.py`
- Modify: `apps/api/cleansolve_api/settings.py`
- Modify: `pyproject.toml`
- Test: `packages/ai/tests/test_client_factory.py`
- Test: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Write failing factory tests**

Create `packages/ai/tests/test_client_factory.py`:

```python
import pytest

from cleansolve_ai import (
    MockAnalysisClient,
    OpenAIAnalysisClient,
    OpenAIConfigurationError,
    build_analysis_client,
)


def test_build_analysis_client_returns_mock_by_default_contract():
    client = build_analysis_client(client_kind="mock")

    assert isinstance(client, MockAnalysisClient)


def test_build_analysis_client_returns_openai_when_key_is_present():
    client = build_analysis_client(
        client_kind="openai",
        openai_api_key="sk-test",
        openai_model_analysis="gpt-5.5",
    )

    assert isinstance(client, OpenAIAnalysisClient)


def test_build_analysis_client_rejects_openai_without_key():
    with pytest.raises(OpenAIConfigurationError, match="OPENAI_API_KEY is required"):
        build_analysis_client(
            client_kind="openai",
            openai_api_key=None,
            openai_model_analysis="gpt-5.5",
        )


def test_build_analysis_client_rejects_unknown_kind():
    with pytest.raises(OpenAIConfigurationError, match="Unsupported analysis client"):
        build_analysis_client(client_kind="invalid")
```

- [ ] **Step 2: Write failing settings tests**

Append to `apps/api/tests/test_jobs_api.py`:

```python
def test_settings_default_to_mock_analysis_client(monkeypatch):
    monkeypatch.delenv("CLEANSOLVE_ANALYSIS_CLIENT", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_ANALYSIS", raising=False)
    monkeypatch.delenv("OPENAI_ANALYSIS_IMAGE_DETAIL", raising=False)
    monkeypatch.delenv("OPENAI_ANALYSIS_TIMEOUT_SECONDS", raising=False)

    settings = Settings()

    assert settings.analysis_client == "mock"
    assert settings.openai_model_analysis == "gpt-5.5"
    assert settings.openai_analysis_image_detail == "auto"
    assert settings.openai_analysis_timeout_seconds == 60


def test_settings_reject_invalid_analysis_client(monkeypatch):
    monkeypatch.setenv("CLEANSOLVE_ANALYSIS_CLIENT", "invalid")

    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
python -m pytest packages/ai/tests/test_client_factory.py apps/api/tests/test_jobs_api.py::test_settings_default_to_mock_analysis_client apps/api/tests/test_jobs_api.py::test_settings_reject_invalid_analysis_client -q
```

Expected:

- `ImportError` for `OpenAIAnalysisClient`, `OpenAIConfigurationError`, or `build_analysis_client`.
- Settings tests fail because `analysis_client` fields do not exist.

- [ ] **Step 4: Add OpenAI dependency**

Modify `pyproject.toml` dependencies so the list is:

```toml
dependencies = [
  "fastapi",
  "langgraph",
  "openai",
  "pydantic",
  "pytest",
  "python-multipart",
]
```

- [ ] **Step 5: Implement errors**

Create `packages/ai/cleansolve_ai/errors.py`:

```python
class OpenAIAdapterError(RuntimeError):
    """Base error for OpenAI adapter failures."""


class OpenAIConfigurationError(OpenAIAdapterError):
    """Raised when OpenAI adapter settings are invalid."""


class OpenAIResponseError(OpenAIAdapterError):
    """Raised when OpenAI response cannot be parsed or validated."""
```

- [ ] **Step 6: Update adapter protocol and mock client signature**

Replace `packages/ai/cleansolve_ai/adapter.py` with:

```python
from pathlib import Path
from typing import Protocol

from cleansolve_spec.models import CandidateSpec


class AnalysisClient(Protocol):
    def extract_candidate_spec(
        self,
        job_id: str,
        *,
        problem_image_artifact_id: str | None = None,
        teacher_solution_image_artifact_id: str | None = None,
        problem_image_path: Path | None = None,
        teacher_solution_image_path: Path | None = None,
    ) -> CandidateSpec:
        """Return a candidate rendering spec extracted from source images."""
```

Modify `MockAnalysisClient.extract_candidate_spec()` in `packages/ai/cleansolve_ai/mock_client.py` to add the two optional path parameters:

```python
    def extract_candidate_spec(
        self,
        job_id: str,
        *,
        problem_image_artifact_id: str | None = None,
        teacher_solution_image_artifact_id: str | None = None,
        problem_image_path: Path | None = None,
        teacher_solution_image_path: Path | None = None,
    ) -> CandidateSpec:
```

Also add this import at the top of `mock_client.py`:

```python
from pathlib import Path
```

The mock implementation must not read the paths.

- [ ] **Step 7: Create temporary OpenAIAnalysisClient stub for factory**

Create `packages/ai/cleansolve_ai/openai_client.py`:

```python
from cleansolve_ai.errors import OpenAIConfigurationError

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
            raise OpenAIConfigurationError("OPENAI_API_KEY is required for openai analysis client")
        if not model:
            raise OpenAIConfigurationError("OPENAI_MODEL_ANALYSIS is required for openai analysis client")
        if image_detail not in ALLOWED_IMAGE_DETAILS:
            raise OpenAIConfigurationError(f"Unsupported OpenAI image detail: {image_detail}")
        if timeout_seconds < 1:
            raise OpenAIConfigurationError("OPENAI_ANALYSIS_TIMEOUT_SECONDS must be at least 1")

        self._api_key = api_key
        self._model = model
        self._image_detail = image_detail
        self._timeout_seconds = timeout_seconds
        self._client = client
```

This stub is expanded in Task 2.

- [ ] **Step 8: Implement factory**

Create `packages/ai/cleansolve_ai/client_factory.py`:

```python
from cleansolve_ai.adapter import AnalysisClient
from cleansolve_ai.errors import OpenAIConfigurationError
from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_ai.openai_client import OpenAIAnalysisClient


def build_analysis_client(
    *,
    client_kind: str,
    openai_api_key: str | None = None,
    openai_model_analysis: str = "gpt-5.5",
    openai_analysis_image_detail: str = "auto",
    openai_analysis_timeout_seconds: int = 60,
) -> AnalysisClient:
    if client_kind == "mock":
        return MockAnalysisClient()
    if client_kind == "openai":
        return OpenAIAnalysisClient(
            api_key=openai_api_key or "",
            model=openai_model_analysis,
            image_detail=openai_analysis_image_detail,
            timeout_seconds=openai_analysis_timeout_seconds,
        )
    raise OpenAIConfigurationError(f"Unsupported analysis client: {client_kind}")
```

- [ ] **Step 9: Export new AI package symbols**

Replace `packages/ai/cleansolve_ai/__init__.py` with:

```python
from .adapter import AnalysisClient
from .client_factory import build_analysis_client
from .errors import OpenAIAdapterError, OpenAIConfigurationError, OpenAIResponseError
from .mock_client import MockAnalysisClient
from .openai_client import OpenAIAnalysisClient

__all__ = [
    "AnalysisClient",
    "MockAnalysisClient",
    "OpenAIAnalysisClient",
    "build_analysis_client",
    "OpenAIAdapterError",
    "OpenAIConfigurationError",
    "OpenAIResponseError",
]
```

- [ ] **Step 10: Update settings**

Modify `apps/api/cleansolve_api/settings.py`:

```python
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

AnalysisClientKind = Literal["mock", "openai"]
OpenAIImageDetail = Literal["low", "high", "auto", "original"]
```

In `Settings`, set these exact fields:

```python
    openai_model_analysis: str = Field(
        default_factory=lambda: _env_value("OPENAI_MODEL_ANALYSIS", "gpt-5.5")
    )
    openai_model_validation: str = Field(
        default_factory=lambda: _env_value("OPENAI_MODEL_VALIDATION", "gpt-5.5")
    )
    openai_model_image: str = Field(
        default_factory=lambda: _env_value("OPENAI_MODEL_IMAGE", "gpt-image-1")
    )
    analysis_client: AnalysisClientKind = Field(
        default_factory=lambda: _env_value("CLEANSOLVE_ANALYSIS_CLIENT", "mock")
    )
    openai_analysis_image_detail: OpenAIImageDetail = Field(
        default_factory=lambda: _env_value("OPENAI_ANALYSIS_IMAGE_DETAIL", "auto")
    )
    openai_analysis_timeout_seconds: int = Field(
        default_factory=lambda: int(_env_value("OPENAI_ANALYSIS_TIMEOUT_SECONDS", "60"))
    )
```

- [ ] **Step 11: Run Task 1 tests to verify GREEN**

Run:

```bash
python -m pytest packages/ai/tests/test_client_factory.py apps/api/tests/test_jobs_api.py::test_settings_default_to_mock_analysis_client apps/api/tests/test_jobs_api.py::test_settings_reject_invalid_analysis_client packages/ai/tests/test_mock_client.py -q
```

Expected: all selected tests pass.

- [ ] **Step 12: Commit Task 1**

```bash
git add pyproject.toml packages/ai apps/api/cleansolve_api/settings.py apps/api/tests/test_jobs_api.py
git commit -m "feat(ai): add analysis client selection contracts"
```

## Task 2: OpenAI Responses Client, Prompt, Schema, and Parsing

**Files:**
- Create: `packages/ai/cleansolve_ai/prompts.py`
- Create: `packages/ai/cleansolve_ai/openai_schema.py`
- Modify: `packages/ai/cleansolve_ai/openai_client.py`
- Test: `packages/ai/tests/test_openai_client.py`

- [ ] **Step 1: Write failing OpenAI client tests**

Create `packages/ai/tests/test_openai_client.py`:

```python
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cleansolve_ai.errors import OpenAIConfigurationError, OpenAIResponseError
from cleansolve_ai.openai_client import OpenAIAnalysisClient
from cleansolve_spec.models import CandidateSpec


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 16


class FakeResponses:
    def __init__(self, output_text: str):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeOpenAIClient:
    def __init__(self, output_text: str):
        self.responses = FakeResponses(output_text)


def candidate_payload(job_id: str = "job_openai") -> dict[str, object]:
    return {
        "job_id": job_id,
        "version": 1,
        "source_images": {
            "problem_image_id": "img_problem_123",
            "teacher_solution_image_id": "img_teacher_456",
        },
        "style": {
            "source": "system_builtin",
            "preset_id": "default_pretty_handwriting",
            "preset_version": "v1",
            "description": "Default operator-managed handwriting style preset.",
        },
        "page": {"width": 1080, "height": 1920},
        "regions": [],
        "elements": [],
        "uncertainties": [],
    }


def write_images(tmp_path: Path) -> tuple[Path, Path]:
    problem = tmp_path / "problem.png"
    teacher = tmp_path / "teacher.jpg"
    problem.write_bytes(PNG_BYTES)
    teacher.write_bytes(JPEG_BYTES)
    return problem, teacher


def test_openai_client_rejects_empty_api_key():
    with pytest.raises(OpenAIConfigurationError, match="OPENAI_API_KEY is required"):
        OpenAIAnalysisClient(api_key="", model="gpt-5.5")


def test_openai_client_rejects_invalid_image_detail():
    with pytest.raises(OpenAIConfigurationError, match="Unsupported OpenAI image detail"):
        OpenAIAnalysisClient(api_key="sk-test", model="gpt-5.5", image_detail="full")


def test_extract_candidate_spec_rejects_missing_image_paths():
    client = OpenAIAnalysisClient(api_key="sk-test", model="gpt-5.5", client=FakeOpenAIClient("{}"))

    with pytest.raises(OpenAIConfigurationError, match="problem_image_path and teacher_solution_image_path are required"):
        client.extract_candidate_spec(
            "job_openai",
            problem_image_artifact_id="img_problem_123",
            teacher_solution_image_artifact_id="img_teacher_456",
        )


def test_extract_candidate_spec_builds_responses_payload_with_two_images(tmp_path):
    problem, teacher = write_images(tmp_path)
    fake = FakeOpenAIClient(json.dumps(candidate_payload()))
    client = OpenAIAnalysisClient(
        api_key="sk-test",
        model="gpt-5.5",
        image_detail="high",
        client=fake,
    )

    spec = client.extract_candidate_spec(
        "job_openai",
        problem_image_artifact_id="img_problem_123",
        teacher_solution_image_artifact_id="img_teacher_456",
        problem_image_path=problem,
        teacher_solution_image_path=teacher,
    )

    call = fake.responses.calls[0]
    user_content = call["input"][1]["content"]
    image_items = [item for item in user_content if item["type"] == "input_image"]
    assert isinstance(spec, CandidateSpec)
    assert call["model"] == "gpt-5.5"
    assert call["input"][0]["role"] == "developer"
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["name"] == "candidate_spec_m7"
    assert call["text"]["format"]["strict"] is True
    assert len(image_items) == 2
    assert image_items[0]["image_url"].startswith("data:image/png;base64,")
    assert image_items[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert image_items[0]["detail"] == "high"
    assert "/tmp" not in json.dumps(call)
    assert "sk-test" not in json.dumps(call)


def test_extract_candidate_spec_rejects_mismatched_job_id(tmp_path):
    problem, teacher = write_images(tmp_path)
    fake = FakeOpenAIClient(json.dumps(candidate_payload(job_id="job_other")))
    client = OpenAIAnalysisClient(api_key="sk-test", model="gpt-5.5", client=fake)

    with pytest.raises(OpenAIResponseError, match="job_id mismatch"):
        client.extract_candidate_spec(
            "job_openai",
            problem_image_artifact_id="img_problem_123",
            teacher_solution_image_artifact_id="img_teacher_456",
            problem_image_path=problem,
            teacher_solution_image_path=teacher,
        )


def test_extract_candidate_spec_rejects_mismatched_source_artifact(tmp_path):
    problem, teacher = write_images(tmp_path)
    payload = candidate_payload()
    payload["source_images"]["problem_image_id"] = "img_problem_other"
    fake = FakeOpenAIClient(json.dumps(payload))
    client = OpenAIAnalysisClient(api_key="sk-test", model="gpt-5.5", client=fake)

    with pytest.raises(OpenAIResponseError, match="problem image artifact mismatch"):
        client.extract_candidate_spec(
            "job_openai",
            problem_image_artifact_id="img_problem_123",
            teacher_solution_image_artifact_id="img_teacher_456",
            problem_image_path=problem,
            teacher_solution_image_path=teacher,
        )
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest packages/ai/tests/test_openai_client.py -q
```

Expected: failures because `extract_candidate_spec()` is not implemented and prompt/schema modules are missing.

- [ ] **Step 3: Create prompt module**

Create `packages/ai/cleansolve_ai/prompts.py`:

```python
SUPPORTED_PRIMITIVES = [
    "formula_line",
    "text_note",
    "highlight_line",
    "highlight_curve",
    "dimension_line",
    "dimension_curve",
    "freehand_dimension_marker",
    "arrow",
    "box",
    "circle",
    "angle_mark",
    "point_label",
    "segment_label",
    "graph_point",
    "graph_curve",
    "graph_tangent",
    "shaded_area",
    "choice_mark",
    "freehand_annotation",
    "unsupported_annotation",
]

ANALYSIS_DEVELOPER_PROMPT = """
You create CleanSolve Studio CandidateSpec JSON for deterministic overlay rendering.
The original problem image is the source of truth.
Use the teacher solution image only to infer handwritten solution marks, formulas, labels, highlights, arrows, and dimension markers.
Do not regenerate the whole image.
Return only JSON that matches the provided schema.
When unsure, do not guess. Set needs_review=true, requires_human_review=true, or add an uncertainty.
Use style.source=system_builtin, style.preset_id=default_pretty_handwriting, and style.preset_version=v1.
Preserve source image artifact ids exactly.
Separate target anchors from visible strokes for dimension markers.
Never include API keys, local file paths, or original filenames in the JSON.
""".strip()


def build_analysis_user_prompt(
    *,
    job_id: str,
    problem_image_artifact_id: str,
    teacher_solution_image_artifact_id: str,
) -> str:
    primitive_list = ", ".join(SUPPORTED_PRIMITIVES)
    return "\n".join(
        [
            f"job_id: {job_id}",
            f"problem_image_artifact_id: {problem_image_artifact_id}",
            f"teacher_solution_image_artifact_id: {teacher_solution_image_artifact_id}",
            f"supported_primitives: {primitive_list}",
            "review_policy: expose only requires_human_review=true items to users; needs_review is internal.",
            "Return a CandidateSpec with version=1 and matching source_images ids.",
        ]
    )
```

- [ ] **Step 4: Create schema module**

Create `packages/ai/cleansolve_ai/openai_schema.py` with a compact strict schema:

```python
PRIMITIVE_TYPES = [
    "formula_line",
    "text_note",
    "highlight_line",
    "highlight_curve",
    "dimension_line",
    "dimension_curve",
    "freehand_dimension_marker",
    "arrow",
    "box",
    "circle",
    "angle_mark",
    "point_label",
    "segment_label",
    "graph_point",
    "graph_curve",
    "graph_tangent",
    "shaded_area",
    "choice_mark",
    "freehand_annotation",
    "unsupported_annotation",
]

JSON_VALUE_SCHEMA = {
    "anyOf": [
        {"type": "string"},
        {"type": "number"},
        {"type": "integer"},
        {"type": "boolean"},
        {"type": "null"},
        {"type": "array", "items": {}},
        {"type": "object", "additionalProperties": True},
    ]
}

JSON_MAP_SCHEMA = {
    "type": "object",
    "additionalProperties": JSON_VALUE_SCHEMA,
}

CANDIDATE_SPEC_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "job_id",
        "version",
        "source_images",
        "style",
        "page",
        "regions",
        "elements",
        "uncertainties",
    ],
    "properties": {
        "job_id": {"type": "string"},
        "version": {"type": "integer", "const": 1},
        "source_images": {
            "type": "object",
            "additionalProperties": False,
            "required": ["problem_image_id", "teacher_solution_image_id"],
            "properties": {
                "problem_image_id": {"type": "string"},
                "teacher_solution_image_id": {"type": "string"},
            },
        },
        "style": {
            "type": "object",
            "additionalProperties": False,
            "required": ["source", "preset_id", "preset_version", "description"],
            "properties": {
                "source": {"type": "string", "const": "system_builtin"},
                "preset_id": {"type": "string", "const": "default_pretty_handwriting"},
                "preset_version": {"type": "string", "const": "v1"},
                "description": {"type": ["string", "null"]},
            },
        },
        "page": {
            "type": "object",
            "additionalProperties": False,
            "required": ["width", "height"],
            "properties": {
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
            },
        },
        "regions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "type", "bbox", "preserve_original"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "bbox": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number"}},
                    "preserve_original": {"type": "boolean"},
                },
            },
        },
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "type",
                    "source_region",
                    "color",
                    "confidence",
                    "needs_review",
                    "requires_human_review",
                    "auto_correctable",
                    "evidence",
                    "bbox",
                    "geometry",
                    "style",
                    "interaction",
                    "validation",
                    "revision_history",
                    "text",
                    "display_text",
                    "label",
                    "review_reason",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": PRIMITIVE_TYPES},
                    "source_region": {"type": ["string", "null"]},
                    "color": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "needs_review": {"type": "boolean"},
                    "requires_human_review": {"type": "boolean"},
                    "auto_correctable": {"type": "boolean"},
                    "evidence": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["source", "bbox"],
                        "properties": {
                            "source": {"type": "string"},
                            "bbox": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number"}},
                        },
                    },
                    "bbox": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number"}},
                    "geometry": JSON_MAP_SCHEMA,
                    "style": JSON_MAP_SCHEMA,
                    "interaction": JSON_MAP_SCHEMA,
                    "validation": JSON_MAP_SCHEMA,
                    "revision_history": {"type": "array", "items": JSON_MAP_SCHEMA},
                    "text": {"type": ["string", "null"]},
                    "display_text": {"type": ["string", "null"]},
                    "label": {"type": ["string", "null"]},
                    "review_reason": {"type": ["string", "null"]},
                },
            },
        },
        "uncertainties": {"type": "array", "items": JSON_MAP_SCHEMA},
    },
}
```

- [ ] **Step 5: Implement OpenAI client**

Replace `packages/ai/cleansolve_ai/openai_client.py` with:

```python
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
            raise OpenAIConfigurationError("OPENAI_API_KEY is required for openai analysis client")
        if not model:
            raise OpenAIConfigurationError("OPENAI_MODEL_ANALYSIS is required for openai analysis client")
        if image_detail not in ALLOWED_IMAGE_DETAILS:
            raise OpenAIConfigurationError(f"Unsupported OpenAI image detail: {image_detail}")
        if timeout_seconds < 1:
            raise OpenAIConfigurationError("OPENAI_ANALYSIS_TIMEOUT_SECONDS must be at least 1")

        self._model = model
        self._image_detail = image_detail
        self._client = client or self._build_client(api_key, timeout_seconds)

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
            raise OpenAIConfigurationError("problem_image_path and teacher_solution_image_path are required")

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
    prefix = path.read_bytes()[:8]
    mime_type = _detect_mime_type(prefix)
    if mime_type is None:
        raise OpenAIConfigurationError("unsupported image type for OpenAI analysis")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _detect_mime_type(prefix: bytes) -> str | None:
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _extract_output_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text

    output = getattr(response, "output", None)
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
```

- [ ] **Step 6: Run tests to verify GREEN**

Run:

```bash
python -m pytest packages/ai/tests/test_openai_client.py packages/ai/tests/test_client_factory.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add packages/ai
git commit -m "feat(ai): add openai responses analysis client"
```

## Task 3: Workflow Selection and API Failure Persistence

**Files:**
- Modify: `packages/workflow/cleansolve_workflow/state.py`
- Modify: `packages/workflow/cleansolve_workflow/nodes.py`
- Modify: `packages/workflow/cleansolve_workflow/graph.py`
- Modify: `apps/api/cleansolve_api/artifacts.py`
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
- Test: `packages/workflow/tests/test_graph.py`
- Test: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Write failing workflow tests**

Append to `packages/workflow/tests/test_graph.py`:

```python
from pathlib import Path

import pytest

from cleansolve_ai.errors import OpenAIResponseError


class RecordingAnalysisClient:
    def __init__(self):
        self.calls = []

    def extract_candidate_spec(self, job_id, **kwargs):
        self.calls.append({"job_id": job_id, **kwargs})
        return MockAnalysisClient().extract_candidate_spec(
            job_id,
            problem_image_artifact_id=kwargs["problem_image_artifact_id"],
            teacher_solution_image_artifact_id=kwargs["teacher_solution_image_artifact_id"],
        )


class FailingAnalysisClient:
    def extract_candidate_spec(self, job_id, **kwargs):
        raise OpenAIResponseError("model output rejected")


def test_workflow_passes_source_ids_and_paths_to_analysis_client(tmp_path):
    client = RecordingAnalysisClient()
    problem_path = tmp_path / "problem.png"
    teacher_path = tmp_path / "teacher.jpg"

    state = run_mock_workflow(
        "job_openai",
        source_image_artifact_ids={
            "problem": "img_problem_123",
            "teacher_solution": "img_teacher_456",
        },
        source_image_paths={
            "problem": str(problem_path),
            "teacher_solution": str(teacher_path),
        },
        analysis_client_override=client,
    )

    assert state["status"] == "APPROVED"
    assert client.calls == [
        {
            "job_id": "job_openai",
            "problem_image_artifact_id": "img_problem_123",
            "teacher_solution_image_artifact_id": "img_teacher_456",
            "problem_image_path": Path(problem_path),
            "teacher_solution_image_path": Path(teacher_path),
        }
    ]


def test_workflow_propagates_analysis_adapter_error():
    with pytest.raises(OpenAIResponseError, match="model output rejected"):
        run_mock_workflow(
            "job_openai",
            source_image_artifact_ids={
                "problem": "img_problem_123",
                "teacher_solution": "img_teacher_456",
            },
            analysis_client_override=FailingAnalysisClient(),
        )
```

- [ ] **Step 2: Write failing API failure tests**

Append to `apps/api/tests/test_jobs_api.py`:

```python
def test_run_with_openai_without_key_returns_502_and_marks_job_failed(monkeypatch):
    monkeypatch.setattr(jobs.settings, "analysis_client", "openai")
    monkeypatch.setattr(jobs.settings, "openai_api_key", None)
    client = TestClient(app)
    job_id = client.post("/jobs").json()["job_id"]
    upload_required_images(client, job_id)

    response = client.post(f"/jobs/{job_id}/run")
    job_response_payload = client.get(f"/jobs/{job_id}").json()
    review_items_payload = client.get(f"/jobs/{job_id}/review-items").json()

    assert response.status_code == 502
    assert_error(response, "ANALYSIS_ADAPTER_FAILED")
    assert response.json()["detail"]["fields"] == {
        "client": "openai",
        "reason": "configuration_error",
    }
    assert job_response_payload["status"] == "FAILED"
    assert job_response_payload["review_items"][-1]["type"] == "analysis_adapter_failed"
    assert job_response_payload["review_items"][-1]["retryable"] is True
    assert review_items_payload == {"items": []}
    assert "jobs" not in str(response.json())
    assert "sk-" not in str(response.json())
```

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
python -m pytest packages/workflow/tests/test_graph.py apps/api/tests/test_jobs_api.py::test_run_with_openai_without_key_returns_502_and_marks_job_failed -q
```

Expected: workflow fails on unknown `analysis_client_override`; API test fails because settings/route failure handling is not implemented.

- [ ] **Step 4: Update workflow state type**

Modify `packages/workflow/cleansolve_workflow/state.py` to include optional keys:

```python
from typing import NotRequired, TypedDict


class WorkflowState(TypedDict, total=False):
    job_id: str
    status: str
    status_history: list[str]
    validation_reports: list[object]
    correction_plans: list[dict[str, object]]
    revision_attempts: int
    max_revision_attempts: int
    review_items: list[dict[str, object]]
    inspection_issue: dict[str, object] | None
    source_image_artifact_ids: dict[str, str | None]
    source_image_paths: dict[str, str]
    analysis_client_kind: str
    openai_api_key: str | None
    openai_model_analysis: str
    openai_analysis_image_detail: str
    openai_analysis_timeout_seconds: int
    analysis_client_override: object
```

Preserve any existing keys already in the file.

- [ ] **Step 5: Update workflow graph signature**

Modify `packages/workflow/cleansolve_workflow/graph.py`:

```python
def run_mock_workflow(
    job_id: str,
    *,
    source_image_artifact_ids: dict[str, str | None] | None = None,
    source_image_paths: dict[str, str] | None = None,
    analysis_client_kind: str = "mock",
    openai_api_key: str | None = None,
    openai_model_analysis: str = "gpt-5.5",
    openai_analysis_image_detail: str = "auto",
    openai_analysis_timeout_seconds: int = 60,
    analysis_client_override=None,
    max_revision_attempts: int = 2,
    candidate_spec_override=None,
    correction_patch_override: dict[str, object] | None = None,
) -> WorkflowState:
```

Add these keys to `initial_state`:

```python
        "analysis_client_kind": analysis_client_kind,
        "openai_api_key": openai_api_key,
        "openai_model_analysis": openai_model_analysis,
        "openai_analysis_image_detail": openai_analysis_image_detail,
        "openai_analysis_timeout_seconds": openai_analysis_timeout_seconds,
```

If provided, add:

```python
    if source_image_paths is not None:
        initial_state["source_image_paths"] = source_image_paths
    if analysis_client_override is not None:
        initial_state["analysis_client_override"] = analysis_client_override
```

- [ ] **Step 6: Update workflow node client selection**

Modify `packages/workflow/cleansolve_workflow/nodes.py` imports:

```python
from pathlib import Path

from cleansolve_ai import AnalysisClient, build_analysis_client
```

Replace direct `MockAnalysisClient()` use in `analyze_sources()` with:

```python
def analyze_sources(state: WorkflowState) -> WorkflowState:
    if "candidate_spec" not in state:
        source_ids = state.get("source_image_artifact_ids") or {}
        source_paths = state.get("source_image_paths") or {}
        client = _analysis_client_from_state(state)
        state["candidate_spec"] = client.extract_candidate_spec(
            state["job_id"],
            problem_image_artifact_id=source_ids.get("problem"),
            teacher_solution_image_artifact_id=source_ids.get("teacher_solution"),
            problem_image_path=_optional_path(source_paths.get("problem")),
            teacher_solution_image_path=_optional_path(source_paths.get("teacher_solution")),
        )
    _set_status(state, "SPEC_EXTRACTED")
    return state
```

Add helpers:

```python
def _analysis_client_from_state(state: WorkflowState) -> AnalysisClient:
    override = state.get("analysis_client_override")
    if override is not None:
        return override
    return build_analysis_client(
        client_kind=state.get("analysis_client_kind", "mock"),
        openai_api_key=state.get("openai_api_key"),
        openai_model_analysis=state.get("openai_model_analysis", "gpt-5.5"),
        openai_analysis_image_detail=state.get("openai_analysis_image_detail", "auto"),
        openai_analysis_timeout_seconds=state.get("openai_analysis_timeout_seconds", 60),
    )


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value is not None else None
```

- [ ] **Step 7: Add artifact failure helpers and image paths**

Modify `apps/api/cleansolve_api/artifacts.py`.

Add error message:

```python
"ANALYSIS_ADAPTER_FAILED": "analysis adapter 실행에 실패했습니다.",
```

Add helper:

```python
def analysis_adapter_failed_error(client: str, reason: str) -> HTTPException:
    return _error(
        "ANALYSIS_ADAPTER_FAILED",
        status.HTTP_502_BAD_GATEWAY,
        {"client": client, "reason": reason},
    )
```

Add `LocalArtifactStore.latest_image_artifact_paths()`:

```python
    def latest_image_artifact_paths(self, job_id: str) -> dict[ImageRole, Path]:
        manifest = self.get_job(job_id)
        paths: dict[ImageRole, Path] = {}
        for role, artifact_id in manifest.latest_image_artifact_ids.items():
            if artifact_id is None:
                continue
            artifact = next(
                (
                    candidate
                    for candidate in manifest.image_artifacts[role]
                    if candidate.artifact_id == artifact_id
                ),
                None,
            )
            if artifact is None:
                raise job_not_found_error(job_id)
            path = (self._job_root(job_id) / artifact.relative_path).resolve()
            job_root = self._job_root(job_id).resolve()
            try:
                path.relative_to(job_root)
            except ValueError:
                raise job_not_found_error(job_id) from None
            paths[role] = path
        return paths
```

Add `LocalArtifactStore.save_failed_analysis_run()`:

```python
    def save_failed_analysis_run(
        self,
        job_id: str,
        *,
        client: str,
        reason: str,
    ) -> JobManifest:
        _validate_job_id(job_id)
        with self._job_lock(job_id):
            manifest = self.get_job(job_id)
            failed_item = {
                "type": "analysis_adapter_failed",
                "client": client,
                "retryable": True,
                "review_reason": None,
                "safe_reason": reason,
            }
            updated_manifest = JobManifest.model_validate(
                {
                    **manifest.model_dump(mode="python"),
                    "status": "FAILED",
                    "review_items": [*manifest.review_items, failed_item],
                    "updated_at": _utc_now(),
                }
            )
            self.save_manifest(updated_manifest)
            return updated_manifest
```

- [ ] **Step 8: Update API route**

Modify `apps/api/cleansolve_api/routes/jobs.py` imports:

```python
from cleansolve_ai import OpenAIAdapterError, OpenAIConfigurationError
```

Import new artifact helper:

```python
    analysis_adapter_failed_error,
```

Add helper near route helpers:

```python
def _safe_adapter_reason(exc: OpenAIAdapterError) -> str:
    if isinstance(exc, OpenAIConfigurationError):
        return "configuration_error"
    return "response_error"
```

In `run_job()`, before calling workflow:

```python
    source_image_paths = {
        role: str(path)
        for role, path in store.latest_image_artifact_paths(job_id).items()
    }
```

Wrap `run_mock_workflow()`:

```python
    try:
        state = run_mock_workflow(
            job_id=job_id,
            source_image_artifact_ids=source_image_artifact_ids,
            source_image_paths=source_image_paths,
            analysis_client_kind=settings.analysis_client,
            openai_api_key=settings.openai_api_key,
            openai_model_analysis=settings.openai_model_analysis,
            openai_analysis_image_detail=settings.openai_analysis_image_detail,
            openai_analysis_timeout_seconds=settings.openai_analysis_timeout_seconds,
        )
    except OpenAIAdapterError as exc:
        reason = _safe_adapter_reason(exc)
        store.save_failed_analysis_run(job_id, client=settings.analysis_client, reason=reason)
        raise analysis_adapter_failed_error(settings.analysis_client, reason) from exc
```

- [ ] **Step 9: Run Task 3 tests to verify GREEN**

Run:

```bash
python -m pytest packages/workflow/tests/test_graph.py apps/api/tests/test_jobs_api.py::test_run_with_openai_without_key_returns_502_and_marks_job_failed -q
```

Expected: all selected tests pass.

- [ ] **Step 10: Commit Task 3**

```bash
git add packages/workflow apps/api
git commit -m "feat(api): route analysis through selectable adapter"
```

## Task 4: Documentation, Smoke Test, and Roadmap

**Files:**
- Create: `packages/ai/tests/test_openai_smoke.py`
- Modify: `README.md`
- Modify: `apps/api/.env.example`
- Modify: `docs/product/mvp-roadmap.md`
- Test: `packages/ai/tests/test_openai_smoke.py`

- [ ] **Step 1: Write opt-in smoke test**

Create `packages/ai/tests/test_openai_smoke.py`:

```python
import os
from pathlib import Path

import pytest

from cleansolve_ai import OpenAIAnalysisClient
from cleansolve_spec.models import CandidateSpec

FIXTURE_DIR = Path("fixtures/manual/m1-image-ingestion")


@pytest.mark.skipif(
    os.getenv("RUN_OPENAI_SMOKE") != "1" or not os.getenv("OPENAI_API_KEY"),
    reason="OpenAI smoke test requires RUN_OPENAI_SMOKE=1 and OPENAI_API_KEY",
)
def test_openai_analysis_client_smoke_returns_candidate_spec():
    client = OpenAIAnalysisClient(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.getenv("OPENAI_MODEL_ANALYSIS", "gpt-5.5"),
        image_detail=os.getenv("OPENAI_ANALYSIS_IMAGE_DETAIL", "auto"),
    )

    spec = client.extract_candidate_spec(
        "job_00000000000000000000000000000000",
        problem_image_artifact_id="img_problem_smoke",
        teacher_solution_image_artifact_id="img_teacher_smoke",
        problem_image_path=FIXTURE_DIR / "problem.png",
        teacher_solution_image_path=FIXTURE_DIR / "teacher_solution.png",
    )

    assert isinstance(spec, CandidateSpec)
    assert spec.source_images == {
        "problem_image_id": "img_problem_smoke",
        "teacher_solution_image_id": "img_teacher_smoke",
    }
```

- [ ] **Step 2: Run smoke test without env to verify skip**

Run:

```bash
python -m pytest packages/ai/tests/test_openai_smoke.py -q
```

Expected: `1 skipped`.

- [ ] **Step 3: Update `.env.example`**

Replace `apps/api/.env.example` content with:

```env
CLEANSOLVE_ANALYSIS_CLIENT=mock
OPENAI_API_KEY=
OPENAI_MODEL_ANALYSIS=gpt-5.5
OPENAI_MODEL_VALIDATION=gpt-5.5
OPENAI_MODEL_IMAGE=gpt-image-1
OPENAI_ANALYSIS_IMAGE_DETAIL=auto
OPENAI_ANALYSIS_TIMEOUT_SECONDS=60
CLEANSOLVE_STORAGE_ROOT=var/jobs
```

- [ ] **Step 4: Update README in Korean**

In `README.md`, replace the current `## OpenAI API Key` section with:

```markdown
## OpenAI API Key

기본 로컬 개발은 mock analysis adapter를 사용합니다. 그래서 `OPENAI_API_KEY`가 없어도 테스트와 기본 workflow가 동작해야 합니다.

로컬 백엔드에서 실제 OpenAI adapter를 사용하려면 `apps/api/.env` 파일을 만들고 아래처럼 설정합니다.

```env
CLEANSOLVE_ANALYSIS_CLIENT=openai
OPENAI_API_KEY=sk-real-key-from-your-openai-project
OPENAI_MODEL_ANALYSIS=gpt-5.5
OPENAI_MODEL_VALIDATION=gpt-5.5
OPENAI_MODEL_IMAGE=gpt-image-1
OPENAI_ANALYSIS_IMAGE_DETAIL=auto
OPENAI_ANALYSIS_TIMEOUT_SECONDS=60
CLEANSOLVE_STORAGE_ROOT=var/jobs
```

`CLEANSOLVE_ANALYSIS_CLIENT`의 기본값은 `mock`입니다. `openai`로 바꾼 경우에만 실제 OpenAI Responses API를 호출합니다.

`.env` 파일은 커밋하지 않습니다. CI나 배포 환경에서는 환경 변수 또는 secret store를 사용합니다.

실제 OpenAI smoke test는 비용이 발생할 수 있으므로 명시적으로 opt-in해야 합니다.

```bash
RUN_OPENAI_SMOKE=1 OPENAI_API_KEY=sk-real-key-from-your-openai-project python -m pytest packages/ai/tests/test_openai_smoke.py -q
```
```

- [ ] **Step 5: Update roadmap M7**

In `docs/product/mvp-roadmap.md`:

- Change M7 status from `Not Started` to `Done`.
- Add detail link:

```markdown
상세 설계: [M7 OpenAI Adapter Integration 상세 설계](../superpowers/specs/2026-06-18-openai-adapter-integration-design.md)
```

- Add implementation result:

```markdown
구현 결과: `CLEANSOLVE_ANALYSIS_CLIENT=mock|openai` 선택형 analysis adapter, OpenAI Responses API 기반 candidate spec 생성 경로, Structured Outputs payload, safe failure persistence, opt-in smoke test가 구현됨.
```

- In current state summary, change `Real OpenAI adapter` from `Not Started` to `Done`.
- In "다음 추천 작업", change recommendation to `M8. MVP E2E Harness & Release Checklist`.

- [ ] **Step 6: Run docs and smoke verification**

Run:

```bash
python -m pytest packages/ai/tests/test_openai_smoke.py -q
rg -n "CLEANSOLVE_ANALYSIS_CLIENT|OPENAI_ANALYSIS_IMAGE_DETAIL|RUN_OPENAI_SMOKE|M7 OpenAI" README.md apps/api/.env.example docs/product/mvp-roadmap.md
git diff --check
```

Expected:

- smoke test is skipped unless real env is set.
- `rg` finds documented settings.
- `git diff --check` exits 0.

- [ ] **Step 7: Commit Task 4**

```bash
git add README.md apps/api/.env.example docs/product/mvp-roadmap.md packages/ai/tests/test_openai_smoke.py
git commit -m "docs(ai): document openai adapter opt-in flow"
```

## Task 5: Full Verification, Reviews, Push, and PR Text

**Files:**
- All changed files from Tasks 1-4.

- [ ] **Step 1: Run full verification**

Run:

```bash
python -m pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
git diff --check
```

Expected:

- `python -m pytest -q` passes. The OpenAI smoke test is skipped unless `RUN_OPENAI_SMOKE=1`.
- web tests pass.
- web build exits 0. Node/Vite version warnings are acceptable only if exit code is 0.
- `git diff --check` exits 0.

- [ ] **Step 2: Request final code review**

Use `superpowers:requesting-code-review` with this scope:

- M7 OpenAI adapter contract and settings.
- OpenAI client payload/parsing safety.
- Workflow/API failure handling and manifest state.
- Documentation and smoke test behavior.

Reviewer must verify:

- No default path requires API key.
- No test calls OpenAI network unless opt-in env is set.
- No API key/local path/raw model output is exposed in errors.
- M7 does not add image generation/editing or one-shot regeneration.

- [ ] **Step 3: Fix review findings**

For each Critical or Important finding:

1. Add a failing regression test.
2. Run it to observe failure.
3. Apply the smallest fix.
4. Run the targeted test.
5. Re-run full verification if the fix touches shared behavior.

- [ ] **Step 4: Push branch**

Run:

```bash
git status --short --branch
git push -u origin feat/openai-adapter
```

Expected:

- working tree is clean before push.
- branch pushes to `origin/feat/openai-adapter`.

- [ ] **Step 5: Prepare PR title and body**

PR title:

```text
feat: add OpenAI analysis adapter integration
```

PR body:

```markdown
## Summary
- Add selectable `mock|openai` analysis adapter configuration.
- Add OpenAI Responses API client with Structured Outputs candidate spec parsing.
- Route workflow/API run through the selected adapter while keeping mock as the default.
- Persist safe failed job state and return structured 502 errors for adapter failures.
- Document Korean setup instructions and opt-in smoke testing.

## Scope
- Candidate spec analysis adapter only.
- No image generation/editing API.
- No whole-image one-shot regeneration.
- OpenAI smoke test is opt-in and skipped by default.

## Test Plan
- [ ] `python -m pytest -q`
- [ ] `npm --prefix apps/web test`
- [ ] `npm --prefix apps/web run build`
- [ ] `git diff --check`
```

