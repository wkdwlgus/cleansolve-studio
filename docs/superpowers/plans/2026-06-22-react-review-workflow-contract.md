# ReAct Review/Correction Workflow Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mock/deterministic ReAct review/correction workflow contract with tool decisions, eval gate results, and progress event artifacts that later SSE/Web milestones can consume.

**Architecture:** Add focused workflow contract modules for Pydantic models, gate evaluation, tool allowlist, deterministic progress events, and mock review planning. Then wire the existing LangGraph workflow to use those contracts while preserving the existing upload-to-approval fixture path. Finally persist review/correction and progress event artifacts through the API without adding SSE or real GPT calls.

**Tech Stack:** Python 3.11, Pydantic v2, LangGraph, FastAPI, pytest, existing local artifact store.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-06-22-react-review-workflow-contract-design.md`

## File Map

- Create: `packages/workflow/cleansolve_workflow/review_contract.py`
  - Pydantic contract models, constants, progress event helper, gate evaluation helper, score improvement helper.
- Create: `packages/workflow/cleansolve_workflow/review_tools.py`
  - Review tool allowlist and `ReviewToolRejected`.
- Create: `packages/workflow/tests/test_review_contract.py`
  - Unit tests for progress events, gate evaluation, tool allowlist, score improvement.
- Create: `packages/workflow/tests/test_react_review_workflow.py`
  - Integration tests for the deterministic mock ReAct workflow path.
- Modify: `packages/workflow/cleansolve_workflow/state.py`
  - Add optional review/progress state fields.
- Modify: `packages/workflow/cleansolve_workflow/nodes.py`
  - Replace ad hoc inspection/correction details with contract-backed review attempts, decisions, gate results, and progress events.
- Modify: `packages/workflow/cleansolve_workflow/graph.py`
  - Route based on latest gate result and latest tool decision.
- Modify: `packages/workflow/cleansolve_workflow/__init__.py`
  - Extend the existing `__all__` with public review contract helpers.
- Modify: `packages/workflow/tests/test_graph.py`
  - Update existing status expectations to the new, more explicit ReAct/progress statuses.
- Modify: `apps/api/cleansolve_api/artifacts.py`
  - Add `review_correction` and `progress_events` analysis artifact types and persistence support.
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
  - Save review/progress artifacts from run output and add latest artifact read endpoints.
- Modify: `apps/api/tests/test_jobs_api.py`
  - Add API persistence/read tests and update expected artifact ids.
- Modify: `packages/harness/tests/test_e2e.py`
  - Add progress event count metric assertion.
- Modify: `docs/product/mvp-roadmap.md`
  - Update roadmap status and next recommendation.
- Modify: `docs/product/mvp-release-checklist.md`
  - Update gap wording after contract/mock path lands.

## Contracts To Preserve

- No real GPT-5.5 call in this milestone.
- No `gpt-image-2` or image generation call in this milestone.
- No `GET /jobs/{job_id}/events` SSE endpoint in this milestone.
- No web UI changes in this milestone.
- Existing mock workflow happy path still approves the default fixture job.
- API key absence must not affect tests.
- Progress events must not contain raw prompts, raw model output, hidden reasoning, source image paths, or API keys.
- Progress event `message` must be one of the Korean allowlist strings from the design spec.
- `revision_attempts` increments only after a mutation action changes the candidate spec.
- The latest API run response must include `review_correction` and `progress_events` in `latest_analysis_artifact_ids`.

---

### Task 1: Review Contract Models And Unit Helpers

**Files:**
- Create: `packages/workflow/cleansolve_workflow/review_contract.py`
- Create: `packages/workflow/cleansolve_workflow/review_tools.py`
- Create: `packages/workflow/tests/test_review_contract.py`
- Modify: `packages/workflow/cleansolve_workflow/__init__.py`

- [ ] **Step 1: Write failing contract tests**

Create `packages/workflow/tests/test_review_contract.py` with exactly these tests:

```python
import re

import pytest

from cleansolve_workflow.review_contract import (
    APPROVED_SCORE_FIXTURE,
    DEFAULT_APPROVAL_GATE,
    MISMATCH_SCORE_FIXTURE,
    PROGRESS_MESSAGE_ALLOWLIST,
    ReviewScores,
    append_progress_event,
    evaluate_approval_gate,
    has_score_improved,
)
from cleansolve_workflow.review_tools import ReviewToolRejected, ensure_allowed_tool


def base_state():
    return {
        "job_id": "job_contract",
        "revision_attempts": 0,
        "max_revision_attempts": 2,
        "review_event_sequence": 0,
        "progress_events": [],
    }


def test_progress_event_rejects_unapproved_message():
    state = base_state()

    with pytest.raises(ValueError, match="progress event message is not allowlisted"):
        append_progress_event(
            state,
            phase="review_and_correct",
            status="INSPECTING_LAYOUT",
            message="모델 내부 추론을 요약하고 있습니다.",
            next_action="layout_check",
        )


def test_progress_event_sequence_is_deterministic():
    state = base_state()

    append_progress_event(
        state,
        phase="analysis",
        status="CREATED",
        message="작업을 시작했습니다.",
        next_action="continue",
    )
    append_progress_event(
        state,
        phase="validation",
        status="SPEC_VALIDATING",
        message="candidate spec 계약을 검증하고 있습니다.",
        next_action="continue",
    )

    events = state["progress_events"]
    assert [event.sequence for event in events] == [0, 1]
    assert [event.event_id for event in events] == ["evt_0000", "evt_0001"]
    assert state["review_event_sequence"] == 2
    assert events[0].message in PROGRESS_MESSAGE_ALLOWLIST
    assert re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z", events[0].created_at)


def test_gate_passes_when_all_thresholds_met():
    result = evaluate_approval_gate(
        scores=APPROVED_SCORE_FIXTURE,
        gate=DEFAULT_APPROVAL_GATE,
        contract_valid=True,
        visible_review_item_count=0,
        max_error_severity="none",
    )

    assert result.passed is True
    assert result.failed_reasons == []


def test_gate_fails_for_layout_score():
    result = evaluate_approval_gate(
        scores=MISMATCH_SCORE_FIXTURE,
        gate=DEFAULT_APPROVAL_GATE,
        contract_valid=True,
        visible_review_item_count=0,
        max_error_severity="high",
    )

    assert result.passed is False
    assert "layout_alignment_below_threshold" in result.failed_reasons
    assert "max_error_severity_exceeded" in result.failed_reasons


def test_gate_fails_for_visual_diff():
    result = evaluate_approval_gate(
        scores=ReviewScores(
            content_consistency=0.95,
            layout_alignment=0.9,
            style_similarity=0.78,
            visual_diff=0.26,
        ),
        gate=DEFAULT_APPROVAL_GATE,
        contract_valid=True,
        visible_review_item_count=0,
        max_error_severity="none",
    )

    assert result.passed is False
    assert result.failed_reasons == ["visual_diff_above_threshold"]


def test_review_tool_allowlist_rejects_unknown_tool():
    assert ensure_allowed_tool("inspect_layout") == "inspect_layout"

    with pytest.raises(ReviewToolRejected, match="review tool is not allowlisted"):
        ensure_allowed_tool("read_raw_prompt")


def test_score_improvement_helper_detects_improvement():
    previous = ReviewScores(
        content_consistency=0.9,
        layout_alignment=0.6,
        style_similarity=0.7,
        visual_diff=0.3,
    )

    assert has_score_improved(
        previous,
        ReviewScores(
            content_consistency=0.9,
            layout_alignment=0.61,
            style_similarity=0.7,
            visual_diff=0.3,
        ),
    )
    assert has_score_improved(
        previous,
        ReviewScores(
            content_consistency=0.9,
            layout_alignment=0.6,
            style_similarity=0.7,
            visual_diff=0.29,
        ),
    )
    assert not has_score_improved(previous, previous)
```

- [ ] **Step 2: Run contract tests and verify RED**

Run:

```bash
pytest packages/workflow/tests/test_review_contract.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `cleansolve_workflow.review_contract`.

- [ ] **Step 3: Add `review_tools.py`**

Create `packages/workflow/cleansolve_workflow/review_tools.py` with:

```python
from __future__ import annotations

from typing import cast

from .review_contract import ReviewToolName


class ReviewToolRejected(ValueError):
    pass


ALLOWED_REVIEW_TOOLS: tuple[ReviewToolName, ...] = (
    "inspect_content",
    "inspect_layout",
    "inspect_style",
    "compute_visual_diff",
    "patch_candidate_spec",
    "request_handwriting_asset",
    "rerender",
    "mark_approved",
    "escalate_hitl",
)


def ensure_allowed_tool(tool_name: str) -> ReviewToolName:
    if tool_name not in ALLOWED_REVIEW_TOOLS:
        raise ReviewToolRejected("review tool is not allowlisted")
    return cast(ReviewToolName, tool_name)
```

- [ ] **Step 4: Add `review_contract.py` model and helper implementation**

Create `packages/workflow/cleansolve_workflow/review_contract.py` with all public types from the design spec.

Implementation requirements:

- Use `BaseModel`, `ConfigDict(extra="forbid")`, and `Field` exactly as in the design.
- Define `PROGRESS_MESSAGE_ALLOWLIST` as a `frozenset[str]` containing every allowed Korean message from the design.
- Define `DEFAULT_APPROVAL_GATE = ApprovalGate(contract_valid=True)`.
- Define:

```python
MISMATCH_SCORE_FIXTURE = ReviewScores(
    content_consistency=0.95,
    layout_alignment=0.6,
    style_similarity=0.78,
    visual_diff=0.18,
)

APPROVED_SCORE_FIXTURE = ReviewScores(
    content_consistency=0.95,
    layout_alignment=0.9,
    style_similarity=0.78,
    visual_diff=0.18,
)

CONTRACT_INVALID_SCORE_FIXTURE = ReviewScores(
    content_consistency=0.0,
    layout_alignment=0.0,
    style_similarity=0.0,
    visual_diff=1.0,
)
```

- `append_progress_event` must generate `evt_{sequence:04d}` starting at `evt_0000`.
- `append_progress_event` must set `created_at` using UTC second precision and trailing `Z`.
- `evaluate_approval_gate` must return failed reasons only from the design spec allowed list and in this exact order:
  1. `contract_invalid`
  2. `content_consistency_below_threshold`
  3. `layout_alignment_below_threshold`
  4. `style_similarity_below_threshold`
  5. `visual_diff_above_threshold`
  6. `visible_review_item_budget_exceeded`
  7. `max_error_severity_exceeded`
- Severity ordering is `none < low < medium < high`.
- `has_score_improved` returns true if content/layout/style increases or visual_diff decreases.
- Add `model_dump(mode="json")` friendly models only; do not store non-serializable objects.

- [ ] **Step 5: Export public helpers**

Modify `packages/workflow/cleansolve_workflow/__init__.py` so package imports remain stable and these names are importable:

```python
from .review_contract import (
    APPROVED_SCORE_FIXTURE,
    CONTRACT_INVALID_SCORE_FIXTURE,
    DEFAULT_APPROVAL_GATE,
    MISMATCH_SCORE_FIXTURE,
    ApprovalGate,
    CorrectionAction,
    GateResult,
    ProgressEvent,
    ReviewAttempt,
    ReviewIssue,
    ReviewScores,
    ToolDecision,
    append_progress_event,
    evaluate_approval_gate,
    has_score_improved,
)
from .review_tools import ReviewToolRejected, ensure_allowed_tool
```

Extend the existing `__all__` list with these names. Keep existing `build_graph` and `run_mock_workflow` exports.

- [ ] **Step 6: Run tests and verify GREEN**

Run:

```bash
pytest packages/workflow/tests/test_review_contract.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add packages/workflow/cleansolve_workflow/review_contract.py packages/workflow/cleansolve_workflow/review_tools.py packages/workflow/cleansolve_workflow/__init__.py packages/workflow/tests/test_review_contract.py
git commit -m "feat(workflow): add review contract models"
```

---

### Task 2: Contract-Backed Mock ReAct Workflow

**Files:**
- Modify: `packages/workflow/cleansolve_workflow/state.py`
- Modify: `packages/workflow/cleansolve_workflow/nodes.py`
- Modify: `packages/workflow/cleansolve_workflow/graph.py`
- Modify: `packages/workflow/tests/test_graph.py`
- Create: `packages/workflow/tests/test_react_review_workflow.py`

- [ ] **Step 1: Write failing ReAct workflow tests**

Create `packages/workflow/tests/test_react_review_workflow.py` with:

```python
from copy import deepcopy

from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_spec.models import Element, Evidence

from cleansolve_workflow.graph import run_mock_workflow


EXPECTED_HAPPY_PATH_STATUSES = [
    "CREATED",
    "STYLE_PRESET_LOADED",
    "SPEC_EXTRACTED",
    "SPEC_VALIDATING",
    "RENDERING",
    "RENDERED",
    "INSPECTING_CONTENT",
    "INSPECTING_LAYOUT",
    "INSPECTING_STYLE",
    "COMPUTING_VISUAL_DIFF",
    "CORRECTION_PLANNING",
    "PATCHING_SPEC",
    "RE_RENDERING",
    "RENDERED",
    "SPEC_REVALIDATING",
    "INSPECTING_CONTENT",
    "INSPECTING_LAYOUT",
    "INSPECTING_STYLE",
    "COMPUTING_VISUAL_DIFF",
    "APPROVED",
]


def dumped_progress_events(state):
    return [event.model_dump(mode="json") for event in state["progress_events"]]


def test_react_workflow_auto_revises_with_progress_events():
    state = run_mock_workflow(job_id="job_react")

    assert state["status"] == "APPROVED"
    assert state["status_history"] == EXPECTED_HAPPY_PATH_STATUSES
    assert [event.status for event in state["progress_events"]] == EXPECTED_HAPPY_PATH_STATUSES
    assert len(state["review_attempts"]) >= 2
    assert state["review_attempts"][0].gate_result.failed_reasons == [
        "layout_alignment_below_threshold",
        "max_error_severity_exceeded",
    ]
    assert state["review_attempts"][-1].gate_result.passed is True
    assert dumped_progress_events(state)[0]["message"] == "작업을 시작했습니다."
    assert "source_image_paths" not in dumped_progress_events(state)[0]


def test_react_workflow_records_tool_decisions():
    state = run_mock_workflow(job_id="job_react_decisions")

    decisions = [decision.tool_name for decision in state["review_tool_decisions"]]

    assert "inspect_content" in decisions
    assert "inspect_layout" in decisions
    assert "inspect_style" in decisions
    assert "compute_visual_diff" in decisions
    assert "patch_candidate_spec" in decisions
    assert decisions[-1] == "mark_approved"


def test_react_workflow_zero_revision_budget_escalates():
    state = run_mock_workflow(job_id="job_react_zero_budget", max_revision_attempts=0)

    assert state["status"] == "REVISION_REQUIRED"
    assert state["revision_attempts"] == 0
    assert state["progress_events"][-1].status == "REVISION_REQUIRED"
    assert state["review_tool_decisions"][-1].reason_code == "revision_budget_exceeded"
    assert state["candidate_spec"].elements[0].revision_history == []


def test_react_workflow_rejects_repeated_unhelpful_patch():
    state = run_mock_workflow(
        job_id="job_react_unhelpful_patch",
        correction_patch_override={"geometry.label_anchor": [300, 620]},
    )

    assert state["status"] == "REVISION_REQUIRED"
    assert state["revision_attempts"] == 2
    assert state["review_tool_decisions"][-1].reason_code in {
        "repeated_element_patch",
        "revision_budget_exceeded",
    }
    assert state["candidate_spec"].elements[0].geometry["target_anchor_end"] != [540, 850]


def test_react_workflow_validation_failure_has_contract_invalid_gate():
    candidate_spec = MockAnalysisClient().extract_candidate_spec("job_react_invalid")
    candidate_spec.elements = [
        Element(
            id="el_invalid_dimension",
            type="dimension_curve",
            color="red",
            confidence=0.85,
            needs_review=True,
            requires_human_review=False,
            auto_correctable=False,
            evidence=Evidence(source="teacher_solution_image", bbox=[10, 10, 100, 100]),
            bbox=[10, 10, 100, 100],
            geometry={"kind": "dimension_curve", "label": "1", "label_anchor": [50, 50]},
        )
    ]

    state = run_mock_workflow(
        job_id="job_react_invalid",
        candidate_spec_override=candidate_spec,
    )

    assert state["status"] == "REVISION_REQUIRED"
    assert state["latest_gate_result"].passed is False
    assert "contract_invalid" in state["latest_gate_result"].failed_reasons
    assert state["latest_scores"].visual_diff == 1.0


def test_react_workflow_auto_correction_changes_candidate_spec_geometry():
    original_spec = MockAnalysisClient().extract_candidate_spec("job_react_patch")
    original_endpoint = deepcopy(original_spec.elements[0].geometry["target_anchor_end"])

    state = run_mock_workflow(
        job_id="job_react_patch",
        candidate_spec_override=original_spec,
    )

    element = state["candidate_spec"].elements[0]
    assert element.geometry["target_anchor_end"] != original_endpoint
    assert element.geometry["target_anchor_end"] == [540, 850]
```

- [ ] **Step 2: Update existing graph test expectations first**

Modify `packages/workflow/tests/test_graph.py`:

- Replace the old happy-path `status_history` list with `EXPECTED_HAPPY_PATH_STATUSES` from the new test.
- Replace assertions expecting `AUTO_REVISING` with `PATCHING_SPEC` or `RE_RENDERING`.
- Keep existing behavioral assertions for approval, revision attempts, review items, correction plans, and geometry patch.

- [ ] **Step 3: Run workflow tests and verify RED**

Run:

```bash
pytest packages/workflow/tests/test_graph.py packages/workflow/tests/test_react_review_workflow.py -q
```

Expected: FAIL because workflow state does not contain `progress_events`, `review_attempts`, `review_tool_decisions`, or new statuses.

- [ ] **Step 4: Extend WorkflowState**

Modify `packages/workflow/cleansolve_workflow/state.py` to include:

```python
    review_attempts: list[Any]
    progress_events: list[Any]
    latest_scores: Any
    latest_gate_result: Any
    review_tool_decisions: list[Any]
    review_event_sequence: int
```

- [ ] **Step 5: Initialize review state in `run_mock_workflow`**

Modify `packages/workflow/cleansolve_workflow/graph.py` initial state:

```python
        "review_attempts": [],
        "progress_events": [],
        "review_tool_decisions": [],
        "review_event_sequence": 0,
```

Keep `status_history` initialized to `["CREATED"]`.

- [ ] **Step 6: Add graph routing based on review contract**

Modify `_route_after_inspection` in `graph.py`:

```python
def _route_after_inspection(state: WorkflowState) -> str:
    latest_gate_result = state.get("latest_gate_result")
    if latest_gate_result is not None and latest_gate_result.passed:
        return "decide_human_review"

    decisions = state.get("review_tool_decisions", [])
    latest_decision = decisions[-1] if decisions else None
    if latest_decision is None:
        return "require_revision"
    if latest_decision.tool_name == "patch_candidate_spec":
        return "plan_correction"
    if latest_decision.tool_name in {"request_handwriting_asset", "escalate_hitl"}:
        return "require_revision"
    return "require_revision"
```

- [ ] **Step 7: Implement review helpers in `nodes.py`**

Modify `packages/workflow/cleansolve_workflow/nodes.py`:

- Import contract helpers:

```python
from cleansolve_workflow.review_contract import (
    APPROVED_SCORE_FIXTURE,
    CONTRACT_INVALID_SCORE_FIXTURE,
    DEFAULT_APPROVAL_GATE,
    MISMATCH_SCORE_FIXTURE,
    CorrectionAction,
    GateResult,
    ReviewAttempt,
    ReviewIssue,
    ToolDecision,
    append_progress_event,
    evaluate_approval_gate,
)
```

- Add a message mapping constant:

```python
STATUS_MESSAGES = {
    "CREATED": "작업을 시작했습니다.",
    "STYLE_PRESET_LOADED": "기본 손글씨 스타일을 불러왔습니다.",
    "SPEC_EXTRACTED": "원본 문제와 선생님 손풀이를 분석하고 있습니다.",
    "SPEC_VALIDATING": "candidate spec 계약을 검증하고 있습니다.",
    "SPEC_REVALIDATING": "candidate spec 계약을 검증하고 있습니다.",
    "RENDERING": "deterministic renderer로 preview를 만들고 있습니다.",
    "RENDERED": "deterministic renderer로 preview를 만들고 있습니다.",
    "INSPECTING_CONTENT": "렌더 결과의 풀이 내용을 확인하고 있습니다.",
    "INSPECTING_LAYOUT": "렌더 결과의 위치와 치수선 정합성을 확인하고 있습니다.",
    "INSPECTING_STYLE": "렌더 결과의 손글씨 스타일 일관성을 확인하고 있습니다.",
    "COMPUTING_VISUAL_DIFF": "렌더 결과의 시각적 차이를 계산하고 있습니다.",
    "CORRECTION_PLANNING": "자동 수정 계획을 세우고 있습니다.",
    "PATCHING_SPEC": "candidate spec patch를 적용하고 있습니다.",
    "REQUESTING_HANDWRITING_ASSET": "특정 손글씨 블록 asset 재생성이 필요합니다.",
    "RE_RENDERING": "수정된 spec으로 preview를 다시 렌더링하고 있습니다.",
    "APPROVED": "자동 승인 기준을 통과했습니다.",
    "NEEDS_REVIEW": "사용자 검수가 필요합니다.",
    "REVISION_REQUIRED": "자동 수정 한도에 도달했습니다.",
    "FAILED": "작업이 실패했습니다.",
}
```

- Replace `_set_status` body with status history plus progress event append:

```python
def _set_status(
    state: WorkflowState,
    status: str,
    *,
    phase: str = "review_and_correct",
    next_action: str = "continue",
    scores=None,
) -> None:
    state["status"] = status
    state.setdefault("status_history", []).append(status)
    append_progress_event(
        state,
        phase=phase,
        status=status,
        message=STATUS_MESSAGES[status],
        next_action=next_action,
        scores=scores,
    )
```

- Add a helper to remove the initial duplicate `CREATED` progress event problem:
  - Do not call `_set_status(state, "CREATED")`; the initial state only has `status_history`.
  - In `load_style_preset`, before setting style, if no progress events exist, append a `CREATED` event manually with `phase="analysis"`, `status="CREATED"`, `next_action="continue"`.

- [ ] **Step 8: Implement deterministic inspection and gate attempt**

In `nodes.py`, replace `inspect_render` so it:

1. Appends statuses in this order:
   - `INSPECTING_CONTENT`
   - `INSPECTING_LAYOUT`
   - `INSPECTING_STYLE`
   - `COMPUTING_VISUAL_DIFF`
2. Adds `ToolDecision` entries for:
   - `inspect_content`, reason `initial_content_inspection`, confidence `1.0`
   - `inspect_layout`, reason `initial_layout_inspection`, confidence `1.0`
   - `inspect_style`, reason `initial_style_inspection`, confidence `1.0`
   - `compute_visual_diff`, reason `initial_visual_diff`, confidence `1.0`
3. Uses `_find_element(state, "el_freehand_dimension_001")`.
4. If endpoint equals `[540, 850]`, uses `APPROVED_SCORE_FIXTURE`, no issues, severity `none`.
5. If endpoint differs, uses `MISMATCH_SCORE_FIXTURE`, one high `ReviewIssue` with type `dimension_endpoint_mismatch`.
6. Evaluates gate with `visible_review_item_count=len(visible_review_items(state["candidate_spec"]))`.
7. Builds a `ReviewAttempt` for the current `revision_attempts`.
8. If gate passes, appends `ToolDecision(tool_name="mark_approved", reason_code="gate_passed", confidence=1.0)`.
9. If gate fails and budget remains, appends `ToolDecision(tool_name="patch_candidate_spec", reason_code="dimension_endpoint_mismatch", target_element_id="el_freehand_dimension_001", confidence=1.0, arguments={"patch": state.get("correction_patch_override", {"geometry.target_anchor_end": EXPECTED_TARGET_ANCHOR_END})})`.
10. If budget is exhausted, appends `ToolDecision(tool_name="escalate_hitl", reason_code="revision_budget_exceeded", confidence=1.0)`.

- [ ] **Step 9: Implement validation failure contract state**

Modify `require_revision`:

- If latest validation report exists and `passed is False`, set:

```python
state["latest_scores"] = CONTRACT_INVALID_SCORE_FIXTURE
state["latest_gate_result"] = evaluate_approval_gate(
    scores=CONTRACT_INVALID_SCORE_FIXTURE,
    gate=DEFAULT_APPROVAL_GATE,
    contract_valid=False,
    visible_review_item_count=len(visible_review_items(state["candidate_spec"])),
    max_error_severity="high",
)
```

- Append a `ReviewAttempt` with one `ToolDecision(tool_name="escalate_hitl", reason_code="validation_failed", confidence=1.0)`.
- Then set status `REVISION_REQUIRED`.

- [ ] **Step 10: Implement correction planning and patching**

Modify `plan_correction`:

- Use the latest `ToolDecision`.
- Set status `CORRECTION_PLANNING`.
- Append a `correction_plans` entry that uses the decision arguments patch.
- Append `CorrectionAction(type="spec_patch")` to the current `ReviewAttempt.actions`.

Modify `apply_correction`:

- Set status `PATCHING_SPEC` before applying patch.
- Apply only `geometry.` patch paths.
- Increment `revision_attempts` after candidate spec is changed.
- Set status `RE_RENDERING`.
- Render preview.
- Set status `RENDERED`.
- Do not set `AUTO_REVISING`.

- [ ] **Step 11: Keep approval/HITL behavior**

Modify `decide_human_review`:

- Compute visible review items.
- If latest gate passed and no visible items, set `APPROVED`.
- If visible items exist, set `NEEDS_REVIEW`.

Modify `require_revision`:

- Preserve visible review items.
- Set `REVISION_REQUIRED`.

- [ ] **Step 12: Run workflow tests and verify GREEN**

Run:

```bash
pytest packages/workflow/tests -q
```

Expected: PASS.

- [ ] **Step 13: Commit Task 2**

```bash
git add packages/workflow/cleansolve_workflow/state.py packages/workflow/cleansolve_workflow/nodes.py packages/workflow/cleansolve_workflow/graph.py packages/workflow/tests/test_graph.py packages/workflow/tests/test_react_review_workflow.py
git commit -m "feat(workflow): add mock react review loop"
```

---

### Task 3: API Artifact Persistence For Review And Progress

**Files:**
- Modify: `apps/api/cleansolve_api/artifacts.py`
- Modify: `apps/api/cleansolve_api/routes/jobs.py`
- Modify: `apps/api/tests/test_jobs_api.py`

- [ ] **Step 1: Write failing API tests**

Append to `apps/api/tests/test_jobs_api.py`:

```python
def test_run_job_persists_review_correction_and_progress_events():
    client = TestClient(app)
    job = client.post("/jobs").json()
    job_id = job["job_id"]
    upload_required_images(client, job_id)

    response = client.post(f"/jobs/{job_id}/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_analysis_artifact_ids"]["review_correction"].startswith("review_")
    assert payload["latest_analysis_artifact_ids"]["progress_events"].startswith("events_")

    review_response = client.get(f"/jobs/{job_id}/review-correction")
    assert review_response.status_code == 200
    review_payload = review_response.json()
    assert review_payload["job_id"] == job_id
    assert review_payload["revision_attempts"] == 1
    assert review_payload["tool_decisions"][-1]["tool_name"] == "mark_approved"
    assert review_payload["latest_gate_result"]["passed"] is True

    events_response = client.get(f"/jobs/{job_id}/progress-events")
    assert events_response.status_code == 200
    events_payload = events_response.json()
    assert events_payload["job_id"] == job_id
    assert len(events_payload["events"]) >= 1
    assert events_payload["events"][0]["message"] == "작업을 시작했습니다."
    assert "source_image_paths" not in events_payload["events"][0]


def test_progress_events_endpoint_returns_404_before_run():
    client = TestClient(app)
    job = client.post("/jobs").json()

    response = client.get(f"/jobs/{job['job_id']}/progress-events")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "ANALYSIS_ARTIFACT_NOT_FOUND"
```

- [ ] **Step 2: Run API tests and verify RED**

Run:

```bash
pytest apps/api/tests/test_jobs_api.py -q
```

Expected: FAIL because artifact types and routes do not exist.

- [ ] **Step 3: Add artifact types**

Modify `apps/api/cleansolve_api/artifacts.py`:

- Change `AnalysisArtifactType` to include:

```python
AnalysisArtifactType = Literal[
    "candidate_spec",
    "validation_report",
    "correction_plan",
    "review_correction",
    "progress_events",
]
```

- Add to `ANALYSIS_ARTIFACT_TYPES`:

```python
    "review_correction",
    "progress_events",
```

- Add prefixes:

```python
    "review_correction": "review",
    "progress_events": "events",
```

- Add directories:

```python
    "review_correction": "reviews",
    "progress_events": "events",
```

- [ ] **Step 4: Extend `save_analysis_outputs`**

Modify signature:

```python
        review_correction_payload: dict[str, Any] | None = None,
        progress_events_payload: dict[str, Any] | None = None,
```

Build payloads with optional entries:

```python
        payloads: dict[AnalysisArtifactType, dict[str, Any]] = {
            "candidate_spec": candidate_spec_payload,
            "validation_report": validation_report_payload,
            "correction_plan": correction_plan_payload,
        }
        if review_correction_payload is not None:
            payloads["review_correction"] = review_correction_payload
        if progress_events_payload is not None:
            payloads["progress_events"] = progress_events_payload
```

Do not change `save_spec_patch_outputs`; spec patch writes only candidate spec and validation report.

- [ ] **Step 5: Add latest payload endpoints in API routes**

Modify `apps/api/cleansolve_api/routes/jobs.py`.

In `run_job`, build:

```python
review_correction_payload = {
    "job_id": job_id,
    "review_attempts": [
        attempt.model_dump(mode="json") for attempt in state.get("review_attempts", [])
    ],
    "tool_decisions": [
        decision.model_dump(mode="json") for decision in state.get("review_tool_decisions", [])
    ],
    "latest_gate_result": (
        state["latest_gate_result"].model_dump(mode="json")
        if state.get("latest_gate_result") is not None
        else None
    ),
    "revision_attempts": state["revision_attempts"],
}
progress_events_payload = {
    "job_id": job_id,
    "events": [
        event.model_dump(mode="json") for event in state.get("progress_events", [])
    ],
}
```

Pass both to `store.save_analysis_outputs`.

Add routes:

```python
@router.get("/{job_id}/review-correction")
def get_review_correction(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "review_correction")


@router.get("/{job_id}/progress-events")
def get_progress_events(job_id: str) -> dict[str, object]:
    return _store().read_latest_analysis_payload(job_id, "progress_events")
```

- [ ] **Step 6: Run API tests and verify GREEN**

Run:

```bash
pytest apps/api/tests/test_jobs_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add apps/api/cleansolve_api/artifacts.py apps/api/cleansolve_api/routes/jobs.py apps/api/tests/test_jobs_api.py
git commit -m "feat(api): persist review progress artifacts"
```

---

### Task 4: Harness Metrics And Korean Product Docs

**Files:**
- Modify: `packages/harness/tests/test_e2e.py`
- Modify: `docs/product/mvp-roadmap.md`
- Modify: `docs/product/mvp-release-checklist.md`

- [ ] **Step 1: Write failing harness assertion**

Modify `packages/harness/tests/test_e2e.py`.

In `test_api_upload_to_export_e2e_passes_with_manual_fixture`, after `assert result.export_size_bytes > 0`, add:

```python
progress_payload = client.get(f"/jobs/{result.job_id}/progress-events").json()
assert len(progress_payload["events"]) >= 1
assert progress_payload["events"][0]["message"] == "작업을 시작했습니다."
```

- [ ] **Step 2: Run harness test and verify pass or expected fail**

Run:

```bash
pytest packages/harness/tests/test_e2e.py -q
```

Expected after Task 3: PASS.

- [ ] **Step 3: Update roadmap doc**

Modify `docs/product/mvp-roadmap.md`:

- In current status summary, update `Workflow orchestrator` note to:

```markdown
LangGraph self-revision prototype에 ReAct review/correction contract, eval gate result, progress event artifact가 추가됐으나 실제 GPT-5.5 planner와 SSE stream은 아직 없음
```

- In `## 다음 추천 작업`, change priority list so the first item is:

```markdown
1. job progress SSE stream과 web progress UI
```

- Move renderer calibration out of the top recommendation and state:

```markdown
`default_pretty_handwriting v1` renderer calibration contract는 완료됐고, 다음 UX 병목은 긴 review/correction loop 진행 상황을 사용자에게 보여주는 것이다.
```

- [ ] **Step 4: Update release checklist doc**

Modify `docs/product/mvp-release-checklist.md`:

- Change:

```markdown
- GPT-5.5 기반 ReAct review/correction agent와 score 기반 eval gate가 없다.
```

to:

```markdown
- ReAct review/correction contract와 mock eval gate는 있으나 실제 GPT-5.5 planner와 실제 eval model은 없다.
```

- Change remaining gap:

```markdown
- GPT-5.5 기반 ReAct review/correction workflow
```

to:

```markdown
- 실제 GPT-5.5 기반 ReAct planner 연결
```

- Keep `job progress SSE stream과 web progress UI`.

- [ ] **Step 5: Verify docs and harness**

Run:

```bash
pytest packages/harness/tests/test_e2e.py -q
rg -n "ReAct review/correction contract|job progress SSE stream과 web progress UI|실제 GPT-5.5 기반 ReAct planner" docs/product/mvp-roadmap.md docs/product/mvp-release-checklist.md
```

Expected: test PASS and all phrases found.

- [ ] **Step 6: Commit Task 4**

```bash
git add packages/harness/tests/test_e2e.py docs/product/mvp-roadmap.md docs/product/mvp-release-checklist.md
git commit -m "docs(product): update react review roadmap status"
```

---

### Task 5: Verification, Review, Push, And PR

**Files:**
- No planned production edits.

- [ ] **Step 1: Run workflow tests**

Run:

```bash
pytest packages/workflow/tests -q
```

Expected: PASS.

- [ ] **Step 2: Run API and harness tests**

Run:

```bash
pytest apps/api/tests packages/harness/tests -q
```

Expected: PASS.

- [ ] **Step 3: Run Python suite without API env**

Run:

```bash
CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/spec/tests packages/workflow/tests -q
```

Expected: PASS.

- [ ] **Step 4: Verify no SSE/Web/OpenAI-image scope creep**

Run:

```bash
git diff --name-only main..HEAD
rg -n "EventSource|text/event-stream|gpt-image-2|Images API|chain-of-thought|raw model output|OPENAI_API_KEY" packages/workflow apps/api packages/harness docs/product
```

Expected:

- No files under `apps/web`.
- No `text/event-stream` or `EventSource`.
- Any `gpt-image-2`, `chain-of-thought`, or raw model output matches are documentation exclusions only, not runtime code.
- No progress event payload includes source image paths or API keys.

- [ ] **Step 5: Run diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 6: Request reviews**

Use `superpowers:requesting-code-review` with two reviewers:

- Spec compliance reviewer:
  - Compare branch against `docs/superpowers/specs/2026-06-22-react-review-workflow-contract-design.md`.
  - Verify no real GPT-5.5 call, no SSE endpoint, no web UI, no image generation API.
  - Verify progress event allowlist and no raw model/prompt/path/API key leak.

- Code quality reviewer:
  - Review model boundaries, workflow routing clarity, artifact persistence compatibility, and test robustness.

- [ ] **Step 7: Address review findings**

For each Critical or Important finding:

1. Reproduce with a failing test or exact command.
2. Patch only relevant files.
3. Run the narrow test.
4. Run the affected full verification command.
5. Commit with:

```bash
git commit -m "fix(workflow): address react review contract finding"
```

- [ ] **Step 8: Push branch**

Run:

```bash
git status --short
git push -u origin feat/react-review-workflow-contract
```

Expected: branch pushes to origin.

- [ ] **Step 9: Create PR**

PR title:

```text
feat(workflow): add ReAct review contract and progress artifacts
```

PR body:

```markdown
## 요약
- ReAct review/correction workflow의 tool decision, eval gate, review attempt, progress event contract를 추가했습니다.
- 기존 mock workflow가 contract-backed review loop로 endpoint mismatch를 자동 수정하고 승인하도록 연결했습니다.
- API run 결과에 `review_correction`과 `progress_events` artifact를 저장하고 조회 endpoint를 추가했습니다.
- 실제 GPT-5.5 호출, SSE endpoint, web progress UI, image generation API는 이번 범위에서 제외했습니다.

## 검증
- [ ] `pytest packages/workflow/tests -q`
- [ ] `pytest apps/api/tests packages/harness/tests -q`
- [ ] `CLEANSOLVE_API_ENV_FILE=/tmp/cleansolve-no-env python -m pytest apps/api/tests packages/ai/tests packages/harness/tests packages/spec/tests packages/workflow/tests -q`
- [ ] `git diff --check`

## 참고
- Progress event는 allowlist된 한국어 message만 사용하며 raw model output, prompt, hidden reasoning, source image path, API key를 포함하지 않습니다.
- 다음 milestone은 `GET /jobs/{job_id}/events` SSE endpoint와 web progress UI입니다.
```
