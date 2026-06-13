# CleanSolve Studio Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the initial CleanSolve Studio monorepo scaffold from `SoT.md`, including schemas, mock workflow orchestration, deterministic renderer prototype, fixture harness, FastAPI shell, and React/Konva editor shell.

**Architecture:** The repository is a monorepo. Python packages own the backend contracts, LangGraph workflow, mock AI adapter, renderer, and quality harness. The web app owns the interactive editor shell and emits spec patches; it does not own workflow state or final rendering truth.

**Tech Stack:** Python 3.13, FastAPI, LangGraph, Pydantic, pytest, React, TypeScript, Vite, Konva, Tailwind CSS, Vitest.

---

## File Structure

Create or modify these files:

- Create: `.gitignore`
- Create: `README.md`
- Create: `ASSUMPTIONS.md`
- Create: `DECISIONS.md`
- Create: `pyproject.toml`
- Create: `pytest.ini`
- Create: `apps/api/.env.example`
- Create: `apps/api/cleansolve_api/__init__.py`
- Create: `apps/api/cleansolve_api/main.py`
- Create: `apps/api/cleansolve_api/settings.py`
- Create: `apps/api/cleansolve_api/routes/__init__.py`
- Create: `apps/api/cleansolve_api/routes/jobs.py`
- Create: `apps/api/tests/test_jobs_api.py`
- Create: `apps/web/package.json`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/app/App.tsx`
- Create: `apps/web/src/editor/EditorCanvas.tsx`
- Create: `apps/web/src/editor/ReviewPanel.tsx`
- Create: `apps/web/src/editor/interactionPolicy.ts`
- Create: `apps/web/src/api/client.ts`
- Create: `apps/web/src/types/spec.ts`
- Create: `apps/web/src/styles.css`
- Create: `packages/spec/cleansolve_spec/__init__.py`
- Create: `packages/spec/cleansolve_spec/models.py`
- Create: `packages/spec/cleansolve_spec/validation.py`
- Create: `packages/spec/tests/test_validation.py`
- Create: `packages/renderer/cleansolve_renderer/__init__.py`
- Create: `packages/renderer/cleansolve_renderer/overlay.py`
- Create: `packages/renderer/tests/test_overlay.py`
- Create: `packages/ai/cleansolve_ai/__init__.py`
- Create: `packages/ai/cleansolve_ai/adapter.py`
- Create: `packages/ai/cleansolve_ai/mock_client.py`
- Create: `packages/ai/tests/test_mock_client.py`
- Create: `packages/workflow/cleansolve_workflow/__init__.py`
- Create: `packages/workflow/cleansolve_workflow/state.py`
- Create: `packages/workflow/cleansolve_workflow/nodes.py`
- Create: `packages/workflow/cleansolve_workflow/graph.py`
- Create: `packages/workflow/tests/test_graph.py`
- Create: `packages/harness/cleansolve_harness/__init__.py`
- Create: `packages/harness/cleansolve_harness/metrics.py`
- Create: `packages/harness/cleansolve_harness/runner.py`
- Create: `packages/harness/tests/test_metrics.py`
- Create: `fixtures/samples/dimension_marker_basic/expected_partial_spec.json`
- Create: `fixtures/samples/dimension_marker_basic/expected_review_items.json`
- Create: `fixtures/samples/dimension_marker_basic/expected_render_constraints.json`
- Create: `fixtures/samples/dimension_marker_basic/expected_correction_plan.json`
- Create: `fixtures/samples/dimension_marker_basic/expected_final_constraints.json`
- Create: `fixtures/samples/dimension_marker_basic/README.md`
- Create: `assets/style-presets/default_pretty_handwriting/preset.json`
- Create: `docs/architecture/repository-structure.md`
- Create: `docs/workflow/initial-workflow.md`
- Create: `docs/hitl/ux-policy.md`

## Task 1: Repository Foundation

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `ASSUMPTIONS.md`
- Create: `DECISIONS.md`
- Create: `pyproject.toml`
- Create: `pytest.ini`
- Create: `apps/api/.env.example`
- Create: `assets/style-presets/default_pretty_handwriting/preset.json`
- Create: `docs/architecture/repository-structure.md`
- Create: `docs/workflow/initial-workflow.md`
- Create: `docs/hitl/ux-policy.md`

- [ ] **Step 1: Add root configuration and secret handling**

Create `.gitignore`:

```gitignore
.DS_Store
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.mypy_cache/
.venv/
venv/
node_modules/
dist/
build/
coverage/
var/
*.log
.env
.env.*
!.env.example
apps/api/.env
apps/web/.env
```

Create `apps/api/.env.example`:

```env
OPENAI_API_KEY=
OPENAI_MODEL_ANALYSIS=
OPENAI_MODEL_VALIDATION=
CLEANSOLVE_STORAGE_ROOT=var/jobs
```

- [ ] **Step 2: Add Python project config**

Create `pyproject.toml`:

```toml
[project]
name = "cleansolve-studio"
version = "0.1.0"
description = "Math handwriting cleanup editor scaffold"
requires-python = ">=3.13"
dependencies = [
  "fastapi",
  "langgraph",
  "pydantic",
  "pytest",
]

[tool.pytest.ini_options]
testpaths = [
  "apps/api/tests",
  "packages/ai/tests",
  "packages/harness/tests",
  "packages/renderer/tests",
  "packages/spec/tests",
  "packages/workflow/tests",
]
pythonpath = [
  "apps/api",
  "packages/ai",
  "packages/harness",
  "packages/renderer",
  "packages/spec",
  "packages/workflow",
]
```

Create `pytest.ini`:

```ini
[pytest]
testpaths =
    apps/api/tests
    packages/ai/tests
    packages/harness/tests
    packages/renderer/tests
    packages/spec/tests
    packages/workflow/tests
pythonpath =
    apps/api
    packages/ai
    packages/harness
    packages/renderer
    packages/spec
    packages/workflow
```

- [ ] **Step 3: Add repository docs**

Create `README.md` with:

```markdown
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
CLEANSOLVE_STORAGE_ROOT=var/jobs
```

Do not commit `.env` files. Use environment secrets in CI and deployment.

## First Verification

```bash
python -m pytest
```
```

Create `ASSUMPTIONS.md` with:

```markdown
# Assumptions

- The initial scaffold uses local filesystem storage under `var/jobs`.
- The built-in handwriting style preset is represented by metadata first; generated style assets can be added later.
- Mock AI output is acceptable for initial workflow and harness tests.
- Server-side deterministic rendering starts with SVG output before PNG/PDF export is completed.
- The web editor shell can render sample spec data before upload and export are feature-complete.
```

Create `DECISIONS.md` with:

```markdown
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
```

- [ ] **Step 4: Add style preset and architecture docs**

Create `assets/style-presets/default_pretty_handwriting/preset.json`:

```json
{
  "preset_id": "default_pretty_handwriting",
  "preset_version": "v1",
  "source": "system_builtin",
  "description": "Default operator-managed handwriting style preset for the MVP.",
  "rendering_notes": {
    "formula_priority": "accuracy_first",
    "text_style": "clean_handwritten",
    "color_preservation": true
  }
}
```

Create `docs/architecture/repository-structure.md`:

```markdown
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
```

Create `docs/workflow/initial-workflow.md`:

```markdown
# Initial Workflow

The first runtime workflow uses LangGraph and follows this path:

```text
CREATED
STYLE_PRESET_LOADED
SPEC_EXTRACTED
SPEC_VALIDATING
RENDERED
INSPECTING
CORRECTION_PLANNING
AUTO_REVISING
APPROVED or NEEDS_REVIEW
```

The workflow loads the system built-in style preset, uses a mock analysis client to produce a candidate spec, validates that spec, renders an SVG overlay preview, inspects the render with a deterministic mock issue, creates a correction plan before correction, applies one bounded automatic revision, then exposes only `requires_human_review=true` items.

`max_revision_attempts` defaults to `2`. The scaffold test asserts the mock workflow auto-revises before HITL and ends with no visible review items.
```

Create `docs/hitl/ux-policy.md`:

```markdown
# HITL UX Policy

HITL is an exception path. `needs_review=true` means the system needs internal validation or automatic correction. It does not mean the user sees the item.

Only `requires_human_review=true` items are exposed in the editor review panel. The review panel budget is three items per job. Jobs that exceed three visible items should be treated as a quality warning in the harness.

Corrections should be visual first:

- approve or reject a candidate
- drag an endpoint
- drag a label
- drag a curve control point
- choose from candidates

The default UI must not ask users to type mathematical point names, segment names, or commands such as `OR` or `QR`.
```

- [ ] **Step 5: Verify foundation**

Run:

```bash
python -m pytest
```

Expected: pytest discovers no tests or only later-added tests. It must not fail due to config import errors.

- [ ] **Step 6: Commit foundation**

```bash
git add .gitignore README.md ASSUMPTIONS.md DECISIONS.md pyproject.toml pytest.ini apps/api/.env.example assets docs/architecture docs/workflow docs/hitl
git commit -m "chore: scaffold repository foundation"
```

## Task 2: Candidate Spec Models and Validation

**Files:**
- Create: `packages/spec/cleansolve_spec/__init__.py`
- Create: `packages/spec/cleansolve_spec/models.py`
- Create: `packages/spec/cleansolve_spec/validation.py`
- Create: `packages/spec/tests/test_validation.py`

- [ ] **Step 1: Write failing validation tests**

Create `packages/spec/tests/test_validation.py`:

```python
from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, StylePreset
from cleansolve_spec.validation import validate_candidate_spec, visible_review_items


def make_spec(element: Element) -> CandidateSpec:
    return CandidateSpec(
        job_id="job_test",
        version=1,
        source_images={
            "problem_image_id": "problem_test",
            "teacher_solution_image_id": "solution_test",
        },
        style=StylePreset(
            source="system_builtin",
            preset_id="default_pretty_handwriting",
            preset_version="v1",
        ),
        page=Page(width=1080, height=1920),
        regions=[],
        elements=[element],
        uncertainties=[],
    )


def test_dimension_curve_requires_target_anchors():
    element = Element(
        id="el_dim",
        type="dimension_curve",
        color="red",
        confidence=0.85,
        needs_review=True,
        evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 100]),
        bbox=[10, 10, 100, 100],
        geometry={"kind": "dimension_curve", "label_anchor": [50, 50]},
    )

    report = validate_candidate_spec(make_spec(element))

    assert report.passed is False
    assert report.issues[0].type == "missing_dimension_target_anchor"


def test_needs_review_is_not_user_visible_by_default():
    element = Element(
        id="el_formula",
        type="formula_line",
        color="blue",
        confidence=0.61,
        needs_review=True,
        requires_human_review=False,
        evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
        bbox=[10, 10, 100, 40],
    )

    items = visible_review_items(make_spec(element))

    assert items == []


def test_review_item_budget_limits_visible_items_to_three():
    elements = [
        Element(
            id=f"el_{index}",
            type="formula_line",
            color="red",
            confidence=0.4,
            needs_review=True,
            requires_human_review=True,
            evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 40]),
            bbox=[10, 10, 100, 40],
        )
        for index in range(5)
    ]
    spec = make_spec(elements[0])
    spec.elements = elements

    items = visible_review_items(spec)

    assert [item["element_id"] for item in items] == ["el_0", "el_1", "el_2"]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest packages/spec/tests/test_validation.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cleansolve_spec'`.

- [ ] **Step 3: Implement models and validation**

Create `packages/spec/cleansolve_spec/__init__.py`:

```python
from .models import CandidateSpec, Element, Evidence, Page, StylePreset, ValidationIssue, ValidationReport
from .validation import validate_candidate_spec, visible_review_items

__all__ = [
    "CandidateSpec",
    "Element",
    "Evidence",
    "Page",
    "StylePreset",
    "ValidationIssue",
    "ValidationReport",
    "validate_candidate_spec",
    "visible_review_items",
]
```

Create `packages/spec/cleansolve_spec/models.py`:

```python
from typing import Any, Literal

from pydantic import BaseModel, Field


PrimitiveType = Literal[
    "formula_line",
    "text_note",
    "highlight_line",
    "highlight_curve",
    "dimension_line",
    "dimension_curve",
    "freehand_dimension_marker",
    "arrow",
    "box",
    "circle",
    "angle_mark",
    "point_label",
    "segment_label",
    "graph_point",
    "graph_curve",
    "graph_tangent",
    "shaded_area",
    "choice_mark",
    "freehand_annotation",
    "unsupported_annotation",
]


class Evidence(BaseModel):
    source: str
    bbox: list[float] = Field(min_length=4, max_length=4)


class StylePreset(BaseModel):
    source: Literal["system_builtin"]
    preset_id: str
    preset_version: str
    description: str | None = None


class Page(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Region(BaseModel):
    id: str
    type: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    preserve_original: bool = True


class Element(BaseModel):
    id: str
    type: PrimitiveType
    source_region: str | None = None
    color: str | None = None
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False
    requires_human_review: bool = False
    auto_correctable: bool = False
    evidence: Evidence
    bbox: list[float] = Field(min_length=4, max_length=4)
    geometry: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    interaction: dict[str, Any] = Field(default_factory=dict)
    validation: dict[str, Any] = Field(default_factory=dict)
    revision_history: list[dict[str, Any]] = Field(default_factory=list)
    text: str | None = None
    display_text: str | None = None
    label: str | None = None
    review_reason: str | None = None


class CandidateSpec(BaseModel):
    job_id: str
    version: int = Field(ge=1)
    source_images: dict[str, str]
    style: StylePreset
    page: Page
    regions: list[Region] = Field(default_factory=list)
    elements: list[Element] = Field(default_factory=list)
    uncertainties: list[dict[str, Any]] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    issue_id: str
    type: str
    severity: Literal["low", "medium", "high"]
    element_id: str | None = None
    message: str
    auto_correctable: bool = False


class ValidationReport(BaseModel):
    report_id: str
    passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
```

Create `packages/spec/cleansolve_spec/validation.py`:

```python
from .models import CandidateSpec, ValidationIssue, ValidationReport

DIMENSION_TYPES = {"dimension_line", "dimension_curve", "freehand_dimension_marker"}


def _bbox_inside_page(bbox: list[float], width: int, height: int) -> bool:
    x1, y1, x2, y2 = bbox
    return 0 <= x1 <= x2 <= width and 0 <= y1 <= y2 <= height


def validate_candidate_spec(spec: CandidateSpec) -> ValidationReport:
    issues: list[ValidationIssue] = []

    if spec.style.source != "system_builtin":
        issues.append(
            ValidationIssue(
                issue_id="issue_style_source",
                type="invalid_style_source",
                severity="high",
                message="MVP specs must use a system_builtin style preset.",
            )
        )

    for element in spec.elements:
        if not _bbox_inside_page(element.bbox, spec.page.width, spec.page.height):
            issues.append(
                ValidationIssue(
                    issue_id=f"issue_{element.id}_bbox",
                    type="bbox_out_of_bounds",
                    severity="high",
                    element_id=element.id,
                    message="Element bbox must stay inside the page.",
                )
            )

        if element.type in DIMENSION_TYPES:
            missing_start = "target_anchor_start" not in element.geometry
            missing_end = "target_anchor_end" not in element.geometry
            if missing_start or missing_end:
                issues.append(
                    ValidationIssue(
                        issue_id=f"issue_{element.id}_target_anchor",
                        type="missing_dimension_target_anchor",
                        severity="high",
                        element_id=element.id,
                        message="Dimension elements require target_anchor_start and target_anchor_end.",
                        auto_correctable=element.auto_correctable,
                    )
                )

            has_label = bool(element.label or element.geometry.get("label"))
            if has_label and "label_anchor" not in element.geometry:
                issues.append(
                    ValidationIssue(
                        issue_id=f"issue_{element.id}_label_anchor",
                        type="missing_dimension_label_anchor",
                        severity="medium",
                        element_id=element.id,
                        message="Dimension labels require label_anchor.",
                        auto_correctable=element.auto_correctable,
                    )
                )

    return ValidationReport(
        report_id=f"report_{spec.job_id}_v{spec.version}",
        passed=len(issues) == 0,
        issues=issues,
    )


def visible_review_items(spec: CandidateSpec, budget: int = 3) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for element in spec.elements:
        if not element.requires_human_review:
            continue
        items.append(
            {
                "element_id": element.id,
                "type": element.type,
                "review_reason": element.review_reason or "Human review required.",
            }
        )
    return items[:budget]
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
python -m pytest packages/spec/tests/test_validation.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit spec package**

```bash
git add packages/spec
git commit -m "feat(spec): add candidate spec validation"
```

## Task 3: Deterministic Overlay Renderer

**Files:**
- Create: `packages/renderer/cleansolve_renderer/__init__.py`
- Create: `packages/renderer/cleansolve_renderer/overlay.py`
- Create: `packages/renderer/tests/test_overlay.py`

- [ ] **Step 1: Write failing renderer tests**

Create `packages/renderer/tests/test_overlay.py`:

```python
from cleansolve_renderer.overlay import render_overlay_svg
from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, StylePreset


def test_renderer_preserves_dimension_target_and_visible_strokes():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_marker",
                type="freehand_dimension_marker",
                color="red",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 120, 100]),
                bbox=[10, 10, 120, 100],
                geometry={
                    "kind": "freehand_dimension_marker",
                    "target_anchor_start": [20, 80],
                    "target_anchor_end": [120, 40],
                    "visible_strokes": [
                        {"stroke_id": "s1", "points": [[25, 75], [45, 60], [60, 55]]},
                        {"stroke_id": "s2", "points": [[70, 52], [95, 45], [115, 42]]}
                    ],
                    "label": "1",
                    "label_anchor": [65, 50],
                    "stroke_continuity": "fragmented"
                },
            )
        ],
    )

    svg = render_overlay_svg(spec)

    assert 'data-element-id="el_marker"' in svg
    assert 'data-target-anchor-start="20,80"' in svg
    assert 'data-target-anchor-end="120,40"' in svg
    assert 'data-stroke-continuity="fragmented"' in svg
    assert ">1<" in svg
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest packages/renderer/tests/test_overlay.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cleansolve_renderer'`.

- [ ] **Step 3: Implement SVG overlay renderer**

Create `packages/renderer/cleansolve_renderer/__init__.py`:

```python
from .overlay import render_overlay_svg

__all__ = ["render_overlay_svg"]
```

Create `packages/renderer/cleansolve_renderer/overlay.py`:

```python
from html import escape

from cleansolve_spec.models import CandidateSpec, Element


def _point_attr(point: list[float]) -> str:
    return ",".join(str(int(value)) if float(value).is_integer() else str(value) for value in point)


def _polyline(points: list[list[float]], color: str, attrs: str) -> str:
    pairs = " ".join(_point_attr(point) for point in points)
    return f'<polyline points="{pairs}" fill="none" stroke="{escape(color)}" stroke-width="3" {attrs} />'


def _render_freehand_dimension_marker(element: Element) -> list[str]:
    geometry = element.geometry
    color = element.color or "black"
    base_attrs = (
        f'data-element-id="{escape(element.id)}" '
        f'data-target-anchor-start="{_point_attr(geometry["target_anchor_start"])}" '
        f'data-target-anchor-end="{_point_attr(geometry["target_anchor_end"])}" '
        f'data-stroke-continuity="{escape(str(geometry.get("stroke_continuity", "unknown")))}"'
    )
    output = [f"<g {base_attrs}>"]
    for stroke in geometry.get("visible_strokes", []):
        output.append(_polyline(stroke["points"], color, f'data-stroke-id="{escape(stroke["stroke_id"])}"'))
    label = geometry.get("label") or element.label
    if label and "label_anchor" in geometry:
        x, y = geometry["label_anchor"]
        output.append(f'<text x="{x}" y="{y}" fill="{escape(color)}">{escape(str(label))}</text>')
    output.append("</g>")
    return output


def render_overlay_svg(spec: CandidateSpec) -> str:
    body: list[str] = []
    for element in spec.elements:
        if element.type == "freehand_dimension_marker":
            body.extend(_render_freehand_dimension_marker(element))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{spec.page.width}" height="{spec.page.height}" '
        f'viewBox="0 0 {spec.page.width} {spec.page.height}">'
        + "".join(body)
        + "</svg>"
    )
```

- [ ] **Step 4: Run renderer tests**

Run:

```bash
python -m pytest packages/renderer/tests/test_overlay.py packages/spec/tests/test_validation.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit renderer**

```bash
git add packages/renderer
git commit -m "feat(renderer): add deterministic overlay prototype"
```

## Task 4: Mock AI Adapter and Fixtures

**Files:**
- Create: `packages/ai/cleansolve_ai/__init__.py`
- Create: `packages/ai/cleansolve_ai/adapter.py`
- Create: `packages/ai/cleansolve_ai/mock_client.py`
- Create: `packages/ai/tests/test_mock_client.py`
- Create: `fixtures/samples/dimension_marker_basic/expected_partial_spec.json`
- Create: `fixtures/samples/dimension_marker_basic/expected_review_items.json`
- Create: `fixtures/samples/dimension_marker_basic/expected_render_constraints.json`
- Create: `fixtures/samples/dimension_marker_basic/expected_correction_plan.json`
- Create: `fixtures/samples/dimension_marker_basic/expected_final_constraints.json`
- Create: `fixtures/samples/dimension_marker_basic/README.md`

- [ ] **Step 1: Write failing mock client test**

Create `packages/ai/tests/test_mock_client.py`:

```python
from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_spec.validation import validate_candidate_spec, visible_review_items


def test_mock_analysis_client_returns_dimension_marker_spec():
    spec = MockAnalysisClient().extract_candidate_spec(job_id="job_mock")

    report = validate_candidate_spec(spec)
    review_items = visible_review_items(spec)

    assert spec.style.source == "system_builtin"
    assert spec.elements[0].type == "freehand_dimension_marker"
    assert report.passed is True
    assert review_items == []
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
python -m pytest packages/ai/tests/test_mock_client.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cleansolve_ai'`.

- [ ] **Step 3: Implement mock AI adapter**

Create `packages/ai/cleansolve_ai/__init__.py`:

```python
from .adapter import AnalysisClient
from .mock_client import MockAnalysisClient

__all__ = ["AnalysisClient", "MockAnalysisClient"]
```

Create `packages/ai/cleansolve_ai/adapter.py`:

```python
from typing import Protocol

from cleansolve_spec.models import CandidateSpec


class AnalysisClient(Protocol):
    def extract_candidate_spec(self, job_id: str) -> CandidateSpec:
        """Return a candidate rendering spec extracted from source images."""
```

Create `packages/ai/cleansolve_ai/mock_client.py`:

```python
from cleansolve_spec.models import CandidateSpec, Element, Evidence, Page, Region, StylePreset


class MockAnalysisClient:
    def extract_candidate_spec(self, job_id: str) -> CandidateSpec:
        return CandidateSpec(
            job_id=job_id,
            version=1,
            source_images={
                "problem_image_id": f"{job_id}_problem",
                "teacher_solution_image_id": f"{job_id}_teacher_solution",
            },
            style=StylePreset(
                source="system_builtin",
                preset_id="default_pretty_handwriting",
                preset_version="v1",
                description="Default operator-managed handwriting style preset.",
            ),
            page=Page(width=1080, height=1920),
            regions=[
                Region(id="region_diagram", type="diagram", bbox=[120, 420, 960, 980], preserve_original=True),
                Region(id="region_solution", type="solution_area", bbox=[80, 1080, 1000, 1800], preserve_original=False),
            ],
            elements=[
                Element(
                    id="el_freehand_dimension_001",
                    type="freehand_dimension_marker",
                    color="red",
                    confidence=0.82,
                    needs_review=True,
                    requires_human_review=False,
                    auto_correctable=True,
                    evidence=Evidence(source="teacher_solution_image", bbox=[160, 430, 540, 850]),
                    bbox=[160, 430, 540, 850],
                    geometry={
                        "kind": "freehand_dimension_marker",
                        "target_anchor_start": [180, 820],
                        "target_anchor_end": [520, 470],
                        "visible_strokes": [
                            {"stroke_id": "s1", "points": [[190, 805], [210, 720], [250, 650]]},
                            {"stroke_id": "s2", "points": [[305, 580], [370, 510], [500, 455]]}
                        ],
                        "label": "1",
                        "label_anchor": [280, 610],
                        "offset_side": "left",
                        "stroke_continuity": "fragmented",
                    },
                    interaction={
                        "allowed": [
                            "drag_target_anchor_start",
                            "drag_target_anchor_end",
                            "drag_visible_stroke",
                            "drag_label",
                        ]
                    },
                )
            ],
            uncertainties=[
                {
                    "id": "unc_001",
                    "element_id": "el_freehand_dimension_001",
                    "type": "dimension_endpoint_uncertain",
                    "review_ui": "drag_dimension_endpoint",
                    "user_visible_by_default": False,
                }
            ],
        )
```

- [ ] **Step 4: Add fixture JSON files**

Create `fixtures/samples/dimension_marker_basic/expected_review_items.json`:

```json
[]
```

Create `fixtures/samples/dimension_marker_basic/expected_render_constraints.json`:

```json
{
  "must_include": [
    "data-element-id=\"el_freehand_dimension_001\"",
    "data-target-anchor-start=\"180,820\"",
    "data-target-anchor-end=\"520,470\"",
    "data-stroke-continuity=\"fragmented\""
  ]
}
```

Create `fixtures/samples/dimension_marker_basic/expected_correction_plan.json`:

```json
{
  "revision_id": "rev_001",
  "source_preview_id": "rendered_preview_v1",
  "issues": [
    {
      "issue_id": "issue_auto_001",
      "type": "dimension_endpoint_mismatch",
      "severity": "high",
      "auto_correctable": true
    }
  ],
  "actions": [
    {
      "action_id": "act_001",
      "type": "spec_patch",
      "element_id": "el_freehand_dimension_001",
      "patch": {
        "geometry.target_anchor_end": [520, 470]
      }
    }
  ],
  "requires_human_review": false
}
```

Create `fixtures/samples/dimension_marker_basic/expected_final_constraints.json`:

```json
{
  "max_revision_attempts": 2,
  "expected_revision_attempts": 1,
  "expected_status": "APPROVED",
  "expected_visible_review_items": 0
}
```

Create `fixtures/samples/dimension_marker_basic/expected_partial_spec.json`:

```json
{
  "job_id": "fixture_dimension_marker_basic",
  "version": 1,
  "source_images": {
    "problem_image_id": "fixture_dimension_marker_basic_problem",
    "teacher_solution_image_id": "fixture_dimension_marker_basic_teacher_solution"
  },
  "style": {
    "source": "system_builtin",
    "preset_id": "default_pretty_handwriting",
    "preset_version": "v1",
    "description": "Default operator-managed handwriting style preset."
  },
  "page": {
    "width": 1080,
    "height": 1920
  },
  "regions": [
    {
      "id": "region_diagram",
      "type": "diagram",
      "bbox": [120, 420, 960, 980],
      "preserve_original": true
    },
    {
      "id": "region_solution",
      "type": "solution_area",
      "bbox": [80, 1080, 1000, 1800],
      "preserve_original": false
    }
  ],
  "elements": [
    {
      "id": "el_freehand_dimension_001",
      "type": "freehand_dimension_marker",
      "source_region": null,
      "color": "red",
      "confidence": 0.82,
      "needs_review": true,
      "requires_human_review": false,
      "auto_correctable": true,
      "evidence": {
        "source": "teacher_solution_image",
        "bbox": [160, 430, 540, 850]
      },
      "bbox": [160, 430, 540, 850],
      "geometry": {
        "kind": "freehand_dimension_marker",
        "target_anchor_start": [180, 820],
        "target_anchor_end": [520, 470],
        "visible_strokes": [
          {
            "stroke_id": "s1",
            "points": [[190, 805], [210, 720], [250, 650]]
          },
          {
            "stroke_id": "s2",
            "points": [[305, 580], [370, 510], [500, 455]]
          }
        ],
        "label": "1",
        "label_anchor": [280, 610],
        "offset_side": "left",
        "stroke_continuity": "fragmented"
      },
      "style": {},
      "interaction": {
        "allowed": [
          "drag_target_anchor_start",
          "drag_target_anchor_end",
          "drag_visible_stroke",
          "drag_label"
        ]
      },
      "validation": {},
      "revision_history": [],
      "text": null,
      "display_text": null,
      "label": null,
      "review_reason": null
    }
  ],
  "uncertainties": [
    {
      "id": "unc_001",
      "element_id": "el_freehand_dimension_001",
      "type": "dimension_endpoint_uncertain",
      "review_ui": "drag_dimension_endpoint",
      "user_visible_by_default": false
    }
  ]
}
```

Create `fixtures/samples/dimension_marker_basic/README.md`:

```markdown
# Dimension Marker Basic Fixture

This fixture represents a fragmented freehand dimension marker with a label. It protects the distinction between a dimension marker and a highlight curve.

The fixture has no committed source images yet. The JSON contracts are enough for the initial scaffold harness.
```

- [ ] **Step 5: Run AI tests**

Run:

```bash
python -m pytest packages/ai/tests/test_mock_client.py packages/spec/tests/test_validation.py -q
```

Expected: `4 passed`.

- [ ] **Step 6: Commit mock AI and fixtures**

```bash
git add packages/ai fixtures/samples/dimension_marker_basic
git commit -m "feat(ai): add mock analysis fixture"
```

## Task 5: Harness Metrics and Correction Contracts

**Files:**
- Create: `packages/harness/cleansolve_harness/__init__.py`
- Create: `packages/harness/cleansolve_harness/metrics.py`
- Create: `packages/harness/cleansolve_harness/runner.py`
- Create: `packages/harness/tests/test_metrics.py`

- [ ] **Step 1: Write failing harness tests**

Create `packages/harness/tests/test_metrics.py`:

```python
from cleansolve_harness.metrics import HarnessMetrics, summarize_review_budget


def test_review_budget_passes_when_exposure_rate_is_under_target():
    metrics = HarnessMetrics(
        total_jobs=5,
        jobs_requiring_human_review=1,
        total_visible_review_items=3,
        jobs_over_review_item_budget=0,
    )

    summary = summarize_review_budget(metrics)

    assert summary["hitl_exposure_rate"] == 0.2
    assert summary["average_review_items"] == 0.6
    assert summary["passes_hitl_target"] is True


def test_review_budget_fails_when_any_job_exceeds_three_items():
    metrics = HarnessMetrics(
        total_jobs=2,
        jobs_requiring_human_review=1,
        total_visible_review_items=4,
        jobs_over_review_item_budget=1,
    )

    summary = summarize_review_budget(metrics)

    assert summary["passes_review_item_budget"] is False
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest packages/harness/tests/test_metrics.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cleansolve_harness'`.

- [ ] **Step 3: Implement harness metrics**

Create `packages/harness/cleansolve_harness/__init__.py`:

```python
from .metrics import HarnessMetrics, summarize_review_budget

__all__ = ["HarnessMetrics", "summarize_review_budget"]
```

Create `packages/harness/cleansolve_harness/metrics.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessMetrics:
    total_jobs: int
    jobs_requiring_human_review: int
    total_visible_review_items: int
    jobs_over_review_item_budget: int


def summarize_review_budget(metrics: HarnessMetrics) -> dict[str, float | bool]:
    hitl_exposure_rate = (
        metrics.jobs_requiring_human_review / metrics.total_jobs
        if metrics.total_jobs
        else 0.0
    )
    average_review_items = (
        metrics.total_visible_review_items / metrics.total_jobs
        if metrics.total_jobs
        else 0.0
    )
    return {
        "hitl_exposure_rate": hitl_exposure_rate,
        "average_review_items": average_review_items,
        "passes_hitl_target": hitl_exposure_rate <= 0.2,
        "passes_average_review_item_target": average_review_items <= 1,
        "passes_review_item_budget": metrics.jobs_over_review_item_budget == 0,
    }
```

Create `packages/harness/cleansolve_harness/runner.py`:

```python
from cleansolve_spec.models import CandidateSpec
from cleansolve_spec.validation import visible_review_items

from .metrics import HarnessMetrics


def collect_metrics(specs: list[CandidateSpec]) -> HarnessMetrics:
    total_visible = 0
    jobs_requiring_review = 0
    jobs_over_budget = 0
    for spec in specs:
        items = visible_review_items(spec)
        total_visible += len(items)
        if items:
            jobs_requiring_review += 1
        if len(items) > 3:
            jobs_over_budget += 1
    return HarnessMetrics(
        total_jobs=len(specs),
        jobs_requiring_human_review=jobs_requiring_review,
        total_visible_review_items=total_visible,
        jobs_over_review_item_budget=jobs_over_budget,
    )
```

- [ ] **Step 4: Run harness tests**

Run:

```bash
python -m pytest packages/harness/tests/test_metrics.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit harness**

```bash
git add packages/harness
git commit -m "feat(harness): add review budget metrics"
```

## Task 6: LangGraph Workflow Prototype

**Files:**
- Create: `packages/workflow/cleansolve_workflow/__init__.py`
- Create: `packages/workflow/cleansolve_workflow/state.py`
- Create: `packages/workflow/cleansolve_workflow/nodes.py`
- Create: `packages/workflow/cleansolve_workflow/graph.py`
- Create: `packages/workflow/tests/test_graph.py`

- [ ] **Step 1: Write failing workflow tests**

Create `packages/workflow/tests/test_graph.py`:

```python
from cleansolve_workflow.graph import run_mock_workflow


def test_workflow_auto_revises_before_human_review():
    state = run_mock_workflow(job_id="job_workflow")

    assert state["status"] == "APPROVED"
    assert state["revision_attempts"] == 1
    assert state["max_revision_attempts"] == 2
    assert state["review_items"] == []
    assert state["correction_plans"][0]["actions"][0]["type"] == "spec_patch"
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
python -m pytest packages/workflow/tests/test_graph.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cleansolve_workflow'`.

- [ ] **Step 3: Implement workflow state and nodes**

Create `packages/workflow/cleansolve_workflow/__init__.py`:

```python
from .graph import build_graph, run_mock_workflow

__all__ = ["build_graph", "run_mock_workflow"]
```

Create `packages/workflow/cleansolve_workflow/state.py`:

```python
from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    job_id: str
    status: str
    candidate_spec: Any
    validation_reports: list[Any]
    correction_plans: list[dict[str, Any]]
    revision_attempts: int
    max_revision_attempts: int
    review_items: list[dict[str, str]]
    rendered_preview: str
```

Create `packages/workflow/cleansolve_workflow/nodes.py`:

```python
from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_renderer.overlay import render_overlay_svg
from cleansolve_spec.validation import validate_candidate_spec, visible_review_items

from .state import WorkflowState


def load_style_preset(state: WorkflowState) -> WorkflowState:
    state["status"] = "STYLE_PRESET_LOADED"
    return state


def analyze_sources(state: WorkflowState) -> WorkflowState:
    state["status"] = "SPEC_EXTRACTED"
    state["candidate_spec"] = MockAnalysisClient().extract_candidate_spec(state["job_id"])
    return state


def validate_spec(state: WorkflowState) -> WorkflowState:
    report = validate_candidate_spec(state["candidate_spec"])
    state.setdefault("validation_reports", []).append(report)
    state["status"] = "SPEC_VALIDATING"
    return state


def render_preview(state: WorkflowState) -> WorkflowState:
    state["rendered_preview"] = render_overlay_svg(state["candidate_spec"])
    state["status"] = "RENDERED"
    return state


def inspect_render(state: WorkflowState) -> WorkflowState:
    state["status"] = "INSPECTING"
    state["inspection_issue"] = {
        "issue_id": "issue_auto_001",
        "type": "dimension_endpoint_mismatch",
        "severity": "high",
        "auto_correctable": True,
    }
    return state


def plan_correction(state: WorkflowState) -> WorkflowState:
    issue = state["inspection_issue"]
    state.setdefault("correction_plans", []).append(
        {
            "revision_id": "rev_001",
            "source_preview_id": "rendered_preview_v1",
            "issues": [issue],
            "actions": [
                {
                    "action_id": "act_001",
                    "type": "spec_patch",
                    "element_id": "el_freehand_dimension_001",
                    "patch": {"geometry.target_anchor_end": [520, 470]},
                }
            ],
            "requires_human_review": False,
        }
    )
    state["status"] = "CORRECTION_PLANNING"
    return state


def apply_correction(state: WorkflowState) -> WorkflowState:
    state["revision_attempts"] = state.get("revision_attempts", 0) + 1
    state["status"] = "AUTO_REVISING"
    return state


def decide_human_review(state: WorkflowState) -> WorkflowState:
    state["review_items"] = visible_review_items(state["candidate_spec"])
    state["status"] = "NEEDS_REVIEW" if state["review_items"] else "APPROVED"
    return state
```

Create `packages/workflow/cleansolve_workflow/graph.py`:

```python
from langgraph.graph import END, StateGraph

from .nodes import (
    analyze_sources,
    apply_correction,
    decide_human_review,
    inspect_render,
    load_style_preset,
    plan_correction,
    render_preview,
    validate_spec,
)
from .state import WorkflowState


def build_graph():
    graph = StateGraph(WorkflowState)
    graph.add_node("load_style_preset", load_style_preset)
    graph.add_node("analyze_sources", analyze_sources)
    graph.add_node("validate_spec", validate_spec)
    graph.add_node("render_preview", render_preview)
    graph.add_node("inspect_render", inspect_render)
    graph.add_node("plan_correction", plan_correction)
    graph.add_node("apply_correction", apply_correction)
    graph.add_node("decide_human_review", decide_human_review)

    graph.set_entry_point("load_style_preset")
    graph.add_edge("load_style_preset", "analyze_sources")
    graph.add_edge("analyze_sources", "validate_spec")
    graph.add_edge("validate_spec", "render_preview")
    graph.add_edge("render_preview", "inspect_render")
    graph.add_edge("inspect_render", "plan_correction")
    graph.add_edge("plan_correction", "apply_correction")
    graph.add_edge("apply_correction", "decide_human_review")
    graph.add_edge("decide_human_review", END)
    return graph.compile()


def run_mock_workflow(job_id: str) -> WorkflowState:
    app = build_graph()
    return app.invoke(
        {
            "job_id": job_id,
            "status": "CREATED",
            "validation_reports": [],
            "correction_plans": [],
            "revision_attempts": 0,
            "max_revision_attempts": 2,
            "review_items": [],
        }
    )
```

- [ ] **Step 4: Run workflow tests**

Run:

```bash
python -m pytest packages/workflow/tests/test_graph.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit workflow**

```bash
git add packages/workflow
git commit -m "feat(workflow): add LangGraph self-revision prototype"
```

## Task 7: FastAPI Job Shell

**Files:**
- Create: `apps/api/cleansolve_api/__init__.py`
- Create: `apps/api/cleansolve_api/main.py`
- Create: `apps/api/cleansolve_api/settings.py`
- Create: `apps/api/cleansolve_api/routes/__init__.py`
- Create: `apps/api/cleansolve_api/routes/jobs.py`
- Create: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Write failing API tests**

Create `apps/api/tests/test_jobs_api.py`:

```python
from fastapi.testclient import TestClient

from cleansolve_api.main import app


def test_create_job_and_run_mock_workflow():
    client = TestClient(app)

    create_response = client.post("/jobs")
    job_id = create_response.json()["job_id"]
    run_response = client.post(f"/jobs/{job_id}/run")

    assert create_response.status_code == 201
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "APPROVED"
    assert run_response.json()["revision_attempts"] == 1


def test_review_items_endpoint_hides_internal_needs_review_items():
    client = TestClient(app)

    job_id = client.post("/jobs").json()["job_id"]
    client.post(f"/jobs/{job_id}/run")
    response = client.get(f"/jobs/{job_id}/review-items")

    assert response.status_code == 200
    assert response.json()["items"] == []
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cleansolve_api'`.

- [ ] **Step 3: Implement API shell**

Create `apps/api/cleansolve_api/__init__.py`:

```python
```

Create `apps/api/cleansolve_api/settings.py`:

```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    storage_root: str = os.getenv("CLEANSOLVE_STORAGE_ROOT", "var/jobs")


settings = Settings()
```

Create `apps/api/cleansolve_api/routes/__init__.py`:

```python
from .jobs import router as jobs_router

__all__ = ["jobs_router"]
```

Create `apps/api/cleansolve_api/routes/jobs.py`:

```python
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from cleansolve_workflow.graph import run_mock_workflow

router = APIRouter()
_jobs: dict[str, dict] = {}


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
def create_job() -> dict[str, str]:
    job_id = str(uuid4())
    _jobs[job_id] = {"job_id": job_id, "status": "CREATED", "review_items": []}
    return {"job_id": job_id, "status": "CREATED"}


@router.post("/jobs/{job_id}/run")
def run_job(job_id: str) -> dict:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    state = run_mock_workflow(job_id)
    _jobs[job_id] = {
        "job_id": job_id,
        "status": state["status"],
        "revision_attempts": state["revision_attempts"],
        "review_items": state["review_items"],
    }
    return _jobs[job_id]


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _jobs[job_id]


@router.get("/jobs/{job_id}/review-items")
def get_review_items(job_id: str) -> dict[str, list[dict[str, str]]]:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"items": _jobs[job_id].get("review_items", [])}
```

Create `apps/api/cleansolve_api/main.py`:

```python
from fastapi import FastAPI

from cleansolve_api.routes import jobs_router

app = FastAPI(title="CleanSolve Studio API")
app.include_router(jobs_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run API tests**

Run:

```bash
python -m pytest apps/api/tests/test_jobs_api.py packages/workflow/tests/test_graph.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit API shell**

```bash
git add apps/api
git commit -m "feat(api): add job workflow shell"
```

## Task 8: Web Editor Shell

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/app/App.tsx`
- Create: `apps/web/src/editor/EditorCanvas.tsx`
- Create: `apps/web/src/editor/ReviewPanel.tsx`
- Create: `apps/web/src/editor/interactionPolicy.ts`
- Create: `apps/web/src/api/client.ts`
- Create: `apps/web/src/types/spec.ts`
- Create: `apps/web/src/styles.css`

- [ ] **Step 1: Add web package manifest**

Create `apps/web/package.json`:

```json
{
  "name": "@cleansolve/web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "typescript": "latest",
    "react": "latest",
    "react-dom": "latest",
    "konva": "latest",
    "react-konva": "latest",
    "lucide-react": "latest"
  },
  "devDependencies": {
    "vitest": "latest"
  }
}
```

- [ ] **Step 2: Add web types and interaction policy**

Create `apps/web/src/types/spec.ts`:

```typescript
export type PrimitiveType =
  | 'formula_line'
  | 'text_note'
  | 'highlight_line'
  | 'highlight_curve'
  | 'dimension_line'
  | 'dimension_curve'
  | 'freehand_dimension_marker'
  | 'arrow'
  | 'box'
  | 'circle'
  | 'angle_mark'
  | 'point_label'
  | 'segment_label'
  | 'graph_point'
  | 'graph_curve'
  | 'graph_tangent'
  | 'shaded_area'
  | 'choice_mark'
  | 'freehand_annotation'
  | 'unsupported_annotation';

export interface ReviewItem {
  element_id: string;
  type: PrimitiveType;
  review_reason: string;
}
```

Create `apps/web/src/editor/interactionPolicy.ts`:

```typescript
import type { PrimitiveType } from '../types/spec';

export const interactionPolicy: Record<PrimitiveType, string[]> = {
  formula_line: ['choose_candidate', 'edit_text', 'move', 'adjust_line_spacing', 'change_color'],
  text_note: ['choose_candidate', 'edit_text', 'move', 'change_color'],
  highlight_line: ['drag_start', 'drag_end', 'move', 'change_color', 'adjust_width'],
  highlight_curve: ['drag_start', 'drag_end', 'drag_control_point', 'move', 'change_color', 'adjust_width'],
  dimension_line: ['drag_target_anchor_start', 'drag_target_anchor_end', 'drag_visible_offset', 'drag_label', 'choose_endpoint_style', 'change_color'],
  dimension_curve: ['drag_target_anchor_start', 'drag_target_anchor_end', 'drag_curve_control_point', 'drag_curve_offset', 'drag_label', 'choose_endpoint_style', 'change_color'],
  freehand_dimension_marker: ['drag_target_anchor_start', 'drag_target_anchor_end', 'move_visible_stroke_group', 'adjust_stroke_point', 'drag_label', 'change_color', 'preserve_stroke_continuity'],
  arrow: ['drag_start', 'drag_end', 'choose_arrow_head', 'drag_label', 'change_color'],
  box: ['resize', 'move', 'change_color', 'adjust_width'],
  circle: ['resize', 'move', 'change_color', 'adjust_width'],
  angle_mark: ['drag_vertex', 'drag_start_ray', 'drag_end_ray', 'adjust_radius', 'drag_label', 'change_color'],
  point_label: ['drag_point', 'drag_label', 'change_color'],
  segment_label: ['drag_label', 'change_color'],
  graph_point: ['drag_point', 'drag_label', 'snap_to_graph', 'change_color'],
  graph_curve: ['drag_control_point', 'drag_endpoint', 'change_color'],
  graph_tangent: ['drag_control_point', 'drag_endpoint', 'drag_tangent_point', 'change_color'],
  shaded_area: ['drag_polygon_handle', 'adjust_opacity', 'change_color', 'drag_label'],
  choice_mark: ['move', 'change_color'],
  freehand_annotation: ['move', 'scale', 'adjust_opacity', 'redraw'],
  unsupported_annotation: ['view_source_crop', 'keep_original', 'manual_edit']
};
```

- [ ] **Step 3: Add app shell**

Create `apps/web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CleanSolve Studio</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `apps/web/src/main.tsx`:

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './app/App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Create `apps/web/src/app/App.tsx`:

```typescript
import { EditorCanvas } from '../editor/EditorCanvas';
import { ReviewPanel } from '../editor/ReviewPanel';

export function App() {
  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>CleanSolve Studio</h1>
            <p>Style preset: default_pretty_handwriting v1</p>
          </div>
        </header>
        <EditorCanvas />
      </section>
      <ReviewPanel items={[]} />
    </main>
  );
}
```

Create `apps/web/src/editor/EditorCanvas.tsx`:

```typescript
import { Circle, Group, Layer, Line, Stage, Text } from 'react-konva';

export function EditorCanvas() {
  return (
    <div className="canvas-frame" aria-label="CleanSolve preview canvas">
      <Stage width={720} height={520}>
        <Layer>
          <Text x={24} y={24} text="Problem image layer" fontSize={18} fill="#334155" />
          <Group>
            <Line
              points={[160, 360, 190, 300, 245, 250]}
              stroke="#dc2626"
              strokeWidth={4}
              tension={0.45}
              lineCap="round"
              lineJoin="round"
            />
            <Line
              points={[280, 220, 360, 170, 430, 145]}
              stroke="#dc2626"
              strokeWidth={4}
              tension={0.45}
              lineCap="round"
              lineJoin="round"
            />
            <Text x={245} y={248} text="1" fontSize={26} fill="#dc2626" />
            <Circle x={160} y={360} radius={6} fill="#0f766e" draggable />
            <Circle x={430} y={145} radius={6} fill="#0f766e" draggable />
          </Group>
        </Layer>
      </Stage>
    </div>
  );
}
```

Create `apps/web/src/editor/ReviewPanel.tsx`:

```typescript
import type { ReviewItem } from '../types/spec';

interface ReviewPanelProps {
  items: ReviewItem[];
}

export function ReviewPanel({ items }: ReviewPanelProps) {
  return (
    <aside className="review-panel">
      <h2>Review</h2>
      {items.length === 0 ? (
        <p>No user-visible review items.</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item.element_id}>
              <strong>{item.type}</strong>
              <span>{item.review_reason}</span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
```

Create `apps/web/src/api/client.ts`:

```typescript
export async function createJob(baseUrl = ''): Promise<{ job_id: string; status: string }> {
  const response = await fetch(`${baseUrl}/jobs`, { method: 'POST' });
  if (!response.ok) {
    throw new Error('Failed to create job');
  }
  return response.json();
}
```

Create `apps/web/src/styles.css`:

```css
body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #172033;
  background: #f6f7f9;
}

.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
}

.workspace {
  padding: 24px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.topbar h1 {
  font-size: 24px;
  margin: 0 0 4px;
}

.topbar p {
  margin: 0;
  color: #64748b;
}

.canvas-frame {
  width: 720px;
  height: 520px;
  background: #ffffff;
  border: 1px solid #d5dae1;
  border-radius: 8px;
  overflow: hidden;
}

.review-panel {
  border-left: 1px solid #d5dae1;
  background: #ffffff;
  padding: 24px;
}

.review-panel h2 {
  font-size: 18px;
  margin: 0 0 16px;
}

.review-panel p {
  color: #64748b;
}
```

- [ ] **Step 4: Verify web files are syntactically scoped**

Run:

```bash
test -f apps/web/package.json
test -f apps/web/src/editor/interactionPolicy.ts
```

Expected: both commands exit with status `0`.

- [ ] **Step 5: Commit web shell**

```bash
git add apps/web
git commit -m "feat(web): add editor shell"
```

## Task 9: Final Verification

**Files:**
- Modify only files required to fix verification issues from prior tasks.

- [ ] **Step 1: Run full Python test suite**

Run:

```bash
python -m pytest -q
```

Expected: all Python tests pass.

- [ ] **Step 2: Check secret handling**

Run:

```bash
git check-ignore apps/api/.env
```

Expected output:

```text
apps/api/.env
```

- [ ] **Step 3: Check SoT remains unmodified**

Run:

```bash
git diff -- SoT.md
```

Expected: no output.

- [ ] **Step 4: Commit final fixes if needed**

If verification required fixes, inspect the changed files:

```bash
git status --short
```

Stage only files listed by `git status --short` that were changed to fix verification failures, then commit:

```bash
git commit -m "chore: finalize scaffold verification"
```

If `git status --short` has no output, do not create an empty commit.
