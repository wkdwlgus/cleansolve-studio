from langgraph.graph import END, StateGraph

from .nodes import (
    analyze_sources,
    apply_correction,
    decide_human_review,
    inspect_render,
    load_style_preset,
    plan_correction,
    require_revision,
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
    graph.add_node("require_revision", require_revision)

    graph.set_entry_point("load_style_preset")
    graph.add_edge("load_style_preset", "analyze_sources")
    graph.add_edge("analyze_sources", "validate_spec")
    graph.add_conditional_edges(
        "validate_spec",
        _route_after_validation,
        {
            "render_preview": "render_preview",
            "require_revision": "require_revision",
        },
    )
    graph.add_edge("render_preview", "inspect_render")
    graph.add_conditional_edges(
        "inspect_render",
        _route_after_inspection,
        {
            "plan_correction": "plan_correction",
            "decide_human_review": "decide_human_review",
            "require_revision": "require_revision",
        },
    )
    graph.add_edge("plan_correction", "apply_correction")
    graph.add_edge("apply_correction", "validate_spec")
    graph.add_edge("decide_human_review", END)
    graph.add_edge("require_revision", END)
    return graph.compile()


def run_mock_workflow(
    job_id: str,
    *,
    max_revision_attempts: int = 2,
    candidate_spec_override=None,
    correction_patch_override: dict[str, object] | None = None,
) -> WorkflowState:
    app = build_graph()
    initial_state = {
        "job_id": job_id,
        "status": "CREATED",
        "status_history": ["CREATED"],
        "validation_reports": [],
        "correction_plans": [],
        "revision_attempts": 0,
        "max_revision_attempts": max_revision_attempts,
        "review_items": [],
        "inspection_issue": None,
    }
    if candidate_spec_override is not None:
        initial_state["candidate_spec"] = candidate_spec_override
    if correction_patch_override is not None:
        initial_state["correction_patch_override"] = correction_patch_override

    return app.invoke(initial_state)


def _route_after_validation(state: WorkflowState) -> str:
    if state["validation_reports"][-1].passed:
        return "render_preview"
    return "require_revision"


def _route_after_inspection(state: WorkflowState) -> str:
    if state.get("inspection_issue") is None:
        return "decide_human_review"
    if state.get("revision_attempts", 0) >= state.get("max_revision_attempts", 2):
        return "require_revision"
    return "plan_correction"
