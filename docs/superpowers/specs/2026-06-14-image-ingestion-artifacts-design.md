# M1 Image Ingestion & Artifact Storage 상세 설계

Date: 2026-06-14
Status: Draft for user review

## 1. 목적

M1의 목적은 CleanSolve Studio의 첫 번째 MVP 성공 기준인 “사용자가 원본 문제 이미지와 손풀이 이미지를 업로드할 수 있다”를 구현 가능한 수준으로 닫힌 설계로 정의하는 것이다.

이 milestone은 이미지 분석, candidate spec 생성, preview 렌더링, export를 구현하지 않는다. 오직 job에 image artifact를 안전하게 저장하고, 이후 pipeline이 참조할 수 있는 manifest를 만드는 데 집중한다.

## 2. 구현자가 임의로 결정하면 안 되는 원칙

아래 항목은 구현자가 변경하거나 임의로 해석하면 안 된다.

- 저장 backend는 local filesystem만 사용한다.
- 저장 root는 `Settings.storage_root`를 사용한다.
- 원본 업로드 파일은 절대 덮어쓰지 않는다.
- 동일 role 이미지를 다시 업로드하면 새 artifact를 추가하고 latest pointer만 갱신한다.
- 파일명은 사용자가 올린 파일명을 사용하지 않는다.
- manifest와 API response에는 absolute filesystem path를 노출하지 않는다.
- 이미지 허용 타입은 PNG와 JPEG만이다.
- MIME type과 magic bytes가 같은 타입을 가리켜야만 허용한다.
- 최대 파일 크기는 정확히 `10 * 1024 * 1024` bytes다.
- `POST /jobs/{job_id}/run`은 problem image와 teacher solution image가 모두 업로드되기 전에는 실행하지 않는다.
- 이 milestone에서 OpenAI API 호출, OCR, image generation, PNG/PDF export, web upload UI는 구현하지 않는다.

## 3. 변경 파일 목록

### 새로 만들 파일

- `apps/api/cleansolve_api/artifacts.py`
- `apps/api/tests/test_image_upload_api.py`

### 수정할 파일

- `apps/api/cleansolve_api/routes/jobs.py`
- `apps/api/tests/test_jobs_api.py`
- `README.md`
- `docs/product/mvp-roadmap.md`

### 수정하지 않을 파일

- `packages/ai/**`
- `packages/workflow/**`
- `packages/renderer/**`
- `apps/web/**`

이 milestone은 backend artifact storage milestone이므로 web UI와 workflow internals를 바꾸지 않는다. 단, `routes/jobs.py`에서 workflow 실행 전 image precondition만 추가한다.

## 4. 용어

### Image role

이미지 role은 정확히 두 개만 허용한다.

```python
ImageRole = Literal["problem", "teacher_solution"]
```

URL path에서는 teacher solution role을 `teacher-solution`으로 쓴다. Manifest 내부 값은 `teacher_solution`으로 쓴다.

### Artifact id

이미지 artifact id는 다음 형식을 사용한다.

```text
img_{uuid4_hex}
```

예:

```text
img_2fbd5d51cc8d490ba678716a3c581b2a
```

`uuid4_hex`는 Python `uuid4().hex`의 32자 lowercase hex 문자열이다.

### Job id

기존 형식을 유지한다.

```text
job_{uuid4_hex}
```

## 5. 저장 경로

`Settings.storage_root`의 기본값은 기존처럼 `var/jobs`다.

Job root:

```text
{storage_root}/{job_id}/
```

Manifest path:

```text
{storage_root}/{job_id}/manifest.json
```

Problem image artifact path:

```text
{storage_root}/{job_id}/artifacts/images/problem/{artifact_id}.{ext}
```

Teacher solution image artifact path:

```text
{storage_root}/{job_id}/artifacts/images/teacher_solution/{artifact_id}.{ext}
```

확장자 규칙:

| MIME type | Magic bytes | ext |
| --- | --- | --- |
| `image/png` | `89 50 4E 47 0D 0A 1A 0A` | `png` |
| `image/jpeg` | first three bytes `FF D8 FF` | `jpg` |

`teacher-solution`은 URL segment에만 사용한다. Directory와 JSON role에는 `teacher_solution`을 사용한다.

## 6. Manifest schema

`apps/api/cleansolve_api/artifacts.py`에 Pydantic model을 둔다.

### ImageArtifact

```python
class ImageArtifact(BaseModel):
    artifact_id: str
    role: Literal["problem", "teacher_solution"]
    mime_type: Literal["image/png", "image/jpeg"]
    extension: Literal["png", "jpg"]
    size_bytes: int
    sha256: str
    relative_path: str
    created_at: str
```

필드 규칙:

- `artifact_id`: `img_` prefix와 uuid hex를 가진다.
- `relative_path`: `{job_id}/artifacts/images/...`가 아니라 job root 기준 상대 경로다.
  - 예: `artifacts/images/problem/img_xxx.png`
- `created_at`: UTC ISO-8601 문자열이며 suffix는 `Z`다.
  - 예: `2026-06-14T07:30:00Z`
- `size_bytes`: 1 이상 `10485760` 이하
- `sha256`: lowercase hex digest 64자

### JobManifest

```python
class JobManifest(BaseModel):
    job_id: str
    status: Literal["CREATED", "APPROVED", "NEEDS_REVIEW", "FAILED"]
    created_at: str
    updated_at: str
    revision_attempts: int
    review_items: list[dict[str, Any]]
    image_artifacts: dict[Literal["problem", "teacher_solution"], list[ImageArtifact]]
    latest_image_artifact_ids: dict[Literal["problem", "teacher_solution"], str | None]
```

새 job의 초기 manifest는 정확히 아래 shape를 따른다.

```json
{
  "job_id": "job_<uuid>",
  "status": "CREATED",
  "created_at": "<utc-iso-z>",
  "updated_at": "<utc-iso-z>",
  "revision_attempts": 0,
  "review_items": [],
  "image_artifacts": {
    "problem": [],
    "teacher_solution": []
  },
  "latest_image_artifact_ids": {
    "problem": null,
    "teacher_solution": null
  }
}
```

## 7. API response schema

별도 `schemas.py` 파일은 만들지 않는다. M1에서는 response shape를 `artifacts.py`의 Pydantic model과 route-local helper로 구성한다.

### Job response

`POST /jobs`와 `GET /jobs/{job_id}`와 `POST /jobs/{job_id}/run`은 같은 job response shape를 반환한다.

```json
{
  "job_id": "job_<uuid>",
  "status": "CREATED",
  "revision_attempts": 0,
  "review_items": [],
  "latest_image_artifact_ids": {
    "problem": null,
    "teacher_solution": null
  },
  "image_artifacts": {
    "problem": [],
    "teacher_solution": []
  }
}
```

`created_at`, `updated_at`, local path는 job response에 포함하지 않는다. Timestamp는 manifest 내부에만 저장한다.

### Image upload response

`POST /jobs/{job_id}/images/problem`과 `POST /jobs/{job_id}/images/teacher-solution`은 아래 shape를 반환한다.

```json
{
  "job_id": "job_<uuid>",
  "role": "problem",
  "artifact": {
    "artifact_id": "img_<uuid>",
    "role": "problem",
    "mime_type": "image/png",
    "extension": "png",
    "size_bytes": 68,
    "sha256": "<64-lowercase-hex>",
    "relative_path": "artifacts/images/problem/img_<uuid>.png",
    "created_at": "<utc-iso-z>"
  },
  "latest_image_artifact_ids": {
    "problem": "img_<uuid>",
    "teacher_solution": null
  }
}
```

`relative_path`는 API response에 포함해도 된다. Absolute path는 포함하면 안 된다.

### Review items response

기존 shape를 유지한다.

```json
{
  "items": []
}
```

M1은 review item filtering logic을 바꾸지 않는다.

## 8. API endpoints

### POST /jobs

동작:

1. `job_id = "job_" + uuid4().hex` 생성
2. `{storage_root}/{job_id}` directory 생성
3. `manifest.json` 생성
4. job response 반환

Status:

- success: `201 Created`

오류:

- storage root 생성 실패: `500 Internal Server Error`

### GET /jobs/{job_id}

동작:

1. manifest를 읽는다.
2. job response를 반환한다.

Status:

- success: `200 OK`
- unknown job: `404 Not Found`

### POST /jobs/{job_id}/images/problem

Multipart field:

```text
file
```

동작:

1. job manifest 존재 확인
2. multipart field `file`을 받음
3. byte stream을 읽으며 size limit 확인
4. empty file 확인
5. `UploadFile.content_type` 확인
6. magic bytes 확인
7. `artifact_id` 생성
8. role directory 생성
9. temp file에 저장
10. sha256 계산
11. temp file을 final path로 atomic replace
12. manifest `image_artifacts.problem`에 append
13. manifest `latest_image_artifact_ids.problem` 갱신
14. manifest `updated_at` 갱신
15. upload response 반환

Status:

- success: `201 Created`
- unknown job: `404 Not Found`
- missing multipart file: FastAPI 기본 `422 Unprocessable Entity`
- unsupported MIME type: `415 Unsupported Media Type`
- MIME/magic mismatch: `400 Bad Request`
- empty file: `400 Bad Request`
- file larger than 10MB: `413 Payload Too Large`

### POST /jobs/{job_id}/images/teacher-solution

`problem` endpoint와 동일하다. 단 role은 `teacher_solution`, directory는 `teacher_solution`이다.

### POST /jobs/{job_id}/run

M1에서 precondition을 추가한다.

동작:

1. manifest 존재 확인
2. `latest_image_artifact_ids.problem`이 `None`이면 missing role에 `problem` 추가
3. `latest_image_artifact_ids.teacher_solution`이 `None`이면 missing role에 `teacher_solution` 추가
4. missing role이 하나라도 있으면 workflow를 실행하지 않고 `409 Conflict`
5. 둘 다 있으면 기존 `run_mock_workflow(job_id=job_id)` 실행
6. manifest `status`, `revision_attempts`, `review_items`, `updated_at` 갱신
7. job response 반환

Status:

- success: `200 OK`
- unknown job: `404 Not Found`
- missing required image: `409 Conflict`

## 9. Error response shape

M1에서 새로 추가하는 명시적 오류는 아래 shape를 사용한다.

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "한국어 오류 메시지",
    "fields": {}
  }
}
```

Error code 목록:

| Code | HTTP status | fields |
| --- | --- | --- |
| `JOB_NOT_FOUND` | 404 | `{"job_id": "<job_id>"}` |
| `UNSUPPORTED_IMAGE_TYPE` | 415 | `{"allowed": ["image/png", "image/jpeg"], "received": "<mime>"}` |
| `INVALID_IMAGE_BYTES` | 400 | `{"reason": "mime_magic_mismatch"}` |
| `EMPTY_IMAGE` | 400 | `{}` |
| `IMAGE_TOO_LARGE` | 413 | `{"max_size_bytes": 10485760}` |
| `MISSING_REQUIRED_IMAGES` | 409 | `{"missing_roles": ["problem", "teacher_solution"]}` |
| `STORAGE_WRITE_FAILED` | 500 | `{}` |

기존 unknown job 오류 문자열 `"Job not found"`는 사용하지 않는다. M1에서 unknown job은 `JOB_NOT_FOUND` shape로 바꾼다.

한국어 message 고정값:

| Code | message |
| --- | --- |
| `JOB_NOT_FOUND` | `작업을 찾을 수 없습니다.` |
| `UNSUPPORTED_IMAGE_TYPE` | `지원하지 않는 이미지 형식입니다.` |
| `INVALID_IMAGE_BYTES` | `이미지 파일 내용이 MIME 형식과 일치하지 않습니다.` |
| `EMPTY_IMAGE` | `빈 이미지 파일은 업로드할 수 없습니다.` |
| `IMAGE_TOO_LARGE` | `이미지 파일 크기가 허용 범위를 초과했습니다.` |
| `MISSING_REQUIRED_IMAGES` | `workflow 실행에 필요한 이미지가 아직 업로드되지 않았습니다.` |
| `STORAGE_WRITE_FAILED` | `이미지 artifact 저장에 실패했습니다.` |

## 10. Validation rules

### MIME validation

Allowed MIME values:

```python
ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg"}
```

`UploadFile.content_type`이 이 set에 없으면 `UNSUPPORTED_IMAGE_TYPE`.

### Magic byte validation

PNG:

```python
data.startswith(b"\x89PNG\r\n\x1a\n")
```

JPEG:

```python
data.startswith(b"\xff\xd8\xff")
```

MIME과 magic bytes가 일치하지 않으면 `INVALID_IMAGE_BYTES`.

### Size validation

상수:

```python
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
```

파일을 읽은 총 byte 수가 `MAX_IMAGE_UPLOAD_BYTES`보다 크면 즉시 `IMAGE_TOO_LARGE`.

구현은 한 번에 전체 파일을 무제한으로 읽으면 안 된다. `1024 * 1024` bytes chunk 단위로 읽는다.

### Empty validation

총 byte 수가 0이면 `EMPTY_IMAGE`.

## 11. LocalArtifactStore 상세

`apps/api/cleansolve_api/artifacts.py`에 `LocalArtifactStore`를 만든다.

Constructor:

```python
class LocalArtifactStore:
    def __init__(self, storage_root: Path):
        self.storage_root = storage_root
```

Public methods:

```python
def create_job(self, job_id: str) -> JobManifest
def get_job(self, job_id: str) -> JobManifest
def save_manifest(self, manifest: JobManifest) -> None
def save_image(self, job_id: str, role: ImageRole, upload: UploadFile) -> tuple[JobManifest, ImageArtifact]
def update_after_run(self, job_id: str, status: str, revision_attempts: int, review_items: list[dict[str, Any]]) -> JobManifest
```

Private helper names:

```python
def _job_root(self, job_id: str) -> Path
def _manifest_path(self, job_id: str) -> Path
def _role_directory(self, job_id: str, role: ImageRole) -> Path
def _utc_now() -> str
def _new_job_id() -> str
def _new_artifact_id() -> str
def _detect_magic_type(data_prefix: bytes) -> str | None
def _error(code: str, status_code: int, fields: dict[str, Any] | None = None) -> HTTPException
```

`_utc_now()` format:

```python
datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

Manifest JSON serialization:

- `manifest.model_dump(mode="json")` 사용
- `json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True)` 사용
- UTF-8로 저장

Atomic write:

- manifest 저장은 같은 directory에 `manifest.json.tmp`를 쓴 뒤 `Path.replace()`로 교체한다.
- image 저장은 final role directory에 `{artifact_id}.{ext}.tmp`를 쓴 뒤 final path로 `Path.replace()`한다.
- 실패 시 tmp file이 남을 수 있으나 final artifact file과 manifest는 불완전 상태로 갱신하면 안 된다.

## 12. routes/jobs.py 변경 상세

`routes/jobs.py`는 아래 구조를 따른다.

Imports:

```python
from fastapi import APIRouter, File, UploadFile, status
from cleansolve_api.artifacts import ImageRole, LocalArtifactStore
from cleansolve_api.settings import settings
```

Store helper:

```python
def _store() -> LocalArtifactStore:
    return LocalArtifactStore(settings.storage_root)
```

Endpoints:

```python
@router.post("", status_code=status.HTTP_201_CREATED)
def create_job() -> dict[str, object]:
    ...

@router.post("/{job_id}/images/problem", status_code=status.HTTP_201_CREATED)
async def upload_problem_image(job_id: str, file: UploadFile = File(...)) -> dict[str, object]:
    ...

@router.post("/{job_id}/images/teacher-solution", status_code=status.HTTP_201_CREATED)
async def upload_teacher_solution_image(job_id: str, file: UploadFile = File(...)) -> dict[str, object]:
    ...
```

`create_job()`은 기존 `_jobs` dict를 사용하지 않는다. `_jobs` 전역 변수는 제거한다.

기존 tests가 `_jobs`를 import하는 구조는 M1에서 삭제한다.

## 13. Test design

새 테스트 파일:

```text
apps/api/tests/test_image_upload_api.py
```

기존 테스트 파일 수정:

```text
apps/api/tests/test_jobs_api.py
```

### Test fixture

각 API test는 독립 temp storage root를 사용한다.

Fixture 이름:

```python
@pytest.fixture(autouse=True)
def isolated_storage_root(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs.settings, "storage_root", tmp_path / "jobs")
```

`jobs`는 `from cleansolve_api.routes import jobs`로 import한다.

### Minimal image bytes

테스트에서 사용할 PNG bytes:

```python
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
```

테스트에서 사용할 JPEG bytes:

```python
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 16
```

실제 이미지 decode는 하지 않는다. M1 validation은 MIME/magic byte contract만 검증한다.

### Required tests in `test_image_upload_api.py`

1. `test_upload_problem_png_persists_artifact_and_manifest`
   - create job
   - upload problem PNG with field `file`
   - assert `201`
   - assert role `problem`
   - assert artifact mime/ext/size/sha256
   - assert relative_path starts with `artifacts/images/problem/`
   - assert file exists under storage root
   - assert manifest latest problem id equals artifact id

2. `test_upload_teacher_solution_jpeg_persists_artifact_and_manifest`
   - role `teacher_solution`
   - endpoint path uses `teacher-solution`
   - directory uses `teacher_solution`
   - ext is `jpg`

3. `test_reupload_same_role_appends_artifact_without_overwriting_previous_file`
   - upload two problem images
   - assert two artifact records in manifest
   - assert both files exist
   - assert latest points to second artifact

4. `test_upload_unknown_job_returns_structured_404`
   - endpoint returns `JOB_NOT_FOUND`

5. `test_upload_rejects_unsupported_mime_type`
   - content type `image/gif`
   - PNG-looking bytes are still rejected because MIME is unsupported
   - status `415`

6. `test_upload_rejects_mime_magic_mismatch`
   - content type `image/png`
   - JPEG bytes
   - status `400`
   - code `INVALID_IMAGE_BYTES`

7. `test_upload_rejects_empty_file`
   - content type `image/png`
   - empty bytes
   - status `400`
   - code `EMPTY_IMAGE`

8. `test_upload_rejects_oversized_file`
   - content type `image/png`
   - bytes are PNG header plus enough bytes to exceed `10 * 1024 * 1024`
   - status `413`
   - code `IMAGE_TOO_LARGE`

9. `test_job_response_does_not_expose_absolute_paths_or_original_filename`
   - upload with filename `teacher-private-name.png`
   - `GET /jobs/{job_id}` response must not contain `/Users/`, temp root string, or `teacher-private-name`

10. `test_run_requires_both_problem_and_teacher_solution_images`
    - create job
    - upload only problem image
    - run returns `409`
    - code `MISSING_REQUIRED_IMAGES`
    - missing role is exactly `["teacher_solution"]`

11. `test_run_succeeds_after_both_required_images_are_uploaded`
    - create job
    - upload problem and teacher solution
    - run returns `200`
    - status is `APPROVED`
    - revision attempts is `1`

### Required updates in `test_jobs_api.py`

- Remove `_jobs` import.
- Remove `clear_jobs` fixture.
- Add the same `isolated_storage_root` fixture directly in `test_jobs_api.py`; do not create `conftest.py` in M1.
- Existing `test_create_job_and_run_mock_workflow` must upload both images before calling `/run`.
- Unknown job tests must assert structured `JOB_NOT_FOUND` detail.
- Review items before run remains `{"items": []}`.
- Settings env file tests remain unchanged.

## 14. Documentation updates

### README.md

Add a short subsection under local verification or API usage:

```markdown
## 로컬 이미지 업로드 흐름

1. `POST /jobs`로 job을 만든다.
2. `POST /jobs/{job_id}/images/problem`에 multipart field `file`로 원본 문제 이미지를 업로드한다.
3. `POST /jobs/{job_id}/images/teacher-solution`에 multipart field `file`로 선생님 손풀이 이미지를 업로드한다.
4. 두 이미지가 모두 업로드된 뒤 `POST /jobs/{job_id}/run`을 호출한다.
```

### docs/product/mvp-roadmap.md

M1 상태는 implementation이 끝난 뒤에만 바꾼다. Design spec 작성만으로는 M1 상태를 `Partial`로 바꾸지 않는다.

이번 M1 design spec 작업에서는 `docs/product/mvp-roadmap.md`에 아래 한 줄만 추가한다.

```markdown
상세 설계: [M1 Image Ingestion & Artifact Storage 상세 설계](../superpowers/specs/2026-06-14-image-ingestion-artifacts-design.md)
```

이 줄은 M1 섹션의 상태 바로 아래에 둔다.

## 15. Dependencies

`UploadFile = File(...)`를 쓰려면 multipart parser가 필요하다.

`pyproject.toml` dependencies에 아래를 추가한다.

```toml
"python-multipart",
```

M1 implementation plan은 dependency 추가를 명시해야 한다.

## 16. Out of scope

다음은 M1에서 구현하지 않는다.

- Web upload UI
- image preview UI
- OpenAI adapter 호출
- OCR
- candidate spec 생성 변경
- renderer 변경
- export endpoint
- public download endpoint
- object storage/S3
- virus scan
- image dimension extraction
- EXIF parsing/removal
- authentication/authorization
- rate limiting

## 17. Acceptance criteria

M1 implementation은 아래를 모두 만족해야 완료로 본다.

- `POST /jobs`가 manifest를 생성한다.
- `POST /jobs/{job_id}/images/problem`이 PNG/JPEG problem image artifact를 저장한다.
- `POST /jobs/{job_id}/images/teacher-solution`이 PNG/JPEG teacher solution image artifact를 저장한다.
- 같은 role 재업로드 시 이전 artifact file과 manifest record가 남는다.
- `GET /jobs/{job_id}`가 latest image artifact ids와 image artifact 목록을 반환한다.
- API response에 absolute path와 original filename이 없다.
- unsupported MIME, MIME/magic mismatch, empty file, oversized file, unknown job이 지정된 status/code로 실패한다.
- `/run`은 두 required image가 없으면 `409 MISSING_REQUIRED_IMAGES`를 반환한다.
- 두 required image가 있으면 기존 mock workflow가 실행된다.
- Python 전체 테스트가 통과한다.
- README류 문서는 한국어다.

## 18. 다음 단계

이 spec이 승인되면 다음 단계는 `superpowers:writing-plans`를 사용해 `docs/superpowers/plans/2026-06-14-image-ingestion-artifacts.md`를 작성하는 것이다.

Writing plan이 승인된 뒤, 코드 작업 착수 전에 사용자에게 실제 샘플 이미지 2장을 제공할지 확인한다.

필요한 샘플:

- 원본 문제 이미지 1장
- 같은 문제의 선생님 손풀이 이미지 1장

샘플이 없으면 plan에 포함된 synthetic PNG/JPEG fixture bytes로 구현을 시작한다.
