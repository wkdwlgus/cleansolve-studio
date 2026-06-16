import type { UploadToReviewResult } from '../api/client';

export type WorkflowPhase = 'idle' | 'creating' | 'uploading' | 'running' | 'ready' | 'error';

export interface WorkflowViewState {
  phase: WorkflowPhase;
  job: UploadToReviewResult | null;
  errorMessage: string | null;
}

export type WorkflowEvent =
  | { type: 'start' }
  | { type: 'creating' }
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
    case 'creating':
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
