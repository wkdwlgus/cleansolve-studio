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
