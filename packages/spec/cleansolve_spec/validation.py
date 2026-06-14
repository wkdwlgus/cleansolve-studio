from math import isfinite
from numbers import Real

from .models import CandidateSpec, ValidationIssue, ValidationReport

DIMENSION_TYPES = {"dimension_line", "dimension_curve", "freehand_dimension_marker"}


def _bbox_inside_page(bbox: list[float], width: int, height: int) -> bool:
    x1, y1, x2, y2 = bbox
    return (
        all(isfinite(value) for value in bbox)
        and 0 <= x1 <= x2 <= width
        and 0 <= y1 <= y2 <= height
    )


def _point_inside_page(point: object, width: int, height: int) -> bool:
    if not isinstance(point, list) or len(point) != 2:
        return False

    x, y = point
    if not isinstance(x, Real) or not isinstance(y, Real):
        return False
    if isinstance(x, bool) or isinstance(y, bool):
        return False

    return isfinite(x) and isfinite(y) and 0 <= x <= width and 0 <= y <= height


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

    for region in spec.regions:
        if not _bbox_inside_page(region.bbox, spec.page.width, spec.page.height):
            issues.append(
                ValidationIssue(
                    issue_id=f"issue_{region.id}_bbox",
                    type="region_bbox_out_of_bounds",
                    severity="high",
                    message="Region bbox must stay inside the page.",
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

        if not _bbox_inside_page(element.evidence.bbox, spec.page.width, spec.page.height):
            issues.append(
                ValidationIssue(
                    issue_id=f"issue_{element.id}_evidence_bbox",
                    type="evidence_bbox_out_of_bounds",
                    severity="high",
                    element_id=element.id,
                    message="Evidence bbox must stay inside the page.",
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
            else:
                for anchor_name in ("target_anchor_start", "target_anchor_end"):
                    if not _point_inside_page(
                        element.geometry[anchor_name],
                        spec.page.width,
                        spec.page.height,
                    ):
                        issues.append(
                            ValidationIssue(
                                issue_id=f"issue_{element.id}_{anchor_name}",
                                type="invalid_dimension_target_anchor",
                                severity="high",
                                element_id=element.id,
                                message="Dimension target anchors must be finite two-number points inside the page.",
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
            elif has_label and not _point_inside_page(
                element.geometry["label_anchor"],
                spec.page.width,
                spec.page.height,
            ):
                issues.append(
                    ValidationIssue(
                        issue_id=f"issue_{element.id}_label_anchor",
                        type="invalid_dimension_label_anchor",
                        severity="medium",
                        element_id=element.id,
                        message="Dimension label anchors must be finite two-number points inside the page.",
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
