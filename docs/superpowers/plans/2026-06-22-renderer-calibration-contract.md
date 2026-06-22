# Renderer Calibration Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a committed `default_pretty_handwriting v1` renderer calibration contract and make the deterministic SVG renderer consume it without reading ignored `/image` artifacts at runtime.

**Architecture:** The renderer gets a focused `style.py` module that loads and validates the committed calibration JSON, converts it to a frozen `RendererStyle`, and provides small resolver helpers for semantic color, font size, stroke width, and opacity. `overlay.py` keeps its public API unchanged, resolves a `RendererStyle` once per render, and applies calibrated defaults while preserving element inline style precedence.

**Tech Stack:** Python 3.11, Pydantic spec models, stdlib `json`/`dataclasses`/`pathlib`, pytest, deterministic SVG string rendering.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-06-22-renderer-calibration-contract-design.md`

## File Map

- Create: `assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json`
  - Committed draft calibration token contract derived from local `style_profile.generated.json`.
- Create: `packages/renderer/cleansolve_renderer/style.py`
  - Renderer calibration loader, validator, `RendererStyle` dataclass, fallback style, semantic color/font/stroke/opacity resolvers.
- Create: `packages/renderer/tests/test_style.py`
  - Unit tests for calibration loading, fallback, semantic color, and invalid calibration behavior.
- Modify: `assets/style-presets/default_pretty_handwriting/preset.json`
  - Adds renderer calibration metadata and changes `calibration_status` to `renderer_calibration_draft`.
- Modify: `packages/renderer/cleansolve_renderer/__init__.py`
  - Exports style resolver types/functions needed by renderer tests and later packages.
- Modify: `packages/renderer/cleansolve_renderer/overlay.py`
  - Applies `RendererStyle` inside existing SVG renderer while preserving `render_overlay_svg(spec)` signature.
- Modify: `packages/renderer/tests/test_overlay.py`
  - Updates existing expectations and adds calibrated renderer behavior coverage.
- Modify: `docs/product/handwriting-style-reference-set.md`
  - Documents that `renderer_calibration.v1.json` is committed draft contract and `/image` profile remains ignored runtime input.

## Contracts To Preserve

- `render_overlay_svg(spec: CandidateSpec) -> str` remains the public renderer entrypoint.
- Runtime renderer never reads `image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json`.
- `image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json` stays ignored and untracked.
- Unknown style preset or broken committed calibration file must not crash rendering; renderer uses fallback style.
- Valid element inline `font_size`, `stroke_width`, and `opacity` override calibration defaults.
- Invalid inline bool/non-number/out-of-range style values are ignored.
- This milestone does not implement hatching, style similarity gates, visual diff gates, web UI, LangGraph runtime integration, or gpt-image-2 asset generation.

---

### Task 1: Calibration Artifact And Renderer Style Resolver

**Files:**
- Create: `assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json`
- Create: `packages/renderer/cleansolve_renderer/style.py`
- Create: `packages/renderer/tests/test_style.py`
- Modify: `assets/style-presets/default_pretty_handwriting/preset.json`
- Modify: `packages/renderer/cleansolve_renderer/__init__.py`

- [ ] **Step 1: Write failing style resolver tests**

Create `packages/renderer/tests/test_style.py` with these tests:

```python
import json
from pathlib import Path

import pytest

from cleansolve_renderer.style import (
    RendererStyleError,
    load_renderer_calibration,
    renderer_style_for_preset,
    resolve_font_size,
    resolve_opacity,
    resolve_semantic_color,
    resolve_stroke_width,
)
from cleansolve_spec.models import StylePreset


CALIBRATION_PATH = Path("assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json")


def default_preset() -> StylePreset:
    return StylePreset(
        source="system_builtin",
        preset_id="default_pretty_handwriting",
        preset_version="v1",
    )


def test_load_renderer_calibration_returns_contract():
    payload = load_renderer_calibration(CALIBRATION_PATH)

    assert payload["schema_version"] == "renderer_calibration.v1"
    assert payload["preset_id"] == "default_pretty_handwriting"
    assert payload["preset_version"] == "v1"
    assert payload["status"] == "draft_needs_review"
    assert payload["tokens"]["palette"]["blue"] == "#34309A"
    assert payload["renderer_mapping"]["generic_stroke_width_px"] == 2.0
    assert payload["renderer_mapping"]["diagram_stroke_width_px"] == 1.9
    assert payload["renderer_mapping"]["highlight_opacity"] == 0.35


def test_renderer_style_for_default_preset_uses_calibration():
    style = renderer_style_for_preset(default_preset())

    assert style.status == "draft_needs_review"
    assert style.palette_blue == "#34309A"
    assert style.palette_red_orange == "#E1583E"
    assert style.generic_stroke_width_px == 2.0
    assert style.diagram_stroke_width_px == 1.9
    assert style.text_letter_spacing_px == 0.25
    assert style.text_line_height_ratio == 1.32


def test_renderer_style_for_unknown_preset_uses_fallback():
    style = renderer_style_for_preset(
        StylePreset(source="system_builtin", preset_id="unknown", preset_version="v1")
    )

    assert style.status == "fallback"
    assert style.preset_id == "unknown"
    assert style.preset_version == "v1"
    assert style.palette_black == "black"
    assert style.generic_stroke_width_px == 2


def test_resolve_semantic_color_maps_only_known_semantics():
    style = renderer_style_for_preset(default_preset())

    assert resolve_semantic_color(None, style) == "#222222"
    assert resolve_semantic_color("", style) == "#222222"
    assert resolve_semantic_color("black", style) == "#222222"
    assert resolve_semantic_color("blue", style) == "#34309A"
    assert resolve_semantic_color("red", style) == "#E1583E"
    assert resolve_semantic_color("red_orange", style) == "#E1583E"
    assert resolve_semantic_color("purple", style) == "purple"


def test_inline_numeric_resolvers_accept_valid_values_and_reject_invalid_values():
    assert resolve_stroke_width({"stroke_width": 3.5}, default_width=2.0) == 3.5
    assert resolve_stroke_width({"stroke_width": True}, default_width=2.0) == 2.0
    assert resolve_stroke_width({"stroke_width": 0}, default_width=2.0) == 2.0
    assert resolve_font_size({"font_size": 21}, default_size=16) == 21
    assert resolve_font_size({"font_size": False}, default_size=16) == 16
    assert resolve_font_size({"font_size": -1}, default_size=16) == 16
    assert resolve_opacity({"opacity": 0}, default_opacity=0.35) == 0
    assert resolve_opacity({"opacity": 1.2}, default_opacity=0.35) == 0.35
    assert resolve_opacity({"opacity": False}, default_opacity=0.35) == 0.35


def test_invalid_calibration_file_raises_style_error(tmp_path):
    invalid = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    invalid["schema_version"] = "wrong"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(RendererStyleError, match="invalid renderer calibration schema_version"):
        load_renderer_calibration(path)


def test_renderer_style_falls_back_when_calibration_loader_fails(monkeypatch, tmp_path):
    broken_path = tmp_path / "broken.json"
    broken_path.write_text("{", encoding="utf-8")
    monkeypatch.setattr("cleansolve_renderer.style.DEFAULT_RENDERER_CALIBRATION_PATH", broken_path)

    style = renderer_style_for_preset(default_preset())

    assert style.status == "fallback"
    assert style.palette_black == "black"
```

- [ ] **Step 2: Run the style tests and verify they fail**

Run:

```bash
pytest packages/renderer/tests/test_style.py -q
```

Expected: FAIL because `cleansolve_renderer.style` and `renderer_calibration.v1.json` do not exist.

- [ ] **Step 3: Add calibration JSON**

Create `assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json` with exactly:

```json
{
  "deferred_tokens": [
    "stroke.jitter_px",
    "formula.baseline_jitter_px",
    "formula.symbol_slant_deg",
    "formula.vertical_compactness",
    "diagram.hatching_gap_px",
    "diagram.hatching_angle_jitter_deg"
  ],
  "preset_id": "default_pretty_handwriting",
  "preset_version": "v1",
  "renderer_mapping": {
    "diagram_stroke_width_px": 1.9,
    "dimension_label_font_size_px": 16,
    "formula_font_size_px": 18,
    "generic_stroke_width_px": 2.0,
    "highlight_opacity": 0.35,
    "highlight_stroke_width_px": 8,
    "label_font_size_px": 14,
    "text_font_size_px": 16
  },
  "schema_version": "renderer_calibration.v1",
  "source": {
    "kind": "style_profile",
    "path": "image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json",
    "profile_status": "needs_review"
  },
  "status": "draft_needs_review",
  "tokens": {
    "diagram": {
      "annotation_line_width_px": 1.9,
      "hatching_angle_jitter_deg": 5.0,
      "hatching_gap_px": 6.5,
      "label_offset_px": 7.0
    },
    "formula": {
      "baseline_jitter_px": 0.9,
      "fraction_bar_width_px": 1.8,
      "symbol_slant_deg": 3.0,
      "vertical_compactness": 0.86
    },
    "palette": {
      "black": "#222222",
      "blue": "#34309A",
      "red_orange": "#E1583E"
    },
    "stroke": {
      "black_width_px": 2.0,
      "blue_width_px": 2.1,
      "jitter_px": 0.45,
      "opacity": 0.94,
      "red_width_px": 2.1
    },
    "text": {
      "korean_baseline_jitter_px": 1.2,
      "letter_spacing_px": 0.25,
      "line_height_ratio": 1.32,
      "size_ratio_to_formula": 0.88
    }
  }
}
```

- [ ] **Step 4: Implement style resolver module**

Create `packages/renderer/cleansolve_renderer/style.py` with:

- `RendererStyleError(ValueError)`.
- Frozen dataclass `RendererStyle` with all fields from the design spec.
- Constant `DEFAULT_RENDERER_CALIBRATION_PATH`.
- `load_renderer_calibration(path: Path) -> dict[str, object]`.
- `renderer_style_for_preset(style_preset: StylePreset) -> RendererStyle`.
- `resolve_semantic_color`, `resolve_stroke_width`, `resolve_font_size`, `resolve_opacity`.

Implementation requirements:

- `DEFAULT_RENDERER_CALIBRATION_PATH = Path(__file__).resolve().parents[3] / "assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json"`.
- `load_renderer_calibration` reads UTF-8 JSON and validates exactly the rules in the design spec.
- JSON parse errors, non-object JSON, missing keys, invalid schema version/status/palette/numeric values all raise `RendererStyleError` with a short message.
- `renderer_style_for_preset` returns fallback unless the preset is exactly `system_builtin/default_pretty_handwriting/v1`.
- `renderer_style_for_preset` catches `RendererStyleError` and `OSError` from loading and returns fallback.
- Fallback values are exactly those in the design spec.
- Resolver helpers reject bool even though bool is an `int` subclass.

- [ ] **Step 5: Update preset metadata**

Modify `assets/style-presets/default_pretty_handwriting/preset.json`:

- Change `"calibration_status": "reference_contract_ready"` to `"calibration_status": "renderer_calibration_draft"`.
- Add:

```json
"renderer_calibration": {
  "runtime_reads_ignored_artifacts": false,
  "schema_version": "renderer_calibration.v1",
  "source_profile_artifact": "image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json",
  "status": "draft_needs_review",
  "tokens_filename": "renderer_calibration.v1.json"
}
```

Keep JSON sorted enough for readability; do not remove existing `style_lab` or `rendering_notes`.

- [ ] **Step 6: Export style API**

Modify `packages/renderer/cleansolve_renderer/__init__.py` to export:

```python
from .style import (
    RendererStyle,
    RendererStyleError,
    load_renderer_calibration,
    renderer_style_for_preset,
    resolve_font_size,
    resolve_opacity,
    resolve_semantic_color,
    resolve_stroke_width,
)
```

Add these names to `__all__`.

- [ ] **Step 7: Run tests and verify pass**

Run:

```bash
pytest packages/renderer/tests/test_style.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json assets/style-presets/default_pretty_handwriting/preset.json packages/renderer/cleansolve_renderer/style.py packages/renderer/cleansolve_renderer/__init__.py packages/renderer/tests/test_style.py
git commit -m "feat(renderer): add calibration style resolver"
```

---

### Task 2: Apply Calibration To Text And Generic Overlay Primitives

**Files:**
- Modify: `packages/renderer/cleansolve_renderer/overlay.py`
- Modify: `packages/renderer/tests/test_overlay.py`

- [ ] **Step 1: Write failing overlay calibration tests**

Modify `packages/renderer/tests/test_overlay.py`:

- In `test_renderer_preserves_source_image_metadata`, add assertions:

```python
assert 'data-style-preset-id="default_pretty_handwriting"' in svg
assert 'data-style-preset-version="v1"' in svg
assert 'data-renderer-calibration-status="draft_needs_review"' in svg
```

- In `test_renderer_renders_formula_line_and_text_note`, update/add assertions:

```python
assert (
    '<text x="30" y="40" fill="navy" font-family="serif" '
    'font-size="20" data-text-kind="formula_line">x &lt; y</text>'
) in svg
assert (
    '<text x="50" y="70" fill="#222222" font-family="sans-serif" '
    'font-size="16" letter-spacing="0.25" data-text-kind="text_note">check &amp; solve</text>'
) in svg
assert 'data-line-height-ratio="1.32"' in svg
```

- Add a new test:

```python
def test_renderer_uses_calibrated_semantic_palette_and_strokes():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_arrow",
                type="arrow",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 80, 20]),
                bbox=[10, 10, 80, 20],
                geometry={"start": [10, 20], "end": [90, 20]},
            ),
            Element(
                id="el_box",
                type="box",
                color="red",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[20, 30, 100, 50]),
                bbox=[20, 30, 100, 50],
            ),
            Element(
                id="el_circle",
                type="circle",
                color="black",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[100, 120, 40, 60]),
                bbox=[100, 120, 40, 60],
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert '<line x1="10" y1="20" x2="90" y2="20" stroke="#34309A" stroke-width="2"' in svg
    assert '<rect x="20" y="30" width="100" height="50" fill="none" stroke="#E1583E" stroke-width="2"' in svg
    assert '<circle cx="120" cy="150" r="20" fill="none" stroke="#222222" stroke-width="2"' in svg
```

- Add a new test:

```python
def test_renderer_inline_style_overrides_calibration():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_arrow",
                type="arrow",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 80, 20]),
                bbox=[10, 10, 80, 20],
                geometry={"start": [10, 20], "end": [90, 20]},
                style={"stroke_width": 3.5},
            ),
            Element(
                id="el_note",
                type="text_note",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 50, 120, 40]),
                bbox=[40, 50, 120, 40],
                geometry={"anchor": [50, 70], "text": "note"},
                style={"font_size": 21},
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'stroke="#34309A" stroke-width="3.5"' in svg
    assert 'font-size="21" letter-spacing="0.25" data-text-kind="text_note">note</text>' in svg
```

- Add a new test:

```python
def test_renderer_ignores_invalid_inline_style_values():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_arrow",
                type="arrow",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 80, 20]),
                bbox=[10, 10, 80, 20],
                geometry={"start": [10, 20], "end": [90, 20]},
                style={"stroke_width": True},
            ),
            Element(
                id="el_note",
                type="text_note",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 50, 120, 40]),
                bbox=[40, 50, 120, 40],
                geometry={"anchor": [50, 70], "text": "note"},
                style={"font_size": False},
            ),
            Element(
                id="el_highlight",
                type="highlight_line",
                confidence=0.8,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 90, 90, 20]),
                bbox=[10, 90, 90, 20],
                geometry={"start": [10, 100], "end": [100, 100]},
                style={"opacity": False},
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert 'stroke="#34309A" stroke-width="2"' in svg
    assert 'font-size="16" letter-spacing="0.25" data-text-kind="text_note">note</text>' in svg
    assert 'opacity="0.35"' in svg
```

- [ ] **Step 2: Run focused overlay tests and verify failure**

Run:

```bash
pytest packages/renderer/tests/test_overlay.py -q
```

Expected: FAIL because `overlay.py` does not yet add calibration metadata or resolve semantic colors from calibration.

- [ ] **Step 3: Wire renderer style into overlay**

Modify `packages/renderer/cleansolve_renderer/overlay.py`:

- Import:

```python
from cleansolve_renderer.style import (
    RendererStyle,
    renderer_style_for_preset,
    resolve_font_size,
    resolve_opacity,
    resolve_semantic_color,
    resolve_stroke_width,
)
```

- In `render_overlay_svg`, compute:

```python
renderer_style = renderer_style_for_preset(spec.style)
rendered_elements = [
    rendered for element in spec.elements if (rendered := _render_element(element, renderer_style))
]
```

- Add top-level SVG attrs:

```python
"data-style-preset-id": renderer_style.preset_id,
"data-style-preset-version": renderer_style.preset_version,
"data-renderer-calibration-status": renderer_style.status,
```

- Change `_render_element(element: Element)` to `_render_element(element: Element, renderer_style: RendererStyle)`.
- Pass `renderer_style` to every renderer helper.

- [ ] **Step 4: Apply calibration to text primitives**

Modify `_render_text_element`:

- Signature becomes:

```python
def _render_text_element(
    element: Element,
    renderer_style: RendererStyle,
    text_kind: str,
    font_family: str,
    default_font_size: float,
) -> str:
```

- Resolve color:

```python
color = resolve_semantic_color(element.color, renderer_style)
```

- Resolve font size:

```python
font_size = resolve_font_size(element.style, default_size=default_font_size)
```

- Group attrs include:

```python
"data-style-status": renderer_style.status,
"data-line-height-ratio": _format_number(renderer_style.text_line_height_ratio),
```

- `text_attrs` includes `letter-spacing` only when `text_kind == "text_note"` and `renderer_style.text_letter_spacing_px != 0`.

- Default call values:
  - `formula_line`: `renderer_style.formula_font_size_px`
  - `text_note`: `renderer_style.text_font_size_px`

- [ ] **Step 5: Apply calibration to generic shape primitives**

For `_render_arrow`, `_render_box`, `_render_circle`:

- Resolve color with `resolve_semantic_color`.
- Use `resolve_stroke_width(element.style, default_width=renderer_style.generic_stroke_width_px)`.

For `_render_point_label`:

- Resolve color with `resolve_semantic_color`.
- If `label_anchor` is missing, use `renderer_style.label_offset_px` instead of hard-coded 8.
- Use `resolve_font_size(element.style, default_size=renderer_style.label_font_size_px)` for label font.

For `_render_segment_label`:

- Resolve color with `resolve_semantic_color`.
- Use `resolve_font_size(element.style, default_size=renderer_style.label_font_size_px)`.

For `_render_highlight_line` and `_render_highlight_curve`:

- Keep default color `#ffd84d`.
- Use `resolve_stroke_width(element.style, default_width=renderer_style.highlight_stroke_width_px)`.
- Use `resolve_opacity(element.style, default_opacity=renderer_style.highlight_opacity)`.

- [ ] **Step 6: Run focused tests and verify pass**

Run:

```bash
pytest packages/renderer/tests/test_style.py packages/renderer/tests/test_overlay.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add packages/renderer/cleansolve_renderer/overlay.py packages/renderer/tests/test_overlay.py
git commit -m "feat(renderer): apply calibration to overlay primitives"
```

---

### Task 3: Apply Calibration To Dimension And Freehand Primitives

**Files:**
- Modify: `packages/renderer/cleansolve_renderer/overlay.py`
- Modify: `packages/renderer/tests/test_overlay.py`

- [ ] **Step 1: Add failing dimension/freehand calibration tests**

Modify `packages/renderer/tests/test_overlay.py`:

- Add:

```python
def test_renderer_uses_calibrated_point_label_offset():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=300, height=200),
        elements=[
            Element(
                id="el_point",
                type="point_label",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[10, 20, 30, 20]),
                bbox=[10, 20, 30, 20],
                geometry={"point": [15, 25]},
                label="A",
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert '<circle cx="15" cy="25" r="3" fill="#34309A" />' in svg
    assert '<text x="22" y="18" fill="#34309A" font-family="sans-serif" font-size="14">A</text>' in svg
```

- Add:

```python
def test_renderer_uses_calibrated_dimension_stroke_width():
    spec = CandidateSpec(
        job_id="job_render",
        version=1,
        source_images={"problem_image_id": "p", "teacher_solution_image_id": "s"},
        style=StylePreset(source="system_builtin", preset_id="default_pretty_handwriting", preset_version="v1"),
        page=Page(width=400, height=300),
        elements=[
            Element(
                id="el_dimension_line",
                type="dimension_line",
                color="red_orange",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 50, 140, 30]),
                bbox=[40, 50, 140, 30],
                geometry={
                    "target_anchor_start": [40, 60],
                    "target_anchor_end": [180, 60],
                    "visible_start": [45, 70],
                    "visible_end": [175, 70],
                    "label_anchor": [100, 55],
                    "label": "5",
                },
            ),
            Element(
                id="el_dimension_curve",
                type="dimension_curve",
                color="blue",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 100, 140, 60]),
                bbox=[40, 100, 140, 60],
                geometry={
                    "target_anchor_start": [40, 140],
                    "target_anchor_end": [180, 140],
                    "visible_start": [45, 145],
                    "visible_end": [175, 145],
                    "control_points": [[100, 90]],
                    "label_anchor": [102, 120],
                    "label": "arc",
                },
            ),
            Element(
                id="el_freehand",
                type="freehand_dimension_marker",
                color="black",
                confidence=0.9,
                evidence=Evidence(source="teacher_solution_image", bbox=[40, 180, 140, 60]),
                bbox=[40, 180, 140, 60],
                geometry={
                    "target_anchor_start": [40, 220],
                    "target_anchor_end": [180, 220],
                    "visible_strokes": [
                        {"stroke_id": "stroke_a", "points": [[45, 215], [90, 205], [175, 216]]}
                    ],
                    "label_anchor": [100, 195],
                    "label": "free",
                },
            ),
        ],
    )

    svg = render_overlay_svg(spec)

    assert_xml_parseable(svg)
    assert '<line x1="45" y1="70" x2="175" y2="70" stroke="#E1583E" stroke-width="1.9"' in svg
    assert '<path d="M 45,145 Q 100,90 175,145" fill="none" stroke="#34309A" stroke-width="1.9"' in svg
    assert '<polyline data-stroke-id="stroke_a" points="45,215 90,205 175,216" fill="none" stroke="#222222" stroke-width="1.9"' in svg
    assert '<text x="100" y="55" fill="#E1583E" font-family="sans-serif" font-size="16">5</text>' in svg
    assert '<text x="102" y="120" fill="#34309A" font-family="sans-serif" font-size="16">arc</text>' in svg
    assert '<text x="100" y="195" fill="#222222" font-family="sans-serif" font-size="16">free</text>' in svg
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
pytest packages/renderer/tests/test_overlay.py -q
```

Expected: FAIL because dimension/freehand renderers still use hard-coded stroke width and label font size.

- [ ] **Step 3: Apply style to dimension renderers**

Modify `packages/renderer/cleansolve_renderer/overlay.py`:

- `_render_dimension_line(element, renderer_style)`:
  - `color = resolve_semantic_color(element.color, renderer_style)`.
  - `stroke-width = resolve_stroke_width(element.style, default_width=renderer_style.diagram_stroke_width_px)`.
  - Pass `renderer_style.dimension_label_font_size_px` to label rendering.

- `_render_dimension_curve(element, renderer_style)`:
  - Same color/stroke/label rules as dimension line.

- `_dimension_group_attrs` remains deterministic and keeps target anchor metadata.

- [ ] **Step 4: Apply style to freehand dimension marker**

Modify:

- `_render_freehand_dimension_marker(element, renderer_style)`.
- `_render_visible_stroke(stroke, color, stroke_width)`.
- `_render_label(element, geometry, color, font_size)`.

Rules:

- Freehand color uses `resolve_semantic_color`.
- Freehand visible stroke width uses `resolve_stroke_width(element.style, default_width=renderer_style.diagram_stroke_width_px)`.
- Label font size uses `resolve_font_size(element.style, default_size=renderer_style.dimension_label_font_size_px)`.
- Keep existing `data-target-anchor-start`, `data-target-anchor-end`, and `data-stroke-continuity` attributes.

- [ ] **Step 5: Run renderer tests and verify pass**

Run:

```bash
pytest packages/renderer/tests -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add packages/renderer/cleansolve_renderer/overlay.py packages/renderer/tests/test_overlay.py
git commit -m "feat(renderer): calibrate dimension overlays"
```

---

### Task 4: Documentation And Product Contract

**Files:**
- Modify: `docs/product/handwriting-style-reference-set.md`

- [ ] **Step 1: Update product documentation**

Append this section to `docs/product/handwriting-style-reference-set.md` after the existing `## GPT-5.5 Style Profile Extraction` section:

```markdown
## Renderer Calibration Contract

`renderer_calibration.v1.json`은 `default_pretty_handwriting v1`을 deterministic SVG renderer가 읽을 수 있게 만든 repository-committed draft contract다.

경로:

```text
assets/style-presets/default_pretty_handwriting/renderer_calibration.v1.json
```

현재 상태는 `draft_needs_review`다. 이 값은 `image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json`에서 추출한 style profile token을 기반으로 하지만, ignored local artifact를 runtime renderer가 직접 읽지는 않는다.

이번 calibration은 색상, 기본 획 두께, 텍스트/수식 크기, label offset처럼 deterministic SVG에 안전하게 반영 가능한 값만 적용한다.

이번 단계에서 완료하지 않는 항목:

- 손글씨 font 생성 또는 학습
- `gpt-image-2` asset 생성
- style similarity gate
- visual diff score gate
- Web UI 연결
- LangGraph runtime 연결
- `draft_needs_review`에서 `approved`로 상태 변경
```

- [ ] **Step 2: Verify docs contain required phrases**

Run:

```bash
rg -n "Renderer Calibration Contract|renderer_calibration.v1.json|draft_needs_review|runtime renderer가 직접 읽지는 않는다|style similarity gate" docs/product/handwriting-style-reference-set.md
```

Expected: all five phrases appear.

- [ ] **Step 3: Commit Task 4**

```bash
git add docs/product/handwriting-style-reference-set.md
git commit -m "docs(renderer): document calibration contract"
```

---

### Task 5: Verification, Review, Push, And PR

**Files:**
- No planned code edits.
- Generated ignored artifacts under `/image` must remain untracked.

- [ ] **Step 1: Run renderer tests**

Run:

```bash
pytest packages/renderer/tests -q
```

Expected: PASS.

- [ ] **Step 2: Run Style Lab tests**

Run:

```bash
pytest tools/style_lab/tests -q
```

Expected: PASS with the OpenAI smoke test skipped unless opt-in env is set.

- [ ] **Step 3: Run existing Python suite**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/spec/tests packages/workflow/tests -q
```

Expected: PASS.

- [ ] **Step 4: Verify ignored profile remains ignored**

Run:

```bash
git check-ignore -v image/style-lab/default_pretty_handwriting/v1/style_profile.generated.json
```

Expected: output references `.gitignore` and `/image/`.

- [ ] **Step 5: Run diff check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 6: Request final reviews**

Use `superpowers:requesting-code-review` with two reviewers:

- Spec compliance reviewer:
  - Base: `main` before this branch.
  - Head: current branch head.
  - Compare against `docs/superpowers/specs/2026-06-22-renderer-calibration-contract-design.md`.
  - Check excluded scope was not implemented.

- Code quality reviewer:
  - Check resolver validation, fallback behavior, overlay maintainability, test robustness, and docs accuracy.

- [ ] **Step 7: Address review findings**

For each Critical or Important finding:

1. Reproduce with a failing test or exact command.
2. Patch only the relevant files.
3. Run the narrow test.
4. Run the relevant full verification command.
5. Commit with `fix(renderer): address calibration review finding`.

- [ ] **Step 8: Push branch**

Run:

```bash
git status --short
git push -u origin feat/renderer-calibration-contract
```

Expected: branch pushes to origin.

- [ ] **Step 9: Create PR**

PR title:

```text
feat(renderer): add default handwriting calibration contract
```

PR body:

```markdown
## 요약
- `default_pretty_handwriting v1` renderer calibration draft contract를 committed JSON으로 추가했습니다.
- renderer style resolver를 추가해 semantic color, stroke width, font size, opacity 기본값을 deterministic하게 해석합니다.
- SVG overlay renderer가 calibration 값을 적용하되, element inline style이 있으면 inline style을 우선합니다.

## 검증
- [ ] `pytest packages/renderer/tests -q`
- [ ] `pytest tools/style_lab/tests -q`
- [ ] `CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/spec/tests packages/workflow/tests -q`
- [ ] `git diff --check`

## 참고
- `style_profile.generated.json`은 `/image` 아래 ignored local artifact이며 runtime renderer가 직접 읽지 않습니다.
- 이번 calibration 상태는 `draft_needs_review`입니다.
- style similarity gate, visual diff gate, font generation, gpt-image-2 asset generation은 이번 PR 범위가 아닙니다.
```
