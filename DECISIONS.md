# 결정 기록

## D-001: Repository Slug

저장소 slug는 `SoT.md`와 맞춰 `cleansolve-studio`를 사용한다.

## D-002: Backend Framework

백엔드는 FastAPI를 사용한다. workflow, 검증 harness, AI adapter, 이미지 처리 pipeline이 Python 생태계와 LangGraph 연동의 이점을 받기 때문이다.

## D-003: Workflow Orchestrator

workflow orchestrator는 LangGraph를 사용한다. 명시적인 graph state, 제한된 반복, node 단위 실패 처리, HITL interrupt/resume 구조로 확장하기 쉽다.

## D-004: Frontend Canvas

프론트엔드 canvas는 React와 Konva를 사용한다. 레이어드 canvas, draggable anchor, curve handle, element별 상호작용을 직접 표현하기 좋다.

## D-005: Renderer Direction

renderer는 서버 측 deterministic SVG overlay부터 시작한다. PNG/PDF export는 같은 geometry model을 감싸는 방식으로 이후 확장한다.

## D-006: Style Presets

MVP에서는 시스템 내장 손글씨 스타일 프리셋만 사용한다. 사용자가 업로드하는 스타일 프리셋은 범위 밖이다.

## D-007: Test Strategy

테스트는 fixture 기반 pytest와 Vitest를 사용한다. schema, 치수 표시 검증, workflow revision bound, correction planning, HITL review budget, 웹 편집 정책을 우선 검증한다.
