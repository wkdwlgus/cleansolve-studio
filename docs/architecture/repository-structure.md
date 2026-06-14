# 저장소 구조

CleanSolve Studio는 monorepo로 구성한다.

- `apps/api`: FastAPI job API와 route 계층
- `apps/web`: React, TypeScript, Vite, Konva 기반 editor shell
- `packages/spec`: candidate spec 모델과 검증 규칙
- `packages/workflow`: LangGraph job workflow prototype
- `packages/renderer`: deterministic overlay renderer prototype
- `packages/ai`: OpenAI adapter interface와 mock analysis client
- `packages/harness`: fixture metrics와 품질 harness
- `fixtures/samples`: 작은 평가 fixture
- `assets/style-presets`: 시스템 내장 손글씨 스타일 프리셋
- `docs`: architecture, workflow, HITL, Superpowers 작업 기록

MVP에서는 사용자 업로드 스타일 프리셋 저장소를 포함하지 않는다.
