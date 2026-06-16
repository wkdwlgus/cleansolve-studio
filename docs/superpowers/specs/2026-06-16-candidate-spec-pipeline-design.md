# M2 Candidate Spec Pipeline 상세 설계

Date: 2026-06-16
Status: Approved

## 목적

M2의 목적은 M1에서 저장한 원본 문제 이미지와 선생님 손풀이 이미지 artifact를 mock analysis workflow 입력으로 연결하고, workflow 산출물을 job artifact로 저장하는 것이다.

이번 milestone은 실제 OpenAI adapter를 붙이지 않는다. 실제 OpenAI 호출은 M7에서 다룬다.

이번 milestone은 renderer primitive 확장을 하지 않는다. renderer 확장은 M3에서 다룬다.

## 현재 기반

현재 API는 아래를 지원한다.

- `POST /jobs`
- `POST /jobs/{job_id}/images/problem`
- `POST /jobs/{job_id}/images/teacher-solution`
- `POST /jobs/{job_id}/run`
- `GET /jobs/{job_id}`
- `GET /jobs/{job_id}/review-items`

현재 workflow는 `run_mock_workflow(job_id)`로 실행되며, 메모리 state 안에 아래 값을 만든다.

- `candidate_spec`
- `validation_reports`
- `correction_plans`
- `revision_attempts`
- `review_items`
- `status`

현재 API는 workflow 결과 중 `status`, `revision_attempts`, `review_items`만 manifest에 저장한다.

## 범위

구현한다.

- uploaded image artifact id를 mock workflow candidate spec의 source image reference로 사용한다.
- `candidate_spec` artifact를 job 폴더에 저장한다.
- `validation_report` artifact를 job 폴더에 저장한다.
- `correction_plan` artifact를 job 폴더에 저장한다.
- analysis artifact metadata를 manifest에 저장한다.
- 최신 analysis artifact 조회 API를 추가한다.
- upload-to-run-to-artifact API 테스트를 추가한다.

구현하지 않는다.

- OpenAI adapter
- OCR
- 이미지 crop 또는 dataset matching
- renderer primitive 확장
- export
- web UI 변경
- spec patch API

## Artifact Type

M2에서 추가하는 artifact type은 정확히 아래 셋이다.

```text
candidate_spec
validation_report
correction_plan
```

Python type alias는 API layer에 둔다.

```python
AnalysisArtifactType = Literal[
    "candidate_spec",
    "validation_report",
    "correction_plan",
]
```

## 저장 경로

각 job root는 기존과 동일하게 `settings.storage_root / job_id`다.

M2 analysis artifact는 아래 경로에 저장한다.

```text
artifacts/specs/{artifact_id}.json
artifacts/reports/{artifact_id}.json
artifacts/corrections/{artifact_id}.json
```

Artifact id prefix는 아래를 사용한다.

| artifact type | prefix | path directory |
| --- | --- | --- |
| `candidate_spec` | `spec_` | `artifacts/specs` |
| `validation_report` | `report_` | `artifacts/reports` |
| `correction_plan` | `correction_` | `artifacts/corrections` |

Artifact id는 prefix + UUID hex다.

예:

```text
spec_0123456789abcdef0123456789abcdef
report_0123456789abcdef0123456789abcdef
correction_0123456789abcdef0123456789abcdef
```

## Analysis Artifact Metadata

Manifest에 저장할 metadata model은 아래 필드를 가진다.

```json
{
  "artifact_id": "spec_0123456789abcdef0123456789abcdef",
  "type": "candidate_spec",
  "relative_path": "artifacts/specs/spec_0123456789abcdef0123456789abcdef.json",
  "size_bytes": 1234,
  "sha256": "64 hex chars",
  "created_at": "2026-06-16T00:00:00Z",
  "source_image_artifact_ids": {
    "problem": "img_problem_id",
    "teacher_solution": "img_teacher_id"
  }
}
```

`size_bytes`는 UTF-8 JSON byte length다.

`sha256`은 저장된 JSON byte payload의 SHA-256 hex다.

`source_image_artifact_ids`는 run 시점의 `latest_image_artifact_ids` snapshot이다. 이후 같은 role의 이미지를 다시 업로드해도 이전 run artifact의 source reference는 바뀌지 않는다.

## Manifest 확장

`JobManifest`에 아래 필드를 추가한다.

```python
analysis_artifacts: dict[AnalysisArtifactType, list[AnalysisArtifact]]
latest_analysis_artifact_ids: dict[AnalysisArtifactType, str | None]
```

기존 manifest JSON을 읽을 수 있어야 하므로 두 필드는 default factory를 가진다.

Default value는 아래와 같다.

```json
{
  "analysis_artifacts": {
    "candidate_spec": [],
    "validation_report": [],
    "correction_plan": []
  },
  "latest_analysis_artifact_ids": {
    "candidate_spec": null,
    "validation_report": null,
    "correction_plan": null
  }
}
```

`job_response()`는 기존 응답 필드를 유지하고, 아래 두 필드를 추가한다.

```json
{
  "analysis_artifacts": {
    "candidate_spec": [],
    "validation_report": [],
    "correction_plan": []
  },
  "latest_analysis_artifact_ids": {
    "candidate_spec": null,
    "validation_report": null,
    "correction_plan": null
  }
}
```

기존 응답 필드 이름은 변경하지 않는다.

## Candidate Spec Source Image Reference

기존 mock client는 source image reference를 아래처럼 만든다.

```json
{
  "problem_image_id": "{job_id}_problem",
  "teacher_solution_image_id": "{job_id}_teacher_solution"
}
```

M2에서는 run 시점 manifest의 최신 image artifact id를 사용한다.

```json
{
  "problem_image_id": "img_...",
  "teacher_solution_image_id": "img_..."
}
```

이를 위해 `MockAnalysisClient.extract_candidate_spec()` signature를 아래로 확장한다.

```python
def extract_candidate_spec(
    self,
    job_id: str,
    *,
    problem_image_artifact_id: str | None = None,
    teacher_solution_image_artifact_id: str | None = None,
) -> CandidateSpec:
```

둘 중 하나라도 `None`이면 기존 fallback 값을 사용한다.

Workflow entry point는 아래 keyword를 받는다.

```python
run_mock_workflow(
    job_id: str,
    *,
    source_image_artifact_ids: dict[str, str | None] | None = None,
    max_revision_attempts: int = 2,
    candidate_spec_override=None,
    correction_patch_override: dict[str, object] | None = None,
) -> WorkflowState
```

`analyze_sources()`는 state의 `source_image_artifact_ids`를 `MockAnalysisClient`에 전달한다.

## Run 저장 절차

`POST /jobs/{job_id}/run`은 아래 순서를 따른다.

1. job id를 검증하고 manifest를 읽는다.
2. `latest_image_artifact_ids.problem`과 `latest_image_artifact_ids.teacher_solution`이 모두 있는지 확인한다.
3. 없으면 기존 `MISSING_REQUIRED_IMAGES` 409 error를 반환한다.
4. run 시점의 latest image artifact id snapshot을 만든다.
5. `run_mock_workflow(job_id=job_id, source_image_artifact_ids=snapshot)`을 실행한다.
6. workflow state에서 최신 candidate spec, 최신 validation report, correction plans list를 꺼낸다.
7. 아래 세 JSON payload를 저장한다.
   - candidate spec: `state["candidate_spec"].model_dump(mode="json")`
   - validation report: `state["validation_reports"][-1].model_dump(mode="json")`
   - correction plan: `{"job_id": job_id, "revision_attempts": state["revision_attempts"], "correction_plans": state.get("correction_plans", [])}`
8. 세 artifact metadata를 manifest에 append한다.
9. `latest_analysis_artifact_ids`를 세 artifact id로 갱신한다.
10. manifest의 `status`, `revision_attempts`, `review_items`, `updated_at`을 workflow state 기준으로 갱신한다.
11. 저장된 manifest를 `job_response()`로 반환한다.

세 artifact 저장과 manifest 갱신은 하나의 job lock 안에서 수행한다.

Artifact JSON 파일 쓰기는 temp file을 먼저 쓰고 `replace()`로 교체한다.

## API

### `GET /jobs/{job_id}/artifacts`

최신 manifest의 analysis artifact 목록만 반환한다.

Response:

```json
{
  "job_id": "job_...",
  "analysis_artifacts": {
    "candidate_spec": [],
    "validation_report": [],
    "correction_plan": []
  },
  "latest_analysis_artifact_ids": {
    "candidate_spec": null,
    "validation_report": null,
    "correction_plan": null
  }
}
```

Unknown job은 기존 `JOB_NOT_FOUND` 404를 반환한다.

### `GET /jobs/{job_id}/candidate-spec`

최신 candidate spec artifact JSON payload를 그대로 반환한다.

Run 전이면 아래 error를 반환한다.

```json
{
  "detail": {
    "code": "ANALYSIS_ARTIFACT_NOT_FOUND",
    "message": "분석 artifact를 찾을 수 없습니다.",
    "fields": {
      "artifact_type": "candidate_spec"
    }
  }
}
```

HTTP status는 404다.

### `GET /jobs/{job_id}/validation-report`

최신 validation report artifact JSON payload를 그대로 반환한다.

Run 전 error는 `artifact_type: "validation_report"`를 사용한다.

### `GET /jobs/{job_id}/correction-plan`

최신 correction plan artifact JSON payload를 그대로 반환한다.

Run 전 error는 `artifact_type: "correction_plan"`를 사용한다.

## Error Handling

기존 error를 유지한다.

- `JOB_NOT_FOUND`
- `MISSING_REQUIRED_IMAGES`
- `STORAGE_WRITE_FAILED`

M2에서 아래 error를 추가한다.

```python
"ANALYSIS_ARTIFACT_NOT_FOUND": "분석 artifact를 찾을 수 없습니다."
```

Artifact metadata가 manifest에 있는데 파일이 없으면 `ANALYSIS_ARTIFACT_NOT_FOUND` 404를 반환한다.

Artifact type이 내부 helper에 잘못 전달되면 `ValueError`를 발생시킨다. 외부 API route는 고정 route만 제공하므로 사용자 입력 artifact type은 받지 않는다.

## 상태 정책

Mock workflow state status를 manifest status로 그대로 저장한다.

따라서 `JobStatus`는 아래 값을 허용해야 한다.

```python
Literal[
    "CREATED",
    "APPROVED",
    "NEEDS_REVIEW",
    "FAILED",
    "REVISION_REQUIRED",
]
```

기존 기본 mock workflow는 correction 이후 `APPROVED`가 된다.

## Backward Compatibility

기존 테스트에서 직접 작성한 오래된 `manifest.json`은 `analysis_artifacts`와 `latest_analysis_artifact_ids`가 없다. M2 구현 후에도 해당 manifest는 읽혀야 한다.

이를 위해 `JobManifest`의 신규 필드는 default factory를 사용한다.

## Tests

새 테스트 파일은 만들지 않고 기존 API 테스트 파일에 M2 테스트를 추가한다.

추가할 테스트:

1. `POST /jobs/{job_id}/run` 후 job response에 analysis artifact metadata와 latest id가 포함된다.
2. run 후 세 JSON 파일이 실제 storage root 아래에 존재한다.
3. candidate spec의 `source_images.problem_image_id`와 `source_images.teacher_solution_image_id`가 업로드된 최신 image artifact id와 일치한다.
4. `GET /jobs/{job_id}/artifacts`가 analysis artifact 목록과 latest ids를 반환한다.
5. `GET /jobs/{job_id}/candidate-spec`가 최신 candidate spec JSON을 반환한다.
6. `GET /jobs/{job_id}/validation-report`가 최신 validation report JSON을 반환한다.
7. `GET /jobs/{job_id}/correction-plan`이 correction plan wrapper JSON을 반환한다.
8. run 전 세 latest artifact 조회 API는 `ANALYSIS_ARTIFACT_NOT_FOUND` 404를 반환한다.
9. 오래된 manifest JSON을 읽어도 신규 analysis fields가 default로 채워진다.

기존 테스트는 모두 계속 통과해야 한다.

## Acceptance Criteria

- `POST /jobs/{job_id}/run`이 mock workflow 결과를 세 analysis artifact JSON 파일로 저장한다.
- job response가 analysis artifact metadata와 latest ids를 포함한다.
- candidate spec은 업로드된 최신 image artifact id를 source image reference로 가진다.
- validation report와 correction plan을 API에서 조회할 수 있다.
- run 전 analysis artifact 조회는 structured 404를 반환한다.
- 기존 manifest JSON shape와 기존 API 테스트가 깨지지 않는다.
- 실제 OpenAI key 없이 전체 테스트가 통과한다.
