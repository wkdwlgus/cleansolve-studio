# M10 Background Job & Live SSE 상세 설계

## 목적

M10은 현재 동기식 `POST /jobs/{job_id}/run` 실행을 비동기 background job으로 바꾸고, workflow 실행 중 생성되는 progress event를 durable file에 즉시 flush한 뒤 `GET /jobs/{job_id}/progress-stream`에서 live SSE로 전달한다.

M9에서 완료한 저장된 `progress_events` artifact replay UI는 유지한다. M10은 replay endpoint의 payload shape를 바꾸지 않고, 같은 endpoint가 실행 중에는 live stream으로, terminal 상태에서는 기존 replay stream으로 동작하게 만든다.

## 현재 상태와 문제

현재 API는 `apps/api/cleansolve_api/routes/jobs.py`의 `run_job()`에서 다음을 한 요청 안에서 모두 수행한다.

1. job manifest와 필수 image artifact를 검증한다.
2. `run_mock_workflow()`를 동기 호출한다.
3. workflow state 안의 `progress_events`를 한 번에 `progress_events` analysis artifact로 저장한다.
4. 완료된 job response를 `200 OK`로 반환한다.

현재 `GET /jobs/{job_id}/progress-stream`은 이미 저장된 `progress_events` artifact만 `text/event-stream`으로 replay한다. 따라서 긴 OpenAI 분석 또는 self-revision loop가 실행되는 동안 웹은 실제 server event를 볼 수 없다.

## 설계 원칙

- MVP에서는 외부 queue, Celery, Redis, 별도 worker process를 도입하지 않는다.
- FastAPI process 내부 background thread로 시작하되, progress event는 반드시 파일에 flush해 process crash 전까지 생성된 event를 보존한다.
- deterministic renderer는 기존처럼 deterministic이어야 하며, background 실행 구조가 renderer 입력이나 output ordering을 바꾸면 안 된다.
- 모델은 spec 생성, 검수, 수정 계획에만 사용한다. progress event, job response, UI에는 raw model output, prompt, local path, API key, `source_image_paths`를 노출하지 않는다.
- M9의 `ProgressEvent` SSE payload와 web timeline 모델은 깨지지 않아야 한다.

## 검토한 접근

### A. FastAPI 내부 background thread + durable progress file

`POST /jobs/{job_id}/run`이 manifest를 `RUNNING`으로 바꾸고 process-local background executor에 작업을 제출한다. worker는 workflow를 실행하면서 progress event마다 job별 JSONL 파일에 append, flush, fsync한다. SSE endpoint는 이 파일을 polling하며 replay와 live delivery를 함께 처리한다.

장점:

- 현재 local filesystem artifact store와 가장 잘 맞는다.
- 추가 운영 의존성이 없다.
- 테스트에서 executor와 progress store를 주입해 결정적으로 검증할 수 있다.
- M11~M14 전에 MVP live progress gap을 작게 닫을 수 있다.

단점:

- process가 여러 개이면 in-memory executor registry가 공유되지 않는다.
- process crash 중 실행 중이던 worker를 자동 재개하지 않는다.
- 대량 job scheduling, retry, priority, distributed lock은 제공하지 않는다.

### B. FastAPI `BackgroundTasks`

route handler에서 FastAPI `BackgroundTasks`에 workflow 실행 함수를 등록한다.

장점:

- 구현량이 가장 적다.
- FastAPI 기본 기능이라 새 executor abstraction이 작다.

단점:

- task 상태와 active worker registry를 명시적으로 관리하기 어렵다.
- 테스트에서 worker lifecycle, duplicate run, shutdown behavior를 통제하기 어렵다.
- 장시간 작업과 SSE replay/cancel/failure contract를 확장하기 애매하다.

### C. 외부 queue/Celery/RQ

`POST /run`이 queue에 message를 넣고 별도 worker process가 workflow를 실행한다.

장점:

- production scale, retry, worker restart, horizontal scaling에 적합하다.
- API process와 worker process lifecycle이 분리된다.

단점:

- MVP 범위 대비 운영 구조가 크다.
- 현재 local artifact store와 lock 정책을 queue-safe하게 다시 설계해야 한다.
- M10의 핵심 목표인 live progress UX보다 인프라 작업이 커진다.

### 추천

M10은 **A. FastAPI 내부 background thread + durable progress file**로 진행한다.

이 선택은 M10 목표에 충분하고, M11 이후 실제 planner/eval loop가 길어져도 사용자는 live progress를 볼 수 있다. 단, spec에 process-local 한계를 명시하고 post-MVP에서 외부 queue로 옮길 때 유지해야 할 worker/progress/SSE 계약을 고정한다.

## API 계약

### `POST /jobs/{job_id}/run`

M10에서 이 endpoint는 비동기 시작 endpoint가 된다.

요청:

```http
POST /jobs/{job_id}/run
```

성공 응답:

```http
202 Accepted
Content-Type: application/json
```

```json
{
  "job_id": "job_...",
  "status": "RUNNING",
  "revision_attempts": 0,
  "review_items": [],
  "latest_image_artifact_ids": {
    "problem": "img_...",
    "teacher_solution": "img_..."
  },
  "image_artifacts": {
    "problem": [],
    "teacher_solution": []
  },
  "analysis_artifacts": {
    "candidate_spec": [],
    "validation_report": [],
    "correction_plan": [],
    "review_correction": [],
    "progress_events": []
  },
  "latest_analysis_artifact_ids": {
    "candidate_spec": null,
    "validation_report": null,
    "correction_plan": null,
    "review_correction": null,
    "progress_events": null
  },
  "render_artifacts": [],
  "latest_render_artifact_id": null,
  "export_artifacts": [],
  "latest_export_artifact_id": null
}
```

규칙:

- 응답 body는 기존 `job_response()` shape를 유지하고, `status`만 `RUNNING`을 반환한다.
- `job_response()`에 `run_id`, local file path, prompt, model raw output, API key, `source_image_paths`를 추가하지 않는다.
- route는 workflow 완료를 기다리지 않는다.
- 필수 이미지가 없으면 기존처럼 `409 MISSING_REQUIRED_IMAGES`를 반환하고 background job을 만들지 않는다.
- unknown 또는 invalid job id는 기존 `404 JOB_NOT_FOUND`를 유지한다.
- 이미 `RUNNING`이면 `409 JOB_ALREADY_RUNNING`을 반환한다.
- terminal status인 `APPROVED`, `NEEDS_REVIEW`, `REVISION_REQUIRED`, `FAILED`, `CANCELLED`에서 같은 job을 다시 실행하는 것은 M10에서 지원하지 않고 `409 JOB_RUN_NOT_RESTARTABLE`을 반환한다. 웹은 이미 upload마다 새 job을 만들므로 MVP UX에 영향이 없다.
- 기존 failure review item의 `retryable: true`는 "새 job으로 재시도 가능"이라는 의미로만 남긴다. 같은 job 재실행은 M10 범위가 아니다.

추가 error code:

```json
{
  "detail": {
    "code": "JOB_ALREADY_RUNNING",
    "message": "이미 실행 중인 작업입니다.",
    "fields": {
      "job_id": "job_..."
    }
  }
}
```

```json
{
  "detail": {
    "code": "JOB_RUN_NOT_RESTARTABLE",
    "message": "이 작업은 다시 실행할 수 없습니다.",
    "fields": {
      "job_id": "job_...",
      "status": "APPROVED"
    }
  }
}
```

```json
{
  "detail": {
    "code": "JOB_RUN_SUBMIT_FAILED",
    "message": "background 작업을 시작하지 못했습니다.",
    "fields": {
      "job_id": "job_..."
    }
  }
}
```

### `GET /jobs/{job_id}/progress-stream`

M10에서도 endpoint path는 유지한다.

요청:

```http
GET /jobs/{job_id}/progress-stream
Accept: text/event-stream
Last-Event-ID: evt_0003
```

테스트와 수동 replay를 위해 query cursor도 지원한다.

```http
GET /jobs/{job_id}/progress-stream?after=evt_0003
```

우선순위:

1. `after` query가 있으면 query 값을 사용한다.
2. 없으면 `Last-Event-ID` header를 사용한다.
3. 둘 다 없으면 처음부터 replay한다.

cursor 규칙:

- cursor는 기존 M9 regex와 같은 `^evt_\d{4,}$`만 인정한다.
- invalid cursor는 응답에 반영하지 않고 처음부터 replay한다.
- valid cursor `evt_0003`이 들어오면 `sequence <= 3` event는 보내지 않는다.
- event id는 sequence 기반이므로 파일에 cursor id가 직접 존재하지 않아도 numeric cursor보다 큰 sequence를 replay한다.

응답 header:

```http
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache
X-Accel-Buffering: no
```

실행 전:

- live progress file도 terminal `progress_events` artifact도 없으면 기존 M9와 같이 `404 ANALYSIS_ARTIFACT_NOT_FOUND`를 반환한다.

실행 중:

- manifest status가 `RUNNING`이면 live progress file을 읽어 이미 flush된 event를 replay한 뒤 새 event를 polling한다.
- polling interval 기본값은 250ms다.
- event가 없는 시간이 15초를 넘으면 SSE comment heartbeat를 보낸다.

```text
: keep-alive

```

terminal:

- `APPROVED`, `NEEDS_REVIEW`, `REVISION_REQUIRED`는 모든 progress event를 보낸 뒤 `complete` event를 보내고 연결을 닫는다.
- `FAILED`는 모든 progress event를 보낸 뒤 `failed` event를 보내고 연결을 닫는다.
- `CANCELLED`는 모든 progress event를 보낸 뒤 `cancelled` event를 보내고 연결을 닫는다.

success terminal frame:

```text
event: complete
data: {"job_id":"job_...","status":"APPROVED","event_count":17}

```

failure terminal frame:

```text
event: failed
data: {"job_id":"job_...","status":"FAILED","reason":"response_error","event_count":6}

```

cancel terminal frame:

```text
event: cancelled
data: {"job_id":"job_...","status":"CANCELLED","reason":"cancelled","event_count":4}

```

terminal data 규칙:

- `reason`은 allowlisted safe reason만 사용한다.
- `reason`에 exception message, local path, prompt, raw model output, API key를 넣지 않는다.
- terminal frame에는 `id:`를 붙이지 않는다.

## Job 상태 전이

`apps/api/cleansolve_api/artifacts.py`의 `JobStatus`에 `RUNNING`과 `CANCELLED`를 추가한다.

상태 전이:

```text
CREATED
  -> RUNNING
RUNNING
  -> APPROVED
  -> NEEDS_REVIEW
  -> REVISION_REQUIRED
  -> FAILED
  -> CANCELLED
```

허용하지 않는 전이:

- `RUNNING -> RUNNING`
- terminal 상태에서 `RUNNING`
- terminal 상태에서 다른 terminal 상태로 직접 변경

M10에서 user-facing cancel endpoint와 web cancel button은 만들지 않는다. `CANCELLED`는 worker shutdown 또는 future cancel API가 같은 stream contract를 사용할 수 있도록 상태와 SSE terminal contract만 고정한다. 실제 cooperative cancellation은 M14 이후로 보류한다.

`packages/workflow/cleansolve_workflow/review_contract.py`의 `ProgressStatus`에는 `CANCELLED`를 추가하고 message allowlist에는 "작업이 취소되었습니다."를 추가한다. M10 product UI에서는 이 status를 직접 만들지 않지만, stream contract와 tests가 같은 progress payload schema를 사용할 수 있게 한다.

## Artifact store 상태 전이 API

`LocalArtifactStore`에 route와 worker가 직접 manifest dict를 만지지 않도록 전이 method를 추가한다.

```python
def start_analysis_run(
    self,
    job_id: str,
    *,
    source_image_artifact_ids: dict[ImageRole, str],
) -> JobManifest:
    ...

def save_failed_background_run(
    self,
    job_id: str,
    *,
    reason: str,
    review_item: dict[str, Any],
    progress_events_payload: dict[str, Any],
    source_image_artifact_ids: dict[ImageRole, str],
) -> JobManifest:
    ...
```

`start_analysis_run()` 규칙:

- job id를 검증한다.
- job lock 안에서 manifest를 읽는다.
- status가 `CREATED`가 아니면 위 API error contract대로 거절한다.
- manifest의 latest image artifact ids가 `source_image_artifact_ids`와 같지 않으면 `ANALYSIS_SOURCE_CHANGED`를 반환한다.
- status를 `RUNNING`으로 저장한다.
- analysis artifact id는 만들지 않는다.

worker success는 기존 `save_analysis_outputs()`를 사용하되 `RUNNING`에서 terminal status로 가는 호출만 허용하도록 검증을 추가한다.

`save_failed_background_run()` 규칙:

- `FAILED` status를 저장한다.
- candidate spec, validation report, correction plan, review_correction artifact는 만들지 않는다.
- safe `progress_events` artifact는 저장한다.
- review item에는 safe reason만 저장한다.
- exception message, local path, prompt, API key는 저장하지 않는다.

## Background job/worker 실행 계약

새 internal module을 둔다.

```text
apps/api/cleansolve_api/background.py
apps/api/cleansolve_api/live_progress.py
```

### `JobRunExecutor`

역할:

- process-local `ThreadPoolExecutor`를 소유한다.
- active job id set을 관리한다.
- route에서 submit할 수 있는 작은 interface를 제공한다.
- 테스트에서는 inline 또는 manually-drained executor로 교체할 수 있어야 한다.

계약:

```python
class JobRunExecutor:
    def submit(self, request: JobRunRequest) -> None:
        ...

    def is_active(self, job_id: str) -> bool:
        ...
```

`submit()`은 queueing 성공 여부만 책임진다. workflow 성공/실패는 worker가 manifest와 progress file에 기록한다.

기본 설정:

- `CLEANSOLVE_BACKGROUND_MAX_WORKERS=1`
- `CLEANSOLVE_PROGRESS_POLL_INTERVAL_MS=250`
- `CLEANSOLVE_PROGRESS_HEARTBEAT_SECONDS=15`

MVP에서는 worker 수를 1로 두는 것이 기본이다. 동시성보다 deterministic artifact ordering과 테스트 안정성을 우선한다.

### `JobRunRequest`

worker에 넘기는 값:

```python
class JobRunRequest(BaseModel):
    job_id: str
    source_image_artifact_ids: dict[ImageRole, str]
    analysis_client_kind: str
    openai_model_analysis: str
    openai_analysis_image_detail: str
    openai_analysis_timeout_seconds: int
```

넘기지 않는 값:

- `openai_api_key`
- `source_image_paths`
- prompt
- raw model output

worker 함수 안에서만 settings와 store를 새로 읽어 필요한 값을 구성한다. request object나 progress event에 민감 정보를 싣지 않는다.

### Worker 처리 순서

worker는 아래 순서만 따른다.

1. `LocalArtifactStore`를 만든다.
2. job manifest가 `RUNNING`인지 확인한다.
3. route가 만든 live progress file과 meta file이 있는지 확인한다.
4. 최신 image artifact path를 내부에서 조회한다.
5. `run_mock_workflow()`를 호출하되 progress sink를 주입한다.
6. workflow progress event가 생성될 때마다 sink가 public event만 JSONL에 append하고 fsync한다.
7. workflow 성공 시 기존 `save_analysis_outputs()`와 같은 artifact를 저장한다.
8. terminal `progress_events` artifact는 live JSONL에서 읽은 public events 기준으로 저장한다.
9. manifest status를 workflow final status로 저장한다.
10. worker active registry에서 job id를 제거한다.

failure 처리:

- `OpenAIAdapterError`는 기존처럼 safe reason `configuration_error` 또는 `response_error`로 매핑한다.
- mapped reason은 manifest review item과 terminal SSE reason에는 들어갈 수 있다.
- exception message는 저장하지 않는다.
- failure 전 이미 생성된 progress event는 live JSONL과 terminal `progress_events` artifact에 남긴다.
- failure 시 final progress event `FAILED`를 append한다. 이미 workflow가 `FAILED` event를 append했다면 중복으로 append하지 않는다.
- generic exception은 safe reason `internal_error`로 저장한다.

### Route 처리 순서

`POST /jobs/{job_id}/run` route는 아래 순서를 지킨다. 이 순서는 web client가 run 시작 응답 직후 SSE를 열 때 404 race가 생기지 않게 하기 위한 필수 계약이다.

1. job manifest를 읽고 필수 image artifact ids를 검증한다.
2. `LocalArtifactStore.start_analysis_run()`으로 status를 `RUNNING`으로 저장한다.
3. `LiveProgressStore.initialize(job_id, source_image_artifact_ids)`로 빈 `live_progress.jsonl`과 `live_progress.meta.json`을 만든다.
4. `JobRunRequest`를 구성한다.
5. `JobRunExecutor.submit()`을 호출한다.
6. submit 성공 시 `202 RUNNING` job response를 반환한다.
7. submit 실패 시 safe `FAILED` progress event를 live file에 append하고, `save_failed_background_run()`으로 manifest를 `FAILED`로 바꾼 뒤 `503 JOB_RUN_SUBMIT_FAILED`를 반환한다.

`LiveProgressStore.initialize()`가 실패하면 route는 background worker를 submit하지 않는다. 가능한 경우 memory에서 safe `FAILED` progress event를 만든 뒤 `save_failed_background_run(reason="progress_write_failed")`으로 manifest를 `FAILED`로 저장하고 `500 STORAGE_WRITE_FAILED`를 반환한다. 이 경우에도 exception message와 local path는 response에 넣지 않는다.

submit 실패 시에도 `source_image_paths`, prompt, raw model output, API key는 response와 progress file에 쓰지 않는다.

## Workflow progress sink 계약

현재 `append_progress_event()`는 workflow state의 `progress_events` list에 event를 append한다. M10에서는 optional sink를 추가한다.

`packages/workflow/cleansolve_workflow/state.py`:

```python
progress_event_sink: NotRequired[Callable[[ProgressEvent], None]]
```

`append_progress_event()` 처리:

```python
state.setdefault("progress_events", []).append(event)
sink = state.get("progress_event_sink")
if callable(sink):
    sink(event)
```

규칙:

- sink exception은 workflow를 실패시킨다. durable progress write 실패는 사용자가 볼 수 없는 silent failure가 되면 안 된다.
- sink에는 `ProgressEvent` 모델만 전달한다.
- sink는 `ProgressEvent.model_dump(mode="json")` 결과에서 M9 public allowlist field만 저장한다.
- sink는 `source_image_paths`, prompt, raw model output, API key를 알 수 없어야 한다.

## Live progress durable flush

### 파일 위치

job root 아래 internal live 파일을 둔다.

```text
{storage_root}/{job_id}/artifacts/events/live_progress.jsonl
{storage_root}/{job_id}/artifacts/events/live_progress.meta.json
```

`live_progress.jsonl` line 예시:

```json
{"event_id":"evt_0000","job_id":"job_...","sequence":0,"phase":"analysis","status":"CREATED","message":"작업을 시작했습니다.","attempt":0,"max_attempts":2,"scores":null,"next_action":"continue","created_at":"2026-06-23T00:00:00Z"}
```

`live_progress.meta.json` 예시:

```json
{
  "job_id": "job_...",
  "status": "RUNNING",
  "started_at": "2026-06-23T00:00:00Z",
  "finished_at": null,
  "terminal_reason": null,
  "source_image_artifact_ids": {
    "problem": "img_...",
    "teacher_solution": "img_..."
  }
}
```

meta file은 internal file이다. API response와 progress event에 노출하지 않는다.

### Append 규칙

`LiveProgressStore.append(job_id, event)`는 다음을 보장한다.

- public fields만 저장한다.
- `ProgressEvent.model_validate()`가 실패하면 append하지 않고 예외를 낸다.
- unsafe `event_id`는 append하지 않고 예외를 낸다.
- 이미 같은 `event_id` 또는 같은 `sequence`가 있으면 append하지 않는다.
- line write 후 `flush()`와 `os.fsync()`를 호출한다.
- append 중 오류가 나면 workflow를 실패시킨다.

### Terminal artifact 생성

worker terminal 처리에서 `live_progress.jsonl`을 읽어 아래 artifact를 만든다.

```json
{
  "job_id": "job_...",
  "events": [
    {
      "event_id": "evt_0000",
      "job_id": "job_...",
      "sequence": 0,
      "phase": "analysis",
      "status": "CREATED",
      "message": "작업을 시작했습니다.",
      "attempt": 0,
      "max_attempts": 2,
      "scores": null,
      "next_action": "continue",
      "created_at": "2026-06-23T00:00:00Z"
    }
  ]
}
```

이 artifact는 M9 `GET /jobs/{job_id}/progress-events`와 terminal SSE replay가 그대로 사용할 수 있어야 한다.

M10에서는 `FAILED` job도 `progress_events` artifact를 가질 수 있다. 기존 failure tests는 candidate spec, validation report, correction plan, review_correction이 비어 있음을 계속 검증하되, `progress_events`는 safe terminal event를 저장할 수 있도록 수정한다.

## Live SSE 동작

SSE generator는 아래 source를 순서대로 선택한다.

1. manifest status가 `RUNNING`이고 live progress file이 있으면 live JSONL reader를 사용한다.
2. terminal `progress_events` artifact가 있으면 artifact replay reader를 사용한다.
3. terminal status이고 artifact 저장 전 crash 흔적 때문에 live progress file만 있으면 live JSONL reader를 replay-only mode로 사용하고 terminal frame을 보낸다.
4. 둘 다 없으면 `404 ANALYSIS_ARTIFACT_NOT_FOUND`.

live reader loop:

1. cursor 이후 event를 모두 보낸다.
2. manifest status를 다시 읽는다.
3. status가 terminal이면 남은 event를 한 번 더 읽고 terminal frame을 보낸 뒤 종료한다.
4. status가 `RUNNING`이면 250ms sleep 후 1번으로 돌아간다.
5. 15초 동안 progress event가 없으면 heartbeat comment를 보낸다.

정렬:

- file order가 아니라 `sequence` 오름차순으로 보낸다.
- duplicate `event_id` 또는 duplicate `sequence`는 처음 읽힌 event만 보낸다.
- malformed line은 stream 전체를 중단하지 않고 skip한다. 단, write path에서는 malformed event가 생기면 안 된다.

SSE progress frame은 M9와 동일하다.

```text
id: evt_0000
event: progress
data: {"event_id":"evt_0000","job_id":"job_...","sequence":0,"phase":"analysis","status":"CREATED","message":"작업을 시작했습니다.","attempt":0,"max_attempts":2,"scores":null,"next_action":"continue","created_at":"2026-06-23T00:00:00Z"}

```

## Failure와 cancelled stream contract

### Analysis adapter failure

OpenAI key 누락, SDK failure, response parsing failure는 다음 흐름을 따른다.

1. worker가 safe reason을 만든다.
2. live progress에 `FAILED` progress event를 append한다.
3. manifest를 `FAILED`로 저장한다.
4. safe review item을 저장한다.
5. terminal `progress_events` artifact를 저장한다.
6. SSE는 마지막 progress event까지 보낸 뒤 `event: failed`를 보낸다.

`failed` data:

```json
{
  "job_id": "job_...",
  "status": "FAILED",
  "reason": "configuration_error",
  "event_count": 3
}
```

허용 reason:

- `configuration_error`
- `response_error`
- `internal_error`
- `progress_write_failed`
- `analysis_source_changed`

### Cancelled

M10은 user-facing cancel 기능을 만들지 않는다. 그러나 상태와 SSE contract는 아래와 같이 고정한다.

1. manifest status가 `CANCELLED`가 되면 SSE는 추가 event를 기다리지 않는다.
2. live progress에 `CANCELLED` event가 있으면 먼저 보낸다.
3. 없으면 terminal frame만 보낸다.
4. terminal frame은 `event: cancelled`다.

`cancelled` data:

```json
{
  "job_id": "job_...",
  "status": "CANCELLED",
  "reason": "cancelled",
  "event_count": 4
}
```

## Web client 흐름

`apps/web/src/api/client.ts`의 upload-to-review flow는 M10에서 아래 순서로 바뀐다.

1. `createJob()`
2. problem image upload
3. teacher solution image upload
4. `runJob()` 호출
5. `runJob()`이 `202 RUNNING`을 반환하면 즉시 `streamProgressEvents(jobId)` 시작
6. `progress` event를 받을 때마다 기존 `nextWorkflowState(..., { type: 'progress-server' })`로 timeline 갱신
7. `complete` event를 받으면 stream을 닫고 `getJob()`, candidate spec, review items를 조회
8. `failed` event를 받으면 stream을 닫고 한국어 오류 상태로 전환
9. `cancelled` event를 받으면 stream을 닫고 한국어 취소 상태로 전환

중요 변경:

- M9처럼 `POST /run` 완료 후 SSE를 여는 것이 아니라, `POST /run` 시작 응답 직후 SSE를 연다.
- `runUploadToReviewWorkflow()`는 `run.status === "RUNNING"`을 정상 중간 상태로 처리한다.
- final job status는 `complete` 이후 새 `getJob(jobId)` helper가 호출하는 `GET /jobs/{job_id}` 결과 기준으로 반영한다.
- 기존 optimistic client progress item `creating`, `uploading`, `running`은 유지한다.
- server event가 도착하면 기존 방식대로 중복 event id를 무시한다.

### Web SSE reconnect

브라우저 `EventSource`는 `Last-Event-ID`를 자동으로 보낸다. M10 client는 이 동작을 막지 않는다.

`streamProgressEvents()` 변경 규칙:

- `progress`, `complete`, `failed`, `cancelled` event listener를 등록한다.
- `onerror`에서 즉시 `close()`하지 않는다.
- `onerror` 발생 후 10초 안에 새 `progress` 또는 terminal event가 오면 정상 reconnect로 간주한다.
- 10초 동안 회복되지 않으면 stream을 닫고 "진행 상황 연결이 끊겼습니다." 오류를 전달한다.
- malformed progress payload는 기존처럼 즉시 stream을 닫고 "진행 상황을 해석하지 못했습니다." 오류를 전달한다.

테스트용 `eventSourceFactory`는 기존 interface를 유지하되 terminal event를 추가로 emit할 수 있어야 한다.

## M9 replay UI 호환성

호환 유지 항목:

- `ProgressEventPayload` field set은 그대로 유지한다.
- `event: progress` frame shape는 그대로 유지한다.
- `id: evt_0000` 형식은 그대로 유지한다.
- `event: complete`는 terminal success에서 계속 사용한다.
- web `WorkflowProgressItem` server item shape는 그대로 유지한다.
- `GET /jobs/{job_id}/progress-events`는 terminal artifact 조회 endpoint로 계속 남긴다.

호환 변경 항목:

- `POST /jobs/{job_id}/run` status code는 `200`에서 `202`로 바뀐다.
- `runJob()`은 terminal status가 아니라 `RUNNING`을 받을 수 있다.
- `progress-stream`은 run 완료 전에도 열릴 수 있다.
- failed job도 safe `progress_events` artifact를 가질 수 있다.

## 보안과 민감정보 차단

M10 구현은 아래를 테스트로 고정한다.

- job response에는 `source_image_paths`가 없다.
- progress event와 SSE body에는 `source_image_paths`가 없다.
- progress event와 SSE body에는 local absolute path 조각이 없다.
- progress event와 SSE body에는 `sk-` prefix API key가 없다.
- progress event와 SSE body에는 prompt 또는 raw model output이 없다.
- terminal `failed` reason은 allowlist 값만 사용한다.
- OpenAI SDK exception message는 API response, progress event, manifest review item에 저장하지 않는다.

## 테스트 전략

### API unit tests

`apps/api/tests/test_jobs_api.py`에 추가 또는 수정한다.

- `POST /jobs/{job_id}/run`은 필수 이미지 업로드 후 `202`와 `RUNNING`을 반환한다.
- run 시작 직후 `GET /jobs/{job_id}`는 `RUNNING`을 반환한다.
- 이미 `RUNNING`인 job에 `POST /run`하면 `409 JOB_ALREADY_RUNNING`.
- terminal job에 `POST /run`하면 `409 JOB_RUN_NOT_RESTARTABLE`.
- missing images는 background submit 없이 기존 `409 MISSING_REQUIRED_IMAGES`.
- background worker success 후 manifest는 `APPROVED`이고 기존 analysis artifacts가 저장된다.
- worker success 후 `progress_events` artifact가 있고 첫 event message는 "작업을 시작했습니다."다.
- `progress-stream`은 `RUNNING` 중 live JSONL event를 SSE로 보낸다.
- `progress-stream`은 `Last-Event-ID: evt_0000` 또는 `?after=evt_0000` 이후 event만 보낸다.
- terminal success stream은 `event: complete`를 보낸다.
- adapter failure stream은 `FAILED` progress event와 `event: failed`를 보낸다.
- adapter failure response, job response, progress stream body에 `sk-`, `/private`, `source_image_paths`가 없다.
- `progress-stream`은 run 전에는 기존처럼 `404 ANALYSIS_ARTIFACT_NOT_FOUND`.

테스트 안정성을 위해 default executor를 직접 thread로 기다리지 않는다. route module의 executor를 test double로 monkeypatch한다.

필수 test double:

```python
class CapturingExecutor:
    def __init__(self):
        self.requests = []

    def submit(self, request):
        self.requests.append(request)

    def is_active(self, job_id):
        return any(request.job_id == job_id for request in self.requests)
```

worker 자체는 별도 unit test에서 직접 호출해 success/failure terminal writes를 검증한다.

### Live progress store tests

새 test module 후보:

```text
apps/api/tests/test_live_progress.py
```

검증:

- append는 public field만 JSONL에 저장한다.
- append 후 파일에 line이 존재하고 JSON parse 가능하다.
- duplicate event id 또는 sequence는 중복 저장하지 않는다.
- invalid event id는 예외를 낸다.
- `read_after(None)`은 전체 event를 sequence 순서로 반환한다.
- `read_after("evt_0001")`은 sequence 2 이상만 반환한다.
- malformed trailing line은 read path에서 skip한다.

### Workflow tests

`packages/workflow/tests`에 추가한다.

- `run_mock_workflow(..., progress_event_sink=sink)` 또는 equivalent parameter가 각 progress event를 sink로 전달한다.
- sink가 받은 event와 final state의 `progress_events` event id sequence가 같다.
- sink exception은 workflow invocation을 실패시킨다.

### Web unit tests

`apps/web/src/api/client.test.ts` 수정:

- `runUploadToReviewWorkflow()`는 `POST /run` 후 즉시 `/progress-stream`을 열고, `complete` 후 candidate spec/review items를 조회한다.
- `runJob()`이 `RUNNING`을 반환해도 오류로 보지 않는다.
- `failed` event는 한국어 오류를 reject한다.
- `cancelled` event는 한국어 취소 오류를 reject한다.
- malformed progress payload는 기존 오류를 유지한다.
- duplicate reconnect replay event는 기존 workflow state에서 한 번만 표시된다.

`apps/web/src/app/workflowState.test.ts` 수정:

- server progress event dedupe는 reconnect replay에서도 유지된다.
- failed/cancelled terminal 이후 progress items는 inactive가 된다.

### Harness/E2E

`packages/harness/cleansolve_harness/e2e.py`는 synchronous `POST /run` 완료 가정을 버린다.

새 흐름:

1. `POST /run`에서 `202 RUNNING` 확인
2. `GET /progress-stream` 또는 test helper로 stream drain
3. `complete` terminal event 확인
4. `GET /jobs/{job_id}`로 terminal status 확인
5. 기존 candidate spec, validation report, correction plan, render, export 검증 진행

Playwright `apps/web/e2e/upload-review.spec.ts`는 route mock을 M10 흐름으로 갱신한다.

- `/jobs/job_e2e/run`은 `202`와 `RUNNING`을 반환한다.
- `/jobs/job_e2e/progress-stream`은 progress frame과 complete frame을 반환한다.
- UI는 run 시작 직후 progress panel에 server progress를 표시한다.
- terminal complete 후 "자동 검토 완료"와 candidate preview가 보인다.

추가 browser-level reconnect E2E는 M10에서 필수로 하지 않는다. reconnect는 API unit test와 web unit test로 검증한다.

## M10에서 하지 않을 범위

- Celery, Redis, RQ, 외부 queue 도입
- multi-process worker coordination
- process crash 후 running job 자동 재개
- user-facing cancel endpoint와 cancel button
- cooperative cancellation checks
- background job retry/backoff
- multiple run attempts per job
- progress event schema 확장
- OpenAI planner/eval gate 실제 연결
- dataset evaluation
- renderer output 변경
- visual regression
- PDF export
- raw model output/prompt 저장 또는 UI 노출

## Acceptance criteria

- `POST /jobs/{job_id}/run`은 workflow 완료를 기다리지 않고 `202 RUNNING`을 반환한다.
- background worker가 workflow를 완료하고 기존 analysis artifacts를 저장한다.
- workflow 실행 중 progress event가 durable JSONL에 flush된다.
- `GET /jobs/{job_id}/progress-stream`은 실행 중 event를 live로 전달한다.
- `Last-Event-ID` 또는 `after` cursor로 reconnect replay가 가능하다.
- success, failure, cancelled terminal stream contract가 명확히 지켜진다.
- M9 web progress timeline은 payload 변경 없이 live stream을 표시한다.
- failure path에서 `sk-`, local path, `source_image_paths`, prompt, raw model output이 API/SSE/UI에 노출되지 않는다.
- 기존 full test suite와 M10 추가 tests가 통과한다.
