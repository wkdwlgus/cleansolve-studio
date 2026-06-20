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
- 시스템 내장 손글씨 스타일은 metadata와 기본 renderer 규칙 수준이며, 실제 이쁜 손글씨 reference corpus 기반 캘리브레이션이 없다.
- 한글/수식/도형 주석이 한 사람의 손글씨처럼 보이는지 측정하는 style similarity gate가 없다.
- GPT-5.5 기반 ReAct review/correction agent와 score 기반 eval gate가 없다.
- 긴 AI 분석/보정 loop 동안 사용자가 진행 상황을 볼 수 있는 SSE progress UX가 없다.
- PDF export가 없다.
- 상용 품질 raster compositing 검증이 없다.
- browser full export flow와 visual snapshot regression이 없다.
- source-to-spec, render-to-source validation이 fixture prototype 수준이다.

## 남은 gap

- Handwriting Style Lab과 `default_pretty_handwriting v1` renderer calibration
- GPT-5.5 기반 ReAct review/correction workflow
- content/layout/style/visual diff score 기반 eval gate
- job progress SSE stream과 web progress UI
- 실제 OpenAI adapter 결과에 대한 dataset evaluation
- 여러 문제/여러 페이지 입력에 대한 crop 및 matching 평가
- PDF export와 production-grade compositing
- Playwright visual regression과 full browser export flow
- 치수선 endpoint/source alignment의 이미지 기반 검증
