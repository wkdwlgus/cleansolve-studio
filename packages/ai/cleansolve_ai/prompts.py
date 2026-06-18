SUPPORTED_PRIMITIVES = [
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

ANALYSIS_DEVELOPER_PROMPT = """
You create CleanSolve Studio CandidateSpec JSON for deterministic overlay rendering.
The original problem image is the source of truth.
Use the teacher solution image only to infer handwritten solution marks, formulas, labels, highlights, arrows, and dimension markers.
Do not regenerate the whole image.
Return only JSON that matches the provided schema.
When unsure, do not guess. Set needs_review=true, requires_human_review=true, or add an uncertainty.
Use style.source=system_builtin, style.preset_id=default_pretty_handwriting, and style.preset_version=v1.
Use deterministic element id prefixes such as el_formula_, el_arrow_, el_dimension_, el_note_, and el_unsupported_.
Set page width and height from the original problem image pixel dimensions.
Preserve source image artifact ids exactly in source_images.
Separate target anchors from visible strokes for dimension markers.
Never include API keys, local file paths, original filenames, or user personal information in the JSON.
""".strip()


def build_analysis_user_prompt(
    *,
    job_id: str,
    problem_image_artifact_id: str,
    teacher_solution_image_artifact_id: str,
) -> str:
    primitive_list = ", ".join(SUPPORTED_PRIMITIVES)
    return "\n".join(
        [
            f"job_id: {job_id}",
            f"problem_image_artifact_id: {problem_image_artifact_id}",
            f"teacher_solution_image_artifact_id: {teacher_solution_image_artifact_id}",
            f"supported_primitives: {primitive_list}",
            "review_policy: expose only requires_human_review=true items to users; needs_review is internal.",
            "Return a CandidateSpec with version=1 and matching source_images ids.",
        ]
    )
