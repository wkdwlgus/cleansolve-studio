# Job Progress SSE Replay UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an SSE replay endpoint and web progress timeline so users can see saved workflow progress events after analysis completes.

**Architecture:** Keep `POST /jobs/{job_id}/run` synchronous. Add `GET /jobs/{job_id}/progress-stream` to replay the existing `progress_events` artifact as `text/event-stream`, then teach the web client to consume the stream, fall back to `GET /progress-events`, and render a progress timeline in the editor.

**Tech Stack:** Python 3.11, FastAPI `StreamingResponse`, pytest, React 19, TypeScript, Vite/Vitest, Playwright.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-06-23-job-progress-sse-ui-design.md`

## File Map

- Modify: `apps/api/cleansolve_api/routes/jobs.py`
  - Import `json`.
  - Import `Iterable`.
  - Import `StreamingResponse`.
  - Add `_sse_frame()`.
  - Add `_progress_event_stream()`.
  - Add `GET /jobs/{job_id}/progress-stream`.
- Modify: `apps/api/tests/test_jobs_api.py`
  - Add SSE replay endpoint tests.
  - Add `_sse_frame()` serialization test.
- Modify: `apps/web/src/api/client.ts`
  - Add `ProgressEventPayload`.
  - Add `ProgressEventsResponse`.
  - Add `EventSourceLike`.
  - Add `streamProgressEvents()`.
  - Add `replayProgressEvents()`.
  - Add `getProgressEvents()`.
  - Extend `LoadEditorJobOptions`.
  - Extend `UploadToReviewResult` with `progressEvents`.
  - Update `runUploadToReviewWorkflow()` fallback flow.
- Modify: `apps/web/src/api/client.test.ts`
  - Add injected EventSource test harness.
  - Add stream, replay, fallback, and workflow tests.
- Modify: `apps/web/src/app/workflowState.ts`
  - Add `WorkflowProgressItem`.
  - Add `progressItems` to `WorkflowViewState`.
  - Add `progress-client` and `progress-server` events.
- Modify: `apps/web/src/app/workflowState.test.ts`
  - Add progress timeline state tests.
  - Update existing expected states to include `progressItems`.
- Modify: `apps/web/src/app/App.tsx`
  - Wire `onProgress` into workflow.
  - Render progress panel between upload panel and `EditorCanvas`.
- Modify: `apps/web/src/styles.css`
  - Add progress panel/list styles.
- Modify: `apps/web/e2e/upload-review.spec.ts`
  - Mock `progress-stream`.
  - Assert progress panel message.
- Modify: `docs/product/mvp-roadmap.md`
  - Change M9 status from `Planned` to `In Progress`.

## Contracts To Preserve

- Do not make `POST /jobs/{job_id}/run` asynchronous.
- Do not add background worker, queue, task registry, reconnect cursor, or `Last-Event-ID`.
- Do not change workflow progress event schema or allowlist.
- Do not change OpenAI/GPT/image generation behavior.
- Do not expose `source_image_paths`, local paths, API keys, raw model output, or raw JSON in the visible UI.
- SSE failure must not block candidate spec or review item loading.
- README/user-facing docs remain Korean.

---

### Task 1: API SSE Replay Endpoint

**Files:**
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
- Modify: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Add failing API tests**

In `apps/api/tests/test_jobs_api.py`, add this import near existing imports:

```python
from cleansolve_api.routes.jobs import _sse_frame
```

Append these tests immediately after `test_progress_events_endpoint_returns_404_before_run`:

```python
def test_progress_stream_replays_saved_progress_events_as_sse():
    client = TestClient(app)
    job = client.post("/jobs").json()
    job_id = job["job_id"]
    upload_required_images(client, job_id)
    run_response = client.post(f"/jobs/{job_id}/run")

    response = client.get(f"/jobs/{job_id}/progress-stream")

    assert run_response.status_code == 200
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    body = response.text
    assert "id: evt_0000\n" in body
    assert "event: progress\n" in body
    assert "data:" in body
    assert '"message":"작업을 시작했습니다."' in body
    assert "event: complete\n" in body
    assert '"event_count":' in body
    assert "source_image_paths" not in body


def test_progress_stream_returns_404_before_run():
    client = TestClient(app)
    job = client.post("/jobs").json()

    response = client.get(f"/jobs/{job['job_id']}/progress-stream")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"


def test_sse_frame_serializes_korean_without_ascii_escape():
    frame = _sse_frame(
        event="progress",
        event_id="evt_0000",
        data={"message": "작업을 시작했습니다."},
    )

    assert frame == (
        'id: evt_0000\n'
        'event: progress\n'
        'data: {"message":"작업을 시작했습니다."}\n\n'
    )
    assert "\\uc791" not in frame
    assert frame.endswith("\n\n")
```

- [ ] **Step 2: Run RED API tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests/test_jobs_api.py::test_progress_stream_replays_saved_progress_events_as_sse apps/api/tests/test_jobs_api.py::test_progress_stream_returns_404_before_run apps/api/tests/test_jobs_api.py::test_sse_frame_serializes_korean_without_ascii_escape -q
```

Expected:

- Import fails because `_sse_frame` does not exist, or route test fails with 404.
- Do not edit implementation before seeing the expected failure.

- [ ] **Step 3: Implement SSE helpers and route**

In `apps/api/cleansolve_api/routes/jobs.py`, add imports:

```python
import json
from collections.abc import Iterable
```

Change the response import:

```python
from fastapi.responses import FileResponse, StreamingResponse
```

Add these helpers after `_safe_adapter_reason()`:

```python
def _sse_frame(
    *,
    event: str,
    data: dict[str, object],
    event_id: str | None = None,
) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


def _progress_event_stream(payload: dict[str, object]) -> Iterable[str]:
    events = payload.get("events")
    if not isinstance(events, list):
        events = []
    sorted_events = sorted(
        (event for event in events if isinstance(event, dict)),
        key=lambda event: event.get("sequence", 0),
    )
    for event in sorted_events:
        event_id = event.get("event_id")
        yield _sse_frame(
            event="progress",
            event_id=event_id if isinstance(event_id, str) else None,
            data=event,
        )
    yield _sse_frame(
        event="complete",
        data={
            "job_id": payload.get("job_id", ""),
            "event_count": len(sorted_events),
        },
    )
```

Add this route immediately after `get_progress_events()`:

```python
@router.get("/{job_id}/progress-stream")
def stream_progress_events(job_id: str) -> StreamingResponse:
    payload = _store().read_latest_analysis_payload(job_id, "progress_events")
    return StreamingResponse(
        _progress_event_stream(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 4: Run GREEN API tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests/test_jobs_api.py::test_progress_stream_replays_saved_progress_events_as_sse apps/api/tests/test_jobs_api.py::test_progress_stream_returns_404_before_run apps/api/tests/test_jobs_api.py::test_sse_frame_serializes_korean_without_ascii_escape -q
```

Expected: `3 passed`.

- [ ] **Step 5: Run API regression tests**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests -q
```

Expected: all API tests pass.

- [ ] **Step 6: Commit API SSE endpoint**

Run:

```bash
git add apps/api/cleansolve_api/routes/jobs.py apps/api/tests/test_jobs_api.py
git commit -m "feat(api): replay progress events as sse"
```

---

### Task 2: Web API Progress Stream Client

**Files:**
- Modify: `apps/web/src/api/client.ts`
- Modify: `apps/web/src/api/client.test.ts`

- [ ] **Step 1: Add failing web client tests**

In `apps/web/src/api/client.test.ts`, extend the import list:

```ts
import {
  getCandidateSpec,
  getProgressEvents,
  getRenderedPreview,
  loadEditorJob,
  patchCandidateSpec,
  renderJobPreview,
  replayProgressEvents,
  runUploadToReviewWorkflow,
  streamProgressEvents,
  type EventSourceLike
} from './client';
```

Add this helper near the top of the file after imports:

```ts
class FakeEventSource implements EventSourceLike {
  listeners: Record<string, Array<(event: MessageEvent) => void>> = {};
  onerror: ((event: Event) => void) | null = null;
  closeCount = 0;

  addEventListener(type: string, listener: (event: MessageEvent) => void): void {
    this.listeners[type] = [...(this.listeners[type] ?? []), listener];
  }

  emit(type: string, data: string): void {
    for (const listener of this.listeners[type] ?? []) {
      listener(new MessageEvent(type, { data }));
    }
  }

  fail(): void {
    this.onerror?.(new Event('error'));
  }

  close(): void {
    this.closeCount += 1;
  }
}

const progressEventPayload = {
  event_id: 'evt_0000',
  job_id: 'job_test',
  sequence: 0,
  phase: 'analysis',
  status: 'CREATED',
  message: '작업을 시작했습니다.',
  attempt: 0,
  max_attempts: 2,
  scores: null,
  next_action: 'continue',
  created_at: '2026-06-23T00:00:00Z'
};
```

Append these tests before the existing `throws Korean messages for patch and render failures` test:

```ts
  it('streams progress events with an injected EventSource', () => {
    const source = new FakeEventSource();
    const progressEvents: unknown[] = [];
    let completed = false;

    const unsubscribe = streamProgressEvents('job_test', {
      eventSourceFactory: (url) => {
        expect(url).toBe('/jobs/job_test/progress-stream');
        return source;
      },
      onProgress: (event) => progressEvents.push(event),
      onComplete: () => {
        completed = true;
      }
    });

    source.emit('progress', JSON.stringify(progressEventPayload));
    source.emit('complete', JSON.stringify({ job_id: 'job_test', event_count: 1 }));
    unsubscribe();

    expect(progressEvents).toEqual([progressEventPayload]);
    expect(completed).toBe(true);
    expect(source.closeCount).toBe(1);
  });

  it('closes stream and reports Korean error for malformed progress JSON', () => {
    const source = new FakeEventSource();
    const errors: string[] = [];

    streamProgressEvents('job_test', {
      eventSourceFactory: () => source,
      onError: (error) => errors.push(error.message)
    });

    source.emit('progress', '{bad json');

    expect(errors).toEqual(['진행 상황을 해석하지 못했습니다.']);
    expect(source.closeCount).toBe(1);
  });

  it('replays progress events into an array', async () => {
    const source = new FakeEventSource();
    const seen: string[] = [];
    const promise = replayProgressEvents('job_test', {
      eventSourceFactory: () => source,
      onProgress: (event) => seen.push(event.message)
    });

    source.emit('progress', JSON.stringify(progressEventPayload));
    source.emit('complete', JSON.stringify({ job_id: 'job_test', event_count: 1 }));

    await expect(promise).resolves.toEqual([progressEventPayload]);
    expect(seen).toEqual(['작업을 시작했습니다.']);
    expect(source.closeCount).toBe(1);
  });

  it('fetches progress events and skips malformed event records', async () => {
    const fetcher = async (url: string): Promise<Response> => {
      expect(url).toBe('/jobs/job_test/progress-events');
      return Response.json({
        job_id: 'job_test',
        events: [
          progressEventPayload,
          { event_id: 42, message: 'bad', status: 'BAD', sequence: 1 }
        ]
      });
    };

    await expect(getProgressEvents('job_test', '', fetcher)).resolves.toEqual([progressEventPayload]);
  });
```

In the existing first test `uploads both images, runs workflow, and loads candidate spec plus review items`, add route handling after the `/run` branch:

```ts
      if (url === '/jobs/job_test/progress-events') {
        return Response.json({ job_id: 'job_test', events: [progressEventPayload] });
      }
```

Also add an `eventSourceFactory` that fails the SSE path to force fallback:

```ts
      {
        fetcher,
        eventSourceFactory: () => {
          throw new Error('EventSource unavailable in this test');
        },
        onPhase: (phase) => phases.push(phase)
      }
```

Update the expected call list to include:

```ts
      { url: '/jobs/job_test/progress-events', method: 'GET', bodyType: 'none', fileName: undefined },
```

after the `/run` call and before `/candidate-spec`.

Add this assertion:

```ts
    expect(result.progressEvents).toEqual([progressEventPayload]);
```

- [ ] **Step 2: Run RED web client tests**

Run:

```bash
npm --prefix apps/web test -- src/api/client.test.ts --run
```

Expected:

- Import or type errors because `EventSourceLike`, `streamProgressEvents`, `replayProgressEvents`, and `getProgressEvents` do not exist.

- [ ] **Step 3: Implement progress stream client types and helpers**

In `apps/web/src/api/client.ts`, add after `ReviewItemsResponse`:

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

export interface ProgressEventsResponse {
  job_id: string;
  events: unknown[];
}

export interface EventSourceLike {
  addEventListener(type: string, listener: (event: MessageEvent) => void): void;
  close(): void;
  onerror: ((event: Event) => void) | null;
}
```

Extend `LoadEditorJobOptions`:

```ts
interface LoadEditorJobOptions {
  baseUrl?: string;
  fetcher?: typeof fetch;
  onPhase?: (phase: 'creating' | 'uploading' | 'running') => void;
  onProgress?: (event: ProgressEventPayload) => void;
  eventSourceFactory?: (url: string) => EventSourceLike;
}
```

Extend `UploadToReviewResult`:

```ts
export interface UploadToReviewResult extends EditorJob {
  candidateSpec: CandidateSpecPreview | null;
  progressEvents: ProgressEventPayload[];
}
```

Add these functions after `getReviewItems()`:

```ts
export function streamProgressEvents(
  jobId: string,
  {
    baseUrl = '',
    eventSourceFactory = (url: string) => new EventSource(url),
    onProgress,
    onComplete,
    onError
  }: {
    baseUrl?: string;
    eventSourceFactory?: (url: string) => EventSourceLike;
    onProgress?: (event: ProgressEventPayload) => void;
    onComplete?: () => void;
    onError?: (error: Error) => void;
  } = {}
): () => void {
  let closed = false;
  const source = eventSourceFactory(`${baseUrl}/jobs/${jobId}/progress-stream`);
  const close = () => {
    if (!closed) {
      closed = true;
      source.close();
    }
  };

  source.addEventListener('progress', (event) => {
    try {
      onProgress?.(JSON.parse(event.data) as ProgressEventPayload);
    } catch {
      onError?.(new Error('진행 상황을 해석하지 못했습니다.'));
      close();
    }
  });

  source.addEventListener('complete', () => {
    onComplete?.();
    close();
  });

  source.onerror = () => {
    onError?.(new Error('진행 상황 연결이 끊겼습니다.'));
    close();
  };

  return close;
}

export async function replayProgressEvents(
  jobId: string,
  {
    baseUrl = '',
    eventSourceFactory,
    onProgress
  }: {
    baseUrl?: string;
    eventSourceFactory?: (url: string) => EventSourceLike;
    onProgress?: (event: ProgressEventPayload) => void;
  } = {}
): Promise<ProgressEventPayload[]> {
  return new Promise((resolve, reject) => {
    const events: ProgressEventPayload[] = [];
    streamProgressEvents(jobId, {
      baseUrl,
      eventSourceFactory,
      onProgress: (event) => {
        events.push(event);
        onProgress?.(event);
      },
      onComplete: () => resolve(events),
      onError: reject
    });
  });
}

export async function getProgressEvents(
  jobId: string,
  baseUrl = '',
  fetcher: typeof fetch = fetch
): Promise<ProgressEventPayload[]> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/progress-events`);
  const payload = await readJson<ProgressEventsResponse>(response, '진행 상황을 불러오지 못했습니다.');
  if (!Array.isArray(payload.events)) {
    return [];
  }
  return payload.events.filter(isProgressEventPayload);
}
```

Add this type guard after `normalizeReviewItem()`:

```ts
function isProgressEventPayload(value: unknown): value is ProgressEventPayload {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.event_id === 'string' &&
    typeof value.job_id === 'string' &&
    isNumber(value.sequence) &&
    typeof value.phase === 'string' &&
    typeof value.status === 'string' &&
    typeof value.message === 'string' &&
    isNumber(value.attempt) &&
    isNumber(value.max_attempts) &&
    (isRecord(value.scores) || value.scores === null) &&
    typeof value.next_action === 'string' &&
    typeof value.created_at === 'string'
  );
}
```

- [ ] **Step 4: Update upload-to-review workflow fallback**

Replace `runUploadToReviewWorkflow()` with:

```ts
export async function runUploadToReviewWorkflow(
  input: UploadToReviewInput,
  { baseUrl = '', fetcher = fetch, onPhase, onProgress, eventSourceFactory }: LoadEditorJobOptions = {}
): Promise<UploadToReviewResult> {
  onPhase?.('creating');
  const created = await createJob(baseUrl, fetcher);
  onPhase?.('uploading');
  await uploadImage(created.job_id, 'problem', input.problemFile, baseUrl, fetcher);
  await uploadImage(created.job_id, 'teacher_solution', input.teacherSolutionFile, baseUrl, fetcher);
  onPhase?.('running');
  const run = await runJob(created.job_id, baseUrl, fetcher);
  const progressEvents = await collectProgressEvents(created.job_id, {
    baseUrl,
    fetcher,
    eventSourceFactory,
    onProgress
  });
  const candidateSpec = await getCandidateSpec(created.job_id, baseUrl, fetcher);
  const reviewItems = await getReviewItems(created.job_id, baseUrl, fetcher);

  return {
    jobId: created.job_id,
    status: run.status,
    revisionAttempts: run.revision_attempts ?? 0,
    reviewItems,
    candidateSpec,
    progressEvents
  };
}
```

Add helper after `runUploadToReviewWorkflow()`:

```ts
async function collectProgressEvents(
  jobId: string,
  {
    baseUrl,
    fetcher,
    eventSourceFactory,
    onProgress
  }: {
    baseUrl: string;
    fetcher: typeof fetch;
    eventSourceFactory?: (url: string) => EventSourceLike;
    onProgress?: (event: ProgressEventPayload) => void;
  }
): Promise<ProgressEventPayload[]> {
  try {
    return await replayProgressEvents(jobId, { baseUrl, eventSourceFactory, onProgress });
  } catch {
    try {
      const events = await getProgressEvents(jobId, baseUrl, fetcher);
      for (const event of events) {
        onProgress?.(event);
      }
      return events;
    } catch {
      return [];
    }
  }
}
```

- [ ] **Step 5: Run GREEN web client tests**

Run:

```bash
npm --prefix apps/web test -- src/api/client.test.ts --run
```

Expected: client tests pass.

- [ ] **Step 6: Commit web client stream helpers**

Run:

```bash
git add apps/web/src/api/client.ts apps/web/src/api/client.test.ts
git commit -m "feat(web): consume progress event stream"
```

---

### Task 3: Workflow Progress State

**Files:**
- Modify: `apps/web/src/app/workflowState.ts`
- Modify: `apps/web/src/app/workflowState.test.ts`

- [ ] **Step 1: Update tests for progress state**

In `apps/web/src/app/workflowState.test.ts`, update all existing expected state objects to include `progressItems: []` where no progress items exist.

Add this helper after imports:

```ts
const progressEvent = {
  event_id: 'evt_0000',
  job_id: 'job_test',
  sequence: 0,
  phase: 'analysis',
  status: 'CREATED',
  message: '작업을 시작했습니다.',
  attempt: 0,
  max_attempts: 2,
  scores: null,
  next_action: 'continue',
  created_at: '2026-06-23T00:00:00Z'
};
```

Append these tests:

```ts
  it('tracks client progress steps and keeps only one active item', () => {
    const creating = nextWorkflowState(initialWorkflowState, { type: 'progress-client', step: 'creating' });
    const uploading = nextWorkflowState(creating, { type: 'progress-client', step: 'uploading' });
    const running = nextWorkflowState(uploading, { type: 'progress-client', step: 'running' });

    expect(running.progressItems).toEqual([
      { source: 'client', id: 'client-creating', message: '작업을 생성하는 중', status: 'CREATING', active: false },
      { source: 'client', id: 'client-uploading', message: '이미지를 업로드하는 중', status: 'UPLOADING', active: false },
      { source: 'client', id: 'client-running', message: '분석 workflow를 실행하는 중', status: 'RUNNING', active: true }
    ]);
  });

  it('adds server progress once and ignores duplicate event ids', () => {
    const first = nextWorkflowState(initialWorkflowState, { type: 'progress-server', event: progressEvent });
    const duplicate = nextWorkflowState(first, { type: 'progress-server', event: progressEvent });

    expect(duplicate.progressItems).toHaveLength(1);
    expect(duplicate.progressItems[0]).toMatchObject({
      source: 'server',
      id: 'evt_0000',
      message: '작업을 시작했습니다.',
      status: 'CREATED',
      active: true
    });
  });

  it('marks progress items inactive when ready', () => {
    const withProgress = nextWorkflowState(initialWorkflowState, { type: 'progress-server', event: progressEvent });
    const job = {
      jobId: 'job_ready',
      status: 'APPROVED',
      revisionAttempts: 1,
      reviewItems: [],
      candidateSpec: null,
      progressEvents: [progressEvent]
    };

    expect(nextWorkflowState(withProgress, { type: 'ready', job }).progressItems).toEqual([
      {
        source: 'server',
        id: 'evt_0000',
        message: '작업을 시작했습니다.',
        status: 'CREATED',
        sequence: 0,
        attempt: 0,
        maxAttempts: 2,
        createdAt: '2026-06-23T00:00:00Z',
        active: false
      }
    ]);
  });

  it('preserves progress items on error and clears them on reset', () => {
    const withProgress = nextWorkflowState(initialWorkflowState, { type: 'progress-server', event: progressEvent });
    const error = nextWorkflowState(withProgress, { type: 'error', message: '작업을 완료하지 못했습니다.' });

    expect(error.progressItems).toHaveLength(1);
    expect(error.progressItems[0].active).toBe(false);
    expect(nextWorkflowState(error, { type: 'reset' })).toEqual(initialWorkflowState);
  });
```

- [ ] **Step 2: Run RED workflow state tests**

Run:

```bash
npm --prefix apps/web test -- src/app/workflowState.test.ts --run
```

Expected:

- Type or assertion failures because `progressItems`, `progress-client`, and `progress-server` are not implemented.

- [ ] **Step 3: Implement progress state**

Replace `apps/web/src/app/workflowState.ts` with this content:

```ts
import type { ProgressEventPayload, UploadToReviewResult } from '../api/client';

export type WorkflowPhase = 'idle' | 'creating' | 'uploading' | 'running' | 'ready' | 'error';

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

export interface WorkflowViewState {
  phase: WorkflowPhase;
  job: UploadToReviewResult | null;
  errorMessage: string | null;
  progressItems: WorkflowProgressItem[];
}

export type WorkflowEvent =
  | { type: 'start' }
  | { type: 'creating' }
  | { type: 'uploading' }
  | { type: 'running' }
  | { type: 'progress-client'; step: 'creating' | 'uploading' | 'running' }
  | { type: 'progress-server'; event: ProgressEventPayload }
  | { type: 'ready'; job: UploadToReviewResult }
  | { type: 'error'; message: string }
  | { type: 'reset' };

export const initialWorkflowState: WorkflowViewState = {
  phase: 'idle',
  job: null,
  errorMessage: null,
  progressItems: []
};

const clientProgressItems = {
  creating: {
    source: 'client',
    id: 'client-creating',
    message: '작업을 생성하는 중',
    status: 'CREATING'
  },
  uploading: {
    source: 'client',
    id: 'client-uploading',
    message: '이미지를 업로드하는 중',
    status: 'UPLOADING'
  },
  running: {
    source: 'client',
    id: 'client-running',
    message: '분석 workflow를 실행하는 중',
    status: 'RUNNING'
  }
} as const;

export function nextWorkflowState(state: WorkflowViewState, event: WorkflowEvent): WorkflowViewState {
  switch (event.type) {
    case 'start':
    case 'creating':
      return {
        phase: 'creating',
        job: null,
        errorMessage: null,
        progressItems: [withActive(clientProgressItems.creating)]
      };
    case 'uploading':
      return {
        phase: 'uploading',
        job: null,
        errorMessage: null,
        progressItems: appendClientProgress(state.progressItems, 'uploading')
      };
    case 'running':
      return {
        phase: 'running',
        job: null,
        errorMessage: null,
        progressItems: appendClientProgress(state.progressItems, 'running')
      };
    case 'progress-client':
      return {
        ...state,
        progressItems:
          event.step === 'creating'
            ? [withActive(clientProgressItems.creating)]
            : appendClientProgress(state.progressItems, event.step)
      };
    case 'progress-server':
      return {
        ...state,
        progressItems: appendServerProgress(state.progressItems, event.event)
      };
    case 'ready':
      return {
        phase: 'ready',
        job: event.job,
        errorMessage: null,
        progressItems: state.progressItems.map((item) => ({ ...item, active: false }))
      };
    case 'error':
      return {
        phase: 'error',
        job: null,
        errorMessage: event.message,
        progressItems: state.progressItems.map((item) => ({ ...item, active: false }))
      };
    case 'reset':
      return initialWorkflowState;
  }
}

function appendClientProgress(
  items: WorkflowProgressItem[],
  step: 'uploading' | 'running'
): WorkflowProgressItem[] {
  const item = withActive(clientProgressItems[step]);
  if (items.some((existing) => existing.id === item.id)) {
    return items.map((existing) => ({ ...existing, active: existing.id === item.id }));
  }
  return [...items.map((existing) => ({ ...existing, active: false })), item];
}

function appendServerProgress(items: WorkflowProgressItem[], event: ProgressEventPayload): WorkflowProgressItem[] {
  if (items.some((item) => item.id === event.event_id)) {
    return items;
  }
  return [
    ...items.map((item) => ({ ...item, active: false })),
    {
      source: 'server',
      id: event.event_id,
      message: event.message,
      status: event.status,
      sequence: event.sequence,
      attempt: event.attempt,
      maxAttempts: event.max_attempts,
      createdAt: event.created_at,
      active: true
    }
  ];
}

function withActive<T extends Omit<WorkflowProgressItem, 'active'>>(item: T): T & { active: true } {
  return { ...item, active: true };
}
```

- [ ] **Step 4: Run GREEN workflow state tests**

Run:

```bash
npm --prefix apps/web test -- src/app/workflowState.test.ts --run
```

Expected: workflow state tests pass.

- [ ] **Step 5: Commit workflow progress state**

Run:

```bash
git add apps/web/src/app/workflowState.ts apps/web/src/app/workflowState.test.ts
git commit -m "feat(web): track workflow progress timeline"
```

---

### Task 4: Web Progress Panel UI

**Files:**
- Modify: `apps/web/src/app/App.tsx`
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/e2e/upload-review.spec.ts`

- [ ] **Step 1: Update Playwright test for progress UI**

In `apps/web/e2e/upload-review.spec.ts`, add this route after the `/run` route:

```ts
  await page.route('**/jobs/job_e2e/progress-stream', async (route) => {
    await route.fulfill({
      contentType: 'text/event-stream',
      body:
        'id: evt_0000\n' +
        'event: progress\n' +
        'data: {"event_id":"evt_0000","job_id":"job_e2e","sequence":0,"phase":"analysis","status":"CREATED","message":"작업을 시작했습니다.","attempt":0,"max_attempts":2,"scores":null,"next_action":"continue","created_at":"2026-06-23T00:00:00Z"}\n\n' +
        'event: complete\n' +
        'data: {"job_id":"job_e2e","event_count":1}\n\n'
    });
  });
```

Add these expectations after the click:

```ts
  await expect(page.getByLabel('진행 상황')).toBeVisible();
  await expect(page.getByLabel('진행 상황')).toContainText('작업을 시작했습니다.');
```

- [ ] **Step 2: Run RED web tests**

Run:

```bash
npm --prefix apps/web test -- --run
npm --prefix apps/web run test:e2e -- --project=chromium
```

Expected:

- Unit tests may fail because `App.tsx` still sends only `onPhase`.
- Playwright fails because progress panel is not rendered.

- [ ] **Step 3: Wire progress events in App**

In `apps/web/src/app/App.tsx`, update the import:

```ts
import {
  patchCandidateSpec,
  renderJobPreview,
  runUploadToReviewWorkflow,
  type ProgressEventPayload
} from '../api/client';
```

In `handleSubmit`, update the `runUploadToReviewWorkflow` options object:

```ts
        {
          onPhase: (phase) => setWorkflow((current) => nextWorkflowState(current, { type: phase })),
          onProgress: (progressEvent: ProgressEventPayload) =>
            setWorkflow((current) => nextWorkflowState(current, { type: 'progress-server', event: progressEvent }))
        }
```

Do not add separate `progress-client` calls inside `handleSubmit` or `onPhase`; `start`, `creating`, `uploading`, and `running` already update client progress through `nextWorkflowState()`.

Add this component inside `App.tsx` after `handleSaveEdit()` and before `return`:

```tsx
  const progressItems = workflow.progressItems;
```

Add this JSX between the upload form and `EditorCanvas`:

```tsx
        <section className="progress-panel" aria-label="진행 상황">
          <div className="panel-header">
            <h2>진행 상황</h2>
            <span>{progressItems.length}</span>
          </div>
          {progressItems.length === 0 ? (
            <p className="empty-state">아직 시작된 진행 단계가 없습니다.</p>
          ) : (
            <ol className="progress-list">
              {progressItems.map((item) => (
                <li key={item.id} className={`progress-item${item.active ? ' is-active' : ''}`} aria-current={item.active ? 'step' : undefined}>
                  <strong>{item.message}</strong>
                  <small className="progress-meta">
                    {item.active ? '진행 중' : '완료'}
                    {item.source === 'server' ? ` · 시도 ${item.attempt}/${item.maxAttempts}` : ''}
                  </small>
                </li>
              ))}
            </ol>
          )}
        </section>
```

- [ ] **Step 4: Add progress panel CSS**

In `apps/web/src/styles.css`, add after `.upload-panel` block:

```css
.progress-panel {
  width: min(100%, 760px);
  display: grid;
  gap: 12px;
  margin-bottom: 16px;
  border: 1px solid #c7d2de;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px;
}

.progress-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.progress-item {
  display: grid;
  gap: 4px;
  border-left: 3px solid #cbd5e1;
  padding: 8px 10px;
  background: #f8fafc;
}

.progress-item.is-active {
  border-left-color: #0f766e;
  background: #ecfdf5;
}

.progress-item strong {
  color: #25324a;
  font-size: 13px;
  line-height: 1.35;
}

.progress-meta {
  color: #64748b;
  font-size: 12px;
  line-height: 1.35;
}
```

- [ ] **Step 5: Run GREEN web tests**

Run:

```bash
npm --prefix apps/web test -- --run
npm --prefix apps/web run test:e2e -- --project=chromium
```

Expected: web unit tests and Playwright smoke pass.

- [ ] **Step 6: Commit progress UI**

Run:

```bash
git add apps/web/src/app/App.tsx apps/web/src/styles.css apps/web/e2e/upload-review.spec.ts
git commit -m "feat(web): show job progress timeline"
```

---

### Task 5: Roadmap Status, Verification, Review, Push, PR

**Files:**
- Modify: `docs/product/mvp-roadmap.md`

- [ ] **Step 1: Mark M9 in progress**

In `docs/product/mvp-roadmap.md`, change:

```markdown
상태: Planned
```

under `### M9. Job Progress SSE Replay UI` to:

```markdown
상태: In Progress
```

Do not change M10 status. It must remain:

```markdown
상태: Planned
```

- [ ] **Step 2: Run full verification**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests -q
npm --prefix apps/web test -- --run
npm --prefix apps/web run test:e2e -- --project=chromium
CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/harness/tests -q
git diff --check
```

Expected:

- API tests pass.
- Web unit tests pass.
- Playwright smoke passes.
- API+harness tests pass.
- `git diff --check` has no output.

- [ ] **Step 3: Scope check**

Run:

```bash
git diff --name-only main..HEAD
rg -n "BackgroundTasks|asyncio.create_task|Last-Event-ID|gpt-image-2|Images API|OPENAI_API_KEY|raw model output|source_image_paths" apps/api apps/web packages docs/product docs/superpowers/specs docs/superpowers/plans
```

Expected:

- Changed files are limited to the files listed in this plan plus this plan/spec docs.
- `BackgroundTasks`, `asyncio.create_task`, and `Last-Event-ID` do not appear in runtime code.
- `gpt-image-2`, `Images API`, and `OPENAI_API_KEY` matches are existing settings/docs/tests only, not new runtime behavior.
- `source_image_paths` appears only in existing backend workflow input/assertions, not in SSE body tests or web UI.

- [ ] **Step 4: Commit roadmap status if changed**

Run:

```bash
git add docs/product/mvp-roadmap.md
git commit -m "docs: update progress sse roadmap status"
```

If `docs/product/mvp-roadmap.md` was already committed with M9 `In Progress`, skip this commit and record that no roadmap commit was needed.

- [ ] **Step 5: Request reviews**

Use Superpowers subagent-driven development review gates:

1. Spec compliance reviewer:
   - Compare implementation to `docs/superpowers/specs/2026-06-23-job-progress-sse-ui-design.md`.
   - Verify `POST /run` remains synchronous.
   - Verify `GET /progress-stream` replays stored artifact only.
   - Verify web fallback preserves result loading.
   - Verify M10 background live SSE remains deferred and documented.
2. Code quality reviewer:
   - Review SSE frame serialization, EventSource cleanup, duplicate progress state handling, UI accessibility, and test robustness.

If reviewers find Critical or Important issues, fix them before push.

- [ ] **Step 6: Push branch**

Run:

```bash
git push -u origin feat/job-progress-sse-ui
```

- [ ] **Step 7: Create PR**

Title:

```text
feat: add job progress SSE replay UI
```

Body:

```markdown
## 요약
- 저장된 `progress_events` artifact를 `text/event-stream`으로 replay하는 `GET /jobs/{job_id}/progress-stream` endpoint를 추가했습니다.
- 웹 client가 SSE replay를 소비하고, 실패 시 기존 `GET /progress-events`로 fallback하도록 했습니다.
- editor에 진행 상황 timeline panel을 추가하고 M10 `background job + live SSE` 후속 milestone을 로드맵에 고정했습니다.

## 검증
- [ ] `CLEANSOLVE_API_ENV_FILE=/dev/null env -u CLEANSOLVE_ANALYSIS_CLIENT -u OPENAI_MODEL_ANALYSIS -u OPENAI_ANALYSIS_IMAGE_DETAIL -u OPENAI_ANALYSIS_TIMEOUT_SECONDS pytest apps/api/tests -q`
- [ ] `npm --prefix apps/web test -- --run`
- [ ] `npm --prefix apps/web run test:e2e -- --project=chromium`
- [ ] `CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/harness/tests -q`
- [ ] `git diff --check`

## 참고
- 이번 PR은 `POST /jobs/{job_id}/run`을 비동기화하지 않습니다.
- 실시간 실행 중 event push는 다음 M10 `background job + live SSE`에서 별도 설계/구현합니다.
- OpenAI/GPT/image generation 동작은 변경하지 않습니다.
```
