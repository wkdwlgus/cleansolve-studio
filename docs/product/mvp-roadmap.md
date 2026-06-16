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
| Workflow orchestrator | Partial | LangGraph self-revision prototype이 있으나 실제 image ingestion/artifact 상태와는 아직 느슨함 |
| FastAPI job API | Partial | job 생성, 이미지 upload/artifact 저장, run precondition, review item shell이 있음 |
| Web editor shell | Done | 이미지 업로드, workflow 실행, candidate spec preview, review panel 표시 흐름이 있음 |
| HITL policy | Partial | `requires_human_review=true` 필터와 review budget은 구현됨 |
| Spec patch 저장 | Not Started | 사용자의 수정사항을 server-side patch로 저장하는 API가 없음 |
| Re-render after patch | Not Started | patch 이후 deterministic re-render API/상태 갱신이 없음 |
| Export | Not Started | PNG/PDF export endpoint와 artifact 저장이 없음 |
| Real OpenAI adapter | Not Started | mock adapter는 있으나 실제 OpenAI 호출 경로는 아직 없음 |
| E2E harness | Partial | upload-to-analysis fixture 경로는 완료됐으나 upload-to-export end-to-end 검증은 아직 없음 |

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

상태: Not Started

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

상태: Not Started

목표:

- deterministic overlay 결과를 최종 이미지 또는 PDF로 export할 수 있는 기반을 만든다.

주요 산출물:

- `POST /jobs/{job_id}/export`
- export artifact model
- PNG export prototype
- PDF export prototype 또는 명시적 deferred decision
- export 조회/download endpoint

완료 기준:

- approved 또는 review-resolved job에서 export artifact를 만들 수 있다.
- export 결과는 원본 image artifact와 overlay artifact를 참조한다.
- export 실패가 job state와 artifact를 손상시키지 않는다.
- fixture 기반 export smoke test가 통과한다.

### M7. OpenAI Adapter Integration

상태: Not Started

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

상태: Partial

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

## SoT MVP 성공 기준 추적

| # | SoT 성공 기준 | 현재 상태 | 연결 milestone |
| --- | --- | --- | --- |
| 1 | 원본 문제 이미지와 손풀이 이미지 업로드 | Done | M1 |
| 2 | 기본 내장 손글씨 스타일 프리셋 로드 | Done | M0 |
| 3 | candidate spec 생성 또는 mock spec 처리 | Done | M2 |
| 4 | candidate spec 기반 overlay preview | Done | M3 |
| 5 | 하단 풀이 수식/텍스트 재배치 | Partial | M3 |
| 6 | 도형 위 highlight/arrow/box/label 표시 | Done | M3 |
| 7 | dimension_line/dimension_curve endpoint와 anchor 표현 | Done | M3 |
| 8 | needs_review 내부 검증 관리 | Partial | M2, M8 |
| 9 | requires_human_review만 사용자 노출 | Done | M4 |
| 10 | element type별 허용된 수정 방식 | Partial | M4, M5 |
| 11 | 수정사항 spec patch 저장 | Not Started | M5 |
| 12 | 수정 후 deterministic re-render | Not Started | M5 |
| 13 | 최종 이미지 export | Not Started | M6 |
| 14 | 최소 fixture harness 통과 | Partial | M8 |
| 15 | freehand-style 치수선 표현 | Done | M0, M3 |
| 16 | target anchor와 visible stroke 분리 저장 | Done | M0, M3 |
| 17 | 치수선 label을 group 일부로 관리 | Done | M0, M3 |
| 18 | 치수선 endpoint와 span 검증 | Partial | M2, M8 |
| 19 | HITL이 예외 경로로 동작 | Done | M2, M4 |
| 20 | 사용자 검수 노출률과 review item 개수 측정 | Partial | M8 |
| 21 | 생성/렌더링 결과 자동 검수 | Partial | M2, M8 |
| 22 | 오류 발견 시 correction plan 생성 | Partial | M2, M8 |

## 권장 PR 순서

1. `feat/image-ingestion-artifacts`
2. `feat/spec-pipeline-artifacts`
3. `feat/renderer-mvp-primitives`
4. `feat/web-upload-review-flow`
5. `feat/spec-patch-rerender`
6. `feat/export-foundation`
7. `feat/openai-adapter`
8. `feat/mvp-e2e-harness`

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

다음 구현 작업은 `M2. Candidate Spec Pipeline`이 가장 적합하다.

이유:

- M1에서 저장한 source image artifact를 다음 pipeline 입력으로 연결해야 한다.
- candidate spec, validation report, correction input을 artifact로 저장해야 이후 preview, HITL, export 흐름을 붙일 수 있다.
- 실제 OpenAI adapter 없이도 mock 기반 E2E 경로를 먼저 안정화할 수 있다.
