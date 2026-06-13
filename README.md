# CleanSolve Studio

CleanSolve Studio is a math handwriting cleanup editor. It preserves the original problem image, extracts teacher handwritten solution annotations into a candidate rendering spec, validates the spec, renders deterministic overlays, runs automatic self-revision, and exposes only high-impact unresolved items to HITL review.

## Stack

- Web: React, TypeScript, Vite, Konva, Tailwind CSS
- API: FastAPI
- Workflow: LangGraph
- Schemas: Pydantic and JSON Schema
- Tests: pytest, Vitest

## OpenAI API Key

For local backend development, create `apps/api/.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ANALYSIS=
OPENAI_MODEL_VALIDATION=
OPENAI_MODEL_IMAGE=
CLEANSOLVE_STORAGE_ROOT=var/jobs
```

Do not commit `.env` files. Use environment secrets in CI and deployment.

## First Verification

```bash
python -m pytest
```

At the foundation-only checkpoint, pytest may report no tests collected. This is expected until later scaffold tasks add the API, workflow, renderer, spec, and harness tests. After those tests are added, `python -m pytest` is expected to pass.
