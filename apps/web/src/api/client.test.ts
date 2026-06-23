import { describe, expect, it } from 'vitest';
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
        return Response.json(
          { job_id: 'job_test', role: 'problem', artifact: {}, latest_image_artifact_ids: {} },
          { status: 201 }
        );
      }

      if (url === '/jobs/job_test/images/teacher-solution' && init?.method === 'POST') {
        return Response.json(
          { job_id: 'job_test', role: 'teacher_solution', artifact: {}, latest_image_artifact_ids: {} },
          { status: 201 }
        );
      }

      if (url === '/jobs/job_test/run' && init?.method === 'POST') {
        return Response.json({ job_id: 'job_test', status: 'NEEDS_REVIEW', revision_attempts: 1 });
      }

      if (url === '/jobs/job_test/progress-events') {
        return Response.json({ job_id: 'job_test', events: [progressEventPayload] });
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

    const phases: string[] = [];
    const result = await runUploadToReviewWorkflow(
      { problemFile, teacherSolutionFile: teacherFile },
      {
        fetcher,
        eventSourceFactory: () => {
          throw new Error('EventSource unavailable in this test');
        },
        onPhase: (phase) => phases.push(phase)
      }
    );

    expect(calls).toEqual([
      { url: '/jobs', method: 'POST', bodyType: 'none', fileName: undefined },
      { url: '/jobs/job_test/images/problem', method: 'POST', bodyType: 'FormData', fileName: 'problem.png' },
      {
        url: '/jobs/job_test/images/teacher-solution',
        method: 'POST',
        bodyType: 'FormData',
        fileName: 'teacher.png'
      },
      { url: '/jobs/job_test/run', method: 'POST', bodyType: 'none', fileName: undefined },
      { url: '/jobs/job_test/progress-events', method: 'GET', bodyType: 'none', fileName: undefined },
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
    expect(phases).toEqual(['creating', 'uploading', 'running']);
    expect(result.progressEvents).toEqual([progressEventPayload]);
  });

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

  it('normalizes malformed top-level candidate spec payloads', async () => {
    const fetcher = async (): Promise<Response> =>
      Response.json({
        job_id: 42,
        version: 'bad',
        page: { width: 'wide', height: null },
        elements: null
      });

    const spec = await getCandidateSpec('job_test', '', fetcher);

    expect(spec).toEqual({
      job_id: 'job_test',
      version: 1,
      page: { width: 0, height: 0 },
      elements: []
    });
  });

  it('patches candidate spec with JSON body', async () => {
    const calls: Array<{ url: string; method: string; body: unknown }> = [];
    const fetcher = async (url: string, init?: RequestInit): Promise<Response> => {
      calls.push({
        url,
        method: init?.method ?? 'GET',
        body: init?.body ? JSON.parse(init.body as string) : null
      });
      return Response.json({
        job_id: 'job_test',
        candidate_spec: {
          job_id: 'job_test',
          version: 2,
          page: { width: 1080, height: 1920 },
          elements: []
        },
        validation_report: { report_id: 'report_2', passed: true, issues: [] },
        candidate_spec_artifact_id: 'spec_2',
        validation_report_artifact_id: 'report_2',
        latest_analysis_artifact_ids: {
          candidate_spec: 'spec_2',
          validation_report: 'report_2',
          correction_plan: 'correction_1'
        }
      });
    };

    const response = await patchCandidateSpec(
      'job_test',
      {
        client_spec_version: 1,
        element_id: 'el_dimension',
        operation: 'update_element',
        changes: { 'geometry.target_anchor_end': [610, 380] }
      },
      '',
      fetcher
    );

    expect(calls).toEqual([
      {
        url: '/jobs/job_test/spec',
        method: 'PATCH',
        body: {
          client_spec_version: 1,
          element_id: 'el_dimension',
          operation: 'update_element',
          changes: { 'geometry.target_anchor_end': [610, 380] }
        }
      }
    ]);
    expect(response.candidate_spec.version).toBe(2);
  });

  it('renders and reads server SVG previews', async () => {
    const calls: Array<{ url: string; method: string }> = [];
    const fetcher = async (url: string, init?: RequestInit): Promise<Response> => {
      calls.push({ url, method: init?.method ?? 'GET' });
      return Response.json({
        job_id: 'job_test',
        artifact: {
          artifact_id: 'render_1',
          type: 'overlay_svg',
          relative_path: 'artifacts/renders/render_1.svg',
          size_bytes: 11,
          sha256: 'a'.repeat(64),
          created_at: '2026-06-17T00:00:00Z',
          candidate_spec_artifact_id: 'spec_2',
          source_image_artifact_ids: {
            problem: 'img_problem',
            teacher_solution: 'img_teacher'
          }
        },
        svg: '<svg></svg>'
      });
    };

    await renderJobPreview('job_test', '', fetcher);
    await getRenderedPreview('job_test', '', fetcher);

    expect(calls).toEqual([
      { url: '/jobs/job_test/render', method: 'POST' },
      { url: '/jobs/job_test/rendered-preview', method: 'GET' }
    ]);
  });

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
        events: [progressEventPayload, { event_id: 42, message: 'bad', status: 'BAD', sequence: 1 }]
      });
    };

    await expect(getProgressEvents('job_test', '', fetcher)).resolves.toEqual([progressEventPayload]);
  });

  it('throws Korean messages for patch and render failures', async () => {
    const failingFetcher = async (): Promise<Response> => Response.json({ detail: 'bad' }, { status: 400 });

    await expect(
      patchCandidateSpec(
        'job_test',
        {
          client_spec_version: 1,
          element_id: 'el_dimension',
          operation: 'update_element',
          changes: {}
        },
        '',
        failingFetcher
      )
    ).rejects.toThrow('spec 수정사항을 저장하지 못했습니다.');
    await expect(renderJobPreview('job_test', '', failingFetcher)).rejects.toThrow(
      '미리보기를 다시 렌더링하지 못했습니다.'
    );
    await expect(getRenderedPreview('job_test', '', failingFetcher)).rejects.toThrow(
      '렌더링된 미리보기를 불러오지 못했습니다.'
    );
  });

  it('creates, runs, and loads visible review items for an editor job', async () => {
    const calls: Array<{ url: string; method: string }> = [];
    const fetcher = async (url: string, init?: RequestInit): Promise<Response> => {
      calls.push({ url, method: init?.method ?? 'GET' });

      if (url === '/jobs' && init?.method === 'POST') {
        return Response.json({ job_id: 'job_test', status: 'CREATED' }, { status: 201 });
      }

      if (url === '/jobs/job_test/run' && init?.method === 'POST') {
        return Response.json({ job_id: 'job_test', status: 'NEEDS_REVIEW', revision_attempts: 2 });
      }

      if (url === '/jobs/job_test/review-items') {
        return Response.json({
          items: [
            {
              element_id: 'marker-1',
              type: 'freehand_dimension_marker',
              review_reason: 'Endpoint needs operator review.'
            }
          ]
        });
      }

      return Response.json({ detail: 'not found' }, { status: 404 });
    };

    const job = await loadEditorJob({ fetcher });

    expect(calls).toEqual([
      { url: '/jobs', method: 'POST' },
      { url: '/jobs/job_test/run', method: 'POST' },
      { url: '/jobs/job_test/review-items', method: 'GET' }
    ]);
    expect(job.status).toBe('NEEDS_REVIEW');
    expect(job.reviewItems).toEqual([
      {
        element_id: 'marker-1',
        type: 'freehand_dimension_marker',
        requires_human_review: true,
        resolved: false,
        review_reason: 'Endpoint needs operator review.'
      }
    ]);
  });
});
