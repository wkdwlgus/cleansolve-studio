# M7 OpenAI Adapter Integration 상세 설계

## 1. 목적

M7의 목적은 기존 mock analysis client와 같은 계약을 유지하면서 실제 OpenAI Responses API 기반 analysis adapter를 추가하고, workflow가 설정값에 따라 `mock` 또는 `openai` adapter를 선택할 수 있게 만드는 것이다.

M7은 OpenAI adapter의 제품 경로를 연결하되, 기본 로컬 개발과 CI가 OpenAI API key에 의존하지 않도록 한다. 따라서 기본값은 반드시 `mock`이며, `openai` adapter는 명시적 설정과 API key가 있을 때만 사용된다.

## 2. 범위

이번 milestone에서 구현한다.

- `OpenAIAnalysisClient`
- adapter 선택 factory
- `AnalysisClient` protocol signature 정리
- workflow `analyze_sources`의 adapter selection 연결
- OpenAI Responses API 요청 payload builder
- Structured Outputs schema 계약
- OpenAI 응답 parsing과 `CandidateSpec` validation
- API key 없음/설정 오류/모델 호출 오류의 명시적 실패 계약
- optional real smoke test harness
- README와 `.env.example`의 M7 설정 문서화
- roadmap M7 상태 갱신

이번 milestone에서 구현하지 않는다.

- OpenAI image generation/editing API 호출
- 전체 이미지 one-shot regeneration
- PDF export
- 상용 품질 visual compositing
- browser/web UI 설정 화면
- 사용자가 업로드한 손글씨 스타일 예시 기반 개인화
- OpenAI 호출 결과를 무조건 승인하는 bypass
- OpenAI API key를 repository에 저장하는 기능

## 3. 공식 OpenAI API 기준

M7은 OpenAI Responses API를 사용한다. OpenAI 공식 문서 기준 Responses API는 text 또는 image input을 받아 text 또는 JSON output을 생성할 수 있다.

Structured Outputs는 JSON mode보다 강한 schema adherence를 제공한다. M7은 candidate spec JSON을 받아야 하므로 JSON mode가 아니라 Structured Outputs를 사용한다.

모델 기본값은 `OPENAI_MODEL_ANALYSIS`로 설정한다. 새 프로젝트의 최신 대형 모델 권장값은 공식 문서 기준 `gpt-5.5`이므로 M7 이후 기본값은 `gpt-5.5`로 갱신한다.

## 4. 환경 변수

`apps/api/cleansolve_api/settings.py`에 아래 설정을 추가하거나 갱신한다.

```python
AnalysisClientKind = Literal["mock", "openai"]

openai_api_key: str | None
openai_model_analysis: str
openai_model_validation: str
openai_model_image: str
analysis_client: AnalysisClientKind
openai_analysis_image_detail: Literal["low", "high", "auto", "original"]
openai_analysis_timeout_seconds: int
```

환경 변수 이름과 기본값은 정확히 아래와 같다.

| 환경 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `CLEANSOLVE_ANALYSIS_CLIENT` | `mock` | `mock` 또는 `openai` |
| `OPENAI_API_KEY` | 없음 | `openai` adapter 사용 시 필수 |
| `OPENAI_MODEL_ANALYSIS` | `gpt-5.5` | candidate spec 생성 모델 |
| `OPENAI_MODEL_VALIDATION` | `gpt-5.5` | 후속 validation adapter용 예약 설정 |
| `OPENAI_MODEL_IMAGE` | `gpt-image-1` | 후속 image generation/editing용 예약 설정 |
| `OPENAI_ANALYSIS_IMAGE_DETAIL` | `auto` | Responses API image input detail |
| `OPENAI_ANALYSIS_TIMEOUT_SECONDS` | `60` | OpenAI request timeout |

`CLEANSOLVE_ANALYSIS_CLIENT`가 `mock`이면 `OPENAI_API_KEY`가 없어도 오류가 나면 안 된다.

`CLEANSOLVE_ANALYSIS_CLIENT`가 `openai`이고 `OPENAI_API_KEY`가 비어 있으면 adapter 생성 시 `OpenAIConfigurationError`를 발생시킨다.

`CLEANSOLVE_ANALYSIS_CLIENT`가 `mock` 또는 `openai`가 아니면 settings validation에서 실패한다.

## 5. Python 의존성

`pyproject.toml` dependencies에 `openai`를 추가한다.

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

OpenAI package import는 `OpenAIAnalysisClient` 내부 또는 해당 테스트에서만 직접 수행한다. Mock path import만으로 OpenAI client 객체가 생성되면 안 된다.

## 6. Adapter 계약

`packages/ai/cleansolve_ai/adapter.py`를 아래 방향으로 갱신한다.

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

기존 `MockAnalysisClient`는 새 optional path parameter를 받아야 하지만 사용하지 않는다. 이 변경은 workflow가 mock/openai adapter를 같은 방식으로 호출할 수 있게 하기 위한 것이다.

## 7. Error 모델

`packages/ai/cleansolve_ai/errors.py`를 추가한다.

```python
class OpenAIAdapterError(RuntimeError):
    """Base error for OpenAI adapter failures."""


class OpenAIConfigurationError(OpenAIAdapterError):
    """Raised when OpenAI adapter settings are invalid."""


class OpenAIResponseError(OpenAIAdapterError):
    """Raised when OpenAI response cannot be parsed or validated."""
```

이 error들은 API route에서 raw exception으로 노출하지 않는다. Workflow node에서는 예외를 전파하고, FastAPI `run_job()` route가 예외를 잡아 job manifest를 안전한 `FAILED` 상태로 저장한 뒤 structured HTTP 502를 반환한다.

단위 테스트는 error type과 message를 검증한다.

## 8. OpenAIAnalysisClient

파일: `packages/ai/cleansolve_ai/openai_client.py`

### 8.1 Constructor

```python
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
```

규칙:

- `api_key`가 빈 문자열이면 `OpenAIConfigurationError`.
- `model`이 빈 문자열이면 `OpenAIConfigurationError`.
- `image_detail`은 `low`, `high`, `auto`, `original` 중 하나만 허용한다.
- `timeout_seconds`는 1 이상이어야 한다.
- `client`가 주어지면 테스트 double로 사용한다.
- `client`가 없으면 `openai.OpenAI(api_key=api_key, timeout=timeout_seconds)`를 생성한다.

### 8.2 입력 이미지 정책

M7 구현은 실제 image bytes를 Responses API에 전달한다.

이유:

- SoT는 M7의 핵심을 실제 이미지 분석 기반 candidate spec 생성으로 본다.
- artifact id만 prompt에 넣는 방식은 smoke-safe하지만 실제 analysis adapter가 아니므로 M7 완료 기준을 만족하지 못한다.

이미지 전달 방식:

- `problem_image_path`와 `teacher_solution_image_path`가 모두 필요하다.
- 둘 중 하나라도 없으면 `OpenAIConfigurationError`.
- 파일이 존재하지 않으면 `OpenAIConfigurationError`.
- 파일 확장자 또는 magic byte로 MIME을 판정한다.
- 지원 MIME은 `image/png`, `image/jpeg`만이다.
- 이미지는 base64 data URL로 인코딩해 `input_image.image_url`에 넣는다.
- `detail`은 `settings.openai_analysis_image_detail` 값을 사용한다.

### 8.3 Prompt 정책

Prompt는 코드 상수로 둔다.

파일: `packages/ai/cleansolve_ai/prompts.py`

```python
ANALYSIS_DEVELOPER_PROMPT = """..."""
ANALYSIS_USER_PROMPT_TEMPLATE = """..."""
```

Developer prompt 필수 내용:

- 원본 문제 이미지는 최상위 source of truth다.
- 선생님 손풀이 이미지를 원본 문제 위에 재구성하기 위한 candidate spec을 생성한다.
- 전체 이미지를 다시 생성하지 않는다.
- JSON schema를 반드시 따른다.
- 모르는 값은 추측하지 말고 `needs_review=true`, `requires_human_review=true` 또는 `uncertainties`에 남긴다.
- style은 초기 MVP 기준 `system_builtin`, `default_pretty_handwriting`, `v1`만 사용한다.
- element id는 deterministic prefix를 사용한다.
- page size는 원본 문제 이미지 기준 pixel width/height다.
- source image artifact id를 그대로 `source_images`에 넣는다.
- target anchor와 visible stroke를 구분한다.

User prompt dynamic fields:

- `job_id`
- `problem_image_artifact_id`
- `teacher_solution_image_artifact_id`
- 지원 primitive 목록
- review policy 요약

Prompt에는 API key, local absolute filesystem path, 원본 파일명, 사용자 개인 정보가 들어가면 안 된다.

## 9. Structured Output schema

M7은 `CandidateSpec.model_json_schema()`를 그대로 OpenAI Structured Outputs schema로 사용하지 않는다.

이유:

- Pydantic JSON schema의 일부 표현은 OpenAI strict JSON schema subset과 맞지 않을 수 있다.
- M7에서 full schema를 그대로 넣으면 실패 지점이 schema compatibility인지 모델 품질인지 구분하기 어렵다.

대신 `packages/ai/cleansolve_ai/openai_schema.py`에 M7 전용 schema dict를 명시적으로 둔다.

필수 top-level fields:

- `job_id`
- `version`
- `source_images`
- `style`
- `page`
- `regions`
- `elements`
- `uncertainties`

필수 element fields:

- `id`
- `type`
- `confidence`
- `needs_review`
- `requires_human_review`
- `auto_correctable`
- `evidence`
- `bbox`
- `geometry`
- `style`
- `interaction`
- `validation`
- `revision_history`

허용 primitive type은 `cleansolve_spec.models.PrimitiveType`의 현재 Literal 전체와 일치해야 한다.

`geometry`, `style`, `interaction`, `validation`, `revision_history`, `uncertainties`는 primitive별 상세 schema가 아직 얇기 때문에 M7 strict schema에서는 아래처럼 제한한다.

- `geometry`: object, `additionalProperties`는 string/number/boolean/null/array/object JSON value를 허용한다.
- `style`: object, 동일한 JSON value map을 허용한다.
- `interaction`: object, 동일한 JSON value map을 허용한다.
- `validation`: object, 동일한 JSON value map을 허용한다.
- `revision_history`: array of object, 동일한 JSON value map을 허용한다.
- `uncertainties`: array of object, 동일한 JSON value map을 허용한다.

구현자는 OpenAI strict schema subset이 이 자유형 map을 거부하는 경우, `strict=True`를 유지한 채 아래 fallback schema를 사용한다.

- `geometry`, `style`, `interaction`, `validation`을 required empty-object-compatible schema로 둔다.
- primitive별 세부 구조 검증은 OpenAI schema가 아니라 `CandidateSpec.model_validate()`와 `validate_candidate_spec()`가 담당한다.
- 이 fallback을 사용하면 반드시 `packages/ai/tests/test_openai_client.py`에 schema payload snapshot test를 추가해 request shape를 고정한다.

Schema 이름은 `candidate_spec_m7`이다.

OpenAI request의 text format은 아래 구조를 사용한다.

```python
"text": {
    "format": {
        "type": "json_schema",
        "name": "candidate_spec_m7",
        "strict": True,
        "schema": CANDIDATE_SPEC_RESPONSE_SCHEMA,
    }
}
```

## 10. Responses API payload

`OpenAIAnalysisClient.extract_candidate_spec()`는 내부적으로 아래 payload를 만든다.

```python
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
                    "image_url": problem_data_url,
                    "detail": self._image_detail,
                },
                {
                    "type": "input_image",
                    "image_url": teacher_solution_data_url,
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
```

M7에서는 `tools`, `web_search`, `file_search`, `image_generation`을 사용하지 않는다.

## 11. 응답 parsing

Parsing 순서:

1. `response.output_text`가 있으면 사용한다.
2. 없으면 `response.output`에서 first message의 first `output_text` content를 찾는다.
3. 둘 다 없으면 `OpenAIResponseError`.
4. JSON decode 실패 시 `OpenAIResponseError`.
5. `CandidateSpec.model_validate(decoded)` 실패 시 `OpenAIResponseError`.
6. `spec.job_id != job_id`면 `OpenAIResponseError`.
7. `spec.source_images.problem_image_id != problem_image_artifact_id`면 `OpenAIResponseError`.
8. `spec.source_images.teacher_solution_image_id != teacher_solution_image_artifact_id`면 `OpenAIResponseError`.
9. `spec.version != 1`이면 `OpenAIResponseError`.

Parsing 성공 후에는 `CandidateSpec`을 반환한다.

## 12. Adapter factory

파일: `packages/ai/cleansolve_ai/client_factory.py`

```python
def build_analysis_client(
    *,
    client_kind: str,
    openai_api_key: str | None = None,
    openai_model_analysis: str = "gpt-5.5",
    openai_analysis_image_detail: str = "auto",
    openai_analysis_timeout_seconds: int = 60,
) -> AnalysisClient:
```

규칙:

- `client_kind == "mock"`이면 `MockAnalysisClient()` 반환.
- `client_kind == "openai"`이면 `OpenAIAnalysisClient(...)` 반환.
- unknown `client_kind`면 `OpenAIConfigurationError`.

`packages/ai/cleansolve_ai/__init__.py`는 아래를 export한다.

- `AnalysisClient`
- `MockAnalysisClient`
- `OpenAIAnalysisClient`
- `build_analysis_client`
- `OpenAIAdapterError`
- `OpenAIConfigurationError`
- `OpenAIResponseError`

## 13. Workflow 연결

`packages/workflow/cleansolve_workflow/nodes.py`의 `analyze_sources()`는 직접 `MockAnalysisClient()`를 생성하지 않는다.

대신 새 helper를 사용한다.

```python
def _analysis_client_from_state(state: WorkflowState) -> AnalysisClient:
```

State 입력:

- `analysis_client_kind`
- `openai_api_key`
- `openai_model_analysis`
- `openai_analysis_image_detail`
- `openai_analysis_timeout_seconds`
- `source_image_paths`

`run_mock_workflow()`는 이름을 유지한다. M7에서 public API rename은 하지 않는다.

`run_mock_workflow()` signature에 optional parameter를 추가한다.

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
    ...
) -> WorkflowState:
```

기본값은 `mock`이므로 기존 tests는 수정 없이 통과해야 한다.

`analyze_sources()` 호출 시:

- artifact id는 기존처럼 `source_image_artifact_ids`에서 읽는다.
- path는 `source_image_paths`에서 읽는다.
- selected client의 `extract_candidate_spec()`에 id와 path를 모두 전달한다.

## 14. API route 연결

`apps/api/cleansolve_api/routes/jobs.py`의 `run_job()`은 settings를 workflow에 전달한다.

추가 전달 값:

- `analysis_client_kind=settings.analysis_client`
- `openai_api_key=settings.openai_api_key`
- `openai_model_analysis=settings.openai_model_analysis`
- `openai_analysis_image_detail=settings.openai_analysis_image_detail`
- `openai_analysis_timeout_seconds=settings.openai_analysis_timeout_seconds`
- `source_image_paths`

`source_image_paths`는 manifest의 latest image artifact metadata에서 찾은 local artifact path다.

규칙:

- API response에는 local absolute path를 노출하지 않는다.
- `CLEANSOLVE_ANALYSIS_CLIENT=mock`이면 image path를 workflow에 넘겨도 mock은 사용하지 않는다.
- `CLEANSOLVE_ANALYSIS_CLIENT=openai`이면 image path가 반드시 있어야 한다.

## 15. API failure 정책

M7에서는 OpenAI adapter failure를 job manifest의 `FAILED` 상태로 저장한다.

이유:

- roadmap M7 완료 기준은 adapter failure가 job을 안전한 failed/retryable 상태로 만드는 것이다.
- OpenAI 실패가 발생했을 때 manifest를 그대로 `CREATED` 또는 이전 상태로 남기면 사용자가 실패 원인을 구분하기 어렵다.
- M7에서는 retry queue를 만들지 않지만, 동일한 job에서 입력 artifact를 유지하므로 사용자가 설정을 고친 뒤 `POST /jobs/{job_id}/run`을 다시 호출할 수 있다.

`LocalArtifactStore`에 아래 helper를 추가한다.

```python
def save_failed_analysis_run(
    self,
    job_id: str,
    *,
    client: str,
    reason: str,
) -> JobManifest:
```

동작:

- job id를 검증한다.
- manifest를 lock 안에서 읽는다.
- `status`를 `FAILED`로 바꾼다.
- `updated_at`을 갱신한다.
- `review_items`에 아래 internal item을 append한다.

```json
{
  "type": "analysis_adapter_failed",
  "client": "openai",
  "retryable": true,
  "review_reason": null,
  "safe_reason": "configuration_error"
}
```

`review_reason`은 `null`이므로 기존 `/review-items` endpoint에는 노출되지 않는다.

M7 API behavior:

- OpenAI configuration error 또는 response error가 발생하면 FastAPI 기본 500이 아니라 structured HTTP 502를 반환한다.
- 새 error code는 `ANALYSIS_ADAPTER_FAILED`다.
- message는 `analysis adapter 실행에 실패했습니다.`다.
- fields는 `{ "client": "openai" }`와 safe `reason`만 포함한다.
- safe reason에는 API key, local path, raw model output, prompt 전체가 들어가면 안 된다.
- 502를 반환하기 전에 manifest 상태는 `FAILED`로 저장되어야 한다.

`apps/api/cleansolve_api/artifacts.py`에 error helper를 추가한다.

```python
def analysis_adapter_failed_error(client: str, reason: str) -> HTTPException:
```

## 16. Tests

### 16.1 Unit tests: OpenAI client payload

파일: `packages/ai/tests/test_openai_client.py`

테스트:

1. constructor rejects empty api key.
2. constructor rejects invalid image detail.
3. `extract_candidate_spec()` rejects missing image paths.
4. request payload uses `responses.create`.
5. request payload includes developer message, user message, two `input_image` items, configured detail.
6. request payload uses `text.format.type == "json_schema"`.
7. response JSON is parsed into `CandidateSpec`.
8. mismatched job id raises `OpenAIResponseError`.
9. mismatched source image artifact id raises `OpenAIResponseError`.

No test may call the real OpenAI network by default.

### 16.2 Unit tests: factory

파일: `packages/ai/tests/test_client_factory.py`

테스트:

1. `mock` returns `MockAnalysisClient`.
2. `openai` returns `OpenAIAnalysisClient` when key is present.
3. `openai` without key raises `OpenAIConfigurationError`.
4. unknown kind raises `OpenAIConfigurationError`.

### 16.3 Workflow tests

파일: `packages/workflow/tests/test_graph.py`

추가 테스트:

1. default workflow still uses mock and passes without API key.
2. workflow passes image ids and image paths into selected injected OpenAI-style client.
3. OpenAI adapter error propagates from `analyze_sources()`.

M7에서는 worker가 필요하면 `run_mock_workflow()`에 `analysis_client_override` test-only parameter를 추가할 수 있다. 이 parameter는 public API route에서 사용하지 않는다.

### 16.4 API tests

파일: `apps/api/tests/test_jobs_api.py`

추가 테스트:

1. default settings keep `/jobs/{job_id}/run` mock path green without API key.
2. `CLEANSOLVE_ANALYSIS_CLIENT=openai` and missing key returns 502 `ANALYSIS_ADAPTER_FAILED`.
3. `CLEANSOLVE_ANALYSIS_CLIENT=invalid` settings validation fails.
4. API does not expose local path in adapter failure fields.
5. OpenAI adapter failure stores manifest status as `FAILED`.
6. OpenAI adapter failure appends an internal retryable review item that `/review-items` does not expose.

### 16.5 Optional smoke test

파일: `packages/ai/tests/test_openai_smoke.py`

조건:

- 기본 pytest에서 skip.
- `RUN_OPENAI_SMOKE=1`
- `OPENAI_API_KEY` 존재
- fixture image pair 존재

검증:

- `OpenAIAnalysisClient.extract_candidate_spec()`를 실제 호출한다.
- 반환값이 `CandidateSpec`으로 validate된다.
- `spec.source_images`가 입력 artifact id와 일치한다.

Smoke test는 비용이 발생하므로 CI 기본 경로에서 실행하지 않는다.

## 17. Documentation

`README.md`의 OpenAI API Key 섹션을 갱신한다.

포함할 내용:

- 기본값은 mock adapter.
- real adapter 사용 시:

```env
CLEANSOLVE_ANALYSIS_CLIENT=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ANALYSIS=gpt-5.5
OPENAI_ANALYSIS_IMAGE_DETAIL=auto
OPENAI_ANALYSIS_TIMEOUT_SECONDS=60
```

- API key는 `apps/api/.env` 또는 환경 변수/secret store에 둔다.
- API key는 commit하지 않는다.
- smoke test 실행 방법:

```bash
RUN_OPENAI_SMOKE=1 OPENAI_API_KEY=sk-... python -m pytest packages/ai/tests/test_openai_smoke.py -q
```

`apps/api/.env.example`에도 새 env를 추가한다.

`docs/product/mvp-roadmap.md`는 implementation이 끝난 뒤에만 M7 상태를 `Done`으로 바꾼다.

## 18. Security and privacy

- API key는 log, exception message, test snapshot, artifact에 기록하지 않는다.
- local absolute path는 API response에 노출하지 않는다.
- OpenAI request에는 image bytes와 최소 metadata만 보낸다.
- 원본 파일명은 prompt에 넣지 않는다.
- prompt에는 artifact id와 job id만 넣는다.
- raw model output은 error fields에 넣지 않는다.
- optional smoke test는 명시 opt-in이 있어야만 실행한다.

## 19. Acceptance criteria

M7 완료 조건:

1. `CLEANSOLVE_ANALYSIS_CLIENT` 기본값은 `mock`이다.
2. API key 없이 `python -m pytest -q`가 통과한다.
3. API key 없이 mock upload-to-run E2E가 통과한다.
4. `OpenAIAnalysisClient`가 Responses API payload를 생성한다.
5. Responses API payload는 two image inputs와 Structured Outputs schema를 포함한다.
6. OpenAI response JSON은 `CandidateSpec`으로 validate된다.
7. invalid OpenAI output은 `OpenAIResponseError`로 거부된다.
8. `CLEANSOLVE_ANALYSIS_CLIENT=openai` + missing key는 structured 502로 실패한다.
9. optional smoke test는 opt-in env 없이는 skip된다.
10. README와 `.env.example`에 real adapter 설정 방법이 한국어로 문서화된다.
11. OpenAI image generation/editing API는 호출하지 않는다.
12. 전체 이미지 one-shot regeneration 경로는 추가하지 않는다.

## 20. 다음 단계

이 spec이 승인되면 `superpowers:writing-plans`를 사용해 `docs/superpowers/plans/2026-06-18-openai-adapter-integration.md`를 작성한다.
