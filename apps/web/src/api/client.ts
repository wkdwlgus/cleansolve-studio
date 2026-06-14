import type { ReviewItem } from '../types/spec';

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

function normalizeReviewItem(item: ApiReviewItem): ReviewItem {
  return {
    ...item,
    requires_human_review: item.requires_human_review ?? true,
    resolved: item.resolved ?? false
  };
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
