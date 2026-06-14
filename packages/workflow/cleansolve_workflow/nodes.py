from copy import deepcopy

from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_renderer.overlay import render_overlay_svg
from cleansolve_spec.validation import validate_candidate_spec, visible_review_items

from .state import WorkflowState


def load_style_preset(state: WorkflowState) -> WorkflowState:
    state["style_preset"] = {
        "source": "system_builtin",
        "preset_id": "default_pretty_handwriting",
        "preset_version": "v1",
    }
    _set_status(state, "STYLE_PRESET_LOADED")
    return state


def analyze_sources(state: WorkflowState) -> WorkflowState:
    if "candidate_spec" not in state:
        state["candidate_spec"] = MockAnalysisClient().extract_candidate_spec(state["job_id"])
    _set_status(state, "SPEC_EXTRACTED")
    return state


def validate_spec(state: WorkflowState) -> WorkflowState:
    report = validate_candidate_spec(state["candidate_spec"])
    state.setdefault("validation_reports", []).append(report)
    status = "SPEC_REVALIDATING" if state.get("revision_attempts", 0) > 0 else "SPEC_VALIDATING"
    _set_status(state, status)
    return state


def render_preview(state: WorkflowState) -> WorkflowState:
    state["rendered_preview"] = render_overlay_svg(state["candidate_spec"])
    _set_status(state, "RENDERED")
    return state


def inspect_render(state: WorkflowState) -> WorkflowState:
    if state.get("revision_attempts", 0) > 0:
        state["inspection_issue"] = None
        _set_status(state, "RE_INSPECTING")
        return state

    state["inspection_issue"] = {
        "issue_id": "issue_auto_001",
        "type": "dimension_endpoint_mismatch",
        "severity": "high",
        "element_id": "el_freehand_dimension_001",
        "expected": "freehand dimension marker should represent target range from O to S",
        "actual": "visible marker appears to cover only partial range",
        "auto_correctable": True,
        "correction_action": "patch_candidate_spec_geometry",
    }
    _set_status(state, "INSPECTING")
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
                    "patch": {"geometry.label_anchor": [300, 620]},
                }
            ],
            "requires_human_review": False,
        }
    )
    _set_status(state, "CORRECTION_PLANNING")
    return state


def apply_correction(state: WorkflowState) -> WorkflowState:
    candidate_spec = deepcopy(state["candidate_spec"])
    plan = state["correction_plans"][-1]

    for action in plan["actions"]:
        if action["type"] != "spec_patch":
            continue
        _apply_spec_patch(candidate_spec, action["element_id"], action["patch"])

    state["candidate_spec"] = candidate_spec
    state["rendered_preview"] = render_overlay_svg(candidate_spec)
    state["revision_attempts"] = state.get("revision_attempts", 0) + 1
    _set_status(state, "AUTO_REVISING")
    return state


def decide_human_review(state: WorkflowState) -> WorkflowState:
    state["review_items"] = visible_review_items(state["candidate_spec"])
    _set_status(state, "NEEDS_REVIEW" if state["review_items"] else "APPROVED")
    return state


def require_revision(state: WorkflowState) -> WorkflowState:
    state["review_items"] = []
    _set_status(state, "REVISION_REQUIRED")
    return state


def _apply_spec_patch(candidate_spec, element_id: str, patch: dict[str, object]) -> None:
    for element in candidate_spec.elements:
        if element.id != element_id:
            continue
        for path, value in patch.items():
            if path.startswith("geometry."):
                element.geometry[path.removeprefix("geometry.")] = value
        element.revision_history.append(
            {
                "revision_id": "rev_001",
                "source": "auto_correction",
                "patch": patch,
            }
        )
        return


def _set_status(state: WorkflowState, status: str) -> None:
    state["status"] = status
    state.setdefault("status_history", []).append(status)
