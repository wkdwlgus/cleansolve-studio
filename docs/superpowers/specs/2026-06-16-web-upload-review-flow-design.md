# M4 Web Upload-to-Review Flow 상세 설계

작성일: 2026-06-16

## 1. 목적

M4의 목적은 사용자가 웹 화면에서 원본 문제 이미지와 선생님 손풀이 이미지를 업로드하고, mock workflow를 실행한 뒤, candidate spec 기반 preview와 사람 검토 항목을 확인할 수 있게 만드는 것이다.

이 milestone은 서버에 새 렌더링 artifact를 저장하지 않는다. M3에서 확장한 deterministic renderer는 Python SVG renderer이고, M4 웹 preview는 API가 반환한 candidate spec을 React/Konva에서 직접 표시하는 클라이언트 preview다. 서버 side re-render artifact 저장은 M5에서 다룬다.

## 2. 범위

이번 milestone에서 구현한다.

- 웹 업로드 폼
- job 생성
- 문제 이미지 업로드
- 선생님 손풀이 이미지 업로드
- workflow 실행
- candidate spec 조회
- review items 조회
- candidate spec 기반 Konva preview
- 한국어 loading, empty, error 상태
- web unit test와 build 검증

이번 milestone에서 구현하지 않는다.

- spec patch 저장 API
- 사용자의 drag/edit 결과 server-side persistence
- `POST /jobs/{job_id}/render`
- PNG/PDF export
- 원본 이미지 binary download/display endpoint
- 실제 OpenAI adapter 호출
- 서버 저장 SVG preview artifact
- review item resolve API

## 3. API 계약

웹은 기존 API만 사용한다.

### 3.1 `POST /jobs`

입력 없음.

성공 응답:

```json
{
  "job_id": "job_...",
  "status": "CREATED",
  "revision_attempts": 0
}
```

웹 사용:

- 새 workflow 시작 시 가장 먼저 호출한다.
- 응답의 `job_id`를 이후 upload/run/fetch 호출에 사용한다.

### 3.2 `POST /jobs/{job_id}/images/problem`

입력:

- multipart form-data
- field name은 반드시 `file`
- value는 사용자가 선택한 problem image `File`

웹 사용:

- 원본 문제 이미지 업로드에 사용한다.
- 파일명은 UI에만 표시하고 API 응답에는 의존하지 않는다.

### 3.3 `POST /jobs/{job_id}/images/teacher-solution`

입력:

- multipart form-data
- field name은 반드시 `file`
- value는 사용자가 선택한 teacher solution image `File`

웹 사용:

- 선생님 손풀이 이미지 업로드에 사용한다.

### 3.4 `POST /jobs/{job_id}/run`

입력 없음.

웹 사용:

- 두 이미지 업로드가 성공한 뒤 호출한다.
- `status`와 `revision_attempts`를 workflow 결과로 저장한다.

### 3.5 `GET /jobs/{job_id}/candidate-spec`

웹 사용:

- run 성공 뒤 호출한다.
- 응답 payload를 `CandidateSpec`으로 normalize하지 않고 필요한 field만 읽는다.
- `page.width`, `page.height`, `elements`가 없거나 잘못된 경우 preview는 빈 상태로 표시한다. 앱 전체는 crash하지 않는다.

### 3.6 `GET /jobs/{job_id}/review-items`

웹 사용:

- run 성공 뒤 호출한다.
- 각 item은 `ReviewItem`으로 normalize한다.
- `requires_human_review`가 누락되면 `true`로 본다.
- `resolved`가 누락되면 `false`로 본다.

## 4. Web API Client 설계

파일: `apps/web/src/api/client.ts`

### 4.1 공개 타입

```ts
export type ImageRole = 'problem' | 'teacher_solution';

export interface CandidateSpecElement {
  id: string;
  type: PrimitiveType;
  color?: string | null;
  bbox?: number[];
  geometry?: Record<string, unknown>;
  style?: Record<string, unknown>;
  text?: string | null;
  display_text?: string | null;
  label?: string | null;
}

export interface CandidateSpecPreview {
  job_id: string;
  version: number;
  page: {
    width: number;
    height: number;
  };
  elements: CandidateSpecElement[];
}

export interface UploadToReviewInput {
  problemFile: File;
  teacherSolutionFile: File;
}

export interface UploadToReviewResult extends EditorJob {
  candidateSpec: CandidateSpecPreview | null;
}
```

### 4.2 공개 함수

`uploadImage(jobId, role, file, baseUrl, fetcher)`

- role이 `problem`이면 `/jobs/{job_id}/images/problem`으로 POST한다.
- role이 `teacher_solution`이면 `/jobs/{job_id}/images/teacher-solution`으로 POST한다.
- body는 `FormData`이고 `file` field를 append한다.
- 실패 시 `이미지를 업로드하지 못했습니다.`를 throw한다.

`getCandidateSpec(jobId, baseUrl, fetcher)`

- `/jobs/{job_id}/candidate-spec`를 GET한다.
- 실패 시 `미리보기 정보를 불러오지 못했습니다.`를 throw한다.

`runUploadToReviewWorkflow(input, options)`

순서:

1. `createJob`
2. `uploadImage(job_id, "problem", problemFile)`
3. `uploadImage(job_id, "teacher_solution", teacherSolutionFile)`
4. `runJob`
5. `getCandidateSpec`
6. `getReviewItems`

반환:

```ts
{
  jobId,
  status,
  revisionAttempts,
  reviewItems,
  candidateSpec
}
```

중간 단계가 실패하면 이후 단계는 실행하지 않고 한국어 error를 throw한다.

## 5. UI 상태 설계

파일: `apps/web/src/app/workflowState.ts`

### 5.1 상태 값

```ts
export type WorkflowPhase =
  | 'idle'
  | 'creating'
  | 'uploading'
  | 'running'
  | 'ready'
  | 'error';
```

### 5.2 상태 모델

```ts
export interface WorkflowViewState {
  phase: WorkflowPhase;
  job: UploadToReviewResult | null;
  errorMessage: string | null;
}
```

### 5.3 transition 함수

`nextWorkflowState(current, event)`는 pure function이다.

Event:

- `start`
- `uploading`
- `running`
- `ready`
- `error`
- `reset`

규칙:

- `start`는 `creating`으로 전환하고 기존 job/error를 지운다.
- `uploading`은 `uploading`으로 전환한다.
- `running`은 `running`으로 전환한다.
- `ready`는 `ready`로 전환하고 job을 저장한다.
- `error`는 `error`로 전환하고 errorMessage를 저장한다.
- `reset`은 `idle`로 전환하고 job/error를 지운다.

## 6. App UI 설계

파일: `apps/web/src/app/App.tsx`

### 6.1 첫 화면

첫 화면은 landing page가 아니라 실제 작업 화면이다.

표시 요소:

- topbar
  - 제품명
  - 활성 스타일: 기본 손글씨 스타일
  - job 상태 summary
- upload panel
  - 원본 문제 이미지 file input
  - 선생님 손풀이 이미지 file input
  - 실행 버튼
  - 다시 선택 버튼
- preview canvas
- review panel

### 6.2 file input

각 input:

- `accept="image/png,image/jpeg"`
- label은 한국어로 표시한다.
- 선택된 파일명이 있으면 label 아래에 표시한다.
- 두 파일이 모두 선택되지 않으면 실행 버튼은 disabled다.

### 6.3 submit behavior

submit 시:

1. 기본 form submit을 막는다.
2. 두 file이 모두 없으면 상태를 바꾸지 않는다.
3. `start` event
4. `runUploadToReviewWorkflow` 호출
5. 성공 시 `ready`
6. 실패 시 `error`

진행 중에는 실행 버튼 disabled다.

### 6.4 상태 문구

상태별 한국어 문구:

- `idle`: `이미지를 업로드해 작업을 시작하세요`
- `creating`: `작업을 생성하는 중`
- `uploading`: `이미지를 업로드하는 중`
- `running`: `분석 workflow를 실행하는 중`
- `ready`: API status label
- `error`: `작업을 완료하지 못했습니다`

API status label:

- `CREATED`: `작업 생성됨`
- `APPROVED`: `자동 검토 완료`
- `NEEDS_REVIEW`: `사람 검토 필요`
- `REVISION_REQUIRED`: `추가 검토 필요`
- `FAILED`: `작업 실패`
- unknown: `작업 상태 확인 중`

### 6.5 fallback sample 정책

M4 이후 앱은 API 실패 시 자동으로 sample job으로 대체하지 않는다.

이유:

- upload-to-review flow의 실패를 사용자가 알아야 한다.
- sample fallback은 실제 API 연결 실패를 숨긴다.

단, `loadSampleEditorJob` 함수는 테스트/개발 fixture로 유지할 수 있다.

## 7. Candidate Spec Preview 설계

파일: `apps/web/src/editor/EditorCanvas.tsx`

### 7.1 입력 props

```ts
interface EditorCanvasProps {
  candidateSpec: CandidateSpecPreview | null;
  markerReviewItem?: ReviewItem;
}
```

### 7.2 canvas 크기

화면 canvas shell은 기존 `760 x 540` stage를 유지한다.

candidate spec page를 stage에 맞추기 위해 scale을 계산한다.

```ts
scale = min(720 / page.width, 460 / page.height)
offsetX = 20
offsetY = 40
```

모든 candidate spec 좌표는 `offset + value * scale`로 변환한다.

### 7.3 빈 preview

`candidateSpec`이 없으면 기존 sample triangle placeholder를 표시한다.

문구:

- `업로드 후 분석을 실행하면 미리보기가 여기에 표시됩니다.`

### 7.4 지원 primitive

M4 웹 preview는 아래 primitive만 표시한다.

- `formula_line`
- `text_note`
- `highlight_line`
- `highlight_curve`
- `arrow`
- `box`
- `circle`
- `point_label`
- `segment_label`
- `dimension_line`
- `dimension_curve`
- `freehand_dimension_marker`

범위 밖 primitive나 malformed geometry는 crash 없이 skip한다.

### 7.5 primitive rendering 규칙

공통:

- `element.color`가 있으면 사용한다.
- 없으면 `#dc2626`을 기본 overlay color로 사용한다.
- `element.id`는 React key로만 사용하고 화면에 노출하지 않는다.

텍스트:

- 표시 문자열 우선순위는 M3와 동일하다.
  1. `display_text`
  2. `text`
  3. `geometry.text`
  4. `geometry.label`
  5. `label`
- 빈 문자열이면 skip한다.

선/곡선:

- `Line` component를 사용한다.
- curve는 Konva `tension={0.42}`로 최소 표현한다.
- arrow는 line 끝점 근처에 작은 `Text` `→`를 표시한다. M4에서는 정확한 arrowhead geometry를 계산하지 않는다.

box/circle:

- box는 `Rect`.
- circle은 center/radius 또는 bbox fallback을 사용한다.

dimension/freehand:

- `dimension_line`은 visible fallback 후 직선으로 표시한다.
- `dimension_curve`는 start, control point, end를 `Line` tension으로 표시한다.
- `freehand_dimension_marker`는 valid visible stroke를 각각 `Line`으로 표시하고 label을 같이 표시한다.

## 8. Review Panel 계약

파일: `apps/web/src/editor/ReviewPanel.tsx`

기존 `filterHumanReviewItems` 정책을 유지한다.

- `requires_human_review === true`
- `resolved !== true`
- 최대 3개

M4에서 review item resolve button은 추가하지 않는다.

## 9. Error Handling

API client는 endpoint별 한국어 오류를 throw한다.

UI는 thrown error가 `Error`이면 `error.message`를 표시한다. 그렇지 않으면 `작업을 완료하지 못했습니다.`를 표시한다.

사용자가 다시 선택 버튼을 누르면:

- file 선택 상태를 비운다.
- workflow state를 `idle`로 되돌린다.
- preview와 review panel도 빈 상태로 되돌린다.

## 10. Test 요구사항

### 10.1 API client tests

`apps/web/src/api/client.test.ts`

검증:

1. `runUploadToReviewWorkflow`가 create → problem upload → teacher upload → run → candidate spec → review items 순서로 호출한다.
2. upload 요청은 `FormData`를 사용하고 field name은 `file`이다.
3. candidate spec을 result에 포함한다.
4. problem upload 실패 시 teacher upload/run/fetch를 호출하지 않는다.
5. review item default normalize를 유지한다.

### 10.2 workflow state tests

`apps/web/src/app/workflowState.test.ts`

검증:

1. `start`는 `creating`과 empty job/error를 만든다.
2. `ready`는 job을 저장한다.
3. `error`는 한국어 errorMessage를 저장한다.
4. `reset`은 `idle`로 되돌린다.

### 10.3 candidate preview tests

`apps/web/src/editor/candidatePreview.test.ts`

Renderer helper를 UI component 밖 pure function으로 분리한다.

파일: `apps/web/src/editor/candidatePreview.ts`

검증:

1. page scale과 coordinate transform이 안정적이다.
2. text 우선순위와 empty skip을 지킨다.
3. malformed primitive를 skip한다.
4. `freehand_dimension_marker`의 visible stroke와 label primitive를 생성한다.

### 10.4 build/tests

실행:

```bash
npm --prefix apps/web test
npm --prefix apps/web run build
python -m pytest -q
git diff --check
```

## 11. 완료 조건

M4는 다음 조건을 모두 만족하면 Done이다.

- 웹에서 두 이미지를 선택하고 workflow를 실행할 수 있다.
- run 성공 후 candidate spec preview가 표시된다.
- run 성공 후 review panel이 최신 review items를 표시한다.
- 사람에게 보여줄 review item은 `requires_human_review=true`이고 unresolved인 항목뿐이다.
- API 실패 시 sample fallback으로 숨기지 않고 한국어 error를 표시한다.
- M5 범위인 patch 저장/re-render/export를 구현하지 않는다.
- web tests, web build, Python tests, diff check가 통과한다.
