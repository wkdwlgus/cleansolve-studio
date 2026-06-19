# M8 MVP E2E Harness & Release Checklist 상세 설계

## 1. 목적

M8의 목적은 CleanSolve Studio의 MVP 경로가 fixture 기준으로 end-to-end 실행되는지 검증하고, SoT의 MVP 성공 기준을 release 판단에 사용할 수 있는 checklist로 정리하는 것이다.

M8은 제품 기능을 크게 확장하는 milestone이 아니다. M1부터 M7까지 구현된 upload, mock analysis, validation, automatic correction, render, export, web upload flow를 하나의 반복 가능한 harness로 묶어 “현재 MVP가 어디까지 통과하는지”를 드러내는 품질 게이트를 만든다.

## 2. 범위

이번 milestone에서 구현한다.

- pytest 기반 서버 E2E harness
- FastAPI app을 직접 호출하는 upload-to-export E2E 테스트
- fixture 이미지 기반 job 생성, 이미지 업로드, workflow 실행, artifact 조회, render, export, download 검증
- E2E 결과를 구조화하는 harness data model
- review item budget metric 확장
- correction plan metric 추가
- render/export artifact 존재 metric 추가
- SoT MVP 성공 기준 22개를 `Done`, `Partial`, `Fail`로 기록하는 release checklist 문서
- Playwright 기반 웹 smoke E2E
- Playwright test runner 설정
- Playwright가 Vite web app을 띄우고 API 응답은 browser route mock으로 처리하는 local test setup
- README의 M8 검증 명령 문서화
- roadmap M8 상태 갱신

이번 milestone에서 구현하지 않는다.

- OpenAI real adapter의 대량 평가 dataset
- 실제 OpenAI 호출을 Playwright E2E에 포함하는 것
- PDF export
- 상용 품질 raster compositing 개선
- 브라우저에서 export download까지 검증하는 전체 web E2E
- Playwright visual snapshot baseline
- cross-browser matrix
- mobile viewport matrix
- 로그인, 결제, LMS 연동
- 사용자 지정 손글씨 스타일 업로드
- SoT 성공 기준 중 현재 코드가 지원하지 않는 기능을 억지로 Done 처리하는 것

## 3. 원칙

### 3.1 기본 adapter는 mock이다

M8의 기본 E2E harness는 `CLEANSOLVE_ANALYSIS_CLIENT=mock` 경로만 사용한다. `OPENAI_API_KEY`가 없어도 전체 M8 테스트가 통과해야 한다.

Playwright E2E도 실제 OpenAI 네트워크를 호출하지 않는다.

### 3.2 서버 E2E와 브라우저 E2E의 책임을 분리한다

서버 E2E는 artifact와 metric을 깊게 검증한다.

브라우저 E2E는 사용자가 보는 최소 흐름이 깨지지 않았는지 확인한다.

브라우저 E2E는 API 내부 artifact 저장 구조를 직접 검증하지 않는다. 그 검증은 pytest 서버 E2E가 담당한다.

### 3.3 release checklist는 진실해야 한다

SoT 성공 기준이 아직 구현되지 않았으면 `Partial` 또는 `Fail`로 남긴다. M8은 checklist를 좋게 보이게 만드는 작업이 아니라, 실제 상태를 드러내는 작업이다.

### 3.4 fixture는 repository에 이미 있는 작은 이미지 세트를 사용한다

기본 fixture는 `fixtures/manual/m1-image-ingestion/problem.png`와 `fixtures/manual/m1-image-ingestion/teacher_solution.png`를 사용한다.

M8은 사용자가 제공한 대량 image dataset을 git에 추가하지 않는다.

## 4. 서버 E2E Harness 설계

### 4.1 파일 구조

새 파일:

- `packages/harness/cleansolve_harness/e2e.py`
- `packages/harness/tests/test_e2e.py`

수정 파일:

- `packages/harness/cleansolve_harness/__init__.py`
- `packages/harness/cleansolve_harness/metrics.py`
- `packages/harness/cleansolve_harness/runner.py`
- `packages/harness/tests/test_metrics.py`
- `apps/api/tests/test_jobs_api.py`

### 4.2 `E2EHarnessResult`

`packages/harness/cleansolve_harness/e2e.py`에 아래 dataclass를 둔다.

```python
from dataclasses import dataclass


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
```

각 필드는 반드시 실제 API 응답에서 읽은 값으로 채운다. 테스트에서 임의 상수로 채우면 안 된다.

### 4.3 `run_api_upload_to_export_e2e()`

`packages/harness/cleansolve_harness/e2e.py`에 아래 함수를 둔다.

```python
from pathlib import Path
from fastapi.testclient import TestClient


def run_api_upload_to_export_e2e(
    *,
    client: TestClient,
    problem_image_path: Path,
    teacher_solution_image_path: Path,
) -> E2EHarnessResult:
```

동작 순서는 정확히 아래와 같다.

1. `POST /jobs`
2. `POST /jobs/{job_id}/images/problem`
3. `POST /jobs/{job_id}/images/teacher-solution`
4. `POST /jobs/{job_id}/run`
5. `GET /jobs/{job_id}/candidate-spec`
6. `GET /jobs/{job_id}/validation-report`
7. `GET /jobs/{job_id}/correction-plan`
8. `GET /jobs/{job_id}/review-items`
9. `POST /jobs/{job_id}/render`
10. `GET /jobs/{job_id}/rendered-preview`
11. `POST /jobs/{job_id}/export` with JSON body `{"format": "png"}`
12. `GET /jobs/{job_id}/exports/latest`
13. `GET /jobs/{job_id}/exports/{export_id}/download`

실패 처리:

- 각 HTTP 응답은 기대 status code가 아니면 `AssertionError`를 발생시킨다.
- `run` 응답의 `status`는 `APPROVED` 또는 `NEEDS_REVIEW` 또는 `REVISION_REQUIRED`만 허용한다.
- M8 fixture의 현재 기대값은 `APPROVED`다.
- candidate spec artifact id, validation report artifact id, correction plan artifact id, render artifact id, export artifact id가 모두 non-empty string이어야 한다.
- downloaded export bytes는 `b"\x89PNG\r\n\x1a\n"`으로 시작해야 한다.
- `review-items` endpoint의 visible item 수는 0 이상 3 이하이어야 한다.

### 4.4 서버 E2E 테스트

`packages/harness/tests/test_e2e.py`에 아래 테스트를 둔다.

1. `test_api_upload_to_export_e2e_passes_with_manual_fixture`
   - fixture 이미지를 사용한다.
   - `LocalArtifactStore` storage root는 `tmp_path / "jobs"`로 격리한다.
   - `jobs.settings.analysis_client`는 `mock`으로 강제한다.
   - `run_api_upload_to_export_e2e()`를 호출한다.
   - 결과가 아래 조건을 만족해야 한다.

```python
assert result.status == "APPROVED"
assert result.revision_attempts >= 1
assert result.visible_review_item_count == 0
assert result.correction_plan_count >= 1
assert result.export_size_bytes > 0
```

2. `test_api_upload_to_export_e2e_does_not_require_openai_key`
   - `OPENAI_API_KEY` 환경 변수를 제거한다.
   - `CLEANSOLVE_ANALYSIS_CLIENT`를 설정하지 않는다.
   - 같은 E2E를 실행한다.
   - 결과가 `APPROVED`여야 한다.

## 5. Metrics 설계

### 5.1 기존 review budget metric 유지

현재 `HarnessMetrics`와 `summarize_review_budget()`은 유지한다.

### 5.2 `E2EMetrics`

`packages/harness/cleansolve_harness/metrics.py`에 아래 dataclass를 추가한다.

```python
@dataclass(frozen=True)
class E2EMetrics:
    total_jobs: int
    approved_jobs: int
    jobs_with_render_artifact: int
    jobs_with_export_artifact: int
    jobs_with_correction_plan: int
    total_visible_review_items: int
    jobs_over_review_item_budget: int
```

### 5.3 `summarize_e2e_metrics()`

`packages/harness/cleansolve_harness/metrics.py`에 아래 함수를 추가한다.

```python
def summarize_e2e_metrics(metrics: E2EMetrics) -> dict[str, float | bool]:
```

반환 dict는 정확히 아래 key를 가진다.

- `has_jobs`
- `approval_rate`
- `render_artifact_rate`
- `export_artifact_rate`
- `correction_plan_rate`
- `average_visible_review_items`
- `passes_approval_target`
- `passes_render_artifact_target`
- `passes_export_artifact_target`
- `passes_review_item_budget`

목표값:

- `passes_approval_target`: job이 1개 이상이고 `approval_rate == 1.0`
- `passes_render_artifact_target`: job이 1개 이상이고 `render_artifact_rate == 1.0`
- `passes_export_artifact_target`: job이 1개 이상이고 `export_artifact_rate == 1.0`
- `passes_review_item_budget`: job이 1개 이상이고 `jobs_over_review_item_budget == 0`

### 5.4 `collect_e2e_metrics()`

`packages/harness/cleansolve_harness/runner.py`에 아래 함수를 추가한다.

```python
from cleansolve_harness.e2e import E2EHarnessResult


def collect_e2e_metrics(results: list[E2EHarnessResult]) -> E2EMetrics:
```

계산 규칙:

- `approved_jobs`: `status == "APPROVED"`인 result 수
- `jobs_with_render_artifact`: `render_artifact_id`가 non-empty string인 result 수
- `jobs_with_export_artifact`: `export_artifact_id`가 non-empty string이고 `export_size_bytes > 0`인 result 수
- `jobs_with_correction_plan`: `correction_plan_count > 0`인 result 수
- `total_visible_review_items`: 모든 result의 `visible_review_item_count` 합
- `jobs_over_review_item_budget`: `visible_review_item_count > 3`인 result 수

## 6. Playwright E2E 설계

### 6.1 의존성

`apps/web/package.json` devDependencies에 `@playwright/test`를 추가한다.

scripts에 아래를 추가한다.

```json
"test:e2e": "playwright test"
```

Playwright browser install은 repository commit에 포함하지 않는다. 사용자는 필요 시 아래 명령을 실행한다.

```bash
npx --prefix apps/web playwright install chromium
```

### 6.2 Playwright 설정

새 파일:

- `apps/web/playwright.config.ts`

설정값:

- `testDir`: `./e2e`
- `timeout`: `30000`
- `expect.timeout`: `10000`
- `use.baseURL`: `http://127.0.0.1:5173`
- `use.trace`: `retain-on-failure`
- `use.screenshot`: `only-on-failure`
- `projects`: chromium 1개만 사용
- `webServer`: Vite dev server만 자동으로 띄운다.

FastAPI server는 Playwright `globalSetup`에서 띄우지 않는다. M8에서는 더 단순하게 Playwright test 안에서 `page.route()`로 API 응답을 mock한다.

이 결정의 이유:

- 브라우저 smoke의 목적은 web shell이 사용자의 업로드/분석/preview 상태를 올바르게 표시하는지 검증하는 것이다.
- 서버 artifact 깊은 검증은 pytest 서버 E2E가 담당한다.
- Playwright test가 FastAPI server lifecycle을 직접 관리하면 flaky해질 가능성이 커진다.

### 6.3 Playwright fixture data

새 파일:

- `apps/web/e2e/upload-review.spec.ts`

테스트 내부에서 `FileChooser` 또는 `input.setInputFiles()`에 사용할 파일 경로는 repository root 기준 아래 두 개다.

- `../../fixtures/manual/m1-image-ingestion/problem.png`
- `../../fixtures/manual/m1-image-ingestion/teacher_solution.png`

API route mock은 아래 endpoint를 처리한다.

- `POST /jobs`
- `POST /jobs/job_e2e/images/problem`
- `POST /jobs/job_e2e/images/teacher-solution`
- `POST /jobs/job_e2e/run`
- `GET /jobs/job_e2e/candidate-spec`
- `GET /jobs/job_e2e/review-items`

mock candidate spec은 아래 조건을 만족한다.

- `job_id`: `job_e2e`
- `version`: `1`
- `page.width`: `1080`
- `page.height`: `1920`
- elements에 `freehand_dimension_marker` 1개 포함
- 해당 element는 `requires_human_review: false`
- `geometry.visible_strokes`와 `geometry.label_anchor` 포함

mock review items 응답은 `{ "items": [] }`로 한다.

### 6.4 Playwright 테스트 계약

`apps/web/e2e/upload-review.spec.ts`에 아래 테스트를 둔다.

1. `uploads fixture images and renders approved preview`

검증 순서:

1. `page.goto("/")`
2. `aria-label="이미지 업로드"` form이 보인다.
3. 두 file input에 fixture 이미지를 넣는다.
4. `업로드 후 분석 실행` 버튼을 클릭한다.
5. `자동 검토 완료` 텍스트가 보인다.
6. `candidate spec 기반 미리보기 캔버스`가 보인다.
7. `검토 항목 0`이 보인다.
8. `검토 패널`에 “검토할 항목이 없습니다.” 계열 empty state가 보인다.

테스트는 backend 내부 artifact id를 직접 검증하지 않는다.

### 6.5 Playwright 실행 명령

M8 검증 명령은 아래와 같다.

```bash
npm --prefix apps/web run test:e2e
```

browser binary가 없으면 테스트는 실패한다. README에는 `npx --prefix apps/web playwright install chromium`을 사전 준비 명령으로 문서화한다.

CI 설정 파일은 M8에서 추가하지 않는다.

## 7. Release Checklist 설계

새 파일:

- `docs/product/mvp-release-checklist.md`

문서는 한국어로 작성한다.

문서 구조:

1. `# MVP Release Checklist`
2. `## 판정 기준`
3. `## 자동 검증 명령`
4. `## SoT MVP 성공 기준 추적`
5. `## 현재 release 판단`
6. `## 남은 gap`

### 7.1 상태 값

성공 기준 상태는 아래 세 값만 사용한다.

- `Done`
- `Partial`
- `Fail`

### 7.2 SoT 성공 기준 표

SoT의 MVP 성공 기준 중 roadmap에 추적 중인 22개 항목을 그대로 사용한다.

각 행은 아래 열을 가진다.

- `#`
- `성공 기준`
- `상태`
- `근거`
- `검증`
- `남은 작업`

`검증` 열에는 테스트 파일 또는 문서 경로를 쓴다. 자동 테스트가 없으면 `문서 판단`이라고 쓴다.

### 7.3 현재 release 판단

M8 완료 시점의 판정은 `Partial MVP`로 둔다.

이유:

- upload-to-export 경로는 fixture 기준으로 통과한다.
- OpenAI adapter는 opt-in smoke 수준이다.
- PDF export, 상용 품질 raster compositing, 대량 dataset evaluation, browser full export flow는 아직 없다.

문서에 `Production Ready`라고 쓰면 안 된다.

## 8. README와 Roadmap 업데이트

### 8.1 README

`README.md`에 `## MVP E2E Harness` 섹션을 추가한다.

반드시 포함할 명령:

```bash
python -m pytest packages/harness/tests/test_e2e.py -q
npm --prefix apps/web run test:e2e
```

Playwright 준비 명령도 포함한다.

```bash
npx --prefix apps/web playwright install chromium
```

### 8.2 Roadmap

`docs/product/mvp-roadmap.md`에서 M8 상태를 `Done`으로 바꾸는 것은 implementation과 verification이 완료된 뒤에만 한다.

M8 구현 결과에는 아래 문구를 넣는다.

```markdown
구현 결과: pytest 기반 upload-to-export 서버 E2E harness, Playwright 기반 web upload smoke E2E, E2E metrics, MVP release checklist가 구현됨.
```

## 9. 검증 명령

M8 완료 전 반드시 아래 명령을 실행한다.

```bash
python -m pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e
git diff --check
```

Node/Vite version warning은 exit code가 0이면 허용한다.

Playwright browser binary가 없는 환경에서는 `npm --prefix apps/web run test:e2e`가 실패할 수 있다. 그 경우 `npx --prefix apps/web playwright install chromium`을 실행하고 재시도한다.

## 10. Acceptance Criteria

M8은 아래 조건을 모두 만족해야 완료로 본다.

- pytest 서버 E2E가 fixture upload-to-export 전체 경로를 검증한다.
- 서버 E2E 결과가 `E2EHarnessResult`로 구조화된다.
- E2E metrics가 approval, render artifact, export artifact, review budget을 요약한다.
- Playwright smoke E2E가 web upload-to-preview 흐름을 검증한다.
- Playwright test는 실제 OpenAI API를 호출하지 않는다.
- README에 M8 harness 실행법이 한국어로 문서화된다.
- `docs/product/mvp-release-checklist.md`가 SoT 22개 성공 기준의 현재 상태와 gap을 기록한다.
- roadmap의 M8 상태가 Done으로 갱신된다.
- 전체 검증 명령이 통과한다.

## 11. 제외 결정

아래 항목은 M8 이후 필요성이 확인되면 별도 milestone으로 제안한다. 현재는 이름이나 번호를 고정하지 않는다.

- browser full E2E에서 export download까지 검증
- Playwright visual snapshot regression
- OpenAI real adapter dataset evaluation
- multi-page problem crop/matching evaluation
- PDF export
- production-grade compositing quality gate
