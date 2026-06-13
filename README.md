# CleanSolve Studio

> **WIP:** 이 저장소는 현재 초기 세팅 중입니다. 아직 실행 가능한 앱이 완성된 상태가 아니며, `main` 브랜치는 제품 방향과 Source of Truth를 공유하기 위한 기준 문서 중심으로 관리됩니다.

CleanSolve Studio는 **수학 손풀이 정서 AI 편집기**입니다.

선생님이 작성한 손글씨 풀이 이미지를 원본 문제 이미지 위에 더 깔끔하고 읽기 좋은 손글씨 스타일로 재구성하되, 풀이 내용, 수식, 도형 주석, 색상, 강조, 풀이 순서를 최대한 보존하는 것을 목표로 합니다.

## 핵심 방향

이 프로젝트는 단순히 이미지를 한 번에 새로 생성하는 서비스가 아닙니다.

CleanSolve Studio의 기본 흐름은 다음과 같습니다.

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

## 현재 저장소 상태

현재 `main` 브랜치에는 프로젝트의 기준 문서가 올라와 있습니다. 실제 scaffold 구현은 별도 작업 브랜치에서 진행 중이며, 완료 전까지 이 README의 실행 방법과 기술 스택 설명은 계획 단계의 안내입니다.

- [SoT.md](./SoT.md): 제품과 아키텍처의 Source of Truth
- [설계 spec](./docs/superpowers/specs/2026-06-14-cleansolve-studio-scaffold-design.md): 초기 scaffold 설계
- [구현 plan](./docs/superpowers/plans/2026-06-14-cleansolve-studio-scaffold.md): Superpowers 기반 구현 계획

## 예정 기술 스택

초기 scaffold의 기본 스택은 다음과 같습니다.

- Frontend: React, TypeScript, Vite, Konva, Tailwind CSS
- Backend: Python FastAPI
- Workflow: LangGraph
- Schema/validation: Pydantic, JSON Schema
- Renderer: spec 기반 deterministic SVG/overlay renderer prototype
- AI adapter: OpenAI API adapter interface와 mock client
- Test harness: pytest 기반 fixture/evaluation harness

## OpenAI API Key

scaffold 구현 후 로컬 backend 개발에서는 다음 파일을 사용합니다.

```text
apps/api/.env
```

예상 환경 변수는 다음과 같습니다.

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ANALYSIS=
OPENAI_MODEL_VALIDATION=
OPENAI_MODEL_IMAGE=
CLEANSOLVE_STORAGE_ROOT=var/jobs
```

실제 `.env` 파일은 커밋하지 않습니다. 저장소에는 `.env.example`만 포함합니다.

## MVP 범위

초기 MVP는 다음을 목표로 합니다.

- 원본 문제 이미지와 선생님 손풀이 이미지 업로드
- 시스템 내장 손글씨 스타일 프리셋 로드
- candidate spec 생성 또는 mock spec 처리
- spec validation
- 원본 위 overlay preview 렌더링
- dimension line/curve/freehand marker의 target anchor와 visible stroke 분리
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

## 문서 읽는 순서

처음 보는 사람은 아래 순서로 읽으면 됩니다.

1. [SoT.md](./SoT.md)
2. [설계 spec](./docs/superpowers/specs/2026-06-14-cleansolve-studio-scaffold-design.md)
3. [구현 plan](./docs/superpowers/plans/2026-06-14-cleansolve-studio-scaffold.md)

scaffold 작업이 끝나면 README에 실제 실행 방법, 테스트 방법, 디렉터리 구조를 다시 정리합니다.

SoT와 구현이 충돌하는 경우 SoT를 우선합니다.
