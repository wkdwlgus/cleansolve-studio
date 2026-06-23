# Job Progress SSE Replay UI 상세 설계

## 목적

사용자가 이미지 업로드 후 분석 결과를 기다리는 동안 CleanSolve Studio가 어떤 과정을 거치는지 볼 수 있게 한다.

이번 작업은 `progress_events` artifact를 이미 저장하고 있는 현재 구조를 활용해, 저장된 progress event를 Server-Sent Events(SSE) 형식으로 replay하고 웹 editor에 진행 timeline을 표시하는 UX 기반을 만든다.

## 중요한 범위 결정

이번 PR은 **SSE replay UI**다. 실시간 workflow 실행 중 event push는 아니다.

현재 `POST /jobs/{job_id}/run`은 동기식이다. workflow가 끝난 뒤 `progress_events` artifact가 저장된다. 따라서 이번 작업의 SSE endpoint는 저장된 artifact를 읽어 `text/event-stream`으로 순서대로 replay한다.

실행 중 사용자가 완전히 빈 화면을 보지 않도록 웹은 다음 두 층을 함께 표시한다.

1. client-side optimistic 단계
   - `creating`
   - `uploading`
   - `running`
2. server replay progress events
   - `CREATED`
   - `STYLE_PRESET_LOADED`
   - `SPEC_EXTRACTED`
   - `SPEC_VALIDATING`
   - `RENDERING`
   - `RENDERED`
   - `INSPECTING_CONTENT`
   - `INSPECTING_LAYOUT`
   - `INSPECTING_STYLE`
   - `COMPUTING_VISUAL_DIFF`
   - `CORRECTION_PLANNING`
   - `PATCHING_SPEC`
   - `RE_RENDERING`
   - `APPROVED`
   - `NEEDS_REVIEW`
   - `REVISION_REQUIRED`
   - `FAILED`

## 반드시 다음 작업으로 확장할 내용

이번 작업 다음에는 **background job + live SSE**를 설계하고 구현한다. 이 후속 작업은 이번 spec에서 빠지면 안 되는 deferred contract다.

후속 작업의 목표:

- `POST /jobs/{job_id}/run` 또는 새 `POST /jobs/{job_id}/runs`가 즉시 `202 Accepted`를 반환한다.
- workflow 실행은 background task 또는 worker에서 진행된다.
- progress event가 append될 때마다 durable progress store에 flush된다.
- `GET /jobs/{job_id}/progress-stream`은 실행 중 event를 실시간으로 송출한다.
- browser refresh 후에도 이미 송출된 event를 replay할 수 있다.
- job failure, worker restart, duplicate connection, reconnect cursor를 별도 계약으로 다룬다.

이번 작업은 이 후속 작업을 쉽게 만들기 위해 SSE payload shape, event id, client timeline model을 미리 고정한다.

## 범위

### 포함

- FastAPI SSE replay endpoint 추가
  - `GET /jobs/{job_id}/progress-stream`
- 저장된 `progress_events` artifact를 SSE event sequence로 변환
- SSE event payload schema 명시
- 웹 API client에 progress stream consumer 추가
- 웹 workflow state에 progress timeline 추가
- 업로드/분석 실행 중 progress panel 표시
- run 완료 후 `progress_events` replay 결과를 timeline에 반영
- API unit test, web client test, app state test, Playwright smoke test 갱신
- MVP 로드맵의 다음 작업을 `background job + live SSE`로 명시

### 제외

- `POST /jobs/{job_id}/run` 비동기화
- background worker, queue, task registry
- workflow node 실행 중 실시간 flush
- reconnect cursor 또는 `Last-Event-ID` 처리
- OpenAI/GPT/image generation 동작 변경
- progress event allowlist 변경
- progress event model schema 변경
- 새로운 workflow phase/status 추가
- export progress stream
- PDF export

## 현재 상태

workflow는 이미 `ProgressEvent`를 생성한다.

- model: `packages/workflow/cleansolve_workflow/review_contract.py`
- event append: `append_progress_event()`
- status message map: `packages/workflow/cleansolve_workflow/nodes.py`
- artifact 저장: `apps/api/cleansolve_api/routes/jobs.py`의 `run_job()`
- artifact 조회: `GET /jobs/{job_id}/progress-events`

웹은 현재 `runUploadToReviewWorkflow()`에서 `onPhase` callback으로 `creating`, `uploading`, `running`만 표시한다. server progress event는 읽지 않는다.

## API 설계

### Endpoint

```http
GET /jobs/{job_id}/progress-stream
Accept: text/event-stream
```

### 응답 성공

응답은 `StreamingResponse`로 반환한다.

Header:

```http
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache
X-Accel-Buffering: no
```

`X-Accel-Buffering`은 nginx 같은 proxy가 SSE를 버퍼링하지 않도록 돕는 hint다. 로컬 FastAPI 테스트에서는 header 존재만 검증한다.

### SSE frame 형식

각 progress event는 아래 형식으로 송출한다.

```text
id: evt_0000
event: progress
data: {"event_id":"evt_0000","job_id":"job_...","sequence":0,"phase":"analysis","status":"CREATED","message":"작업을 시작했습니다.","attempt":0,"max_attempts":2,"scores":null,"next_action":"continue","created_at":"2026-06-23T00:00:00Z"}

```

마지막에는 complete event를 한 번 송출한다.

```text
event: complete
data: {"job_id":"job_...","event_count":17}

```

규칙:

- progress event frame 순서는 `sequence` 오름차순이다.
- `id:` 값은 `event.event_id`를 그대로 사용한다.
- `event:` 값은 progress event에 대해 항상 `progress`다.
- `data:` 값은 `ProgressEvent.model_dump(mode="json")`와 같은 shape다.
- `ensure_ascii=False`로 JSON을 serialize해 한국어 메시지를 escape하지 않는다.
- complete event에는 `id:`를 붙이지 않는다.
- frame 사이에는 빈 줄 하나를 둔다.

### 404 / failure behavior

아직 run이 완료되지 않아 `progress_events` artifact가 없으면 기존 artifact error contract를 그대로 따른다.

```json
{
  "detail": {
    "code": "ANALYSIS_ARTIFACT_NOT_FOUND",
    "message": "...",
    "fields": {
      "artifact_type": "progress_events"
    }
  }
}
```

이번 작업에서는 endpoint가 artifact 생성을 기다리며 block하지 않는다. 이 결정은 동기 `POST /run` 구조와 일관된다.

### 구현 위치

- `apps/api/cleansolve_api/routes/jobs.py`
  - route 추가
  - `_sse_frame()` helper 추가
  - `_progress_event_stream()` generator 추가

helper 상세 계약:

```python
def _sse_frame(
    *,
    event: str,
    data: dict[str, object],
    event_id: str | None = None,
) -> str:
    ...
```

출력:

- `event_id`가 있으면 첫 줄은 `id: {event_id}`
- 그 다음 줄은 `event: {event}`
- 그 다음 줄은 `data: {json.dumps(data, ensure_ascii=False, separators=(",", ":"))}`
- 마지막은 `\n\n`

`event`와 `event_id`는 내부 allowlisted value만 전달한다. 사용자 입력을 직접 넣지 않는다.

## Web 설계

### 타입

`apps/web/src/api/client.ts`에 API payload 타입을 추가한다.

```ts
export interface ProgressEventPayload {
  event_id: string;
  job_id: string;
  sequence: number;
  phase: string;
  status: string;
  message: string;
  attempt: number;
  max_attempts: number;
  scores: Record<string, number> | null;
  next_action: string;
  created_at: string;
}
```

`apps/web/src/app/workflowState.ts`에 UI timeline 타입을 추가한다. API client가 UI state 타입을 소유하지 않게 한다.

```ts
export type WorkflowProgressItem =
  | {
      source: 'client';
      id: 'client-creating' | 'client-uploading' | 'client-running';
      message: string;
      status: 'CREATING' | 'UPLOADING' | 'RUNNING';
      active: boolean;
    }
  | {
      source: 'server';
      id: string;
      message: string;
      status: string;
      sequence: number;
      attempt: number;
      maxAttempts: number;
      createdAt: string;
      active: boolean;
    };
```

### SSE consumer

브라우저 런타임에서는 `EventSource`를 사용한다. 테스트에서는 `eventSourceFactory`를 주입한다.

`apps/web/src/api/client.ts`에 아래 helper를 추가한다.

```ts
export interface EventSourceLike {
  addEventListener(type: string, listener: (event: MessageEvent) => void): void;
  close(): void;
  onerror: ((event: Event) => void) | null;
}
```

low-level stream helper:

```ts
export function streamProgressEvents(
  jobId: string,
  options?: {
    baseUrl?: string;
    eventSourceFactory?: (url: string) => EventSourceLike;
    onProgress?: (event: ProgressEventPayload) => void;
    onComplete?: () => void;
    onError?: (error: Error) => void;
  }
): () => void
```

계약:

- 반환값은 unsubscribe 함수다.
- unsubscribe는 내부 `EventSource.close()`를 정확히 한 번 호출한다.
- `progress` message를 받으면 JSON parse 후 `onProgress`를 호출한다.
- `complete` message를 받으면 `onComplete`를 호출하고 connection을 닫는다.
- malformed JSON이면 `onError(new Error("진행 상황을 해석하지 못했습니다."))`를 호출하고 connection을 닫는다.
- native `error` event가 발생하면 `onError(new Error("진행 상황 연결이 끊겼습니다."))`를 호출하고 connection을 닫는다.
- `EventSource`가 없는 테스트 환경에서는 반드시 `eventSourceFactory`를 주입한다.

high-level replay helper:

```ts
export async function replayProgressEvents(
  jobId: string,
  options?: {
    baseUrl?: string;
    eventSourceFactory?: (url: string) => EventSourceLike;
    onProgress?: (event: ProgressEventPayload) => void;
  }
): Promise<ProgressEventPayload[]>
```

계약:

- 내부적으로 `streamProgressEvents()`를 사용한다.
- `progress` event를 받을 때마다 내부 배열에 append하고 `onProgress`를 호출한다.
- `complete` event를 받으면 collected array를 resolve한다.
- stream error 또는 malformed JSON이면 reject한다.
- resolve/reject 후에는 connection이 닫혀 있어야 한다.

fallback fetch helper:

```ts
export async function getProgressEvents(
  jobId: string,
  baseUrl?: string,
  fetcher?: typeof fetch
): Promise<ProgressEventPayload[]>
```

계약:

- `GET /jobs/{job_id}/progress-events`를 호출한다.
- payload shape는 `{ job_id: string, events: ProgressEventPayload[] }`다.
- `events`가 배열이 아니면 빈 배열을 반환한다.
- 각 event는 `event_id`, `message`, `status`, `sequence`가 올바른 type일 때만 보존한다.
- invalid event는 skip한다.

### fallback fetch

SSE replay endpoint가 404일 수 있으므로, `runUploadToReviewWorkflow()`는 `POST /run` 완료 후 다음 순서로 동작한다.

1. `replayProgressEvents()`로 replay를 시도한다.
2. SSE가 `complete`되면 candidate spec과 review items를 조회한다.
3. SSE가 실패하면 기존 `GET /jobs/{job_id}/progress-events`를 한 번 조회한다.
4. fallback 조회도 실패하면 progress timeline 없이 candidate spec과 review items를 조회한다.

이 fallback은 MVP UX를 깨지 않기 위한 것이다. progress UI 실패는 job 결과 조회를 막지 않는다.

`LoadEditorJobOptions`는 다음 필드를 추가한다.

```ts
interface LoadEditorJobOptions {
  baseUrl?: string;
  fetcher?: typeof fetch;
  onPhase?: (phase: 'creating' | 'uploading' | 'running') => void;
  onProgress?: (event: ProgressEventPayload) => void;
  eventSourceFactory?: (url: string) => EventSourceLike;
}
```

`UploadToReviewResult`는 다음 필드를 추가한다.

```ts
progressEvents: ProgressEventPayload[];
```

`progressEvents`는 replay 또는 fallback fetch로 얻은 server event 목록이다. server event를 하나도 얻지 못하면 빈 배열이다.

### workflow state

`apps/web/src/app/workflowState.ts`를 확장한다.

```ts
export interface WorkflowViewState {
  phase: WorkflowPhase;
  job: UploadToReviewResult | null;
  errorMessage: string | null;
  progressItems: WorkflowProgressItem[];
}
```

event 추가:

```ts
| { type: 'progress-client'; step: 'creating' | 'uploading' | 'running' }
| { type: 'progress-server'; event: ProgressEventPayload }
```

규칙:

- `start`, `creating`은 `progressItems`를 초기화하고 `client-creating`을 active로 넣는다.
- `uploading`은 `client-uploading`을 append하고 이전 client item `active=false`.
- `running`은 `client-running`을 append하고 이전 client item `active=false`.
- `progress-server`는 같은 `event_id`가 이미 있으면 중복 추가하지 않는다.
- 새 server event를 추가하면 기존 모든 item은 `active=false`, 새 item만 `active=true`.
- `ready`는 모든 progress item을 `active=false`로 만든다.
- `error`는 progress item을 보존하고 모든 item을 `active=false`로 만든다.
- `reset`은 progress item을 빈 배열로 되돌린다.

### UI

`apps/web/src/app/App.tsx`에 progress panel을 추가한다.

위치:

- upload form 아래
- `EditorCanvas` 위

DOM:

```tsx
<section className="progress-panel" aria-label="진행 상황">
  <div className="panel-header">
    <h2>진행 상황</h2>
    <span>{workflow.progressItems.length}</span>
  </div>
  ...
</section>
```

표시 규칙:

- progress item이 없으면 “아직 시작된 진행 단계가 없습니다.”를 표시한다.
- item은 시간순으로 표시한다.
- active item은 시각적으로 강조한다.
- server item에 `attempt/maxAttempts`가 있으면 `시도 {attempt}/{maxAttempts}`를 작은 텍스트로 표시한다.
- 사용자가 읽기 쉬운 한국어 message만 표시한다.
- raw `event_id`, raw `sequence`, raw JSON은 UI에 표시하지 않는다.

CSS:

- `.progress-panel`
- `.progress-list`
- `.progress-item`
- `.progress-item.is-active`
- `.progress-meta`

카드 안 카드 구조를 만들지 않는다. 기존 panel 스타일과 맞춰 조용한 작업 UI로 둔다.

## 테스트 설계

### API tests

파일: `apps/api/tests/test_jobs_api.py`

추가 테스트:

1. `test_progress_stream_replays_saved_progress_events_as_sse`
   - job 생성
   - required images upload
   - `POST /run`
   - `GET /progress-stream`
   - status 200
   - `content-type`이 `text/event-stream`으로 시작
   - body에 `event: progress`, `id: evt_0000`, `data:` 포함
   - body에 한국어 `"작업을 시작했습니다."` 포함
   - body에 `event: complete` 포함
   - body에 `source_image_paths` 없음

2. `test_progress_stream_returns_404_before_run`
   - job 생성
   - `GET /progress-stream`
   - status 404
   - detail code `ANALYSIS_ARTIFACT_NOT_FOUND`

3. `test_sse_frame_serializes_korean_without_ascii_escape`
   - `_sse_frame(event="progress", event_id="evt_0000", data={"message": "작업을 시작했습니다."})`
   - output에 `작업을 시작했습니다.` 포함
   - output에 `\\uc791` 없음
   - output이 `\n\n`로 끝남

### Web client tests

파일: `apps/web/src/api/client.test.ts`

추가 테스트:

1. `streamProgressEvents`가 injected EventSource에서 progress와 complete를 처리한다.
2. malformed progress JSON이면 한국어 error를 전달하고 close한다.
3. `replayProgressEvents`가 progress event를 배열로 모은 뒤 complete에서 resolve한다.
4. `getProgressEvents`가 malformed event를 skip하고 valid event만 반환한다.
5. `runUploadToReviewWorkflow`가 run 완료 후 progress replay를 소비하고 result에 `progressEvents`를 포함한다.

`UploadToReviewResult`에 다음 필드를 추가한다.

```ts
progressEvents: ProgressEventPayload[];
```

### Workflow state tests

파일: `apps/web/src/app/workflowState.test.ts`

추가 테스트:

1. client progress 단계가 순서대로 쌓이고 active가 하나만 남는다.
2. server progress event가 중복 `event_id`를 무시한다.
3. ready가 모든 progress item을 inactive로 만든다.
4. error가 progress item을 보존한다.
5. reset이 progress item을 비운다.

### App / Playwright smoke

파일: `apps/web/e2e/upload-review.spec.ts`

route 추가:

- `**/jobs/job_e2e/progress-stream`

mock SSE body:

```text
id: evt_0000
event: progress
data: {"event_id":"evt_0000","job_id":"job_e2e","sequence":0,"phase":"analysis","status":"CREATED","message":"작업을 시작했습니다.","attempt":0,"max_attempts":2,"scores":null,"next_action":"continue","created_at":"2026-06-23T00:00:00Z"}

event: complete
data: {"job_id":"job_e2e","event_count":1}

```

검증:

- `진행 상황` panel이 표시된다.
- `작업을 시작했습니다.`가 표시된다.
- 기존 `자동 검토 완료`, preview, review panel 검증은 유지한다.

## 접근성

- job summary는 기존 `role="status" aria-live="polite"`를 유지한다.
- progress panel 전체에는 `aria-label="진행 상황"`을 둔다.
- progress list는 plain list로 구현한다.
- active item은 색상만으로 구분하지 않고 `진행 중` 텍스트 또는 `aria-current="step"`을 둔다.

## 보안/개인정보

- SSE payload는 저장된 `ProgressEvent`만 송출한다.
- `source_image_paths`, API key, local path, raw model output은 송출하지 않는다.
- 이번 작업은 이미 저장된 `progress_events` artifact read path hardening을 전제로 한다.
- SSE data는 `json.dumps()` 결과만 사용하고, 사용자 입력을 SSE field 이름으로 쓰지 않는다.

## 완료 기준

- `GET /jobs/{job_id}/progress-stream`이 저장된 progress events를 SSE로 replay한다.
- run 전에는 기존 artifact-specific 404 contract를 유지한다.
- 웹에서 upload/run 흐름 중 progress panel이 표시된다.
- run 완료 후 server progress message가 timeline에 표시된다.
- SSE 실패가 candidate spec/review item 조회를 막지 않는다.
- 한국어 progress message가 UI와 SSE body에서 escape되지 않는다.
- 기존 mock E2E와 API tests가 회귀 없이 통과한다.
- OpenAI/GPT/image generation 동작은 변경하지 않는다.

## 다음 작업 고정

이번 PR 다음 우선순위는 **background job + live SSE**다.

이 후속 작업은 별도 상세 설계를 작성한다. 최소 포함 범위는 다음과 같다.

- run request 비동기화
- live progress store
- workflow node별 event flush
- SSE reconnect policy
- browser refresh replay
- failed/cancelled job stream contract
- API/web/harness E2E
