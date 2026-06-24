# MVP 로드맵

> 이 문서는 `SoT.md`의 MVP 범위와 성공 기준을 기준으로, CleanSolve Studio가 초기 scaffold에서 실제 MVP까지 가기 위해 남은 작업을 정리한다.

## 목적

초기 scaffold는 spec, renderer, mock AI, workflow, API shell, web shell, harness의 기반을 만들었다. 하지만 MVP까지 남은 작업의 순서와 완료 기준이 명확히 보이지 않으면 다음 작업을 고르기 어렵다.

이 로드맵은 다음을 명확히 한다.

- 현재 완료된 것
- 부분적으로만 완료된 것
- 아직 시작하지 않은 것
- milestone별 산출물
- milestone별 acceptance criteria
- 사용자가 제공하면 좋은 입력 파일

## 현재 상태 요약

| 영역 | 상태 | 메모 |
| --- | --- | --- |
| Repository scaffold | Done | monorepo, Python packages, web app, docs, fixture 구조가 있음 |
| Candidate spec model | Partial | MVP primitive registry와 validation 기반은 있으나 모든 primitive별 세부 schema는 아직 얇음. M2 artifact pipeline은 완료됨 |
| Validation | Partial | style, bbox, evidence, dimension anchor, review budget 중심 검증은 있음 |
| Deterministic renderer | Done | M3 MVP primitive SVG overlay와 source image metadata 보존 지원 |
| Mock AI adapter | Done | fixture 기반 candidate spec 생성 경로가 있음 |
| Workflow orchestrator | Partial | LangGraph self-revision prototype에 ReAct review/correction contract, eval gate result, durable progress event artifact, background worker live progress sink가 추가됨 |
| FastAPI job API | Partial | job 생성, 이미지 upload/artifact 저장, async run, live/replay SSE, spec patch, render, export endpoint가 있음 |
| Web editor shell | Done | 이미지 업로드, async workflow 실행, live progress timeline, candidate spec preview, review panel 표시 흐름이 있음 |
| HITL policy | Partial | `requires_human_review=true` 필터와 review budget은 구현됨 |
| Spec patch 저장 | Done | 제한된 server-side spec patch API와 revision history 저장이 구현됨 |
| Re-render after patch | Done | patch 이후 deterministic SVG render artifact 생성/조회 API가 구현됨 |
| Export | Done | PNG export foundation, artifact 저장/조회/download API가 구현됨. PDF는 M6에서 명시적으로 보류함 |
| Real OpenAI adapter | Done | 선택형 `mock|openai` analysis adapter와 opt-in smoke test가 구현됨 |
| E2E harness | Done | M8 서버 E2E harness와 Playwright web upload smoke E2E가 fixture 기반 MVP 경로와 metric을 검증함 |

## Milestone

### M0. Scaffold Foundation

상태: Done

목표:

- SoT 기반 repository 구조를 만든다.
- MVP 핵심 계약을 깨지 않도록 spec, renderer, workflow, API, web, harness의 최소 기반을 만든다.

완료 기준:

- Python 테스트와 웹 테스트가 통과한다.
- README와 주요 docs가 한국어로 작성되어 있다.
- `.env` 파일은 ignore되고 `.env.example`만 커밋된다.
- `OPENAI_MODEL_IMAGE`를 포함한 model/env 설정 위치가 문서화되어 있다.

### M1. Image Ingestion & Artifact Storage

상태: Done

상세 설계: [M1 Image Ingestion & Artifact Storage 상세 설계](../superpowers/specs/2026-06-14-image-ingestion-artifacts-design.md)

구현 결과: local filesystem artifact store, problem/teacher-solution image upload API, manifest persistence, run precondition이 구현됨.

목표:

- 사용자가 원본 문제 이미지와 선생님 손풀이 이미지를 job에 업로드할 수 있다.
- 업로드된 원본 이미지는 최상위 Source of Truth로 저장되고 덮어쓰지 않는다.
- job별 artifact manifest를 만든다.

주요 산출물:

- `POST /jobs/{job_id}/images/problem`
- `POST /jobs/{job_id}/images/teacher-solution`
- local artifact storage interface
- job artifact manifest model
- 이미지 mime/type/size validation
- fixture image 저장 위치

완료 기준:

- 원본 문제 이미지와 손풀이 이미지가 job별로 저장된다.
- 같은 artifact를 다시 업로드할 때 원본을 덮어쓰지 않거나 명시적 versioning을 한다.
- API 테스트가 upload, invalid file, unknown job, artifact lookup을 검증한다.
- README 또는 API docs에 로컬 업로드 흐름이 설명된다.

필요하면 좋은 사용자 제공 파일:

- 원본 문제 이미지 1장
- 같은 문제에 대한 선생님 손풀이 이미지 1장

없으면 synthetic PNG fixture로 시작한다.

### M2. Candidate Spec Pipeline

상태: Done

상세 설계: [M2 Candidate Spec Pipeline 상세 설계](../superpowers/specs/2026-06-16-candidate-spec-pipeline-design.md)

구현 결과: uploaded image artifact id를 mock workflow candidate spec source로 연결하고, candidate spec, validation report, correction plan을 job analysis artifact로 저장/조회하는 API가 구현됨.

목표:

- source image artifact를 입력으로 받아 candidate spec, validation report, correction input을 산출하는 pipeline을 만든다.
- mock adapter와 real adapter가 같은 interface를 사용하게 한다.

주요 산출물:

- image artifact reference를 받는 analysis request model
- candidate spec artifact 저장
- validation report artifact 저장
- correction plan artifact 저장
- adapter selection 설정

완료 기준:

- mock pipeline이 uploaded artifact를 참조해 candidate spec을 생성한다.
- candidate spec은 job artifact로 저장된다.
- validation report가 저장되고 API에서 조회 가능하다.
- 실제 OpenAI adapter 없이도 fixture E2E가 통과한다.

### M3. Renderer Coverage Expansion

상태: Done

상세 설계: [M3 Renderer Coverage Expansion 상세 설계](../superpowers/specs/2026-06-16-renderer-coverage-expansion-design.md)

구현 결과: `formula_line`, `text_note`, `highlight_line`, `highlight_curve`, `arrow`, `box`, `circle`, `point_label`, `segment_label`, `dimension_line`, `dimension_curve`, `freehand_dimension_marker`의 deterministic SVG overlay 출력이 구현됨. Renderer는 원본 image artifact id를 SVG metadata로 보존하고, malformed geometry와 M3 범위 밖 primitive는 crash 없이 skip한다.

목표:

- MVP primitive를 deterministic preview로 충분히 보여준다.
- 원본 이미지를 변경하지 않고 overlay만 생성한다.

우선순위 primitive:

1. `formula_line`
2. `text_note`
3. `highlight_line`
4. `highlight_curve`
5. `arrow`
6. `box`
7. `circle`
8. `point_label`
9. `segment_label`
10. `dimension_line`
11. `dimension_curve`
12. `freehand_dimension_marker`

완료 기준:

- 각 MVP primitive가 최소 SVG output을 가진다.
- unsupported/malformed geometry는 renderer crash 없이 validation issue 또는 skip policy로 처리된다.
- renderer test가 주요 primitive의 output contract를 검증한다.
- original image reference는 output metadata로 유지되고 원본 파일은 변경되지 않는다.

### M4. Web Upload-to-Review Flow

상태: Done

상세 설계: [M4 Web Upload-to-Review Flow 상세 설계](../superpowers/specs/2026-06-16-web-upload-review-flow-design.md)

구현 결과: 웹에서 원본 문제 이미지와 선생님 손풀이 이미지를 선택해 업로드하고, mock workflow 실행 후 candidate spec 기반 Konva preview와 review items를 표시하는 흐름이 구현됨. API 실패는 sample fallback으로 숨기지 않고 한국어 오류 상태로 표시한다.

목표:

- 웹에서 job 생성, 이미지 업로드, workflow 실행, preview 표시, review item 표시까지 연결한다.

주요 산출물:

- 이미지 업로드 UI
- job status polling 또는 refresh
- preview artifact 표시
- review item list 표시
- 로딩/실패/빈 상태

완료 기준:

- 사용자가 브라우저에서 원본 문제 이미지와 손풀이 이미지를 업로드할 수 있다.
- workflow 실행 후 preview와 review item이 표시된다.
- `requires_human_review=true`이고 unresolved인 항목만 사용자에게 보인다.
- API 실패 시 한국어 오류 상태가 표시된다.

필요하면 좋은 사용자 제공 파일:

- 실제 샘플 이미지 1쌍
- 기대 결과 예시가 있으면 추후 visual QA에 사용한다.

### M5. Spec Patch & Deterministic Re-render

상태: Done

상세 설계: [M5 Spec Patch & Deterministic Re-render 상세 설계](../superpowers/specs/2026-06-17-spec-patch-rerender-design.md)

구현 결과: 제한된 candidate spec patch API, patch validation, revision history 저장, deterministic SVG render artifact 생성/조회 API가 구현됨. 웹 editor는 지원되는 draft 변경을 server patch로 저장하고 최신 preview를 다시 조회할 수 있음.

목표:

- 사용자의 클릭/드래그/선택 수정사항을 spec patch로 저장한다.
- patch 적용 후 deterministic renderer가 preview를 갱신한다.

주요 산출물:

- `PATCH /jobs/{job_id}/spec`
- patch validation
- revision history 저장
- `POST /jobs/{job_id}/render`
- web edit state와 server patch 동기화

완료 기준:

- 허용된 interaction만 patch를 만들 수 있다.
- patch가 candidate spec version을 증가시킨다.
- patch 이후 render artifact가 새로 생성된다.
- invalid patch는 원본 spec과 artifact를 손상시키지 않는다.

### M6. Export Foundation

상태: Done

상세 설계: [M6 Export Foundation 상세 설계](../superpowers/specs/2026-06-17-export-foundation-design.md)

구현 결과: 승인된 job의 최신 candidate spec과 최신 render artifact를 참조해 PNG export artifact를 생성, 저장, 조회, 다운로드하는 기반이 구현됨. PDF export와 상용 품질 raster compositing은 후속 milestone으로 보류됨.

목표:

- deterministic overlay 결과를 최종 이미지 또는 PDF로 export할 수 있는 기반을 만든다.

주요 산출물:

- `POST /jobs/{job_id}/export`
- export artifact model
- PNG export prototype
- PDF export prototype 또는 명시적 deferred decision
- export 조회/download endpoint

완료 기준:

- `APPROVED` job에서 PNG export artifact를 만들 수 있다.
- export 결과는 최신 source image artifact, 최신 candidate spec artifact, 최신 render artifact를 참조한다.
- export 실패가 job state와 artifact를 손상시키지 않는다.
- fixture 기반 export smoke test가 통과한다.

### M7. OpenAI Adapter Integration

상태: Done

상세 설계: [M7 OpenAI Adapter Integration 상세 설계](../superpowers/specs/2026-06-18-openai-adapter-integration-design.md)

구현 결과: `CLEANSOLVE_ANALYSIS_CLIENT=mock|openai` 선택형 analysis adapter, OpenAI Responses API 기반 candidate spec 생성 경로, Structured Outputs payload, safe failure persistence, opt-in smoke test가 구현됨.

목표:

- mock adapter와 같은 계약으로 실제 OpenAI adapter를 연결한다.
- 기본 경로는 candidate spec 생성이며, 전체 이미지 one-shot regeneration이 아니다.

주요 산출물:

- OpenAI adapter implementation
- model/env settings
- prompt/input contract
- structured output parsing
- failure/retry policy
- cost/logging guardrail

완료 기준:

- `OPENAI_API_KEY`가 있을 때 real adapter smoke test를 선택적으로 실행할 수 있다.
- API key가 없어도 unit test와 mock E2E는 통과한다.
- model/image model env가 문서화되어 있다.
- adapter failure가 job을 안전한 failed/retryable 상태로 만든다.

### M8. MVP E2E Harness & Release Checklist

상태: Done

상세 설계: [M8 MVP E2E Harness & Release Checklist 상세 설계](../superpowers/specs/2026-06-19-mvp-e2e-harness-release-checklist-design.md)

구현 결과: pytest 기반 upload-to-export 서버 E2E harness, Playwright 기반 web upload smoke E2E, E2E metrics, MVP release checklist가 구현됨.

목표:

- MVP 경로를 fixture 기준으로 end-to-end 검증한다.
- release 여부를 판단할 수 있는 checklist를 만든다.

주요 산출물:

- upload-to-export local E2E test
- review budget metric
- correction plan metric
- render artifact existence check
- export artifact smoke check
- MVP release checklist

완료 기준:

- fixture job이 upload, mock analysis, validation, render, correction, review filtering, export까지 실행된다.
- harness가 visible review item count와 budget 초과를 측정한다.
- MVP 성공 기준 22개에 대한 pass/partial/fail 표가 문서화된다.

### M9. Job Progress SSE Replay UI

상태: Done

상세 설계: [M9 Job Progress SSE Replay UI 상세 설계](../superpowers/specs/2026-06-23-job-progress-sse-ui-design.md)

구현 결과: 저장된 `progress_events` artifact를 `text/event-stream`으로 replay하는 API, web progress stream consumer, workflow progress state, 접근 가능한 진행 상황 panel, Playwright SSE replay smoke test가 구현됨.

목표:

- 저장된 `progress_events` artifact를 SSE 형식으로 replay한다.
- 웹 editor에 client-side optimistic 단계와 server progress timeline을 표시한다.
- 긴 review/correction loop에서 사용자가 시스템이 어떤 단계를 거쳤는지 확인할 수 있게 한다.

주요 산출물:

- `GET /jobs/{job_id}/progress-stream`
- SSE replay helper
- web progress stream consumer
- progress timeline state
- progress panel UI
- API/web/Playwright smoke test

완료 기준:

- run 완료 후 저장된 progress event가 `text/event-stream`으로 replay된다.
- 웹에서 `작업을 시작했습니다.` 같은 server progress message가 timeline에 표시된다.
- SSE replay 실패가 candidate spec/review item 조회를 막지 않는다.
- 기존 upload-to-review E2E 흐름이 유지된다.

### M10. Background Job & Live SSE

상태: Done

상세 설계: [M10 Background Job & Live SSE 상세 설계](../superpowers/specs/2026-06-23-m10-background-job-live-sse-design.md)

구현 결과: `POST /jobs/{job_id}/run`은 `202 RUNNING`을 반환하는 비동기 시작 endpoint가 되었고, FastAPI process 내부 background worker가 workflow를 실행한다. 실행 중 progress event는 job별 durable JSONL 파일에 flush되며, `GET /jobs/{job_id}/progress-stream`은 live event, reconnect replay, success/failure/cancelled terminal event를 제공한다. 웹 upload flow는 run 시작 직후 SSE를 열어 M9 timeline UI와 같은 payload로 live progress를 표시한다.

목표:

- `POST /jobs/{job_id}/run` 또는 새 run 생성 endpoint를 비동기화한다.
- workflow 실행 중 progress event를 durable store에 flush한다.
- `GET /jobs/{job_id}/progress-stream`이 실행 중 event를 실시간으로 송출한다.
- refresh/reconnect 시 이미 생성된 progress event를 replay한다.

주요 산출물:

- background task 또는 worker 실행 계약
- live progress store
- `Last-Event-ID` 또는 cursor 기반 replay 정책
- failed/cancelled job stream contract
- live SSE API/web/harness E2E

완료 기준:

- 사용자가 workflow 실행 중 실제 server event를 순서대로 볼 수 있다.
- browser refresh 후에도 누락 없이 진행 timeline을 복원한다.
- worker failure 또는 analysis adapter failure가 stream과 job 상태에 일관되게 반영된다.

### M11. Real Planner & Eval Gate Integration

상태: Planned

목표:

- mock 중심 self-revision loop를 실제 모델 기반 planner/evaluator loop로 확장한다.
- `validate_spec_ai`, `inspect_render_ai`, `plan_correction_ai`에 실제 AI adapter 계약을 연결한다.
- deterministic renderer는 그대로 유지하고, 모델은 spec 생성/검수/수정 계획에만 사용한다.

주요 산출물:

- planner/evaluator adapter interface
- GPT-5.5 기반 correction planning adapter
- render inspection/eval adapter
- score threshold 기반 approval gate
- safe failure/retry/HITL contract
- opt-in real model smoke test

완료 기준:

- mock adapter와 real adapter가 같은 planner/eval 계약을 사용한다.
- API key가 없어도 기본 테스트와 mock E2E가 통과한다.
- 실제 모델 호출은 opt-in smoke로만 실행된다.
- raw model output, prompt, local path, API key가 job response/progress event/UI에 노출되지 않는다.
- 낮은 confidence 또는 반복 실패는 HITL로 전환된다.

### M12. Dataset Evaluation & Source Alignment

상태: Planned

목표:

- 단일 fixture가 아니라 여러 실제 문제/손풀이 샘플에서 candidate spec, renderer, correction 품질을 평가한다.
- 여러 문제/여러 페이지 입력에 대한 crop/matching 결과를 평가 dataset으로 연결한다.
- source-to-spec, render-to-source alignment metric을 MVP release 판단에 포함한다.

주요 산출물:

- local ignored dataset manifest
- sample/job matching manifest
- batch evaluation CLI 또는 pytest harness
- source-to-spec alignment metric
- render-to-source visual/layout metric
- dataset summary report

완료 기준:

- 사용자가 제공한 실제 샘플 subset을 git에 커밋하지 않고 평가할 수 있다.
- batch run 결과가 pass/partial/fail과 주요 실패 원인을 남긴다.
- dimension endpoint/source alignment, formula/text layout, visible review item count가 dataset 단위로 측정된다.
- MVP release checklist가 단일 fixture가 아닌 dataset metric을 근거로 업데이트된다.

### M13. Export Quality & Visual Regression

상태: Planned

목표:

- 최종 산출물 품질을 MVP release 기준으로 검증한다.
- PNG export foundation을 production-grade compositing 방향으로 강화하고 PDF export 여부를 결정/구현한다.
- browser full export flow와 visual regression을 자동화한다.

주요 산출물:

- full browser upload-to-export E2E
- Playwright visual snapshot 또는 pixel-level regression harness
- production-grade PNG compositing check
- PDF export prototype 또는 명시적 MVP 제외 결정
- export artifact QA report

완료 기준:

- 사용자가 브라우저에서 upload, review, patch, render, export까지 한 흐름으로 실행할 수 있다.
- export 결과가 최신 source image, candidate spec, render artifact와 일관된다.
- visual regression이 핵심 fixture의 preview/export 차이를 감지한다.
- PDF를 MVP에 포함할지 제외할지 문서와 테스트 기준으로 확정한다.

### M14. MVP Release Candidate Hardening

상태: Planned

목표:

- M0~M13 산출물을 묶어 MVP release candidate 여부를 판정한다.
- release checklist의 `Partial` 항목을 MVP 허용/차단 기준으로 재분류한다.
- 사용자/운영 문서를 실제 실행 가능한 형태로 정리한다.

주요 산출물:

- updated MVP release checklist
- release candidate verification script
- env/setup/runbook 문서
- known limitations 문서
- PR/issue backlog for post-MVP production hardening

완료 기준:

- release checklist가 `MVP RC Pass`, `MVP RC Blocker`, `Post-MVP`로 재분류된다.
- fresh clone 기준 setup, env, test, local run 절차가 문서대로 동작한다.
- API/web/harness/e2e 검증 명령이 하나의 release checklist에 정리된다.
- MVP에 포함하지 않는 기능이 명시적으로 post-MVP backlog로 이동된다.

## SoT MVP 성공 기준 추적

| # | SoT 성공 기준 | 현재 상태 | 연결 milestone |
| --- | --- | --- | --- |
| 1 | 원본 문제 이미지와 손풀이 이미지 업로드 | Done | M1 |
| 2 | 기본 내장 손글씨 스타일 프리셋 로드 | Done | M0 |
| 3 | candidate spec 생성 또는 mock spec 처리 | Done | M2 |
| 4 | candidate spec 기반 overlay preview | Done | M3 |
| 5 | 하단 풀이 수식/텍스트 재배치 | Partial | M3, M12, M13 |
| 6 | 도형 위 highlight/arrow/box/label 표시 | Done | M3 |
| 7 | dimension_line/dimension_curve endpoint와 anchor 표현 | Done | M3 |
| 8 | needs_review 내부 검증 관리 | Partial | M2, M8 |
| 9 | requires_human_review만 사용자 노출 | Done | M4 |
| 10 | element type별 허용된 수정 방식 | Partial | M4, M5, M11 |
| 11 | 수정사항 spec patch 저장 | Done | M5 |
| 12 | 수정 후 deterministic re-render | Done | M5 |
| 13 | 최종 이미지 export | Partial | M6, M8, M13 |
| 14 | 최소 fixture harness 통과 | Done | M8 |
| 15 | freehand-style 치수선 표현 | Done | M0, M3 |
| 16 | target anchor와 visible stroke 분리 저장 | Done | M0, M3 |
| 17 | 치수선 label을 group 일부로 관리 | Done | M0, M3 |
| 18 | 치수선 endpoint와 span 검증 | Partial | M2, M8, M12 |
| 19 | HITL이 예외 경로로 동작 | Done | M2, M4 |
| 20 | 사용자 검수 노출률과 review item 개수 측정 | Done | M8 |
| 21 | 생성/렌더링 결과 자동 검수 | Partial | M2, M8, M11, M12 |
| 22 | 오류 발견 시 correction plan 생성 | Partial | M2, M8, M11 |

## MVP까지 남은 확정 마일스톤

현재 고정된 MVP release candidate 경로는 **M11~M14, 총 4개 마일스톤**이다.

| 순서 | 마일스톤 | 목적 | MVP 판단에 주는 의미 |
| --- | --- | --- | --- |
| 1 | M11 Real Planner & Eval Gate Integration | 실제 planner/evaluator 모델을 workflow 계약에 연결한다. | mock이 아닌 실제 모델 기반 자동 검수/수정 판단을 시작한다. |
| 2 | M12 Dataset Evaluation & Source Alignment | 실제 샘플 dataset으로 품질을 측정한다. | 단일 fixture가 아니라 여러 실제 문제에서 실패율을 본다. |
| 3 | M13 Export Quality & Visual Regression | 최종 산출물과 browser export flow를 검증한다. | 사용자가 받을 결과물이 MVP 품질인지 확인한다. |
| 4 | M14 MVP Release Candidate Hardening | checklist, 문서, 검증 명령을 release 기준으로 묶는다. | MVP RC 여부를 명확히 판정한다. |

M14 이후 작업은 MVP 자체가 아니라 production hardening으로 분리한다. 예: multi-user auth, cloud storage, external queue, billing, admin dashboard, 대규모 monitoring.

## 권장 PR 순서

1. `feat/image-ingestion-artifacts`
2. `feat/spec-pipeline-artifacts`
3. `feat/renderer-mvp-primitives`
4. `feat/web-upload-review-flow`
5. `feat/spec-patch-rerender`
6. `feat/export-foundation`
7. `feat/openai-adapter`
8. `feat/mvp-e2e-harness`
9. `feat/job-progress-sse-ui`
10. `feat/background-live-sse`
11. `feat/real-planner-eval-gate`
12. `feat/dataset-evaluation-source-alignment`
13. `feat/export-quality-visual-regression`
14. `feat/mvp-release-candidate-hardening`

각 PR은 Superpowers 흐름을 따른다.

- brainstorming 또는 기존 roadmap 확인
- design spec 작성
- implementation plan 작성
- TDD
- 구현
- spec compliance review
- code quality review
- verification
- push/PR

## 다음 추천 작업

M10 기준으로 현재 상태는 `Partial MVP`다. 다음 작업은 M11으로 고정한다. M11 이후에는 M12~M14 순서대로 진행해야 MVP release candidate 판정까지 갈 수 있다.

`default_pretty_handwriting v1` renderer calibration contract, M9 SSE replay UI, M10 background job/live SSE는 완료됐다. 다음 병목은 실제 planner/eval gate가 아직 mock 중심이라는 점이다.

우선순위 후보:

1. M11 실제 GPT-5.5 기반 ReAct planner와 eval gate 연결
2. M12 실제 OpenAI adapter 결과에 대한 dataset evaluation과 source alignment
3. M13 production-grade PNG/PDF export와 visual regression
4. M14 MVP release candidate hardening

현재 추천 순서는 M11을 먼저 구현하는 것이다. 이유는 실행/진행 표시 기반은 갖춰졌지만, MVP 품질 판단에는 실제 planner/evaluator 계약과 safe HITL 전환이 필요하기 때문이다.
