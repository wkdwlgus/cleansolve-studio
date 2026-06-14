import { describe, expect, it } from 'vitest';
import { loadEditorJob } from './client';

describe('editor API client', () => {
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
