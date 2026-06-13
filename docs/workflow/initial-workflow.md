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
