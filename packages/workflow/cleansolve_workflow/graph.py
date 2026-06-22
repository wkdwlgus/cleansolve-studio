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
            "inspect_render": "inspect_render",
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
    source_image_artifact_ids: dict[str, str | None] | None = None,
    source_image_paths: dict[str, str] | None = None,
    analysis_client_kind: str = "mock",
    openai_api_key: str | None = None,
    openai_model_analysis: str = "gpt-5.5",
    openai_analysis_image_detail: str = "auto",
    openai_analysis_timeout_seconds: int = 60,
    analysis_client_override=None,
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
        "review_attempts": [],
        "progress_events": [],
        "review_tool_decisions": [],
        "review_event_sequence": 0,
        "revision_attempts": 0,
        "max_revision_attempts": max_revision_attempts,
        "review_items": [],
        "inspection_issue": None,
        "analysis_client_kind": analysis_client_kind,
        "openai_api_key": openai_api_key,
        "openai_model_analysis": openai_model_analysis,
        "openai_analysis_image_detail": openai_analysis_image_detail,
        "openai_analysis_timeout_seconds": openai_analysis_timeout_seconds,
    }
    if candidate_spec_override is not None:
        initial_state["candidate_spec"] = candidate_spec_override
    if correction_patch_override is not None:
        initial_state["correction_patch_override"] = correction_patch_override
    if source_image_artifact_ids is not None:
        initial_state["source_image_artifact_ids"] = source_image_artifact_ids
    if source_image_paths is not None:
        initial_state["source_image_paths"] = source_image_paths
    if analysis_client_override is not None:
        initial_state["analysis_client_override"] = analysis_client_override

    return app.invoke(initial_state)


def _route_after_validation(state: WorkflowState) -> str:
    if state["validation_reports"][-1].passed and state.get("rendered_preview") is not None:
        return "inspect_render"
    if state["validation_reports"][-1].passed:
        return "render_preview"
    return "require_revision"


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
