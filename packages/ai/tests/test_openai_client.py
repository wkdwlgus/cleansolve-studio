import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cleansolve_ai.errors import OpenAIConfigurationError, OpenAIResponseError
from cleansolve_ai.openai_client import OpenAIAnalysisClient
from cleansolve_ai.openai_schema import CANDIDATE_SPEC_RESPONSE_SCHEMA
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


class FakeResponsesWithResponse:
    def __init__(self, response: object):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeOpenAIClientWithResponse:
    def __init__(self, response: object):
        self.responses = FakeResponsesWithResponse(response)


class FalsyFakeOpenAIClient(FakeOpenAIClient):
    def __bool__(self):
        return False


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


def candidate_payload_with_dimension_marker(job_id: str = "job_openai") -> dict[str, object]:
    payload = candidate_payload(job_id)
    payload["elements"] = [
        {
            "id": "el_freehand_dimension_001",
            "type": "freehand_dimension_marker",
            "source_region": None,
            "color": "#1f4bd8",
            "confidence": 0.92,
            "needs_review": False,
            "requires_human_review": False,
            "auto_correctable": True,
            "evidence": {"source": "teacher_solution", "bbox": [20, 40, 140, 120]},
            "bbox": [20, 40, 140, 120],
            "geometry": {
                "target_anchor_start": [20, 80],
                "target_anchor_end": [120, 40],
                "visible_strokes": [
                    {
                        "stroke_id": "stroke_001",
                        "points": [[25, 75], [45, 60], [120, 40]],
                    }
                ],
                "label_anchor": [65, 50],
            },
            "style": {"stroke_width": 2.0, "opacity": 0.95},
            "interaction": {"locked": False},
            "validation": {"status": "candidate"},
            "revision_history": [
                {
                    "revision_id": "rev_initial",
                    "source": "openai_analysis",
                    "patch": {"geometry.target_anchor_end": [120, 40]},
                }
            ],
            "text": None,
            "display_text": None,
            "label": "1",
            "review_reason": None,
        }
    ]
    payload["uncertainties"] = [
        {
            "id": "unc_001",
            "message": "Low contrast near the final stroke.",
            "bbox": [20, 40, 140, 120],
        }
    ]
    return payload


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
    client = OpenAIAnalysisClient(
        api_key="sk-test",
        model="gpt-5.5",
        client=FakeOpenAIClient("{}"),
    )

    with pytest.raises(
        OpenAIConfigurationError,
        match="problem_image_path and teacher_solution_image_path are required",
    ):
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
    serialized_call = json.dumps(call)
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
    assert "sk-test" not in serialized_call
    assert str(problem) not in serialized_call
    assert str(teacher) not in serialized_call


def test_openai_client_maps_original_detail_to_auto_for_responses_payload(tmp_path):
    problem, teacher = write_images(tmp_path)
    fake = FakeOpenAIClient(json.dumps(candidate_payload()))
    client = OpenAIAnalysisClient(
        api_key="sk-test",
        model="gpt-5.5",
        image_detail="original",
        client=fake,
    )

    client.extract_candidate_spec(
        "job_openai",
        problem_image_artifact_id="img_problem_123",
        teacher_solution_image_artifact_id="img_teacher_456",
        problem_image_path=problem,
        teacher_solution_image_path=teacher,
    )

    user_content = fake.responses.calls[0]["input"][1]["content"]
    image_items = [item for item in user_content if item["type"] == "input_image"]
    assert [item["detail"] for item in image_items] == ["auto", "auto"]


def test_openai_client_uses_falsy_injected_client(tmp_path, monkeypatch):
    problem, teacher = write_images(tmp_path)
    fake = FalsyFakeOpenAIClient(json.dumps(candidate_payload()))

    def fail_build_client(api_key: str, timeout_seconds: int) -> object:
        raise AssertionError("OpenAIAnalysisClient._build_client should not be called")

    monkeypatch.setattr(
        OpenAIAnalysisClient,
        "_build_client",
        staticmethod(fail_build_client),
    )
    client = OpenAIAnalysisClient(api_key="sk-test", model="gpt-5.5", client=fake)

    spec = client.extract_candidate_spec(
        "job_openai",
        problem_image_artifact_id="img_problem_123",
        teacher_solution_image_artifact_id="img_teacher_456",
        problem_image_path=problem,
        teacher_solution_image_path=teacher,
    )

    assert isinstance(spec, CandidateSpec)
    assert len(fake.responses.calls) == 1


def test_openai_schema_does_not_allow_arbitrary_properties():
    def collect_arbitrary_properties(schema: object) -> list[object]:
        if isinstance(schema, dict):
            matches = []
            if schema.get("additionalProperties") is True:
                matches.append(schema)
            for value in schema.values():
                matches.extend(collect_arbitrary_properties(value))
            return matches
        if isinstance(schema, list):
            matches = []
            for value in schema:
                matches.extend(collect_arbitrary_properties(value))
            return matches
        return []

    element_properties = CANDIDATE_SPEC_RESPONSE_SCHEMA["properties"]["elements"]["items"][
        "properties"
    ]

    assert collect_arbitrary_properties(CANDIDATE_SPEC_RESPONSE_SCHEMA) == []
    for property_name in ["geometry", "style", "interaction", "validation"]:
        assert element_properties[property_name]["additionalProperties"] is False
    assert (
        element_properties["revision_history"]["items"]["additionalProperties"]
        is False
    )


def test_openai_schema_allows_renderable_dimension_marker_contract():
    element_schema = CANDIDATE_SPEC_RESPONSE_SCHEMA["properties"]["elements"]["items"]
    element_properties = element_schema["properties"]
    geometry_properties = element_properties["geometry"]["properties"]
    revision_properties = element_properties["revision_history"]["items"]["properties"]
    uncertainty_properties = CANDIDATE_SPEC_RESPONSE_SCHEMA["properties"][
        "uncertainties"
    ]["items"]["properties"]

    assert element_properties["geometry"]["additionalProperties"] is False
    for property_name in [
        "target_anchor_start",
        "target_anchor_end",
        "visible_strokes",
        "label_anchor",
    ]:
        assert property_name in geometry_properties
    for property_name in ["stroke_width", "opacity"]:
        assert property_name in element_properties["style"]["properties"]
    for property_name in ["revision_id", "source", "patch"]:
        assert property_name in revision_properties
    for property_name in ["id", "message", "bbox"]:
        assert property_name in uncertainty_properties


def test_extract_candidate_spec_accepts_dimension_marker_payload(tmp_path):
    problem, teacher = write_images(tmp_path)
    fake = FakeOpenAIClient(json.dumps(candidate_payload_with_dimension_marker()))
    client = OpenAIAnalysisClient(api_key="sk-test", model="gpt-5.5", client=fake)

    spec = client.extract_candidate_spec(
        "job_openai",
        problem_image_artifact_id="img_problem_123",
        teacher_solution_image_artifact_id="img_teacher_456",
        problem_image_path=problem,
        teacher_solution_image_path=teacher,
    )

    element = spec.elements[0]
    assert element.type == "freehand_dimension_marker"
    assert element.geometry["target_anchor_end"] == [120, 40]
    assert element.geometry["visible_strokes"][0]["stroke_id"] == "stroke_001"


def test_extract_candidate_spec_parses_top_level_dict_output_text(tmp_path):
    problem, teacher = write_images(tmp_path)
    fake = FakeOpenAIClientWithResponse(
        {"output_text": json.dumps(candidate_payload())}
    )
    client = OpenAIAnalysisClient(api_key="sk-test", model="gpt-5.5", client=fake)

    spec = client.extract_candidate_spec(
        "job_openai",
        problem_image_artifact_id="img_problem_123",
        teacher_solution_image_artifact_id="img_teacher_456",
        problem_image_path=problem,
        teacher_solution_image_path=teacher,
    )

    assert isinstance(spec, CandidateSpec)


def test_extract_candidate_spec_parses_top_level_dict_output_content(tmp_path):
    problem, teacher = write_images(tmp_path)
    fake = FakeOpenAIClientWithResponse(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(candidate_payload()),
                        }
                    ]
                }
            ]
        }
    )
    client = OpenAIAnalysisClient(api_key="sk-test", model="gpt-5.5", client=fake)

    spec = client.extract_candidate_spec(
        "job_openai",
        problem_image_artifact_id="img_problem_123",
        teacher_solution_image_artifact_id="img_teacher_456",
        problem_image_path=problem,
        teacher_solution_image_path=teacher,
    )

    assert isinstance(spec, CandidateSpec)


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
