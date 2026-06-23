# Artifact Path Hardening 상세 설계

## 목적

`LocalArtifactStore`가 manifest에 저장된 artifact `relative_path`를 읽을 때 job 디렉터리 밖 파일을 참조하지 못하게 막는다.

이번 작업은 다음 SSE/progress UI milestone 전에 처리하는 보안/스토리지 hardening이다. `review_correction`, `progress_events` artifact replay가 기존 analysis artifact reader를 재사용하므로, progress stream을 추가하기 전에 read path containment 계약을 먼저 고정한다.

## 범위

### 포함

- analysis artifact read path hardening
  - `LocalArtifactStore.read_latest_analysis_payload()`
  - 적용 artifact type:
    - `candidate_spec`
    - `validation_report`
    - `correction_plan`
    - `review_correction`
    - `progress_events`
- render artifact read path hardening
  - `LocalArtifactStore.rendered_preview_response()`
  - `LocalArtifactStore.latest_render_artifact()`
- 내부 공통 path containment helper 추가
- corrupt manifest fixture 기반 API/store 테스트 추가

### 제외

- 새로운 artifact type 추가
- manifest schema 변경
- SSE endpoint 추가
- web UI 변경
- OpenAI/GPT/image generation 호출 변경
- export artifact 동작 변경. 단, 기존 export path helper와 새 공통 helper의 규칙은 같아야 한다.
- image upload write path 변경

## 현재 문제

현재 `read_latest_analysis_payload()`는 다음 방식으로 artifact 파일을 읽는다.

```python
artifact_path = self._job_root(job_id) / artifact.relative_path
if not artifact_path.exists():
    raise analysis_artifact_not_found_error(artifact_type)
return json.loads(artifact_path.read_text(encoding="utf-8"))
```

이 방식은 manifest가 손상되었거나 내부적으로 조작된 경우 다음 값을 막지 못한다.

- `../escape.json`
- `/tmp/escape.json`
- `artifacts/specs/link.json`이 job root 밖 파일을 가리키는 symlink

같은 패턴이 render read path에도 있다.

```python
artifact_path = self._job_root(job_id) / artifact.relative_path
```

이미 export download path에는 `Path.resolve()`와 `relative_to(job_root)` 검사가 있다. 이번 작업은 analysis/render read path도 같은 수준의 containment를 적용한다.

## 보안 계약

모든 manifest 기반 read path는 다음 조건을 만족해야 한다.

1. `relative_path`가 absolute path이면 거부한다.
2. `relative_path`를 `job_root`와 결합한 뒤 `resolve()`한 경로가 `job_root.resolve()` 내부가 아니면 거부한다.
3. symlink가 job root 밖을 가리키면 거부한다.
4. 거부 시 path 값을 응답에 노출하지 않는다.
5. 거부 시 기존 artifact별 404 error contract를 유지한다.
6. 정상 artifact 저장/조회 API 응답 shape는 바꾸지 않는다.

## 에러 매핑

| 대상 | 함수 | escape/absolute/missing일 때 에러 |
| --- | --- | --- |
| analysis artifact | `read_latest_analysis_payload()` | `analysis_artifact_not_found_error(artifact_type)` |
| rendered preview response | `rendered_preview_response()` | `render_artifact_not_found_error()` |
| latest render artifact | `latest_render_artifact()` | `render_artifact_not_found_error()` |
| export artifact | `latest_export_response()`, `export_download()` | 기존 `export_artifact_not_found_error()` 유지 |

## 구현 설계

### 새 내부 helper

`apps/api/cleansolve_api/artifacts.py`의 `LocalArtifactStore`에 다음 helper를 추가한다.

```python
def _artifact_path_inside_job(
    self,
    job_id: str,
    relative_path_value: str,
    not_found_error: HTTPException,
) -> Path:
    relative_path = Path(relative_path_value)
    if relative_path.is_absolute():
        raise not_found_error

    job_root = self._job_root(job_id).resolve()
    artifact_path = (job_root / relative_path).resolve()
    try:
        artifact_path.relative_to(job_root)
    except ValueError:
        raise not_found_error from None
    return artifact_path
```

세부 규칙:

- helper는 파일 존재 여부를 검사하지 않는다.
- helper는 containment만 검사한다.
- caller가 `exists()`와 read를 수행하고, missing이면 기존 artifact별 not found error를 raise한다.
- `not_found_error`는 caller가 만든 `HTTPException` 객체를 그대로 받는다.
- helper는 path 문자열을 error detail에 포함하지 않는다.

### analysis read path

`read_latest_analysis_payload()`는 artifact lookup 이후 다음 순서로 동작한다.

1. `artifact_path = self._artifact_path_inside_job(job_id, artifact.relative_path, analysis_artifact_not_found_error(artifact_type))`
2. `if not artifact_path.exists(): raise analysis_artifact_not_found_error(artifact_type)`
3. `return json.loads(artifact_path.read_text(encoding="utf-8"))`

JSON decode error 처리는 이번 범위에서 새로 정의하지 않는다. 현재도 corrupt JSON은 별도 wrapping하지 않으며, 이번 작업은 path containment만 다룬다.

### render read path

`rendered_preview_response()`와 `latest_render_artifact()`는 artifact lookup 이후 다음 순서로 동작한다.

1. `artifact_path = self._artifact_path_inside_job(job_id, artifact.relative_path, render_artifact_not_found_error())`
2. `if not artifact_path.exists(): raise render_artifact_not_found_error()`
3. SVG text를 읽는다.

### export helper 정리

기존 `_export_artifact_path()`의 외부 동작은 바꾸지 않는다. 내부 구현은 반드시 새 공통 helper를 재사용한다.

```python
def _export_artifact_path(self, job_id: str, artifact: ExportArtifact) -> Path:
    return self._artifact_path_inside_job(
        job_id,
        artifact.relative_path,
        export_artifact_not_found_error(),
    )
```

동작은 기존 테스트와 동일해야 한다.

## 테스트 설계

테스트는 `apps/api/tests/test_jobs_api.py`에 추가한다.

### analysis artifact escape

테스트명:

```python
def test_read_latest_analysis_payload_rejects_path_escape_from_corrupt_manifest(tmp_path):
```

절차:

1. `LocalArtifactStore(tmp_path / "jobs")` 생성
2. job 생성
3. `manifest.latest_image_artifact_ids`를 임의 source id로 채워 저장
4. `store.save_analysis_outputs(job_id=manifest.job_id, status_value="APPROVED", revision_attempts=1, review_items=[], candidate_spec_payload={"job_id": manifest.job_id, "version": 1}, validation_report_payload={"report_id": "report_1", "passed": True, "issues": []}, correction_plan_payload={"job_id": manifest.job_id, "revision_attempts": 1, "correction_plans": []}, source_image_artifact_ids=source_ids)`로 정상 candidate spec artifact 생성
5. 최신 `candidate_spec` artifact의 `relative_path`를 `"../escape.json"`로 변경
6. manifest 저장
7. `tmp_path / "jobs" / "escape.json"`에 JSON 파일 작성
8. `store.read_latest_analysis_payload(job_id, "candidate_spec")` 호출
9. `HTTPException` status code `404`, detail code `ANALYSIS_ARTIFACT_NOT_FOUND` 검증

절대 경로도 같은 테스트에서 검증한다.

1. artifact `relative_path`를 `str(tmp_path / "escape-absolute.json")`로 변경
2. 해당 파일 작성
3. 동일하게 404 검증

### analysis artifact symlink escape

테스트명:

```python
def test_read_latest_analysis_payload_rejects_symlink_escape_from_corrupt_manifest(tmp_path):
```

절차:

1. 정상 analysis artifact 생성
2. job root 아래 `artifacts/specs/spec_escape.json` symlink를 생성하고 target은 `tmp_path / "outside.json"`로 둔다.
3. artifact `relative_path`를 `"artifacts/specs/spec_escape.json"`로 변경
4. `read_latest_analysis_payload()` 호출
5. `ANALYSIS_ARTIFACT_NOT_FOUND` 404 검증

Windows 또는 symlink 미지원 환경은 현재 주 대상이 아니다. macOS/Linux 기준으로 테스트한다.

### render artifact escape

테스트명:

```python
def test_render_artifact_reads_reject_path_escape_from_corrupt_manifest(tmp_path):
```

절차:

1. `save_render_artifact()`로 정상 render artifact 생성
2. manifest의 최신 render artifact `relative_path`를 `"../escape.svg"`로 변경
3. `tmp_path / "jobs" / "escape.svg"`에 SVG 작성
4. 다음 두 호출이 모두 `RENDER_ARTIFACT_NOT_FOUND` 404를 내는지 검증
   - `store.rendered_preview_response(job_id)`
   - `store.latest_render_artifact(job_id)`

### 기존 export test 유지

기존 테스트 `test_store_rejects_export_download_path_escape_from_corrupt_manifest`는 그대로 통과해야 한다.

## 검증 명령

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests/test_jobs_api.py -q
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests -q
git diff --check
```

## 완료 기준

- corrupt analysis artifact `relative_path`가 job root 밖을 가리키면 404로 거부된다.
- corrupt render artifact `relative_path`가 job root 밖을 가리키면 404로 거부된다.
- path 값은 API error detail에 포함되지 않는다.
- 정상 job 생성, run, artifact 조회, render, export 테스트가 회귀 없이 통과한다.
- SSE, web UI, GPT/OpenAI/image generation 관련 변경이 없다.

## 다음 작업

이 hardening 브랜치가 병합된 뒤 `job progress SSE stream과 web progress UI` 설계/구현으로 돌아간다.
