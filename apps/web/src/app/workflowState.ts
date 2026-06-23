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
