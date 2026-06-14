# CleanSolve Studio

> 현재 이 저장소는 **WIP scaffold**입니다. 제품 전체가 완성된 상태가 아니라, SoT 기준 아키텍처와 핵심 계약을 검증하기 위한 초기 기반입니다.

CleanSolve Studio는 **수학 손풀이 정서 AI 편집기**입니다. 선생님이 작성한 손글씨 풀이 이미지를 원본 문제 이미지 위에 더 깔끔하고 읽기 좋은 손글씨 스타일로 재구성하되, 풀이 내용, 수식, 도형 주석, 색상, 강조, 풀이 순서를 최대한 보존하는 것을 목표로 합니다.

## 핵심 방향

이 프로젝트는 전체 이미지를 한 번에 다시 생성하는 서비스가 아닙니다.

기본 흐름은 다음과 같습니다.

```text
원본 문제 이미지
+ 선생님 손풀이 이미지
+ 시스템 내장 손글씨 스타일 프리셋
→ 시각 요소 분석
→ candidate spec JSON 생성
→ spec 검증
→ deterministic overlay 렌더링
→ 결과 자동 검수
→ 자동 수정/재렌더링
→ 필요한 경우에만 HITL 검수
→ 최종 export
```

중요한 원칙은 다음입니다.

- 원본 이미지는 최상위 Source of Truth입니다.
- JSON spec은 정답지가 아니라 검증 대상 중간 명세입니다.
- 수정할 때마다 전체 이미지를 AI로 재생성하지 않습니다.
- 치수선, 강조선, 라벨, 화살표, 수식, 도형 주석을 시각 primitive로 분리해 다룹니다.
- `needs_review=true`는 내부 검증 대상이고, 곧바로 사용자에게 노출한다는 뜻이 아닙니다.
- 사용자는 수학 명령어를 입력하는 대신 클릭, 선택, 드래그로 수정해야 합니다.

## 현재 포함된 것

- Pydantic 기반 후보 spec 모델과 검증 규칙
- dimension line, dimension curve, freehand dimension marker 중심 deterministic SVG overlay renderer
- mock AI adapter와 fixture 기반 테스트
- LangGraph 기반 자기수정 workflow prototype
- FastAPI job API shell
- React, Vite, Konva 기반 웹 editor shell
- pytest, Vitest 기반 테스트 harness

## 기술 스택

- Web: React, TypeScript, Vite, Konva, plain CSS shell
- API: FastAPI
- Workflow: LangGraph
- Schemas: Pydantic
- Tests: pytest, Vitest

## OpenAI API Key

로컬 백엔드 개발에서는 `apps/api/.env` 파일을 만들고 아래처럼 값을 넣으면 됩니다.

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ANALYSIS=
OPENAI_MODEL_VALIDATION=
OPENAI_MODEL_IMAGE=
CLEANSOLVE_STORAGE_ROOT=var/jobs
```

`.env` 파일은 커밋하지 않습니다. CI나 배포 환경에서는 환경 변수 또는 secret store를 사용합니다.

## 로컬 검증

Python 테스트:

```bash
python -m pytest -q
```

웹 의존성 설치:

```bash
npm --prefix apps/web install
```

웹 테스트와 빌드:

```bash
npm --prefix apps/web run test
npm --prefix apps/web run build
```

웹 도구는 Vite 8 기준으로 Node.js `20.19+` 또는 `22.12+`가 필요합니다. optional native dependency가 빠져 Rolldown binding 오류가 나면 `npm --prefix apps/web install --include=optional`을 한 번 더 실행하세요.

## MVP 범위

초기 MVP는 다음을 목표로 합니다.

- 원본 문제 이미지와 선생님 손풀이 이미지 업로드
- 시스템 내장 손글씨 스타일 프리셋 로드
- candidate spec 생성 또는 mock spec 처리
- spec validation
- 원본 위 overlay preview 렌더링
- dimension line, dimension curve, freehand marker의 target anchor와 visible stroke 분리
- 자동 self-revision loop
- `requires_human_review=true` 항목만 HITL에 노출
- fixture 기반 harness
- 최종 이미지/PDF export의 기반 구조

초기 MVP에서 제외하는 것은 다음입니다.

- 결제, 로그인, LMS 연동
- 사용자 지정 손글씨 스타일 업로드
- 완전 자동 100% 무검수 보장
- 전체 고등수학 정답 검증 엔진
- Figma 수준의 복잡한 벡터 편집기
- 전체 이미지를 기본적으로 AI로 재생성하는 구조

## 주요 문서

1. [SoT](./SoT.md)
2. [설계 spec](./docs/superpowers/specs/2026-06-14-cleansolve-studio-scaffold-design.md)
3. [구현 plan](./docs/superpowers/plans/2026-06-14-cleansolve-studio-scaffold.md)
4. [저장소 구조](./docs/architecture/repository-structure.md)
5. [초기 workflow](./docs/workflow/initial-workflow.md)
6. [HITL UX 정책](./docs/hitl/ux-policy.md)

SoT와 구현이 충돌하는 경우 SoT를 우선합니다.
