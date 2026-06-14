# CleanSolve Studio Scaffold Design

Date: 2026-06-14
Status: Approved for implementation planning

## Source of Truth

This design follows `SoT.md` as the product and architecture source of truth. The scaffold must preserve these constraints:

- Original images are the highest source of truth and are never overwritten.
- Candidate spec JSON is an intermediate rendering contract, not the truth.
- One-shot full image generation is not the default path.
- Annotation primitives, especially dimension markers, are first-class data.
- Automatic self-revision runs before HITL whenever an issue is auto-correctable.
- HITL only exposes `requires_human_review=true` items, not every `needs_review=true` item.
- MVP uses system built-in handwriting style presets only.

## Recommended Approach

Use a monorepo with:

- Frontend: React, TypeScript, Vite, Konva, Tailwind CSS.
- Backend: Python FastAPI.
- Workflow runtime: LangGraph.
- Schemas and validation: Pydantic models plus exported JSON Schema.
- Tests and harness: pytest for backend/workflow/spec validation, Vitest for frontend unit tests, Playwright later for visual browser checks.
- Renderer prototype: deterministic SVG-compatible overlay renderer in Python first, with a matching Konva renderer surface in the web app.

This approach keeps the job workflow, validation reports, correction plans, revision history, and export path on the server while allowing precise click/drag HITL editing in the browser.

## Repository Structure

```text
apps/
  api/
    cleansolve_api/
      main.py
      routes/
      settings.py
    tests/
  web/
    src/
      app/
      editor/
      api/
      types/
    tests/
packages/
  ai/
    cleansolve_ai/
      adapter.py
      mock_client.py
  harness/
    cleansolve_harness/
      runner.py
      metrics.py
  renderer/
    cleansolve_renderer/
      overlay.py
      export.py
  spec/
    cleansolve_spec/
      models.py
      validation.py
      schemas/
  workflow/
    cleansolve_workflow/
      graph.py
      state.py
      nodes.py
assets/
  style-presets/
    default_pretty_handwriting/
fixtures/
  samples/
docs/
  architecture/
  hitl/
  workflow/
  superpowers/
ASSUMPTIONS.md
DECISIONS.md
README.md
SoT.md
```

## Backend Design

FastAPI exposes job-oriented endpoints:

- `POST /jobs` creates a job.
- `POST /jobs/{job_id}/images/problem` stores the problem image.
- `POST /jobs/{job_id}/images/teacher-solution` stores the teacher solution image.
- `POST /jobs/{job_id}/run` starts the LangGraph workflow.
- `GET /jobs/{job_id}` returns state and artifact references.
- `GET /jobs/{job_id}/review-items` returns only user-visible HITL items.
- `PATCH /jobs/{job_id}/spec` applies user patches.
- `POST /jobs/{job_id}/render` re-renders deterministically.
- `POST /jobs/{job_id}/export` exports PNG/PDF.

The initial scaffold may use local filesystem storage under `var/jobs/` and mock image artifacts. The code must keep storage behind an interface so object storage can replace it later.

## Workflow Design

LangGraph is the default orchestrator because SoT explicitly requires workflow orchestration from the start and LangGraph supports explicit state, retries, graph nodes, and HITL-style interrupt/resume patterns.

Initial graph nodes:

```text
create_job
load_style_preset
analyze_sources
extract_candidate_spec
validate_spec
render_preview
inspect_render
plan_correction
apply_correction
reinspect
decide_human_review
apply_user_patch
final_render
export
```

The graph state includes:

- `job_id`
- `status`
- `style_preset_id`
- `style_preset_version`
- `candidate_spec_version`
- `validation_reports`
- `correction_plans`
- `revision_attempts`
- `max_revision_attempts` defaulting to `2`
- `review_items`
- `artifacts`

If a high-impact issue remains after automatic revision attempts, the workflow sets `NEEDS_REVIEW` and returns only budgeted review items.

## Candidate Spec Model

The scaffold starts with the MVP primitive registry from `SoT.md`:

```text
formula_line
text_note
highlight_line
highlight_curve
dimension_line
dimension_curve
freehand_dimension_marker
arrow
box
circle
angle_mark
point_label
segment_label
graph_point
graph_curve
graph_tangent
shaded_area
choice_mark
freehand_annotation
unsupported_annotation
```

Every element includes, where applicable:

- `id`
- `type`
- `source_region`
- `color`
- `confidence`
- `needs_review`
- `requires_human_review`
- `auto_correctable`
- `evidence`
- `bbox`
- `geometry`
- `style`
- `interaction`
- `validation`
- `revision_history`

Dimension primitives must separate `target_anchor_start` and `target_anchor_end` from visible strokes. `freehand_dimension_marker` must preserve fragmented stroke groups and label membership.

## Validation Design

The initial validation layer checks:

- Required fields exist.
- Bounding boxes are inside the page.
- Evidence exists for extracted elements.
- Confidence values are normalized.
- Low-confidence items are marked `needs_review`.
- `style.source` is `system_builtin`.
- `style.preset_id` and `style.preset_version` exist.
- Dimension elements have target anchors.
- Dimension labels include `label_anchor`.
- Unsupported annotations are preserved.
- `needs_review=true` is not automatically exposed to the user.
- Review item budget is enforced.

Validation reports are saved as artifacts and can feed correction plan generation.

## Renderer Design

The renderer starts as a deterministic overlay renderer:

- It takes the original problem image reference and candidate spec.
- It renders confirmed overlay elements without mutating the original image.
- It treats text/formula rendering as placeholder assets until handwriting style rendering is implemented.
- It supports dimension line, dimension curve, and freehand dimension marker geometry enough for fixture validation.
- It can render preview artifacts and later export PNG/PDF.

Simple user edits apply as spec patches followed by deterministic re-render. Full image regeneration is never the default correction path.

## Frontend Design

The web app starts as an editor shell:

- Job creation/upload surface.
- Preview canvas backed by Konva.
- Layers for source image, rendered overlay, handles, and review highlights.
- HITL panel that shows at most three review items.
- Element-specific controls for allowed interactions.
- Spec patch emission when users drag anchors, labels, curves, or points.

The UI must not ask users to type mathematical point names or segment names as the default correction mechanism. Corrections should be click, select, drag, approve, or reject first.

## OpenAI API Key Handling

The API key should be stored in a local environment file that is never committed:

```text
apps/api/.env
```

Expected variable:

```text
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ANALYSIS=
OPENAI_MODEL_VALIDATION=
OPENAI_MODEL_IMAGE=
```

The repository should include a committed example file:

```text
apps/api/.env.example
```

with:

```text
OPENAI_API_KEY=
OPENAI_MODEL_ANALYSIS=
OPENAI_MODEL_VALIDATION=
OPENAI_MODEL_IMAGE=
```

The backend settings module reads `apps/api/.env` during local development. CI and deployment should provide the same variables through environment secrets. The scaffold must add `.env` files to `.gitignore`.

## Quality Harness

The fixture harness starts with a small sample layout:

```text
fixtures/samples/dimension_marker_basic/
  problem_image.png
  teacher_solution_image.png
  expected_partial_spec.json
  expected_review_items.json
  expected_render_constraints.json
  expected_correction_plan.json
  expected_final_constraints.json
```

Harness metrics:

- Candidate spec schema validity.
- Primitive renderer coverage.
- Dimension target anchor validity.
- Visible stroke alignment.
- Dimension/highlight classification.
- Correction plan presence before automatic correction.
- `max_revision_attempts` enforcement.
- HITL exposure rate.
- Average review item count.
- Review item count budget.
- Regression after auto-revision.

The harness is not a math answer checker. It protects extraction, validation, rendering, correction, and HITL workflow contracts.

## Documentation Artifacts

The scaffold creates:

- `README.md`
- `ASSUMPTIONS.md`
- `DECISIONS.md`
- `docs/workflow/initial-workflow.md`
- `docs/hitl/ux-policy.md`
- `docs/architecture/repository-structure.md`

`DECISIONS.md` records LangGraph selection, FastAPI selection, Konva selection, renderer/export direction, state handling, failure/retry handling, self-revision loop, HITL interrupt/resume, and test strategy.

`ASSUMPTIONS.md` records narrow assumptions required to scaffold without overbuilding beyond `SoT.md`.

## Out of Scope

The scaffold must not include:

- Login, billing, LMS, or deployment platform setup.
- User-uploaded handwriting style presets.
- Full high school math answer verification.
- Complex Figma-like editing.
- Temporal or a custom distributed workflow runtime.
- Full image regeneration as the default correction path.

## Acceptance Criteria

The scaffold is acceptable when:

- The repo has the required documents and package structure.
- Candidate spec, validation report, and correction plan schemas exist.
- LangGraph workflow prototype includes automatic self-revision and HITL branching.
- Mock AI client can produce a candidate spec fixture.
- Deterministic renderer prototype can render basic overlay artifacts.
- Harness tests cover dimension primitives, review budget, correction planning, and max revision attempts.
- Frontend shell can represent preview, review items, and element interaction policies.
- `.env.example` documents OpenAI environment variables and real `.env` files are ignored.
