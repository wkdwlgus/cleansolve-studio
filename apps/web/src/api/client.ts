export interface JobResponse {
  job_id: string;
  status: string;
}

export async function createJob(baseUrl = ''): Promise<JobResponse> {
  const response = await fetch(`${baseUrl}/jobs`, { method: 'POST' });
  if (!response.ok) {
    throw new Error('작업을 생성하지 못했습니다.');
  }
  return response.json();
}
