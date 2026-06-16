# M4 Web Upload-to-Review Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 웹에서 두 이미지를 업로드하고 mock workflow 실행 후 candidate spec preview와 review items를 확인할 수 있게 한다.

**Architecture:** 기존 FastAPI endpoint를 그대로 사용하고, 웹 API client가 create/upload/run/fetch 순서를 orchestration한다. App은 upload 중심 상태 머신을 사용하고, EditorCanvas는 candidate spec을 React/Konva preview primitive로 변환한 결과를 표시한다.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Konva/react-konva, existing FastAPI job API.

---

## File Map

- Modify: `apps/web/src/api/client.ts`
  - image upload, candidate spec fetch, upload-to-review orchestration 추가
- Modify: `apps/web/src/api/client.test.ts`
  - upload-to-review client contract 테스트 추가
- Create: `apps/web/src/app/workflowState.ts`
  - upload workflow phase reducer/pure transition
- Create: `apps/web/src/app/workflowState.test.ts`
  - workflow state transition 테스트
- Create: `apps/web/src/editor/candidatePreview.ts`
  - CandidateSpec element를 Konva-friendly preview primitive로 변환
- Create: `apps/web/src/editor/candidatePreview.test.ts`
  - preview helper 테스트
- Modify: `apps/web/src/editor/EditorCanvas.tsx`
  - candidate spec preview 표시
- Modify: `apps/web/src/app/App.tsx`
  - upload form, run button, status/error state 연결
- Modify: `apps/web/src/styles.css`
  - upload panel, status/error UI styling
- Modify: `docs/product/mvp-roadmap.md`
  - M4 완료 상태 갱신

Do not modify API routes in M4 unless tests reveal an actual integration bug.

## Task 1: Web API Client Upload Workflow

**Files:**
- Modify: `apps/web/src/api/client.ts`
- Modify: `apps/web/src/api/client.test.ts`

- [ ] **Step 1: Write failing client test for upload-to-review order**

Add this test to `apps/web/src/api/client.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { loadEditorJob, runUploadToReviewWorkflow } from './client';

describe('editor API client', () => {
  it('uploads both images, runs workflow, and loads candidate spec plus review items', async () => {
    const problemFile = new File(['problem'], 'problem.png', { type: 'image/png' });
    const teacherFile = new File(['teacher'], 'teacher.png', { type: 'image/png' });
    const calls: Array<{ url: string; method: string; bodyType: string; fileName?: string }> = [];
    const fetcher = async (url: string, init?: RequestInit): Promise<Response> => {
      const body = init?.body;
      let fileName: string | undefined;
      if (body instanceof FormData) {
        const uploaded = body.get('file');
        fileName = uploaded instanceof File ? uploaded.name : undefined;
      }
      calls.push({
        url,
        method: init?.method ?? 'GET',
        bodyType: body instanceof FormData ? 'FormData' : 'none',
        fileName
      });

      if (url === '/jobs' && init?.method === 'POST') {
        return Response.json({ job_id: 'job_test', status: 'CREATED' }, { status: 201 });
      }
      if (url === '/jobs/job_test/images/problem' && init?.method === 'POST') {
        return Response.json({ job_id: 'job_test', role: 'problem', artifact: {}, latest_image_artifact_ids: {} }, { status: 201 });
      }
      if (url === '/jobs/job_test/images/teacher-solution' && init?.method === 'POST') {
        return Response.json({ job_id: 'job_test', role: 'teacher_solution', artifact: {}, latest_image_artifact_ids: {} }, { status: 201 });
      }
      if (url === '/jobs/job_test/run' && init?.method === 'POST') {
        return Response.json({ job_id: 'job_test', status: 'NEEDS_REVIEW', revision_attempts: 1 });
      }
      if (url === '/jobs/job_test/candidate-spec') {
        return Response.json({
          job_id: 'job_test',
          version: 1,
          page: { width: 1080, height: 1920 },
          elements: [{ id: 'el_formula', type: 'formula_line', geometry: { anchor: [20, 30] }, text: 'x=1' }]
        });
      }
      if (url === '/jobs/job_test/review-items') {
        return Response.json({
          items: [{ element_id: 'review-1', type: 'formula_line', review_reason: 'Human review required.' }]
        });
      }
      return Response.json({ detail: 'not found' }, { status: 404 });
    };

    const result = await runUploadToReviewWorkflow(
      { problemFile, teacherSolutionFile: teacherFile },
      { fetcher }
    );

    expect(calls).toEqual([
      { url: '/jobs', method: 'POST', bodyType: 'none', fileName: undefined },
      { url: '/jobs/job_test/images/problem', method: 'POST', bodyType: 'FormData', fileName: 'problem.png' },
      { url: '/jobs/job_test/images/teacher-solution', method: 'POST', bodyType: 'FormData', fileName: 'teacher.png' },
      { url: '/jobs/job_test/run', method: 'POST', bodyType: 'none', fileName: undefined },
      { url: '/jobs/job_test/candidate-spec', method: 'GET', bodyType: 'none', fileName: undefined },
      { url: '/jobs/job_test/review-items', method: 'GET', bodyType: 'none', fileName: undefined }
    ]);
    expect(result).toMatchObject({
      jobId: 'job_test',
      status: 'NEEDS_REVIEW',
      revisionAttempts: 1,
      candidateSpec: {
        job_id: 'job_test',
        version: 1,
        page: { width: 1080, height: 1920 }
      }
    });
    expect(result.reviewItems[0]).toMatchObject({
      element_id: 'review-1',
      requires_human_review: true,
      resolved: false
    });
  });
});
```

- [ ] **Step 2: Write failing client test for upload failure short-circuit**

Add this test:

```ts
it('stops workflow when problem image upload fails', async () => {
  const problemFile = new File(['problem'], 'problem.png', { type: 'image/png' });
  const teacherFile = new File(['teacher'], 'teacher.png', { type: 'image/png' });
  const calls: string[] = [];
  const fetcher = async (url: string, init?: RequestInit): Promise<Response> => {
    calls.push(`${init?.method ?? 'GET'} ${url}`);
    if (url === '/jobs' && init?.method === 'POST') {
      return Response.json({ job_id: 'job_test', status: 'CREATED' }, { status: 201 });
    }
    if (url === '/jobs/job_test/images/problem' && init?.method === 'POST') {
      return Response.json({ detail: 'bad upload' }, { status: 400 });
    }
    return Response.json({ detail: 'should not be called' }, { status: 500 });
  };

  await expect(
    runUploadToReviewWorkflow({ problemFile, teacherSolutionFile: teacherFile }, { fetcher })
  ).rejects.toThrow('이미지를 업로드하지 못했습니다.');
  expect(calls).toEqual(['POST /jobs', 'POST /jobs/job_test/images/problem']);
});
```

- [ ] **Step 3: Run client tests to verify RED**

Run:

```bash
npm --prefix apps/web test -- src/api/client.test.ts
```

Expected: FAIL because `runUploadToReviewWorkflow` is not exported.

- [ ] **Step 4: Implement client types and functions**

In `apps/web/src/api/client.ts`, add imports and types:

```ts
import type { PrimitiveType, ReviewItem } from '../types/spec';

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

Add functions:

```ts
export async function uploadImage(
  jobId: string,
  role: ImageRole,
  file: File,
  baseUrl = '',
  fetcher: typeof fetch = fetch
): Promise<void> {
  const formData = new FormData();
  formData.append('file', file);
  const pathRole = role === 'teacher_solution' ? 'teacher-solution' : 'problem';
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/images/${pathRole}`, {
    method: 'POST',
    body: formData
  });
  await readJson<unknown>(response, '이미지를 업로드하지 못했습니다.');
}

export async function getCandidateSpec(
  jobId: string,
  baseUrl = '',
  fetcher: typeof fetch = fetch
): Promise<CandidateSpecPreview> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/candidate-spec`);
  return readJson<CandidateSpecPreview>(response, '미리보기 정보를 불러오지 못했습니다.');
}

export async function runUploadToReviewWorkflow(
  input: UploadToReviewInput,
  { baseUrl = '', fetcher = fetch }: LoadEditorJobOptions = {}
): Promise<UploadToReviewResult> {
  const created = await createJob(baseUrl, fetcher);
  await uploadImage(created.job_id, 'problem', input.problemFile, baseUrl, fetcher);
  await uploadImage(created.job_id, 'teacher_solution', input.teacherSolutionFile, baseUrl, fetcher);
  const run = await runJob(created.job_id, baseUrl, fetcher);
  const candidateSpec = await getCandidateSpec(created.job_id, baseUrl, fetcher);
  const reviewItems = await getReviewItems(created.job_id, baseUrl, fetcher);

  return {
    jobId: created.job_id,
    status: run.status,
    revisionAttempts: run.revision_attempts ?? 0,
    reviewItems,
    candidateSpec
  };
}
```

- [ ] **Step 5: Run client tests to verify GREEN**

Run:

```bash
npm --prefix apps/web test -- src/api/client.test.ts
```

Expected: PASS.

## Task 2: Workflow State

**Files:**
- Create: `apps/web/src/app/workflowState.ts`
- Create: `apps/web/src/app/workflowState.test.ts`

- [ ] **Step 1: Write failing workflow state tests**

Create `apps/web/src/app/workflowState.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { initialWorkflowState, nextWorkflowState } from './workflowState';

describe('workflow state transitions', () => {
  it('moves start to creating and clears previous job and error', () => {
    const state = nextWorkflowState(
      {
        phase: 'error',
        job: {
          jobId: 'job_old',
          status: 'FAILED',
          revisionAttempts: 0,
          reviewItems: [],
          candidateSpec: null
        },
        errorMessage: '이전 오류'
      },
      { type: 'start' }
    );

    expect(state).toEqual({ phase: 'creating', job: null, errorMessage: null });
  });

  it('stores job when ready', () => {
    const job = {
      jobId: 'job_ready',
      status: 'APPROVED',
      revisionAttempts: 1,
      reviewItems: [],
      candidateSpec: null
    };

    expect(nextWorkflowState(initialWorkflowState, { type: 'ready', job })).toEqual({
      phase: 'ready',
      job,
      errorMessage: null
    });
  });

  it('stores Korean error message', () => {
    expect(nextWorkflowState(initialWorkflowState, { type: 'error', message: '이미지를 업로드하지 못했습니다.' })).toEqual({
      phase: 'error',
      job: null,
      errorMessage: '이미지를 업로드하지 못했습니다.'
    });
  });

  it('resets to idle', () => {
    expect(
      nextWorkflowState(
        { phase: 'ready', job: { jobId: 'job_ready', status: 'APPROVED', revisionAttempts: 1, reviewItems: [], candidateSpec: null }, errorMessage: null },
        { type: 'reset' }
      )
    ).toEqual(initialWorkflowState);
  });
});
```

- [ ] **Step 2: Run workflow state tests to verify RED**

Run:

```bash
npm --prefix apps/web test -- src/app/workflowState.test.ts
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement workflow state**

Create `apps/web/src/app/workflowState.ts`:

```ts
import type { UploadToReviewResult } from '../api/client';

export type WorkflowPhase = 'idle' | 'creating' | 'uploading' | 'running' | 'ready' | 'error';

export interface WorkflowViewState {
  phase: WorkflowPhase;
  job: UploadToReviewResult | null;
  errorMessage: string | null;
}

export type WorkflowEvent =
  | { type: 'start' }
  | { type: 'uploading' }
  | { type: 'running' }
  | { type: 'ready'; job: UploadToReviewResult }
  | { type: 'error'; message: string }
  | { type: 'reset' };

export const initialWorkflowState: WorkflowViewState = {
  phase: 'idle',
  job: null,
  errorMessage: null
};

export function nextWorkflowState(_: WorkflowViewState, event: WorkflowEvent): WorkflowViewState {
  switch (event.type) {
    case 'start':
      return { phase: 'creating', job: null, errorMessage: null };
    case 'uploading':
      return { phase: 'uploading', job: null, errorMessage: null };
    case 'running':
      return { phase: 'running', job: null, errorMessage: null };
    case 'ready':
      return { phase: 'ready', job: event.job, errorMessage: null };
    case 'error':
      return { phase: 'error', job: null, errorMessage: event.message };
    case 'reset':
      return initialWorkflowState;
  }
}
```

- [ ] **Step 4: Run workflow state tests to verify GREEN**

Run:

```bash
npm --prefix apps/web test -- src/app/workflowState.test.ts
```

Expected: PASS.

## Task 3: Candidate Preview Helpers

**Files:**
- Create: `apps/web/src/editor/candidatePreview.ts`
- Create: `apps/web/src/editor/candidatePreview.test.ts`

- [ ] **Step 1: Write failing candidate preview tests**

Create `apps/web/src/editor/candidatePreview.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import type { CandidateSpecPreview } from '../api/client';
import { buildPreviewModel, getElementText } from './candidatePreview';

const baseSpec: CandidateSpecPreview = {
  job_id: 'job_preview',
  version: 1,
  page: { width: 1080, height: 1920 },
  elements: []
};

describe('candidate preview helpers', () => {
  it('computes a stable scale and coordinate transform', () => {
    const preview = buildPreviewModel({
      ...baseSpec,
      elements: [
        {
          id: 'el_line',
          type: 'highlight_line',
          geometry: { start: [0, 0], end: [1080, 1920] }
        }
      ]
    });

    expect(preview.stage.width).toBe(760);
    expect(preview.stage.height).toBe(540);
    expect(preview.scale).toBeCloseTo(0.239583, 5);
    expect(preview.primitives[0]).toMatchObject({
      kind: 'line',
      points: [20, 40, 278.75, 500]
    });
  });

  it('uses text priority and skips empty high priority text', () => {
    expect(
      getElementText({
        id: 'el_text',
        type: 'formula_line',
        display_text: 'display',
        text: 'text',
        geometry: { text: 'geometry' },
        label: 'label'
      })
    ).toBe('display');
    expect(
      getElementText({
        id: 'el_empty',
        type: 'formula_line',
        display_text: '',
        text: 'fallback'
      })
    ).toBeNull();
  });

  it('skips malformed primitives without throwing', () => {
    const preview = buildPreviewModel({
      ...baseSpec,
      elements: [
        { id: 'bad_line', type: 'highlight_line', geometry: { start: [true, 0], end: [10, 10] } },
        { id: 'bad_text', type: 'formula_line', geometry: { anchor: ['x', 0] }, text: 'bad' }
      ]
    });

    expect(preview.primitives).toEqual([]);
  });

  it('renders freehand visible strokes and label primitives', () => {
    const preview = buildPreviewModel({
      ...baseSpec,
      elements: [
        {
          id: 'el_marker',
          type: 'freehand_dimension_marker',
          color: 'red',
          geometry: {
            visible_strokes: [{ stroke_id: 's1', points: [[100, 200], [200, 300]] }],
            label: '1',
            label_anchor: [150, 250]
          }
        }
      ]
    });

    expect(preview.primitives).toHaveLength(2);
    expect(preview.primitives[0]).toMatchObject({ kind: 'line', id: 'el_marker:s1', color: 'red' });
    expect(preview.primitives[1]).toMatchObject({ kind: 'text', id: 'el_marker:label', text: '1', color: 'red' });
  });
});
```

- [ ] **Step 2: Run candidate preview tests to verify RED**

Run:

```bash
npm --prefix apps/web test -- src/editor/candidatePreview.test.ts
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement candidate preview helpers**

Create `apps/web/src/editor/candidatePreview.ts` with these exported shapes and functions:

```ts
import type { CandidateSpecElement, CandidateSpecPreview } from '../api/client';

export type PreviewPrimitive =
  | { kind: 'line'; id: string; points: number[]; color: string; strokeWidth: number; closed?: boolean; tension?: number }
  | { kind: 'rect'; id: string; x: number; y: number; width: number; height: number; color: string; strokeWidth: number }
  | { kind: 'circle'; id: string; x: number; y: number; radius: number; color: string; strokeWidth: number; fill?: string }
  | { kind: 'text'; id: string; x: number; y: number; text: string; color: string; fontSize: number };

export interface PreviewModel {
  stage: { width: 760; height: 540 };
  scale: number;
  offset: { x: 20; y: 40 };
  primitives: PreviewPrimitive[];
}
```

Implementation rules:

- stage is always `{ width: 760, height: 540 }`.
- scale is `Math.min(720 / page.width, 460 / page.height)`.
- transform point is `[20 + x * scale, 40 + y * scale]`.
- `_isNumber` must reject booleans.
- invalid primitive returns empty array.
- render supported primitives from the M4 design only.

- [ ] **Step 4: Run candidate preview tests to verify GREEN**

Run:

```bash
npm --prefix apps/web test -- src/editor/candidatePreview.test.ts
```

Expected: PASS.

## Task 4: App and Canvas Integration

**Files:**
- Modify: `apps/web/src/app/App.tsx`
- Modify: `apps/web/src/editor/EditorCanvas.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Update EditorCanvas props and preview rendering**

Modify `EditorCanvasProps`:

```ts
interface EditorCanvasProps {
  candidateSpec: CandidateSpecPreview | null;
  markerReviewItem?: ReviewItem;
}
```

Use `buildPreviewModel(candidateSpec)` when candidateSpec exists.

Render each `PreviewPrimitive`:

- `line` -> `Line`
- `rect` -> `Rect`
- `circle` -> `Circle`
- `text` -> `Text`

Keep existing anchor controls disabled unless `markerReviewItem` allows them. Do not persist edits.

- [ ] **Step 2: Update App state and upload form**

In `App.tsx`:

- Replace automatic `useEffect(loadEditorJob)` behavior.
- Use `useState<File | null>` for problem and teacher files.
- Use `useState(initialWorkflowState)`.
- On submit:
  - dispatch `start`
  - dispatch `uploading`
  - call `runUploadToReviewWorkflow`
  - dispatch `running` immediately before awaiting run is not possible with current single client function, so keep phase `uploading` until result returns.
  - dispatch `ready` or `error`
- Run button disabled when either file missing or phase is creating/uploading/running.
- Pass `workflow.job?.candidateSpec ?? null` to `EditorCanvas`.
- Pass `workflow.job?.reviewItems ?? []` to `ReviewPanel`.

Use these visible labels:

- problem input label: `원본 문제 이미지`
- teacher input label: `선생님 손풀이 이미지`
- run button: `업로드 후 분석 실행`
- reset button: `다시 선택`

- [ ] **Step 3: Add CSS**

Add styles:

```css
.upload-panel { ... }
.upload-grid { ... }
.file-field { ... }
.file-field input { ... }
.file-name { ... }
.workflow-error { ... }
.workflow-actions { ... }
```

Keep layout restrained and consistent with existing shell. Do not add a landing page.

- [ ] **Step 4: Run web build**

Run:

```bash
npm --prefix apps/web run build
```

Expected: PASS.

## Task 5: Verification, Review, Roadmap, Commit

**Files:**
- Modify: `docs/product/mvp-roadmap.md`

- [ ] **Step 1: Run full verification**

Run:

```bash
npm --prefix apps/web test
npm --prefix apps/web run build
python -m pytest -q
git diff --check
```

Expected:

- web tests pass
- web build pass
- Python tests pass
- diff check pass

- [ ] **Step 2: Run Superpowers reviews**

Dispatch two reviewers:

1. Spec compliance reviewer:
   - Compare `docs/superpowers/specs/2026-06-16-web-upload-review-flow-design.md` with implementation.
   - Check scope boundaries, upload flow, preview, review item policy, Korean error states.
2. Code/UI quality reviewer:
   - Check TypeScript type safety, no hidden sample fallback, malformed preview safety, mobile layout, test robustness.

Fix all findings and re-run verification.

- [ ] **Step 3: Update roadmap**

In `docs/product/mvp-roadmap.md`:

- Set M4 status to `Done`.
- Add M4 상세 설계 link.
- Add implementation result summary.
- Update current status summary for web editor shell from Partial to Done for upload-to-review shell.
- Update SoT success criteria:
  - #1 remains Done.
  - #4 remains Done.
  - #9 becomes Done for M4 visible review filtering.
  - #19 becomes Done for M4 HITL visibility shell.

- [ ] **Step 4: Commit and push**

Run:

```bash
git add apps/web docs/product/mvp-roadmap.md docs/superpowers/specs/2026-06-16-web-upload-review-flow-design.md docs/superpowers/plans/2026-06-16-web-upload-review-flow.md
git commit -m "feat(web): connect upload to review flow"
git push origin feat/mvp-roadmap
```
