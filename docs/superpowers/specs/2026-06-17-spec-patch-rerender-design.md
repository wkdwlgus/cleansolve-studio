# M5 Spec Patch & Deterministic Re-render 상세 설계

작성일: 2026-06-17

## 1. 목적

M5의 목적은 사용자가 웹에서 수행한 제한된 수정사항을 서버에 candidate spec patch로 저장하고, 수정된 candidate spec을 deterministic renderer로 다시 렌더링해 최신 SVG preview artifact로 저장/조회할 수 있게 만드는 것이다.

M5는 OpenAI API를 호출하지 않는다. 모든 수정은 candidate spec JSON에 대한 allowlist 기반 patch이며, preview 갱신은 `cleansolve_renderer.overlay.render_overlay_svg`를 사용하는 deterministic SVG 렌더링이다.

## 2. 범위

이번 milestone에서 구현한다.

- `PATCH /jobs/{job_id}/spec`
- patch request/response model
- patch allowlist validation
- stale spec version conflict 처리
- candidate spec version 증가
- element `revision_history` 기록
- patched candidate spec artifact 저장
- patched validation report artifact 저장
- `POST /jobs/{job_id}/render`
- rendered SVG preview artifact 저장
- `GET /jobs/{job_id}/rendered-preview`
- web edit controls 최소 구현
- web patch 저장 후 server render 재조회
- API/web tests

이번 milestone에서 구현하지 않는다.

- element 추가/삭제
- freehand stroke point 단위 편집
- review item resolve API
- 최종 PNG/PDF export
- OpenAI 재분석/재생성
- 여러 patch를 한 요청에 batch 적용
- 범용 JSON Patch
- 완전한 벡터 에디터

## 3. Branch 기준

M5 작업 브랜치는 `origin/main` 기준 `feat/spec-patch-rerender`이다.

## 4. Patch API 계약

### 4.1 Endpoint

```http
PATCH /jobs/{job_id}/spec
Content-Type: application/json
```

### 4.2 Request body

```json
{
  "client_spec_version": 1,
  "element_id": "el_freehand_dimension_001",
  "operation": "update_element",
  "changes": {
    "geometry.target_anchor_end": [540, 850],
    "label": "1",
    "color": "red"
  }
}
```

필드 의미:

- `client_spec_version`
  - 사용자가 편집한 화면의 candidate spec version이다.
  - 서버 최신 candidate spec version과 다르면 patch를 거부한다.
- `element_id`
  - 수정 대상 element id.
- `operation`
  - M5에서는 반드시 `"update_element"`만 허용한다.
- `changes`
  - patch path와 값의 object.
  - key는 아래 allowlist에 있는 path만 허용한다.
  - 한 요청에는 하나의 element만 수정한다.

### 4.3 Response body

성공 시 `200`:

```json
{
  "job_id": "job_...",
  "candidate_spec": {
    "job_id": "job_...",
    "version": 2,
    "source_images": {},
    "style": {},
    "page": {},
    "regions": [],
    "elements": [],
    "uncertainties": []
  },
  "validation_report": {
    "report_id": "report_job_..._v2",
    "passed": true,
    "issues": []
  },
  "candidate_spec_artifact_id": "spec_...",
  "validation_report_artifact_id": "report_...",
  "latest_analysis_artifact_ids": {
    "candidate_spec": "spec_...",
    "validation_report": "report_...",
    "correction_plan": "correction_..."
  }
}
```

응답의 `candidate_spec`은 patch 적용 후 저장된 최신 payload다.

## 5. Patch allowlist

M5는 primitive별 허용 path만 수정한다.

### 5.1 공통 primitive path

아래 primitive는 `color`를 수정할 수 있다.

- `formula_line`
- `text_note`
- `highlight_line`
- `highlight_curve`
- `dimension_line`
- `dimension_curve`
- `freehand_dimension_marker`
- `arrow`
- `box`
- `circle`
- `point_label`
- `segment_label`

`color` 값은 non-empty string이어야 한다.

### 5.2 `formula_line`

허용 path:

- `text`
- `display_text`
- `geometry.anchor`
- `color`

값 조건:

- `text`, `display_text`: non-empty string
- `geometry.anchor`: page 내부 finite two-number point

### 5.3 `text_note`

허용 path:

- `text`
- `display_text`
- `geometry.anchor`
- `color`

값 조건은 `formula_line`과 같다.

### 5.4 `highlight_line`

허용 path:

- `geometry.start`
- `geometry.end`
- `color`

값 조건:

- `geometry.start`, `geometry.end`: page 내부 finite two-number point

### 5.5 `highlight_curve`

허용 path:

- `geometry.start`
- `geometry.end`
- `geometry.control_points`
- `color`

값 조건:

- start/end: page 내부 finite two-number point
- control_points: point list, 길이 1 또는 2, 모든 point는 page 내부

### 5.6 `arrow`

허용 path:

- `geometry.start`
- `geometry.end`
- `color`

값 조건은 `highlight_line`과 같다.

### 5.7 `box`

허용 path:

- `bbox`
- `geometry.bbox`
- `color`

값 조건:

- bbox: `[x, y, width, height]`
- x/y/width/height는 finite number
- width/height는 0보다 커야 한다.
- bbox 영역은 page 내부에 있어야 한다.

### 5.8 `circle`

허용 path:

- `geometry.center`
- `geometry.radius`
- `geometry.bbox`
- `bbox`
- `color`

값 조건:

- center: page 내부 finite two-number point
- radius: positive finite number
- bbox: box 규칙과 동일

### 5.9 `point_label`

허용 path:

- `geometry.point`
- `geometry.label_anchor`
- `label`
- `color`

값 조건:

- point/label_anchor: page 내부 finite two-number point
- label: non-empty string

### 5.10 `segment_label`

허용 path:

- `geometry.start`
- `geometry.end`
- `geometry.label_anchor`
- `label`
- `color`

값 조건:

- start/end/label_anchor: page 내부 finite two-number point
- label: non-empty string

### 5.11 `dimension_line`

허용 path:

- `geometry.target_anchor_start`
- `geometry.target_anchor_end`
- `geometry.visible_start`
- `geometry.visible_end`
- `geometry.label_anchor`
- `label`
- `color`

값 조건:

- 모든 point: page 내부 finite two-number point
- label: non-empty string

### 5.12 `dimension_curve`

허용 path:

- `geometry.target_anchor_start`
- `geometry.target_anchor_end`
- `geometry.visible_start`
- `geometry.visible_end`
- `geometry.control_points`
- `geometry.curve_control_points`
- `geometry.label_anchor`
- `label`
- `color`

값 조건:

- point path: page 내부 finite two-number point
- control point list: 길이 1 또는 2, 모든 point는 page 내부
- label: non-empty string

### 5.13 `freehand_dimension_marker`

허용 path:

- `geometry.target_anchor_start`
- `geometry.target_anchor_end`
- `geometry.label_anchor`
- `label`
- `color`

값 조건:

- point path: page 내부 finite two-number point
- label: non-empty string

M5에서는 `visible_strokes`와 stroke point 편집을 허용하지 않는다.

## 6. Patch 적용 규칙

1. job id를 검증한다.
2. 최신 candidate spec artifact가 없으면 `SPEC_NOT_READY`를 반환한다.
3. request body를 검증한다.
4. 서버 최신 spec version과 `client_spec_version`을 비교한다.
5. version이 다르면 `SPEC_VERSION_CONFLICT`를 반환한다.
6. target element를 찾는다.
7. element가 없으면 `SPEC_PATCH_REJECTED`를 반환한다.
8. operation이 `"update_element"`가 아니면 `SPEC_PATCH_REJECTED`를 반환한다.
9. 모든 change path/value를 allowlist와 value validator로 검증한다.
10. 모든 change가 유효한 경우에만 candidate spec deep copy에 적용한다.
11. spec version을 1 증가시킨다.
12. 수정된 element의 `revision_history`에 patch 기록을 append한다.
13. `validate_candidate_spec`을 실행한다.
14. validation이 실패하면 기존 manifest/artifact를 변경하지 않고 `SPEC_PATCH_REJECTED`를 반환한다.
15. validation이 성공하면 새 candidate spec artifact와 validation report artifact를 저장한다.
16. manifest의 latest candidate spec/validation report artifact id를 갱신한다.
17. correction plan latest id는 변경하지 않는다.
18. response를 반환한다.

## 7. revision_history 계약

Patch 적용 시 수정된 element에 아래 기록을 append한다.

```json
{
  "revision_id": "user_patch_v2",
  "source": "user_patch",
  "client_spec_version": 1,
  "result_spec_version": 2,
  "operation": "update_element",
  "changes": {
    "geometry.target_anchor_end": [540, 850]
  }
}
```

`revision_id`는 deterministic하게 `user_patch_v{result_spec_version}`로 만든다.

## 8. Render artifact 계약

### 8.1 Manifest model

`JobManifest`에 아래 필드를 추가한다.

```py
render_artifacts: list[RenderArtifact]
latest_render_artifact_id: str | None
```

기존 manifest JSON에는 해당 필드가 없으므로 default가 필요하다.

### 8.2 RenderArtifact model

```py
class RenderArtifact(BaseModel):
    artifact_id: str
    type: Literal["overlay_svg"]
    relative_path: str
    size_bytes: int
    sha256: str
    created_at: str
    candidate_spec_artifact_id: str
    source_image_artifact_ids: dict[ImageRole, str]
```

artifact id prefix는 `render_`다.

저장 경로:

```text
artifacts/renders/{artifact_id}.svg
```

### 8.3 `POST /jobs/{job_id}/render`

동작:

1. 최신 candidate spec artifact를 읽는다.
2. 최신 candidate spec artifact id를 확인한다.
3. `CandidateSpec.model_validate`로 payload를 검증한다.
4. `render_overlay_svg(spec)`를 실행한다.
5. SVG 문자열을 render artifact로 저장한다.
6. manifest의 `render_artifacts`에 append한다.
7. manifest의 `latest_render_artifact_id`를 갱신한다.
8. JSON response를 반환한다.

성공 응답:

```json
{
  "job_id": "job_...",
  "artifact": {
    "artifact_id": "render_...",
    "type": "overlay_svg",
    "relative_path": "artifacts/renders/render_....svg",
    "size_bytes": 1234,
    "sha256": "...",
    "created_at": "...",
    "candidate_spec_artifact_id": "spec_...",
    "source_image_artifact_ids": {}
  },
  "svg": "<svg ...></svg>"
}
```

### 8.4 `GET /jobs/{job_id}/rendered-preview`

최신 rendered preview SVG를 반환한다.

성공 응답은 `POST /render`와 같은 shape다.

최신 render artifact가 없으면 `RENDER_ARTIFACT_NOT_FOUND` 404를 반환한다.

## 9. Error 계약

### `SPEC_NOT_READY`

- HTTP status: 409
- 조건: latest candidate spec artifact id가 없다.
- message: `수정할 candidate spec이 아직 없습니다.`

### `SPEC_VERSION_CONFLICT`

- HTTP status: 409
- 조건: `client_spec_version`이 서버 최신 spec version과 다르다.
- fields:

```json
{
  "client_spec_version": 1,
  "server_spec_version": 2
}
```

- message: `화면의 spec version이 최신이 아닙니다.`

### `SPEC_PATCH_REJECTED`

- HTTP status: 400
- 조건: operation/path/value/element가 허용되지 않거나 patch 적용 후 validation이 실패한다.
- fields는 가능한 경우 아래 중 하나를 포함한다.

```json
{
  "element_id": "el_...",
  "path": "geometry.unknown",
  "reason": "path_not_allowed"
}
```

- message: `허용되지 않는 spec 수정입니다.`

### `RENDER_ARTIFACT_NOT_FOUND`

- HTTP status: 404
- 조건: 최신 render artifact가 없다.
- message: `렌더링 preview artifact를 찾을 수 없습니다.`

## 10. Store helper 설계

`LocalArtifactStore`에 다음 helper를 추가한다.

### `save_spec_patch_outputs`

입력:

- `job_id`
- `candidate_spec_payload`
- `validation_report_payload`
- `source_image_artifact_ids`

동작:

- job lock 안에서 최신 manifest를 읽는다.
- candidate spec artifact를 쓴다.
- validation report artifact를 쓴다.
- `analysis_artifacts["candidate_spec"]`와 `analysis_artifacts["validation_report"]`에 append한다.
- latest id를 갱신한다.
- correction plan artifact 목록과 latest id는 그대로 둔다.
- manifest `updated_at`을 갱신한다.

### `save_render_artifact`

입력:

- `job_id`
- `svg`
- `candidate_spec_artifact_id`
- `source_image_artifact_ids`

동작:

- SVG를 UTF-8 bytes로 저장한다.
- render artifact metadata를 manifest에 append한다.
- latest render artifact id를 갱신한다.

### `rendered_preview_response`

입력:

- `job_id`

동작:

- latest render artifact metadata를 찾는다.
- SVG file을 읽는다.
- `{job_id, artifact, svg}` shape로 반환한다.

## 11. Web API client 계약

`apps/web/src/api/client.ts`에 다음을 추가한다.

### `patchCandidateSpec`

```ts
export interface SpecPatchRequest {
  client_spec_version: number;
  element_id: string;
  operation: 'update_element';
  changes: Record<string, unknown>;
}

export interface SpecPatchResponse {
  job_id: string;
  candidate_spec: CandidateSpecPreview;
  validation_report: {
    report_id: string;
    passed: boolean;
    issues: Array<Record<string, unknown>>;
  };
  candidate_spec_artifact_id: string;
  validation_report_artifact_id: string;
  latest_analysis_artifact_ids: Record<string, string | null>;
}
```

실패 메시지:

- `spec 수정사항을 저장하지 못했습니다.`

### `renderJobPreview`

`POST /jobs/{job_id}/render`

실패 메시지:

- `미리보기를 다시 렌더링하지 못했습니다.`

### `getRenderedPreview`

`GET /jobs/{job_id}/rendered-preview`

실패 메시지:

- `렌더링된 미리보기를 불러오지 못했습니다.`

## 12. Web UI 계약

M5 웹 UI는 M4 화면에 최소 editing surface만 추가한다.

### 12.1 ReviewPanel

각 review item row에 아래 버튼을 추가한다.

- label: `수정`
- 클릭 시 parent에 `onSelectItem(item)` callback을 호출한다.

ReviewPanel은 직접 API를 호출하지 않는다.

### 12.2 App edit state

App은 다음 state를 가진다.

- `selectedReviewItem`
- `editDraft`
- `editError`
- `editPhase`: `idle | saving | rendering`

### 12.3 지원 edit controls

M5에서는 `freehand_dimension_marker`와 `dimension_line`, `dimension_curve`의 target anchor 수정만 UI로 제공한다.

이유:

- 현재 mock workflow가 실제 review item으로 노출할 가능성이 있는 element는 dimension 계열이다.
- M5의 API는 더 넓은 allowlist를 갖지만 UI는 최소 surface로 시작한다.

표시 조건:

- selected item type이 `freehand_dimension_marker`, `dimension_line`, `dimension_curve` 중 하나다.
- candidate spec에 해당 `element_id`가 존재한다.
- element geometry에 `target_anchor_start`와 `target_anchor_end`가 point면 input 기본값으로 사용한다.

UI controls:

- 시작점 x
- 시작점 y
- 끝점 x
- 끝점 y
- 저장 후 미리보기 갱신 button

저장 요청 changes:

```json
{
  "geometry.target_anchor_start": [startX, startY],
  "geometry.target_anchor_end": [endX, endY]
}
```

### 12.4 Save flow

저장 button 클릭 시:

1. `patchCandidateSpec(jobId, request)`
2. 성공 response의 candidate spec을 web state에 반영한다.
3. `renderJobPreview(jobId)` 호출
4. 성공 response의 SVG를 web state에 저장한다.
5. candidate spec preview는 updated spec 기준으로 갱신된다.

M5에서 SVG 문자열은 디버그/검증 정보로 state에 보존하지만 canvas는 기존 candidate spec Konva preview를 계속 사용한다. 서버 SVG artifact 저장/조회는 API와 test로 검증한다.

### 12.5 Error UI

Patch 또는 render 실패 시:

- 한국어 오류를 edit panel 안에 표시한다.
- 기존 candidate spec과 preview state는 변경하지 않는다.

## 13. Test 요구사항

### 13.1 API tests

`apps/api/tests/test_jobs_api.py`

추가 테스트:

1. run 후 `PATCH /spec`이 allowed path를 적용하고 version을 증가시킨다.
2. patch 후 candidate spec artifact와 validation report artifact가 append된다.
3. patched element revision_history에 user_patch 기록이 남는다.
4. stale `client_spec_version`은 `SPEC_VERSION_CONFLICT` 409.
5. disallowed path는 `SPEC_PATCH_REJECTED` 400이고 기존 latest spec은 바뀌지 않는다.
6. run 전 patch는 `SPEC_NOT_READY` 409.
7. `POST /render`가 SVG render artifact를 저장한다.
8. `GET /rendered-preview`가 최신 SVG를 반환한다.
9. render 전 `GET /rendered-preview`는 `RENDER_ARTIFACT_NOT_FOUND` 404.

### 13.2 Store tests

`apps/api/tests/test_jobs_api.py` 또는 별도 store test에서 old manifest default를 확인한다.

- 오래된 manifest는 `render_artifacts=[]`, `latest_render_artifact_id=None`으로 읽힌다.

### 13.3 Web tests

`apps/web/src/api/client.test.ts`

- `patchCandidateSpec`가 `PATCH /jobs/{job_id}/spec`으로 JSON body를 보낸다.
- `renderJobPreview`가 `POST /jobs/{job_id}/render`를 호출한다.
- 실패 시 한국어 오류를 throw한다.

`apps/web/src/editor/reviewHelpers.test.ts` 또는 새 test:

- dimension review item 선택 시 target anchor draft를 만든다.
- unsupported selected item은 draft를 만들지 않는다.

### 13.4 Full verification

```bash
npm --prefix apps/web test
npm --prefix apps/web run build
python -m pytest -q
git diff --check
```

## 14. 완료 조건

M5는 다음을 모두 만족하면 Done이다.

- `PATCH /jobs/{job_id}/spec`가 allowlist 기반 patch를 저장한다.
- patch 성공 시 spec version이 증가한다.
- patch 성공 시 revision_history가 기록된다.
- invalid patch는 기존 latest spec을 바꾸지 않는다.
- `POST /jobs/{job_id}/render`가 SVG preview artifact를 저장한다.
- `GET /jobs/{job_id}/rendered-preview`가 최신 SVG를 반환한다.
- 웹에서 review item을 선택해 target anchor를 수정하고 저장할 수 있다.
- 저장 후 candidate spec preview가 갱신된다.
- M6 export, M7 OpenAI adapter, 범용 JSON Patch는 구현하지 않는다.
- 모든 테스트와 build가 통과한다.
