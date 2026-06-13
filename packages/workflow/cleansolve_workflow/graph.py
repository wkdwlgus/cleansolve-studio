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
