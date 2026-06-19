# M8 MVP E2E Harness & Release Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build repeatable server and browser E2E harnesses that verify the MVP upload-to-export path and document the current MVP release readiness against SoT criteria.

**Architecture:** `packages/harness` owns server E2E orchestration and metrics. `apps/web` owns Playwright smoke coverage for browser upload-to-preview behavior using route-mocked API responses. `docs/product` owns the Korean release checklist that records what is Done, Partial, or Fail without overstating production readiness.

**Tech Stack:** Python 3.13, pytest, FastAPI TestClient, React/Vite, Playwright Chromium, TypeScript, npm.

---

## File Structure

- Create: `packages/harness/cleansolve_harness/e2e.py`
  - Owns `E2EHarnessResult` and `run_api_upload_to_export_e2e()`.
- Modify: `packages/harness/cleansolve_harness/__init__.py`
  - Exports E2E models and metric helpers.
- Modify: `packages/harness/cleansolve_harness/metrics.py`
  - Adds `E2EMetrics` and `summarize_e2e_metrics()`.
- Modify: `packages/harness/cleansolve_harness/runner.py`
  - Adds `collect_e2e_metrics()`.
- Create: `packages/harness/tests/test_e2e.py`
  - Verifies fixture upload-to-export E2E through the FastAPI app.
- Modify: `packages/harness/tests/test_metrics.py`
  - Verifies E2E metric summaries and aggregation.
- Modify: `apps/web/package.json`
  - Adds `test:e2e` script and `@playwright/test` dev dependency.
- Modify: `apps/web/package-lock.json`
  - Updated by `npm --prefix apps/web install --save-dev @playwright/test`.
- Create: `apps/web/playwright.config.ts`
  - Configures Chromium-only Playwright smoke tests and Vite web server.
- Create: `apps/web/e2e/upload-review.spec.ts`
  - Route-mocks API and verifies browser upload-to-preview smoke flow.
- Create: `docs/product/mvp-release-checklist.md`
  - Korean release checklist for SoT MVP criteria.
- Modify: `README.md`
  - Documents M8 harness commands.
- Modify: `docs/product/mvp-roadmap.md`
  - Marks M8 Done after implementation and verification.

## Task 1: Server Upload-to-Export E2E Harness

**Files:**
- Create: `packages/harness/cleansolve_harness/e2e.py`
- Create: `packages/harness/tests/test_e2e.py`
- Modify: `packages/harness/cleansolve_harness/__init__.py`

- [ ] **Step 1: Write failing server E2E tests**

Create `packages/harness/tests/test_e2e.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from cleansolve_api.main import app
from cleansolve_api.routes import jobs
from cleansolve_harness.e2e import run_api_upload_to_export_e2e


FIXTURE_DIR = Path("fixtures/manual/m1-image-ingestion")


def test_api_upload_to_export_e2e_passes_with_manual_fixture(monkeypatch, tmp_path):
    monkeypatch.setattr(jobs.settings, "storage_root", tmp_path / "jobs")
    monkeypatch.setattr(jobs.settings, "analysis_client", "mock")
    monkeypatch.setattr(jobs.settings, "openai_api_key", None)
    client = TestClient(app)

    result = run_api_upload_to_export_e2e(
        client=client,
        problem_image_path=FIXTURE_DIR / "problem.png",
        teacher_solution_image_path=FIXTURE_DIR / "teacher_solution.png",
    )

    assert result.status == "APPROVED"
    assert result.revision_attempts >= 1
    assert result.visible_review_item_count == 0
    assert result.correction_plan_count >= 1
    assert result.candidate_spec_artifact_id.startswith("spec_")
    assert result.validation_report_artifact_id.startswith("report_")
    assert result.correction_plan_artifact_id.startswith("correction_")
    assert result.render_artifact_id.startswith("render_")
    assert result.export_artifact_id.startswith("export_")
    assert result.export_size_bytes > 0


def test_api_upload_to_export_e2e_does_not_require_openai_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CLEANSOLVE_ANALYSIS_CLIENT", raising=False)
    monkeypatch.setattr(jobs.settings, "storage_root", tmp_path / "jobs")
    monkeypatch.setattr(jobs.settings, "analysis_client", "mock")
    monkeypatch.setattr(jobs.settings, "openai_api_key", None)
    client = TestClient(app)

    result = run_api_upload_to_export_e2e(
        client=client,
        problem_image_path=FIXTURE_DIR / "problem.png",
        teacher_solution_image_path=FIXTURE_DIR / "teacher_solution.png",
    )

    assert result.status == "APPROVED"
    assert result.visible_review_item_count == 0
    assert result.export_size_bytes > 0
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest packages/harness/tests/test_e2e.py -q
```

Expected:

- Fails with `ModuleNotFoundError: No module named 'cleansolve_harness.e2e'`.

- [ ] **Step 3: Implement server E2E harness**

Create `packages/harness/cleansolve_harness/e2e.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
ALLOWED_RUN_STATUSES = {"APPROVED", "NEEDS_REVIEW", "REVISION_REQUIRED"}


@dataclass(frozen=True)
class E2EHarnessResult:
    job_id: str
    status: str
    revision_attempts: int
    visible_review_item_count: int
    correction_plan_count: int
    candidate_spec_artifact_id: str
    validation_report_artifact_id: str
    correction_plan_artifact_id: str
    render_artifact_id: str
    export_artifact_id: str
    export_size_bytes: int


def run_api_upload_to_export_e2e(
    *,
    client: TestClient,
    problem_image_path: Path,
    teacher_solution_image_path: Path,
) -> E2EHarnessResult:
    create_response = client.post("/jobs")
    create_payload = _json_response(create_response, 201)
    job_id = _required_string(create_payload, "job_id")

    _upload_image(
        client=client,
        job_id=job_id,
        path="/images/problem",
        file_path=problem_image_path,
        mime_type="image/png",
    )
    _upload_image(
        client=client,
        job_id=job_id,
        path="/images/teacher-solution",
        file_path=teacher_solution_image_path,
        mime_type="image/png",
    )

    run_payload = _json_response(client.post(f"/jobs/{job_id}/run"), 200)
    status = _required_string(run_payload, "status")
    if status not in ALLOWED_RUN_STATUSES:
        raise AssertionError(f"Unexpected run status: {status}")
    if status != "APPROVED":
        raise AssertionError(f"M8 manual fixture must be APPROVED, got {status}")

    candidate_payload = _json_response(client.get(f"/jobs/{job_id}/candidate-spec"), 200)
    validation_payload = _json_response(client.get(f"/jobs/{job_id}/validation-report"), 200)
    correction_payload = _json_response(client.get(f"/jobs/{job_id}/correction-plan"), 200)
    review_payload = _json_response(client.get(f"/jobs/{job_id}/review-items"), 200)
    render_payload = _json_response(client.post(f"/jobs/{job_id}/render"), 200)
    rendered_payload = _json_response(client.get(f"/jobs/{job_id}/rendered-preview"), 200)
    export_payload = _json_response(
        client.post(f"/jobs/{job_id}/export", json={"format": "png"}),
        200,
    )
    latest_export_payload = _json_response(client.get(f"/jobs/{job_id}/exports/latest"), 200)

    latest_analysis_ids = _required_dict(run_payload, "latest_analysis_artifact_ids")
    candidate_spec_artifact_id = _required_string(latest_analysis_ids, "candidate_spec")
    validation_report_artifact_id = _required_string(latest_analysis_ids, "validation_report")
    correction_plan_artifact_id = _required_string(latest_analysis_ids, "correction_plan")
    render_artifact = _required_dict(render_payload, "artifact")
    rendered_artifact = _required_dict(rendered_payload, "artifact")
    export_artifact = _required_dict(export_payload, "artifact")
    latest_export_artifact = _required_dict(latest_export_payload, "artifact")

    render_artifact_id = _required_string(render_artifact, "artifact_id")
    if _required_string(rendered_artifact, "artifact_id") != render_artifact_id:
        raise AssertionError("rendered-preview returned a different render artifact")

    export_artifact_id = _required_string(export_artifact, "artifact_id")
    if _required_string(latest_export_artifact, "artifact_id") != export_artifact_id:
        raise AssertionError("latest export returned a different export artifact")

    download_response = client.get(f"/jobs/{job_id}/exports/{export_artifact_id}/download")
    if download_response.status_code != 200:
        raise AssertionError(
            f"Expected export download status 200, got {download_response.status_code}: "
            f"{download_response.text}"
        )
    if not download_response.content.startswith(PNG_MAGIC):
        raise AssertionError("Export download did not return PNG bytes")

    review_items = review_payload.get("items")
    if not isinstance(review_items, list):
        raise AssertionError("review-items response must include list field 'items'")
    if len(review_items) > 3:
        raise AssertionError(f"review item budget exceeded: {len(review_items)}")

    correction_plans = correction_payload.get("correction_plans")
    if not isinstance(correction_plans, list):
        raise AssertionError("correction-plan response must include list field 'correction_plans'")

    if candidate_payload.get("job_id") != job_id:
        raise AssertionError("candidate spec job_id mismatch")
    if validation_payload.get("passed") is not True:
        raise AssertionError("validation report must pass for M8 manual fixture")

    return E2EHarnessResult(
        job_id=job_id,
        status=status,
        revision_attempts=_required_int(run_payload, "revision_attempts"),
        visible_review_item_count=len(review_items),
        correction_plan_count=len(correction_plans),
        candidate_spec_artifact_id=candidate_spec_artifact_id,
        validation_report_artifact_id=validation_report_artifact_id,
        correction_plan_artifact_id=correction_plan_artifact_id,
        render_artifact_id=render_artifact_id,
        export_artifact_id=export_artifact_id,
        export_size_bytes=len(download_response.content),
    )


def _upload_image(
    *,
    client: TestClient,
    job_id: str,
    path: str,
    file_path: Path,
    mime_type: str,
) -> None:
    if not file_path.exists():
        raise AssertionError(f"Missing fixture image: {file_path}")
    response = client.post(
        f"/jobs/{job_id}{path}",
        files={"file": (file_path.name, file_path.read_bytes(), mime_type)},
    )
    _json_response(response, 201)


def _json_response(response, expected_status: int) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise AssertionError(
            f"Expected status {expected_status}, got {response.status_code}: {response.text}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise AssertionError("Expected JSON object response")
    return payload


def _required_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise AssertionError(f"Expected dict field: {key}")
    return value


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise AssertionError(f"Expected non-empty string field: {key}")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise AssertionError(f"Expected int field: {key}")
    return value
```

Modify `packages/harness/cleansolve_harness/__init__.py`:

```python
from .e2e import E2EHarnessResult, run_api_upload_to_export_e2e
from .metrics import HarnessMetrics, summarize_review_budget

__all__ = [
    "E2EHarnessResult",
    "HarnessMetrics",
    "run_api_upload_to_export_e2e",
    "summarize_review_budget",
]
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
python -m pytest packages/harness/tests/test_e2e.py -q
```

Expected:

- `2 passed`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add packages/harness/cleansolve_harness/e2e.py packages/harness/cleansolve_harness/__init__.py packages/harness/tests/test_e2e.py
git commit -m "feat(harness): add api upload to export e2e"
```

## Task 2: E2E Metrics

**Files:**
- Modify: `packages/harness/cleansolve_harness/metrics.py`
- Modify: `packages/harness/cleansolve_harness/runner.py`
- Modify: `packages/harness/cleansolve_harness/__init__.py`
- Modify: `packages/harness/tests/test_metrics.py`

- [ ] **Step 1: Write failing E2E metrics tests**

Append to `packages/harness/tests/test_metrics.py`:

```python
from cleansolve_harness.e2e import E2EHarnessResult
from cleansolve_harness.metrics import E2EMetrics, summarize_e2e_metrics
from cleansolve_harness.runner import collect_e2e_metrics


def make_e2e_result(
    *,
    status: str = "APPROVED",
    visible_review_item_count: int = 0,
    correction_plan_count: int = 1,
    render_artifact_id: str = "render_1",
    export_artifact_id: str = "export_1",
    export_size_bytes: int = 128,
) -> E2EHarnessResult:
    return E2EHarnessResult(
        job_id="job_metric",
        status=status,
        revision_attempts=1,
        visible_review_item_count=visible_review_item_count,
        correction_plan_count=correction_plan_count,
        candidate_spec_artifact_id="spec_1",
        validation_report_artifact_id="report_1",
        correction_plan_artifact_id="correction_1",
        render_artifact_id=render_artifact_id,
        export_artifact_id=export_artifact_id,
        export_size_bytes=export_size_bytes,
    )


def test_summarize_e2e_metrics_passes_when_all_targets_are_met():
    summary = summarize_e2e_metrics(
        E2EMetrics(
            total_jobs=1,
            approved_jobs=1,
            jobs_with_render_artifact=1,
            jobs_with_export_artifact=1,
            jobs_with_correction_plan=1,
            total_visible_review_items=0,
            jobs_over_review_item_budget=0,
        )
    )

    assert summary == {
        "has_jobs": True,
        "approval_rate": 1.0,
        "render_artifact_rate": 1.0,
        "export_artifact_rate": 1.0,
        "correction_plan_rate": 1.0,
        "average_visible_review_items": 0.0,
        "passes_approval_target": True,
        "passes_render_artifact_target": True,
        "passes_export_artifact_target": True,
        "passes_review_item_budget": True,
    }


def test_summarize_e2e_metrics_does_not_pass_empty_input():
    summary = summarize_e2e_metrics(
        E2EMetrics(
            total_jobs=0,
            approved_jobs=0,
            jobs_with_render_artifact=0,
            jobs_with_export_artifact=0,
            jobs_with_correction_plan=0,
            total_visible_review_items=0,
            jobs_over_review_item_budget=0,
        )
    )

    assert summary["has_jobs"] is False
    assert summary["passes_approval_target"] is False
    assert summary["passes_render_artifact_target"] is False
    assert summary["passes_export_artifact_target"] is False
    assert summary["passes_review_item_budget"] is False


def test_collect_e2e_metrics_counts_artifacts_corrections_and_review_budget():
    metrics = collect_e2e_metrics(
        [
            make_e2e_result(),
            make_e2e_result(
                status="REVISION_REQUIRED",
                visible_review_item_count=4,
                correction_plan_count=0,
                render_artifact_id="",
                export_artifact_id="",
                export_size_bytes=0,
            ),
        ]
    )

    assert metrics == E2EMetrics(
        total_jobs=2,
        approved_jobs=1,
        jobs_with_render_artifact=1,
        jobs_with_export_artifact=1,
        jobs_with_correction_plan=1,
        total_visible_review_items=4,
        jobs_over_review_item_budget=1,
    )
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest packages/harness/tests/test_metrics.py -q
```

Expected:

- Fails with `ImportError` for `E2EMetrics`, `summarize_e2e_metrics`, or `collect_e2e_metrics`.

- [ ] **Step 3: Implement E2E metrics**

Modify `packages/harness/cleansolve_harness/metrics.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessMetrics:
    total_jobs: int
    jobs_requiring_human_review: int
    total_visible_review_items: int
    jobs_over_review_item_budget: int


@dataclass(frozen=True)
class E2EMetrics:
    total_jobs: int
    approved_jobs: int
    jobs_with_render_artifact: int
    jobs_with_export_artifact: int
    jobs_with_correction_plan: int
    total_visible_review_items: int
    jobs_over_review_item_budget: int


def summarize_review_budget(metrics: HarnessMetrics) -> dict[str, float | bool]:
    hitl_exposure_rate = _rate(metrics.jobs_requiring_human_review, metrics.total_jobs)
    average_review_items = _rate(metrics.total_visible_review_items, metrics.total_jobs)
    has_jobs = metrics.total_jobs > 0

    return {
        "has_jobs": has_jobs,
        "hitl_exposure_rate": hitl_exposure_rate,
        "average_review_items": average_review_items,
        "passes_hitl_target": has_jobs and hitl_exposure_rate <= 0.2,
        "passes_average_review_item_target": has_jobs and average_review_items <= 1,
        "passes_review_item_budget": has_jobs and metrics.jobs_over_review_item_budget == 0,
    }


def summarize_e2e_metrics(metrics: E2EMetrics) -> dict[str, float | bool]:
    has_jobs = metrics.total_jobs > 0
    approval_rate = _rate(metrics.approved_jobs, metrics.total_jobs)
    render_artifact_rate = _rate(metrics.jobs_with_render_artifact, metrics.total_jobs)
    export_artifact_rate = _rate(metrics.jobs_with_export_artifact, metrics.total_jobs)
    correction_plan_rate = _rate(metrics.jobs_with_correction_plan, metrics.total_jobs)
    average_visible_review_items = _rate(
        metrics.total_visible_review_items,
        metrics.total_jobs,
    )

    return {
        "has_jobs": has_jobs,
        "approval_rate": approval_rate,
        "render_artifact_rate": render_artifact_rate,
        "export_artifact_rate": export_artifact_rate,
        "correction_plan_rate": correction_plan_rate,
        "average_visible_review_items": average_visible_review_items,
        "passes_approval_target": has_jobs and approval_rate == 1.0,
        "passes_render_artifact_target": has_jobs and render_artifact_rate == 1.0,
        "passes_export_artifact_target": has_jobs and export_artifact_rate == 1.0,
        "passes_review_item_budget": has_jobs and metrics.jobs_over_review_item_budget == 0,
    }


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
```

Modify `packages/harness/cleansolve_harness/runner.py`:

```python
from __future__ import annotations

from cleansolve_spec.models import CandidateSpec
from cleansolve_spec.validation import visible_review_items

from .e2e import E2EHarnessResult
from .metrics import E2EMetrics, HarnessMetrics

REVIEW_ITEM_BUDGET = 3


def collect_metrics(specs: list[CandidateSpec]) -> HarnessMetrics:
    total_visible_review_items = 0
    jobs_requiring_human_review = 0
    jobs_over_review_item_budget = 0

    for spec in specs:
        visible_review_item_count = len(visible_review_items(spec))
        review_demand_count = sum(1 for element in spec.elements if element.requires_human_review)
        total_visible_review_items += visible_review_item_count

        if review_demand_count > 0:
            jobs_requiring_human_review += 1
        if review_demand_count > REVIEW_ITEM_BUDGET:
            jobs_over_review_item_budget += 1

    return HarnessMetrics(
        total_jobs=len(specs),
        jobs_requiring_human_review=jobs_requiring_human_review,
        total_visible_review_items=total_visible_review_items,
        jobs_over_review_item_budget=jobs_over_review_item_budget,
    )


def collect_e2e_metrics(results: list[E2EHarnessResult]) -> E2EMetrics:
    return E2EMetrics(
        total_jobs=len(results),
        approved_jobs=sum(1 for result in results if result.status == "APPROVED"),
        jobs_with_render_artifact=sum(1 for result in results if bool(result.render_artifact_id)),
        jobs_with_export_artifact=sum(
            1
            for result in results
            if bool(result.export_artifact_id) and result.export_size_bytes > 0
        ),
        jobs_with_correction_plan=sum(1 for result in results if result.correction_plan_count > 0),
        total_visible_review_items=sum(result.visible_review_item_count for result in results),
        jobs_over_review_item_budget=sum(
            1 for result in results if result.visible_review_item_count > REVIEW_ITEM_BUDGET
        ),
    )
```

Modify `packages/harness/cleansolve_harness/__init__.py`:

```python
from .e2e import E2EHarnessResult, run_api_upload_to_export_e2e
from .metrics import (
    E2EMetrics,
    HarnessMetrics,
    summarize_e2e_metrics,
    summarize_review_budget,
)
from .runner import collect_e2e_metrics, collect_metrics

__all__ = [
    "E2EHarnessResult",
    "E2EMetrics",
    "HarnessMetrics",
    "collect_e2e_metrics",
    "collect_metrics",
    "run_api_upload_to_export_e2e",
    "summarize_e2e_metrics",
    "summarize_review_budget",
]
```

- [ ] **Step 4: Run metrics tests to verify GREEN**

Run:

```bash
python -m pytest packages/harness/tests/test_metrics.py packages/harness/tests/test_e2e.py -q
```

Expected:

- All selected tests pass.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add packages/harness/cleansolve_harness packages/harness/tests
git commit -m "feat(harness): add e2e metrics"
```

## Task 3: Playwright Web Smoke E2E

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Create: `apps/web/playwright.config.ts`
- Create: `apps/web/e2e/upload-review.spec.ts`

- [ ] **Step 1: Write Playwright config and smoke test before wiring script**

Create `apps/web/playwright.config.ts`:

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: {
    timeout: 10_000
  },
  use: {
    baseURL: 'http://127.0.0.1:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ],
  webServer: {
    command: 'npm run dev -- --port 5173',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000
  }
});
```

Create `apps/web/e2e/upload-review.spec.ts`:

```typescript
import path from 'node:path';
import { expect, test, type Page, type Route } from '@playwright/test';

const JOB_ID = 'job_e2e';
const webRoot = process.cwd();
const fixtureRoot = path.resolve(webRoot, '../../fixtures/manual/m1-image-ingestion');

test('uploads fixture images and renders approved preview', async ({ page }) => {
  await mockApi(page);

  await page.goto('/');
  await expect(page.getByRole('form', { name: '이미지 업로드' })).toBeVisible();

  await page.getByLabel('원본 문제 이미지').setInputFiles(path.join(fixtureRoot, 'problem.png'));
  await page
    .getByLabel('선생님 손풀이 이미지')
    .setInputFiles(path.join(fixtureRoot, 'teacher_solution.png'));
  await page.getByRole('button', { name: '업로드 후 분석 실행' }).click();

  await expect(page.getByText('자동 검토 완료')).toBeVisible();
  await expect(page.getByLabel('candidate spec 기반 미리보기 캔버스')).toBeVisible();
  await expect(page.getByText('검토 항목 0')).toBeVisible();
  await expect(page.getByLabel('검토 패널')).toContainText('사용자 확인이 필요한 항목이 없습니다.');
});

async function mockApi(page: Page): Promise<void> {
  await page.route('**/jobs**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathName = url.pathname;
    const method = request.method();

    if (method === 'POST' && pathName === '/jobs') {
      await fulfillJson(route, {
        job_id: JOB_ID,
        status: 'CREATED',
        revision_attempts: 0,
        review_items: []
      });
      return;
    }

    if (method === 'POST' && pathName === `/jobs/${JOB_ID}/images/problem`) {
      await fulfillJson(route, { job_id: JOB_ID, role: 'problem' });
      return;
    }

    if (method === 'POST' && pathName === `/jobs/${JOB_ID}/images/teacher-solution`) {
      await fulfillJson(route, { job_id: JOB_ID, role: 'teacher_solution' });
      return;
    }

    if (method === 'POST' && pathName === `/jobs/${JOB_ID}/run`) {
      await fulfillJson(route, {
        job_id: JOB_ID,
        status: 'APPROVED',
        revision_attempts: 1,
        review_items: []
      });
      return;
    }

    if (method === 'GET' && pathName === `/jobs/${JOB_ID}/candidate-spec`) {
      await fulfillJson(route, candidateSpecPayload());
      return;
    }

    if (method === 'GET' && pathName === `/jobs/${JOB_ID}/review-items`) {
      await fulfillJson(route, { items: [] });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: `Unhandled mock route: ${method} ${pathName}` })
    });
  });
}

async function fulfillJson(route: Route, payload: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload)
  });
}

function candidateSpecPayload() {
  return {
    job_id: JOB_ID,
    version: 1,
    page: {
      width: 1080,
      height: 1920
    },
    elements: [
      {
        id: 'el_marker_e2e',
        type: 'freehand_dimension_marker',
        color: 'red',
        bbox: [160, 430, 540, 850],
        geometry: {
          kind: 'freehand_dimension_marker',
          target_anchor_start: [180, 820],
          target_anchor_end: [540, 850],
          visible_strokes: [
            {
              stroke_id: 's1',
              points: [
                [190, 805],
                [210, 720],
                [250, 650]
              ]
            },
            {
              stroke_id: 's2',
              points: [
                [305, 580],
                [370, 510],
                [500, 455]
              ]
            }
          ],
          label: '1',
          label_anchor: [280, 610]
        },
        label: '1',
        requires_human_review: false
      }
    ]
  };
}
```

- [ ] **Step 2: Run Playwright command to verify RED**

Run:

```bash
npm --prefix apps/web run test:e2e
```

Expected:

- Fails because `test:e2e` script does not exist, or `@playwright/test` is not installed.

- [ ] **Step 3: Install Playwright and add script**

Run:

```bash
npm --prefix apps/web install --save-dev @playwright/test
```

Modify `apps/web/package.json` scripts to include:

```json
"test:e2e": "playwright test"
```

The scripts object must contain:

```json
"scripts": {
  "dev": "vite --host 127.0.0.1",
  "build": "tsc && vite build",
  "test": "vitest run",
  "test:e2e": "playwright test"
}
```

- [ ] **Step 4: Ensure Chromium browser is installed if needed**

Run:

```bash
npm --prefix apps/web run test:e2e
```

If output says a browser executable is missing, run:

```bash
npx --prefix apps/web playwright install chromium
```

Then run again:

```bash
npm --prefix apps/web run test:e2e
```

Expected:

- Playwright runs one Chromium test and passes.

- [ ] **Step 5: Run web unit tests and build**

Run:

```bash
npm --prefix apps/web test
npm --prefix apps/web run build
```

Expected:

- Vitest passes.
- Build exits 0. Node/Vite version warnings are acceptable only if exit code is 0.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/playwright.config.ts apps/web/e2e/upload-review.spec.ts
git commit -m "test(web): add playwright upload smoke e2e"
```

## Task 4: MVP Release Checklist and Documentation

**Files:**
- Create: `docs/product/mvp-release-checklist.md`
- Modify: `README.md`
- Modify: `docs/product/mvp-roadmap.md`

- [ ] **Step 1: Write release checklist document**

Create `docs/product/mvp-release-checklist.md`:

```markdown
# MVP Release Checklist

> 이 문서는 CleanSolve Studio의 현재 MVP 상태를 SoT 성공 기준에 맞춰 판단하기 위한 release checklist다. M8 기준 판정은 `Partial MVP`이며, 상용 production ready 판정이 아니다.

## 판정 기준

- `Done`: 현재 코드와 자동 테스트 또는 명확한 문서 근거로 MVP 기준을 만족한다.
- `Partial`: 일부 경로는 구현됐지만 품질, 범위, 자동화, 데이터셋, UX 중 남은 gap이 있다.
- `Fail`: MVP 기준을 만족하는 구현 또는 검증이 없다.

## 자동 검증 명령

```bash
python -m pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e
git diff --check
```

Playwright Chromium이 설치되어 있지 않으면 먼저 실행한다.

```bash
npx --prefix apps/web playwright install chromium
```

## SoT MVP 성공 기준 추적

| # | 성공 기준 | 상태 | 근거 | 검증 | 남은 작업 |
| --- | --- | --- | --- | --- | --- |
| 1 | 원본 문제 이미지와 손풀이 이미지 업로드 | Done | job image artifact upload API와 web upload shell이 있다. | `apps/api/tests/test_image_upload_api.py`, `apps/web/e2e/upload-review.spec.ts` | 없음 |
| 2 | 기본 내장 손글씨 스타일 프리셋 로드 | Done | workflow가 `default_pretty_handwriting` style preset을 로드한다. | `packages/workflow/tests/test_graph.py` | 운영용 스타일 preset registry 확장 |
| 3 | candidate spec 생성 또는 mock spec 처리 | Done | mock adapter와 OpenAI opt-in adapter가 공통 계약으로 candidate spec을 생성한다. | `packages/ai/tests/test_mock_client.py`, `packages/ai/tests/test_openai_client.py` | OpenAI dataset 평가 |
| 4 | candidate spec 기반 overlay preview | Done | renderer와 web preview helper가 candidate spec을 overlay로 표시한다. | `packages/renderer/tests/test_overlay.py`, `apps/web/src/editor/candidatePreview.test.ts` | visual snapshot regression |
| 5 | 하단 풀이 수식/텍스트 재배치 | Partial | `formula_line`과 `text_note` primitive는 있으나 고급 layout 품질 검증은 없다. | `packages/renderer/tests/test_overlay.py` | 실제 풀이 layout dataset 평가 |
| 6 | 도형 위 highlight/arrow/box/label 표시 | Done | MVP primitive renderer coverage가 있다. | `packages/renderer/tests/test_overlay.py` | 더 많은 도형 fixture |
| 7 | dimension_line/dimension_curve endpoint와 anchor 표현 | Done | target anchor와 visible geometry가 renderer에 반영된다. | `packages/renderer/tests/test_overlay.py`, `packages/spec/tests/test_validation.py` | 실제 이미지 기반 위치 평가 |
| 8 | needs_review 항목을 내부 검증 대상으로 관리 | Partial | `needs_review`는 candidate spec에 존재하고 workflow에서 자동 수정된다. | `packages/workflow/tests/test_graph.py` | richer internal validation states |
| 9 | requires_human_review만 사용자 노출 | Done | API와 web helper가 visible review item을 필터링한다. | `apps/api/tests/test_jobs_api.py`, `apps/web/src/editor/reviewHelpers.test.ts` | 없음 |
| 10 | element type별 허용된 수정 방식 | Partial | web interaction policy와 제한된 spec patch API가 있다. | `apps/web/src/editor/interactionPolicy.test.ts`, `apps/api/tests/test_spec_patch.py` | 모든 primitive별 편집 UI |
| 11 | 수정사항 spec patch 저장 | Done | server-side patch API와 artifact 저장이 있다. | `apps/api/tests/test_spec_patch.py`, `apps/api/tests/test_jobs_api.py` | 없음 |
| 12 | 수정 후 deterministic re-render | Done | patch 이후 render artifact 생성 경로가 있다. | `apps/api/tests/test_jobs_api.py` | browser full patch E2E |
| 13 | 최종 이미지 export | Partial | PNG export artifact와 download 경로는 있다. PDF와 상용 품질 compositing은 없다. | `packages/harness/tests/test_e2e.py`, `packages/renderer/tests/test_export_png.py` | PDF export, compositing 품질 |
| 14 | 최소 fixture 기반 harness 통과 | Done | M8 서버 E2E와 Playwright smoke E2E가 fixture 경로를 검증한다. | `packages/harness/tests/test_e2e.py`, `apps/web/e2e/upload-review.spec.ts` | 대량 fixture dataset |
| 15 | freehand-style 치수선 표현 | Done | freehand dimension marker renderer가 visible strokes와 label을 출력한다. | `packages/renderer/tests/test_overlay.py` | 실제 손글씨 다양성 평가 |
| 16 | target anchor와 visible stroke 분리 저장 | Done | candidate spec과 renderer가 target anchor와 visible stroke를 분리한다. | `packages/renderer/tests/test_overlay.py`, `packages/workflow/tests/test_graph.py` | source-image alignment 평가 |
| 17 | 치수선 label을 group 일부로 관리 | Done | label anchor와 label rendering이 dimension group에 포함된다. | `packages/renderer/tests/test_overlay.py` | label collision 검증 |
| 18 | 치수선 endpoint와 span 검증 | Partial | 기본 dimension anchor validation과 workflow self-revision은 있다. | `packages/spec/tests/test_validation.py`, `packages/workflow/tests/test_graph.py` | source-to-spec visual validation |
| 19 | HITL은 기본 경로가 아니라 예외 경로로 동작 | Done | mock workflow fixture는 visible review item 없이 승인된다. | `packages/harness/tests/test_e2e.py` | real adapter exposure rate 평가 |
| 20 | fixture 기준 사용자 검수 노출률과 review item 개수를 측정 | Done | review budget metric과 E2E metric이 있다. | `packages/harness/tests/test_metrics.py` | multi-job dataset metric |
| 21 | 생성/렌더링 결과 자동 검수 | Partial | validation, render inspection, self-revision prototype이 있다. | `packages/workflow/tests/test_graph.py` | 실제 render-to-source validation |
| 22 | 오류 발견 시 correction plan 생성 | Partial | mock workflow는 correction plan을 만들고 저장한다. | `apps/api/tests/test_jobs_api.py`, `packages/harness/tests/test_e2e.py` | broader correction policy |

## 현재 release 판단

현재 상태는 `Partial MVP`다.

가능한 것:

- fixture 기준 원본/손풀이 이미지 업로드
- mock analysis 기반 candidate spec 생성
- validation과 automatic correction
- deterministic SVG preview
- PNG export artifact 생성과 download
- web upload-to-preview smoke flow
- review item budget과 E2E artifact metric 측정

아직 production ready로 보지 않는 이유:

- OpenAI adapter는 opt-in smoke 수준이며 대량 dataset 평가가 없다.
- PDF export가 없다.
- 상용 품질 raster compositing 검증이 없다.
- browser full export flow와 visual snapshot regression이 없다.
- source-to-spec, render-to-source validation이 fixture prototype 수준이다.

## 남은 gap

- 실제 OpenAI adapter 결과에 대한 dataset evaluation
- 여러 문제/여러 페이지 입력에 대한 crop 및 matching 평가
- PDF export와 production-grade compositing
- Playwright visual regression과 full browser export flow
- 치수선 endpoint/source alignment의 이미지 기반 검증
```

- [ ] **Step 2: Update README**

Add this section after `## 로컬 export 흐름` in `README.md`:

```markdown
## MVP E2E Harness

M8 기준 MVP 검증은 서버 E2E와 브라우저 smoke E2E로 나뉩니다.

서버 E2E는 fixture 이미지를 업로드한 뒤 mock analysis, validation, correction plan, render, PNG export, download까지 확인합니다.

```bash
python -m pytest packages/harness/tests/test_e2e.py -q
```

브라우저 smoke E2E는 Playwright로 웹 업로드 화면과 preview 표시 흐름을 확인합니다. 이 테스트는 API 응답을 브라우저 레벨에서 mock하며 OpenAI API를 호출하지 않습니다.

처음 한 번 Chromium browser binary를 설치합니다.

```bash
npx --prefix apps/web playwright install chromium
```

이후 테스트를 실행합니다.

```bash
npm --prefix apps/web run test:e2e
```

현재 MVP release 판단은 [MVP Release Checklist](./docs/product/mvp-release-checklist.md)를 기준으로 합니다.
```

- [ ] **Step 3: Update roadmap M8 status**

Modify `docs/product/mvp-roadmap.md`:

- Change `### M8. MVP E2E Harness & Release Checklist` status from `Partial` to `Done`.
- Add this detail link under the status:

```markdown
상세 설계: [M8 MVP E2E Harness & Release Checklist 상세 설계](../superpowers/specs/2026-06-19-mvp-e2e-harness-release-checklist-design.md)
```

- Add this implementation result:

```markdown
구현 결과: pytest 기반 upload-to-export 서버 E2E harness, Playwright 기반 web upload smoke E2E, E2E metrics, MVP release checklist가 구현됨.
```

- In current state summary, change `E2E harness` from `Partial` to `Done`.
- In SoT MVP success criteria table, change item 14 to `Done`.
- In SoT MVP success criteria table, change item 20 to `Done`.
- Replace `## 다음 추천 작업` text with:

```markdown
## 다음 추천 작업

M8 기준으로 현재 상태는 `Partial MVP`다. 다음 작업은 새 milestone 번호를 미리 고정하지 않고, [MVP Release Checklist](./mvp-release-checklist.md)의 남은 gap 중 하나를 선택해 별도 설계부터 시작한다.

우선순위 후보:

1. 실제 OpenAI adapter 결과에 대한 dataset evaluation
2. production-grade PNG/PDF export와 compositing 품질 개선
3. Playwright visual regression과 browser full export flow
4. 치수선 endpoint/source alignment의 이미지 기반 검증
```

- [ ] **Step 4: Run docs verification**

Run:

```bash
rg -n "MVP E2E Harness|test:e2e|mvp-release-checklist|Partial MVP|M8 MVP" README.md docs/product/mvp-roadmap.md docs/product/mvp-release-checklist.md
git diff --check
```

Expected:

- `rg` finds all documented M8 commands and release checklist links.
- `git diff --check` exits 0.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add README.md docs/product/mvp-roadmap.md docs/product/mvp-release-checklist.md
git commit -m "docs: add mvp release checklist"
```

## Task 5: Full Verification, Reviews, Push, and PR Text

**Files:**
- All changed files from Tasks 1-4.

- [ ] **Step 1: Run full verification**

Run:

```bash
python -m pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e
git diff --check
```

Expected:

- Python tests pass.
- Vitest passes.
- Vite build exits 0. Node/Vite version warnings are acceptable only if exit code is 0.
- Playwright smoke E2E passes in Chromium.
- `git diff --check` exits 0.

- [ ] **Step 2: Request final code review**

Use `superpowers:requesting-code-review` with this scope:

- Server E2E harness correctness.
- E2E metrics correctness.
- Playwright route-mocked web smoke E2E.
- Release checklist truthfulness.
- README and roadmap accuracy.

Reviewer must verify:

- M8 E2E does not require `OPENAI_API_KEY`.
- Playwright test does not call real OpenAI or real FastAPI.
- Server E2E validates upload-to-export artifact path deeply enough.
- Release checklist does not claim production readiness.
- Roadmap does not invent a fixed M9.

- [ ] **Step 3: Fix review findings**

For every Critical or Important finding:

1. Add a failing regression test or documentation assertion.
2. Run the targeted command and observe failure.
3. Apply the smallest fix.
4. Re-run the targeted command.
5. Re-run full verification if shared behavior changed.

- [ ] **Step 4: Push branch**

Run:

```bash
git status --short --branch
git push -u origin feat/mvp-e2e-harness
```

Expected:

- Working tree is clean before push.
- Branch pushes to `origin/feat/mvp-e2e-harness`.

- [ ] **Step 5: Prepare PR title and body**

PR title:

```text
test: add MVP E2E harness and release checklist
```

PR body:

```markdown
## Summary
- Add pytest server E2E harness for fixture upload-to-export verification.
- Add E2E metrics for approval, render/export artifacts, correction plans, and review item budget.
- Add Playwright web smoke E2E for upload-to-preview flow with route-mocked API responses.
- Add Korean MVP release checklist and update README/roadmap for M8.

## Scope
- Uses mock analysis by default.
- Does not call OpenAI in M8 E2E tests.
- Does not add PDF export, visual snapshots, or production compositing.
- Does not define a fixed M9.

## Test Plan
- [ ] `python -m pytest -q`
- [ ] `npm --prefix apps/web test`
- [ ] `npm --prefix apps/web run build`
- [ ] `npm --prefix apps/web run test:e2e`
- [ ] `git diff --check`
```
