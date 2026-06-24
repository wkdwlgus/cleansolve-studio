import type { PrimitiveType, ReviewItem } from '../types/spec';

export type ImageRole = 'problem' | 'teacher_solution';

export interface JobResponse {
  job_id: string;
  status: string;
  revision_attempts?: number;
}

export interface ReviewItemsResponse {
  items: ApiReviewItem[];
}

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

class ProgressStreamError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ProgressStreamError';
  }
}

class ProgressConsumerError extends Error {
  constructor(error: unknown) {
    super(error instanceof Error ? error.message : '진행 상황 처리 중 오류가 발생했습니다.');
    this.name = 'ProgressConsumerError';
  }
}

export interface EditorJob {
  jobId: string;
  status: string;
  revisionAttempts: number;
  reviewItems: ReviewItem[];
}

interface LoadEditorJobOptions {
  baseUrl?: string;
  fetcher?: typeof fetch;
  onPhase?: (phase: 'creating' | 'uploading' | 'running') => void;
  onProgress?: (event: ProgressEventPayload) => void;
  eventSourceFactory?: (url: string) => EventSourceLike;
}

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

export interface SpecPatchRequest {
  client_spec_version: number;
  element_id: string;
  operation: 'update_element';
  changes: Record<string, unknown>;
}

export interface SpecPatchResponse {
  job_id: string;
  candidate_spec: CandidateSpecPreview;
  validation_report: {
    report_id: string;
    passed: boolean;
    issues: Array<Record<string, unknown>>;
  };
  candidate_spec_artifact_id: string;
  validation_report_artifact_id: string;
  latest_analysis_artifact_ids: Record<string, string | null>;
}

export interface RenderedPreviewResponse {
  job_id: string;
  artifact: {
    artifact_id: string;
    type: 'overlay_svg';
    relative_path: string;
    size_bytes: number;
    sha256: string;
    created_at: string;
    candidate_spec_artifact_id: string;
    source_image_artifact_ids: Record<ImageRole, string>;
  };
  svg: string;
}

export interface UploadToReviewInput {
  problemFile: File;
  teacherSolutionFile: File;
}

export interface UploadToReviewResult extends EditorJob {
  candidateSpec: CandidateSpecPreview | null;
  progressEvents: ProgressEventPayload[];
}

type ApiReviewItem = Omit<ReviewItem, 'requires_human_review' | 'resolved'> &
  Partial<Pick<ReviewItem, 'requires_human_review' | 'resolved'>>;

const SAMPLE_REVIEW_ITEMS: ReviewItem[] = [
  {
    element_id: 'sample-marker-1',
    type: 'freehand_dimension_marker',
    requires_human_review: false,
    resolved: true,
    review_reason: 'Endpoint needs operator review.'
  }
];

async function readJson<T>(response: Response, message: string): Promise<T> {
  if (!response.ok) {
    throw new Error(message);
  }

  return response.json();
}

export async function createJob(baseUrl = '', fetcher: typeof fetch = fetch): Promise<JobResponse> {
  const response = await fetcher(`${baseUrl}/jobs`, { method: 'POST' });
  return readJson<JobResponse>(response, '작업을 생성하지 못했습니다.');
}

export async function runJob(jobId: string, baseUrl = '', fetcher: typeof fetch = fetch): Promise<JobResponse> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/run`, { method: 'POST' });
  return readJson<JobResponse>(response, '작업을 실행하지 못했습니다.');
}

export async function getJob(jobId: string, baseUrl = '', fetcher: typeof fetch = fetch): Promise<JobResponse> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}`);
  return readJson<JobResponse>(response, '작업 상태를 불러오지 못했습니다.');
}

export async function getReviewItems(
  jobId: string,
  baseUrl = '',
  fetcher: typeof fetch = fetch
): Promise<ReviewItem[]> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/review-items`);
  const payload = await readJson<ReviewItemsResponse>(response, '검토 항목을 불러오지 못했습니다.');
  return payload.items.map(normalizeReviewItem);
}

export function streamProgressEvents(
  jobId: string,
  {
    baseUrl = '',
    eventSourceFactory = (url: string) => new EventSource(url),
    onProgress,
    onComplete,
    onFailed,
    onCancelled,
    onError
  }: {
    baseUrl?: string;
    eventSourceFactory?: (url: string) => EventSourceLike;
    onProgress?: (event: ProgressEventPayload) => void;
    onComplete?: () => void;
    onFailed?: () => void;
    onCancelled?: () => void;
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
    let payload: ProgressEventPayload;
    try {
      payload = JSON.parse(event.data);
      if (!isProgressEventPayload(payload)) {
        throw new Error('invalid progress event payload');
      }
    } catch {
      close();
      onError?.(new ProgressStreamError('진행 상황을 해석하지 못했습니다.'));
      return;
    }

    try {
      onProgress?.(payload);
    } catch (error) {
      close();
      onError?.(error instanceof Error ? error : new ProgressConsumerError(error));
    }
  });

  source.addEventListener('complete', () => {
    close();
    onComplete?.();
  });

  source.addEventListener('failed', () => {
    close();
    onFailed?.();
  });

  source.addEventListener('cancelled', () => {
    close();
    onCancelled?.();
  });

  source.onerror = () => {};

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
    try {
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
    } catch (error) {
      reject(error instanceof ProgressConsumerError ? error : new ProgressStreamError('진행 상황 연결이 끊겼습니다.'));
    }
  });
}

export async function getProgressEvents(
  jobId: string,
  baseUrl = '',
  fetcher: typeof fetch = fetch
): Promise<ProgressEventPayload[]> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/progress-events`);
  const payload = await readJson<unknown>(response, '진행 상황을 불러오지 못했습니다.');
  if (!isRecord(payload)) {
    return [];
  }
  if (!Array.isArray(payload.events)) {
    return [];
  }
  return payload.events.filter(isProgressEventPayload);
}

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
  const payload = await readJson<unknown>(response, '미리보기 정보를 불러오지 못했습니다.');
  return normalizeCandidateSpec(payload, jobId);
}

export async function patchCandidateSpec(
  jobId: string,
  request: SpecPatchRequest,
  baseUrl = '',
  fetcher: typeof fetch = fetch
): Promise<SpecPatchResponse> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/spec`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  const payload = await readJson<SpecPatchResponse>(response, 'spec 수정사항을 저장하지 못했습니다.');
  return {
    ...payload,
    candidate_spec: normalizeCandidateSpec(payload.candidate_spec, jobId)
  };
}

export async function renderJobPreview(
  jobId: string,
  baseUrl = '',
  fetcher: typeof fetch = fetch
): Promise<RenderedPreviewResponse> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/render`, { method: 'POST' });
  return readJson<RenderedPreviewResponse>(response, '미리보기를 다시 렌더링하지 못했습니다.');
}

export async function getRenderedPreview(
  jobId: string,
  baseUrl = '',
  fetcher: typeof fetch = fetch
): Promise<RenderedPreviewResponse> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/rendered-preview`);
  return readJson<RenderedPreviewResponse>(response, '렌더링된 미리보기를 불러오지 못했습니다.');
}

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
  if (run.status !== 'RUNNING') {
    throw new Error('작업 실행을 시작하지 못했습니다.');
  }
  const progressEvents = await waitForLiveProgress(created.job_id, {
    baseUrl,
    eventSourceFactory,
    onProgress
  });
  const finalJob = await getJob(created.job_id, baseUrl, fetcher);
  const candidateSpec = await getCandidateSpec(created.job_id, baseUrl, fetcher);
  const reviewItems = await getReviewItems(created.job_id, baseUrl, fetcher);

  return {
    jobId: created.job_id,
    status: finalJob.status,
    revisionAttempts: finalJob.revision_attempts ?? 0,
    reviewItems,
    candidateSpec,
    progressEvents
  };
}

async function waitForLiveProgress(
  jobId: string,
  {
    baseUrl,
    eventSourceFactory,
    onProgress
  }: {
    baseUrl: string;
    eventSourceFactory?: (url: string) => EventSourceLike;
    onProgress?: (event: ProgressEventPayload) => void;
  }
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
      onFailed: () => reject(new ProgressStreamError('작업 실행 중 오류가 발생했습니다.')),
      onCancelled: () => reject(new ProgressStreamError('작업이 취소되었습니다.')),
      onError: reject
    });
  });
}

function normalizeReviewItem(item: ApiReviewItem): ReviewItem {
  return {
    ...item,
    requires_human_review: item.requires_human_review ?? true,
    resolved: item.resolved ?? false
  };
}

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
    (isNumberRecord(value.scores) || value.scores === null) &&
    typeof value.next_action === 'string' &&
    typeof value.created_at === 'string'
  );
}

function isNumberRecord(value: unknown): value is Record<string, number> {
  return isRecord(value) && Object.values(value).every(isNumber);
}

function normalizeCandidateSpec(payload: unknown, fallbackJobId: string): CandidateSpecPreview {
  const record = isRecord(payload) ? payload : {};
  const page = isRecord(record.page) ? record.page : {};
  const elements = Array.isArray(record.elements)
    ? record.elements
        .filter(isRecord)
        .filter((element) => typeof element.id === 'string' && typeof element.type === 'string')
        .map((element) => ({
          id: element.id as string,
          type: element.type as PrimitiveType,
          color: typeof element.color === 'string' || element.color === null ? element.color : undefined,
          bbox: Array.isArray(element.bbox) ? element.bbox.filter(isNumber) : undefined,
          geometry: isRecord(element.geometry) ? element.geometry : undefined,
          style: isRecord(element.style) ? element.style : undefined,
          text: typeof element.text === 'string' || element.text === null ? element.text : undefined,
          display_text: typeof element.display_text === 'string' || element.display_text === null ? element.display_text : undefined,
          label: typeof element.label === 'string' || element.label === null ? element.label : undefined
        }))
    : [];

  return {
    job_id: typeof record.job_id === 'string' ? record.job_id : fallbackJobId,
    version: isNumber(record.version) && record.version > 0 ? record.version : 1,
    page: {
      width: isNumber(page.width) && page.width > 0 ? page.width : 0,
      height: isNumber(page.height) && page.height > 0 ? page.height : 0
    },
    elements
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export async function loadEditorJob({ baseUrl = '', fetcher = fetch }: LoadEditorJobOptions = {}): Promise<EditorJob> {
  const created = await createJob(baseUrl, fetcher);
  const run = await runJob(created.job_id, baseUrl, fetcher);
  const reviewItems = await getReviewItems(created.job_id, baseUrl, fetcher);

  return {
    jobId: created.job_id,
    status: run.status,
    revisionAttempts: run.revision_attempts ?? 0,
    reviewItems
  };
}

export function loadSampleEditorJob(): EditorJob {
  return {
    jobId: 'sample',
    status: 'NEEDS_REVIEW',
    revisionAttempts: 1,
    reviewItems: SAMPLE_REVIEW_ITEMS
  };
}
