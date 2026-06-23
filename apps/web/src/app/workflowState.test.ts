import { describe, expect, it } from 'vitest';
import { initialWorkflowState, nextWorkflowState } from './workflowState';

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
          candidateSpec: null,
          progressEvents: []
        },
        errorMessage: '이전 오류',
        progressItems: []
      },
      { type: 'start' }
    );

    expect(state).toEqual({
      phase: 'creating',
      job: null,
      errorMessage: null,
      progressItems: [
        { source: 'client', id: 'client-creating', message: '작업을 생성하는 중', status: 'CREATING', active: true }
      ]
    });
  });

  it('stores job when ready', () => {
    const job = {
      jobId: 'job_ready',
      status: 'APPROVED',
      revisionAttempts: 1,
      reviewItems: [],
      candidateSpec: null,
      progressEvents: []
    };

    expect(nextWorkflowState(initialWorkflowState, { type: 'ready', job })).toEqual({
      phase: 'ready',
      job,
      errorMessage: null,
      progressItems: []
    });
  });

  it('stores Korean error message', () => {
    expect(nextWorkflowState(initialWorkflowState, { type: 'error', message: '이미지를 업로드하지 못했습니다.' })).toEqual({
      phase: 'error',
      job: null,
      errorMessage: '이미지를 업로드하지 못했습니다.',
      progressItems: []
    });
  });

  it('resets to idle', () => {
    expect(
      nextWorkflowState(
        {
          phase: 'ready',
          job: {
            jobId: 'job_ready',
            status: 'APPROVED',
            revisionAttempts: 1,
            reviewItems: [],
            candidateSpec: null,
            progressEvents: []
          },
          errorMessage: null,
          progressItems: [
            { source: 'client', id: 'client-running', message: '분석 workflow를 실행하는 중', status: 'RUNNING', active: true }
          ]
        },
        { type: 'reset' }
      )
    ).toEqual(initialWorkflowState);
  });

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
});
