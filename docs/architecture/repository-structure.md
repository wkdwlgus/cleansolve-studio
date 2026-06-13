# Repository Structure

CleanSolve Studio uses a monorepo.

- `apps/api`: FastAPI job API and route layer.
- `apps/web`: React, TypeScript, Vite, and Konva editor shell.
- `packages/spec`: Candidate spec models and validation.
- `packages/workflow`: LangGraph job workflow prototype.
- `packages/renderer`: Deterministic overlay renderer prototype.
- `packages/ai`: OpenAI adapter interface and mock analysis client.
- `packages/harness`: Fixture metrics and quality harness.
- `fixtures/samples`: Small evaluation fixtures.
- `assets/style-presets`: System built-in handwriting style presets.
- `docs`: Architecture, workflow, HITL, and Superpowers planning docs.

The repository does not include user-uploaded style preset storage in the MVP.
