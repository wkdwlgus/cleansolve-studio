import { expect, test } from '@playwright/test';
import path from 'node:path';

const fixtureRoot = path.resolve(process.cwd(), '../../fixtures/manual/m1-image-ingestion');

test('uploads fixture images and renders approved preview', async ({ page }) => {
  await page.route('**/jobs**', async (route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Unexpected E2E route' })
    });
  });

  await page.route('**/jobs', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' })
      });
      return;
    }

    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ job_id: 'job_e2e', status: 'CREATED' })
    });
  });

  await page.route('**/jobs/job_e2e/images/problem', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ ok: true })
    });
  });

  await page.route('**/jobs/job_e2e/images/teacher-solution', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ ok: true })
    });
  });

  await page.route('**/jobs/job_e2e/run', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ job_id: 'job_e2e', status: 'APPROVED', revision_attempts: 1 })
    });
  });

  await page.route('**/jobs/job_e2e/progress-stream', async (route) => {
    await route.fulfill({
      contentType: 'text/event-stream',
      body:
        'id: evt_0000\n' +
        'event: progress\n' +
        'data: {"event_id":"evt_0000","job_id":"job_e2e","sequence":0,"phase":"analysis","status":"CREATED","message":"작업을 시작했습니다.","attempt":0,"max_attempts":2,"scores":null,"next_action":"continue","created_at":"2026-06-23T00:00:00Z"}\n\n' +
        'event: complete\n' +
        'data: {"job_id":"job_e2e","event_count":1}\n\n'
    });
  });

  await page.route('**/jobs/job_e2e/candidate-spec', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: 'job_e2e',
        version: 1,
        page: { width: 800, height: 600 },
        elements: [
          {
            id: 'formula-line-1',
            type: 'formula_line',
            bbox: [120, 160, 360, 48],
            text: 'x^2 + 2x + 1 = (x + 1)^2'
          }
        ]
      })
    });
  });

  await page.route('**/jobs/job_e2e/review-items', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ items: [] })
    });
  });

  await page.goto('/');

  await page.getByLabel('원본 문제 이미지').setInputFiles(path.join(fixtureRoot, 'problem.png'));
  await page.getByLabel('선생님 손풀이 이미지').setInputFiles(path.join(fixtureRoot, 'teacher_solution.png'));
  await page.getByRole('button', { name: '업로드 후 분석 실행' }).click();

  const progressPanel = page.getByLabel('진행 상황');
  await expect(progressPanel).toBeVisible();
  await expect(progressPanel).toHaveAttribute('role', 'status');
  await expect(progressPanel).toHaveAttribute('aria-live', 'polite');
  await expect(progressPanel).toContainText('작업을 시작했습니다.');
  await expect(page.getByText('자동 검토 완료')).toBeVisible();
  await expect(page.getByLabel('candidate spec 기반 미리보기 캔버스')).toBeVisible();
  await expect(page.getByText('검토 항목 0')).toBeVisible();
  await expect(page.getByLabel('검토 패널')).toContainText('사용자 확인이 필요한 항목이 없습니다.');
});
