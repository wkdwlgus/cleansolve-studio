# Decisions

## D-001: Repository Slug

Use `cleansolve-studio` as the repository slug, matching `SoT.md`.

## D-002: Backend Framework

Use FastAPI because the workflow, validation harness, AI adapters, and image processing pipeline benefit from Python libraries and direct LangGraph integration.

## D-003: Workflow Orchestrator

Use LangGraph. It provides explicit graph state, bounded loops, node-level failure handling, and a clean path to HITL interrupt/resume.

## D-004: Frontend Canvas

Use React with Konva. Konva gives direct support for layered canvases, draggable anchors, curve handles, and element-specific interactions.

## D-005: Renderer Direction

Start with deterministic SVG-compatible overlay rendering on the server. PNG/PDF export can wrap the same geometry model later.

## D-006: Style Presets

Use only system built-in handwriting style presets in the MVP. User-uploaded style presets are out of scope.

## D-007: Test Strategy

Use fixture-based pytest coverage for schemas, dimension validation, workflow revision bounds, correction planning, and HITL review budgets.
