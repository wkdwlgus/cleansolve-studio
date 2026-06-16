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

export interface UploadToReviewInput {
  problemFile: File;
  teacherSolutionFile: File;
}

export interface UploadToReviewResult extends EditorJob {
  candidateSpec: CandidateSpecPreview | null;
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

export async function getReviewItems(
  jobId: string,
  baseUrl = '',
  fetcher: typeof fetch = fetch
): Promise<ReviewItem[]> {
  const response = await fetcher(`${baseUrl}/jobs/${jobId}/review-items`);
  const payload = await readJson<ReviewItemsResponse>(response, '검토 항목을 불러오지 못했습니다.');
  return payload.items.map(normalizeReviewItem);
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

export async function runUploadToReviewWorkflow(
  input: UploadToReviewInput,
  { baseUrl = '', fetcher = fetch, onPhase }: LoadEditorJobOptions = {}
): Promise<UploadToReviewResult> {
  onPhase?.('creating');
  const created = await createJob(baseUrl, fetcher);
  onPhase?.('uploading');
  await uploadImage(created.job_id, 'problem', input.problemFile, baseUrl, fetcher);
  await uploadImage(created.job_id, 'teacher_solution', input.teacherSolutionFile, baseUrl, fetcher);
  onPhase?.('running');
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

function normalizeReviewItem(item: ApiReviewItem): ReviewItem {
  return {
    ...item,
    requires_human_review: item.requires_human_review ?? true,
    resolved: item.resolved ?? false
  };
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
