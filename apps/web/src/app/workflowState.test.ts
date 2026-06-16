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
        {
          phase: 'ready',
          job: {
            jobId: 'job_ready',
            status: 'APPROVED',
            revisionAttempts: 1,
            reviewItems: [],
            candidateSpec: null
          },
          errorMessage: null
        },
        { type: 'reset' }
      )
    ).toEqual(initialWorkflowState);
  });
});
