# M6 Export Foundation 상세 설계

작성일: 2026-06-17

## 1. 목적

M6의 목적은 승인된 job의 최신 candidate spec과 최신 deterministic render artifact를 참조해 export artifact를 생성, 저장, 조회, 다운로드할 수 있는 서버 기반을 만드는 것이다.

M6는 실제 OpenAI API를 호출하지 않는다. M6는 최종 상용 품질의 이미지 합성 엔진을 완성하지 않는다. 이번 milestone은 export artifact 계약, manifest 저장 구조, API error 계약, binary download 경로, fixture 기반 smoke test를 고정한다.

## 2. 범위

이번 milestone에서 구현한다.

- `POST /jobs/{job_id}/export`
- PNG export prototype
- export artifact model
- manifest export artifact 목록과 latest id
- export artifact 조회 API
- latest export 조회 API
- export artifact download API
- export precondition validation
- stale render/source guard
- 오래된 manifest default compatibility
- API tests
- renderer package의 deterministic PNG writer
- README의 export API 사용법 업데이트

이번 milestone에서 구현하지 않는다.

- PDF export 생성
- 최종 상용 품질의 원본 이미지 + overlay raster compositing
- browser/web export button
- review item resolve API
- `REVISION_REQUIRED` 또는 unresolved review item이 있는 job의 export 허용
- OpenAI 재생성 또는 OpenAI image model 호출
- 사용자가 export 해상도, 배경색, crop 영역을 선택하는 기능
- batch export

## 3. Branch 기준

M6 작업 브랜치는 `origin/main` 기준 `feat/export-foundation`이다.

## 4. Export format 정책

M6에서 지원하는 요청 format은 `"png"` 하나다.

요청 body가 비어 있으면 format은 `"png"`로 간주한다.

```json
{}
```

명시 요청도 허용한다.

```json
{
  "format": "png"
}
```

`"pdf"`를 포함한 다른 format은 `UNSUPPORTED_EXPORT_FORMAT` 400으로 거부한다.

PDF는 M6에서 구현하지 않는다. 이 결정은 `docs/product/mvp-roadmap.md`의 M6 항목 중 “PDF export prototype 또는 명시적 deferred decision”을 충족하기 위한 deferred decision이다.

## 5. PNG export prototype 정책

M6 PNG export prototype은 `packages/renderer/cleansolve_renderer/export_png.py`에 구현한다.

### 5.1 함수 계약

```py
def render_export_png(
    *,
    width: int,
    height: int,
    svg: str,
    metadata: dict[str, str],
) -> bytes:
```

입력 규칙:

- `width`, `height`는 positive integer다.
- `svg`는 latest render artifact에서 읽은 SVG 문자열이다.
- `metadata`는 ASCII key와 UTF-8 string value를 가진다.

출력 규칙:

- 반환값은 valid PNG bytes다.
- PNG color type은 RGB truecolor다.
- bit depth는 8이다.
- 이미지 픽셀은 흰색 배경이다.
- PNG에는 아래 `tEXt` chunk를 포함한다.
  - `CleanSolve-Export-Version`: `m6-png-prototype-v1`
  - `CleanSolve-SVG-SHA256`: SVG UTF-8 bytes의 SHA-256 hex
  - `CleanSolve-Source`: `deterministic-overlay-svg`
- caller가 전달한 metadata는 위 chunk 뒤에 deterministic key sort 순서로 추가한다.
- 같은 입력은 byte-for-byte 동일한 PNG bytes를 만든다.
- PNG row filter byte는 모든 row에서 `0`이다.
- zlib compression level은 `9`다.

M6 PNG prototype은 SVG primitive를 rasterize하지 않는다. 대신 export artifact가 latest render artifact와 candidate spec artifact를 참조하고, PNG metadata가 SVG checksum을 포함한다. 실제 visual compositing은 M8 이후 export quality milestone에서 다룬다.

### 5.2 파일 책임

`packages/renderer/cleansolve_renderer/export_png.py`

- PNG chunk 생성
- PNG CRC 계산
- IHDR/IDAT/IEND 작성
- `tEXt` chunk 작성
- 입력 검증

`packages/renderer/tests/test_export_png.py`

- PNG signature, IHDR width/height, tEXt chunk, deterministic bytes를 검증한다.

## 6. Export artifact 계약

### 6.1 Type aliases

`apps/api/cleansolve_api/artifacts.py`에 추가한다.

```py
ExportFormat = Literal["png"]
ExportMimeType = Literal["image/png"]
```

### 6.2 ExportArtifact model

```py
class ExportArtifact(BaseModel):
    artifact_id: str
    format: ExportFormat
    mime_type: ExportMimeType
    relative_path: str
    size_bytes: int
    sha256: str
    created_at: str
    candidate_spec_artifact_id: str
    render_artifact_id: str
    source_image_artifact_ids: dict[ImageRole, str]
```

`artifact_id` prefix는 `export_`다.

저장 경로:

```text
artifacts/exports/{artifact_id}.png
```

### 6.3 JobManifest 확장

`JobManifest`에 아래 필드를 추가한다.

```py
export_artifacts: list[ExportArtifact]
latest_export_artifact_id: str | None
```

기존 manifest JSON에는 해당 필드가 없으므로 default가 필요하다.

### 6.4 job response 확장

`job_response(manifest)`는 아래 필드를 포함한다.

```json
{
  "export_artifacts": [],
  "latest_export_artifact_id": null
}
```

기존 응답 필드는 제거하지 않는다.

## 7. Export preconditions

`POST /jobs/{job_id}/export`는 아래 조건을 순서대로 검증한다.

1. job id가 유효하고 manifest가 존재한다.
2. 요청 format이 `"png"` 또는 omitted인지 검증한다.
3. `manifest.status == "APPROVED"`인지 검증한다.
4. latest candidate spec artifact id가 존재하는지 검증한다.
5. latest render artifact id가 존재하는지 검증한다.
6. latest render artifact metadata가 manifest에 존재하는지 검증한다.
7. latest render artifact file이 존재하는지 검증한다.
8. latest render artifact의 `candidate_spec_artifact_id`가 latest candidate spec artifact id와 같은지 검증한다.
9. latest render artifact의 `source_image_artifact_ids`가 manifest latest image ids와 같은지 검증한다.
10. PNG bytes를 생성한다.
11. store lock 안에서 8, 9번을 다시 검증한다.
12. export artifact file과 manifest를 저장한다.
13. response를 반환한다.

`review-resolved` 상태는 아직 없다. M6에서는 `APPROVED` job만 export할 수 있다.

## 8. Store helper 설계

`LocalArtifactStore`에 다음 helper를 추가한다.

### 8.1 `latest_render_artifact`

입력:

- `job_id`

동작:

- latest render artifact id가 없으면 `render_artifact_not_found_error()`를 발생시킨다.
- manifest에 matching render artifact metadata가 없으면 같은 error를 발생시킨다.
- render SVG 파일이 없으면 같은 error를 발생시킨다.

반환:

```py
tuple[JobManifest, RenderArtifact, str]
```

세 번째 값은 SVG 문자열이다.

### 8.2 `save_export_artifact`

입력:

- `job_id`
- `png_bytes`
- `candidate_spec_artifact_id`
- `render_artifact_id`
- `source_image_artifact_ids`

동작:

- job lock 안에서 manifest를 다시 읽는다.
- latest candidate spec artifact id가 입력 `candidate_spec_artifact_id`와 다르면 `EXPORT_SOURCE_CHANGED`를 발생시킨다.
- latest render artifact id가 입력 `render_artifact_id`와 다르면 `EXPORT_SOURCE_CHANGED`를 발생시킨다.
- manifest latest image ids가 입력 `source_image_artifact_ids`와 다르면 `EXPORT_SOURCE_CHANGED`를 발생시킨다.
- PNG bytes를 `artifacts/exports/{artifact_id}.png`에 temp file 후 replace로 저장한다.
- `export_artifacts`에 metadata를 append한다.
- `latest_export_artifact_id`를 갱신한다.
- `updated_at`을 갱신한다.

반환:

```py
tuple[JobManifest, ExportArtifact]
```

### 8.3 `export_artifacts_response`

입력:

- `job_id`

반환:

```json
{
  "job_id": "job_...",
  "export_artifacts": [],
  "latest_export_artifact_id": null
}
```

### 8.4 `latest_export_response`

입력:

- `job_id`

동작:

- latest export artifact가 없으면 `EXPORT_ARTIFACT_NOT_FOUND`를 발생시킨다.
- export file이 없으면 같은 error를 발생시킨다.

반환:

```json
{
  "job_id": "job_...",
  "artifact": {}
}
```

### 8.5 `export_download`

입력:

- `job_id`
- `export_id`

동작:

- manifest에서 matching export artifact metadata를 찾는다.
- 없으면 `EXPORT_ARTIFACT_NOT_FOUND`.
- export file이 없으면 `EXPORT_ARTIFACT_NOT_FOUND`.

반환:

```py
tuple[ExportArtifact, Path]
```

Route layer는 이 반환값으로 `FileResponse`를 만든다.

## 9. API 계약

### 9.1 `POST /jobs/{job_id}/export`

Request:

```json
{
  "format": "png"
}
```

`format` omitted이면 `"png"`로 처리한다.

Success `200`:

```json
{
  "job_id": "job_...",
  "artifact": {
    "artifact_id": "export_...",
    "format": "png",
    "mime_type": "image/png",
    "relative_path": "artifacts/exports/export_....png",
    "size_bytes": 1234,
    "sha256": "...",
    "created_at": "2026-06-17T00:00:00Z",
    "candidate_spec_artifact_id": "spec_...",
    "render_artifact_id": "render_...",
    "source_image_artifact_ids": {
      "problem": "img_...",
      "teacher_solution": "img_..."
    }
  },
  "latest_export_artifact_id": "export_..."
}
```

### 9.2 `GET /jobs/{job_id}/exports`

Success `200`:

```json
{
  "job_id": "job_...",
  "export_artifacts": [],
  "latest_export_artifact_id": null
}
```

### 9.3 `GET /jobs/{job_id}/exports/latest`

Success `200`:

```json
{
  "job_id": "job_...",
  "artifact": {}
}
```

### 9.4 `GET /jobs/{job_id}/exports/{export_id}/download`

Success `200`:

- Content-Type: `image/png`
- Content-Disposition filename: `{export_id}.png`
- Body: PNG bytes

Route must not expose absolute filesystem paths.

## 10. Error 계약

### `UNSUPPORTED_EXPORT_FORMAT`

- HTTP status: 400
- 조건: request format이 `"png"`가 아니다.
- message: `지원하지 않는 export 형식입니다.`
- fields:

```json
{
  "allowed": ["png"],
  "received": "pdf"
}
```

### `EXPORT_JOB_NOT_READY`

- HTTP status: 409
- 조건: job status가 `"APPROVED"`가 아니다.
- message: `승인된 job만 export할 수 있습니다.`
- fields:

```json
{
  "status": "NEEDS_REVIEW"
}
```

### `EXPORT_SPEC_NOT_READY`

- HTTP status: 409
- 조건: latest candidate spec artifact id가 없다.
- message: `export할 candidate spec이 아직 없습니다.`

### `EXPORT_RENDER_NOT_READY`

- HTTP status: 409
- 조건: latest render artifact가 없거나 latest render가 latest candidate spec과 연결되어 있지 않다.
- message: `export할 render artifact가 최신 상태가 아닙니다.`
- fields는 가능한 경우 아래를 포함한다.

```json
{
  "latest_candidate_spec_artifact_id": "spec_...",
  "render_candidate_spec_artifact_id": "spec_old"
}
```

### `EXPORT_SOURCE_CHANGED`

- HTTP status: 409
- 조건: export 생성 중 latest candidate spec, render, image source가 바뀌었다.
- message: `export 생성 중 입력 artifact가 변경되었습니다.`
- fields는 변경된 id를 포함한다.

### `EXPORT_ARTIFACT_NOT_FOUND`

- HTTP status: 404
- 조건: export artifact metadata 또는 file이 없다.
- message: `export artifact를 찾을 수 없습니다.`

## 11. API route 세부 동작

### 11.1 `POST /export`

1. request model을 parsing한다.
2. unsupported format이면 `UNSUPPORTED_EXPORT_FORMAT`.
3. manifest를 읽는다.
4. status가 `APPROVED`가 아니면 `EXPORT_JOB_NOT_READY`.
5. latest candidate spec artifact id가 없으면 `EXPORT_SPEC_NOT_READY`.
6. `latest_render_artifact`로 render metadata와 SVG를 읽는다.
7. render metadata의 candidate spec id가 latest candidate spec id와 다르면 `EXPORT_RENDER_NOT_READY`.
8. render metadata의 source image ids가 manifest latest image ids와 다르면 `EXPORT_SOURCE_CHANGED`.
9. candidate spec payload를 읽고 `CandidateSpec.model_validate`로 page width/height를 얻는다.
10. `render_export_png(width=spec.page.width, height=spec.page.height, svg=svg, metadata=...)`를 호출한다.
11. `save_export_artifact`로 저장한다.
12. response를 반환한다.

Metadata:

```py
{
    "CleanSolve-Job-ID": job_id,
    "CleanSolve-Candidate-Spec-Artifact-ID": candidate_spec_artifact_id,
    "CleanSolve-Render-Artifact-ID": render_artifact.artifact_id,
}
```

### 11.2 `GET /exports`

Store의 `export_artifacts_response`를 그대로 반환한다.

### 11.3 `GET /exports/latest`

Store의 `latest_export_response`를 그대로 반환한다.

### 11.4 `GET /exports/{export_id}/download`

Store의 `export_download` 결과로 `FileResponse`를 반환한다.

`media_type`은 `artifact.mime_type`이다.

`filename`은 `{artifact.artifact_id}.png`다.

## 12. Test 요구사항

### 12.1 Renderer tests

`packages/renderer/tests/test_export_png.py`

추가 테스트:

1. PNG signature가 `b"\x89PNG\r\n\x1a\n"`이다.
2. IHDR width/height가 입력값과 같다.
3. `CleanSolve-Export-Version`, `CleanSolve-SVG-SHA256`, caller metadata tEXt chunk가 포함된다.
4. 같은 입력은 같은 bytes를 만든다.
5. width 또는 height가 0이면 `ValueError`.

### 12.2 Store/API tests

`apps/api/tests/test_jobs_api.py`

추가 테스트:

1. old manifest JSON은 `export_artifacts=[]`, `latest_export_artifact_id=None` default를 가진다.
2. `POST /export` 전에 job이 `APPROVED`가 아니면 `EXPORT_JOB_NOT_READY`.
3. run 후 render 전 export는 `EXPORT_RENDER_NOT_READY`.
4. run 후 render 후 export는 PNG artifact를 저장한다.
5. export response artifact가 latest candidate spec, latest render, source image artifact ids를 참조한다.
6. `GET /exports`가 export 목록과 latest id를 반환한다.
7. `GET /exports/latest`가 latest export metadata를 반환한다.
8. `GET /exports/latest` before export는 `EXPORT_ARTIFACT_NOT_FOUND`.
9. `GET /exports/{export_id}/download`가 `image/png` body를 반환한다.
10. unknown export id download는 `EXPORT_ARTIFACT_NOT_FOUND`.
11. unsupported format `"pdf"`는 `UNSUPPORTED_EXPORT_FORMAT`.
12. latest render가 stale candidate spec artifact id를 참조하면 `EXPORT_RENDER_NOT_READY`.
13. `save_export_artifact`는 store lock 안에서 stale candidate spec/render/source를 거부한다.

### 12.3 Full verification

```bash
python -m pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
git diff --check
```

## 13. README 업데이트

`README.md`에 한국어로 “로컬 export 흐름”을 추가한다.

포함 내용:

1. job 생성
2. 이미지 업로드
3. run
4. render
5. export
6. latest export 조회
7. download

PDF는 M6에서 deferred라고 명시한다.

## 14. 완료 조건

M6는 다음을 모두 만족하면 Done이다.

- `POST /jobs/{job_id}/export`가 PNG export artifact를 생성한다.
- export artifact가 manifest에 append되고 latest id가 갱신된다.
- export artifact가 candidate spec artifact, render artifact, source image artifact ids를 참조한다.
- latest render가 latest candidate spec과 맞지 않으면 export가 거부된다.
- export 생성 중 source/candidate/render가 바뀌면 store-level guard가 거부한다.
- `GET /jobs/{job_id}/exports`가 export 목록을 반환한다.
- `GET /jobs/{job_id}/exports/latest`가 latest metadata를 반환한다.
- `GET /jobs/{job_id}/exports/{export_id}/download`가 PNG bytes를 반환한다.
- PDF는 unsupported format으로 거부되고 README/spec에 deferred가 명시된다.
- API response와 README는 absolute filesystem path를 노출하지 않는다.
- 모든 테스트와 build가 통과한다.
